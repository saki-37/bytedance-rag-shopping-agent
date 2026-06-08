# Server

FastAPI backend for the RAG shopping agent MVP.

## Run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example ../.env
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Default local settings should use `LLM_PROVIDER=ark` and `MOCK_LLM=false` with a real Ark key and model endpoint. For faster demos, set `LLM_PROVIDER=yunwu` with `YUNWU_API_KEY` and `YUNWU_MODEL`; the planner and answer generator will both use that OpenAI-compatible provider. With `MOCK_LLM=true`, the server returns a local streaming response without calling a model API; use that only for offline structure checks or no-key environments.
