import asyncio
import logging
from collections.abc import AsyncIterator

from openai import AsyncOpenAI

from app.config import Settings
from app.guardrails import build_safe_answer, guard_answer
from app.guardrails import GenerationGuardrailResult
from app.models import ChatMessage, ProductCard


logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """你是一个电商智能导购 Agent。
回答必须基于提供的商品资料和商品卡片，不要编造不存在的价格、库存、优惠券、成分或功效。
如果用户需求信息不足，先用一句话追问关键条件；如果已有足够条件，给出 2-3 个推荐及原因。
如果用户明确要求“对比/怎么选/哪个更适合”，必须按价格、适合人群或场景、关键优点、注意事项给出结构化比较，并给出一句保守选择建议。
需要提醒用户敏感肌、过敏、户外补涂等注意事项时，必须说明依据来自商品资料或用户评价。
只能提到“可用商品卡片”中的商品。价格只能使用商品卡片中列出的价格或用户问题中给出的预算数字。
不要输出任何库存、现货、优惠、优惠券、满减、折扣、购买链接或下单承诺。
当用户提出“不含/不要/避开”某类成分、肤感或风险时，如果商品资料没有明确写明“不含/无/不添加”，不要断言“没有/不会/不含”，只能说“资料中没有看到相关风险提示”或建议用户进一步核对成分表。
不要承诺“不会堵塞 / 不会长闭口 / 不会残留 / 不会过敏 / 绝对温和 / 一定安全”。如果这类说法只来自用户评价，只能说“用户评价中有人提到”，并补充“不能保证你使用后也一定如此”。
"""


async def stream_answer(
    settings: Settings,
    user_message: str,
    history: list[ChatMessage],
    context: str,
    cards: list[ProductCard],
):
    guardrail_user_context = _compose_guardrail_user_context(user_message, history)
    if settings.mock_llm or not settings.ark_api_key or not settings.ark_model:
        logger.info("Streaming mock LLM response")
        async for token in _stream_text(_mock_answer(guardrail_user_context, cards)):
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
    guardrail = guard_answer(raw_answer, user_message=guardrail_user_context, cards=cards)
    if not guardrail.passed:
        logger.warning("LLM answer blocked by generation guardrails: %s", guardrail.issues)
        guardrail = await _try_repair_answer(
            settings=settings,
            user_message=guardrail_user_context,
            context=context,
            cards=cards,
            raw_answer=raw_answer,
            guardrail=guardrail,
        )
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
    try:
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
    finally:
        await client.close()


async def _try_repair_answer(
    settings: Settings,
    user_message: str,
    context: str,
    cards: list[ProductCard],
    raw_answer: str,
    guardrail: GenerationGuardrailResult,
) -> GenerationGuardrailResult:
    if not raw_answer.strip() or not cards:
        return guardrail
    try:
        repaired_answer = await _collect_ark_repair(
            settings=settings,
            user_message=user_message,
            context=context,
            raw_answer=raw_answer,
            issues=guardrail.issues,
        )
    except Exception as exc:
        logger.warning("Ark repair failed; using safe fallback: %s", exc)
        return guardrail

    repaired_guardrail = guard_answer(repaired_answer, user_message=user_message, cards=cards)
    if repaired_guardrail.passed:
        logger.info("LLM answer repaired after guardrail feedback")
        return repaired_guardrail
    logger.warning("LLM repaired answer still blocked: %s", repaired_guardrail.issues)
    return guardrail


async def _collect_ark_repair(
    settings: Settings,
    user_message: str,
    context: str,
    raw_answer: str,
    issues: list[str],
) -> str:
    client = AsyncOpenAI(api_key=settings.ark_api_key, base_url=settings.ark_base_url)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                "下面是一版导购回答，但它触发了安全校验。"
                "请只改写回答，不要新增商品、价格、库存、优惠、购买承诺或商品资料之外的功效。\n"
                "如果校验问题包含 unsupported_absence_claims，必须删除所有“不会/没有/无/不含/不添加 + 酒精/刺激/香精/致痘/拔干”的句式；"
                "不要说“无酒精”“没有刺激”“不会刺激”“不含酒精”。\n"
                "如果校验问题包含 unsupported_result_absence_claims，必须删除或改写“不会堵塞/不会长闭口/不会残留/不会过敏/绝对温和/一定安全/放心使用”这类结果保证；"
                "如果资料里只是用户评价提到，只能写成“用户评价中有人提到……，但不能保证你使用后也一定如此”。\n"
                "可以改成：资料中有温和、舒缓、耳后测试等信息，但我不能确认具体成分或刺激风险；建议核对成分表并先局部测试。\n"
                "输出时不要解释校验规则，只给用户可读的改写版回答。\n\n"
                f"用户问题：{user_message}\n\n"
                f"可用商品资料：\n{context}\n\n"
                f"校验问题：{', '.join(issues)}\n\n"
                f"待改写回答：\n{raw_answer}"
            ),
        },
    ]
    try:
        response = await client.chat.completions.create(
            model=settings.ark_model,
            messages=messages,
            temperature=0.1,
        )
        return response.choices[0].message.content or ""
    finally:
        await client.close()


def _mock_answer(user_message: str, cards: list[ProductCard]) -> str:
    if "护肤品" in user_message and not any(word in user_message for word in ["油皮", "干皮", "敏感", "预算", "防晒", "修护"]):
        return "我可以先帮你缩小范围：你更在意肤质适配、预算，还是防晒/修护/控油这类具体功效？"
    return build_safe_answer(cards, user_message=user_message)


def _compose_guardrail_user_context(user_message: str, history: list[ChatMessage]) -> str:
    user_turns = [
        item.content
        for item in history[-6:]
        if item.role == "user" and item.content.strip()
    ]
    user_turns.append(user_message)
    return "\n".join(user_turns)


async def _stream_text(text: str) -> AsyncIterator[str]:
    for char in text:
        yield char
        await asyncio.sleep(0.01)
