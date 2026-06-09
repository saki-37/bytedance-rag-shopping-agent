import asyncio
import json
import logging
import random
import re
import time
from collections.abc import AsyncIterator
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

from app.asr_routes import router as asr_router
from app.config import get_settings
from app.data_loader import load_enriched_products, load_raw_products
from app.feedback import save_feedback
from app.llm import stream_answer
from app.models import (
    AnswerDirective,
    ChatRequest,
    ConstraintTrace,
    FeedbackRequest,
    FeedbackResponse,
    HealthResponse,
    MemoryTrace,
    PlannerTrace,
    ProductCard,
)
from app.planner import build_planned_retrieval_message
from app.retrieval import retrieve
from app.user_memory import (
    DisabledMemoryProvider,
    MEMORY_PROVIDER_DISABLED,
    build_memory_augmented_request,
    build_memory_trace,
    get_memory_provider,
    resolve_user_id,
)
from app.trace_logger import new_trace_id, write_runtime_trace

logger = logging.getLogger(__name__)
settings = get_settings()
raw_products = load_raw_products(settings.raw_data_dir)
enriched_products = load_enriched_products(settings.enriched_data_dir, raw_products)
memory_provider = get_memory_provider(settings)

app = FastAPI(title="ByteDance RAG Shopping Agent")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/assets", StaticFiles(directory=settings.image_base_path), name="assets")
app.include_router(asr_router)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        catalog_size=len(enriched_products),
        mock_llm=settings.mock_llm or not settings.llm_configured,
        llm_provider=settings.active_llm_provider,
        llm_model=settings.llm_model,
    )


@app.post("/api/chat/stream")
async def chat_stream(request: ChatRequest) -> StreamingResponse:
    trace_id = new_trace_id()

    async def events() -> AsyncIterator[str]:
        started_at = time.perf_counter()
        retrieval_build = None
        retrieval_message = request.message
        result = None
        answer_directive = None
        quick_reply: dict[str, Any] | None = None
        answer_tokens: list[str] = []
        stage_timings: dict[str, int] = {}
        memory_trace: MemoryTrace | None = None
        interaction_prefs = None
        memory_profile = None
        resolved_user_id = resolve_user_id(request)

        def mark_stage(name: str) -> None:
            stage_timings.setdefault(name, int((time.perf_counter() - started_at) * 1000))

        async def build_retrieval_context() -> tuple[Any, str, Any, AnswerDirective | None]:
            nonlocal memory_profile, memory_trace, interaction_prefs
            memory_profile = memory_provider.get_profile(resolved_user_id)
            retrieval_request, _, applied_constraints, applied_short_term_signals = build_memory_augmented_request(
                request,
                memory_profile,
            )
            provider_name = MEMORY_PROVIDER_DISABLED if isinstance(memory_provider, DisabledMemoryProvider) else settings.memory_provider
            memory_trace = build_memory_trace(
                provider=provider_name,
                user_id=resolved_user_id,
                memory_profile=memory_profile,
                applied_constraints=applied_constraints,
                applied_short_term_signals=applied_short_term_signals,
                applied_preferences=memory_profile.interaction_preferences.model_dump(mode="json"),
                skipped=[],
                fallback=None,
            )
            interaction_prefs = memory_profile.interaction_preferences
            retrieval_build_inner = await build_planned_retrieval_message(settings, retrieval_request)
            mark_stage("planner_complete_ms")
            retrieval_message_inner = retrieval_build_inner.message
            result_inner = retrieve(
                retrieval_message_inner,
                enriched_products,
                index_dir=settings.index_dir,
                memory_profile=memory_profile,
            )
            _attach_conversation_trace(result_inner.trace, retrieval_build_inner.trace)
            answer_directive_inner = _build_answer_directive(request, retrieval_build_inner.trace, result_inner.cards)
            if answer_directive_inner:
                result_inner.cards = _ordered_cards(result_inner.cards, answer_directive_inner.target_product_ids)
            mark_stage("retrieval_complete_ms")
            return retrieval_build_inner, retrieval_message_inner, result_inner, answer_directive_inner

        try:
            mark_stage("retrieving_status_sent_ms")
            yield _event("status", {"status": "retrieving", "trace_id": trace_id})
            retrieval_task = asyncio.create_task(build_retrieval_context())
            quick_reply_sent = False
            if settings.fast_first_screen_enabled:
                done, _ = await asyncio.wait(
                    {retrieval_task},
                    timeout=settings.fast_quick_reply_deadline_seconds,
                )
                if retrieval_task not in done:
                    quick_reply = _quick_reply_waiting_payload(trace_id=trace_id, request=request)
                    mark_stage("quick_reply_deadline_ms")
                    mark_stage("quick_reply_sent_ms")
                    yield _event("quick_reply", quick_reply)
                    quick_reply_sent = True
            retrieval_build, retrieval_message, result, answer_directive = await retrieval_task
            if result.clarification_question:
                quick_reply = _quick_reply_payload(
                    trace_id=trace_id,
                    request=request,
                    cards=result.cards,
                    answer_directive=answer_directive,
                    clarification_question=result.clarification_question,
                )
                if quick_reply_sent:
                    mark_stage("quick_reply_update_sent_ms")
                else:
                    mark_stage("quick_reply_sent_ms")
                yield _event("quick_reply", quick_reply)
                quick_reply_sent = True
                mark_stage("generating_status_sent_ms")
                yield _event("status", {"status": "generating", "trace_id": trace_id})
                async for token in _stream_text(result.clarification_question):
                    if not answer_tokens:
                        mark_stage("first_token_sent_ms")
                    answer_tokens.append(token)
                    yield _event("token", {"token": token})
            else:
                quick_reply = _quick_reply_payload(
                    trace_id=trace_id,
                    request=request,
                    cards=result.cards,
                    answer_directive=answer_directive,
                    clarification_question=None,
                )
                if quick_reply_sent:
                    mark_stage("quick_reply_update_sent_ms")
                else:
                    mark_stage("quick_reply_sent_ms")
                yield _event("quick_reply", quick_reply)
                quick_reply_sent = True
                mark_stage("products_sent_ms")
                yield _event("products", {"trace_id": trace_id, "products": [card.model_dump() for card in result.cards]})
                mark_stage("generating_status_sent_ms")
                yield _event("status", {"status": "generating", "trace_id": trace_id})
                async for token in stream_answer(
                    settings=settings,
                    user_message=retrieval_message,
                    history=request.history,
                    context=result.context,
                    cards=result.cards,
                    answer_directive=answer_directive,
                    interaction_preferences=interaction_prefs,
                ):
                    if not answer_tokens:
                        mark_stage("first_token_sent_ms")
                    answer_tokens.append(token)
                    yield _event("token", {"token": token})
            mark_stage("done_ready_ms")
            _write_runtime_trace_safely(
                trace_id=trace_id,
                endpoint="chat_stream",
                request=request,
                started_at=started_at,
                status="ok",
                memory_trace=memory_trace.model_dump(mode="json") if memory_trace else None,
                retrieval_message=retrieval_message,
                conversation_state=retrieval_build.trace if retrieval_build else None,
                retrieval_trace=result.trace.model_dump(mode="json") if result else None,
                answer_directive=answer_directive,
                quick_reply=quick_reply,
                stage_timings=stage_timings,
                products=result.cards if result else [],
                answer="".join(answer_tokens),
                token_count=len(answer_tokens),
                error=None,
            )
            yield _event("done", {"ok": True, "trace_id": trace_id})
        except Exception as exc:  # Keep SSE shape stable for the Android client.
            mark_stage("error_ready_ms")
            _write_runtime_trace_safely(
                trace_id=trace_id,
                endpoint="chat_stream",
                request=request,
                started_at=started_at,
                status="error",
                memory_trace=memory_trace.model_dump(mode="json") if memory_trace else None,
                retrieval_message=retrieval_message,
                conversation_state=retrieval_build.trace if retrieval_build else None,
                retrieval_trace=result.trace.model_dump(mode="json") if result else None,
                answer_directive=answer_directive,
                quick_reply=quick_reply,
                stage_timings=stage_timings,
                products=result.cards if result else [],
                answer="".join(answer_tokens),
                token_count=len(answer_tokens),
                error=str(exc),
            )
            yield _event("error", {"message": str(exc), "trace_id": trace_id})

    return StreamingResponse(events(), media_type="text/event-stream")


@app.post("/api/debug/retrieve")
async def debug_retrieve(request: ChatRequest) -> dict:
    trace_id = new_trace_id()
    started_at = time.perf_counter()
    resolved_user_id = resolve_user_id(request)
    memory_profile = memory_provider.get_profile(resolved_user_id)
    retrieval_request, _, applied_constraints, applied_short_term_signals = build_memory_augmented_request(request, memory_profile)
    provider_name = MEMORY_PROVIDER_DISABLED if isinstance(memory_provider, DisabledMemoryProvider) else settings.memory_provider
    memory_trace = build_memory_trace(
        provider=provider_name,
        user_id=resolved_user_id,
        memory_profile=memory_profile,
        applied_constraints=applied_constraints,
        applied_short_term_signals=applied_short_term_signals,
        applied_preferences=memory_profile.interaction_preferences.model_dump(mode="json"),
        skipped=[],
        fallback=None,
    )
    retrieval_build = await build_planned_retrieval_message(settings, retrieval_request)
    retrieval_message = retrieval_build.message
    result = retrieve(
        retrieval_message,
        enriched_products,
        index_dir=settings.index_dir,
        memory_profile=memory_profile,
    )
    _attach_conversation_trace(result.trace, retrieval_build.trace)
    answer_directive = _build_answer_directive(request, retrieval_build.trace, result.cards)
    if answer_directive:
        result.cards = _ordered_cards(result.cards, answer_directive.target_product_ids)
    _write_runtime_trace_safely(
        trace_id=trace_id,
        endpoint="debug_retrieve",
        request=request,
        started_at=started_at,
        status="ok",
        memory_trace=memory_trace.model_dump(mode="json"),
        retrieval_message=retrieval_message,
        conversation_state=retrieval_build.trace,
        retrieval_trace=result.trace.model_dump(mode="json"),
        answer_directive=answer_directive,
        quick_reply=None,
        stage_timings=None,
        products=result.cards,
        answer=None,
        token_count=0,
        error=None,
    )
    return {
        "trace_id": trace_id,
        "retrieval_message": retrieval_message,
        "conversation_state": retrieval_build.trace,
        "products": [card.model_dump() for card in result.cards],
        "answer_directive": answer_directive.model_dump() if answer_directive else None,
        "clarification_question": result.clarification_question,
        "trace": result.trace.model_dump(),
    }


@app.post("/api/feedback", response_model=FeedbackResponse)
def submit_feedback(request: FeedbackRequest) -> FeedbackResponse:
    return save_feedback(settings, request)


def _event(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _quick_reply_payload(
    *,
    trace_id: str,
    request: ChatRequest,
    cards: list[ProductCard],
    answer_directive: AnswerDirective | None,
    clarification_question: str | None,
) -> dict[str, Any]:
    return {
        "trace_id": trace_id,
        "text": _build_quick_reply_text(
            message=request.message,
            cards=cards,
            answer_directive=answer_directive,
            clarification_question=clarification_question,
        ),
        "ephemeral": True,
        "source": "template",
    }


def _quick_reply_waiting_payload(*, trace_id: str, request: ChatRequest) -> dict[str, Any]:
    return {
        "trace_id": trace_id,
        "text": _build_quick_reply_waiting_text(request.message),
        "ephemeral": True,
        "source": "deadline_fallback",
    }


def _build_quick_reply_waiting_text(message: str) -> str:
    dimensions = _quick_reply_dimensions(message)
    templates = [
        "我先接住你的需求，正在查商品资料和约束；如果需要推荐，我会先按{dimensions}来核对。",
        "收到，我先不急着下结论，正在核对商品资料、限制条件和可比维度。",
        "我在先过一遍你的条件，稍后会把候选和依据一起补上；重点会看{dimensions}。",
        "我先把需求记住了，正在找匹配候选；会优先看{dimensions}，再给出推荐依据。",
    ]
    return random.choice(templates).format(dimensions=dimensions)


def _build_quick_reply_text(
    *,
    message: str,
    cards: list[ProductCard],
    answer_directive: AnswerDirective | None,
    clarification_question: str | None,
) -> str:
    if clarification_question:
        return "我先接住你的需求，下面会先确认一个关键条件，避免直接乱推商品。"

    if answer_directive and answer_directive.mode == "compare":
        subject = _quick_card_subject(cards, fallback="这几款候选")
        return f"我正在把{subject}放在一起比较，先看价格、适合人群和注意事项，再给你收敛建议。"

    if cards:
        subject = _quick_card_subject(cards, fallback=f"{min(len(cards), 3)} 款候选")
        dimensions = _quick_reply_dimensions(message)
        return f"我正在浏览{subject}这几款候选，先按{dimensions}做取舍，再补齐推荐依据。"

    return "我先接住你的需求，下面会先确认关键条件，避免直接乱推商品。"


def _quick_card_subject(cards: list[ProductCard], fallback: str) -> str:
    names = []
    for card in cards[:3]:
        label = card.brand.strip() or card.sub_category.strip() or card.category.strip()
        if label and label not in names:
            names.append(label)
    if not names:
        return fallback
    if len(names) == 1:
        return f"{names[0]}这类候选"
    return "、".join(names)


def _quick_reply_dimensions(message: str) -> str:
    dimensions: list[str] = []
    if any(term in message for term in ["预算", "元", "便宜", "贵", "价格", "性价比"]):
        dimensions.append("价格")
    if any(term in message for term in ["通勤", "早八", "办公室", "户外", "运动", "上课", "出差", "度假", "场景"]):
        dimensions.append("使用场景")
    if any(term in message for term in ["敏感", "过敏", "不要", "不想", "避开", "风险", "刺激"]):
        dimensions.append("注意事项")
    if any(term in message for term in ["适合", "人群", "肤质", "油皮", "干皮", "学生", "妈妈"]):
        dimensions.append("适合人群")
    if not dimensions:
        dimensions = ["价格", "适合人群", "注意事项"]
    return "、".join(list(dict.fromkeys(dimensions))[:3])


async def _stream_text(text: str) -> AsyncIterator[str]:
    for char in text:
        yield char
        await asyncio.sleep(0.005)


def _write_runtime_trace_safely(
    *,
    trace_id: str,
    endpoint: str,
    request: ChatRequest,
    memory_trace: dict[str, Any] | None,
    started_at: float,
    status: str,
    retrieval_message: str | None,
    conversation_state: dict | None,
    retrieval_trace: dict | None,
    answer_directive: AnswerDirective | None,
    quick_reply: dict[str, Any] | None,
    stage_timings: dict[str, int] | None,
    products: list[ProductCard],
    answer: str | None,
    token_count: int,
    error: str | None,
) -> None:
    try:
        write_runtime_trace(
            settings.trace_dir,
            {
                "trace_id": trace_id,
                "endpoint": endpoint,
                "status": status,
                "request": _request_trace_snapshot(request),
                "memory_trace": memory_trace,
                "settings": _settings_trace_snapshot(),
                "retrieval_message": retrieval_message,
                "conversation_state": conversation_state,
                "retrieval_trace": retrieval_trace,
                "answer_directive": answer_directive.model_dump(mode="json") if answer_directive else None,
                "quick_reply": quick_reply,
                "stage_timings_ms": stage_timings or {},
                "products": [card.model_dump(mode="json") for card in products],
                "answer": answer,
                "token_count": token_count,
                "answer_char_count": len(answer) if answer else 0,
                "error": error,
                "latency_ms": int((time.perf_counter() - started_at) * 1000),
            },
        )
    except Exception:
        logger.warning("Failed to write runtime trace", exc_info=True)


def _request_trace_snapshot(request: ChatRequest) -> dict[str, Any]:
    return {
        "message": request.message,
        "user_id": request.user_id,
        "conversation_id": request.conversation_id,
        "history": [item.model_dump(mode="json") for item in request.history],
    }


def _settings_trace_snapshot() -> dict[str, Any]:
    return {
        "mock_llm": settings.mock_llm,
        "llm_provider": settings.active_llm_provider,
        "has_llm_key": bool(settings.llm_api_key),
        "has_llm_model": bool(settings.llm_model),
        "llm_model": settings.llm_model,
        "planner_timeout_seconds": settings.planner_timeout_seconds,
        "memory_provider": settings.memory_provider,
        "fast_first_screen_enabled": settings.fast_first_screen_enabled,
        "fast_quick_reply_deadline_seconds": settings.fast_quick_reply_deadline_seconds,
    }


def _attach_conversation_trace(retrieval_trace, conversation_trace: dict) -> None:
    constraint_trace = conversation_trace.get("constraint_trace")
    if constraint_trace:
        retrieval_trace.constraint_trace = ConstraintTrace(**constraint_trace)
    planner_trace = conversation_trace.get("planner_trace")
    if planner_trace:
        retrieval_trace.planner_trace = PlannerTrace(**planner_trace)


def _build_answer_directive(
    request: ChatRequest,
    retrieval_trace: dict,
    cards: list[ProductCard],
) -> AnswerDirective | None:
    if not cards or not _is_comparison_request(request.message, retrieval_trace):
        return None
    target_product_ids = _comparison_target_product_ids(request, retrieval_trace, cards)
    if len(target_product_ids) < 2:
        target_product_ids = [card.product_id for card in cards[:3]]
    if len(target_product_ids) < 2:
        return None
    return AnswerDirective(
        target_product_ids=target_product_ids[:3],
        focus_dimensions=_comparison_focus_dimensions(request.message, retrieval_trace),
    )


def _is_comparison_request(message: str, retrieval_trace: dict) -> bool:
    normalized_message = re.sub(r"比较(合适|适合|舒服|稳妥|好|划算|便宜|贵|大|小)", "", message)
    planner_plan = (
        retrieval_trace.get("planner_trace", {})
        .get("validated_plan", {})
        .get("comparison_plan", {})
    )
    if planner_plan.get("enabled"):
        return True
    constraint_trace = retrieval_trace.get("constraint_trace", {})
    if constraint_trace.get("effective", {}).get("comparison_mode"):
        return True
    return any(term in normalized_message for term in ["对比", "比较", "怎么选", "选哪个", "哪个更", "哪款更", "更适合", "二选一", "区别"])


def _comparison_target_product_ids(
    request: ChatRequest,
    retrieval_trace: dict,
    cards: list[ProductCard],
) -> list[str]:
    card_ids = [card.product_id for card in cards]
    planner_plan = (
        retrieval_trace.get("planner_trace", {})
        .get("validated_plan", {})
        .get("comparison_plan", {})
    )
    planner_ids = [
        product_id
        for product_id in planner_plan.get("target_product_ids", [])
        if product_id in card_ids
    ]
    if len(planner_ids) >= 2:
        return list(dict.fromkeys(planner_ids))

    history_ids = _latest_history_product_ids(request)
    indexed_ids = _comparison_indexed_product_ids(request.message, history_ids)
    indexed_ids = [product_id for product_id in indexed_ids if product_id in card_ids]
    if len(indexed_ids) >= 2:
        return indexed_ids

    referenced_ids = (
        retrieval_trace.get("constraint_trace", {})
        .get("effective", {})
        .get("referenced_product_ids", [])
    )
    referenced_ids = [product_id for product_id in referenced_ids if product_id in card_ids]
    if len(referenced_ids) >= 2:
        return list(dict.fromkeys(referenced_ids))

    return card_ids[:3]


def _comparison_indexed_product_ids(message: str, product_ids: list[str]) -> list[str]:
    if not product_ids:
        return []
    if _references_first_two_products(message):
        return product_ids[:2]
    indexes = _comparison_indexes(message)
    if indexes:
        return [product_ids[index] for index in indexes if 0 <= index < len(product_ids)]
    if _references_all_previous_products(message):
        return product_ids
    return []


def _comparison_indexes(message: str) -> list[int]:
    markers = [
        (r"(第一|第1(?:个|款|件)?|1(?:号|个|款|件))", 0),
        (r"(第二|第2(?:个|款|件)?|2(?:号|个|款|件))", 1),
        (r"(第三|第3(?:个|款|件)?|3(?:号|个|款|件))", 2),
    ]
    indexes = [index for pattern, index in markers if re.search(pattern, message)]
    if _has_numbered_comparison_context(message):
        bare_markers = [
            (r"(?<!\d)[1一](?!\d)", 0),
            (r"(?<!\d)[2二](?!\d)", 1),
            (r"(?<!\d)[3三](?!\d)", 2),
        ]
        indexes.extend(index for pattern, index in bare_markers if re.search(pattern, message))
    if indexes and any(term in message for term in ["它", "这个", "这款", "刚才那个", "刚才那款", "上一款", "上一个"]):
        indexes.insert(0, 0)
    return list(dict.fromkeys(indexes))


def _has_numbered_comparison_context(message: str) -> bool:
    return any(term in message for term in ["比较", "对比", "1和", "1 和", "一和", "一 和", "和2", "和 2", "和二", "和 二"])


def _comparison_focus_dimensions(message: str, retrieval_trace: dict) -> list[str]:
    planner_dimensions = (
        retrieval_trace.get("planner_trace", {})
        .get("validated_plan", {})
        .get("comparison_plan", {})
        .get("focus_dimensions", [])
    )
    dimensions = [str(item).strip() for item in planner_dimensions if str(item).strip()]
    candidates = [
        ("价格", ["价格", "预算", "便宜", "贵", "性价比"]),
        ("适合肤质", ["肤质", "油皮", "干皮", "敏感", "混油", "混干"]),
        ("通勤场景", ["通勤", "上班", "日常"]),
        ("户外/防水防汗", ["户外", "防水", "防汗", "海边", "运动"]),
        ("补涂方便度", ["补涂", "便携", "随身"]),
        ("注意事项", ["注意", "风险", "过敏", "敏感", "避开"]),
    ]
    for label, signals in candidates:
        if any(signal in message for signal in signals):
            dimensions.append(label)
    if not dimensions:
        dimensions = ["价格", "适合肤质/人群", "使用场景", "核心优点", "注意事项", "选择建议"]
    return list(dict.fromkeys(dimensions))[:6]


def _latest_history_product_ids(request: ChatRequest) -> list[str]:
    for item in reversed(request.history):
        if item.role != "assistant":
            continue
        product_ids = [product_id for product_id in item.product_ids if product_id]
        if product_ids:
            return product_ids
    return []


def _references_first_two_products(message: str) -> bool:
    return bool(re.search(r"(前两|前二|前2|前两个|前二个|前两款|前2款)", message))


def _references_all_previous_products(message: str) -> bool:
    if not any(term in message for term in ["对比", "比较", "怎么选", "哪个更", "哪款更", "区别"]):
        return False
    return any(term in message for term in ["这几个", "这些", "它们", "刚才这些", "刚才几个", "全部", "都"])


def _ordered_cards(cards: list[ProductCard], target_product_ids: list[str]) -> list[ProductCard]:
    order = {product_id: index for index, product_id in enumerate(target_product_ids)}
    return sorted(cards, key=lambda card: order.get(card.product_id, len(order)))
