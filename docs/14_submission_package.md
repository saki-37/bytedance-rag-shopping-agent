# 提交材料清单

日期：2026-06-04

用途：把评委或后续复盘最需要看的材料收束到一页，避免代码、文档、录屏和评测证据散落。

## 提交入口

建议提交时优先给出：

1. GitHub 仓库：`saki-37/bytedance-rag-shopping-agent`
2. 根目录 README：`README.md`
3. Demo 录屏：优先上传本地 `demo/录屏v1_submission_phone_60s.mp4`；原始录屏为 `demo/录屏v1.mov`
4. 架构说明：`docs/10_architecture.md`
5. 评测记录：`docs/11_evaluation_report.md`
6. 依赖版本与复现说明：`docs/20_reproducibility_and_dependencies.md`
7. 答辩口袋稿：`docs/22_defense_cheatsheet.md`

其中 README 是第一入口；本页是提交前自检清单；架构说明和评测记录用于支撑答辩或技术追问。
如果需要快速准备口头讲解，优先看答辩口袋稿。

## 一句话项目介绍

这是一个原生 Android + FastAPI 的美妆 RAG 导购 Agent。用户在 App 中输入肤质、预算、使用场景和排除条件后，后端通过结构化硬过滤、关键词/属性匹配和 Chroma 向量召回筛选商品，再调用 Doubao / Ark 生成受商品证据约束的导购回复，最后在 Android 端流式展示回答、商品卡片、图片和详情弹窗。

## 当前可展示能力

| 能力 | 当前状态 | 对应材料 |
| --- | --- | --- |
| Android 原生聊天 | 已完成 | `client/android/`、Demo 录屏 |
| FastAPI 后端 | 已完成 | `server/app/`、`docs/10_architecture.md` |
| SSE 流式回复 | 已完成 | `docs/04_api_contract.md`、`docs/10_architecture.md` |
| 商品卡片与图片 | 已完成 | Demo 录屏、`docs/11_evaluation_report.md` |
| 商品详情弹窗 | 已完成 | Demo 录屏、`docs/11_evaluation_report.md` |
| 真实 Doubao 接入 | 已完成第一版 | `docs/11_evaluation_report.md` |
| RAG 检索与内部三层 trace | 已完成 V1+ | `docs/08_rag_retrieval_strategy.md`、`docs/10_architecture.md`、`docs/11_evaluation_report.md` |
| 反幻觉 guardrail / evidence-aware fallback | 已完成 V1+ | `docs/11_evaluation_report.md`、`server/app/guardrails.py` |
| Golden query 评测 | 已完成第一轮 | `scripts/run_golden_queries.py`、`docs/11_evaluation_report.md` |
| 子类 query 评测 | 已完成第一轮 | `scripts/run_subcategory_queries.py`、`docs/11_evaluation_report.md` |
| 多商品对比 | 已完成第一版 | `scripts/run_comparison_queries.py`、`docs/11_evaluation_report.md` |
| Groundedness 陷阱评测 | 已完成生成层第一版 | `data/eval/groundedness_cases.json`、`scripts/run_groundedness_cases.py`、`docs/11_evaluation_report.md` |
| 轻量反馈闭环 | 已完成 Android + 后端第一版 | Android `有用` / `不准确` 按钮、`POST /api/feedback`、`scripts/check_feedback_loop.py`、`docs/04_api_contract.md` |
| 依赖版本与复现说明 | 已完成 | `docs/20_reproducibility_and_dependencies.md` |

## 评分点对照

| 评分维度 | 当前抓手 | 说明 |
| --- | --- | --- |
| 基础功能完整性 | Android -> FastAPI -> RAG -> Doubao -> SSE -> 商品卡片 | 第一版真实模型端到端闭环已跑通 |
| 工程质量 | monorepo、API 契约、架构文档、安全配置、评测脚本、依赖复现说明 | README 已作为提交入口；`docs/` 可支撑复盘和答辩 |
| 效果与可靠性 | golden、subcategory、apparel、comparison、conversation、groundedness full mock / retrieval-only、真实 API golden stream 三轮、guardrail、真实 groundedness failure cases、三层 trace、结果型绝对承诺拦截、claim-level audit 样例、`GRD-L03/05/08/L01` 真实 API + AI review | 当前主打“约束感知 + 可解释 trace + 反编造回归”，不是单纯聊天框；下一步把证据整理成答辩可讲版本 |
| 加分项深度 | 可解释 RAG、反幻觉、多商品对比、轻量 graph-aware、多品类样例、Android 可见轻量反馈闭环、移动端流式体验、claim-level audit 样例 | 下一阶段优先做最终复验与提交材料收口；完整自动化 claim-level judge 平台仍是可选增强 |

## Demo 讲解顺序

详见 `docs/12_demo_script.md`。当前建议上传 60 秒手机屏版本：

```text
demo/录屏v1_submission_phone_60s.mp4
```

建议 60-90 秒内展示：

1. 打开 Android App，展示快捷问题。
2. 点击 `油皮通勤防晒`，展示真实流式回复和商品卡片。
3. 点击商品卡片，展示详情弹窗。
4. 可选点击回答下方 `有用` / `不准确`，展示反馈闭环已接入真实 App。
5. 点击或展示 `信息不足追问`，证明系统不会在信息不足时强行推荐。

讲解重点：

- 价格、品牌、图片和详情字段来自数据源，不由模型自由生成。
- 预算、肤质、使用场景和排除条件进入检索约束。
- 对“无酒精/不刺激”等资料未支持的绝对断言，后端会触发 guardrail 或二次改写。

## 运行复现路径

完整版本表、环境说明和复现检查表见 `docs/20_reproducibility_and_dependencies.md`。这里保留最短复现顺序：

最短复现顺序：

```bash
cd bytedance-rag-shopping-agent
python3 -m venv server/.venv
source server/.venv/bin/activate
pip install -r server/requirements.txt
cp .env.example .env
python scripts/check_data.py
python scripts/build_enriched_beauty.py
python scripts/build_index.py
cd server
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Android 端：

```bash
cd bytedance-rag-shopping-agent
adb reverse tcp:8000 tcp:8000
./gradlew :client:android:app:assembleDebug
```

说明：Debug APK 只包含 Android 客户端，不包含 FastAPI 后端。评审本地运行时，需要先启动后端，再通过 Android Studio / APK 运行客户端。当前 App 优先使用 `127.0.0.1:8000` + `adb reverse`，如果未设置 reverse，会回退尝试模拟器宿主机地址 `10.0.2.2:8000`。真机运行时也建议使用 USB 调试下的 `adb reverse`，或改成手机可访问的后端地址后重新构建。

真实模型需要在本地 `.env` 中填入：

```env
ARK_API_KEY=YOUR_LOCAL_KEY
ARK_MODEL=YOUR_MODEL_ENDPOINT
MOCK_LLM=false
```

不要把真实 `.env`、API Key、官方含 Key 原文或包含 Key 的截图/录屏提交到 Git。

## 评测复现路径

正式 benchmark 先跑真实 API。若本地需要代理，先在终端设置代理；不要把 mock 结果当作正式效果结论。

```bash
cd bytedance-rag-shopping-agent
export https_proxy=http://127.0.0.1:7897
export http_proxy=http://127.0.0.1:7897
export all_proxy=socks5://127.0.0.1:7897

server/.venv/bin/python scripts/run_golden_queries.py --require-vector
server/.venv/bin/python scripts/run_subcategory_queries.py --require-vector
server/.venv/bin/python scripts/run_conversation_cases.py
server/.venv/bin/python scripts/run_comparison_queries.py --require-vector
MOCK_LLM=false PYTHONDONTWRITEBYTECODE=1 server/.venv/bin/python scripts/run_groundedness_cases.py
server/.venv/bin/python scripts/check_generation_guardrails.py
server/.venv/bin/python scripts/check_feedback_loop.py
```

离线结构检查可以额外跑：

```bash
PYTHONDONTWRITEBYTECODE=1 server/.venv/bin/python scripts/run_groundedness_cases.py --mock-llm
PYTHONDONTWRITEBYTECODE=1 server/.venv/bin/python scripts/run_groundedness_cases.py --mock-llm --retrieval-only
```

真实 API 快速检查：

```bash
https_proxy=http://127.0.0.1:7897 http_proxy=http://127.0.0.1:7897 \
  server/.venv/bin/python scripts/probe_chat.py \
  --turn 我是油皮，想要200元以内通勤防晒 \
  --turn 我想买护肤品，你推荐什么？ \
  --turn 敏感肌，最近屏障不稳定，想找修护面霜，不要酒精味太重或者刺激感强的产品
```

## 提交前检查

```bash
git status --short
python3 scripts/scan_secrets.py --all
git diff --check
```

人工确认：

- `.env` 没有进入 Git。
- README 和 docs 里没有真实 `ARK_API_KEY`。
- Demo 录屏中没有显示 API Key 或终端敏感配置。
- `data/indexes/`、`data/tmp/`、`*.mov`、`*.mp4` 不进入 Git。
- 如果平台要求上传视频，使用本地录屏作为单独附件，而不是提交到代码仓库。
- 当前 60 秒版本已裁掉 Android Studio 主界面和终端内容；仍能看到模拟器悬浮控制条和一次剪贴板提示，若时间允许可后续重录更干净版本。

## 当前边界

当前提交版本明确不覆盖：

1. 图片输入、语音输入、购物车和下单。
2. 全品类导购主线。
3. 完整重型 GraphRAG / Neo4j 图数据库。
4. 完整自动化 claim-level groundedness judge 平台化；当前已有人工标注样例和报告脚本。
5. 完整自动反馈归因和自动转 benchmark。

这些不是当前版本的失败点，而是下一阶段路线。当前版本主打的是：

> 可运行的原生移动端闭环 + 约束感知 RAG + 证据约束生成 + 可复验评测。

## 下一阶段建议

1. 当前下一步优先做最终复验与提交前检查：真实 API、Android 构建/演示、secret scan、录屏安全。
2. Android 反馈按钮已完成第一版；后续可把 `inaccurate` 样例自动转成 benchmark 或数据增强任务。
3. 最终提交前按 `docs/20_reproducibility_and_dependencies.md` 跑一轮复现检查，并确认 Demo 录屏没有敏感信息。
