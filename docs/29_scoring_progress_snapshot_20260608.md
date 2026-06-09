# 2026-06-08 评分表进度快照

用途：把当前主线进度严格按官方采分口径重新归档，作为提交前讨论和答辩材料收口的临时快照。本页不接管并行修改中的 `docs/17_scoring_todo_board.md`、`docs/18_official_scoring_checklist.md` 和 UI / provider 文档；只记录本轮已验证事实。2026-06-09 已追加说明：后续提交准备中，多模态图片输入、ASR 语音输入和 TTS 播报已接入代码，需最终设备/provider/sidecar 复验后决定演示占比。

## 官方权重对照

| 官方采分块 | 权重 | 当前判断 | 证据 | 仍需收口 |
| --- | ---: | --- | --- | --- |
| 基础功能完整性 | 35% | ✅ 基本稳 | Android 原生聊天、FastAPI RAG、真实 Ark / Doubao 流式、商品卡片、详情页、SKU 同系列卡、Markdown 表格均已端上可见 | 最终录屏前再跑一次 Android 核心路径 |
| 工程质量 | 25% | ✅ 基本稳 | monorepo 结构、API 契约、架构/评测/安全/依赖文档、benchmark 脚本、trace 和 feedback 记录链路已有 | 当前 dirty 文件较多，最终提交前需要分线合并、secret scan 和全量 `git diff --check` |
| 效果与可靠性 | 20% | ◯ 有真实 API 证据，但仍是答辩重点 | 本轮真实 API `golden stream` 8/8 PASS；failure regression 12/12 PASS；conversation 7/7 PASS；Android 真实多轮复测通过防晒、T 恤、咖啡和信息不足追问；三亚场景组合 Planner probe 真实 API PASS | 真实模型仍会触发 guardrail，答辩要讲清 repair / fallback 边界；groundedness real generation 仍不能说“全量稳定” |
| 加分项深度 | 20% | ◯ 主打方向清晰 | SKU 同系列规格、商品对比表、可解释 trace、轻量 graph-aware relation score、反馈闭环、claim-level audit 样例、场景化组合推荐 Planner search slots、图片输入、ASR 语音输入和 TTS 播报已有 | 不建议再开购物车、下单等大功能；图片/语音只在最终验证稳定时放主视频 |

## 本轮新增证据

| 项目 | 结果 | 说明 |
| --- | --- | --- |
| 真实 API health | PASS | `/health` 返回 `mock_llm=false`、`llm_provider=ark`、真实 model endpoint |
| 真实 API golden stream | PASS | `scripts/run_golden_queries.py --mode http --check-stream --require-vector`，8/8 PASS；澄清场景 `GQ-08` 为 `products=[]` |
| failure regression | PASS | `scripts/run_failure_regression_cases.py`，12/12 PASS；`FR-011` 锁住“多轮后泛护肤需求不能继承旧防晒/咖啡条件”，`FR-012` 锁住“三亚场景组合不能只召回美妆防晒” |
| conversation regression | PASS | `scripts/run_conversation_cases.py`，7/7 PASS；本地 planner 连接失败时降级到 rule-only，这部分只作为结构回归证据 |
| Android 真实多轮 | PASS | 同一会话依次点击防晒、T 恤对比、早八咖啡、信息不足追问；最终护肤泛需求正确追问，不追加旧商品卡 |
| trace 复核 | PASS | 最新 trace 显示 `message=我想买护肤品，你推荐什么？`、`products=[]`、`needs_clarification=True` |
| 三亚场景组合 Planner probe | PASS | `PLANNER_TIMEOUT_SECONDS=30 server/.venv/bin/python scripts/probe_planner.py --case scene_bundle_sanya --repeat 1`；真实 API 返回 `recommendation_mode=scene_bundle`、beauty/apparel 两个 `search_slots`、`validation_errors=[]` |

截图证据：

```text
/private/tmp/rag-real-retest-sunscreen.png
/private/tmp/rag-real-retest-tshirt.png
/private/tmp/rag-real-retest-coffee-done.png
/private/tmp/rag-real-retest-clarify.png
```

## 已修或已记录的问题

| 问题 | 根因 | 当前处理 | 评分影响 |
| --- | --- | --- | --- |
| 真实 API guardrail repair crash | repair prompt 内使用 `cards`，但 `_collect_*_repair` 没有接收该参数 | 已补 `cards` 参数传递；真实 API 触发 guardrail 后不再因 `name 'cards' is not defined` 直接掉回异常 | 提升效果与可靠性，尤其是反幻觉防线可演示性 |
| 澄清场景 stream 检查误判 | 评测脚本曾要求所有 stream 都必须有 `products` 事件，但 API 契约里澄清流不发送商品 | 已调整 golden stream 检查：推荐场景要求 `products`，澄清场景要求没有 `products` | 保持 API 契约准确，避免假失败 |
| 多轮历史后泛需求继承旧条件 | `我想买护肤品，你推荐什么？` 被短句 follow-up 规则误判，继承前文防晒 / T 恤 / 咖啡条件 | 已新增 self-contained clarification 判断，并沉淀 `FR-011` | 支撑主动澄清和多轮可靠性 |
| 三亚度假方案只推荐防晒 | Planner 曾把“从防晒到穿搭的一套方案”收窄成 `beauty + 防晒`，retrieval 随后只召回美妆防晒 | Planner contract 新增 `recommendation_mode=scene_bundle` 和 `search_slots`；retrieval 只执行 Planner 标记的场景组合跨类目选品；沉淀 `FR-012` 和真实 Planner probe | 支撑官方“场景化组合推荐 / 跨类目检索 + 场景理解 + 组合编排”进阶点 |

## 对官方场景的当前覆盖

| 官方场景 | 当前状态 | 当前证据 |
| --- | --- | --- |
| 单轮模糊推荐 | ✅ | 泛护肤品会主动追问，不乱推商品 |
| 条件筛选 | ✅ | 油皮、预算、通勤、防晒等条件可进入检索和生成 |
| 意图识别 | ◯ | 规则 + Planner 第一版；真实 API 验证通过核心路径；场景化组合已由 Planner 输出 `scene_bundle + search_slots`，但 Planner 延迟仍需保守说明 |
| 商品属性匹配 | ✅ | 商品卡、SKU variant、表格字段来自结构化数据 |
| 参数抽取和范围过滤 | ✅ | 预算、类目、子类、排除条件有 hard filter / trace |
| 推荐理由来自资料 | ◯ | 商品卡和 fallback 有证据边界；真实模型输出仍靠 guardrail / repair 兜底 |
| 多轮追问与细化 | ◯ | conversation 7/7、failure regression 11/11；Android 多轮真实复测通过 |
| 主动澄清 | ✅ | `我想买护肤品，你推荐什么？` 在真实 Android 多轮后仍正确追问 |
| 对比决策 | ✅ | Markdown 表格、T 恤对比和防晒 SKU 对比均已端上可见 |
| 反选 / 排除约束 | ◯ | guardrail 和 groundedness case 有第一版，仍需最终讲清边界 |
| 购物车与下单 | ⏸ | 未做，不作为当前主线 |
| 拍照找货 / 多模态 | △ | 2026-06-09 后已接入图片上传、`image_plan` 和 text-first RAG；不是图像向量搜同款，需最终实机/provider 验证 |
| 语音输入 / TTS | △ | 2026-06-09 后已接入 ASR sidecar 代理和 Android 系统 TTS 播报；需最终设备/sidecar 验证 |

## 当前建议

1. 不再扩新功能，优先等并行 bug 修复线和 UI 线完成后做一次集成验收。
2. 集成验收必须包含真实 API，不用 mock 结果替代生成质量结论。
3. 提交材料里把主打亮点收成三件事：证据约束 RAG 与反幻觉、场景化 Planner / 多轮对比、原生移动端多模态与语音可访问体验。
4. 对未完成或需验证能力保持保守口径：购物车、下单、库存、实时优惠、图像向量搜同款和完整 claim-level judge 平台都作为后续方向；图片/语音/TTS 写成“已接入第一版，需最终验证”。
5. 三亚场景组合可以作为新增答辩例子：失败 trace -> Planner 结构化计划 -> retrieval 跨类目执行 -> failure regression 和真实 API probe 双验证。
