# Runtime Trace Log 与可追溯反馈闭环

## 背景

本次发现的新问题是：Android 现场出现“用户说对比产品 1 和 3，但实际比较成产品 2 和 3”的现象。事后排查时，本地只有部分 feedback 记录和旧 benchmark trace，缺少 Android 现场那一轮的完整运行证据，只能靠重建 history 复现。

这说明当前 trace 还有一个缺口：`/api/debug/retrieve` 和 benchmark JSONL 能看到 `RetrievalTrace`，但真实 `/api/chat/stream` 的每轮运行没有自动落盘；Android 反馈也暂不携带完整 trace。因此一旦现场流式对话出错，很难判断问题发生在 Android history 顺序、Planner、retrieval、answer directive，还是生成层。

## 目标

把 Runtime Trace Log 做成一个同时服务调试和评分的能力：

- Debug：每个后端 turn 都有可追溯 JSONL，能复盘 Planner 是否调用、是否 fallback、检索是否硬过滤、最终卡片顺序是否正确。
- 反馈闭环：用户点 `不准确` 时，可以通过 `trace_id` 关联到同一轮 runtime trace。
- 评分与答辩：证明系统不是黑盒 RAG，而是可解释、可复盘、可把失败样例转成 benchmark 的工程闭环。

## 记录位置

Runtime trace 写入本地临时目录，不进入 Git：

```text
data/tmp/traces/trace_YYYY-MM-DD.jsonl
```

该目录已经被 `.gitignore` 的 `data/tmp/` 覆盖。

## 记录内容

每条记录至少包含：

```json
{
  "schema_version": "1.0",
  "trace_id": "uuid",
  "created_at": "ISO-8601",
  "endpoint": "chat_stream",
  "status": "ok",
  "request": {
    "message": "用户当前消息",
    "conversation_id": "local-demo",
    "history": [
      {"role": "assistant", "content": "...", "product_ids": ["p_food_022", "p_food_011", "p_food_012"]}
    ]
  },
  "settings": {
    "mock_llm": false,
    "has_ark_key": true,
    "has_ark_model": true,
    "planner_timeout_seconds": 20.0
  },
  "retrieval_message": "规则合并 + Planner 补充后的检索消息",
  "conversation_state": {},
  "retrieval_trace": {},
  "answer_directive": {
    "mode": "compare",
    "target_product_ids": ["p_food_022", "p_food_012"]
  },
  "products": [
    {"product_id": "p_food_022", "brand": "三顿半", "title": "冷萃黑咖...", "sub_category": "咖啡"}
  ],
  "answer": "最终流式输出文本",
  "token_count": 128,
  "answer_char_count": 128,
  "error": null,
  "latency_ms": 10753
}
```

对“产品 1 和 3”这类问题，关键字段是：

- `request.history[-1].product_ids`
- `planner_trace.called`
- `planner_trace.applied`
- `planner_trace.fallback_reason`
- `planner_trace.raw_plan.comparison_plan`
- `planner_trace.validated_plan.comparison_plan`
- `answer_directive.target_product_ids`
- `products[].product_id`

## 安全与边界

- 不记录 API key、Authorization header、完整环境变量或请求 header。
- `settings` 只记录布尔状态和 timeout。
- `data/tmp/traces/` 是 local-only，不提交。
- 流式 token 不逐 token 记录，只记录最终 answer 和 token_count。
- 后续可加保留策略，例如只保留最近 14-30 天。

## 实现方案

1. 新增 `server/app/trace_logger.py`。
2. 在 `/api/chat/stream` 入口生成 `trace_id`，并通过 SSE `status` / `done` payload 回传。
3. 在 streaming 过程中累积最终 answer、products、answer directive、retrieval trace 和 error。
4. 在 turn 结束时写入 `data/tmp/traces/trace_YYYY-MM-DD.jsonl`。
5. 在 `/api/debug/retrieve` 也写入同一格式的 trace，并在 response 中返回 `trace_id`。
6. `POST /api/feedback` 增加可选 `trace_id` 字段，后续 Android 可把反馈和 runtime trace 关联。

## 已落地文件

- `server/app/trace_logger.py`：负责生成 `trace_id` 和写入本地 JSONL。
- `server/app/config.py`：新增 `trace_dir`，默认指向 `data/tmp/traces`。
- `server/app/main.py`：`chat_stream` / `debug_retrieve` 自动写 runtime trace；SSE payload 和 debug response 返回 `trace_id`。
- `server/app/models.py`、`server/app/feedback.py`：反馈请求和 JSONL 记录支持 `trace_id`。
- `scripts/check_feedback_loop.py`：smoke test 会把 debug response 的 `trace_id` 带入 feedback。
- `docs/04_api_contract.md`：记录 SSE、debug、feedback 和 runtime trace 契约。

## 验收标准

- 调用 `/api/debug/retrieve` 后，`data/tmp/traces/trace_YYYY-MM-DD.jsonl` 新增一条记录。
- 调用 `/api/chat/stream` 后，SSE payload 中能看到同一个 `trace_id`，本地 JSONL 也能搜到。
- trace 记录不包含 Ark API key。
- 对比类问题 trace 中包含 `answer_directive.target_product_ids`。
- Android 端即使暂时不上传完整 trace，也可以在后续通过 `trace_id` 关联 feedback。
