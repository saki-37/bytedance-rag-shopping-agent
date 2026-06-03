# 评分点对照与阶段路线

日期：2026-05-26  
更新：2026-05-28

用途：把课题评分点、当前实现状态、V0/V1/V2/V3 路线和下一步优先级放在同一页。每次开始推进前先看本页，避免被局部 UI、单个 bug 或某个新想法带跑。

如果只想快速判断“哪些分已经比较稳、哪些待补”，优先看 `docs/17_scoring_todo_board.md`。本页保留更完整的阶段路线和实现解释。

## 当前定位

当前项目已经形成一个 **V1 可提交版本**：

> Android Kotlin 原生 App -> FastAPI `/api/chat/stream` -> 美妆商品 RAG 检索 -> Doubao/Mock 流式生成 -> Android 展示回复、商品卡片、图片和详情弹窗。

当前最准确的阶段判断：

| 阶段 | 名称 | 当前状态 | 判断 |
| --- | --- | --- | --- |
| V0 | 可跑端到端闭环 | 已完成 | Android、FastAPI、SSE、商品卡片、图片和详情弹窗都已跑通 |
| V1 | Constraint-Aware Hybrid RAG | 基本完成 | 25 条美妆 enriched 数据、Chroma、QueryIntent、显式 RetrievalTrace、golden/subcategory/conversation/comparison benchmark、guardrail 已有 |
| V1.5 | 提交材料和 Demo 稳定性 | 第一版完成 | README、架构、评测、Demo 脚本、提交材料、安全说明、1 分钟录屏均已有 |
| V2 | 多品类 / Graph-aware Retrieval | V2-A、V2-B、V2-C 第一版完成 | raw 总库 100 条；25 条美妆 + 5 条服饰进入 enriched；统一向量索引 + 轻量 graph relation score 已进主链路 |
| V3 | Verifier / Feedback Loop | 有雏形，未完整闭环 | 生成后 guardrail 和 failure case 有了，但用户反馈、失败 query 自动记录、groundedness judge 未完成 |

一句话说：**我们已经有保底可提交版本，接下来要做的是提高层次，而不是继续证明“能不能跑”。**

最新进展：统一 `products` collection + metadata filter 已完成并提交；**多商品对比** 第一版已完成，当前支持两款防晒、两件 T 恤、跑步鞋/徒步鞋这类“怎么选/哪个更适合/该买哪个” query，并已沉淀 `comparison_queries` benchmark；**RetrievalTrace 可解释性增强** 第一版也已完成，debug 和评测 JSONL 都能看到 `metadata_filter`、`filter_summary`、`ranking_signals`；**Graph-aware relation score** 第一版已进入主链路，trace 可展示 `graph_category`、`graph_sub_category`、`graph_effect`、`graph_price_within_budget` 等关系命中。下一步建议转入轻量反馈闭环或 groundedness judge。

## 评分维度对照

| 评分维度 | 权重 | 评审关注点 | 当前状态 | 下一步抓手 |
| --- | --- | --- | --- | --- |
| 基础功能完整性 | 35% | 客户端对话 -> 后端 RAG -> 模型生成 -> 流式返回 -> 商品卡片 | V0 已完成，并有 Android 端复验证据 | 保持稳定，必要时重录更干净 Demo |
| 工程质量 | 25% | 代码结构、接口设计、错误处理、文档、安全配置 | monorepo、API 契约、README、架构、评测、安全、提交材料已有 | 每次新增能力后同步文档和评测证据 |
| 效果与可靠性 | 20% | 检索准确、无幻觉、复杂场景处理 | V1 基本完成；预算、排除、追问、对比、显式 trace、guardrail 已有 | 补更细 groundedness |
| 加分项深度 | 20% | 多模态、性能优化、交互创新，选 1-2 个做深 | 当前主打 RAG 可靠性和可解释 trace；多商品对比和 graph-aware 第一版已有 | 下一步做反馈闭环或 groundedness judge |

## V0：可跑闭环

目标：证明这是一个真实全栈移动端项目，而不是脚本或静态页面。

当前状态：**已完成**。

已完成：

1. Android Kotlin + Jetpack Compose 原生 App。
2. FastAPI 后端。
3. `POST /api/chat/stream` SSE 流式接口。
4. Android 端展示：
   - 用户消息。
   - 助手流式回复。
   - 商品卡片。
   - 商品图片。
   - 商品详情弹窗。
5. Mock 和真实 Doubao 都完成过闭环复验。
6. 本地已有第一版 Demo 录屏。

V0 风险：

1. 录屏仍可更干净，但不影响功能成立。
2. 现场真实 API 依赖网络和 Key，Demo 前需要保留 mock fallback。

## V1：Constraint-Aware Hybrid RAG

目标：证明系统不是“把用户问题丢给大模型”，而是有约束解析、检索、证据控制和可评测能力。

当前状态：**基本完成，约 80%**。

已完成：

1. 数据层：
   - 25 条美妆商品已进入 `data/enriched/beauty_products.jsonl`。
   - raw 商品字段和 enriched 字段分离。
   - 商品卡字段来自数据源，不由模型自由生成。
2. 检索层：
   - `QueryIntent`：预算、肤质、功效、场景、排除条件、信息不足。
   - 预算硬过滤，例如 `200 元以内` 不返回超预算商品。
   - 排除条件解析，例如 `不要酒精`、`不要刺激`。
   - 信息不足时主动追问。
   - Chroma 向量召回进入主链路。
   - `RetrievalTrace` 可解释 query parse、filter、keyword/vector hits、final ranking。
3. 评测层：
   - 8 条 golden queries。
   - 6 条 subcategory queries。
   - 5 条 conversation cases。
   - 3 条 comparison queries。
   - 生成层 guardrail regression。
4. Android 端复验：
   - 油皮通勤防晒。
   - 信息不足追问。
   - 商品详情。
   - 眼霜、蜜粉、卸妆子类抽样。
5. 生成层：
   - Doubao/Ark OpenAI-compatible API 接入。
   - 生成后 guardrail 拦截编造价格、库存、优惠、下单承诺和无证据绝对断言。
   - 对 `unsupported_absence_claims` 已有 failure case 和二次改写策略。

尚未完成：

1. 对所有功效声明做细粒度 groundedness 校验。
2. 对比型 query 已有第一版 benchmark 和实现策略，但 Android 端真实演示还可继续复验。
3. 真实 Doubao 下的所有子类 query 尚未系统复验。
4. 纯向量、约束混合、graph-aware 三种检索版本的指标对比还没形成。

V1 下一步如果继续补强：

1. 扩展对比型 benchmark 到更多品类和更复杂约束。
2. 给真实 Doubao 输出继续沉淀 failure cases。
3. 把 guardrail 从“明显违规”推进到“声明是否有证据支持”。

## V1.5：提交材料与演示稳定性

目标：让评委或自己换一台机器后能快速理解项目、跑起项目、看懂亮点。

当前状态：**第一版完成，可继续收口**。

已完成：

1. 根目录 `README.md`。
2. `docs/10_architecture.md` 系统架构说明。
3. `docs/11_evaluation_report.md` 评测记录。
4. `docs/12_demo_script.md` Demo 脚本。
5. `docs/13_security_and_config.md` 安全和配置说明。
6. `docs/14_submission_package.md` 提交材料清单。
7. API Key 扫描脚本和 pre-commit hook。
8. 本地 1 分钟 Demo 视频。

仍可收口：

1. 把“当前主线是美妆，raw 总库是 100 条，后续可扩品类”写得更自然。
2. 如果时间允许，重录一个没有模拟器悬浮控制条/剪贴板提示的版本。
3. 随后每新增 V2/V3 能力，都同步更新 README、评测和提交材料。

## V2：多品类 / Graph-aware Retrieval

目标：证明当前系统不是只为美妆写死，而是可以扩展到多类目电商导购；同时让“为什么推荐”从字段匹配升级到关系匹配。

当前状态：**V2-A 多品类 schema 与外部电商字段参考第一版已完成，V2-B 服饰运动 5 条样例已进入统一 Chroma `products` collection 和后端检索链路**。

现状：

1. raw 总库已有 100 条：
   - 美妆护肤 25 条。
   - 数码电子 25 条。
   - 服饰运动 25 条。
   - 食品饮料 25 条。
2. enriched 当前覆盖 25 条美妆和 5 条服饰运动样例。
3. Chroma 当前统一索引 30 条 enriched 商品，并通过 metadata filter 限定 `canonical_category`、`sub_category` 和 `base_price`。
4. RAG 主 Demo 仍聚焦美妆；服饰运动样例已可通过 debug retrieval 和本地 benchmark 验证。
5. `docs/08_rag_retrieval_strategy.md` 已设计 V2 图结构：
   - product -> brand。
   - product -> category。
   - product -> sub_category。
   - product -> universal_facet。
   - product -> category_specific_facet。
   - product -> price_bucket。
   - product -> evidence_text。

V2 建议不要一步做全品类。建议拆成三步：

1. **V2-A：多品类 schema 设计**
   - 通用字段：价格、品牌、类目、子类目、场景、适合/不适合、注意事项。
   - 美妆字段：肤质、功效、成分、质地、禁忌。
   - 数码字段：性能、续航、屏幕、存储、用途、兼容性。
   - 服饰字段：材质、尺码、季节、版型、运动场景、天气条件。
   - 食品字段：口味、糖分、咖啡因、包装、过敏原、健康声明注意。
   - 设计文档见 `docs/15_multicategory_schema.md`。
   - 外部字段参考见 `docs/16_ecommerce_schema_references.md`。
2. **V2-B：第二品类 5 条 enriched 样例**
   - 推荐优先选 `服饰运动`。
   - 原因：材质、尺码、运动场景和主办方提到的“纯棉”这类约束更贴近，也能和美妆形成差异。
   - 当前已完成第一版：`data/enriched/apparel_products.jsonl` + `data/eval/apparel_queries.json`。
3. **V2-C：轻量属性图打分**
   - 不接 Neo4j，不接重型 GraphRAG。
   - 用本地 dict/JSON 构建 product-attribute relations。
   - 在 `RetrievalTrace` 中新增 `graph_hits` / `graph_relation_score`。
   - 当前已完成第一版：运行时派生 category、sub_category、budget、facet、soft preference 关系命中，作为小权重 rerank 信号，并写入 `retrieval_channels.graph` 与 `ranking_signals.graph`。

V2 完成标准：

1. 至少 1 个非美妆品类有 5 条 enriched 样例。
2. 至少 3 条跨品类或第二品类 query 能完成检索。
3. trace 中能看到 graph relation 命中。
4. 文档能说明：系统支持品类专属字段扩展，不是美妆写死规则。

## V3：Verifier / Feedback Loop

目标：让系统不仅能推荐，还能记录哪里错、为什么错、下一轮怎么修。

当前状态：**有雏形，未完整闭环**。

已有：

1. 生成后规则 guardrail。
2. `unsupported_absence_claims` failure case。
3. golden/subcategory/conversation benchmark。
4. 密钥扫描和提交前检查。

未完成：

1. 用户反馈按钮，例如“有用/无用”。
2. 失败 query 自动记录。
3. 推荐失败原因分类。
4. prompt / 数据增强 / 检索规则迭代记录。
5. LLM judge 或 Ragas groundedness 指标。

V3 建议拆成两层：

1. **轻量反馈闭环**
   - Android 卡片或回复下方加 `有用` / `不准确`。
   - 后端记录 query、intent、products、trace、feedback。
   - 先写本地 JSONL，不急着上数据库。
2. **Verifier 增强**
   - 检查推荐是否超预算。
   - 检查是否出现非候选商品。
   - 检查价格、库存、优惠、功效是否有数据源支持。
   - 对“资料中未说明”类问题保留谨慎措辞。

## 当前推荐优先级

### 第一优先级：多商品对比

状态：**第一版已完成**。

原因：

1. 统一 `products` collection + metadata filter 已完成，服饰样例也有 vector hits。
2. 对比是“辅助决策”的强展示点，能直接体现导购不是单品推荐。
3. 现在已有 `variants`、`specifications`、`attribute_provenance`，对比会比纯 prompt 模板更扎实。

完成标准：

1. 增加 1-2 条对比型 benchmark。
2. 回答按价格、适合人群、场景、注意事项给出选择建议。
3. Android 展示多张相关商品卡片。

当前验证：

1. 新增 `data/eval/comparison_queries.json`，覆盖两款防晒、两件 T 恤、跑步鞋/徒步鞋三类对比。
2. 新增 `scripts/run_comparison_queries.py`，检查 comparison mode、期望商品召回、子类范围和 vector hits。
3. `server/.venv/bin/python scripts/run_comparison_queries.py --require-vector` 已通过，3 条 case 全部 PASS。
4. 生成兜底回答已支持对比式结构：价格、适合对象、理由、注意事项和保守选择建议。

实现边界：

1. 第一版不新增复杂 UI；继续复用聊天回复和多商品卡片。
2. 优先支持同品类对比，例如两款防晒、两件 T 恤、跑步鞋/徒步鞋选择。
3. 若用户明确点名商品或品牌，召回必须覆盖被点名对象；若没有点名，则以同子类或相近用途商品做对比。
4. 回答必须使用商品卡片和 enriched 字段，不输出资料外价格、库存、优惠或功效。

### 第二优先级：RetrievalTrace 可解释性增强

状态：**第一版已完成**。

原因：

1. metadata filter 已经参与召回，但当前 trace 主要通过 vector hit reason 间接展示。
2. 答辩时如果能清楚展示“先按类目/子类/预算过滤，再向量召回，再 rerank”，会更容易讲清楚工程深度。
3. 后续 graph-aware relation score 也需要 trace 结构先留位置。

完成标准：

1. Trace 中显式展示 metadata filter。
2. Trace 中区分 category/sub_category/budget filter、keyword、vector、facet score。
3. debug 接口和评测 JSONL 能看到这些字段。

当前验证：

1. `RetrievalTrace` 新增 `metadata_filter`、`filter_summary`、`ranking_signals`。
2. `scripts/run_golden_queries.py`、`scripts/run_subcategory_queries.py`、`scripts/run_comparison_queries.py`、`scripts/run_conversation_cases.py` 的 JSONL 输出已包含上述字段。
3. comparison、golden、subcategory、apparel、conversation 和 generation guardrail 回归均 PASS。

### 第三优先级：反馈闭环

原因：

1. 是课题要求里的“质量评测与反馈闭环”的加分项。
2. 但它依赖 trace 和 benchmark，适合在 V2 后补。

完成标准：

1. 用户能标记推荐是否有用。
2. 后端记录 feedback JSONL。
3. 文档中能展示如何用失败 query 反哺 prompt 或数据增强。

### 已完成：Graph-aware Relation Score

状态：**第一版已完成**。

实现边界：

1. 不接 Neo4j，不接重型 GraphRAG 框架。
2. 运行时从 `canonical_category`、`sub_category`、`attributes`、`category_attributes` 派生轻量关系。
3. 只把 graph relation score 作为 rerank 的小权重信号，不覆盖预算、排除项和子类硬过滤。
4. `RetrievalTrace.retrieval_channels.graph` 展示 graph hits；`ranking_signals` 展示 graph 信号分桶。

完成标准：

1. 对当前 golden、subcategory、apparel、comparison query 不造成回归。
2. 对服饰/美妆 query 能看到 category、sub_category、facet、budget 等关系命中。
3. 评测 JSONL 可用于答辩解释“这不是纯向量召回，而是结构化关系 + 向量 + 关键词/facet 的混合检索”。

当前验证：

1. `retrieval_channels.graph` 已输出 graph hits。
2. `ranking_signals.graph` 已显示最终商品的关系信号。
3. comparison、golden、subcategory、apparel、conversation 和 generation guardrail 回归均 PASS。

## 当前不建议优先做

1. 图片输入 / 拍照找货：
   - 多模态是加分项，但工程和调试成本高。
   - 当前更稳的加分点是 RAG 可靠性、多品类和可解释性。
2. 购物车 / 下单：
   - 与当前课题核心“导购决策辅助”关系弱。
   - 容易把范围拉散。
3. 全量 75 条非美妆一次性标注：
   - 成本高，且短期不一定提升 Demo。
   - 先做 5 条第二品类样例更稳。

## 每次开工工作流

每次开始推进前，按这个顺序看：

1. 看本文件，确认今天做的是 V1 收口、V2 扩展，还是 V3 闭环。
2. 看 `docs/06_progress_tracker.md`，确认当前实现状态。
3. 如果动接口，先看 `docs/04_api_contract.md`。
4. 如果动检索或模型，先看 `docs/05_golden_queries.md` 和 `docs/08_rag_retrieval_strategy.md`。
5. 改完后至少做一项验证：
   - 数据脚本。
   - 后端接口。
   - Android 端手动验证。
   - golden/subcategory/conversation query 复跑。
6. 把结论写回文档，不只留在聊天里。

## 答辩必须讲清楚的点

1. 为什么选择 Android Kotlin 原生。
2. FastAPI 在链路中负责什么。
3. SSE 流式回复如何被客户端消费。
4. RAG 为什么不是直接问模型。
5. 商品卡字段为什么可信，哪些字段来自数据源。
6. 如何防止模型编造价格、优惠、库存和功效。
7. 原始数据和 enriched 数据为什么分开。
8. 当前主线为什么聚焦美妆，以及如何扩展到多品类。
9. V1 的约束感知检索和 V2 的 graph-aware retrieval 有什么区别。

## 安全与提交注意事项

1. 共享 API Key 只放本地 `.env`，不能提交。
2. 说明会原始文档如果包含 API Key，不能原样进入公开仓库。
3. Demo 和文档中展示配置时必须脱敏。
4. 商品数据如果最终公开，需要确认是否允许公开；比赛私有仓库内可先保留。
5. 提交前运行：

```bash
git diff --check
python3 scripts/scan_secrets.py --all
```
