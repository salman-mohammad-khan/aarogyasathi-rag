"""Download the two models the app needs at runtime, so the first start (or CI) does not wait for them.

    python scripts/setup.py

1. multilingual-e5-base (about 1.1 GB, Hugging Face cache): search and the curated-myth match.
2. fastText language identification lid.176.bin (about 130 MB, data/models): picks the language of emergency replies.
The document library and the search index are built separately: `python -m ingest.build_chunks` then
`python -m app.retrieval.index`.
"""
import shutil
import sys

from app.config import LANG_DETECT_MODEL, MODEL_DIR


def main():
    from huggingface_hub import snapshot_download

    print("Downloading intfloat/multilingual-e5-base ...")
    snapshot_download("intfloat/multilingual-e5-base", allow_patterns=[
        "config.json", "model.safetensors", "tokenizer.json", "tokenizer_config.json", "special_tokens_map.json",
        "sentencepiece.bpe.model"])
    target = MODEL_DIR / LANG_DETECT_MODEL
    if not target.exists():
        print(f"Downloading fastText language model {LANG_DETECT_MODEL} ...")
        import urllib.request

        MODEL_DIR.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(".part")
        urllib.request.urlretrieve(f"https://dl.fbaipublicfiles.com/fasttext/supervised-models/{LANG_DETECT_MODEL}", tmp)
        shutil.move(str(tmp), str(target))
    print("SETUP COMPLETE")


if __name__ == "__main__":
    sys.exit(main())
