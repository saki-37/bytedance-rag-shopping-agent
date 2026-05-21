# ByteDance RAG Shopping Agent

字节 AI 全栈挑战赛项目：基于 RAG 的多模态电商智能导购 AI Agent。

第一阶段目标是跑通美妆文字导购闭环：

Android Kotlin 原生客户端输入文字 -> FastAPI 后端检索美妆商品数据 -> 调用大模型流式生成回复 -> 客户端展示回复和商品卡片。

## Repository Layout

```text
client/android/   Android Kotlin + Jetpack Compose 客户端
server/           FastAPI 后端服务
data/raw/         官方原始数据集，不直接修改
data/enriched/    结构化增强数据
docs/             项目文档、技术决策、API 契约、推进记录
scripts/          数据检查、增强、索引构建、评测脚本
```

## Quick Start

### Backend

```bash
cd server
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example ../.env
python ../scripts/check_data.py
python ../scripts/build_enriched_beauty.py
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

如果没有配置真实 `ARK_API_KEY`，后端会使用本地 mock 流式回复，方便先验证端到端链路。

### Android

```bash
./gradlew :client:android:app:assembleDebug
```

默认后端地址是 Android 模拟器访问宿主机的 `http://10.0.2.2:8000`。

如果 Gradle 需要走本地代理：

```bash
./gradlew :client:android:app:assembleDebug \
  -Dhttp.proxyHost=127.0.0.1 -Dhttp.proxyPort=7897 \
  -Dhttps.proxyHost=127.0.0.1 -Dhttps.proxyPort=7897
```

## Current MVP Scope

- 只做美妆护肤文字导购。
- 暂不做图片、语音、购物车、下单。
- 商品价格、品牌、图片和卡片字段必须来自数据源，不由模型自由生成。
