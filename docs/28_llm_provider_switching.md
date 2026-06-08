# LLM Provider 切换与演示模型候选

日期：2026-06-08

用途：说明当前项目如何在正式评测的 Ark / Doubao provider 和演示用 Yunwu provider 之间切换，以及如何选择和验证演示模型。正式 benchmark 仍以 Ark / Doubao 为准；Yunwu 只作为现场演示或录屏时降低等待时间的备用 provider。

## 当前结论

推荐把 `.env` 当作长期默认配置，把命令行环境变量当作单次临时覆盖：

- `.env` 长期保持 `LLM_PROVIDER=ark`，用于正式测试和回归。
- 演示时用命令行前缀临时覆盖 `LLM_PROVIDER=yunwu` 和 `YUNWU_MODEL=...`。
- 每次改 provider 或模型后，都要重启 Uvicorn；后端启动时读取配置。
- `GET /health` 会返回当前 `llm_provider` 和 `llm_model`，用于确认本轮实际生效的模型。

## `.env` 建议写法

仓库读取的是根目录 `.env`：

```text
/Users/jia/Developer/bytedance-rag-shopping-agent/.env
```

建议 `.env` 同时保留正式 provider 和演示 provider 的 key，但默认 provider 仍设为 `ark`：

```env
# 正式测试默认
LLM_PROVIDER=ark

ARK_API_KEY=YOUR_ARK_KEY
ARK_BASE_URL=https://ark.cn-beijing.volces.com/api/v3/
ARK_MODEL=YOUR_ARK_ENDPOINT

# 演示备用
YUNWU_API_KEY=YOUR_YUNWU_KEY
YUNWU_BASE_URL=https://yunwu.ai/v1
YUNWU_MODEL=gpt-5.4-mini

MOCK_LLM=false
PLANNER_TIMEOUT_SECONDS=20
APP_ENV=local
```

`.env` 里的 `YUNWU_MODEL` 只是默认备用值。临时演示时可以在命令行覆盖它，不需要反复编辑 `.env`。

## 两种切换方式

### 方式一：改 `.env`

适合持续一整段时间都用同一个 provider：

```env
LLM_PROVIDER=yunwu
YUNWU_MODEL=gpt-5.4-mini
```

然后重启后端。

切回正式测试：

```env
LLM_PROVIDER=ark
```

### 方式二：命令行临时覆盖

适合演示、录屏或模型 A/B smoke test。命令行环境变量会覆盖 `.env` 中同名字段。

启动后端时临时切到 Yunwu：

```bash
cd /Users/jia/Developer/bytedance-rag-shopping-agent/server
LLM_PROVIDER=yunwu YUNWU_MODEL=gpt-5.4-mini \
  uvicorn app.main:app --host 0.0.0.0 --port 8000
```

只跑一次 probe：

```bash
cd /Users/jia/Developer/bytedance-rag-shopping-agent
LLM_PROVIDER=yunwu YUNWU_MODEL=gpt-5.4-mini \
  server/.venv/bin/python scripts/probe_chat.py \
  --turn 我是油皮，想要200元以内通勤防晒
```

## 生效检查

后端启动后检查：

```bash
curl http://127.0.0.1:8000/health
```

期望看到类似：

```json
{
  "status": "ok",
  "catalog_size": 100,
  "mock_llm": false,
  "llm_provider": "yunwu",
  "llm_model": "gpt-5.4-mini"
}
```

如果 `llm_provider` 仍是 `ark`，说明本轮没有切成功；通常是后端没有重启，或命令行环境变量没有带到启动命令里。

## 模型候选

2026-06-08 使用 Yunwu `/v1/models` 查询到当前账号可见模型后，建议把候选分成四档。这里列的是适合当前文本导购链路的 chat 模型，不包含 embedding、reranker、TTS、Whisper、图片、视频模型。

| 角色 | 模型 ID | 推荐用途 | 注意事项 |
| --- | --- | --- | --- |
| 第一候选 | `gpt-5.4-mini` | 演示默认候选；比 `gpt-4o-mini` 更新，也应该比大模型更轻 | 需要先跑 probe，确认流式和 Planner JSON 稳定 |
| 速度候选 | `gemini-3.5-flash` | 现场速度优先；适合减少等待 | 需要确认中文导购口吻和 guardrail 命中情况 |
| 质量候选 | `claude-sonnet-4-6` | 回答质量和指令遵循优先 | 可能比 mini / flash 慢；不建议作为唯一现场备选 |
| 保底候选 | `gpt-4o-mini` | 兼容性保守；ActiView 里已有类似 OpenAI-compatible 使用经验 | 能力不一定最新，但最稳妥 |

可选补充：

| 系列 | 可试模型 | 用途 |
| --- | --- | --- |
| OpenAI 强模型 | `gpt-5.5`, `gpt-5.5-pro` | 只适合质量对比，不适合现场低延迟演示默认 |
| Gemini 强模型 | `gemini-3.1-pro-preview`, `gemini-3-pro-preview`, `gemini-2.5-pro` | 质量或复杂推理对比 |
| Claude 强模型 | `claude-opus-4-8`, `claude-opus-4-7` | 高质量对比；不建议演示默认 |
| Yunwu 上的 Doubao | `doubao-seed-2-0-mini-260428`, `doubao-seed-2-0-lite-260428`, `doubao-seed-2-0-pro-260215` | 如果想备用 provider 仍尽量贴近豆包生态 |

## 模型选择原则

当前系统每轮可能调用两次模型：

1. Planner：输出结构化 `RetrievalPlan` JSON。
2. Answer generator：生成最终导购回答，并接受 guardrail 校验。

所以演示模型不是只看“聪不聪明”，还要看：

- Planner JSON 是否稳定。
- 首 token 是否快。
- stream 是否正常。
- 中文导购口吻是否自然。
- 是否容易触发 guardrail 后 fallback。
- 价格、库存、优惠、无证据功效等边界是否保守。

因此推荐顺序是：

```text
gpt-5.4-mini
-> gemini-3.5-flash
-> claude-sonnet-4-6
-> gpt-4o-mini
```

如果 `gpt-5.4-mini` probe 稳定，它可以作为演示默认；如果它慢或格式不稳，切 `gemini-3.5-flash`；如果要展示回答质量，试 `claude-sonnet-4-6`；如果现场出现兼容问题，退回 `gpt-4o-mini`。

## 三模型 smoke test

演示前建议用同一条 query 对三个候选做最小对比：

```bash
cd /Users/jia/Developer/bytedance-rag-shopping-agent

LLM_PROVIDER=yunwu YUNWU_MODEL=gpt-5.4-mini \
  server/.venv/bin/python scripts/probe_chat.py \
  --turn 我是油皮，想要200元以内通勤防晒

LLM_PROVIDER=yunwu YUNWU_MODEL=gemini-3.5-flash \
  server/.venv/bin/python scripts/probe_chat.py \
  --turn 我是油皮，想要200元以内通勤防晒

LLM_PROVIDER=yunwu YUNWU_MODEL=claude-sonnet-4-6 \
  server/.venv/bin/python scripts/probe_chat.py \
  --turn 我是油皮，想要200元以内通勤防晒
```

记录时重点看：

- 总耗时和首 token 体感。
- 是否返回商品卡片。
- 回答是否只基于卡片和商品资料。
- 有没有库存、优惠、下单承诺、无证据“不含/不会”等高风险说法。
- trace 中 `planner_trace.fallback_reason` 是否频繁出现。

## 不能替代正式评测

Yunwu provider 是演示加速路径，不是正式评测口径。正式回归、答辩质量证据和提交材料里的真实模型评测，仍应切回：

```env
LLM_PROVIDER=ark
MOCK_LLM=false
```

如果报告里使用了 Yunwu 输出，必须标注为“演示 provider / 非正式 benchmark”。
