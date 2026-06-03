# 每日推进记录

## 2026-05-21

- 创建独立工程仓库计划。
- 锁定客户端技术栈：Android Kotlin 原生，优先 Jetpack Compose。
- 锁定第一阶段切片：美妆文字闭环。
- 数据策略：保留官方 raw 数据，新增 enriched 增强层。
- 完成 Android -> FastAPI -> 商品检索 -> mock 流式回复 -> 商品卡片展示的第一条端到端链路。
- 发现并修复 Android SSE 收尾问题：收到 `done` 后结束 loading，并将检索/生成状态改为临时状态条。
- 新增 [进度对照表](06_progress_tracker.md)，用于对照课题最终要求、当前完成度和下一步优先级。
- 补齐商品卡片点击详情第一版：后端在 `products` 事件中返回详情字段，Android 点击卡片打开详情弹窗。
- 接入商品图片第一版：后端通过 `/assets` 暴露官方数据集图片，Android 使用 Coil 加载卡片图和详情图。

## 2026-05-28

- 用真实 Doubao 跑通三轮 `probe_chat.py`：
  - 油皮 200 元内通勤防晒。
  - 短追问继承上一轮上下文。
  - 敏感肌修护 + 酒精/刺激排除条件，触发 guardrail 后二次改写成功。
- Android 端新增 3 个演示快捷问题 chip，绕开 adb / 现场演示中文输入不稳定的问题。
- Android 模拟器完成第一轮真实闭环复验：
  - 油皮通勤防晒：真实回复 + 商品卡片 + 图片。
  - 商品详情：价格、类目、适合、使用场景、卖点、注意事项。
  - 信息不足追问：不乱推商品，先追问肤质/预算/功效。
- 发现连续多轮后列表不会自动滚到底部，已补自动滚动并完成连续两轮复验。
- 新增 [Demo 脚本](12_demo_script.md)，用于录制第一版 1 分钟闭环 Demo。
- 本地录屏 `demo/录屏v1.mov` 已完成，视频文件按 `.gitignore` 规则不提交。
- 新增 [系统架构说明](10_architecture.md)，补齐 Android、FastAPI、RAG、Doubao、guardrail、数据层和验证状态。
- 扩展美妆数据到完整 25 条后，新增 6 条子类 query benchmark，覆盖洁面、眼霜、蜜粉、唇釉、眉笔、卸妆。
- Android 端将快捷问题扩展到 9 个，并抽样复验眼霜、蜜粉、卸妆三个新增子类；当前均能展示对应子类商品卡片。
- 重写 [评分点对照与阶段路线](07_scoring_alignment_workflow.md)，明确 V0/V1/V1.5/V2/V3 当前状态。
- 新增 [多品类 Enriched Schema 设计](15_multicategory_schema.md)，完成 V2-A 第一版 schema，并确定第二品类优先从服饰运动 5 条样例开始。
- 新增 [电商 Schema 外部参考调研](16_ecommerce_schema_references.md)，对照 Amazon、Google Merchant Center、Schema.org、淘宝开放平台和电商属性抽取研究，补回 `variants`、`attributes.specifications` 和 `source.attribute_provenance` 三个 V2-B 标注关键字段。
- 新增 `data/enriched/apparel_products.jsonl`，完成 5 条服饰运动 V2-B enriched 样例；后端改为加载 `data/enriched/*_products.jsonl`，并让检索文本纳入 `display`、`variants`、`category_attributes`、`retrieval` 和 `source`。
- 新增 `data/eval/apparel_queries.json`，服饰 5 条 query 全部 PASS；同步复跑美妆 golden、subcategory、conversation 和 generation guardrail，均 PASS。
- 将 Chroma 从旧的 `beauty_products` collection 升级为统一 `products` collection；`build_index.py` 现在索引全部 enriched 商品，并写入 `canonical_category`、`sub_category`、`base_price` metadata；服饰 benchmark 已可用 `--require-vector` 通过。
- 进入多商品对比切片：先复用现有聊天回复和多商品卡片，不新增复杂 UI；目标是支持“怎么选/哪个更适合/对比”类 query，并沉淀对比型 benchmark。
- 完成多商品对比第一版：新增 `data/eval/comparison_queries.json` 和 `scripts/run_comparison_queries.py`，覆盖两款防晒、两件 T 恤、跑步鞋/徒步鞋三类对比；3 条 comparison benchmark 全部 PASS，并同步复跑 apparel、subcategory、golden、conversation 和 generation guardrail，均 PASS。
- 完成 RetrievalTrace 可解释性增强第一版：trace 新增 `metadata_filter`、`filter_summary`、`ranking_signals`，并同步写入 golden、subcategory、comparison、conversation 的 JSONL 评测输出；完整回归通过。
- 开始 Graph-aware relation score 第一版：先用运行时派生的属性关系做小权重 rerank 和 trace 展示，不接重型图数据库。
- 完成 Graph-aware relation score 第一版：`retrieval_channels.graph` 和 `ranking_signals.graph` 已展示 category、sub_category、budget、facet、preference 等关系命中；comparison、golden、subcategory、apparel、conversation 和 generation guardrail 回归均 PASS。

## 2026-05-29

- 新增 [采分点确认与待办看板](17_scoring_todo_board.md)：按基础功能完整性、工程质量、效果与可靠性、加分项深度整理当前状态，并把 groundedness / 反编造 benchmark 的 5 个待办 case 先放入待办池，暂不扩张成代码实现。
- 新增 [官方采分点逐项对照表](18_official_scoring_checklist.md)：完全按官方“必做最小闭环、明确不能踩的线、评分权重、基础/进阶/高级场景”逐条标注 ✅ / ◯ / △ / ✕ / ⏸，用于判断哪些得分点已踩到、哪些还需要 benchmark 或提交材料收口。
- 新增 `data/eval/groundedness_cases.json`：把反编造/可溯源 case 扩展为 11 条人工标注 benchmark 草案，覆盖成分存在性、功效外推、约束过紧、多轮排除继承、过敏风险、有证据的无添加声明、商业承诺陷阱和孕期/不过敏安全边界；其中 3 条为 5-8 轮长对话。
- 新增 `scripts/run_groundedness_cases.py` 并完成初跑：mock 全链路 2/11 PASS，retrieval-only 7/11 PASS；真实 Ark / Doubao 抽样 `GRD-03`、`GRD-07` 为 2/2 PASS，且 `GRD-07` 验证了商业承诺触发 guardrail 后可回落到安全回答。

## 2026-05-31

- 新增 [Agentic RAG / LLM Planner 调研补充](19_agentic_rag_planner_research.md)：梳理为什么 groundedness benchmark 促使我们调研多轮 Planner、最新 agentic retrieval / logical retrieval / self-query / router 工作如何启发本项目，以及为什么短期不直接接入重框架，而是保留 `rule-only state merge -> optional lightweight planner -> validator` 的轻量路线。

## 2026-06-03

- 完成 rule-only conversation state merge 第一版：新增 `server/app/conversation_state.py`，在检索前合并多轮预算、类目、肤质、功效、场景、排除条件和偏好。
- 修复“预算可以放宽到300”被误当成取消预算的问题；现在有具体数字时更新预算，无具体数字时才取消预算。
- 修复“先不看预算，但酒精刺激还是不要”被误判成放宽排除条件的问题；排除条件会在多轮中默认继承。
- `POST /api/debug/retrieve` 新增 `conversation_state` trace，方便查看 state merge 是否应用以及具体 actions。
- 扩展 `data/eval/conversation_cases.json`：新增 `CQ-05` 5轮预算更新/取消预算/排除继承 case；conversation benchmark 从 4/4 扩展为 5/5 PASS。
- 同步回归：golden 8/8、beauty subcategory 6/6、apparel 5/5、comparison 3/3、generation guardrail PASS。
- 继续补齐商品卡指代第一版：Android history 现在回传 assistant 商品卡 `product_ids`；后端可将“第一款/它/这款”映射到上一轮商品，并新增 `CQ-06`，conversation benchmark 扩展为 6/6 PASS。
- 对齐 groundedness runner 和真实 Android history：runner 现在也把上一轮商品卡 `product_ids` 写入 assistant history，方便复现商品事实追问。
- 修补多轮 parser 小洞：支持 `预算放到300`，把“还有/另外/最好/顺便”等补充语识别为多轮延续，加入 `香精` 排除项，并避免把 `预算200以内` 的裸数字误判为第二款。
- 增加商品/品牌别名引用第一版：`欧莱雅`、`AIRism`、`DRY-EX` 等明确商品名会映射到商品 ID；商品事实追问不再被上一轮预算或子类过滤误杀。
- Groundedness retrieval-only 从 7/11 初跑推进到 9/11 PASS；定位出 `GRD-08` 和 `GRD-L02` 与 `p_beauty_007` raw 价格 `268` 和 benchmark 期望 `89/200元以内/100元以内` 冲突。
- 修正 groundedness case：`GRD-08` 改为 300 元内修护面霜，并允许 `p_beauty_007` / `p_beauty_012`；`GRD-L02` 将修护面霜轮次显式改为预算放宽到 300，参考价格改为 raw 数据中的 260/268。
- 修复“控油精华 -> 修护面霜”的意图切换：当前轮出现新子类并带“更偏/有没有/改看”等切换语义时，`sub_category` 和 `effect` 用当前轮覆盖旧状态，预算/肤质/排除条件继续继承。
- Groundedness retrieval-only 修正后达到 11/11 PASS；同步最终回归：conversation 6/6、golden 8/8、beauty subcategory 6/6、apparel 5/5、comparison 3/3、generation guardrail PASS。
