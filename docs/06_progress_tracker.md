# 进度对照表

日期：2026-05-21  
更新：2026-05-28
用途：把当前实现状态对照课题最终要求，避免只围绕局部 UI 问题推进。

## 当前一句话状态

已经跑通第一版真实模型端到端链路：

> Android 快捷问题/文字输入 -> FastAPI `/api/chat/stream` -> 美妆商品检索 -> Doubao 流式回复 -> Android 展示回复、商品卡片、图片和详情弹窗。

2026-05-26 已补上 V1 检索层：`QueryIntent`、预算/排除条件硬约束、信息不足主动追问、`RetrievalTrace` 可解释输出，以及本地 debug 接口。同日已完成 Chroma 索引构建、8 条 golden query 检索层 benchmark 和生成层 guardrail。2026-05-28 完成真实 Doubao 三轮 probe、Android 端真实请求复验、商品详情弹窗复验，并新增演示快捷问题 chip 解决 adb/现场中文输入不稳定的问题；同日补上多轮消息列表自动滚动并完成连续两轮复验；本地录屏 `demo/录屏v1.mov` 已完成；`docs/10_architecture.md` 已补上系统架构说明；根目录 `README.md` 和 `docs/14_submission_package.md` 已整理成提交入口。当前仍不是最终参赛版本，最主要的缺口是：全量美妆 25 条数据尚未增强、Graph-aware / hybrid retrieval 还没有进入主链路、Demo 录屏还需要按平台要求裁剪或单独上传。

## 对照课题必做最小闭环

| 模块 | 课题要求 | 当前状态 | 说明 |
| --- | --- | --- | --- |
| 原生客户端 | iOS 或 Android 原生 App | 已完成第一版 | Android Kotlin + Jetpack Compose 已能启动和发送文字 |
| 文字输入 | 对话窗口，支持发送文字 | 已完成 | 输入框、发送按钮、用户消息展示已可用 |
| 流式回复 | 接收并渲染 AI 流式回复 | 已完成第一版 | SSE token 能逐步展示；已修正 loading 收尾问题 |
| 商品卡片 | 回复中包含商品卡片 | 已完成第一版 | 展示图片、品牌、商品名、价格、标签、推荐理由 |
| 卡片详情 | 可点击商品卡片，跳转落地页或模拟详情页 | 已完成第一版 | 点击商品卡片打开详情弹窗，详情字段来自数据源 |
| 后端服务 | Python / Go / Node / 任一后端 | 已完成第一版 | FastAPI 服务已跑通 |
| 流式 API | SSE 或 WebSocket | 已完成 | `POST /api/chat/stream` 返回 `status/products/token/done/error` |
| 向量数据库 | 集成向量数据库 | 已完成 V1 | Chroma 索引已可构建，运行时 trace 能看到 vector hits；索引产物仅本地保留 |
| RAG 基本链路 | 检索商品并基于资料回答 | 已完成 V1 | 结构化硬过滤 + 关键词/facet/Chroma 召回 + 可解释 trace；还不是最终 hybrid RAG 管线 |
| 模型调用 | 调用大模型生成导购回复 | 已完成第一版 | OpenAI-compatible Doubao 已通过代理复验；真实调用失败时会走安全兜底 |
| 反幻觉 | 不编造商品、价格、优惠、库存、功效 | 已完成 V1 | 商品卡片字段来自数据源；预算/排除条件在检索层硬过滤；生成层会拦截未授权价格和商业承诺 |

## 对照第一阶段计划

| 阶段项 | 原计划 | 当前状态 | 备注 |
| --- | --- | --- | --- |
| Repo Bootstrap | 独立 monorepo、README、文档、`.env.example`、数据复制 | 已完成 | GitHub 远程已由用户创建并推送 |
| Data MVP | 校验 100 条商品、100 张图片、5 条美妆增强样例 | 已完成第一版 | 已有 6 条美妆增强样例；全量美妆 25 条尚未增强 |
| Backend MVP | `/health`、`/api/chat/stream`、SSE 事件、检索、模型流式 | 已完成第一版 | mock、真实 Doubao 和安全兜底均可跑 |
| Android MVP | Kotlin Compose 聊天、输入、流式回复、商品卡片 | 已完成第一版 | 卡片详情、真实图片、演示快捷问题已做第一版 |
| Closed-loop Demo | 8 个 golden queries，至少 3 个端到端演示 | 已完成第一轮证据 | 后端真实 Doubao 三轮 probe 已保存；Android 端已复验油皮防晒、信息不足追问和商品详情 |

## 已经实际验证过的证据

- Android Studio / Gradle 同步成功，`assembleDebug` 可通过。
- 后端启动后有请求日志：
  - `POST /api/chat/stream HTTP/1.1" 200 OK`
- Android 端已展示：
  - 用户消息。
  - 真实 Doubao 回复。
  - 商品卡片、商品图片、价格和标签。
  - 商品详情弹窗。
- 当前 UI loading 卡住问题已定位为客户端 SSE 收尾问题，并已修正代码。
- 为演示和自动化复验新增 3 个快捷问题 chip：
  - 油皮通勤防晒。
  - 敏感肌修护。
  - 信息不足追问。
- 商品卡片点击详情已完成并在 Android 端复验。
- 商品图片静态接口已完成第一版，`/assets/...jpg` 可返回 `image/jpeg`。
- V1 检索层已完成本地烟测：
  - `200 元以内` 能解析成 `budget_max` 并过滤超预算商品。
  - `我想买护肤品` 这类信息不足 query 会先追问。
  - `不要酒精/刺激` 能进入排除条件，并写入 `RetrievalTrace`。
- Chroma 索引已构建：
  - 当前入库 6 条 enriched 美妆商品。
  - 运行时 vector 通道能返回 6 个 hits。
  - `scripts/run_golden_queries.py --require-vector` 检索层 8 条全部通过。
- 生成层 guardrail 已完成：
  - 模型输出先在后端聚合并校验，再重新流式输出给客户端。
  - 编造价格、库存、优惠、下单承诺会被兜底回答替换。
  - Ark / Doubao 连接失败时返回基于商品卡片的保守回答，避免 SSE 直接报错。
- 真实 Ark / Doubao 后端复验已完成：
  - GQ-01、GQ-02 成功返回真实模型文本并通过 guardrail。
  - GQ-03 暴露“无证据排除项断言”问题，已加入 guardrail 并复验触发兜底。
  - 2026-05-28 三轮 probe 验证了上下文继承、信息不足追问和敏感肌修护场景；敏感肌修护触发 `unsupported_absence_claims:酒精` 后二次改写成功。
- Android 端真实模型复验已完成第一轮：
  - `油皮通勤防晒`：显示真实回复、商品卡片和图片，loading 正常结束。
  - 商品卡片点击：详情弹窗展示价格、类目、适合、使用场景、卖点和注意事项。
  - `信息不足追问`：空会话下不推荐商品，主动追问肤质、预算或具体功效。
  - 多轮连续发送时发现列表不会自动滚到底部，已补自动滚动并完成连续两轮复验。

## 接下来优先级

### P0：提交前材料收口

1. 检查 README 和提交材料清单是否能独立说明项目。
2. 按平台要求处理 `demo/录屏v1.mov`：
   - 如需 1 分钟版本，裁剪到 60-90 秒。
   - 确认录屏中没有 API Key 或敏感终端信息。
   - 作为平台附件单独上传，不进入 Git。
3. 提交前运行：
   - `git diff --check`
   - `python3 scripts/scan_secrets.py --all`
4. 如需最终代码提交，确认只提交 README、docs 和必要代码，不提交 `.env`、索引产物或录屏文件。

### P1：扩展数据与复测

1. 扩展美妆增强数据：
   - 当前 6 条 -> 至少覆盖 25 条美妆。
   - 补全肤质、功效、成分/禁忌、使用场景、适合/不适合人群。
2. 重建 Chroma 索引并复跑：
   - `scripts/run_golden_queries.py --require-vector`
   - `scripts/run_conversation_cases.py`
   - `scripts/check_generation_guardrails.py`
3. 继续记录 Android 端真实输出是否被 guardrail 拦截、是否有 loading/超时/排版问题。
4. 增加多轮上下文：
   - 用户先说模糊需求。
   - Agent 主动追问。
   - 用户补充后再推荐。
5. 设计 Graph-aware / hybrid retrieval V2：
   - 保留通用字段：价格、品牌、类目、子类目。
   - 按品类扩展专属字段：肤质、成分、禁忌、材质、尺寸等。
   - 将硬约束、属性图召回、向量召回和重排 trace 放进同一评测框架。

### P2：主打能力和答辩亮点

1. 商品对比：
   - 2-3 个商品从价格、肤质、功效、注意事项对比。
2. 反馈闭环：
   - 用户标记推荐是否有用。
   - 记录失败 query。
   - 形成 prompt / 数据增强迭代记录。
3. 评测脚本：
   - 检索命中。
   - 是否错误推荐超预算商品。
   - 是否编造价格/库存/优惠。
   - 是否在信息不足时追问。
4. UI 打磨：
   - 商品图片真实加载。
   - 卡片排版、详情弹窗、加载状态、错误重试。
5. 可选多模态：
   - 图片输入 / 拍照找货作为 stretch goal，不抢主线。

## 当前最应该做的下一步

先做 **README / 提交材料整理**。

原因：

- Demo 录屏和架构文档已经有了，下一步要让评委拿到仓库后能快速跑起来和看懂重点。
- README 是提交入口，决定评委第一眼是否能理解项目完成度。
- 提交材料整理可以同时暴露还缺哪些证据。

完成标准：

- README 里有运行方式、环境变量、安全说明和 demo 入口。
- 文档索引能串起架构、评测、demo、RAG 策略。
- 明确列出当前完成能力和边界。
