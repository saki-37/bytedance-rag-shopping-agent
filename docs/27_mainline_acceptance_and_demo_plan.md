# 主线验收与 Demo 收口计划

日期：2026-06-07

用途：在 bug 修复和 UI 优化并行推进时，把当前主线的验收范围、Demo 路径、评分映射和最终集成检查固定下来。本文档不替代具体 benchmark，也不作为新功能需求池；它只回答一个问题：等代码收口后，我们怎么判断主线已经能讲、能演示、能提交。

## 当前背景

当前项目已经具备原生 Android + FastAPI + RAG + Doubao / Mock 流式回复 + 商品卡片 + 详情页 + 反馈按钮的完整闭环。最近又补了 SKU 同系列规格、Markdown / 表格展示、商品对比、trace 和 groundedness 相关能力。

与此同时，当前仓库里还有其他并行修改：

- bug 修复线：处理测试中暴露的商品指代、比较意图、检索排序和 groundedness 问题。
- UI 优化线：处理 Android 展示、卡片样式、图标和视觉细节。

因此本文档的边界是：**先不接管当前 dirty 代码，不抢正在修改的文件；只固定最终验收和演示的标准。**

## 收口目标

本轮收口不追求再开大功能，而是把已有能力变成可复现、可解释、可展示的证据包。

完成后需要能回答：

1. 这个导购 Agent 的主线闭环能不能真实跑通？
2. 用户在 Android 端看到的卡片、详情、对比和反馈是否自然？
3. 推荐和对比是否能回到商品资料，而不是模型自由编造？
4. 多轮指代、SKU 同系列、预算和排除条件是否有稳定行为？
5. 答辩时是否能把每个亮点对应到具体评分点和证据？

## 验收总原则

1. **先真实体验，再补脚本证据**：Android 真实链路优先于只看离线 runner。
2. **先高风险 case，再全量复查**：优先看最容易出错的指代、价格、SKU、表格和跨品类场景。
3. **只修阻断主线的问题**：视觉微调和高级功能不在本轮扩大。
4. **商品事实必须可追溯**：价格、规格、品牌、注意事项、FAQ、评论都应来自数据或 trace。
5. **Demo 口径保守**：不承诺购物车、下单、库存、真实交易、多模态或完整全品类深度标注。

## P0：并行改动收口后先做的集成验收

等 bug 修复线和 UI 优化线都说“可以验”以后，第一步不是继续写新功能，而是做一次集成状态确认。

检查项：

| 项目 | 验收方式 | 通过标准 |
| --- | --- | --- |
| 工作树范围 | `git status --short` | 能分清本轮要提交的 bug、UI、docs 和无关临时文件 |
| Python 语法 | `python3 -m py_compile server/app/main.py server/app/models.py server/app/retrieval.py server/app/conversation_state.py server/app/planner.py` | 无语法错误 |
| Android 编译 | `./gradlew :client:android:app:compileDebugKotlin` | Kotlin 编译通过 |
| 空白/冲突 | `git diff --check` | 无 trailing whitespace / conflict marker |
| 密钥检查 | `python3 scripts/scan_secrets.py --all` | 无 API key、token、私密配置进入 Git |

如果这里失败，优先修阻断项；不要开始录屏或写答辩稿。

## P1：Android 真实体验验收路径

以下路径用于真机或模拟器手动验收。每条都建议截图或短录屏留证据。

| 编号 | 用户路径 | 重点看什么 | 通过标准 |
| --- | --- | --- | --- |
| A1 | `我是油皮，想要200元以内通勤防晒` | 流式输出、商品卡片插入、SKU 同系列卡、价格和标签 | 推荐防晒类商品；预算不越界；同系列 SKU 展示清楚 |
| A2 | 点击防晒同系列商品详情 | SKU 标签切换、价格/规格/理由更新、FAQ/评论/注意事项分区 | 切换规格后字段同步变化；详情页不过度堆文字 |
| A3 | `可以帮我对比一下巴黎欧莱雅和安热沙吗？` | 具体商品名比较、表格、是否暴露 ID | 表格列为商品名，不出现 `p_beauty_*`；结论能说明适合谁 |
| A4 | `可以帮我对比一下产品1和3吗？` | 多轮指代、卡片顺序、比较对象 | 选择的确是上一轮第 1 和第 3 个商品，不错位 |
| A5 | `这几个里面哪个更适合敏感肌？` | 指代继承、风险边界、资料未说明 | 不把“未说明”说成“绝对安全”；必要时说明边界 |
| A6 | `早八想提神，有什么方便带的？` | 全品类 thin 支持、咖啡/功能饮料优先级 | 不把方便食品误当主要提神方案；能解释咖啡因边界 |
| A7 | 任意回答下点击 `有用` / `不准确` | 反馈按钮状态、后端写入 | UI 状态清楚；后端生成反馈 JSONL；不阻断聊天 |
| A8 | 连续发送两轮问题 | loading、按钮恢复、滚动到底部 | 发送中有思考态；完成后按钮恢复；最新消息可见 |

## P2：后端与生成层验收路径

后端验收不要求无限扩 benchmark，重点是复验高风险能力。

建议最小集合：

| 能力 | 推荐 case | 重点看什么 |
| --- | --- | --- |
| 多轮约束继承 | groundedness 长对话 case | 预算、排除词、风险条件是否继承正确 |
| 具体商品名指代 | 巴黎欧莱雅 vs 安热沙 | planner / conversation state 是否识别商品名 |
| 序号指代 | 产品 1 和 3 | 是否按上一轮可见商品顺序选择 |
| 比较误判 | 包含“比较合适 / 比较适合”的普通推荐 | 不应因为“比较”二字进入对比模式 |
| SKU 同系列 | `p_beauty_006` 30ml / 40ml | prompt、fallback、卡片 variants 是否一致 |
| 非美妆薄支持 | 早八提神、跑步鞋/徒步鞋 | 不混入明显无关品类 |
| 反编造 | 孕期、过敏、库存、优惠、下单承诺 | 不生成资料外确定承诺 |

建议命令：

```bash
python3 scripts/check_planner_contract.py
python3 scripts/run_conversation_cases.py
python3 scripts/run_comparison_queries.py --require-vector
python3 scripts/run_groundedness_cases.py
python3 scripts/check_generation_guardrails.py
python3 scripts/check_feedback_loop.py
```

如果真实 API 时间有限，优先抽样：

- 一个 SKU 同系列问题。
- 一个具体商品名对比问题。
- 一个序号指代对比问题。
- 一个高风险安全边界问题。
- 一个跨品类 thin support 问题。

## P3：Demo 主线脚本

最终录屏或现场演示建议只走一条清晰主线，不把所有功能都塞进去。

推荐 90 秒版本：

1. 打开 Android App，说明这是原生 Android 客户端。
2. 输入或点击 `油皮通勤防晒`，展示流式回复和商品卡片。
3. 展示同系列 SKU 标签切换，说明 30ml / 40ml 是同 parent 下的规格，不是模型编造的两款无关商品。
4. 点击详情页，展示价格、规格、推荐理由、FAQ、精选评论和注意事项。
5. 回到聊天，输入 `可以帮我对比一下巴黎欧莱雅和安热沙吗？`，展示 Markdown 表格对比。
6. 点一次 `不准确` 或 `有用`，说明反馈会沉淀为本地 JSONL，后续可转成 benchmark。

如果只有 60 秒，删掉第 5 步对比表，只保留防晒推荐、详情和反馈。

## P4：评分点映射

| 评分方向 | 我们展示什么 | 证据入口 |
| --- | --- | --- |
| 基础闭环 | Android 原生聊天、FastAPI SSE、流式回复、商品卡片、详情页 | `docs/12_demo_script.md`、Android 录屏 |
| RAG 检索 | 预算、肤质、场景、排除条件、Chroma、rerank、trace | `docs/08_rag_retrieval_strategy.md`、`docs/10_architecture.md` |
| 可靠性 | guardrail、fallback、groundedness cases、真实 API 抽样复验 | `docs/11_evaluation_report.md`、`docs/21_groundedness_case_analysis.md` |
| 多轮能力 | 约束继承、序号指代、商品名指代、对比意图 | `scripts/run_conversation_cases.py`、`scripts/check_planner_contract.py` |
| 结构化体验 | SKU 同系列卡、详情页分区、Markdown / 表格、反馈按钮 | Android 端验收截图、`docs/23_variant_sku_display_plan.md`、`docs/24_comparison_table_workflow_research.md` |
| 可追溯闭环 | Runtime trace、feedback JSONL、failure case 文档化 | `docs/25_runtime_trace_log_plan.md` |
| 工程质量 | README、依赖复现、secret scan、编译和测试脚本 | `docs/14_submission_package.md`、`docs/20_reproducibility_and_dependencies.md` |

## 不纳入本轮的事项

这些可以作为后续方向，但不应挤占当前主线验收：

1. 购物车、下单、库存扣减和真实交易 action。
2. 拍照找货、多模态图像相似度检索。
3. 语音输入和实时 ASR。
4. 全量非美妆商品的深度标注。
5. 大规模重构 Planner / Router / Agent 框架。
6. 完整自动 claim-level judge 平台化。

## 最终提交前检查单

提交或 push 前逐项确认：

- [ ] 并行 bug 修复线已确认可以验收。
- [ ] 并行 UI 优化线已确认可以验收。
- [ ] Android 真实体验 A1-A8 至少通过核心 A1-A5。
- [ ] 后端 P2 最小集合通过，失败项有记录和解释。
- [ ] 真实 API 抽样至少覆盖 SKU、对比、指代和安全边界。
- [ ] Demo 脚本能在 60-90 秒内讲清主线。
- [ ] 文档索引、README、提交清单与当前实现一致。
- [ ] `git diff --check` 通过。
- [ ] `python3 scripts/scan_secrets.py --all` 通过。
- [ ] 不提交 `.env`、本地向量索引、录屏原文件、临时反馈 JSONL。

## 如果验收失败，怎么处理

失败项按优先级处理：

1. **事实错 / 价格错 / 商品错位**：必须修，属于主线阻断。
2. **安全边界错 / 资料外承诺**：必须修或加 fallback / guardrail。
3. **Android 卡死 / loading 不结束 / 详情打不开**：必须修。
4. **表格换行、卡片边距、局部视觉不舒服**：只修明显影响演示的部分。
5. **高级功能缺失**：记录边界，不在本轮补。

## 下一步动作

当前最合适的下一步是等待并行 bug 修复线和 UI 优化线完成后，按本文档先跑 P0 集成检查，再跑 P1 Android 真实体验验收。验收通过后，再把结果同步回：

- `docs/06_progress_tracker.md`
- `docs/11_evaluation_report.md`
- `docs/12_demo_script.md`
- `docs/14_submission_package.md`
- `docs/22_defense_cheatsheet.md`

这一步完成后，项目就进入最终提交与录屏准备阶段。
