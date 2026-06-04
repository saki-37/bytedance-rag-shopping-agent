# 依赖版本与复现说明

日期：2026-06-03

用途：集中说明本项目的本地运行环境、主要依赖版本、复现步骤和安全配置边界，方便评审、答辩和后续复盘时快速确认项目可以从代码重新跑起来。

## 复现结论

当前仓库可以用两种方式复现：

| 复现模式 | 需要真实 API Key | 目的 | 推荐场景 |
| --- | --- | --- | --- |
| Mock / safe fallback | 否 | 验证 Android、FastAPI、SSE、RAG 检索、商品卡片和评测脚本闭环 | 评委快速拉起、无 Key 环境、本地自测 |
| Ark / Doubao 真实模型 | 是 | 验证真实模型流式生成和 evidence-bound 导购回复 | Demo 前复验、答辩展示、模型效果抽样 |

默认 `.env.example` 使用 `MOCK_LLM=true`，因此没有真实 Key 时也不会阻塞端到端运行。真实 Key 只放本地 `.env`，不得提交。

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

如果只验证闭环，保持 `.env` 中：

```env
MOCK_LLM=true
```

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

预期：返回服务健康状态；Android 模拟器通过 `http://10.0.2.2:8000` 访问同一个后端。

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

网络说明：

| 场景 | 后端地址 |
| --- | --- |
| Android 模拟器访问本机后端 | `http://10.0.2.2:8000` |
| 宿主机浏览器 / curl 访问后端 | `http://127.0.0.1:8000` |

如果 Gradle 依赖下载需要代理：

```bash
./gradlew :client:android:app:assembleDebug \
  -Dhttp.proxyHost=127.0.0.1 -Dhttp.proxyPort=7897 \
  -Dhttps.proxyHost=127.0.0.1 -Dhttps.proxyPort=7897
```

## 评测复现

建议在每次改检索、prompt、guardrail 或多轮状态后至少跑下面几组：

```bash
server/.venv/bin/python scripts/run_golden_queries.py --require-vector
server/.venv/bin/python scripts/run_conversation_cases.py
server/.venv/bin/python scripts/run_subcategory_queries.py --require-vector
server/.venv/bin/python scripts/run_subcategory_queries.py \
  --cases data/eval/apparel_queries.json \
  --require-vector
server/.venv/bin/python scripts/run_comparison_queries.py --require-vector
server/.venv/bin/python scripts/check_generation_guardrails.py
```

反编造 / groundedness 评测：

```bash
PYTHONDONTWRITEBYTECODE=1 server/.venv/bin/python scripts/run_groundedness_cases.py \
  --mock-llm

PYTHONDONTWRITEBYTECODE=1 server/.venv/bin/python scripts/run_groundedness_cases.py \
  --mock-llm \
  --retrieval-only
```

当前最新一轮 groundedness full mock generation 和 retrieval-only 结果均为 11/11 PASS；完整记录见 `docs/11_evaluation_report.md`。

轻量反馈闭环 smoke test：

```bash
server/.venv/bin/python scripts/check_feedback_loop.py
```

该脚本会通过 `/api/debug/retrieve` 构造一条带商品卡片和 `RetrievalTrace` 的反馈记录，再调用 `/api/feedback` 写入本地 JSONL。记录路径位于 `data/tmp/feedback/`，不会进入 Git。

## 常见失败与处理

| 现象 | 可能原因 | 处理 |
| --- | --- | --- |
| Android 能启动但没有回复 | 后端未启动，或模拟器不能访问宿主机 | 确认 Uvicorn 在 `0.0.0.0:8000`，Android 使用 `10.0.2.2:8000` |
| Gradle 依赖下载慢或失败 | Maven / Google 仓库网络不稳定 | 使用代理参数，或在 Android Studio 中重新 Sync |
| 真实 Doubao 请求超时 | 网络代理或 Key/模型名配置异常 | 先切回 `MOCK_LLM=true` 验证链路，再检查 `.env` 和代理 |
| Chroma 检索无结果 | 索引未构建或 enriched 数据未生成 | 重新运行 `python scripts/build_index.py` |
| 反馈脚本写入失败 | `data/tmp/feedback/` 无写入权限或当前沙盒不允许写仓库临时目录 | 在真实本地终端运行，或确认仓库目录可写 |
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
| 核心评测 | golden / conversation / groundedness 脚本 | 结果与 `docs/11_evaluation_report.md` 当前记录一致或有解释 |
