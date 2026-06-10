# RAG 智能导购 Agent 部署与体验说明

建议飞书标题：RAG 智能导购 Agent 部署与体验说明

本文面向评委快速体验和本地复现。命令默认从仓库根目录执行：

```bash
cd /path/to/bytedance-rag-shopping-agent
```

请不要把真实 `.env`、API Key、终端代理、个人录屏或用户上传图片提交到 Git，也不要在演示视频中展示真实 Key。

## 1. 项目简介

本项目是一个原生 Android + FastAPI 的 RAG 智能导购 Agent。用户可以在 Android App 中输入文字需求，也可以使用已接入的图片输入、ASR 语音输入和 TTS 播报能力。后端会把需求转成结构化约束，从本地商品库中检索商品，再调用 OpenAI-compatible LLM 生成受商品证据约束的导购回复，并通过 SSE 流式返回到 App。

一句话体验目标：

> 评委可以看到“客户端对话 -> 后端 RAG 检索 -> 模型生成 -> 流式返回 -> 商品卡片 -> 商品详情页”的完整链路，并能理解项目如何规避商品、价格、优惠和功效幻觉。

当前边界：

- 不做真实购物车、下单、支付、库存和实时优惠。
- 图片输入是 text-first 图片理解线索，不是图像向量搜同款。
- ASR 依赖本地 sidecar；TTS 依赖 Android 设备中文语音引擎。
- mock/fallback 只证明结构链路，不代表真实生成效果。

## 2. 评委最快体验路径

如果已经安装 Python、Android Studio 和 adb，最快体验顺序如下。

### 2.1 启动后端

```bash
python3 -m venv server/.venv
source server/.venv/bin/activate
pip install -r server/requirements.txt
cp .env.example .env
```

编辑本地 `.env`，填入真实 Ark / Doubao 配置：

```env
LLM_PROVIDER=ark
ARK_API_KEY=YOUR_LOCAL_KEY
ARK_MODEL=YOUR_MODEL_ENDPOINT
MOCK_LLM=false
```

构建商品索引：

```bash
python scripts/check_data.py
python scripts/build_enriched_beauty.py
python scripts/build_index.py
```

启动服务：

```bash
cd server
source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

另开一个终端检查 health：

```bash
curl http://127.0.0.1:8000/health
```

期望看到：

- `status` 为 `ok`
- `mock_llm` 为 `false`
- `llm_provider` 为 `ark`
- `llm_model` 为本地配置的模型或 endpoint

### 2.2 运行 Android App

在仓库根目录执行：

```bash
adb devices
adb reverse tcp:8000 tcp:8000
./gradlew :client:android:app:assembleDebug
```

也可以用 Android Studio 打开仓库根目录，选择 `client/android/app` 对应的 app 运行。

说明：

- Debug App 优先访问 `http://127.0.0.1:8000`。
- 模拟器或 USB 真机建议执行 `adb reverse tcp:8000 tcp:8000`。
- 如果不设置 reverse，模拟器可能回退到 `http://10.0.2.2:8000`。
- 真机不插 USB 时，可走同一 Wi-Fi 局域网：在仓库根目录 `local.properties` 加 `backend.lan.url=http://<电脑局域网IP>:8000` 后重新构建；App 会优先连该地址，失败再回退。要求后端以 `--host 0.0.0.0` 启动、手机与电脑同网、macOS 防火墙放行。

### 2.3 最短 Demo 操作

1. 打开 App，确认首页显示聊天界面和快捷问题。
2. 输入或点击：`我是油皮，想要200元以内通勤防晒`
3. 观察临时气泡、流式回答和商品卡片。
4. 点击任意商品卡片，打开详情页。
5. 点击左上角侧边栏图标，新建一个会话，再输入：`我想买护肤品，你推荐什么？`
6. 观察系统主动追问，而不是强行推荐商品；可在会话列表中切回上一会话验证历史不串。

### 2.4 演示身份与会话切换（可选展示）

- 顶部"演示身份"入口可切换本地 user_id（默认 `local-demo-user`）。这是 Demo 级本地身份，仅保存在本机 SharedPreferences，没有密码或服务端鉴权，不是真实账号系统。
- 切换身份后会重新加载该 user_id 的常用对象（购买对象），并自动开启新会话；常用对象和记忆偏好按 user_id 在后端 `data/tmp/user_memory/` 隔离。
- 左上角侧边栏图标会从左侧滑出会话抽屉（浮层，不改变主界面布局），支持新建会话、查看会话列表（标题取首条提问 + 时间标记）和切换会话；每个会话有独立 `conversation_id` 和消息历史，互不串扰。
- 会话列表为本机内存态：重启 App 后历史会话不保留；身份选择会持久保留。流式回复进行中暂不能切换会话或身份。

如果这条链路通过，就已经覆盖基础功能完整性中的核心链路：Android App、后端 RAG、模型生成、流式返回、商品卡片和详情页。

## 3. 环境变量配置

`.env.example` 是模板；真实值只填本地 `.env`，不要提交。

### 3.1 正式评测口径：Ark / Doubao

```env
LLM_PROVIDER=ark
ARK_API_KEY=YOUR_LOCAL_KEY
ARK_BASE_URL=https://ark.cn-beijing.volces.com/api/v3/
ARK_MODEL=YOUR_MODEL_ENDPOINT
MOCK_LLM=false
```

这是正式评测和最终口径。所有“真实效果”结论都应以 `MOCK_LLM=false` 且 provider 配置正确为准。

### 3.2 演示备用：Yunwu OpenAI-compatible

如果现场等待时间太长，可临时使用 Yunwu 演示备用：

```env
LLM_PROVIDER=yunwu
YUNWU_API_KEY=YOUR_LOCAL_KEY
YUNWU_BASE_URL=https://yunwu.ai/v1
YUNWU_MODEL=gpt-5.4-mini
MOCK_LLM=false
```

注意：Yunwu 只作为演示备用。正式评测口径仍建议切回 Ark / Doubao，并重新检查 `/health`。

### 3.3 离线结构验证：Mock

```env
MOCK_LLM=true
```

mock 只用于无 Key 时验证端到端结构和 UI，不代表真实模型效果。提交材料中不要把 mock 结果写成真实生成质量。

### 3.4 首屏响应

```env
FAST_FIRST_SCREEN_ENABLED=true
FAST_QUICK_REPLY_DEADLINE_SECONDS=0.8
PLANNER_TIMEOUT_SECONDS=20
```

`FAST_QUICK_REPLY_DEADLINE_SECONDS` 只控制首屏临时气泡。它不会截断 Planner、检索或生成主链路。

### 3.5 用户记忆与购买对象

```env
MEMORY_PROVIDER=local
MEMORY_AUTO_LEARN=false
```

当前推荐使用本地 memory provider。它用于购买对象上下文和轻量偏好约束，运行产物写入 `data/tmp/user_memory/`，不进入 Git。

### 3.6 图片输入

```env
MULTIMODAL_MODEL=
MULTIMODAL_MAX_UPLOAD_MB=10
MULTIMODAL_RETENTION_HOURS=24
MULTIMODAL_TIMEOUT_SECONDS=20
```

如果 `MULTIMODAL_MODEL` 留空，后端会尝试复用当前 `LLM_PROVIDER` 对应的模型配置。图片能力需要 provider/model 支持图像输入；如果当前模型不支持，接口会降级返回保守 image_plan 或错误提示。

### 3.7 ASR 语音输入

```env
ASR_SIDECAR_URL=http://127.0.0.1:8765/transcribe
ASR_MAX_UPLOAD_MB=50
ASR_TIMEOUT_SECONDS=180
```

后端只做 ASR 代理，不内置语音识别模型。录制语音 Demo 前，需要先启动符合该接口的本地 ASR sidecar。

## 4. 数据准备和索引构建

首次启动或 enriched 数据更新后，按顺序执行：

```bash
source server/.venv/bin/activate
python scripts/check_data.py
python scripts/build_enriched_beauty.py
python scripts/build_index.py
```

说明：

- `check_data.py` 检查官方 raw 数据和图片是否存在。
- `build_enriched_beauty.py` 生成或刷新美妆 enriched 数据。
- `build_index.py` 读取 `data/enriched/*_products.jsonl`，写入统一 Chroma `products` collection。
- `data/indexes/` 是本地可重建产物，不提交 Git。

如果检索结果明显不对，优先重新运行 `build_index.py` 并重启后端。

## 5. 推荐 Demo Query

建议录屏和评委体验固定使用少量稳定 query。

| 场景 | Query / 操作 | 展示点 |
| --- | --- | --- |
| 普通文字导购 | `我是油皮，想要200元以内通勤防晒` | 预算、肤质、场景进入 RAG；流式回答；商品卡片 |
| 商品详情 | 点击第一张商品卡片 | 图片、价格、类目、适合人群、卖点、注意事项来自数据源 |
| 信息不足追问 | `我想买护肤品，你推荐什么？` | 不乱推商品，先追问 |
| 反选 / 风险边界 | `敏感肌，最近屏障不稳定，想找修护面霜，不要酒精味太重或者刺激感强的产品` | 排除约束、资料未说明边界、guardrail |
| 多轮对比 | 在防晒推荐后问：`第一款和第三款怎么选？` | history product_ids、对比表、商品指代 |
| 场景组合 | `我去三亚玩，想从防晒到穿搭配一套` | Planner `scene_bundle + search_slots`，跨类目选品 |
| 图片输入可选 | 上传一张无隐私商品/包装图，再补充预算 | 图片 -> image_plan -> 文本 RAG |
| 语音/TTS 可选 | 录音说“帮我找 200 元内通勤防晒”并开启播报 | ASR 转写、TTS 播报、移动端可访问性 |

图片、语音和 TTS 建议只在最终实测稳定时进入主视频。若设备或 provider 不稳定，可在文档中说明已接入，并在视频中只展示文字主链路和技术讲解。

## 6. Demo 视频对应操作路径

5-10 分钟主版建议：

1. 展示仓库和 `/health`，说明是原生 Android + FastAPI。
2. Android 输入防晒 query，展示 `quick_reply` 和流式回答。
3. 展示商品卡片和详情页，强调价格/图片/详情来自数据源。
4. 展示信息不足追问或敏感肌边界，说明防幻觉策略。
5. 展示多轮对比或三亚场景组合，说明 Planner 和多轮状态。
6. 可选展示图片输入、ASR 或 TTS 中最稳定的一项。
7. 展示架构图，解释 RAG、Prompt、guardrail、fallback、trace。
8. 说明边界：不做真实库存、优惠、下单、支付，不承诺零幻觉。

详细逐分钟脚本见 `docs/submission_video_script.md`。

## 7. 常见问题排查

| 问题 | 可能原因 | 处理方式 |
| --- | --- | --- |
| App 一直无回复 | 后端未启动或端口不可达 | 先 `curl /health`；模拟器/真机执行 `adb reverse tcp:8000 tcp:8000` |
| `/health` 是 mock | `.env` 中 `MOCK_LLM=true` 或 provider 缺 Key/model | 改为 `MOCK_LLM=false`，填 `ARK_API_KEY` 和 `ARK_MODEL`，重启后端 |
| 真实模型调用超时 | 网络或代理问题 | 设置本地代理环境变量，或临时切 Yunwu 演示备用 |
| 商品卡片没有图片 | 图片路径无法访问或未走同一 baseUrl | 检查 `/assets/...` 是否能打开；确认 App 连到同一个后端 |
| 检索结果不对 | 索引旧或未构建 | 重新运行 `python scripts/build_index.py` 并重启后端 |
| 信息不足却推荐商品 | query 被历史污染或 state 继承异常 | 开新会话复验；必要时跑 conversation/failure regression |
| 图片上传失败 | 文件不是 JPEG/PNG、超过大小、provider 不支持图片 | 换小图；检查 `MULTIMODAL_*` 和 provider；不稳定就不放主视频 |
| ASR 没有转写 | sidecar 未启动或 URL 不对 | 检查 `ASR_SIDECAR_URL`，先用 curl 或 sidecar 自测 |
| TTS 不播报 | Android 设备无中文 TTS 或设置关闭 | 检查系统 TTS 引擎和 App 内播报设置 |
| Gradle 依赖下载失败 | 网络问题 | 使用 Android Studio 同步，或按本机代理加 `-Dhttp.proxyHost`/`-Dhttps.proxyHost` |

代理示例：

```bash
export https_proxy=http://127.0.0.1:7897
export http_proxy=http://127.0.0.1:7897
export all_proxy=socks5://127.0.0.1:7897
```

Gradle 代理示例：

```bash
./gradlew :client:android:app:assembleDebug \
  -Dhttp.proxyHost=127.0.0.1 -Dhttp.proxyPort=7897 \
  -Dhttps.proxyHost=127.0.0.1 -Dhttps.proxyPort=7897
```

## 8. 可选验证命令

这些命令会读取或生成本地运行产物。提交前可按需要执行。

检索 golden queries：

```bash
server/.venv/bin/python scripts/run_golden_queries.py --require-vector
```

多轮对话：

```bash
server/.venv/bin/python scripts/run_conversation_cases.py
```

多商品对比：

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

真实 API 快速 probe：

```bash
https_proxy=http://127.0.0.1:7897 http_proxy=http://127.0.0.1:7897 \
  server/.venv/bin/python scripts/probe_chat.py \
  --turn 我是油皮，想要200元以内通勤防晒 \
  --turn 我想买护肤品，你推荐什么？ \
  --turn 敏感肌，最近屏障不稳定，想找修护面霜，不要酒精味太重或者刺激感强的产品
```

## 9. 提交前安全检查

```bash
git status --short --branch
python3 scripts/scan_secrets.py --all
git diff --check
git ls-files | rg '\\.(mp4|mov|env|pdf|zip)$'
```

人工确认：

- `.env` 没有进入 Git。
- 文档和录屏没有真实 Key。注意两类隐蔽泄露（曾真实发生）：
  飞书导出 Markdown 会把 Key 中的连字符转义成 `\-` 绕过普通文本搜索；
  课题原始 PDF 内嵌共用 APIKey 且文本流被压缩，无法被文本扫描发现。
  `scan_secrets.py` 已针对这两类加规则：转义 Key 模式 + 禁止跟踪二进制文档。
- `data/tmp/`、`data/indexes/`、`demo/*.mp4`、`demo/*.mov` 没有进入 Git。
- 飞书设计文档和说明文档链接权限为评委可访问。
- 演示视频链接可播放，且没有展示 Key、代理账号、私人图片或本地隐私路径。

## 10. 已知限制

0. “演示身份”是本地 user_id 切换，不是真实账号/登录体系；会话列表是本机内存态，重启 App 后不保留历史会话。
1. 当前不接真实交易系统，不提供库存、优惠、购买链接、下单或支付。
2. 图片输入是把图片理解为文本检索线索，不是完整图搜图。
3. ASR 需要本地 sidecar；没有 sidecar 时文字导购主链路不受影响。
4. TTS 取决于 Android 设备系统能力；没有中文 TTS 时可关闭，不影响 RAG 主链路。
5. 美妆是深度主线，服饰是第二品类样例，其余品类是 thin support。
6. Guardrail 和 claim audit 是工程防线和样例报告，不是完整自动化 groundedness judge 平台。
7. 真实模型仍可能尝试越界表达；项目的目标是发现、拦截、修复或兜底，而不是宣称“零幻觉”。

## 11. 飞书迁移说明

复制到飞书后建议：

1. Bash、ENV、JSON 用飞书代码块保留格式。
2. 环境变量只保留 `YOUR_LOCAL_KEY` 这类占位值。
3. 把本说明放在前半部分，评委先看“最快体验路径”，再看完整复现。
4. 插入最终 App 截图、后端 health 截图和演示视频链接。
5. 用无权限或非编辑者视角检查链接是否可访问。
