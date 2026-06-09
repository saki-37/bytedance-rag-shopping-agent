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
- [主线验收与 Demo 收口计划](27_mainline_acceptance_and_demo_plan.md)
- [LLM Provider 切换与演示模型候选](28_llm_provider_switching.md)
- [2026-06-08 评分表进度快照](29_scoring_progress_snapshot_20260608.md)
- [场景化组合推荐 Planner 实现记录](30_scene_bundle_planner_implementation.md)
- [本地 ASR 后端接入方案](31_local_asr_backend_integration.md)
- [TTS 语音播报方案记录](32_tts_voice_broadcast_plan.md)
- [首屏极速响应与临时聊天气泡方案](33_first_screen_fast_response_plan.md)
- [用户记忆与本地偏好层方案](34_user_memory_profile_plan.md)
- [安卓无障碍 P0 执行计划（语音播报 + 字号 + 低视力）](35_accessibility_p0_execution_plan.md)
- [安卓无障碍 P0 执行清单（AI 伙伴工单）](36_accessibility_p0_execution_checklist.md)

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
13. 2026-06-07 主线收口完成：多轮比较意图污染、肤质正向证据过滤、跑步鞋/徒步鞋用途排序、SKU 回答匹配点和 groundedness mock 边界已修；conversation 7/7、comparison 3/3、groundedness mock 11/11、Android Kotlin 编译和反馈闭环均通过。
14. Claim-level judge 样例已落地：5 个高风险人工标注样例、8 条 claim，可渲染 Markdown/JSONL 报告，用于展示“逐条事实主张如何回到数据源”。
15. LLM provider 切换文档已补齐：正式评测默认 Ark / Doubao，演示可临时用命令行覆盖到 Yunwu，并记录 `gpt-5.4-mini`、`gemini-3.5-flash`、`claude-sonnet-4-6` 和 `gpt-4o-mini` 候选。
16. 场景化组合推荐 Planner 第一版已落地：Planner 输出 `scene_bundle + search_slots`，retrieval 按结构化计划跨类目选品；三亚度假 case 已有真实 API Planner probe 和 `FR-012` 回归。
17. 首屏极速响应 UX 已落地：`quick_reply` SSE 事件、Android 临时气泡、ephemeral history 过滤、本地打字机动画和 `stage_timings_ms` trace 均已接入。
18. 快速响应边界已收口：`FAST_QUICK_REPLY_DEADLINE_SECONDS` 只影响临时气泡，不截断 Planner 或向量检索；复杂跨类目 case 已验证 Planner 完整 applied。
19. 用户记忆与本地偏好层方案已补齐：建议先做本仓库 local provider 薄层，硬约束结构化执行，Mem0 仅作为后续软记忆可选增强。
