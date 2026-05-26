import asyncio
import logging
from collections.abc import AsyncIterator

from openai import AsyncOpenAI

from app.config import Settings
from app.guardrails import build_safe_answer, guard_answer
from app.models import ChatMessage, ProductCard


logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """你是一个电商智能导购 Agent。
回答必须基于提供的商品资料和商品卡片，不要编造不存在的价格、库存、优惠券、成分或功效。
如果用户需求信息不足，先用一句话追问关键条件；如果已有足够条件，给出 2-3 个推荐及原因。
需要提醒用户敏感肌、过敏、户外补涂等注意事项时，必须说明依据来自商品资料或用户评价。
只能提到“可用商品卡片”中的商品。价格只能使用商品卡片中列出的价格或用户问题中给出的预算数字。
不要输出任何库存、现货、优惠、优惠券、满减、折扣、购买链接或下单承诺。
"""


async def stream_answer(
    settings: Settings,
    user_message: str,
    history: list[ChatMessage],
    context: str,
    cards: list[ProductCard],
):
    if settings.mock_llm or not settings.ark_api_key or not settings.ark_model:
        logger.info("Streaming mock LLM response")
        async for token in _stream_text(_mock_answer(user_message, cards)):
            yield token
        return

    logger.info("Streaming Ark response with model=%s", settings.ark_model)
    try:
        raw_answer = await _collect_ark_answer(
            settings=settings,
            user_message=user_message,
            history=history,
            context=context,
            cards=cards,
        )
    except Exception as exc:
        logger.warning("Ark response failed; falling back to grounded local answer: %s", exc)
        raw_answer = ""
    guardrail = guard_answer(raw_answer, user_message=user_message, cards=cards)
    if not guardrail.passed:
        logger.warning("LLM answer blocked by generation guardrails: %s", guardrail.issues)
    async for token in _stream_text(guardrail.answer):
        yield token


async def _collect_ark_answer(
    settings: Settings,
    user_message: str,
    history: list[ChatMessage],
    context: str,
    cards: list[ProductCard],
) -> str:
    client = AsyncOpenAI(api_key=settings.ark_api_key, base_url=settings.ark_base_url)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        *[
            {"role": item.role, "content": item.content}
            for item in history[-6:]
            if item.role in {"user", "assistant"}
        ],
        {
            "role": "user",
            "content": f"用户问题：{user_message}\n\n可用商品资料：\n{context}",
        },
    ]
    stream = await client.chat.completions.create(
        model=settings.ark_model,
        messages=messages,
        stream=True,
        temperature=0.2,
    )
    logger.info("Ark stream connected")
    chunks: list[str] = []
    async for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            chunks.append(delta)
    logger.info("Ark stream completed")
    return "".join(chunks)


def _mock_answer(user_message: str, cards: list[ProductCard]) -> str:
    if "护肤品" in user_message and not any(word in user_message for word in ["油皮", "干皮", "敏感", "预算", "防晒", "修护"]):
        return "我可以先帮你缩小范围：你更在意肤质适配、预算，还是防晒/修护/控油这类具体功效？"
    return build_safe_answer(cards)


async def _stream_text(text: str) -> AsyncIterator[str]:
    for char in text:
        yield char
        await asyncio.sleep(0.01)
