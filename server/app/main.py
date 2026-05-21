import json
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from app.config import get_settings
from app.data_loader import load_enriched_products, load_raw_products
from app.llm import stream_answer
from app.models import ChatRequest, HealthResponse
from app.retrieval import retrieve

settings = get_settings()
raw_products = load_raw_products(settings.raw_data_dir)
enriched_products = load_enriched_products(settings.enriched_beauty_path, raw_products)

app = FastAPI(title="ByteDance RAG Shopping Agent")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        catalog_size=len(enriched_products),
        mock_llm=settings.mock_llm or not settings.ark_api_key or not settings.ark_model,
    )


@app.post("/api/chat/stream")
async def chat_stream(request: ChatRequest) -> StreamingResponse:
    async def events() -> AsyncIterator[str]:
        try:
            yield _event("status", {"status": "retrieving"})
            result = retrieve(request.message, enriched_products, index_dir=settings.index_dir)
            yield _event("products", {"products": [card.model_dump() for card in result.cards]})
            yield _event("status", {"status": "generating"})
            async for token in stream_answer(
                settings=settings,
                user_message=request.message,
                history=request.history,
                context=result.context,
                cards=result.cards,
            ):
                yield _event("token", {"token": token})
            yield _event("done", {"ok": True})
        except Exception as exc:  # Keep SSE shape stable for the Android client.
            yield _event("error", {"message": str(exc)})

    return StreamingResponse(events(), media_type="text/event-stream")


def _event(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
