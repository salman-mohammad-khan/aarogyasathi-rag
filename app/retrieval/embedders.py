"""Embedding models: turn text into vectors so that texts with similar meaning get similar vectors.

Three models are compared in S2 (eval/retrieval_bakeoff.py); each one has the same two methods:

    embed_documents(texts) -> matrix, one row per text (used once, to index the library)
    embed_query(text)      -> one vector (used for every user question)

All vectors are L2-normalised, so the similarity of a question and a chunk is a plain dot product
(this equals cosine similarity).
"""
import json
import time
from concurrent.futures import ThreadPoolExecutor

import numpy as np

BATCH_SIZE = 32


class _LocalModel:
    """A Hugging Face model that runs on this machine (GPU when there is one, otherwise CPU)."""

    model_name = ""
    max_tokens = 512

    def __init__(self):
        import torch
        from transformers import AutoModel, AutoTokenizer

        self._torch = torch
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        self.model = AutoModel.from_pretrained(self.model_name).to(self.device).eval()

    def _pool(self, output, mask):
        raise NotImplementedError

    def _encode(self, texts: list[str]) -> np.ndarray:
        rows = []
        for start in range(0, len(texts), BATCH_SIZE):
            batch = self.tokenizer(texts[start:start + BATCH_SIZE], padding=True, truncation=True,
                                   max_length=self.max_tokens, return_tensors="pt").to(self.device)
            with self._torch.no_grad():
                vectors = self._pool(self.model(**batch), batch["attention_mask"])
            vectors = self._torch.nn.functional.normalize(vectors, p=2, dim=1)
            rows.append(vectors.float().cpu().numpy())
        return np.vstack(rows)


class E5Embedder(_LocalModel):
    """intfloat/multilingual-e5-base (Microsoft, 2024): 100 languages, 768 numbers per text.

    The model was trained with the prefixes "query: " and "passage: ", and gives worse results without them.
    The vector is the average over all tokens ("mean pooling"), as in the model card.
    """

    name = "e5-base"
    model_name = "intfloat/multilingual-e5-base"
    max_tokens = 512

    def _pool(self, output, mask):
        mask = mask.unsqueeze(-1).float()
        return (output.last_hidden_state * mask).sum(1) / mask.sum(1).clamp(min=1e-9)

    def embed_documents(self, texts):
        return self._encode(["passage: " + t for t in texts])

    def embed_query(self, text):
        return self._encode(["query: " + text])[0]


class LaBSEEmbedder(_LocalModel):
    """sentence-transformers/LaBSE (Google, 2020): 109 languages, 768 numbers, built to match translations.

    The official vector is the pooled [CLS] output (pooler_output), not the token average that v1 used.
    """

    name = "labse"
    model_name = "sentence-transformers/LaBSE"
    max_tokens = 256

    def _pool(self, output, mask):
        return output.pooler_output

    def embed_documents(self, texts):
        return self._encode(texts)

    def embed_query(self, text):
        return self._encode([text])[0]


class TitanEmbedder:
    """Amazon Titan Text Embeddings v2 on Bedrock (Mumbai region): 1,024 numbers, one API call per text.

    Price: $0.02 per million input tokens (embedding the whole library costs about 2 cents).
    Credentials come from the normal AWS setup (environment or ~/.aws), read by boto3.
    """

    name = "titan-v2"
    model_id = "amazon.titan-embed-text-v2:0"
    dimensions = 1024
    workers = 2  # parallel calls when indexing; the account allows about 1 call per second (8 workers were throttled)

    def __init__(self, region: str = "ap-south-1"):
        import boto3
        from botocore.config import Config

        # "adaptive" retries wait and slow down by themselves when Bedrock says "too many requests".
        retries = Config(retries={"max_attempts": 10, "mode": "adaptive"})
        self.client = boto3.client("bedrock-runtime", region_name=region, config=retries)

    def _embed_one(self, text: str) -> list[float]:
        from botocore.exceptions import ClientError

        body = json.dumps({"inputText": text[:20000], "dimensions": self.dimensions, "normalize": True})
        for attempt in range(6):
            try:
                response = self.client.invoke_model(modelId=self.model_id, body=body)
                return json.loads(response["body"].read())["embedding"]
            except ClientError as error:
                if error.response["Error"]["Code"] != "ThrottlingException" or attempt == 5:
                    raise
                time.sleep(2 ** attempt)  # still throttled after boto3's own retries: wait 1, 2, 4, 8, 16 s

    def embed_documents(self, texts):
        with ThreadPoolExecutor(self.workers) as pool:
            return np.array(list(pool.map(self._embed_one, texts)), dtype=np.float32)

    def embed_query(self, text):
        return np.array(self._embed_one(text), dtype=np.float32)


EMBEDDERS = {cls.name: cls for cls in (E5Embedder, LaBSEEmbedder, TitanEmbedder)}


def passage_text(chunk: dict) -> str:
    """The text that is embedded for a chunk: document title and section first, so a chunk that only says
    "Give ORS after every loose stool" still carries what it is about (e.g. "IDCF Guidelines, Diarrhoea")."""
    head = chunk["title"] + (f". {chunk['section']}" if chunk.get("section") else "")
    return f"{head}\n{chunk['text']}"
