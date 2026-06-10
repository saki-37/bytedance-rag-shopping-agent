# ByteDance RAG Shopping Agent

字节跳动 AI 全栈挑战赛项目：基于 RAG 的多模态电商智能导购 AI Agent。

当前版本聚焦 **原生移动端 RAG 导购闭环 + 证据约束生成**：Android Kotlin 原生 App 支持文字、图片和语音需求输入，FastAPI 后端解析意图并检索商品，Doubao / Ark 生成 evidence-bound 导购回复，Android 端展示临时响应气泡、流式回答、商品卡片、图片、详情弹窗、反馈和 TTS 播报。

## 当前完成能力

- Android Kotlin + Jetpack Compose 原生聊天界面，不是 H5。
- FastAPI 后端，提供 `GET /health`、`POST /api/chat/stream`、`POST /api/debug/retrieve`、`POST /api/feedback`、`POST /api/multimodal/images`、`POST /api/asr/transcribe`、购买对象上下文接口和图片静态服务。
- SSE 流式协议：`status`、`quick_reply`、`products`、`token`、`done`、`error`；推荐场景下先用临时气泡接住需求，完整 Planner + 检索返回后再展示商品卡片和正式回答。
- 商品 RAG：结构化硬过滤 + 必要功效/子类过滤 + keyword/facet 匹配 + Chroma `products` 统一 collection 向量召回 + metadata filter + 可解释 `RetrievalTrace`。
- V2 多品类起步：新增 5 条服饰运动 enriched 样例，覆盖变体、规格、证据来源和第二品类 query benchmark。
- 场景化组合推荐第一版：Planner 可输出 `scene_bundle + search_slots`，retrieval 按结构化计划跨类目选品，并补充防晒霜 + 帽子/防晒衣 + 裤子回归 case。
- Doubao / Ark OpenAI-compatible API 接入；默认评测口径使用真实 Ark / Doubao，也支持通过 `LLM_PROVIDER=yunwu` 临时切到 Yunwu OpenAI-compatible API 做快速演示；只有显式开启 `MOCK_LLM=true` 或缺少当前 provider 的 Key/模型名时才走 mock / safe fallback。
- 生成后 guardrail：拦截编造价格、库存、优惠、下单承诺和无证据的绝对断言。
- 轻量反馈闭环：Android 端可在回答下方点击 `有用` / `不准确`；后端记录最近上下文、回答、商品卡片等有界快照，debug 脚本可额外带上检索 trace。
- Claim-level audit 样例：已沉淀 5 个高风险人工标注样例、8 条 claim，可渲染 Markdown / JSONL 报告，展示商品事实如何逐条回到数据源。
- 多模态图片输入第一版：Android 支持相机/相册图片上传，后端把图片理解为 `image_plan` / `query_text` 后接入现有 RAG；当前是 text-first 图片理解，不是图像向量搜同款。
- 语音输入与 TTS 第一版：Android 录音上传 `/api/asr/transcribe`，后端代理本地 ASR sidecar；助手回答可用 Android 系统 TTS 播报。最终视频是否主展示取决于设备和 sidecar 稳定性。
- 常用购买对象 / recipient context：Android 可选择和管理购买对象，后端把对象约束合入检索请求，作为个性化补充能力。
- 演示身份与本地多会话：App 顶部可切换 Demo 级本地身份（user_id，默认 `local-demo-user`，持久保存在本机），常用对象与记忆偏好按 user_id 隔离；支持新建/切换本地会话，每个会话有独立 `conversation_id` 和消息历史（内存态，重启不保留）。不是真实账号或登录体系。
- 商品卡片展示图片、品牌、商品名、价格、标签、推荐理由；点击卡片打开详情弹窗。
- Golden queries、conversation cases、真实 API 三轮回归和 Android 模拟器复验证据已整理在文档中。

## Demo 与提交入口

- Demo 脚本：[docs/12_demo_script.md](docs/12_demo_script.md)
- 提交版设计文档中间稿：[docs/submission_design_doc.md](docs/submission_design_doc.md)
- 提交版体验说明中间稿：[docs/submission_user_guide.md](docs/submission_user_guide.md)
- 提交版视频脚本：[docs/submission_video_script.md](docs/submission_video_script.md)
- 系统架构：[docs/10_architecture.md](docs/10_architecture.md)
- 评测记录：[docs/11_evaluation_report.md](docs/11_evaluation_report.md)
- 提交材料清单：[docs/14_submission_package.md](docs/14_submission_package.md)
- 依赖版本与复现说明：[docs/20_reproducibility_and_dependencies.md](docs/20_reproducibility_and_dependencies.md)
- LLM Provider 切换与演示模型候选：[docs/28_llm_provider_switching.md](docs/28_llm_provider_switching.md)
- 答辩口袋稿：[docs/22_defense_cheatsheet.md](docs/22_defense_cheatsheet.md)
- Claim-level audit 样例：[data/eval/claim_audit_samples.json](data/eval/claim_audit_samples.json)、[scripts/render_claim_audit_report.py](scripts/render_claim_audit_report.py)
- 文档总入口：[docs/00_index.md](docs/00_index.md)

本地原始录屏位于 `demo/录屏v1.mov`；当前已导出 60 秒手机屏版本 `demo/录屏v1_submission_phone_60s.mp4`，更适合作为平台附件上传。录屏文件属于生成媒体，已被 `.gitignore` 忽略，不进入 Git。

## Repository Layout

```text
client/android/   Android Kotlin + Jetpack Compose 客户端
server/           FastAPI 后端服务
data/raw/         官方原始数据集，不直接修改
data/enriched/    结构化增强数据
data/eval/        多轮评测样例
docs/             项目文档、技术决策、评测记录、提交材料
scripts/          数据检查、增强、索引构建、评测和安全扫描脚本
```

## Quick Start

完整依赖版本、环境说明和复现检查表见 [docs/20_reproducibility_and_dependencies.md](docs/20_reproducibility_and_dependencies.md)。下面保留最短启动路径。

### 1. Backend

```bash
cd bytedance-rag-shopping-agent
python3 -m venv server/.venv
source server/.venv/bin/activate
pip install -r server/requirements.txt
cp .env.example .env
```

本地 `.env` 只放真实配置，不提交到 Git。真实模型调用示例：

```env
ARK_API_KEY=YOUR_LOCAL_KEY
ARK_BASE_URL=https://ark.cn-beijing.volces.com/api/v3/
ARK_MODEL=YOUR_MODEL_ENDPOINT
LLM_PROVIDER=ark
FAST_FIRST_SCREEN_ENABLED=true
FAST_QUICK_REPLY_DEADLINE_SECONDS=0.8
MOCK_LLM=false
```

演示时如需临时使用科研项目里同类的 Yunwu OpenAI-compatible API，可在 `.env` 中切换 provider：

```env
LLM_PROVIDER=yunwu
YUNWU_API_KEY=YOUR_LOCAL_KEY
YUNWU_BASE_URL=https://yunwu.ai/v1
YUNWU_MODEL=gpt-5.4-mini
MOCK_LLM=false
```

切回正式测试口径时，把 `LLM_PROVIDER` 改回 `ark`；Planner 和最终导购回答会同时跟随这个开关。`FAST_QUICK_REPLY_DEADLINE_SECONDS` 只影响 `/api/chat/stream` 的临时气泡：如果完整 Planner + 检索还没返回，先发一个不含候选结论的等待气泡；Planner 和检索本身不会被截断或降级。启动后可用 `curl http://127.0.0.1:8000/health` 确认当前 `llm_provider` 和 `llm_model`。完整命令行临时覆盖方式和候选模型见 [docs/28_llm_provider_switching.md](docs/28_llm_provider_switching.md)。

可选移动端增强配置：

```env
MEMORY_PROVIDER=local
MEMORY_AUTO_LEARN=false
ASR_SIDECAR_URL=http://127.0.0.1:8765/transcribe
ASR_MAX_UPLOAD_MB=50
ASR_TIMEOUT_SECONDS=180
MULTIMODAL_MODEL=
MULTIMODAL_MAX_UPLOAD_MB=10
MULTIMODAL_RETENTION_HOURS=24
MULTIMODAL_TIMEOUT_SECONDS=20
```

`MULTIMODAL_MODEL` 留空时会尝试复用当前 provider 的模型配置；如果当前模型不支持图片，图片理解会降级或返回可理解错误。ASR 需要额外启动本地 sidecar；TTS 使用 Android 系统引擎，不需要后端模型。

如果只是离线验证端到端链路，可以显式改成：

```env
MOCK_LLM=true
```

启动前建议先检查数据并构建本地索引：

```bash
python scripts/check_data.py
python scripts/build_enriched_beauty.py
python scripts/build_index.py
```

`build_index.py` 会读取 `data/enriched/*_products.jsonl`，将所有 enriched 商品写入统一 Chroma `products` collection，并用 metadata 保存 `canonical_category`、`sub_category`、`base_price` 等过滤字段。

启动后端：

```bash
cd server
source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

如果真实 Ark / Doubao 调用需要代理：

```bash
export https_proxy=http://127.0.0.1:7897
export http_proxy=http://127.0.0.1:7897
export all_proxy=socks5://127.0.0.1:7897
```

### 2. Android

```bash
cd bytedance-rag-shopping-agent
./gradlew :client:android:app:assembleDebug
```

也可以用 Android Studio 打开仓库根目录，选择 `client/android/app` 对应的 app 运行。

注意：APK 只包含 Android 客户端，不包含 FastAPI 后端。评审或本地复现时需要先按上一步启动后端，再运行 App。

当前 Debug App 会优先尝试：

```text
http://127.0.0.1:8000
```

运行前推荐给当前模拟器建立 adb reverse，把模拟器的 `127.0.0.1:8000` 转发到电脑上的后端：

```bash
adb reverse tcp:8000 tcp:8000
```

如果设备列表里有多个设备，先查 serial：

```bash
adb devices
adb -s emulator-5554 reverse tcp:8000 tcp:8000
```

如果未设置 adb reverse，App 会继续尝试 Android 模拟器常用的宿主机地址 `http://10.0.2.2:8000`。商品图片地址会跟随实际连上的后端地址，因此回答和卡片图使用同一个本地服务。

如果使用真机而不是模拟器，`127.0.0.1` 指向手机本机，不是电脑。两种方式二选一：

方式 A（USB 调试）：执行 `adb reverse tcp:8000 tcp:8000`，手机的 `127.0.0.1:8000` 会转发到电脑。

方式 B（同一 Wi-Fi 局域网，无需 USB）：在仓库根目录 `local.properties`（不进 Git）加一行电脑的局域网 IP，然后重新构建：

```properties
backend.lan.url=http://192.168.x.x:8000
```

App 会把该地址排在候选首位，连不上时仍会回退 `127.0.0.1` / `10.0.2.2`。换网络后只需改这一行。注意三点：后端必须以 `--host 0.0.0.0` 启动；手机和电脑在同一网络且没有 AP 隔离；macOS 防火墙需放行 Python 的入站连接（系统设置 -> 网络 -> 防火墙）。地址配置集中在 `BackendConfig.kt`，无需改代码。

如果 Gradle 下载依赖需要走本地代理：

```bash
./gradlew :client:android:app:assembleDebug \
  -Dhttp.proxyHost=127.0.0.1 -Dhttp.proxyPort=7897 \
  -Dhttps.proxyHost=127.0.0.1 -Dhttps.proxyPort=7897
```

## Evaluation

评测口径约定：

- 默认开发/回归口径：`.env` 配置真实 `ARK_API_KEY`、`ARK_MODEL`，保持 `LLM_PROVIDER=ark`、`MOCK_LLM=false`。
- 快速演示口径：可临时设 `LLM_PROVIDER=yunwu` 并配置 `YUNWU_API_KEY`、`YUNWU_MODEL`；演示结束后切回 `ark` 再做正式回归。
- `run_golden_queries.py` 不加 `--check-stream` 时只验证检索层，不调用模型。
- `run_groundedness_cases.py` 默认会走项目正常 settings；只有显式传 `--mock-llm` 才是本地 mock generation。
- `--retrieval-only` 只证明检索和约束解析，不证明生成质量。

检索层 golden queries：

```bash
cd bytedance-rag-shopping-agent
server/.venv/bin/python scripts/run_golden_queries.py --require-vector
```

多轮对话样例：

```bash
server/.venv/bin/python scripts/run_conversation_cases.py
```

子类 query 样例：

```bash
server/.venv/bin/python scripts/run_subcategory_queries.py --require-vector
```

服饰运动第二品类样例：

```bash
server/.venv/bin/python scripts/run_subcategory_queries.py \
  --cases data/eval/apparel_queries.json \
  --require-vector \
  --output /private/tmp/bytedance-rag-apparel-v2b.jsonl
```

多商品对比样例：

```bash
server/.venv/bin/python scripts/run_comparison_queries.py --require-vector
```

生成层 guardrail：

```bash
server/.venv/bin/python scripts/check_generation_guardrails.py
```

轻量反馈闭环：

```bash
server/.venv/bin/python scripts/check_feedback_loop.py
```

真实 Doubao 快速 probe：

```bash
https_proxy=http://127.0.0.1:7897 http_proxy=http://127.0.0.1:7897 \
  server/.venv/bin/python scripts/probe_chat.py \
  --turn 我是油皮，想要200元以内通勤防晒 \
  --turn 我想买护肤品，你推荐什么？ \
  --turn 敏感肌，最近屏障不稳定，想找修护面霜，不要酒精味太重或者刺激感强的产品
```

## Security

真实 API Key 只允许放在本地 `.env`。提交前建议启用本地 hook：

```bash
git config core.hooksPath .githooks
chmod +x .githooks/pre-commit scripts/scan_secrets.py
```

手动扫描：

```bash
python3 scripts/scan_secrets.py --all
```

更多说明见 [docs/13_security_and_config.md](docs/13_security_and_config.md)。

## Current Scope

当前版本重点是 **原生 Android RAG 导购主线**，用于证明移动端、后端、RAG、模型生成、流式返回、商品卡片、详情页和评测闭环可以端到端运行。

当前边界：

- enriched 美妆数据已覆盖完整 25 条美妆商品；当前 Demo 仍聚焦美妆垂类。
- 服饰运动已有 5 条 V2-B 样例，并已进入统一 `products` 向量索引；Android 演示仍以美妆主线为主。
- 多商品对比已有第一版 benchmark 和后端回答策略；当前仍复用聊天回复和多商品卡片，不新增复杂对比 UI。
- `RetrievalTrace` 已显式输出 `metadata_filter`、`filter_summary` 和 `ranking_signals`，便于解释过滤和排序过程。
- Graph-aware relation score 已有第一版：运行时派生 category、sub_category、budget、facet、preference 关系，并以小权重参与 rerank。
- 图片输入、ASR 语音输入和 TTS 播报已接入第一版，可作为提交加分项；它们需要最终实机/provider/sidecar 验证后再决定是否放入主视频。
- 当前不做购物车、真实下单、支付、库存和实时优惠；图片输入不等于图像向量搜同款。
- “演示身份”是本地 user_id 切换（无密码、无服务端鉴权），会话列表是本机内存态；两者都是演示辅助能力，不是生产级用户体系。
- Evidence-aware fallback 已有第一版：兜底回答会引用商品资料、官方 FAQ、用户评价和“资料未说明/不能保证”边界。
- 轻量用户反馈闭环已有 Android 可见第一版：回答下方可点 `有用` / `不准确`，反馈 JSONL 写入 `data/tmp/feedback/`，该目录被 `.gitignore` 忽略。
- 更细的 claim-level groundedness 已有第一版人工标注样例和报告脚本；完整自动化 judge 平台仍是下一阶段增强项。
- Guardrail / fallback 是规则版，不是完整 groundedness judge。

## Recommended Reading Order

1. [docs/submission_user_guide.md](docs/submission_user_guide.md)：评委部署与体验说明，适合复制到飞书。
2. [docs/submission_design_doc.md](docs/submission_design_doc.md)：提交版系统设计文档，适合复制到飞书。
3. [docs/submission_video_script.md](docs/submission_video_script.md)：5-10 分钟演示视频脚本。
4. [docs/14_submission_package.md](docs/14_submission_package.md)：提交材料和评审入口。
5. [docs/22_defense_cheatsheet.md](docs/22_defense_cheatsheet.md)：答辩口袋稿和关键代码入口。
6. [docs/10_architecture.md](docs/10_architecture.md)：系统架构和端到端链路。
7. [docs/11_evaluation_report.md](docs/11_evaluation_report.md)：当前评测证据。
8. [docs/12_demo_script.md](docs/12_demo_script.md)：Demo 展示脚本。
9. [docs/20_reproducibility_and_dependencies.md](docs/20_reproducibility_and_dependencies.md)：依赖版本、复现说明和检查表。
10. [docs/08_rag_retrieval_strategy.md](docs/08_rag_retrieval_strategy.md)：RAG 策略调研与后续路线。
