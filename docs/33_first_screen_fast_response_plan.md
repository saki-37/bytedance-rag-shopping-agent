# 首屏极速响应与临时聊天气泡方案

用途：把“1s 内给用户可见回应”的进阶要求落成可实现方案。本文只定义首屏候选态、临时聊天气泡、SSE 协议和验收口径，不替代正式导购回答、Planner 或生成层 guardrail。

## 背景

当前 `/api/chat/stream` 已经采用 SSE，并且推荐场景会先发 `products`，再发 `token`。这对感知性能是好基础，但真实首 token 仍可能慢，主要有两点：

- Planner 在检索前执行，默认超时较长；复杂场景下会挡住首屏商品卡。
- `stream_answer` 当前会先收集完整 LLM 流、做 guardrail / repair，再把最终文本按字符流出；因此接口是 SSE，生成体感不等于真实模型首 token。

新增方案不追求把最终回答强行提前，而是增加一个安全的首屏反馈层：

```text
快速检索拿候选卡 -> 临时聊天气泡接住用户 -> Planner / 正式回答继续生成
```

## 目标

1. 用户发送后 1s 内看到聊天区有明确反馈，而不只是 loading。
2. 商品候选卡尽量先展示，证明系统已经开始基于商品资料工作。
3. 临时气泡只做“需求复述 + 候选态说明 + 将比较的维度”，不输出最终推荐结论。
4. 临时气泡不进入后续 Planner / answer generation history，避免污染多轮上下文。
5. 现有 groundedness、guardrail、trace 和商品事实边界不被削弱。

## 非目标

- 不暴露模型 CoT 或内部推理链。
- 不让快模型直接决定最终排序。
- 不把两个 LLM 答案硬合并。
- 不为 1s 首屏牺牲商品事实、价格、功效和风险边界。

## SSE 协议

新增事件：

```text
quick_reply
```

Payload：

```json
{
  "trace_id": "uuid",
  "text": "我先按你说的早八提神需求找到了一批候选，会重点看提神场景、饮用负担和价格。",
  "ephemeral": true,
  "source": "template"
}
```

字段说明：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `trace_id` | string | 与本轮 stream 一致，方便 trace 关联 |
| `text` | string | 展示在聊天区的临时气泡文案 |
| `ephemeral` | boolean | 固定为 true，表示可见但不进入正式对话历史 |
| `source` | string | `template` 或 `fast_model`，用于后续观测 |

推荐型回答事件顺序建议：

```text
status(retrieving)
products
quick_reply
status(generating)
token...
done
```

如果 Planner 或检索导致 `products` 还未可用，也允许：

```text
status(retrieving)
quick_reply
products
status(generating)
token...
done
```

但优先选择 `products -> quick_reply`，因为本项目 RAG 通常较快，先展示真实候选比先展示泛化文案更稳。

澄清型回答事件顺序：

```text
status(retrieving)
quick_reply
token...
done
```

澄清场景不发 `products`，保持现有 API 契约。

## 临时气泡文案边界

允许内容：

- 复述用户需求。
- 说明已拿到候选或正在筛选。
- 说明将比较的维度，例如价格、适合人群、使用场景、注意事项。
- 说明正式推荐稍后补全。

禁止内容：

- 最终推荐排序。
- “最适合你的是...”这类结论。
- 商品资料中没有的功效、价格、库存、优惠或购买承诺。
- “我已经判断出...”这类容易被理解成 Planner 完成的措辞。
- 任何 CoT 式内部推理链。

推荐措辞：

```text
我先按你的需求筛出了一批候选，会重点看价格、使用场景和注意事项；下面继续补齐推荐依据。
```

对比场景：

```text
我先把这几款候选放在一起看，接下来会按价格、适合人群和风险点做对比。
```

跨类目场景：

```text
我先按这个场景拆成几个候选方向，下面会继续检查哪些商品能组成更完整的方案。
```

不推荐措辞：

```text
我已经想好了，第一款最适合你。
```

## 后端实现方案

### V1：模板临时气泡

V1 不调用额外快模型，只用已有 request、rule intent 和 cards 生成安全文案。

流程：

```text
收到请求
  -> status(retrieving)
  -> build rule-only / planned retrieval message
  -> retrieve 得到 cards
  -> products
  -> quick_reply(template)
  -> status(generating)
  -> stream_answer 正式回答
  -> done
```

优点：

- 改动小，稳定，不增加 API 成本。
- 文案完全可控，不会引入新幻觉。
- 适合先验收“临时聊天气泡”交互。

不足：

- 文案会偏模板化。
- 如果 Planner 很慢，`products` 和 `quick_reply` 仍会被 Planner 阻塞。

### V2：Planner 短超时 + Rule-only 首屏

为了真正靠近 1s，需要把 Planner 从首屏关键路径里移出。

流程：

```text
收到请求
  -> 同时启动 rule-only retrieval 和 Planner
  -> rule-only retrieval 完成后先发 products + quick_reply
  -> Planner 在短 deadline 内返回：用于正式回答或必要时后续 planned retrieval
  -> Planner 超时：正式回答使用 rule-only retrieval
```

建议参数：

- `FAST_FIRST_SCREEN_ENABLED=true`
- `FAST_PLANNER_DEADLINE_SECONDS=0.5`
- `QUICK_REPLY_SOURCE=template`

注意：V2 第一版不建议发送 `products_update`。如果 Planner 后来改了候选列表，会造成 UI 和正式回答不一致。更稳的做法是：首屏卡片和最终回答使用同一批 rule-only cards；Planner 只补充回答策略，或在下一轮再体现。

### V3：快模型临时气泡

如果模板气泡显得生硬，再考虑快模型。

快模型 prompt 必须短，并且只允许输出 acknowledgement：

```text
你只负责生成一条 30 字以内的导购进度提示。
只能复述用户需求、说明将比较哪些维度。
不能推荐具体商品，不能输出价格、功效结论、库存、优惠或购买承诺。
```

输入只给：

- 用户原始 message。
- 规则解析出的类目 / 子类 / 预算 / 场景。
- 候选商品数量，可选给品牌名，不给完整 RAG context。

快模型输出不进入正式 history，不参与 Planner。

## Android 实现方案

新增事件模型：

```kotlin
data class QuickReply(
    val text: String,
    val ephemeral: Boolean = true,
    val source: String = "template",
)
```

`StreamEvent` 增加：

```kotlin
data class QuickReply(val text: String, val ephemeral: Boolean, val source: String) : StreamEvent
```

`ChatMessage` 建议增加：

```kotlin
val isEphemeral: Boolean = false
val isQuickReply: Boolean = false
```

渲染策略：

- `quick_reply` 到达时，在当前 assistant turn 中插入一条临时 assistant 气泡。
- 视觉上比正式回答更轻，例如小字号、浅色背景、无反馈按钮。
- `token` 到达后继续写入正式 assistant message，而不是追加到 quick reply 上。
- `history.toPayloadHistory()` 过滤 `isEphemeral == true` 的消息，避免下轮传回后端。
- `done` 后 V1 可保留该气泡；后续如果聊天区显得冗余，可改成正式回答开始后自动折叠或替换。

推荐消息结构：

```text
User message
Assistant quick reply bubble, ephemeral
Assistant formal answer bubble, with product cards and tokens
```

为了少改 UI，也可以把 quick reply 和正式 answer 放在同一个 assistant turn 里，但需要 ViewModel 区分 `quickReplyText` 和 `content`，不要把它混进正式 content。

## Trace 与验收指标

每轮 trace 新增时间戳：

| 字段 | 说明 |
| --- | --- |
| `request_received_ms` | 后端收到请求 |
| `retrieval_started_ms` | 开始检索 |
| `products_sent_ms` | 发出 `products` |
| `quick_reply_sent_ms` | 发出 `quick_reply` |
| `first_token_sent_ms` | 发出正式回答第一个 token |
| `done_sent_ms` | 本轮结束 |
| `planner_latency_ms` | Planner 耗时 |
| `answer_generation_latency_ms` | 正式回答生成耗时 |
| `guardrail_latency_ms` | guardrail / repair 耗时 |

V1 验收：

- 推荐场景 SSE 中包含 `quick_reply`。
- Android 聊天区可见临时气泡。
- `quick_reply` 不进入下一轮 request history。
- 现有 golden stream、conversation、failure regression 不回退。

V2 验收：

- 典型推荐场景 `products_sent_ms - request_received_ms <= 1000`。
- `quick_reply_sent_ms - request_received_ms <= 1000`。
- Planner 超时不会导致首屏空等。
- trace 能区分 rule-only 首屏和 Planner 是否参与正式回答。

## 分步推进

1. 文档冻结：确认本方案的事件名、payload 和 Android 展示方式。
2. V1 后端：新增 `quick_reply` event 和模板文案生成函数。
3. V1 Android：新增临时聊天气泡，过滤 ephemeral history。
4. V1 回归：跑 API stream、Android 手测和现有 regression。
5. V2 后端：加入 Planner 短 deadline / rule-only 首屏策略。
6. V2 验收：用 trace 数据确认 1s 首屏是否达成。
7. V3 可选：只有模板气泡体验明显不足时，再引入快模型。

## 风险与处理

| 风险 | 处理 |
| --- | --- |
| 临时气泡被误解成最终结论 | 文案只写“先筛出候选 / 接下来会比较”，不写排序和推荐 |
| Planner 后续结果和首屏卡片不一致 | V2 第一版不发送 `products_update`，正式回答沿用首屏 cards |
| 快模型引入幻觉 | V1 先不用快模型；V3 prompt 严格限制，不给完整商品事实 |
| 多轮上下文污染 | Android 过滤 ephemeral message，后端也不接受 quick reply 作为历史依据 |
| trace 变复杂 | 明确记录 `quick_reply_source`、Planner 是否 applied、各阶段 latency |

## 当前推荐决策

先做 V1：新增 `quick_reply` SSE event + Android 临时聊天气泡。它能最小成本验证体验，且不改变检索、Planner 和正式回答安全边界。

V1 稳定后再做 V2：把 Planner 移出首屏关键路径，用 rule-only retrieval 承担 1s 候选态。
