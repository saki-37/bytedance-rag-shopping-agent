import asyncio

from openai import AsyncOpenAI

from app.config import Settings
from app.models import ChatMessage, ProductCard


SYSTEM_PROMPT = """你是一个电商智能导购 Agent。
回答必须基于提供的商品资料和商品卡片，不要编造不存在的价格、库存、优惠券、成分或功效。
如果用户需求信息不足，先用一句话追问关键条件；如果已有足够条件，给出 2-3 个推荐及原因。
需要提醒用户敏感肌、过敏、户外补涂等注意事项时，必须说明依据来自商品资料或用户评价。
"""


async def stream_answer(
    settings: Settings,
    user_message: str,
    history: list[ChatMessage],
    context: str,
    cards: list[ProductCard],
):
    if settings.mock_llm or not settings.ark_api_key or not settings.ark_model:
        async for token in _mock_stream(user_message, cards):
            yield token
        return

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
    async for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta


async def _mock_stream(user_message: str, cards: list[ProductCard]):
    if "护肤品" in user_message and not any(word in user_message for word in ["油皮", "干皮", "敏感", "预算", "防晒", "修护"]):
        text = "我可以先帮你缩小范围：你更在意肤质适配、预算，还是防晒/修护/控油这类具体功效？"
    else:
        names = "、".join(card.brand for card in cards[:3]) or "当前商品池"
        text = (
            f"我先按你的需求从美妆商品池里筛了一轮，比较匹配的是 {names}。"
            "下面的商品卡片价格和品牌来自数据源；如果你是敏感肌，建议优先看注意事项并先做局部测试。"
        )
    for char in text:
        yield char
        await asyncio.sleep(0.01)
