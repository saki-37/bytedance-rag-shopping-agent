# API 契约

## GET `/health`

用于客户端和脚本检查后端是否可用。

响应：

```json
{
  "status": "ok",
  "catalog_size": 5,
  "mock_llm": true
}
```

## POST `/api/chat/stream`

SSE 流式聊天接口。

请求：

```json
{
  "message": "我是油皮，想要200元以内的通勤防晒",
  "conversation_id": "local-demo",
  "history": [
    {"role": "user", "content": "我想找防晒"},
    {
      "role": "assistant",
      "content": "你更在意通勤还是户外？",
      "product_ids": ["p_beauty_006", "p_beauty_022"]
    }
  ]
}
```

`history[].product_ids` 为可选字段。Android 会把上一轮 assistant 商品卡片的 `product_id` 带回后端，用于解析“第一款”“它”“这款”等商品指代；旧请求不传该字段时按空数组处理。

事件类型：

- `status`：阶段状态，`retrieving` 或 `generating`。
- `products`：本轮召回并展示的商品卡片。
- `token`：模型输出文本片段。
- `done`：流结束。
- `error`：可恢复错误。

`products` 事件示例：

```json
{
  "products": [
    {
      "product_id": "p_beauty_006",
      "title": "巴黎欧莱雅新多重防护隔离露水感轻薄高倍防晒修护提亮30ml",
      "brand": "巴黎欧莱雅",
      "category": "美妆护肤",
      "sub_category": "防晒",
      "price": 170.0,
      "image_path": "1_美妆护肤/images/p_beauty_006_live.jpg",
      "tags": ["油皮", "通勤", "防晒"],
      "reason": "SPF50+ PA++++，质地轻薄，价格在200元以内。",
      "target_users": ["油皮", "混油皮", "通勤人群"],
      "use_cases": ["日常通勤防晒", "妆前打底"],
      "selling_points": ["SPF50+ PA++++", "水感轻薄"],
      "cautions": ["敏感肌先做耳后测试"],
      "suitable_for": ["油皮", "混油皮"],
      "avoid_for": ["长时间大量出汗场景"],
      "description": "商品资料中的营销描述片段。"
    }
  ]
}
```

约束：

- 商品卡片中的价格、品牌、标题、图片路径必须来自数据源。
- 商品详情字段来自 `data/enriched` 或原始 `rag_knowledge`，不得由模型自由补全。
- 模型只能解释已召回商品，不允许编造优惠、库存、价格或未提供功效。
- 生成层会做后置校验：如果模型输出包含未授权价格、库存、优惠、购买链接等商业承诺，后端会改用基于商品卡片的安全兜底回答继续流式输出。
- 如果真实 Ark / Doubao 调用失败，后端也会返回安全兜底回答，避免 Android 端只收到 `error` 事件。
- 多轮商品指代依赖 `history[].product_ids`，不会从模型自由猜上一轮商品。

## GET `/assets/{image_path}`

用于 Android 客户端加载商品图片。`image_path` 来自商品卡片字段，客户端需要对中文目录名进行 URL 编码。

示例：

```text
GET /assets/1_%E7%BE%8E%E5%A6%86%E6%8A%A4%E8%82%A4/images/p_beauty_006_live.jpg
```

响应：

- `200 image/jpeg`：返回商品图片。
- `404`：图片路径不存在。

约束：

- 只暴露 `data/raw/ecommerce_agent_dataset` 下的官方数据集图片。
- 客户端不应自行拼接非数据源路径。

## POST `/api/debug/retrieve`

用于本地调试和评测，不是 Android MVP 必需接口。它只运行检索层，不调用大模型，方便检查 `QueryIntent`、硬过滤、召回通道和最终排序。

请求：

```json
{
  "message": "我是油皮，想要200元以内的通勤防晒"
}
```

响应：

```json
{
  "products": [
    {
      "product_id": "p_beauty_006",
      "brand": "巴黎欧莱雅",
      "price": 170.0
    }
  ],
  "clarification_question": null,
  "trace": {
    "query": "我是油皮，想要200元以内的通勤防晒",
    "parsed_intent": {
      "category_candidates": ["beauty"],
      "universal_constraints": {"budget_max": 200.0, "brand_exclude": []},
      "facets": {"skin_type": ["油皮"], "effect": ["防晒"], "use_case": ["通勤"]},
      "needs_clarification": false
    },
    "hard_filtered_out": [],
    "retrieval_channels": {
      "keyword": [],
      "vector": [],
      "graph": []
    },
    "final_ranking": [],
    "guardrail_checks": {
      "over_budget_candidates": 0,
      "excluded_term_candidates": 0,
      "needs_clarification": false
    }
  }
}
```

约束：

- 仅用于本地 debug / benchmark。
- 不返回真实 API Key 或模型配置。
- `trace` 是 V1 检索可解释性的核心证据，后续评测表应引用它。

## POST `/api/feedback`

用于记录轻量反馈闭环。它不是重新调用模型的接口，而是把用户对某次回答的 `有用` / `不准确` 判断，连同当时的有限证据链路写入本地 JSONL，方便后续归因、补 benchmark 或调整数据与 prompt。

请求：

```json
{
  "conversation_id": "local-demo",
  "turn_id": "turn-001",
  "feedback": "inaccurate",
  "message": "我是油皮，想要200元以内通勤防晒",
  "retrieval_message": "我是油皮，想要200元以内通勤防晒",
  "answer": "本轮最终展示给用户的回答文本",
  "note": "用户觉得推荐理由不够可信",
  "history": [
    {"role": "user", "content": "我想找防晒"},
    {
      "role": "assistant",
      "content": "你更在意通勤还是户外？",
      "product_ids": ["p_beauty_006"]
    }
  ],
  "products": [],
  "clarification_question": null,
  "trace": null
}
```

响应：

```json
{
  "ok": true,
  "record_id": "uuid",
  "feedback": "inaccurate"
}
```

记录策略：

- 记录的是有界证据快照，不是无限保存完整聊天。
- `history` 最多保留最近 8 条消息，用于判断多轮上下文是否丢失。
- `products`、`trace`、`retrieval_message` 和 `answer` 用于区分是检索问题、生成问题、商品证据问题，还是用户偏好表达问题。
- 记录文件写入 `data/tmp/feedback/feedback_YYYY-MM-DD.jsonl`，该目录被 `.gitignore` 忽略，不进入 Git。
- 反馈值当前只支持 `helpful` 和 `inaccurate`，先保持足够轻，不扩张成复杂问卷。

本地 smoke test：

```bash
server/.venv/bin/python scripts/check_feedback_loop.py
```
