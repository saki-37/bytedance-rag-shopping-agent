# ByteDance RAG Shopping Agent

字节跳动 AI 全栈挑战赛项目：基于 RAG 的多模态电商智能导购 AI Agent。

当前版本聚焦 **美妆护肤文字导购闭环**：Android Kotlin 原生 App 输入需求，FastAPI 后端解析意图并检索商品，Doubao / Ark 生成 evidence-bound 导购回复，Android 端流式展示回答、商品卡片、图片和详情弹窗。

## 当前完成能力

- Android Kotlin + Jetpack Compose 原生聊天界面。
- FastAPI 后端，提供 `GET /health`、`POST /api/chat/stream`、`POST /api/debug/retrieve`、`POST /api/feedback` 和图片静态服务。
- SSE 流式协议：`status`、`products`、`token`、`done`、`error`。
- 商品 RAG：结构化硬过滤 + 必要功效/子类过滤 + keyword/facet 匹配 + Chroma `products` 统一 collection 向量召回 + metadata filter + 可解释 `RetrievalTrace`。
- V2 多品类起步：新增 5 条服饰运动 enriched 样例，覆盖变体、规格、证据来源和第二品类 query benchmark。
- Doubao / Ark OpenAI-compatible API 接入；默认评测口径使用真实 API，只有显式开启 `MOCK_LLM=true` 或缺少 Key/模型名时才走 mock / safe fallback。
- 生成后 guardrail：拦截编造价格、库存、优惠、下单承诺和无证据的绝对断言。
- 轻量反馈闭环：Android 端可在回答下方点击 `有用` / `不准确`；后端记录最近上下文、回答、商品卡片等有界快照，debug 脚本可额外带上检索 trace。
- 商品卡片展示图片、品牌、商品名、价格、标签、推荐理由；点击卡片打开详情弹窗。
- Golden queries、conversation cases、真实 API 三轮回归和 Android 模拟器复验证据已整理在文档中。

## Demo 与提交入口

- Demo 脚本：[docs/12_demo_script.md](docs/12_demo_script.md)
- 系统架构：[docs/10_architecture.md](docs/10_architecture.md)
- 评测记录：[docs/11_evaluation_report.md](docs/11_evaluation_report.md)
- 提交材料清单：[docs/14_submission_package.md](docs/14_submission_package.md)
- 依赖版本与复现说明：[docs/20_reproducibility_and_dependencies.md](docs/20_reproducibility_and_dependencies.md)
- 答辩口袋稿：[docs/22_defense_cheatsheet.md](docs/22_defense_cheatsheet.md)
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
MOCK_LLM=false
```

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
```

### 2. Android

```bash
cd bytedance-rag-shopping-agent
./gradlew :client:android:app:assembleDebug
```

也可以用 Android Studio 打开仓库根目录，选择 `client/android/app` 对应的 app 运行。默认后端地址是 Android 模拟器访问宿主机的：

```text
http://10.0.2.2:8000
```

如果 Gradle 下载依赖需要走本地代理：

```bash
./gradlew :client:android:app:assembleDebug \
  -Dhttp.proxyHost=127.0.0.1 -Dhttp.proxyPort=7897 \
  -Dhttps.proxyHost=127.0.0.1 -Dhttps.proxyPort=7897
```

## Evaluation

评测口径约定：

- 默认开发/回归口径：`.env` 配置真实 `ARK_API_KEY`、`ARK_MODEL`，并保持 `MOCK_LLM=false`。
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

当前版本重点是 **文字美妆导购主线**，用于证明移动端、后端、RAG、模型生成、商品卡片和评测闭环可以端到端运行。

当前边界：

- enriched 美妆数据已覆盖完整 25 条美妆商品；当前 Demo 仍聚焦美妆垂类。
- 服饰运动已有 5 条 V2-B 样例，并已进入统一 `products` 向量索引；Android 演示仍以美妆主线为主。
- 多商品对比已有第一版 benchmark 和后端回答策略；当前仍复用聊天回复和多商品卡片，不新增复杂对比 UI。
- `RetrievalTrace` 已显式输出 `metadata_filter`、`filter_summary` 和 `ranking_signals`，便于解释过滤和排序过程。
- Graph-aware relation score 已有第一版：运行时派生 category、sub_category、budget、facet、preference 关系，并以小权重参与 rerank。
- 图片输入、语音、购物车、下单不在当前版本。
- Evidence-aware fallback 已有第一版：兜底回答会引用商品资料、官方 FAQ、用户评价和“资料未说明/不能保证”边界。
- 轻量用户反馈闭环已有 Android 可见第一版：回答下方可点 `有用` / `不准确`，反馈 JSONL 写入 `data/tmp/feedback/`，该目录被 `.gitignore` 忽略。
- 更细的 claim-level groundedness judge 是下一阶段增强项。
- Guardrail / fallback 是规则版，不是完整 groundedness judge。

## Recommended Reading Order

1. [docs/14_submission_package.md](docs/14_submission_package.md)：提交材料和评审入口。
2. [docs/22_defense_cheatsheet.md](docs/22_defense_cheatsheet.md)：答辩口袋稿和关键代码入口。
3. [docs/10_architecture.md](docs/10_architecture.md)：系统架构和端到端链路。
4. [docs/11_evaluation_report.md](docs/11_evaluation_report.md)：当前评测证据。
5. [docs/12_demo_script.md](docs/12_demo_script.md)：Demo 展示脚本。
6. [docs/20_reproducibility_and_dependencies.md](docs/20_reproducibility_and_dependencies.md)：依赖版本、复现说明和检查表。
7. [docs/08_rag_retrieval_strategy.md](docs/08_rag_retrieval_strategy.md)：RAG 策略调研与后续路线。
