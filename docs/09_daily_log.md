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
