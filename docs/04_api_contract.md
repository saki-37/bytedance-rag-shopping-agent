# API 契约

## GET `/health`

用于客户端和脚本检查后端是否可用。

响应：

```json
{
  "status": "ok",
  "catalog_size": 100,
  "mock_llm": false,
  "llm_provider": "ark",
  "llm_model": "YOUR_MODEL_ENDPOINT"
}
```

## POST `/api/chat/stream`

SSE 流式聊天接口。

请求：

```json
{
  "message": "我是油皮，想要200元以内的通勤防晒",
  "images": [
    {
      "image_id": "img_20260609_abcd1234",
      "mime_type": "image/jpeg",
      "source": "gallery",
      "preview_url": "/api/multimodal/images/img_20260609_abcd1234/preview",
      "summary": "疑似防晒包装，能看到 SPF50+ 字样",
      "query_text": "图片识别线索：防晒 SPF50+ 白色软管包装",
      "image_plan": {
        "detected_category": "防晒",
        "visible_text": ["SPF50+"],
        "confidence": "medium"
      }
    }
  ],
  "user_id": "local-demo-user",
  "recipient_id": "self",
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

`user_id` 可选。若未传，后端回退到 `conversation_id / local-demo-user`。当 `MEMORY_PROVIDER` 非 `disabled` 时，`user_id` 参与跨会话记忆 profile 加载与应用。Android 端会传入“演示身份”对应的本地 user_id（默认 `local-demo-user`，可在 App 内切换）；这是 Demo 级本地身份，不是服务端鉴权。

`conversation_id` 可选。Android 端每个本地会话生成独立的 conversation_id（形如 `android-<时间戳>-<序号>`），新建/切换会话后该值随之变化；feedback 与 ASR 请求复用当前会话的 conversation_id。

`recipient_id` 可选。Android 会把当前购买对象带给后端；后端从本地 memory profile 中取出该对象的肤质、尺码、预算、避开项等约束，并合并进本轮检索请求。提交主线建议把它作为个性化补充能力，不作为核心亮点。

`images` 可选。图片必须先通过 `POST /api/multimodal/images` 上传并拿到 `UploadedImageResponse`，Android 再把其中的 `image_id`、`query_text`、`image_plan` 带入聊天请求。后端会把图片线索拼进 `message`，复用现有 RAG retrieval；当前不是图像向量搜同款。

事件类型：

- `status`：阶段状态，`retrieving` 或 `generating`，payload 会带 `trace_id`。
- `token`：模型输出文本片段。
- `products`：本轮召回并展示的商品卡片，payload 会带 `trace_id`。
- `quick_reply`：临时聊天气泡，只做需求接收和候选态说明，payload 会带 `trace_id`；客户端可见但不应写入下一轮 history。
- `done`：流结束，payload 会带 `trace_id`。
- `error`：可恢复错误，payload 会带 `trace_id`。

推荐型回答的事件顺序为：

```text
status(retrieving, trace_id) -> quick_reply(template, trace_id) -> products(trace_id) -> status(generating, trace_id) -> token... -> done(trace_id)
```

如果完整 Planner + 检索在 `FAST_QUICK_REPLY_DEADLINE_SECONDS` 内还没返回，后端可以先发送一个 `source=deadline_fallback` 的临时气泡，主链路继续等待完整 Planner 和检索，不取消、不降级：

```text
status(retrieving, trace_id) -> quick_reply(deadline_fallback, trace_id) -> quick_reply(template, trace_id) -> products(trace_id) -> status(generating, trace_id) -> token... -> done(trace_id)
```

这样 Android 端会尽快展示需求已被接收的临时气泡；结构化商品卡片仍来自完整 Planner + 检索结果，再随着 `token` 流式输出嵌入到对应说明段落后。信息不足需要追问时，后端不发送 `products`：

```text
status(retrieving, trace_id) -> quick_reply(trace_id) -> status(generating, trace_id) -> token... -> done(trace_id)
```

`quick_reply` 事件示例：

```json
{
  "trace_id": "uuid",
  "text": "我先筛出了几款候选，接下来会重点看价格、适合人群和注意事项，再补齐推荐依据。",
  "ephemeral": true,
  "source": "template"
}
```

约束：

- `quick_reply` 只允许复述需求、说明候选态或将比较的维度，不输出最终排序、商品功效结论或购买承诺。
- `quick_reply.ephemeral` 固定为 `true`；Android 应渲染成临时气泡，在 `done` / `error` 后移除，并在 `history` 回传时过滤掉它，避免污染 Planner 和正式回答上下文。
- `quick_reply.source=deadline_fallback` 时，不允许写“已筛出某商品/品牌”；只能表达“已接收需求、正在查资料和约束”。
- 同一轮出现多条 `quick_reply` 时，Android 应更新同一个临时气泡，而不是追加多个气泡；展示上可以用本地打字机动画模拟流式思考。

`products` 事件示例：

```json
{
  "trace_id": "uuid",
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
      "description": "商品资料中的营销描述片段。",
      "variants": [
        {
          "variant_id": "s_p_beauty_006_1",
          "parent_product_id": "p_beauty_006",
          "label": "30ml 水感轻肌款",
          "properties": {"规格": "30ml 水感轻肌款"},
          "price": 170.0,
          "image_path": "1_美妆护肤/images/p_beauty_006_live.jpg",
          "reason": "30ml 水感轻肌款，数据源价格 ¥170；防晒相关需求匹配。"
        },
        {
          "variant_id": "s_p_beauty_006_2",
          "parent_product_id": "p_beauty_006",
          "label": "40ml 清爽型",
          "properties": {"规格": "40ml 清爽型"},
          "price": 190.0,
          "image_path": "1_美妆护肤/images/p_beauty_006_live.jpg",
          "reason": "40ml 清爽型，数据源价格 ¥190；防晒相关需求匹配。"
        }
      ]
    }
  ]
}
```

约束：

- 商品卡片中的价格、品牌、标题、图片路径必须来自数据源。
- `variants` 为可选字段；存在时表示同一 parent product 下的可购买 SKU/规格，Android 会渲染为同系列堆叠卡。
- 商品详情字段来自 `data/enriched` 或原始 `rag_knowledge`，不得由模型自由补全。
- 模型只能解释已召回商品，不允许编造优惠、库存、价格或未提供功效。
- 生成层会做后置校验：如果模型输出包含未授权价格、库存、优惠、购买链接等商业承诺，后端会改用基于商品卡片的安全兜底回答继续流式输出。
- 如果真实 Ark / Doubao 调用失败，后端也会返回安全兜底回答，避免 Android 端只收到 `error` 事件。
- 多轮商品指代依赖 `history[].product_ids`，不会从模型自由猜上一轮商品。

## POST `/api/multimodal/images`

用于 Android 相机/相册图片上传和 text-first 图片理解。当前只支持 JPEG / PNG。

请求：

```text
Content-Type: multipart/form-data

file=<image/jpeg or image/png>
user_id=local-demo-user
conversation_id=local-demo
```

响应：

```json
{
  "image_id": "img_20260609_abcd1234",
  "mime_type": "image/jpeg",
  "width": 1200,
  "height": 1600,
  "size_bytes": 245678,
  "preview_url": "/api/multimodal/images/img_20260609_abcd1234/preview",
  "expires_at": "2026-06-10T12:00:00+00:00",
  "summary": "疑似防晒包装，能看到 SPF50+ 字样",
  "query_text": "图片识别线索：防晒 SPF50+ 白色软管包装",
  "image_plan": {
    "detected_category": "防晒",
    "detected_brand": null,
    "visible_text": ["SPF50+"],
    "visual_attributes": ["白色软管包装"],
    "possible_use_cases": ["通勤防晒"],
    "uncertain_fields": ["品牌看不清"],
    "retrieval_terms": ["防晒", "SPF50+"],
    "confidence": "medium",
    "needs_clarification": false,
    "clarification_question": null,
    "query_text": "图片识别线索：防晒 SPF50+ 白色软管包装"
  }
}
```

约束：

- 用户上传图片写入 `data/tmp/user_uploads/`，属于本地临时文件，不进入 Git。
- 后端会写入有限 `multimodal` runtime trace，但不记录 API Key。
- `MULTIMODAL_MODEL` 留空时会尝试复用当前 provider 的模型配置；如果 provider / model 不支持图片，接口会返回低置信度 fallback 或可理解错误。
- 当前是图片到文本线索，再接现有 RAG；不承诺图像 embedding 检索、真实同款识别、价格/优惠/库存识别。

## GET `/api/multimodal/images/{image_id}/preview`

用于 Android 展示用户本轮上传图片的预览。

约束：

- 只允许安全格式的 `image_id`。
- 只在本地 upload 目录中查找文件。
- 预览文件有保留时长，过期或清理后会返回 404。

## POST `/api/asr/transcribe`

用于 Android 录音上传和 ASR 转写。后端只做代理，不内置语音识别模型；需要本地 ASR sidecar。

请求：

```text
Content-Type: multipart/form-data

file=<audio file>
profile=bilingual
hotword=防晒,敏感肌
conversation_id=local-demo
```

响应：

```json
{
  "ok": true,
  "text": "帮我找 200 元以内适合油皮通勤的防晒",
  "raw_text": "帮我找200元以内适合油皮通勤的防晒",
  "profile": "bilingual",
  "language": "zh",
  "duration_ms": 1850,
  "asr_trace_id": "asr_proxy_20260609_120000_abcd1234",
  "segments": [],
  "punctuation_applied": true,
  "punctuation_model": null,
  "error": null
}
```

约束：

- `ASR_SIDECAR_URL` 默认 `http://127.0.0.1:8765/transcribe`。
- 上传大小由 `ASR_MAX_UPLOAD_MB` 控制，默认 50MB。
- 无 sidecar 时不影响文字 RAG 主链路；Android 应展示可理解错误。

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
  "trace_id": "uuid",
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
- 每次调用会写入一条 runtime trace 到 `data/tmp/traces/trace_YYYY-MM-DD.jsonl`，并在响应中返回同一个 `trace_id`。

## Runtime Trace Log

`/api/chat/stream` 和 `/api/debug/retrieve` 每轮都会生成一个 `trace_id`，并把有界运行快照写入本地 JSONL：

```text
data/tmp/traces/trace_YYYY-MM-DD.jsonl
```

单条记录包含：

- `trace_id`、`endpoint`、`status`、`latency_ms`。
- 当前请求的 `message`、`conversation_id` 和 `history`。
- `memory_trace`（provider、user_id、已应用 constraints / preferences / short-term signals / skipped）。
- `retrieval_message`、`conversation_state`、`retrieval_trace`。
- `answer_directive`，用于复盘对比类问题最终选择了哪些商品。
- `quick_reply` 和 `stage_timings_ms`，用于复盘首屏响应；推荐场景重点看 `products_sent_ms`、`quick_reply_sent_ms`、`first_token_sent_ms`、`done_ready_ms`。
- 最终 `products` 顺序、流式拼接后的 `answer`、`token_count`、`answer_char_count`、`error`。
- `settings` 只记录 `mock_llm`、LLM provider、是否配置 key/model、模型名、Planner timeout、quick reply deadline、`memory_provider`；不记录 API key、header 或完整环境变量。

该目录被 `.gitignore` 的 `data/tmp/` 覆盖，不进入 Git。后续用户反馈可以通过 `trace_id` 回指同一条 runtime trace。

## POST `/api/feedback`

用于记录轻量反馈闭环。它不是重新调用模型的接口，而是把用户对某次回答的 `有用` / `不准确` 判断，连同当时的有限证据链路写入本地 JSONL，方便后续归因、补 benchmark 或调整数据与 prompt。

请求：

```json
{
  "conversation_id": "local-demo",
  "turn_id": "turn-001",
  "trace_id": "uuid-from-chat-stream-or-debug",
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
- `trace_id` 用于关联 `data/tmp/traces/` 中同一轮 runtime trace；Android 暂时不上传完整 `RetrievalTrace` 也可以先传这个字段。
- `products`、`trace`、`retrieval_message` 和 `answer` 用于区分是检索问题、生成问题、商品证据问题，还是用户偏好表达问题。
- 记录文件写入 `data/tmp/feedback/feedback_YYYY-MM-DD.jsonl`，该目录被 `.gitignore` 忽略，不进入 Git。
- 反馈值当前只支持 `helpful` 和 `inaccurate`，先保持足够轻，不扩张成复杂问卷。

本地 smoke test：

```bash
server/.venv/bin/python scripts/check_feedback_loop.py
```

## User Memory / Recipients API

用于 Android 管理“给谁买”的轻量上下文。该能力会影响 `POST /api/chat/stream` 中的 `recipient_id` 解析，但不应被夸大为完整用户画像平台。

### GET `/api/user-memory/{user_id}/recipients`

响应：

```json
{
  "user_id": "local-demo-user",
  "selected_recipient_id": "self",
  "recipients": [
    {
      "display_name": "自己",
      "relationship": "self",
      "shipping": {
        "phone": null,
        "address": null
      }
    }
  ],
  "updated_at": "2026-06-09T12:00:00+00:00"
}
```

### PUT `/api/user-memory/{user_id}/recipients`

请求：

```json
{
  "selected_recipient_id": "recipient-0",
  "recipients": [
    {
      "display_name": "妈妈",
      "relationship": "family",
      "shipping": {
        "phone": null,
        "address": null
      }
    }
  ]
}
```

### PUT `/api/user-memory/{user_id}/selected-recipient`

请求：

```json
{
  "selected_recipient_id": "self"
}
```

约束：

- 本地 provider 默认写入 `data/tmp/user_memory/`，不进入 Git。
- Android 管理接口只提交有限字段；不要在 Demo 中录入真实手机号和地址。
- 提交主线建议只讲“购买对象上下文可以进入检索约束”，不主讲完整个性化推荐平台。
