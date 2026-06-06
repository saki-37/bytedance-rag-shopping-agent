# 项目文档索引

## 背景与决策

- [课题梳理](01_topic_brief.md)
- [技术决策记录](02_technical_decisions.md)
- [数据集盘点](03_dataset_inventory.md)

## 工程文档

- [API 契约](04_api_contract.md)
- [Golden Queries](05_golden_queries.md)
- [进度对照表](06_progress_tracker.md)
- [评分点对照与推进工作流](07_scoring_alignment_workflow.md)
- [RAG 检索策略调研与设计](08_rag_retrieval_strategy.md)
- [每日推进记录](09_daily_log.md)
- [系统架构说明](10_architecture.md)
- [评测记录](11_evaluation_report.md)
- [Demo 脚本](12_demo_script.md)
- [安全与本地配置](13_security_and_config.md)
- [提交材料清单](14_submission_package.md)
- [多品类 Enriched Schema 设计](15_multicategory_schema.md)
- [电商 Schema 外部参考调研](16_ecommerce_schema_references.md)
- [采分点确认与待办看板](17_scoring_todo_board.md)
- [官方采分点逐项对照表](18_official_scoring_checklist.md)
- [Agentic RAG / LLM Planner 调研补充](19_agentic_rag_planner_research.md)
- [依赖版本与复现说明](20_reproducibility_and_dependencies.md)
- [Groundedness Case 全量分析](21_groundedness_case_analysis.md)
- [答辩口袋稿](22_defense_cheatsheet.md)
- [SKU 级同系列规格展示方案](23_variant_sku_display_plan.md)
- [商品对比表格工作流调研与方案](24_comparison_table_workflow_research.md)
- [Runtime Trace Log 与可追溯反馈闭环](25_runtime_trace_log_plan.md)
- [进阶路线调研顺序与取舍方案](26_advanced_route_research.md)

## 当前里程碑

第一阶段交付美妆文字闭环：

1. 数据检查与 25 条美妆增强数据。
2. FastAPI SSE 聊天接口。
3. Android Kotlin 原生聊天页、演示快捷问题、商品卡片与详情弹窗。
4. Golden queries、真实 API 三轮回归和 Android 端闭环复验。
5. README 提交入口、架构说明、评测记录、Demo 脚本和提交材料清单。
6. V2 多品类 schema 第一版设计与外部电商字段参考调研。
7. 服饰运动 5 条 enriched 样例和第二品类 query benchmark。
8. 依赖版本与复现说明集中成表，补齐工程质量里的复现友好度。
9. Evidence-aware fallback 和轻量反馈闭环 Android + 后端第一版。
10. 测试默认口径已调整为真实 API generation；mock / retrieval-only 只作为显式离线或结构检查。
11. Groundedness 11 条 case 已完成逐条归因分析，P0-3/P0-4/P0-5 已补真实 API 高风险回归、预算边界修复和 trace-aware AI review。
12. 答辩口袋稿已收口项目介绍、架构链路、可靠性证据、关键代码入口和当前边界。
