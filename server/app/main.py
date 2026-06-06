import asyncio
import json
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.conversation_state import build_retrieval_message
from app.data_loader import load_enriched_products, load_raw_products
from app.feedback import save_feedback
from app.llm import stream_answer
from app.models import ChatRequest, ConstraintTrace, FeedbackRequest, FeedbackResponse, HealthResponse
from app.retrieval import retrieve

settings = get_settings()
raw_products = load_raw_products(settings.raw_data_dir)
enriched_products = load_enriched_products(settings.enriched_data_dir, raw_products)

app = FastAPI(title="ByteDance RAG Shopping Agent")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/assets", StaticFiles(directory=settings.image_base_path), name="assets")


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
            retrieval_build = build_retrieval_message(request)
            retrieval_message = retrieval_build.message
            result = retrieve(retrieval_message, enriched_products, index_dir=settings.index_dir)
            _attach_conversation_trace(result.trace, retrieval_build.trace)
            yield _event("status", {"status": "generating"})
            if result.clarification_question:
                async for token in _stream_text(result.clarification_question):
                    yield _event("token", {"token": token})
            else:
                yield _event("products", {"products": [card.model_dump() for card in result.cards]})
                async for token in stream_answer(
                    settings=settings,
                    user_message=retrieval_message,
                    history=request.history,
                    context=result.context,
                    cards=result.cards,
                ):
                    yield _event("token", {"token": token})
            yield _event("done", {"ok": True})
        except Exception as exc:  # Keep SSE shape stable for the Android client.
            yield _event("error", {"message": str(exc)})

    return StreamingResponse(events(), media_type="text/event-stream")


@app.post("/api/debug/retrieve")
def debug_retrieve(request: ChatRequest) -> dict:
    retrieval_build = build_retrieval_message(request)
    retrieval_message = retrieval_build.message
    result = retrieve(retrieval_message, enriched_products, index_dir=settings.index_dir)
    _attach_conversation_trace(result.trace, retrieval_build.trace)
    return {
        "retrieval_message": retrieval_message,
        "conversation_state": retrieval_build.trace,
        "products": [card.model_dump() for card in result.cards],
        "clarification_question": result.clarification_question,
        "trace": result.trace.model_dump(),
    }


@app.post("/api/feedback", response_model=FeedbackResponse)
def submit_feedback(request: FeedbackRequest) -> FeedbackResponse:
    return save_feedback(settings, request)


def _event(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


async def _stream_text(text: str) -> AsyncIterator[str]:
    for char in text:
        yield char
        await asyncio.sleep(0.005)


def _attach_conversation_trace(retrieval_trace, conversation_trace: dict) -> None:
    constraint_trace = conversation_trace.get("constraint_trace")
    if constraint_trace:
        retrieval_trace.constraint_trace = ConstraintTrace(**constraint_trace)
