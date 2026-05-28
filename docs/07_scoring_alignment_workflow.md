# 评分点对照与推进工作流

日期：2026-05-26  
更新：2026-05-28
用途：把课题说明会的评分点、当前实现状态、缺口和下一步优先级放在同一个稳定参考文档里。每次开始推进前先看本页，避免被局部 UI 或单个 bug 带跑。

## 当前定位

当前项目已经跑通第一版端到端 MVP：

> Android Kotlin 原生输入文字 -> FastAPI 后端 -> 美妆商品检索 -> Doubao/Mock 流式回复 -> Android 展示回复、商品卡片、图片和详情弹窗。

当前版本已经从 **可演示骨架** 推进到 **第一版可录屏闭环**。最需要补强的是：

1. 多轮消息列表自动滚动已补并完成模拟器复验，需要录屏固化证据。
2. 全量美妆 25 条数据还没有全部增强，当前 enriched 仍是 6 条。
3. RAG 主链路已有 `RetrievalTrace`，系统架构说明已补齐，后续需要整理成最终提交说明。
4. 真实 Doubao 输出已有 guardrail 和二次改写，但还需要继续沉淀 failure cases。
5. 多商品对比、反馈闭环、Graph-aware retrieval 还没有进入主线。
6. 根目录 README 和提交材料清单已形成第一版入口；后续需要按平台要求裁剪/上传 Demo，并在扩展数据后更新评测证据。

## 评分维度对照

| 评分维度 | 权重 | 评审关注点 | 当前状态 | 风险判断 |
| --- | --- | --- | --- | --- |
| 基础功能完整性 | 35% | 客户端对话 -> 后端 RAG 检索 -> 模型生成 -> 流式返回 -> 商品卡片展示 | Android、FastAPI、SSE、真实 Doubao、商品卡片、图片、详情弹窗已完成第一版 | 已能录第一版 demo，仍需复验连续多轮体验 |
| 工程质量 | 25% | 代码结构、接口设计、错误处理、文档 | monorepo、API 契约、架构、进度、安全、评测、Demo、README、提交材料清单已有 | 结构清晰，后续需保持材料和真实实现同步 |
| 效果与可靠性 | 20% | 运行流畅、检索准确、无幻觉、复杂场景处理 | V1 检索、真实 Doubao probe、guardrail、二次改写、多轮 benchmark 已有 | 当前主要风险是数据覆盖和更细粒度 groundedness |
| 加分项深度 | 20% | 多模态、性能优化、交互创新，选 1-2 个做深 | RAG 可靠性与可解释 trace 已形成主打方向 | 下一步做多商品对比/反馈闭环，比拍照找货更稳 |

## 最小闭环完成度

| 模块 | 课题要求 | 当前状态 | 下一步 |
| --- | --- | --- | --- |
| 原生客户端 | iOS 或 Android 原生 App | 已完成第一版 Android Kotlin + Jetpack Compose | 录屏证明可运行 |
| 文字对话 | 对话窗口，支持发送文字 | 已完成 | 保持稳定 |
| 流式回复 | 接收并渲染 AI 流式回复 | 已完成 SSE token 渲染，真实 Doubao 已复验 | 复验自动滚动 |
| 商品卡片 | 回复中包含可点击商品卡片 | 已完成第一版并在 Android 端复验 | 录入 Demo 脚本 |
| 商品详情 | 点击卡片进入落地页或模拟详情 | 已完成详情弹窗并在 Android 端复验 | 录入 Demo 脚本 |
| 后端服务 | Python / Go / Node.js 任选 | 已完成 FastAPI 服务 | 补架构说明 |
| 向量数据库 | 集成向量数据库 | Chroma 已可构建并进入 trace | 扩展 enriched 数据后重建索引 |
| RAG 基本链路 | 检索库内商品并基于资料回答 | 结构化硬过滤 + keyword/facet/vector + trace | 整理架构说明 |
| 模型调用 | 调用大模型生成导购回复 | Doubao/Ark 真实 probe 和 Android 端复验已完成第一轮 | 继续沉淀 failure cases |
| 反幻觉 | 不编造商品、价格、优惠、库存、功效 | 商品卡字段来自数据源，guardrail + 二次改写已有 | 增加更细粒度 groundedness 校验 |

## 主攻加分项

当前不建议同时铺开购物车、下单、拍照找货。更合理的策略是：先把 **对话智能与 RAG 增强** 做深，再用 **工程质量与体验优化** 承托 Demo。

### 加分项 A：对话智能与 RAG 增强

优先实现：

1. 信息不足时主动追问。
2. 反选和排除条件，例如不要酒精、不要刺激、不要太油。
3. 多商品对比，例如防晒 A 和防晒 B 更适合谁。

答辩叙事：

> 我没有只做一个包装大模型的聊天框，而是把模糊需求、结构化过滤、向量召回、商品资料约束和推荐理由生成串成了一条可解释链路。

### 加分项 B：工程质量与体验优化

优先实现：

1. 首 token 时间和流式体验稳定。
2. 后端断开、模型超时、空输入等错误状态可理解。
3. 商品卡片、详情弹窗、图片加载稳定。
4. 用 golden queries 形成可重复评测。

答辩叙事：

> 这个项目关注端到端工程完整性：不只让模型能回答，还要让移动端、后端、检索、流式渲染和错误处理都能稳定配合。

## 当前优先级

### 当前实现顺序

本阶段按 `docs/08_rag_retrieval_strategy.md` 的算法路线推进：

1. `V0 当前 Baseline`：已有关键词/结构化 baseline，可跑 MVP。
2. `V1 Constraint-Aware Hybrid Retrieval`：当前最优先。
3. `V2 Graph-Aware Retrieval`：第二阶段加属性图关系分。
4. `V3 Verifier + Benchmark Loop`：与 V1 并行起步，后续深化。

### P0-A：提交材料入口收口

目标：让评委或自己换一台机器后能快速理解并复现当前闭环。

状态：第一版已完成。

已完成：

1. 更新根目录 `README.md`：
   - 项目定位。
   - 当前完成能力。
   - 运行后端和 Android 的步骤。
   - `.env` 配置说明，不暴露真实 Key。
   - Demo 录屏和文档入口。
2. 给出推荐阅读顺序：
   - `docs/10_architecture.md`
   - `docs/11_evaluation_report.md`
   - `docs/12_demo_script.md`
   - `docs/08_rag_retrieval_strategy.md`
3. 明确当前边界：
   - 文字美妆导购主线。
   - enriched 数据仍是 6 条。
   - 多模态、购物车、下单不在当前版本。
4. 新增 `docs/14_submission_package.md`：
   - 提交入口。
   - 评分点对照。
   - Demo 讲解顺序。
   - 运行和评测复现路径。
   - 提交前检查。

完成标准：

1. README 可以作为提交入口。
2. 运行命令不包含真实 API Key。
3. 文档入口完整。

后续维护：

1. 每次扩展数据、改检索、改 Demo 后同步更新 README 和提交材料清单。
2. 提交前确认录屏附件和代码仓库材料一致。

### P0-B：Demo 稳定性收口

目标：把现有真实闭环变成可稳定录屏的版本。

任务：

1. 复验消息列表自动滚动：
   - 连续点击 `油皮通勤防晒` 和 `敏感肌修护`。
   - 最新消息应该自动出现在可视区域。
2. 准备 1 分钟第一版 Demo：
   - 快捷问题触发。
   - 真实 Doubao 回复。
   - 商品卡片与图片。
   - 商品详情弹窗。
   - 信息不足主动追问。
3. 写 `docs/12_demo_script.md`。

完成标准：

1. Demo 不依赖中文输入法手动输入。
2. loading 能回到 `发`。
3. 录屏路径和复验结论写入评测报告。

### P0-C：Constraint-Aware Hybrid Retrieval 收口

目标：先把“硬约束、软偏好、信息不足、可解释 trace”从现有检索逻辑里拆清楚。Chroma 在这一阶段作为向量召回通道加入，但不是第一性约束来源。

任务：

1. 新增 `QueryIntent`：
   - `category_candidates`
   - `universal_constraints`
   - `facets`
   - `hard_constraints`
   - `soft_preferences`
   - `exclude_terms`
   - `needs_clarification`
   - `confidence`
2. 明确处理边界：
   - 明确预算：硬过滤。
   - 明确排除：过滤或极强降权。
   - 软偏好：排序加权。
   - 信息不足：先追问，不进入普通推荐。
3. 新增 `RetrievalTrace`：
   - query parse
   - hard filter
   - keyword hits
   - vector hits
   - final scores
   - guardrail checks
4. 重构 `retrieve()`，让返回结果不仅有 `cards/context`，还有可 debug 的 trace。
5. 继续确保商品卡片字段只来自 raw/enriched 数据源。

完成标准：

1. 至少 3 条 golden queries 能输出完整 trace。
2. “200 元以内”不会返回超预算商品。
3. “我想买护肤品”这类信息不足 query 会先追问。
4. 后端返回的商品与 query 有可解释匹配关系。

### P0-D：Chroma 向量召回进入主链路

目标：让向量召回成为 V1 的一个稳定通道，并用 benchmark 比较它和结构化约束的关系。

任务：

1. 构建 Chroma 索引。
2. 后端运行时真实使用向量召回。
3. trace 中记录 vector hits。
4. 对比：
   - 当前 baseline。
   - 纯 Chroma。
   - Constraint-aware + Chroma。

完成标准：

1. `scripts/build_index.py` 能稳定完成。
2. 至少 3 条 golden queries 经过 Chroma 通道。
3. 能说明纯向量在哪些场景会违反硬约束，constraint-aware 为什么必要。

### P0-E：Golden Query 评测表

目标：让“效果可靠性”有证据，而不是只靠口头感觉。评测从 V1 开始就要同步建立，不等所有功能完成。

任务：

1. 建立评测表，字段包括：
   - query
   - parsed intent
   - 期望召回
   - 实际召回
   - 是否超预算
   - 是否错误推荐
   - 是否编造价格/库存/优惠/功效
   - 是否应该追问
   - 实际是否追问
   - trace 是否完整
   - 备注和修正计划
2. 先覆盖 8 条 golden queries。
3. 每次修改检索或 prompt 后复跑。

完成标准：

1. 至少 8 条记录完整。
2. 能说明 1-2 个失败 case 如何被修正。
3. Demo 中可展示评测表截图或摘要。

### P0-F：真实 Doubao 流式复验

目标：在检索候选和 trace 可靠后，确认真实模型能被 Android 端稳定消费，并且不破坏证据约束。

任务：

1. 本地 `.env` 配置真实 `ARK_API_KEY`、`ARK_MODEL`，保持 `.env` 不提交。
2. `MOCK_LLM=false` 后启动后端。
3. Android 连续跑 3 条 query。
4. 记录是否出现超时、空 token、卡 loading、幻觉输出。
5. 检查模型文本是否只解释候选商品。

完成标准：

1. Android 端能看到真实模型流式输出。
2. loading 能正常结束。
3. 商品卡片和模型文本一致，不出现明显编造价格、优惠、库存。

### P1：复杂语义能力

目标：形成一个真正能讲的加分点。

任务：

1. 基于 V1 的 `needs_clarification` 做信息不足主动追问。
2. 基于 `exclude_terms` 做否定条件解析与排除。
3. 基于 V2 属性图做多商品对比。
4. 支持多轮补充条件，例如“再便宜点”“我其实是敏感肌”。

完成标准：

1. 每类能力至少有 2 条 query 可稳定演示。
2. 代码中能解释意图识别、过滤、后处理的策略。
3. 评测表能体现复杂语义能力提升。

### P1：提交文档与展示材料

目标：让评委能快速理解项目，而不是只看代码。

需要补充：

1. `docs/08_rag_retrieval_strategy.md`：RAG 检索调研、强约束处理和 benchmark 设计。
2. `docs/10_architecture.md`：整体架构和请求链路。
3. `docs/11_evaluation_report.md`：golden queries 评测结果。
4. `docs/12_demo_script.md`：3-5 分钟 Demo 脚本。
5. `docs/13_security_and_config.md`：API Key、`.env`、脱敏和提交注意事项。

## 每次开工工作流

每次开始推进前，按这个顺序看：

1. 看本文件，确认今天做的是 P0 还是 P1。
2. 看 `docs/06_progress_tracker.md`，确认当前实现状态。
3. 如果动接口，先看 `docs/04_api_contract.md`。
4. 如果动检索或模型，先看 `docs/05_golden_queries.md`。
5. 改完后至少做一项验证：
   - 数据脚本。
   - 后端接口。
   - Android 端手动验证。
   - golden query 复跑。
6. 把结论写回文档，不只留在聊天里。

## Demo 建议脚本

推荐 3-5 分钟展示顺序：

1. 打开 Android App，展示聊天界面。
2. 输入：“我是油皮，想要 200 元以内的通勤防晒。”
3. 展示流式回复、商品卡片和图片。
4. 点击商品卡片，展示详情字段来自数据源。
5. 输入：“我想买护肤品，你推荐什么？”
6. 展示 Agent 主动追问肤质、预算或具体需求。
7. 输入：“不要酒精味太重或者刺激感强的产品。”
8. 展示排除约束和温和选项。
9. 切到架构图，讲 Android -> FastAPI -> RAG -> Doubao -> SSE -> 商品卡片。
10. 展示 golden query 评测摘要。

## 答辩必须讲清楚的点

1. 为什么选择 Android Kotlin 原生。
2. FastAPI 在链路中负责什么。
3. SSE 流式回复如何被客户端消费。
4. RAG 为什么不是直接问模型。
5. 商品卡字段为什么可信，哪些字段来自数据源。
6. 如何防止模型编造价格、优惠、库存和功效。
7. 原始数据和 enriched 数据为什么分开。
8. 当前系统边界在哪里，下一步如何增强。

## 安全与提交注意事项

1. 共享 API Key 只放本地 `.env`，不能提交。
2. 说明会原始文档如果包含 API Key，不能原样进入公开仓库。
3. Demo 和文档中展示配置时必须脱敏。
4. 商品数据如果最终公开，需要确认是否允许公开；比赛私有仓库内可先保留。

## 下一步建议

当前最建议先做：

> 提交材料入口收口：更新 README，把架构、评测、Demo 和运行方式串起来。

原因：

1. Demo 和架构文档已经有了，README 是评委看到项目时的入口。
2. README 能把工程质量、效果证据和安全配置放在同一个可读位置。
3. 完成入口整理后，再扩数据或做 Graph-aware 会更踏实。
