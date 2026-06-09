# 首屏极速响应与临时聊天气泡方案

用途：把“1s 内给用户可见回应”的进阶要求落成可实现方案。本文只定义首屏候选态、临时聊天气泡、SSE 协议和验收口径，不替代正式导购回答、Planner 或生成层 guardrail。

## 背景

当前 `/api/chat/stream` 已经采用 SSE，并且推荐场景会发送 `products` 和 `token`。这对感知性能是好基础，但真实首 token 仍可能慢，主要有两点：

- Planner 在检索前执行，默认超时较长；复杂场景下会挡住首屏商品卡。
- `stream_answer` 当前会先收集完整 LLM 流、做 guardrail / repair，再把最终文本按字符流出；因此接口是 SSE，生成体感不等于真实模型首 token。

新增方案不追求把最终回答强行提前，而是增加一个安全的首屏反馈层：

```text
临时聊天气泡接住用户 -> 完整 Planner + retrieval 返回候选 -> 正式回答继续生成
```

## 目标

1. 用户发送后 1s 内看到聊天区有明确反馈，而不只是 loading。
2. 商品候选卡必须来自完整 Planner + retrieval；不为了首屏速度发送 rule-only 卡片。
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
| `source` | string | `template`、`deadline_fallback` 或未来可选 `fast_model`，用于后续观测 |

推荐型回答事件顺序建议：

```text
status(retrieving)
quick_reply
products
status(generating)
token...
done
```

如果 Planner 或检索导致 `products` 还未可用，也允许：

```text
status(retrieving)
quick_reply(deadline_fallback)
quick_reply(template)
products
status(generating)
token...
done
```

`deadline_fallback` 只说明“已接收需求、正在查资料”，不包含候选商品或品牌；`template` quick reply 可在完整候选返回后说明正在浏览/比较哪些候选。

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

### V2：Quick Reply Deadline + 完整主链路

为了让用户在 1s 内看到响应，同时不破坏 Planner 的候选质量，首屏 deadline 只作用在 `quick_reply` 体验支线。Planner、向量检索和正式回答仍属于主链路，不能被首屏 deadline 截断。

流程：

```text
收到请求
  -> 启动完整 Planner + retrieval
  -> 如果主链路在 quick reply deadline 内完成：发送 template quick_reply + products
  -> 如果主链路没有及时完成：先发送 deadline_fallback quick_reply
  -> 继续等待完整 Planner + retrieval
  -> 发送 template quick_reply 更新候选态
  -> 发送 products，并进入正式回答
```

建议参数：

- `FAST_FIRST_SCREEN_ENABLED=true`
- `FAST_QUICK_REPLY_DEADLINE_SECONDS=0.8`
- `QUICK_REPLY_SOURCE=template | deadline_fallback`

注意：`deadline_fallback` 文案不能写“已筛出某商品/品牌”，只能表达“已接收需求，正在查商品资料和约束”。商品卡片必须等完整 Planner + retrieval 完成后再发送；发送卡片前可用 `template` quick reply 把“正在浏览/比较哪些候选”先展示出来。

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
- 同一轮多条 `quick_reply` 到达时，更新同一个临时气泡，不追加多个气泡。
- 视觉上比正式回答更轻，例如小字号、浅色背景、无反馈按钮。
- 客户端可用本地打字机动画逐字显示 quick reply，即使 SSE payload 是一次性到达。
- `token` 到达后继续写入正式 assistant message，而不是追加到 quick reply 上。
- `history.toPayloadHistory()` 过滤 `isEphemeral == true` 的消息，避免下轮传回后端。
- `done` / `error` 后移除该气泡，只保留正式回答，避免聊天区重复。

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
| `done_ready_ms` | 正式回答已生成并准备结束 |
| `planner_latency_ms` | Planner 耗时 |
| `answer_generation_latency_ms` | 正式回答生成耗时 |
| `guardrail_latency_ms` | guardrail / repair 耗时 |

V1 验收：

- 推荐场景 SSE 中包含 `quick_reply`。
- Android 聊天区可见临时气泡。
- `quick_reply` 不进入下一轮 request history。
- 现有 golden stream、conversation、failure regression 不回退。

V2 验收：

- `quick_reply_sent_ms - request_received_ms <= 1000`。
- Planner 不因为 quick reply deadline 被取消；trace 中不能出现 `planner_fast_first_screen_timeout`。
- `products` 和正式回答使用同一套完整 Planner + retrieval 结果。
- `quick_reply.source=deadline_fallback` 时，文案不包含候选商品、品牌、功效结论或购买建议。

## 分步推进

1. 文档冻结：确认本方案的事件名、payload 和 Android 展示方式。
2. V1 后端：新增 `quick_reply` event 和模板文案生成函数。
3. V1 Android：新增临时聊天气泡，过滤 ephemeral history。
4. V1 回归：跑 API stream、Android 手测和现有 regression。
5. V2 后端：加入 quick reply deadline fallback，不截断 Planner。
6. V2 验收：用 trace 数据确认 1s 临时气泡是否达成，并确认 Planner 主链路完整。
7. V3 可选：只有模板气泡体验明显不足时，再引入快模型。

## 风险与处理

| 风险 | 处理 |
| --- | --- |
| 临时气泡被误解成最终结论 | 文案只写“先筛出候选 / 接下来会比较”，不写排序和推荐 |
| Planner 被首屏 deadline 误截断 | deadline 只作用在 `quick_reply` 体验支线，主链路不传短 timeout |
| 快模型引入幻觉 | V1 先不用快模型；V3 prompt 严格限制，不给完整商品事实 |
| 多轮上下文污染 | Android 过滤 ephemeral message，后端也不接受 quick reply 作为历史依据 |
| trace 变复杂 | 明确记录 `quick_reply_source`、Planner 是否 applied、各阶段 latency |

## 当前推荐决策

先做 V1：新增 `quick_reply` SSE event + Android 临时聊天气泡。它能最小成本验证体验，且不改变检索、Planner 和正式回答安全边界。

V1 稳定后再做 V2：把 1s 目标收敛到临时气泡，不用 rule-only retrieval 替代完整 Planner 候选。
