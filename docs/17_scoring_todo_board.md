# 采分点确认与待办看板

更新：2026-06-04

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
| 效果与可靠性 | 第一版可讲，但真实生成层需要继续加固 | golden、subcategory、apparel、comparison、conversation、groundedness full mock / retrieval-only 11/11；真实 API golden stream 三轮 8/8 stable PASS；guardrail；RetrievalTrace；graph relation score；evidence-aware fallback | 真实 API groundedness 三轮仅 3/11 stable PASS，下一步优先修真实生成层边界表达、repair prompt 或 claim-level judge |
| 加分项深度 | 已有主打方向 | 多商品对比、可解释 trace、轻量 graph-aware relation score、多品类 schema、服饰样例、轻量反馈闭环后端第一版 | 多模态/购物车不建议作为主线 |

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

## 当前执行顺序

当前状态：**基础闭环、evidence-aware fallback、轻量反馈闭环后端、真实 API 三轮复验、AI 语义复核脚本、内部 trace 分层、结果型绝对承诺 guardrail 均已有第一版**。下一步不再扩新大功能，而是把“真实回答是否可靠”变成可解释、可复跑、可答辩的证据链。

| 优先级 | 动作 | 目的 | 完成标志 | 主要文件 |
| --- | --- | --- | --- | --- |
| P0-0 | 提交当前 AI review 与文档修正 | 固定新的评测口径，避免后续又回到只看关键词 | `scripts/review_benchmark_with_ai.py` 和相关文档已提交 | `scripts/review_benchmark_with_ai.py`、`docs/11_*`、`docs/17_*`、`docs/18_*`、`docs/20_*`、`docs/21_*` |
| P0-1 | 升级 groundedness judge | 把硬字符串匹配升级为“确定性初筛 + 同义 claim + source check + AI/人工语义核验” | 第一批已完成：`GRD-01/02/04/L01` 新增 claim 配置；runner 输出 `judge_checks`；全量 mock groundedness 11/11 PASS | `data/eval/groundedness_cases.json`、`scripts/run_groundedness_cases.py`、`scripts/review_benchmark_with_ai.py` |
| P0-2 | 增加内部 trace 分层 | 记录约束继承、风险边界和强 claim 来源，不把推理句硬塞给用户 | 已完成：debug / benchmark 输出 `constraint_trace`、`safety_trace`、`source_trace`；全量 groundedness mock 11/11 PASS；conversation 6/6 PASS | `server/app/models.py`、`server/app/retrieval.py`、`server/app/conversation_state.py` |
| P0-3 | 加固真实生成层 guardrail / repair | 减少真实 Doubao 的资料外承诺和绝对安全说法 | 第一刀已完成：`unsupported_result_absence_claims` 拦截 `不会堵塞/不会长闭口/不会残留/不会过敏/绝对温和`；`GRD-L03` 真实 API PASS；AI review PASS；全量 groundedness mock 11/11 作为安全网 | `server/app/guardrails.py`、`server/app/llm.py` |
| P0-4 | 真实 API 回归 + AI 复核 | 证明修复后不是只在单个真实 case 或 mock 里好看 | 已完成第一轮：`GRD-05/08/L01` 真实 API + AI review；`GRD-L01` 暴露的 150 元预算边界 bug 已修复并复验 PASS | `scripts/run_*`、`scripts/review_benchmark_with_ai.py`、`docs/11_evaluation_report.md` |
| P0-5 | AI review / 评测口径对齐 | 约束继承应进入内部 trace，不要求机械显示给用户 | 已完成：AI review prompt 明确内部 trace 不必用户可见；`GRD-L01` trace-aware review 复跑 PASS, score=5, risk=low | `scripts/review_benchmark_with_ai.py`、`docs/11_evaluation_report.md` |
| P1-1 | Android 反馈按钮 | 把后端反馈闭环接到真实 demo 体验里 | 回答下方可点 `有用/不准确`，并写入 feedback JSONL | `client/android/...`、`server/app/feedback.py` |
| P1-2 | Demo / 答辩材料收口 | 降低评委理解成本，确保能讲清架构链路和关键代码 | 第一版已完成：`docs/22_defense_cheatsheet.md` 收口项目介绍、架构链路、可靠性证据、关键代码入口和边界说明 | `docs/12_demo_script.md`、`docs/14_submission_package.md`、`docs/20_reproducibility_and_dependencies.md`、`docs/22_defense_cheatsheet.md` |
| P2 | 暂缓的大功能 | 防止主线扩张 | 多模态、购物车、下单、全量非美妆标注都不作为当前主线 | 暂不改 |

执行原则：

1. 每完成一个 P0 小步，都跑 `git diff --check` 和 secret scan。
2. 涉及 benchmark 的改动，先跑确定性 runner，再跑 `scripts/review_benchmark_with_ai.py`。
3. 先用 3-4 条代表 case 做窄修复，确认方向对，再全量跑 11 条 groundedness case。
4. 如果真实 API 输出和关键词判定冲突，优先看 AI review / 人工语义核验，不直接按硬字符串定生死。
5. 用户可见回答只展示必要结论；约束继承、来源边界和安全判断进入 trace，供 debug、评测和答辩使用。

当前下一步：**最终复验与提交前检查**。P1-2 第一版已经完成；接下来不要再扩功能，优先按 `docs/20_reproducibility_and_dependencies.md` 和 `docs/14_submission_package.md` 跑一次真实 API、Android、secret scan 和录屏安全检查。

### P0：提交材料收口

目标：减少评委复现和理解成本。

待办：

1. 已补一页依赖和版本说明：Android Gradle Plugin、Kotlin、Compose、Python、FastAPI、Chroma、sentence-transformers、主要脚本运行方式。
2. README、提交材料清单、Demo 脚本、依赖复现说明和采分表已经同步到当前状态。
3. Demo 前仍需复验：真实 API 可用；Mock fallback 可用；录屏没有 API Key 或敏感终端信息。

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
scripts/review_benchmark_with_ai.py
```

当前进展：

- 已新增 `data/eval/groundedness_cases.json`，先把 case 格式和 11 条人工标注 case 固定下来。
- case 覆盖三类难度：`L1` 单点事实边界、`L2` 约束/风险/商业声明陷阱、`L3` 多轮上下文继承；其中 3 条是 5-8 轮长对话。
- 每条 case 包含：考察能力、困难点、来源证据摘要、用户问题、期望行为、禁止行为和参考回答。
- 已新增 `scripts/run_groundedness_cases.py`，把这些 case 转成可回归的自动检查。
- 初跑结果：mock 全链路 2/11 PASS，retrieval-only 7/11 PASS；真实 Ark / Doubao 抽样 2/2 PASS。
- 2026-06-03 复跑：runner 已对齐 Android 商品卡 history，补了预算 `放到300`、补充语延续、`香精` 排除和商品/品牌别名引用；retrieval-only 提升到 9/11 PASS。
- 已修正 `p_beauty_007` / `p_beauty_012` 价格证据和预算期望，并补上“控油精华 -> 修护面霜”的轻量意图切换规则；retrieval-only 进一步达到 11/11 PASS。
- 当前位置：检索层和 mock 生成层都已能稳定证明“不乱召回、不乱放宽约束、兜底回答引用证据边界”；真实 API 三轮全量回归显示 golden stream 8/8 stable PASS，但 groundedness real generation 只有 3/11 stable PASS。已新增通用 AI 语义复核脚本 `scripts/review_benchmark_with_ai.py`，用于在任意 benchmark JSONL 结束后追加 `semantic_score`、`likely_false_fail`、`likely_false_pass` 和问题清单。下一步如果继续补可靠性，应优先把 groundedness judge 升级为“确定性初筛 + AI/人工语义核验 + source check”，而不是继续扩 case 数量。
- P0-1 第一批已完成：`scripts/run_groundedness_cases.py` 新增 `answer_claims`、`forbidden_answer_claims`、`source_checks` 和输出字段 `judge_checks`；`GRD-01`、`GRD-02`、`GRD-04`、`GRD-L01` 已配置第一批同义 claim / 禁止 claim / source check。验证结果：4 个代表 case mock PASS；全量 groundedness mock 11/11 PASS；全量 mock AI review 11/11 PASS。

### P2：轻量反馈闭环

目标：对应课题里的“质量评测与反馈闭环”，但先做小。

最小实现：

1. Android 或 debug 接口提供 `有用` / `不准确` 反馈入口。
2. 后端把 `query`、`intent`、`products`、`trace`、`feedback` 写入本地 JSONL。
3. 文档展示一条“失败 query -> 归因 -> 下一轮修正”的例子。

当前进展：

- 已新增 `POST /api/feedback`，支持记录 `helpful` / `inaccurate`。
- 每条反馈写入 `data/tmp/feedback/feedback_YYYY-MM-DD.jsonl`，目录被 `.gitignore` 忽略。
- 记录内容不是只保存当前一句，而是保存有界证据快照：当前 query、最近 8 条 history、最终回答、商品卡片、clarification、retrieval message 和 `RetrievalTrace`。
- 已新增 `scripts/check_feedback_loop.py`，用 `/api/debug/retrieve` 构造一条带 trace 的反馈记录，验证端到端写入。

优先级判断：

- 它是贴近官方“质量评测与反馈闭环”的加分项。
- Android 端按钮还没有接入；目前是后端/debug 第一版，足够支撑“反馈闭环可记录、可复盘”的工程证据。

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
