# 官方采分点逐项对照表

更新：2026-06-06

来源：`docs/01_topic_brief.md` 中根据官方课题说明整理出的“课题真实要求、评分权重、基础/进阶/高级场景”。本页不按我们自己的 V0/V1/V2/V3 展开，只按官方采分口径看当前完成度。

## 状态符号

| 符号 | 含义 |
| --- | --- |
| ✅ | 已完成，并已有代码/文档/评测或 Demo 证据 |
| ◯ | 架构或功能已有第一版，但还需要 benchmark、真实复验或文档收口 |
| △ | 部分完成，只能作为补充亮点，不能当作稳拿 |
| ✕ | 尚未实现 |
| ⏸ | 暂不建议作为主线，避免范围扩张 |

## 一眼结论

| 官方采分块 | 当前判断 | 最短解释 |
| --- | --- | --- |
| 基础功能完整性 35% | ✅ 基本稳 | Android 原生端到后端 RAG、模型流式、商品卡片和详情已经跑通 |
| 工程质量 25% | ✅ 基本稳 | 目录、接口、文档、安全、评测、依赖版本表和复现说明都有；文档状态已收口，最终提交前再跑一轮复现检查 |
| 效果与可靠性 20% | ◯ 已有可讲证据，仍是答辩重点 | 已有检索 benchmark、conversation、guardrail、三层 trace、evidence-aware fallback、groundedness full mock / retrieval-only 11/11；真实 API golden stream 三轮 8/8 stable PASS；`GRD-L03/05/08/L01` 高风险真实 API + AI review 均已通过语义复核 |
| 加分项深度 20% | ◯ 有明确主打 | 可解释 RAG、graph-aware relation score、多商品对比、Always-light Planner、多品类样例和 Android 可见轻量反馈闭环已有 |
| 数据覆盖口径 | ✅ 已补薄支持 | raw 官方数据共 100 条；当前为 25 条美妆 deep + 5 条服饰 deep + 70 条 thin，统一索引 100 条商品；美妆仍作为深度主线 |

## 必做最小闭环

### 客户端

| 官方要求 | 状态 | 当前已做 | 缺口/下一步 |
| --- | --- | --- | --- |
| iOS 或 Android 原生 App，二选一即可 | ✅ | Android Kotlin + Jetpack Compose | 最终演示前再确认 Android Studio 可运行 |
| 对话窗口，支持发送文字 | ✅ | 聊天页、输入框、发送按钮、用户消息展示 | 无明显缺口 |
| 接收并渲染 AI 流式回复 | ✅ | Android 消费 SSE token，已修复 loading 收尾和自动滚动 | 真实 API 演示前再复验 |
| 回复中包含商品卡片 | ✅ | 商品卡展示图片、品牌、商品名、价格、标签、推荐理由 | 无明显缺口 |
| 商品卡片可点击，跳转落地页或模拟详情页 | ✅ | 点击卡片打开详情弹窗，展示价格、类目、适合、场景、卖点、注意事项 | 可在最终 Demo 中展示一次 |

### 后端

| 官方要求 | 状态 | 当前已做 | 缺口/下一步 |
| --- | --- | --- | --- |
| Python / Go / Node.js 任选 | ✅ | Python FastAPI | 无明显缺口 |
| 集成向量数据库 | ✅ | Chroma `products` collection，30 条 enriched 商品入库 | 索引产物本地保留，提交说明里要讲清楚如何构建 |
| 实现 RAG 基本链路 | ✅ | query parse -> hard filter -> keyword/facet/vector/graph rerank -> prompt -> generation guardrail | 可以继续补 groundedness benchmark |
| 提供流式 API，SSE 或 WebSocket 均可 | ✅ | `POST /api/chat/stream`，事件包括 status/products/token/done/error；推荐场景先发送结构化商品卡，再随 token 流式输出嵌入文本 | 无明显缺口 |

### 模型能力

| 官方要求 | 状态 | 当前已做 | 缺口/下一步 |
| --- | --- | --- | --- |
| 理解模糊需求，例如“推荐护肤品” | ✅ | 信息不足时主动追问，不乱推商品；真实 API golden stream 三轮稳定 | 最终 Demo 前再做人工复验 |
| 从库内商品中检索 | ✅ | raw 100 条；25 条美妆 deep + 5 条服饰 deep + 70 条 thin；Chroma `products` collection 索引 100 条；全品类 smoke 7/7 PASS | 最终演示前再复验 Android 真实体验 |
| 给出合理推荐理由 | ◯ | 商品卡 reason 和回答基于召回商品资料；fallback 会引用商品营销文案、官方 FAQ 和用户评价边界；真实 API 流式结构稳定；高风险 case 已追加 AI semantic review | 最终 Demo 前挑 1-2 个案例人工复验表达自然度 |
| 不编造不存在的商品 | ✅ | 生成 prompt 限制只能提候选商品；商品卡来自数据源 | 可补“不存在商品”陷阱 case |
| 不编造价格 | ✅ | 商品卡价格来自数据源；guardrail 拦截未授权价格 | 已有规则 guardrail，可补 benchmark 证明 |
| 不编造优惠/库存/下单承诺 | ✅ | `FORBIDDEN_COMMERCIAL_CLAIMS` 拦截库存、优惠、满减、折扣、购买链接、下单等 | 可补官方演示说明 |
| 不编造功能/功效 | ◯ | 已有 groundedness cases，full mock / retrieval-only 11/11；prompt 要求基于资料；guardrail 拦截部分无证据绝对断言；fallback 会表达“资料未看到/不能保证”边界；P0-3/P0-4 已用真实 API 验证结果型绝对承诺、孕期/过敏和预算越界风险 | 完整 claim-level judge 尚未实现；当前用确定性初筛 + AI semantic review 做第一版证据 |

### 数据

| 官方要求 | 状态 | 当前已做 | 缺口/下一步 |
| --- | --- | --- | --- |
| 50-100 条脱敏电商数据即可 | ✅ | 官方 raw 数据共 100 条；100 条均通过 enriched 层进入统一索引和基础检索 | 说明 thin/deep 分层，避免被误解为所有品类同等深度 |
| 字段至少包含商品名、类目、价格、详情描述、主图 URL | ✅ | raw JSON + 图片；enriched 层补结构化属性 | 图片为本地 assets，不是外部 URL；需要解释为官方数据集图片路径 |
| 数据量不是核心，覆盖场景和属性质量更重要 | ✅ | 美妆 25 条结构化增强，服饰 5 条样例，70 条 thin 支持覆盖数码/食品/剩余服饰 | 食品/数码只承诺资料内基础问答和类目边界提示 |

## 明确不能踩的线

| 官方红线 | 状态 | 当前防线 | 缺口/下一步 |
| --- | --- | --- | --- |
| 不能用纯 Web / H5 方案替代原生 App | ✅ | Android Kotlin 原生 App | 无明显缺口 |
| Demo 不能需要大量手动配置 | ✅ | README、`.env.example`、Mock fallback、Demo 脚本和 `docs/20_reproducibility_and_dependencies.md` 已有 | 最终提交前再按检查表跑一轮 |
| 不能出现明显幻觉 | ◯ | 商品卡来自数据源；guardrail 拦截价格/库存/优惠/下单/部分无证据断言；evidence-aware fallback 已让 groundedness full mock / retrieval-only 达到 11/11；P0-3/P0-4 已覆盖 `GRD-L03/05/08/L01` 真实 API + AI review；150 元预算越界 bug 已修复 | 仍需在答辩材料中讲清“真实模型会越界，后置 guardrail / fallback 如何兜住” |
| 答辩时必须能解释架构、链路和关键代码细节 | ◯ | 架构文档、RAG 策略、`constraint_trace` / `safety_trace` / `source_trace`、评测报告已有 | 需要准备 3-5 句口头解释和关键代码入口 |

## 反幻觉验收口径

反幻觉不能用“模型永远不会错”来验收。更可靠的口径是：

> 在已定义的高风险场景里，系统能发现、拦截、修复或兜底；最终展示给用户的商品事实可以回到本地数据源。

当前采用四层证据：

| 层级 | 验收问题 | 当前证据 |
| --- | --- | --- |
| 检索层 | 是否把不满足预算、类目、排除条件的商品送进候选 | hard filter、metadata filter、conversation benchmark、groundedness retrieval-only |
| 生成层 guardrail | 是否拦截价格、优惠、库存、下单、无证据绝对功效或安全承诺 | `server/app/guardrails.py`、`scripts/check_generation_guardrails.py`、真实 API 高风险回归 |
| fallback / repair | 被拦截后是否回到“资料支持 / 资料未说明 / 不能保证”的边界 | evidence-aware fallback、FAQ/评价/营销文案证据输入 |
| benchmark / semantic review | 高风险 case 是否可复跑、可解释 | `data/eval/groundedness_cases.json`、`scripts/review_benchmark_with_ai.py` |

因此当前目标不是证明“零幻觉”，而是证明系统对官方红线有工程防线：不编造商品、价格、优惠、库存、下单承诺、成分存在性、功效和绝对安全结论。

### Claim-level judge 的定位

`claim-level judge` 指把回答拆成一条条事实主张，再逐条核对数据源是否支持。

示例：

| 回答主张 | 数据源是否支持 | 判定 |
| --- | --- | --- |
| 商品售价 170 元 | raw / card price 有 | 通过 |
| 商品适合油皮 | enriched 属性或评价有依据 | 通过 |
| SPF50+ | 商品资料明确写出 | 通过 |
| 一定不会闷痘 | 数据没有确定证据 | 不通过 |
| 不含酒精 | 资料未说明 | 不通过 |

短期只建议做 3-5 个高风险样例，不做完整大评测系统；它的价值是让“反幻觉”从整段观感变成逐条证据核对。当前已新增第一版样例集 `data/eval/claim_audit_samples.json`，覆盖 SKU 价格、SPF/补涂边界、敏感肌绝对安全、成分不存在和库存/优惠/下单承诺；可用 `python3 scripts/render_claim_audit_report.py --strict` 渲染为 `data/tmp/evals/claim_audit_report.md` 和 JSONL 明细。

## 多品类数据覆盖口径

为了同时满足“50-100 条数据”和“深度不要广度”，当前采用两层数据策略：

| 层级 | 范围 | 目标 |
| --- | --- | --- |
| 全品类薄支持 | 官方 raw 100 条商品 | 基础检索、商品卡片、图片、价格、类目、描述/FAQ/评价资料内回答 |
| 深度主线 | 25 条美妆 + 5 条服饰样例 | 肤质、功效、成分/禁忌、预算、排除条件、多轮、对比、反幻觉和 trace |

实现状态：`data/enriched/thin_products.jsonl` 已补 70 条，`scripts/build_index.py` 已构建 100 条统一 Chroma 索引；`data/eval/all_category_queries.json` 全品类 smoke 7/7 PASS，其中包含“早八提神不指定品类”回归：避免误召回方便食品，并把早八场景的咖啡优先级固定进 benchmark。

答辩口径：

> 系统底层使用官方 100 条商品作为统一商品库；美妆护肤是深度打磨品类，服饰是第二品类样例。数码和食品先提供基础资料内检索与展示，不做资料外参数、健康功效或安全承诺。

## 评分权重逐项对照

### 基础功能完整性 35%

| 官方关注点 | 状态 | 当前证据 | 缺口 |
| --- | --- | --- | --- |
| 原生 App | ✅ | Android Kotlin + Compose | 无 |
| 后端检索 | ✅ | FastAPI + retrieve pipeline | 无 |
| 模型生成 | ✅ | Doubao OpenAI-compatible + mock fallback | 真实 API 演示前复验 |
| 流式返回 | ✅ | SSE token | 无 |
| 商品卡片 | ✅ | 卡片、图片、详情弹窗 | 无 |

### 工程质量 25%

| 官方关注点 | 状态 | 当前证据 | 缺口 |
| --- | --- | --- | --- |
| 清晰目录 | ✅ | monorepo：client/server/data/docs/scripts | 无 |
| 接口设计 | ✅ | `docs/04_api_contract.md`，SSE 事件固定 | 无 |
| 错误处理 | ◯ | Mock fallback、guardrail fallback、无结果追问 | 可补后端断开/真实 API 失败的演示说明 |
| 依赖说明 | ✅ | `docs/20_reproducibility_and_dependencies.md` 已集中列出 Python、Android、Gradle、Chroma、模型配置和复现检查 | 最终提交前确认版本表仍与代码一致 |
| README | ✅ | 根目录 README | 最终提交前再收口 |
| 技术文档 | ✅ | architecture/evaluation/security/RAG strategy/schema docs | 文档较多，需给评委推荐阅读顺序 |

### 效果与可靠性 20%

| 官方关注点 | 状态 | 当前证据 | 缺口 |
| --- | --- | --- | --- |
| 检索准确 | ✅ | golden 8、subcategory 6、apparel 5、all-category smoke 7、comparison 3、groundedness retrieval-only 11 全部 PASS | 最终提交前再按复现检查表跑一轮 |
| 少幻觉 | ◯ | guardrail + failure case + evidence-aware fallback + groundedness full mock / retrieval-only 11/11；真实 API golden stream 三轮稳定；高风险真实 API 代表 case 已通过 AI semantic review | 生成层完整 claim-level judge 尚未实现；当前重点是把已有证据讲清楚 |
| 多轮可用 | ◯ | conversation 6 条 PASS，上下文继承、预算放宽/收紧和商品卡指代有覆盖 | 可补更多真实多轮问法 |
| 复杂约束可用 | ◯ | 预算、排除项、子类、信息不足、对比均有第一版 | 约束过紧无结果和过敏风险需要陷阱 case |
| UI 无明显 Bug | ◯ | loading 收尾、自动滚动、卡片详情已修 | 最终录屏前需要人工复验 |

### 加分项深度 20%

| 可选方向 | 状态 | 当前证据 | 建议 |
| --- | --- | --- | --- |
| 可解释 RAG / trace | ✅ | metadata filter、filter summary、ranking signals、graph hits、约束继承、安全边界和来源证据 trace | 作为主打亮点 |
| 多商品对比 | ✅ | comparison benchmark 3 条 PASS | 可作为辅助决策亮点 |
| 多品类扩展 | ✅ | 服饰 5 条 deep 样例 + 70 条 thin + 100 条统一索引 + all-category smoke 7/7 PASS | 不承诺所有品类都达到美妆深度；答辩时讲 thin/deep 分层 |
| Graph-aware retrieval | ◯ | 轻量 relation score 已进主链路 | 说明是轻量图关系，不是完整 GraphRAG |
| 反馈闭环 | ◯ | Android 端回答下方可点击 `有用` / `不准确`；`POST /api/feedback` 可记录最近上下文、回答、商品卡片到本地 JSONL；debug smoke test 可额外记录 retrieval trace | 目前是轻量反馈第一版，尚未做自动归因或自动转 benchmark |
| 拍照找货 / 多模态 | ⏸ | 尚未做 | 除非时间非常充裕，否则不抢主线 |
| 购物车 / 下单 | ⏸ | 尚未做 | 与核心 RAG 可靠性关系较弱，暂不做 |

## 基础 / 进阶 / 高级场景对照

| 官方场景 | 状态 | 当前证据 | 缺口 |
| --- | --- | --- | --- |
| 单轮模糊推荐 | ✅ | “我想买护肤品”会主动追问；油皮/敏感肌等 query 可推荐 | 无明显缺口 |
| 条件筛选 | ✅ | 预算、子类、肤质、场景、排除项已解析 | 可继续补陷阱 benchmark |
| 意图识别 | ◯ | QueryIntent 规则/词典解析 | 非常复杂表达还不保证 |
| 商品属性匹配 | ✅ | enriched 属性 + facet/graph score | 无明显缺口 |
| 参数抽取和范围过滤 | ✅ | `budget_max`、metadata filter、hard filter | 无明显缺口 |
| 推荐理由来自资料 | ◯ | prompt + 商品卡 + guardrail | groundedness benchmark 需要补强 |
| 多轮追问与细化 | ◯ | conversation benchmark 已覆盖部分 | 真实场景可继续扩展 |
| 主动澄清 | ✅ | 信息不足时追问，不乱推商品 | 无明显缺口 |
| 对比决策 | ✅ | 防晒/T恤/鞋对比 benchmark PASS | Android 真机演示可再复验 |
| 反选 / 排除约束 | ◯ | 不要酒精/刺激已有解析和多轮继承 | 陷阱 case 需要补强 |
| 购物车与下单 | ⏸ | 未做 | 暂不建议做 |
| 拍照找货 | ⏸ | 未做 | 暂不建议做 |
| 端侧体验优化 | △ | 流式、自动滚动、快捷问题、卡片/详情已有 | 没专门做性能指标 |

## 待办池：Groundedness / 反编造 Benchmark

先记录，不立即扩张成大任务。

1. **成分存在性**：用户问某商品是否含某成分，系统只能按商品资料回答，不能猜。
2. **成分功效外推**：用户说“听说某成分能 X”，系统不能替资料外功效背书。
3. **约束过紧无结果**：没有商品同时满足时，必须明确说没有，并询问放宽哪项条件。
4. **多轮排除条件继承**：用户前文说不要酒精/刺激，后文放宽预算时仍不能推荐踩雷商品。
5. **过敏/风险提醒**：用户提到过敏或商品资料写有风险时，必须提醒；资料未说明时不能保证安全。

建议落地文件：

```text
data/eval/groundedness_cases.json
scripts/run_groundedness_cases.py
scripts/review_benchmark_with_ai.py
```

当前进展：`data/eval/groundedness_cases.json` 已落地，包含 11 条人工标注 case，其中 3 条是 5-8 轮长对话。格式刻意保留了 `capabilities`、`why_hard`、`source_evidence`、`expect` 和 `reference_answer`，方便提交材料里解释“我们如何证明不编造”。`scripts/run_groundedness_cases.py` 已完成初版并在 2026-06-03 对齐 Android 商品卡 history；2026-06-04 加入 evidence-aware fallback 后，mock 全链路和 retrieval-only 均达到 11/11 PASS。同日真实 API 三轮全量复验显示：golden stream 8/8 stable PASS，groundedness real generation 3/11 stable PASS，这暴露出真实模型比 mock 更容易越界。P0-2 已新增 `constraint_trace`、`safety_trace`、`source_trace`，使多轮约束继承、风险边界和来源证据可以在 debug / benchmark 中解释。P0-3 已补 `unsupported_result_absence_claims`，拦截 `不会堵塞/不会长闭口/不会残留/不会过敏/绝对温和` 等结果型绝对承诺；`GRD-L03` 已完成真实 API 回归并通过 AI semantic review。P0-4 已扩到 `GRD-05/08/L01` 三条高风险真实 API case，并通过 AI semantic review；其中 `GRD-L01` 暴露出的 150 元预算越界 bug 已修复并复验。P0-5 已修正 AI review 口径：约束继承应进入内部 trace，不要求机械显示给用户。结论是检索、流式结构和内部证据链稳定，真实生成层仍需 guardrail / fallback，但已有可解释、可复跑的反编造证据。

## 现在最清楚的下一步

如果继续做代码，优先级：

1. 真实 Android 端体验复验：确认全品类后卡片、详情、图片、流式顺序仍稳定。
2. 最终 Demo / 答辩材料收口：把真实 API 可靠性证据、trace 解释、guardrail 兜底链路和全品类薄支持整理成 3-5 句可讲清楚的话。
3. 美妆深度线继续保持：Planner、多轮、反幻觉、trace 和 claim-level judge 主要围绕高风险美妆 case 做深。
4. 可选增强：做 3-5 个 claim-level judge 样例，或把 `inaccurate` 反馈样例自动沉淀为 benchmark。

如果只做方向确认，停止在这里即可，不继续开新功能。
