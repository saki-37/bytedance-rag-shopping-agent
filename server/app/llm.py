import asyncio
import logging
from collections.abc import AsyncIterator

from openai import AsyncOpenAI

from app.config import Settings
from app.guardrails import build_safe_answer, guard_answer
from app.guardrails import GenerationGuardrailResult
from app.models import AnswerDirective, ChatMessage, ProductCard


logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """你是一个电商智能导购 Agent。
回答必须基于提供的商品资料和商品卡片，不要编造不存在的价格、库存、优惠券、成分或功效。
如果用户需求信息不足，先用一句话追问关键条件；如果已有足够条件，给出 2-3 个推荐及原因。
如果用户明确要求“对比/怎么选/哪个更适合”，必须按价格、适合人群或场景、关键优点、注意事项给出结构化比较，并给出一句保守选择建议。
如果同一商品资料下提供多个 SKU/规格，必须表达为“同系列规格/款式对比”，使用资料中给出的 variant label 和 price，不要把它们说成互不相关的商品。
需要提醒用户敏感肌、过敏、户外补涂等注意事项时，必须说明依据来自商品资料或用户评价。
只能提到“可用商品卡片”中的商品。价格只能使用商品卡片中列出的价格或用户问题中给出的预算数字。
普通推荐回答的商品编号和展示顺序必须严格遵守“可见商品顺序”。不要因为你认为某个商品更优就调换第 1/2/3 个；如果需要表达更推荐哪一个，只能在推荐理由或选择建议里说明，不能改变编号顺序。
内部商品ID和SKU ID（例如 p_beauty_006、s_p_beauty_006_1）只用于系统定位，不要输出给用户，也不要写进表格表头、商品名称或正文。
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
    answer_directive: AnswerDirective | None = None,
):
    guardrail_user_context = _compose_guardrail_user_context(user_message, history)
    if settings.mock_llm or not settings.ark_api_key or not settings.ark_model:
        logger.info("Streaming mock LLM response")
        async for token in _stream_text(_mock_answer(guardrail_user_context, cards, answer_directive)):
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
            answer_directive=answer_directive,
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
            answer_directive=answer_directive,
        )
    async for token in _stream_text(guardrail.answer):
        yield token


async def _collect_ark_answer(
    settings: Settings,
    user_message: str,
    history: list[ChatMessage],
    context: str,
    cards: list[ProductCard],
    answer_directive: AnswerDirective | None = None,
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
            "content": _build_generation_user_prompt(
                user_message=user_message,
                context=context,
                cards=cards,
                answer_directive=answer_directive,
            ),
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
    answer_directive: AnswerDirective | None = None,
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
            answer_directive=answer_directive,
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
    answer_directive: AnswerDirective | None = None,
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
                f"{_format_answer_directive(answer_directive)}\n\n"
                f"{_format_visible_product_order(cards)}\n\n"
                "顺序要求：如果待改写回答是普通推荐，必须让编号 1/2/3 与上面的可见商品顺序一致；"
                "如果是对比回答，必须让表格列顺序与回答指令中的内部选择顺序一致。\n\n"
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


def _mock_answer(
    user_message: str,
    cards: list[ProductCard],
    answer_directive: AnswerDirective | None = None,
) -> str:
    if answer_directive and answer_directive.mode == "compare" and len(cards) >= 2:
        return _mock_comparison_table(cards, answer_directive)
    if "护肤品" in user_message and not any(word in user_message for word in ["油皮", "干皮", "敏感", "预算", "防晒", "修护"]):
        return "我可以先帮你缩小范围：你更在意肤质适配、预算，还是防晒/修护/控油这类具体功效？"
    return build_safe_answer(cards, user_message=user_message)


def _build_generation_user_prompt(
    user_message: str,
    context: str,
    cards: list[ProductCard],
    answer_directive: AnswerDirective | None = None,
) -> str:
    return (
        f"用户问题：{user_message}\n\n"
        f"{_format_answer_directive(answer_directive)}\n\n"
        f"{_format_visible_product_order(cards)}\n\n"
        "顺序要求：普通推荐回答必须按上面的可见商品顺序编号和描述；"
        "不要调换、重排、跳过或插入其他商品。选择建议可以表达偏好，但不能改变列表编号。\n\n"
        f"可用商品资料：\n{context}"
    )


def _format_visible_product_order(cards: list[ProductCard]) -> str:
    if not cards:
        return "可见商品顺序：无。"
    lines = ["可见商品顺序（仅供内部定位，禁止向用户展示 product_id）："]
    for index, card in enumerate(cards[:3], start=1):
        lines.append(f"{index}. product_id={card.product_id}；品牌={card.brand}；标题={card.title}")
    return "\n".join(lines)


def _format_answer_directive(answer_directive: AnswerDirective | None) -> str:
    if not answer_directive or answer_directive.mode != "compare":
        return "回答指令：按普通导购推荐回答。"
    focus = "、".join(answer_directive.focus_dimensions) if answer_directive.focus_dimensions else "价格、适合人群/肤质、使用场景、核心优点、注意事项、选择建议"
    target_ids = "、".join(answer_directive.target_product_ids)
    return (
        "回答指令：本轮是商品对比。\n"
        "- 必须先输出一张 GitHub Markdown 表格。\n"
        f"- 内部选择顺序：{target_ids}。这些 ID 只用于定位，禁止展示给用户。\n"
        "- 表格中的商品名称只写品牌、标题或规格名，不要带 product_id、variant_id 或类似 p_beauty_006 的内部编号。\n"
        f"- 表格列优先覆盖这些维度：{focus}。\n"
        "- 表格单元格只能使用可用商品资料和商品卡片字段；资料未明确时写“资料未明确”。\n"
        "- 价格只能使用商品资料中的 parent price 或 variant price。\n"
        "- 表格后用 1-2 句给出保守选择建议；不要把完整商品卡内容写进表格。"
    )


def _mock_comparison_table(cards: list[ProductCard], answer_directive: AnswerDirective) -> str:
    target_order = {product_id: index for index, product_id in enumerate(answer_directive.target_product_ids)}
    ordered_cards = sorted(cards, key=lambda card: target_order.get(card.product_id, len(target_order)))[:3]
    rows = [
        "| 商品 | 价格 | 适合人群/肤质 | 核心优点 | 注意事项 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for card in ordered_cards:
        rows.append(
            "| {name} | {price} | {fit} | {points} | {cautions} |".format(
                name=f"{card.brand}｜{card.title}",
                price=_card_price_label(card),
                fit=_table_cell(card.suitable_for or card.target_users or card.use_cases),
                points=_table_cell(card.selling_points or [card.reason]),
                cautions=_table_cell(card.cautions or card.avoid_for or ["资料未明确"]),
            )
        )
    if ordered_cards:
        first = ordered_cards[0]
        advice = f"保守选择：如果你更想稳妥，可以优先看 {first.brand}，但仍建议结合肤质和补涂场景确认。"
    else:
        advice = "保守选择：当前资料不足以给出明确排序，建议先确认对比商品。"
    return "\n".join(["### 商品对比", *rows, "", advice])


def _card_price_label(card: ProductCard) -> str:
    if card.variants:
        return "；".join(f"{variant.label} ¥{variant.price:g}" for variant in card.variants[:3])
    return f"¥{card.price:g}"


def _table_cell(values: list[str]) -> str:
    cleaned = [value.replace("|", "/").strip() for value in values if value.strip()]
    return "；".join(cleaned[:2]) if cleaned else "资料未明确"


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
