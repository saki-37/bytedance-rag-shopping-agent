# 依赖版本与复现说明

日期：2026-06-03

用途：集中说明本项目的本地运行环境、主要依赖版本、复现步骤和安全配置边界，方便评审、答辩和后续复盘时快速确认项目可以从代码重新跑起来。

## 复现结论

当前仓库可以用两种方式复现。**开发和评测默认口径是 Ark / Doubao 真实模型**；Mock / safe fallback 只用于无 Key 环境、离线结构检查或明确的降级演示。

| 复现模式 | 需要真实 API Key | 目的 | 推荐场景 |
| --- | --- | --- | --- |
| Ark / Doubao 真实模型 | 是 | 验证真实模型流式生成和 evidence-bound 导购回复 | 默认开发回归、Demo 前复验、答辩展示、模型效果分析 |
| Mock / safe fallback | 否 | 验证 Android、FastAPI、SSE、RAG 检索、商品卡片和评测脚本闭环 | 无 Key 环境、离线自测、网络故障时的结构检查 |

默认 `.env.example` 使用 `MOCK_LLM=false`。如果没有真实 Key 或模型名，后端会自动使用 safe fallback，保证端到端链路不阻塞；如果要强制离线 mock，请在本地 `.env` 显式改成 `MOCK_LLM=true`。真实 Key 只放本地 `.env`，不得提交。

## 测试口径约定

后续记录评测结果时，必须写清楚属于哪一种：

| 类型 | 是否调用真实模型 | 证明什么 | 典型命令 |
| --- | --- | --- | --- |
| Retrieval-only | 否 | query parse、hard filter、metadata filter、rerank、商品卡片是否正确 | `run_golden_queries.py --require-vector` 或 `run_groundedness_cases.py --retrieval-only` |
| Mock / offline generation | 否 | SSE 形态、safe fallback、guardrail、Android 展示是否稳定 | `run_groundedness_cases.py --mock-llm` |
| Real API generation | 是 | 真实 Doubao 输出、repair / fallback、反幻觉稳定性 | `MOCK_LLM=false ... run_groundedness_cases.py` 或 `run_golden_queries.py --check-stream` |

默认评测不再假设 mock。除非命令里显式出现 `--mock-llm`、`MOCK_LLM=true` 或 `--retrieval-only`，否则应按真实 API 口径理解；如果 `.env` 缺 Key 导致 safe fallback，报告里必须单独说明这不是一次有效的真实 API 生成评测。

### 正式 Benchmark 执行顺序

正式 benchmark 的默认顺序必须是：

```text
真实 API + 真实代理
-> 记录真实结果和失败 case
-> 再用 mock / retrieval-only 做拆因
-> 修复后回到真实 API 复验
```

也就是说：

- **效果结论只以真实 API benchmark 为准**，尤其是 groundedness、Planner、生成质量和 Android 端体验。
- Mock / safe fallback 只用于离线结构检查、网络不可用时的 smoke test、或真实 API 失败后的问题拆解。
- 如果只跑了 mock / retrieval-only，报告里必须写“这不是正式 benchmark，只证明本地结构链路”。
- Codex 或本地脚本需要真实 API / 代理 / Gradle 下载时，应优先使用非沙盒网络或本机终端，不先在网络受限环境里空等。
- 真实 API benchmark 若因网络、Key 或代理失败，不应直接用 mock 结果替代；应先修配置，再重跑真实 API。

## 本机验证环境

以下是当前开发机已验证过的环境，不代表只能使用这些小版本，但建议提交/答辩时优先保持一致。

| 层级 | 项 | 当前验证版本 / 配置 | 来源 |
| --- | --- | --- | --- |
| OS | macOS | Mac OS X 26.5 aarch64 | `./gradlew --version` |
| Python | Python | 3.13.2 | `python3 --version`、`server/.venv/bin/python --version` |
| Java | JDK | OpenJDK 17.0.16 | `java -version` |
| Gradle | Gradle Wrapper | 8.12 | `gradle/wrapper/gradle-wrapper.properties` |
| Android | Android Gradle Plugin | 8.7.3 | 根目录 `build.gradle.kts` |
| Android | Kotlin / Compose compiler plugin | 2.0.21 | 根目录 `build.gradle.kts` |
| Android | compileSdk / targetSdk / minSdk | 35 / 35 / 26 | `client/android/app/build.gradle.kts` |
| Android | App version | `0.1.0` | `client/android/app/build.gradle.kts` |
| Android 网络 | 本地后端访问 | 优先 `127.0.0.1:8000` + `adb reverse`，自动回退 `10.0.2.2:8000` | `BackendConfig.kt` |
| Backend | Web framework | FastAPI 0.115.6 | `server/requirements.txt` |
| Backend | ASGI server | Uvicorn 0.34.0 | `server/requirements.txt` |
| RAG | Vector DB | ChromaDB 0.6.3 | `server/requirements.txt` |
| RAG | Embedding package | sentence-transformers 3.3.1 | `server/requirements.txt` |
| LLM client | OpenAI-compatible SDK | openai 1.59.7 | `server/requirements.txt` |
| Config | Env loader | pydantic-settings 2.7.1、python-dotenv 1.0.1 | `server/requirements.txt` |

## Android 主要依赖

| 依赖 | 版本 | 用途 |
| --- | --- | --- |
| `androidx.compose:compose-bom` | 2024.12.01 | Compose 组件版本对齐 |
| `androidx.activity:activity-compose` | 1.9.3 | Compose Activity 入口 |
| `androidx.lifecycle:lifecycle-runtime-ktx` | 2.8.7 | 生命周期与协程集成 |
| `androidx.lifecycle:lifecycle-viewmodel-compose` | 2.8.7 | Compose ViewModel |
| `io.coil-kt:coil-compose` | 2.7.0 | 商品图片加载 |
| `com.squareup.okhttp3:okhttp` | 4.12.0 | 后端 SSE / HTTP 请求 |
| `org.jetbrains.kotlinx:kotlinx-coroutines-android` | 1.9.0 | Android 协程 |

## 目录与生成物

| 路径 | 是否提交 | 说明 |
| --- | --- | --- |
| `server/requirements.txt` | 是 | Python 依赖锁定来源 |
| `gradle/wrapper/gradle-wrapper.properties` | 是 | Gradle 版本来源 |
| `.env.example` | 是 | 环境变量模板，不含真实 Key |
| `.env` | 否 | 本地真实 Key、模型名和 mock 开关 |
| `data/raw/` | 是 | 官方原始商品数据 |
| `data/enriched/` | 是 | 项目增强后的结构化商品数据 |
| `data/indexes/` | 否 | Chroma 本地索引，可由脚本重建 |
| `data/tmp/feedback/` | 否 | 本地反馈 JSONL，记录有界证据快照，不进入 Git |
| `server/.venv/` | 否 | 本地 Python 虚拟环境 |
| `demo/*.mov`、`demo/*.mp4` | 否 | 录屏作为平台附件上传，不进入代码仓库 |

## 后端最短复现

从仓库根目录执行：

```bash
python3 -m venv server/.venv
source server/.venv/bin/activate
pip install -r server/requirements.txt
cp .env.example .env
```

默认真实 API 口径下，本地 `.env` 应保持：

```env
ARK_API_KEY=YOUR_LOCAL_KEY
ARK_BASE_URL=https://ark.cn-beijing.volces.com/api/v3/
ARK_MODEL=YOUR_MODEL_ENDPOINT
MOCK_LLM=false
```

如果只做离线结构检查，再显式改成 `MOCK_LLM=true`。

检查数据、生成增强数据并构建索引：

```bash
python scripts/check_data.py
python scripts/build_enriched_beauty.py
python scripts/build_index.py
```

启动后端：

```bash
cd server
source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

健康检查：

```bash
curl http://127.0.0.1:8000/health
```

预期：返回服务健康状态。

## 真实 Ark / Doubao 复现

本地 `.env` 填入：

```env
ARK_API_KEY=YOUR_LOCAL_KEY
ARK_BASE_URL=https://ark.cn-beijing.volces.com/api/v3/
ARK_MODEL=YOUR_MODEL_ENDPOINT
MOCK_LLM=false
```

如果本地网络需要代理：

```bash
export https_proxy=http://127.0.0.1:7897
export http_proxy=http://127.0.0.1:7897
export all_proxy=socks5://127.0.0.1:7897
```

快速 probe，不需要启动 Android：

```bash
server/.venv/bin/python scripts/probe_chat.py \
  --turn 我是油皮，想要200元以内通勤防晒 \
  --turn 敏感肌，最近屏障不稳定，想找修护面霜，不要酒精味太重或者刺激感强的产品
```

说明：如果真实模型暂时连接失败，后端仍会返回基于召回商品的 safe fallback，不会让 Android 端卡死。

## Android 最短复现

确保后端已经在宿主机 `8000` 端口运行，然后从仓库根目录执行：

```bash
./gradlew :client:android:app:assembleDebug
```

或使用 Android Studio 打开仓库根目录，选择 `client/android/app` 运行。

### Android 本地联网说明

APK 只包含 Android 客户端，不包含 FastAPI 后端。评审或本地复现时，应先启动后端，再运行 Android App。

当前 Debug App 的后端候选地址为：

1. `http://127.0.0.1:8000`
2. `http://10.0.2.2:8000`

App 会优先使用 `127.0.0.1:8000`；如果连接失败，会继续尝试 `10.0.2.2:8000`。商品图片 `/assets/...` 会跟随实际连上的后端地址，避免“文本成功但图片仍指向旧地址”的问题。

推荐复现路径：

```bash
adb devices
adb reverse tcp:8000 tcp:8000
```

如果设备列表里有多个设备：

```bash
adb -s emulator-5554 reverse tcp:8000 tcp:8000
```

网络场景说明：

| 场景 | 后端地址 |
| --- | --- |
| Android 模拟器 + adb reverse | App 访问 `http://127.0.0.1:8000`，由 adb 转发到宿主机后端 |
| Android 模拟器 + 无 adb reverse | App 回退尝试 `http://10.0.2.2:8000`；如果模拟器网络路由异常，仍建议使用 adb reverse |
| Android 真机 + USB 调试 | 可用 `adb reverse tcp:8000 tcp:8000`，让真机访问电脑本地后端 |
| Android 真机 + 无 USB 调试 | 需要把后端放到手机可访问的局域网或公网地址；当前 Debug APK 不内置后端 |
| 宿主机浏览器 / curl 访问后端 | `http://127.0.0.1:8000` |

Android Manifest 已配置 `INTERNET` 权限和 `usesCleartextTraffic=true`，用于允许 Debug App 访问本地 HTTP 后端。

如果 Gradle 依赖下载需要代理：

```bash
./gradlew :client:android:app:assembleDebug \
  -Dhttp.proxyHost=127.0.0.1 -Dhttp.proxyPort=7897 \
  -Dhttps.proxyHost=127.0.0.1 -Dhttps.proxyPort=7897
```

## 评测复现

建议在每次改检索、prompt、guardrail 或多轮状态后至少跑下面几组。注意：下面前几组主要验证检索和规则层，默认不代表真实生成质量。

```bash
server/.venv/bin/python scripts/run_golden_queries.py --require-vector
server/.venv/bin/python scripts/run_conversation_cases.py
server/.venv/bin/python scripts/run_failure_regression_cases.py
server/.venv/bin/python scripts/run_subcategory_queries.py --require-vector
server/.venv/bin/python scripts/run_subcategory_queries.py \
  --cases data/eval/apparel_queries.json \
  --require-vector
server/.venv/bin/python scripts/run_comparison_queries.py --require-vector
server/.venv/bin/python scripts/check_generation_guardrails.py
```

反编造 / groundedness 评测分两种。正式评测先跑真实 API：

真实 API 口径，也就是后续默认用于判断生成质量的命令：

```bash
MOCK_LLM=false PYTHONDONTWRITEBYTECODE=1 \
  server/.venv/bin/python scripts/run_groundedness_cases.py
```

真实 API 跑完后，若需要拆因或离线回归，再跑结构口径。它必须显式标注为 mock 或 retrieval-only：

```bash
PYTHONDONTWRITEBYTECODE=1 server/.venv/bin/python scripts/run_groundedness_cases.py \
  --mock-llm

PYTHONDONTWRITEBYTECODE=1 server/.venv/bin/python scripts/run_groundedness_cases.py \
  --mock-llm \
  --retrieval-only
```

当前最新一轮 groundedness full mock generation 和 retrieval-only 结果均为 11/11 PASS；真实 API 三轮全量复验为 golden stream 8/8 stable PASS、groundedness real generation 3/11 stable PASS。完整记录见 `docs/11_evaluation_report.md`。

Groundedness runner 现在会输出 `judge_checks`：

- `answer_claims`：同义 claim / 近义表达是否命中。
- `forbidden_answer_claims`：禁止 claim 是否出现在回答中。
- `source_checks`：强效果描述是否需要回连来源。
- `legacy_answer_checks`：旧的硬字符串检查结果，保留作为对照。

第一批已配置 `GRD-01`、`GRD-02`、`GRD-04`、`GRD-L01`，用于减少“语义上合格但关键词没命中”的 false fail。

Benchmark 结束后的 AI 语义复核：

```bash
server/.venv/bin/python scripts/review_benchmark_with_ai.py \
  --input data/tmp/evals/groundedness_cases_latest.jsonl \
  --suite-name groundedness
```

该脚本读取任意 benchmark JSONL，并输出同目录的 `*_ai_review.jsonl`。每条记录会补充 `semantic_score`、`semantic_pass`、`likely_false_fail`、`likely_false_pass`、`needs_human_review` 和问题清单。没有真实 API key、只想检查脚本结构时可用：

```bash
server/.venv/bin/python scripts/review_benchmark_with_ai.py \
  --input data/tmp/evals/groundedness_cases_latest.jsonl \
  --suite-name groundedness \
  --mock-review
```

Planner 修改后的 targeted 性能检查：

```bash
export https_proxy=http://127.0.0.1:7897
export http_proxy=http://127.0.0.1:7897
export all_proxy=socks5://127.0.0.1:7897

server/.venv/bin/python scripts/probe_planner.py --repeat 3
```

该脚本默认要求真实 API 配置，会输出 `planner_trace`、`validated_plan`、`fallback_reason` 和 `latency_ms`；如果只想列出 case，可运行：

当前默认 `PLANNER_TIMEOUT_SECONDS=20`。这是为了先验证 Planner 的真实稳定性上限；最近一轮 15 次真实 Planner probe 在该配置下无 timeout，按修正后的判定为 15/15 PASS，median latency 约 11.3 秒，p95 约 16.0 秒。如果 Android 端体验明显变慢，后续再评估 Router-gated Planner 或更快的 API。

```bash
server/.venv/bin/python scripts/probe_planner.py --list-cases
```

轻量反馈闭环 smoke test：

```bash
server/.venv/bin/python scripts/check_feedback_loop.py
```

该脚本会通过 `/api/debug/retrieve` 构造一条带商品卡片和 `RetrievalTrace` 的反馈记录，再调用 `/api/feedback` 写入本地 JSONL。记录路径位于 `data/tmp/feedback/`，不会进入 Git。

## 常见失败与处理

| 现象 | 可能原因 | 处理 |
| --- | --- | --- |
| Android 能启动但没有回复 | 后端未启动，或模拟器不能访问宿主机 | 确认 Uvicorn 在 `0.0.0.0:8000`，并运行 `adb reverse tcp:8000 tcp:8000`；当前 App 也会回退尝试 `10.0.2.2:8000` |
| Android 显示 `Failed to connect` / `ENETUNREACH` | 模拟器到宿主机的 `10.0.2.2` 路由不可达 | 使用 `adb reverse tcp:8000 tcp:8000`，然后重启 App；这是本地环境桥接问题，不是 RAG 逻辑失败 |
| Android 显示 `unexpected end of stream` | 本地 HTTP 连接被后端/模拟器提前关闭，或旧连接复用异常 | 当前客户端已关闭连接池复用并设置 `Connection: close`；若复现，先重启后端并重新运行 `adb reverse` |
| Android Studio 提示 `Couldn't terminate previous instance of app` | Studio/adb 没能停止旧进程 | 手动执行 `adb shell am force-stop com.saki.bytedance.ragshopping`；仍失败时重启 adb 或模拟器 |
| Gradle 依赖下载慢或失败 | Maven / Google 仓库网络不稳定 | 使用代理参数，或在 Android Studio 中重新 Sync |
| 真实 Doubao 请求超时 | 网络代理、Key/模型名配置异常，或 Planner / 生成模型本身延迟偏高 | 先确认 `.env`、代理和非沙盒网络；必要时用 targeted real API case 定位。Mock / retrieval-only 只能做拆因，不能替代正式 benchmark |
| Chroma 检索无结果 | 索引未构建或 enriched 数据未生成 | 重新运行 `python scripts/build_index.py` |
| 反馈脚本写入失败 | `data/tmp/feedback/` 无写入权限或当前沙盒不允许写仓库临时目录 | 在真实本地终端运行，或确认仓库目录可写 |
| AI 语义复核无法运行 | `.env` 缺少 `ARK_API_KEY` 或 `ARK_MODEL` | 先用 `--mock-review` 做离线烟测；真实复核前确认 `.env` 已配置 |
| 提交前 secret scan 失败 | `.env`、文档或录屏说明中出现疑似 Key | 删除真实 Key，重新运行 `python3 scripts/scan_secrets.py --all` |

## 提交前复现检查表

| 检查项 | 命令 / 动作 | 通过标准 |
| --- | --- | --- |
| Git 状态 | `git status --short` | 只包含本次预期改动 |
| Secret 扫描 | `python3 scripts/scan_secrets.py --all` | `Secret scan passed` |
| 数据检查 | `python scripts/check_data.py` | raw 数据、图片和字段校验通过 |
| 索引构建 | `python scripts/build_index.py` | Chroma `products` collection 重建成功 |
| 后端健康 | `curl http://127.0.0.1:8000/health` | 返回健康状态 |
| Android 构建 | `./gradlew :client:android:app:assembleDebug` | `BUILD SUCCESSFUL` |
| 核心评测 | golden / conversation / groundedness 脚本 | 优先真实 API 结果；若有 mock / retrieval-only，必须标注为辅助拆因结果 |
| AI 复核 | `python scripts/review_benchmark_with_ai.py --input <benchmark.jsonl>` | 输出 `*_ai_review.jsonl`，高风险项有解释 |
