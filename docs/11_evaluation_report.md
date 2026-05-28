# 评测记录

日期：2026-05-26
更新：2026-05-28

用途：沉淀当前可复跑的评测证据，后续每次改检索、prompt 或生成约束后更新。

## 当前结论

当前版本完成四层评测：

1. 检索层：8 条 golden queries 全部通过。
2. 生成层：规则 guardrail 能拦截未授权价格、库存、优惠和下单承诺。
3. SSE 层：真实 Ark / Doubao 暂时不可用时，8 条 golden queries 仍能返回完整 `products/token/done` 事件。
4. Android 层：真实 Doubao 回复、商品卡片、图片、详情弹窗和信息不足追问已完成第一轮模拟器复验。

## 检索层 Benchmark

命令：

```bash
cd /Users/jia/Developer/bytedance-rag-shopping-agent
server/.venv/bin/python scripts/run_golden_queries.py --require-vector
```

本地结果：

| ID | 结论 | 说明 |
| --- | --- | --- |
| GQ-01 | PASS | 油皮、200 元以内、通勤防晒；有 vector hits |
| GQ-02 | PASS | 敏感肌、屏障、修护面霜；召回薇诺娜/理肤泉方向 |
| GQ-03 | PASS | 酒精/刺激排除条件进入 intent |
| GQ-04 | PASS | 300 元预算、抗初老/提亮精华 |
| GQ-05 | PASS | 干皮保湿、不想拔干 |
| GQ-06 | PASS | 控油底妆/定妆 |
| GQ-07 | PASS | 欧莱雅防晒和安热沙防晒对比 |
| GQ-08 | PASS | 信息不足时先追问，不返回商品 |

输出文件：

- 默认：`data/tmp/evals/golden_queries_latest.jsonl`
- 本地沙盒验证：`/private/tmp/bytedance_golden_queries_latest.jsonl`

## 生成层 Guardrail

命令：

```bash
cd /Users/jia/Developer/bytedance-rag-shopping-agent
server/.venv/bin/python scripts/check_generation_guardrails.py
```

覆盖场景：

| 场景 | 期望 | 当前结果 |
| --- | --- | --- |
| 安全回答 | 通过 | PASS |
| 编造未授权价格 | 触发兜底 | PASS |
| 编造库存/优惠/下单承诺 | 触发兜底 | PASS |
| 无证据断言“不含/不会刺激” | 触发兜底 | PASS |
| 空回答 | 触发追问信息式兜底 | PASS |

## 真实 Doubao 复验记录

命令：

```bash
cd /Users/jia/Developer/bytedance-rag-shopping-agent
https_proxy=http://127.0.0.1:7897 http_proxy=http://127.0.0.1:7897 \
  server/.venv/bin/python <one-off-real-api-check>
```

本地结果：

| ID | 真实 API | Guardrail | 备注 |
| --- | --- | --- | --- |
| GQ-01 | 成功 | 通过 | 油皮 200 元内通勤防晒，回答围绕召回商品 |
| GQ-02 | 成功 | 通过 | 敏感肌屏障修护，回答围绕理肤泉/薇诺娜 |
| GQ-03 | 成功 | 已拦截 | 模型断言“不会有酒精味和刺激感”，但商品资料没有明确支持；已加入 unsupported absence claim 校验，复验时触发安全兜底 |

复验要点：

- `.env` 已被本地读取，`MOCK_LLM=false`、API Key 和模型名均存在。
- 真实 API 调用通过 HTTP/HTTPS 代理成功；不要在当前环境默认使用 `all_proxy=socks5://...`，否则 `httpx` 会要求额外 SOCKS 依赖。
- 当前最有价值的 failure case 是 GQ-03：用户说“不要酒精/刺激”时，模型容易把“没有明确风险提示”说成“不会刺激/没有酒精味”。这类断言已进入生成层 guardrail。

### 2026-05-28 三轮 Probe

命令：

```bash
cd /Users/jia/Developer/bytedance-rag-shopping-agent
https_proxy=http://127.0.0.1:7897 http_proxy=http://127.0.0.1:7897 \
  server/.venv/bin/python scripts/probe_chat.py \
  --turn 我是油皮，想要200元以内通勤防晒 \
  --turn 我想买护肤品，你推荐什么？ \
  --turn 敏感肌，最近屏障不稳定，想找修护面霜，不要酒精味太重或者刺激感强的产品 \
  --output /private/tmp/probe_chat_real_3turns_20260528.jsonl
```

结果：

| Turn | 结论 | 召回商品 | 备注 |
| --- | --- | --- | --- |
| 1 | PASS | `p_beauty_006`, `p_beauty_018` | 油皮、200 元以内、通勤防晒解析正确；回答围绕召回商品 |
| 2 | PASS | `p_beauty_006`, `p_beauty_018` | 短追问继承上一轮油皮/预算/通勤上下文 |
| 3 | PASS with rewrite | `p_beauty_012`, `p_beauty_007`, `p_beauty_006` | 首次生成触发 `unsupported_absence_claims:酒精`，二次改写后保留谨慎边界 |

观察：

- 真实模型仍倾向把“资料没有风险提示”说成“没有酒精/不会刺激”，因此二次改写是必要的。
- 二次改写后的回答会明确说“资料中没有看到相关风险提示，但不能确认具体成分或刺激风险”，更符合 evidence-bound 要求。
- Probe 路径不依赖 Uvicorn 或 Android，适合每次改 prompt / guardrail 后快速复验。

## Android 端复验记录

日期：2026-05-28
设备：`emulator-5554` / `Medium_Phone_API_36.0`

本轮新增了 3 个演示快捷问题 chip，避免 adb 和现场演示时中文输入不稳定：

- `油皮通勤防晒` -> `我是油皮，想要200元以内通勤防晒`
- `敏感肌修护` -> `敏感肌，最近屏障不稳定，想找修护面霜，不要酒精味太重或者刺激感强的产品`
- `信息不足追问` -> `我想买护肤品，你推荐什么？`

验证结果：

| 场景 | 结论 | 证据 |
| --- | --- | --- |
| App 启动 | PASS | UI 树出现标题、输入框和 3 个快捷问题 |
| 油皮通勤防晒 | PASS | Android 发出 `POST http://10.0.2.2:8000/api/chat/stream`；UI 展示真实回复、商品卡片、图片、价格和标签 |
| 商品详情 | PASS | 点击商品卡片后弹窗展示价格、类目、推荐理由、适合、使用场景、卖点和注意事项 |
| 信息不足追问 | PASS | 空会话下返回“你更在意肤质、预算，还是防晒/修护/控油这类具体功效？”，没有乱推商品 |
| 连续多轮展示 | PASS | 连续点击 `油皮通勤防晒` 和 `敏感肌修护` 后，列表自动滚到第二条回复和商品卡片；两次 POST 均无网络错误 |

本地截图证据：

- `/private/tmp/ragshopping_quick_prompts_20260528.png`
- `/private/tmp/ragshopping_after_oily_prompt_20260528.png`
- `/private/tmp/ragshopping_product_detail_20260528.png`
- `/private/tmp/ragshopping_clarification_prompt_20260528.png`
- `/private/tmp/ragshopping_autoscroll_two_prompts_20260528.png`

## SSE 稳定性

命令：

```bash
cd /Users/jia/Developer/bytedance-rag-shopping-agent
server/.venv/bin/python scripts/run_golden_queries.py --check-stream --require-vector
```

当前结果：

- 8 条 golden queries 均返回完整 SSE 形态。
- 当 Ark / Doubao 连接失败时，后端记录 warning，并返回基于召回商品卡片的安全兜底回答。
- 这不是最终真实模型效果评测，只证明 Android 端不会因为模型暂时不可用而卡死。

## 当前边界

1. Guardrail V1 是规则校验，不是完整 groundedness judge。
2. 目前只校验价格和明显商业承诺，尚未对所有功效声明做细粒度证据匹配。
3. Android 端真实 Doubao 已完成第一轮复验；自动滚动已完成一轮模拟器复验，后续录屏前仍需做一次人工检查。
4. Chroma 当前只索引 6 条 enriched 美妆商品，扩展到 25 条后需要重跑评测。

## 下一步

1. 按 `docs/12_demo_script.md` 录第一版 1 分钟闭环 Demo。
2. 把被 guardrail 拦截的真实输出继续沉淀为 failure cases。
3. 扩展 enriched 数据后更新评测表。
