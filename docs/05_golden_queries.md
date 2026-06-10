# Golden Queries

用于 MVP 评测和 Demo 脚本。

| ID | Query | 期望能力 | 期望商品/行为 |
| --- | --- | --- | --- |
| GQ-01 | 我是油皮，想要 200 元以内的通勤防晒 | 肤质 + 预算 + 场景过滤 | 推荐欧莱雅防晒；解释轻薄、通勤、价格 |
| GQ-02 | 敏感肌最近屏障不稳定，想找修护面霜 | 肤质 + 修护需求 | 推荐薇诺娜/理肤泉；提示先做局部测试 |
| GQ-03 | 不要酒精味太重或者刺激感强的产品 | 反选/排除 | 避免高刺激描述；给出温和选项和不确定说明 |
| GQ-04 | 预算 300 内，有没有抗初老或者提亮精华 | 预算 + 功效 | 推荐珀莱雅/The Ordinary 等；排除超预算贵价精华 |
| GQ-05 | 干皮想要保湿，不想拔干 | 肤质 + 负面约束 | 推荐保湿面霜/化妆水；避免控油粉底作为主推 |
| GQ-06 | 想要控油底妆或者定妆产品 | 子类目 + 功效 | 推荐粉底液/蜜粉；说明适合油皮或混油 |
| GQ-07 | 欧莱雅防晒和安热沙防晒更适合谁？ | 多商品对比 | 从价格、场景、防水防汗、肤感对比 |
| GQ-08 | 我想买护肤品，你推荐什么？ | 信息不足主动追问 | 先追问肤质、预算和主要需求 |

第一阶段通过标准：

- 至少 3 个 query 端到端跑通 Android -> 后端 -> SSE -> 商品卡片。
- 所有商品卡片字段来自数据源。
- 无明显编造价格、库存或优惠。

## 本地评测命令

构建 Chroma 索引：

```bash
cd /path/to/bytedance-rag-shopping-agent
server/.venv/bin/python scripts/build_index.py
```

运行检索层 benchmark：

```bash
cd /path/to/bytedance-rag-shopping-agent
server/.venv/bin/python scripts/run_golden_queries.py --require-vector
```

输出：

- 默认写入 `data/tmp/evals/golden_queries_latest.jsonl`，该目录已被 `.gitignore` 忽略。
- 每条记录包含 `parsed_intent`、`final_ranking`、`vector_hits_count`、`guardrail_checks` 和失败原因。

联调真实后端 SSE：

```bash
cd /path/to/bytedance-rag-shopping-agent
server/.venv/bin/python scripts/run_golden_queries.py --mode http --check-stream --require-vector
```

当前 2026-05-26 本地结果：8 条 golden queries 在检索层全部通过；其中 GQ-08 会按预期先追问，不返回商品。

运行生成层 guardrail 检查：

```bash
cd /path/to/bytedance-rag-shopping-agent
server/.venv/bin/python scripts/check_generation_guardrails.py
```

检查内容：

- 安全回答可以通过。
- 编造价格、库存、优惠券、下单承诺会触发兜底回答。
- 空回答会触发信息补充式兜底。

## 多轮回归 Case

多轮 case 用来固化真实调试中发现的问题，尤其是：

- 用户已经给出肤质、预算、功效和排除条件时，不应重复追问同一批信息。
- 用户说“先放宽预算”时，应继承上一轮需求，并取消预算硬约束。
- 用户说“预算降到150元”时，应使用最新预算覆盖上一轮预算。
- 当前商品池无同时满足项时，应解释约束冲突，而不是假装推荐。

Case 定义在：

```text
data/eval/conversation_cases.json
```

运行命令：

```bash
cd /path/to/bytedance-rag-shopping-agent
server/.venv/bin/python scripts/run_conversation_cases.py
```

输出：

- 默认写入 `data/tmp/evals/conversation_cases_latest.jsonl`，该目录已被 `.gitignore` 忽略。
- 每条记录包含每一轮的 `retrieval_message`、`parsed_intent`、商品 ID、追问文本和失败原因。

## 单次快速 Probe

如果只想快速看某条 query 或某组多轮对话的真实回复，不想启动 Uvicorn 和 Android，可以直接跑：

```bash
cd /path/to/bytedance-rag-shopping-agent
https_proxy=http://127.0.0.1:7897 http_proxy=http://127.0.0.1:7897 \
  server/.venv/bin/python scripts/probe_chat.py \
  --turn "不要酒精味太重或者刺激感强的产品"
```

多轮调试：

```bash
cd /path/to/bytedance-rag-shopping-agent
https_proxy=http://127.0.0.1:7897 http_proxy=http://127.0.0.1:7897 \
  server/.venv/bin/python scripts/probe_chat.py \
  --turn "我是油皮，想要200元以内通勤防晒。敏感肌最近屏障不稳定，想找修护面霜。不要酒精味太重或者刺激感强的产品。我想买护肤品，你推荐什么？" \
  --turn "先放宽预算"
```

这个脚本直接使用同一个 FastAPI app 的 `/api/debug/retrieve` 和 `/api/chat/stream`，因此不需要重启后端，也不需要打开 Android；输出会包含召回商品、解析出的 intent、多轮合并后的检索文本，以及最终回答。
