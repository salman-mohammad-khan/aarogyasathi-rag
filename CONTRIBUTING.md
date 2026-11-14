# Contributing

Thanks for your interest in AarogyaSathi. Issues and pull requests are welcome.

## Set up

```bash
git clone https://github.com/salman-mohammad-khan/aarogyasathi-rag.git
cd aarogyasathi-rag
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # optional: add OLLAMA_API_KEY for the hosted LLM tier
python scripts/setup.py         # one-time model download (LaBSE and the language-id model)
uvicorn app.main:app --reload --port 8000
```

Never commit `.env` or any API key.

## Workflow

- Branch from `main` and open a pull request. Do not push directly to `main`.
- Name branches `feature/<name>`, `fix/<name>`, `docs/<name>` or `test/<name>`.
- Use conventional commit messages (`feat:`, `fix:`, `docs:`, `test:`, `refactor:`, `ci:`).
- Every pull request runs the test suite in GitHub Actions. Run it locally first:

```bash
python -m pytest tests -q
python scripts/eval.py          # benchmark report
```

## Safety changes

Emergency and self-harm handling must stay rule-based and must run before any other routing. Add a regression test in
`tests/test_safety_routing.py` for any change to `app/core/safety.py`, `app/core/entities.py` or the router order.

## Deploying

Only reviewed code on `main` is deployed. See the Deployment section of the README for `scripts/deploy.sh`.
