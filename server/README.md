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

With `MOCK_LLM=true`, the server returns a local streaming response without calling Ark.
