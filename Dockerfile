FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt requirements-ingest.txt ./
RUN pip install --no-cache-dir "torch==2.6.0" --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r requirements.txt -r requirements-ingest.txt

COPY . .

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Models (e5, fastText language id), then the document library (downloads the official PDFs, about 210 MB) and the
# search index. Answers need Amazon Bedrock at run time: pass AWS_BEARER_TOKEN_BEDROCK (or AWS credentials) as an
# environment variable, never in the image.
RUN python scripts/setup.py && python -m ingest.build_chunks && python -m app.retrieval.index

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
