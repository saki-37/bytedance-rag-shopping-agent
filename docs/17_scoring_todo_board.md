# 采分点确认与待办看板

更新：2026-06-03

用途：把“现在能拿哪些分、哪些还只是第一版、哪些先记下来不扩张”放在一页。每次想继续做功能前，先看这页，避免把局部想法误当成主线。

如果需要逐条对照官方采分点和场景层级，看 `docs/18_official_scoring_checklist.md`。本页保留更短的方向判断和待办池。

## 当前一句话判断

项目已经有一个可提交的端到端版本：Android 原生客户端、FastAPI 后端、RAG 检索、Doubao/Mock 流式回复、商品卡片、详情、图片、评测脚本和安全配置都已形成闭环。

接下来最值得补的不是再开大功能，而是把“回答不编造、资料可追踪、失败可复盘”做成更强的证据。

## 按官方采分点看当前状态

| 采分点 | 当前状态 | 已有证据 | 还缺什么 |
| --- | --- | --- | --- |
| 基础功能完整性 | 稳定可拿 | Android -> FastAPI -> RAG -> Doubao/Mock -> SSE -> 商品卡片；图片和详情弹窗已跑通 | 录屏可更干净；最终演示前再人工复验一次 |
| 工程质量 | 基本可拿 | monorepo、README、API 契约、架构文档、评测报告、安全配置、密钥扫描、依赖版本与复现说明 | 最终提交前按复现检查表再跑一轮 |
| 效果与可靠性 | 第一版可拿，仍值得补强 | golden、subcategory、apparel、comparison、conversation、groundedness retrieval-only benchmark；guardrail；RetrievalTrace；graph relation score | 生成层 evidence-aware fallback 和真实 Doubao failure cases 还可以继续沉淀 |
| 加分项深度 | 已有主打方向 | 多商品对比、可解释 trace、轻量 graph-aware relation score、多品类 schema 和服饰样例 | 反馈闭环还没做；多模态/购物车不建议作为主线 |

## 能确认已经完成的点

1. **端到端闭环**：客户端能发文字，后端能检索，模型能流式回复，客户端能显示商品卡片。
2. **商品证据约束**：商品卡片价格、品牌、图片、标签来自数据源，不由模型生成。
3. **约束感知检索**：预算、子类、排除条件、信息不足追问已经进入检索逻辑。
4. **可解释检索**：trace 中已有 `metadata_filter`、`filter_summary`、`ranking_signals`、`retrieval_channels.graph`。
5. **反编造第一版**：已经拦截价格、库存、优惠、下单承诺和部分无证据绝对断言。
6. **多品类扩展证明**：除了 25 条美妆，已有 5 条服饰样例进入统一索引并通过 benchmark。
7. **对比决策第一版**：两款防晒、两件 T 恤、跑步鞋/徒步鞋对比 benchmark 已通过。

## 需要补、但不要一次全做的点

见下方执行顺序。这里的原则是：先把已完成能力变成稳定证据，再决定是否开反馈闭环或生成层增强。

## 执行顺序

| 顺序 | 动作 | 目的 | 完成标志 |
| --- | --- | --- | --- |
| Step 0 | 提交当前采分表和待办看板 | 固定方向盘，避免后续继续口头漂移 | `17_scoring_todo_board.md`、`18_official_scoring_checklist.md` 已提交 |
| Step 1 | Groundedness / 反编造 Benchmark | 把“不能编造”从原则变成可回归证据 | 已新增 groundedness cases 和脚本；retrieval-only 11/11 PASS |
| Step 2 | 依赖版本 / 复现说明表 | 补工程质量里的复现友好度 | 已新增 `docs/20_reproducibility_and_dependencies.md`，集中说明 Android/Python/Chroma/模型配置与复现检查 |
| Step 3 | 轻量反馈闭环 | 对应质量评测与反馈闭环加分点 | 后端或 debug 入口能记录 feedback JSONL |
| Step 4 | Demo 与提交材料收口 | 降低评委理解成本和现场风险 | README、提交包、Demo、secret scan 最终确认 |

当前正在执行：**Step 4 的文档状态收口**。这是在开新功能前把所有文档同步到当前真实状态，避免旧待办继续误导优先级。

### P0：提交材料收口

目标：减少评委复现和理解成本。

待办：

1. 已补一页依赖和版本说明：Android Gradle Plugin、Kotlin、Compose、Python、FastAPI、Chroma、sentence-transformers、主要脚本运行方式。
2. 最终检查 README、提交材料清单、Demo 脚本是否能独立说明项目。
3. Demo 前复验：真实 API 可用；Mock fallback 可用；录屏没有 API Key 或敏感终端信息。

### P1：Groundedness / 反编造 Benchmark

目标：证明系统不是只“看起来会回答”，而是知道什么时候不能编。

先记下的 5 个 case：

1. **成分存在性**：用户问某商品是否含某成分，系统只能按商品资料回答，不能猜。
2. **成分功效外推**：用户说“听说某成分能 X”，系统不能替资料外功效背书。
3. **约束过紧无结果**：没有商品同时满足时，必须明确说没有，并询问放宽哪项条件。
4. **多轮排除条件继承**：用户前文说不要酒精/刺激，后文放宽预算时仍不能推荐踩雷商品。
5. **过敏/风险提醒**：用户提到过敏或商品资料写有风险时，必须提醒；资料未说明时不能保证安全。

通过标准：

```text
必须基于商品资料；不能编造成分、功效、绝对安全性；信息不足时要说明资料未支持或主动追问。
```

建议落地文件：

```text
data/eval/groundedness_cases.json
scripts/run_groundedness_cases.py
```

当前进展：

- 已新增 `data/eval/groundedness_cases.json`，先把 case 格式和 11 条人工标注 case 固定下来。
- case 覆盖三类难度：`L1` 单点事实边界、`L2` 约束/风险/商业声明陷阱、`L3` 多轮上下文继承；其中 3 条是 5-8 轮长对话。
- 每条 case 包含：考察能力、困难点、来源证据摘要、用户问题、期望行为、禁止行为和参考回答。
- 已新增 `scripts/run_groundedness_cases.py`，把这些 case 转成可回归的自动检查。
- 初跑结果：mock 全链路 2/11 PASS，retrieval-only 7/11 PASS；真实 Ark / Doubao 抽样 2/2 PASS。
- 2026-06-03 复跑：runner 已对齐 Android 商品卡 history，补了预算 `放到300`、补充语延续、`香精` 排除和商品/品牌别名引用；retrieval-only 提升到 9/11 PASS。
- 已修正 `p_beauty_007` / `p_beauty_012` 价格证据和预算期望，并补上“控油精华 -> 修护面霜”的轻量意图切换规则；retrieval-only 进一步达到 11/11 PASS。
- 当前位置：检索层已经能稳定证明“不乱召回、不乱放宽约束”；下一步如果继续补可靠性，应优先做 evidence-aware fallback 或相似替代推荐，而不是继续扩 case 数量。

### P2：轻量反馈闭环

目标：对应课题里的“质量评测与反馈闭环”，但先做小。

最小实现：

1. Android 或 debug 接口提供 `有用` / `不准确` 反馈入口。
2. 后端把 `query`、`intent`、`products`、`trace`、`feedback` 写入本地 JSONL。
3. 文档展示一条“失败 query -> 归因 -> 下一轮修正”的例子。

优先级判断：

- 它是贴近官方“质量评测与反馈闭环”的加分项。
- 但在开做前，应先完成文档状态收口，并确认是否要优先补生成层 evidence-aware fallback。

### P3：暂不作为主线

1. 拍照找货 / 图片输入：加分但成本高，容易拉大范围。
2. 购物车 / 下单：偏交易链路，不是当前 RAG 可靠性主线。
3. 全量 75 条非美妆标注：可以做，但短期不如 groundedness benchmark 更能说明能力。

## 下一个 25 分钟入口

如果目标是恢复方向感：

1. 打开本页。
2. 只看“按官方采分点看当前状态”和“执行顺序”。
3. 写下：

```text
1. 我认为当前最稳的采分点是：____
2. 我认为最值得补强的采分点是：____
3. 我今天只做一个最小动作：____
```

到这里停止，不继续写代码。
