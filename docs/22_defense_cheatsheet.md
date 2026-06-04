# 答辩口袋稿

日期：2026-06-04

用途：把 Demo、架构、可靠性证据和项目边界收成一页。答辩时优先看这一页；需要细节再跳到架构、评测和复现文档。

## 30 秒项目介绍

这是一个原生 Android + FastAPI 的美妆 RAG 导购 Agent。用户输入肤质、预算、使用场景和排除条件后，后端先做结构化约束解析和商品检索，再调用 Doubao / Ark 生成受商品证据约束的导购回复，最后在 Android 端流式展示回答、商品卡片、图片、详情弹窗和轻量反馈按钮。

当前版本主线是“文字导购闭环”，不是购物车或拍照找货。我们更关注一件事：模型推荐必须能回到商品资料、价格、图片和注意事项上，而不是只生成一段看起来像导购的话。

## 3 句话架构链路

1. Android 端只负责聊天体验、SSE 消费、商品卡片和详情弹窗；核心导购逻辑都在 FastAPI 后端。
2. 后端先把用户 query 和必要历史合并成结构化状态，再用预算、肤质、功效、场景、排除词做硬过滤和多路召回，Chroma 向量检索只是其中一个召回通道，不替代硬约束。
3. Doubao 只看到最终候选商品和证据文本；生成后还要经过 guardrail 校验，必要时二次改写或返回 evidence-aware fallback。

## 可靠性怎么讲

不要说“模型不会幻觉”。更准确的说法是：

> 真实模型确实会尝试补充资料外承诺，所以系统把可信度放在后端证据链上：商品卡片来自数据源，价格/库存/优惠/下单承诺会被 guardrail 拦截，高风险回答会通过 repair 或 evidence-aware fallback 拉回到“资料支持/资料未说明/不能保证”的边界。

可以补充的证据：

- Golden stream 真实 API 三轮 8/8 stable PASS，说明端到端流式结构和检索链路稳定。
- Groundedness mock / retrieval-only 11/11 PASS，用于证明检索、约束继承和 fallback 结构是稳定的。
- `GRD-L03/05/08/L01` 高风险真实 API case 已通过 AI semantic review，覆盖结果型绝对承诺、孕期/过敏边界、预算越界和长对话约束继承。
- P0-4 中发现过一个真实 bug：170 元商品被 fallback 说成在 150 元预算内；已修复并加本地断言。这是可以主动讲的工程闭环。

## Trace 怎么讲

`RetrievalTrace` 是工程证据，不是 LLM chain-of-thought，也不是必须展示给用户的内容。

- `constraint_trace`：记录当前轮条件、历史继承、放宽项和最终生效约束。
- `safety_trace`：记录敏感肌、过敏、孕期、排除条件、绝对安全承诺等风险边界。
- `source_trace`：记录商品事实、结构化属性、官方 FAQ 和用户评价来源。

用户可见回答只展示必要结论；约束继承和来源边界进入 trace，供 debug、benchmark 和答辩解释。

## 关键代码入口

| 问题 | 看哪里 | 怎么说 |
| --- | --- | --- |
| API 和 SSE 怎么实现 | `server/app/main.py` | `/api/chat/stream` 负责检索、生成、guardrail 和 SSE 输出 |
| 多轮约束怎么继承 | `server/app/conversation_state.py` | 规则层合并预算、类目、肤质、功效、场景和排除条件 |
| RAG 检索怎么做 | `server/app/retrieval.py` | 硬过滤 + keyword/facet + Chroma 向量召回 + graph-aware relation score + rerank |
| 为什么推荐这些商品 | `RetrievalTrace` / `/api/debug/retrieve` | 可以看到过滤、召回、排序、约束和来源证据 |
| 反幻觉怎么做 | `server/app/guardrails.py`、`server/app/llm.py` | 先 prompt 约束，再生成后校验，失败时 repair 或 fallback |
| Android 端怎么接 | `client/android/app/src/main/...` | OkHttp 消费 SSE，Compose 渲染消息、商品卡片、详情和反馈按钮 |
| 反馈闭环怎么做 | `server/app/feedback.py`、`ShoppingAgentClient.submitFeedback` | Android 提交 `有用/不准确`，后端写入本地 JSONL；debug 脚本可构造带 trace 的复盘记录 |

## Demo 讲解顺序

1. 打开 App，说明这是原生 Android 端，不是 H5。
2. 点 `油皮通勤防晒`，展示真实流式回复和商品卡片。
3. 点商品卡片，展示图片、价格、适合人群、场景、卖点和注意事项。
4. 可选点回答下方 `有用` / `不准确`，展示质量反馈闭环。
5. 点 `信息不足追问`，展示系统不会在条件不足时强行推荐。
6. 口头补一句可靠性：价格、图片和卡片字段来自数据源；模型回答会经过 guardrail 和 evidence-aware fallback。

## 当前边界

当前版本不主打：

1. 图片输入、语音输入。
2. 购物车、下单、真实电商交易链路。
3. 全品类完整标注。
4. 完整 GraphRAG / Neo4j。
5. 完整自动 claim-level groundedness judge。

这些不是当前版本失败点，而是下一阶段。当前版本主打：

> 可运行的原生移动端闭环 + 约束感知 RAG + 证据约束生成 + 可复验的反幻觉评测。

## 评委追问时的保守回答

**问：为什么不直接让大模型自己判断？**  
因为电商导购里价格、库存、优惠、过敏、孕期等边界不能只靠模型自由发挥。我们把预算、排除条件和商品事实放在规则/检索层，模型只负责组织导购表达。

**问：为什么不用完整 GraphRAG？**  
当前数据规模和时间更适合轻量 graph-aware relation score。我们保留商品、属性、功效、场景和风险之间的关系信号，但不引入重型图数据库，避免工程复杂度压过主线闭环。

**问：如果模型还是乱说怎么办？**  
真实模型确实会乱说，所以后端不会直接把原始生成当最终答案。回答会经过 guardrail；如果触发价格、优惠、库存、绝对安全或资料外承诺，就二次改写，仍失败则回到 evidence-aware fallback。

**问：为什么 trace 不展示给用户？**  
trace 是工程证据，不是用户体验文案。用户只需要看到清楚、自然的推荐和边界提醒；评测和答辩需要 trace 来证明系统确实继承了约束、识别了风险、知道证据来自哪里。
