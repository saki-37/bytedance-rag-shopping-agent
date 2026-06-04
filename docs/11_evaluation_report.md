# 评测记录

日期：2026-05-26
更新：2026-06-03

用途：沉淀当前可复跑的评测证据，后续每次改检索、prompt 或生成约束后更新。

## 当前结论

当前版本完成四层评测，并已在 25 条美妆增强数据和 5 条服饰运动样例上复跑：

1. 检索层：8 条 golden queries、6 条美妆子类 queries 和 5 条服饰运动 V2-B queries 全部通过，Chroma 当前使用统一 `products` collection，索引 30 条 enriched 商品，并通过 metadata filter 限定类目、子类和预算。
2. 生成层：规则 guardrail 能拦截未授权价格、库存、优惠、下单承诺和无证据的绝对断言。
3. SSE 层：真实 Ark / Doubao 暂时不可用时，8 条 golden queries 仍能返回完整 `products/token/done` 事件。
4. Android 层：真实 Doubao 主线回复、商品卡片、图片、详情弹窗、信息不足追问已完成模拟器复验；新增子类抽样在 `MOCK_LLM=true` 下完成，重点验证检索、卡片和布局。

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

2026-05-28 数据扩展后复跑结果：

- `server/.venv/bin/python scripts/run_golden_queries.py --require-vector --output /private/tmp/bytedance-rag-golden-metadata-final.jsonl`
- 8 条全部 PASS。
- 每条非追问 query 均有 vector hits，`GQ-08` 信息不足仍保持先追问。
- 本轮 vector hits 来自统一 `products` collection，并通过 `canonical_category=beauty` 等 metadata filter 限定召回范围。

## 子类 Query Benchmark

用途：数据扩到 25 条后，单纯的 golden queries 仍偏主线场景，不能充分覆盖新增子类。新增子类 query 用来检查“用户明确说洁面/眼霜/蜜粉/唇釉/眉笔/卸妆时，系统是否召回对应子类，而不是被相邻功效词带偏”。

命令：

```bash
cd /Users/jia/Developer/bytedance-rag-shopping-agent
server/.venv/bin/python scripts/run_subcategory_queries.py --require-vector
```

2026-05-28 本地结果：

| ID | 结论 | 期望子类 | 当前召回 |
| --- | --- | --- | --- |
| SQ-01 | PASS | 洁面 | `p_beauty_011` |
| SQ-02 | PASS | 眼霜 | `p_beauty_021`, `p_beauty_016` |
| SQ-03 | PASS | 蜜粉 | `p_beauty_013` |
| SQ-04 | PASS | 唇釉 | `p_beauty_015` |
| SQ-05 | PASS | 眉笔 | `p_beauty_025` |
| SQ-06 | PASS | 卸妆 | `p_beauty_017` |

关键修正：

- 将“洁面”和“卸妆”从泛化“清洁”中拆出，避免正文里的“洁面后使用”“卸妆水卸除”误触发。
- 对 `底妆`、`定妆`、`洁面`、`卸妆`、`眼周护理`、`唇妆`、`眉妆` 这类子类级意图做更严格匹配，优先匹配商品子类目和专属标签。
- 保留 vector hits 作为语义召回证据，但子类硬约束优先于相似度排序。

## 服饰运动 V2-B Benchmark

用途：验证多品类 schema 不只是文档设计。当前先标注 5 条服饰运动样例，并用 query 检查类目边界、子类硬约束、预算和关键词召回。

命令：

```bash
cd /Users/jia/Developer/bytedance-rag-shopping-agent
server/.venv/bin/python scripts/run_subcategory_queries.py \
  --cases data/eval/apparel_queries.json \
  --require-vector \
  --output /private/tmp/bytedance-rag-apparel-metadata-final.jsonl
```

2026-05-28 本地结果：

| ID | 结论 | 期望子类 | 当前召回 |
| --- | --- | --- | --- |
| apparel_001_commute_tshirt_budget | PASS | 短袖T恤 | `p_clothes_001` |
| apparel_002_training_quick_dry | PASS | 短袖T恤 | `p_clothes_002`, `p_clothes_001` |
| apparel_003_cushion_running_shoes | PASS | 跑步鞋 | `p_clothes_007` |
| apparel_004_waterproof_hiking_shoes | PASS | 徒步鞋 | `p_clothes_014` |
| apparel_005_commute_outdoor_backpack | PASS | 背包 | `p_clothes_018` |

关键修正：

- 后端现在从 `data/enriched/*_products.jsonl` 加载多份 enriched 数据。
- `product_search_text` 纳入 `display`、`variants`、`category_attributes`、`retrieval` 和 `source`，使第二品类样例能参与关键词/字段检索。
- `build_index.py` 现在索引所有 enriched 商品到统一 Chroma `products` collection，并写入 `canonical_category`、`sub_category`、`base_price` 等 metadata。
- Query parser 增加 `apparel` 类目边界和 `sub_category` 硬约束；向量召回也带同样的 metadata filter，避免服饰 query 被美妆向量召回抢分。
- 本轮 apparel benchmark 已加 `--require-vector`，5 条均有 vector hits。

## 多轮对话 Regression

命令：

```bash
cd /Users/jia/Developer/bytedance-rag-shopping-agent
server/.venv/bin/python scripts/run_conversation_cases.py --output /private/tmp/bytedance-rag-conversation.jsonl
```

2026-05-28 数据扩展后复跑结果：

| ID | 结论 | 说明 |
| --- | --- | --- |
| CQ-01 | PASS | 复杂约束下保留已知条件，返回可证据支撑的部分匹配 |
| CQ-02 | PASS | 用户放宽预算时继承上一轮需求并取消预算硬约束 |
| CQ-03 | PASS | 用户把预算降到 150 元时，因没有同时满足功效和预算的商品而主动追问 |
| CQ-04 | PASS | 泛泛想买护肤品时先追问，不乱推商品 |

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

本轮新增了演示快捷问题 chip，避免 adb 和现场演示时中文输入不稳定：

- `油皮通勤防晒` -> `我是油皮，想要200元以内通勤防晒`
- `敏感肌修护` -> `敏感肌，最近屏障不稳定，想找修护面霜，不要酒精味太重或者刺激感强的产品`
- `信息不足追问` -> `我想买护肤品，你推荐什么？`
- `洁面` -> `预算100以内，混合肌日常温和洁面，洗后不要太拔干`
- `眼霜` -> `眼周干燥卡粉，有没有350元以内的保湿眼霜`
- `蜜粉` -> `油皮夏天想要150元以内控油定妆蜜粉`
- `唇釉` -> `学生党想要150元以内日常通勤唇釉，滋润一点`
- `眉笔` -> `新手想要100元以内自然防晕染眉笔`
- `卸妆` -> `敏感肌想要200元以内温和卸妆，不要酒精`

验证结果：

说明：油皮防晒、商品详情、信息不足追问和连续多轮展示来自真实 Doubao 复验；眼霜、蜜粉、卸妆子类抽样使用 `MOCK_LLM=true`，用于快速验证扩展数据后的检索命中、卡片渲染和布局稳定性。

| 场景 | 结论 | 证据 |
| --- | --- | --- |
| App 启动 | PASS | UI 树出现标题、输入框和 9 个快捷问题 |
| 油皮通勤防晒 | PASS | Android 发出 `POST http://10.0.2.2:8000/api/chat/stream`；UI 展示真实回复、商品卡片、图片、价格和标签 |
| 商品详情 | PASS | 点击商品卡片后弹窗展示价格、类目、推荐理由、适合、使用场景、卖点和注意事项 |
| 信息不足追问 | PASS | 空会话下返回“你更在意肤质、预算，还是防晒/修护/控油这类具体功效？”，没有乱推商品 |
| 连续多轮展示 | PASS | 连续点击 `油皮通勤防晒` 和 `敏感肌修护` 后，列表自动滚到第二条回复和商品卡片；两次 POST 均无网络错误 |
| 眼霜子类 | PASS | 点击 `眼霜` 后展示科颜氏 `¥320` 和 AHC `¥139` 两张眼霜卡片 |
| 蜜粉子类 | PASS | 点击 `蜜粉` 后只展示方里 `¥99` 蜜粉卡片，没有混入防晒、精华或眉笔 |
| 卸妆子类 | PASS | 点击 `卸妆` 后只展示芳珂 `¥178` 卸妆卡片，标签包含“卸妆/清洁/敏感肌/温和/无酒精” |

本地截图证据：

- `/private/tmp/ragshopping_quick_prompts_20260528.png`
- `/private/tmp/ragshopping_after_oily_prompt_20260528.png`
- `/private/tmp/ragshopping_product_detail_20260528.png`
- `/private/tmp/ragshopping_clarification_prompt_20260528.png`
- `/private/tmp/ragshopping_autoscroll_two_prompts_20260528.png`
- `/private/tmp/ragshopping_yanshuang.png`
- `/private/tmp/ragshopping_mifen.png`
- `/private/tmp/ragshopping_xiezhuang.png`

## 多商品对比 Benchmark

命令：

```bash
cd /Users/jia/Developer/bytedance-rag-shopping-agent
server/.venv/bin/python scripts/run_comparison_queries.py \
  --require-vector \
  --output /private/tmp/bytedance-rag-comparison.jsonl
```

当前结果：**3 / 3 PASS**。

| Case | 场景 | 期望 | 当前结果 |
| --- | --- | --- | --- |
| CMP-01 | 欧莱雅防晒和安热沙防晒怎么选 | 召回两款防晒，进入 comparison mode | PASS：召回 `p_beauty_010`、`p_beauty_023`、`p_beauty_006`，vector hits=8 |
| CMP-02 | AIRism 和 DRY-EX 两件 T 恤怎么选 | 召回两件 T 恤，进入 comparison mode | PASS：召回 `p_clothes_001`、`p_clothes_002`，vector hits=2 |
| CMP-03 | 跑步鞋和徒步鞋该买哪个 | 召回跑步鞋和徒步鞋，进入 comparison mode | PASS：召回 `p_clothes_014`、`p_clothes_007`，vector hits=2 |

说明：

1. 第一版不新增复杂 UI，继续复用聊天回复和多商品卡片。
2. Query parser 会识别 `对比`、`比较`、`怎么选`、`选哪个`、`买哪个`、`该买哪个`、`哪个更`、`哪款更`、`更适合`、`二选一`、`区别` 等触发词。
3. 真实 LLM prompt 已要求对比时围绕价格、适合对象/场景、优势、注意事项和保守选择建议回答。
4. 如果真实 LLM 输出被 guardrail 拦截，安全兜底回答也会生成对比式结构，并坚持只基于召回商品资料。

## SSE 稳定性

## RetrievalTrace 可解释性字段

目标：让 debug 接口和离线 JSONL 不只给最终商品列表，还能解释“为什么进入这个候选集、哪些商品被过滤、最终 ranking 靠哪些信号”。

新增字段：

| 字段 | 含义 | 示例 |
| --- | --- | --- |
| `metadata_filter` | 传给 Chroma `products` collection 的 metadata filter | `{"canonical_category": "beauty"}` |
| `filter_summary` | 后端硬过滤原因计数 | `{"category": 5, "required_effect": 16}` |
| `ranking_signals` | 每个最终商品的排序信号分桶 | `keyword`、`vector`、`facet`、`budget`、`soft_preference` |

当前已覆盖的输出：

1. `/api/debug/retrieve` 的 `trace`。
2. `scripts/run_golden_queries.py` 输出 JSONL。
3. `scripts/run_subcategory_queries.py` 输出 JSONL。
4. `scripts/run_comparison_queries.py` 输出 JSONL。
5. `scripts/run_conversation_cases.py` 输出 JSONL。

复验命令：

```bash
server/.venv/bin/python scripts/run_comparison_queries.py \
  --require-vector \
  --output /private/tmp/bytedance-rag-comparison-final.jsonl
```

抽样结果：CMP-01 的 JSONL 中可直接看到：

- `metadata_filter`: `{"canonical_category": "beauty"}`
- `filter_summary`: `{"category": 5, "required_effect": 16}`
- `ranking_signals`: 防晒候选商品分别包含 `vector` / `facet` / `keyword` 等信号。

## Graph-aware Relation Score

目标：在不接重型图数据库的前提下，让检索不只是向量相似度，而是能显式利用商品和属性之间的结构化关系。

第一版实现：

1. 从 enriched 商品运行时派生轻量关系：
   - `graph_category:<canonical_category>`
   - `graph_sub_category:<sub_category>`
   - `graph_price_within_budget`
   - `graph_skin_type:<value>`
   - `graph_effect:<value>`
   - `graph_use_case:<value>`
   - `graph_soft_preference:<value>`
2. graph score 只作为 rerank 的小权重信号。
3. 硬约束仍由预算、排除项和子类过滤控制，不被 graph score 覆盖。
4. `RetrievalTrace.retrieval_channels.graph` 记录 graph hits；`ranking_signals.graph` 记录最终商品的 graph 信号。

抽样结果：CMP-01 的最终排序中可看到：

- `p_beauty_010`: `graph_category:beauty`、`graph_effect:防晒`
- `p_beauty_023`: `graph_category:beauty`、`graph_effect:防晒`
- `p_beauty_006`: `graph_category:beauty`、`graph_effect:防晒`

回归结果：

| Benchmark | Result |
| --- | --- |
| comparison queries | 3 / 3 PASS |
| golden queries | 8 / 8 PASS |
| beauty subcategory queries | 6 / 6 PASS |
| apparel queries | 5 / 5 PASS |
| conversation cases | 6 / 6 PASS |
| generation guardrails | PASS |

命令：

```bash
cd /Users/jia/Developer/bytedance-rag-shopping-agent
server/.venv/bin/python scripts/run_golden_queries.py --check-stream --require-vector
```

当前结果：

- 8 条 golden queries 均返回完整 SSE 形态。
- 当 Ark / Doubao 连接失败时，后端记录 warning，并返回基于召回商品卡片的安全兜底回答。
- 这不是最终真实模型效果评测，只证明 Android 端不会因为模型暂时不可用而卡死。

## Groundedness Benchmark 初跑

目标：把“回答不编造”拆成可回归 case，覆盖成分存在性、功效外推、约束过紧、多轮条件继承、过敏风险、有证据的无添加声明、商业承诺陷阱，以及 5-8 轮长对话。

新增 runner：

```bash
server/.venv/bin/python scripts/run_groundedness_cases.py --mock-llm
```

本地 mock 全链路结果：

| Mode | Result | Output |
| --- | --- | --- |
| retrieval + SSE generation + guardrail/fallback | 2 / 11 PASS | `/private/tmp/groundedness_cases_latest.jsonl` |
| retrieval-only | 7 / 11 PASS | `/private/tmp/groundedness_cases_retrieval_only_latest.jsonl` |

真实 Ark / Doubao 抽样：

```bash
server/.venv/bin/python scripts/run_groundedness_cases.py \
  --case-id GRD-03 \
  --case-id GRD-07 \
  --output /private/tmp/groundedness_cases_real_sample.jsonl
```

抽样结果：2 / 2 PASS。`GRD-07` 中真实模型先输出了库存、优惠、优惠券、下单相关内容，触发 generation guardrail；repair 后仍未通过，最终使用本地 grounded fallback，通过“不能补资料外商业信息”的检查。

初跑发现：

1. 检索层已经能通过短事实 case、商业承诺 case 和一条长卸妆油对话，但多轮上下文继承仍不稳。
2. 预算更新存在问题：`预算可以放宽到300` 和长对话里的预算变化没有稳定覆盖上一轮预算。该问题已在下方 rule-only conversation state merge 中先修复显式规则部分。
3. 产品角色继承存在问题：用户后续问“水杨酸 / 屏障 / 不过敏保证”时，系统会丢失上一轮核心商品。
4. mock / fallback 生成只能给出通用安全回答，不会细粒度引用 PITERA、烟酰胺、无香料无酒精等证据，因此 answer-level 检查大量失败。
5. Guardrail 对商业承诺有效，但对成分/功效 groundedness 还不是完整 judge。

## Conversation State Merge 回归

目标：把多轮对话里最容易丢的“硬约束状态”先做成规则基线，验证不依赖 LLM Planner 时能否稳定处理显式约束。

实现点：

1. 新增 `server/app/conversation_state.py`，在 `retrieve()` 前把 `history + current_message` 合并成结构化检索状态。
2. 最新明确预算覆盖旧预算，例如“预算可以放宽到300”会解析成 `budget_max=300`。
3. “先放宽预算 / 先不看预算”在没有新数字时才取消预算。
4. 排除条件默认继承，例如前文“不要酒精/刺激”不会在“更便宜一点”后丢失。
5. Debug 接口返回 `conversation_state` trace，记录 state merge 是否应用、预算/排除/类目/功效/场景和 actions。

新增 case：

```text
CQ-05: 5轮预算更新、取消预算和排除条件继承
```

覆盖路径：

1. 油皮 + 200元以内 + 通勤防晒 + 不要酒精/刺激。
2. 预算可以放宽到300。
3. 有没有更便宜一点的。
4. 我想把预算降到150元。
5. 先不看预算，但酒精刺激还是不要。

回归结果：

| Benchmark | Result | Output |
| --- | --- | --- |
| conversation cases | 6 / 6 PASS | `/private/tmp/bytedance-rag-conversation-product-ref.jsonl` |
| golden queries | 8 / 8 PASS | `/private/tmp/bytedance-rag-golden-rule-state.jsonl` |
| beauty subcategory queries | 6 / 6 PASS | `/private/tmp/bytedance-rag-subcategory-rule-state.jsonl` |
| apparel queries | 5 / 5 PASS | `/private/tmp/bytedance-rag-apparel-rule-state.jsonl` |
| comparison queries | 3 / 3 PASS | `/private/tmp/bytedance-rag-comparison-rule-state.jsonl` |
| generation guardrails | PASS | terminal output |

注意：这一步只解决显式规则能覆盖的多轮约束；商品卡指代已在下一节补上第一版。复杂抽象偏好和相似替代推荐仍是后续 LLM Planner / retrieval plan validator 的目标。

## Product Reference 回归

目标：让 Android 和后端都能看到上一轮商品卡片，先覆盖“第一款/它/这款”这类商品事实追问。

实现点：

1. `ChatMessage` 支持可选 `product_ids`。
2. Android 端在发送 history 时，会把 assistant 消息里的商品卡 `productId` 列表带回后端。
3. `conversation_state.py` 从最近一条 assistant history 中读取商品 id，并在“第一款/第二款/它/这款/刚才那款”等表达中解析指代。
4. `retrieval.py` 解析 `指代商品ID：p_xxx`，并将候选商品聚焦到该商品，避免重新按关键词召回一批无关商品。

新增 case：

```text
CQ-06: 商品卡指代：第一款追问应聚焦上一轮商品
```

回归结果：conversation benchmark 6 / 6 PASS。`CQ-06` 第二轮“第一款有没有酒精？”只返回上一轮第一款 `p_beauty_006`。

注意：这一步解决商品事实追问，不解决“找一个像刚才那款但更便宜”的替代推荐。替代推荐需要把上一轮商品属性转成相似商品检索条件，留给下一层 planner / similarity plan。

### 2026-06-03 Groundedness 复跑

本轮继续把 groundedness runner 对齐真实 Android 行为：assistant history 现在会记录上一轮商品卡片 `product_ids`，因此多轮 case 里的“它/第一款/这款”能被检索层复现。同时补了几个低成本解析洞：

1. `预算放到300` / `预算放至300` 可以解析为新的预算上限。
2. `还有/另外/最好/顺便` 等补充语会被视为多轮延续。
3. `香精` 进入排除项解析，但“资料明确不含香精”不会被误过滤。
4. 裸数字不再被误判为“第几款”，避免 `预算200以内` 被当成指代第二款。
5. 商品/品牌名第一版别名匹配已加入，例如 `欧莱雅`、`AIRism`、`DRY-EX`；明确商品事实追问时，检索会优先取被点名商品，不再被上一轮预算或子类过滤误杀。

复跑命令：

```bash
cd /Users/jia/Developer/bytedance-rag-shopping-agent
PYTHONDONTWRITEBYTECODE=1 server/.venv/bin/python scripts/run_groundedness_cases.py \
  --mock-llm \
  --retrieval-only \
  --output /private/tmp/groundedness_final_retrieval_only.jsonl
```

第一轮结果：

| Mode | Result | Output |
| --- | --- | --- |
| retrieval-only | 9 / 11 PASS | `/private/tmp/groundedness_final_retrieval_only.jsonl` |

已修复的关键 case：

- `GRD-L01` 现在 6 轮全部通过：预算继承/放宽/压低、酒精/香精/刺激排除继承，以及“如果选欧莱雅能不能保证不过敏”都能聚焦到 `p_beauty_006`。
- `GRD-L03` 继续通过：卸妆油、多轮无添加证据、用户评价边界和购买链接/优惠拒绝都能保持同一商品上下文。

当时剩余失败：

- `GRD-08` 和 `GRD-L02` 都围绕 `p_beauty_007`。当前 raw 数据中 `p_beauty_007` 价格为 `268`，但 benchmark 的来源证据和期望里把它写成 `89` 或 `200元以内/100元以内`可推荐，因此严格预算过滤下不应召回它。
- 这两条当前更像 benchmark-data 对齐问题，而不是应该通过代码绕过预算硬约束。下一步应先修正 `groundedness_cases.json` 的来源证据和期望，再决定是否补“相似替代推荐 / 预算放宽询问”的新 case。

### 2026-06-03 Benchmark 修正后复跑

修正内容：

1. `GRD-08` 将预算从 200 元修正为 300 元，并把可接受商品从单一 `p_beauty_007` 扩展为 `p_beauty_007` / `p_beauty_012`，因为两者都是 raw 数据支持的 300 元内敏感修护面霜候选。
2. `GRD-L02` 将“修护屏障面霜”轮次显式改成“预算放宽到300”，参考答案价格改为 raw 数据中的 `260` / `268`。
3. `conversation_state.py` 增加轻量意图切换规则：当前轮出现新子类并带有“更偏/有没有/改看”等切换语义时，`sub_category` 和 `effect` 用当前轮覆盖旧状态；预算、肤质、排除条件仍继承。

复跑命令：

```bash
cd /Users/jia/Developer/bytedance-rag-shopping-agent
PYTHONDONTWRITEBYTECODE=1 server/.venv/bin/python scripts/run_groundedness_cases.py \
  --mock-llm \
  --retrieval-only \
  --output /private/tmp/groundedness_after_case_and_state_correction_retrieval_only.jsonl
```

结果：

| Mode | Result | Output |
| --- | --- | --- |
| retrieval-only | 11 / 11 PASS | `/private/tmp/groundedness_after_case_and_state_correction_retrieval_only.jsonl` |

关键变化：

- `GRD-08` 现在能在 300 元内召回 `p_beauty_012` / `p_beauty_007`，第二轮“它孕妇也能用吗/能保证不过敏吗”继续聚焦上一轮修护面霜。
- `GRD-L02` 第 5 轮从控油精华切到修护面霜后，召回从旧的 `p_beauty_018` 转为 `p_beauty_012` / `p_beauty_007`，第 6 轮“这个面霜能不能顺便去闭口”也能继续聚焦面霜。

同步回归：

| Benchmark | Result | Output |
| --- | --- | --- |
| conversation cases | 6 / 6 PASS | `/private/tmp/bytedance-rag-conversation-after-groundedness-correction.jsonl` |
| golden queries | 8 / 8 PASS | `/private/tmp/bytedance-rag-golden-after-groundedness-correction.jsonl` |
| beauty subcategory queries | 6 / 6 PASS | `/private/tmp/bytedance-rag-subcategory-after-groundedness-correction.jsonl` |
| apparel queries | 5 / 5 PASS | `/private/tmp/bytedance-rag-apparel-after-groundedness-correction.jsonl` |
| comparison queries | 3 / 3 PASS | `/private/tmp/bytedance-rag-comparison-after-groundedness-correction.jsonl` |
| generation guardrails | PASS | terminal output |

下一步建议：

1. 再单独补“相似替代推荐”：当用户要 100/200 内修护面霜但没有满足商品时，系统应明确无结果，并询问是否放宽预算或改看修护面膜/精华。
2. 对真实 Doubao 长对话做抽样复验，继续沉淀 repair / fallback 的 failure cases。
3. 再把 `answer_must_contain` 从纯字符串检查逐步升级为更稳定的 claim-level judge。

### 2026-06-04 Evidence-aware fallback 复跑

本轮目标：把安全兜底从“泛泛保守回答”升级为“证据化保守回答”。当真实模型输出触发 guardrail，或本地 mock / API 失败走 fallback 时，回答会尽量引用当前商品卡可见的证据，而不是只说“资料不足”。

实现变化：

1. `retrieval.py` 中 `ProductCard.description` 不再只带营销文案，而是合并商品营销文案、官方 FAQ 和用户评价。
2. `guardrails.py` 中 `build_safe_answer` 改成 evidence-aware answer builder：
   - 会引用商品数据源价格、卖点、使用场景、适合人群和注意事项。
   - 对“是否有某成分”“能不能外推功效”“孕期/过敏是否保证安全”“是否有购买链接/优惠”等问题给出资料边界。
   - 支持有证据的无添加声明，例如官方 FAQ 明确写到不含酒精/香精；没有证据时只说资料未说明或不能确认。
3. `llm.py` 的 guardrail / mock fallback 会看到最近几轮用户问题，因此“只放宽预算，但仍保留酒精/刺激排除条件”这类多轮边界能进入兜底回答。

复跑命令：

```bash
cd /Users/jia/Developer/bytedance-rag-shopping-agent
server/.venv/bin/python scripts/check_generation_guardrails.py

PYTHONDONTWRITEBYTECODE=1 server/.venv/bin/python scripts/run_groundedness_cases.py \
  --mock-llm \
  --output /private/tmp/groundedness_evidence_fallback_mock_v3.jsonl

PYTHONDONTWRITEBYTECODE=1 server/.venv/bin/python scripts/run_groundedness_cases.py \
  --mock-llm \
  --retrieval-only \
  --output /private/tmp/groundedness_evidence_fallback_retrieval_only.jsonl
```

结果：

| Benchmark | Result | Output |
| --- | --- | --- |
| generation guardrails | PASS | terminal output |
| groundedness full mock generation | 11 / 11 PASS | `/private/tmp/groundedness_evidence_fallback_mock_v3.jsonl` |
| groundedness retrieval-only | 11 / 11 PASS | `/private/tmp/groundedness_evidence_fallback_retrieval_only.jsonl` |
| golden queries | 8 / 8 PASS | `/private/tmp/bytedance-rag-golden-evidence-fallback.jsonl` |
| conversation cases | 6 / 6 PASS | `/private/tmp/bytedance-rag-conversation-evidence-fallback.jsonl` |
| beauty subcategory queries | 6 / 6 PASS | `/private/tmp/bytedance-rag-subcategory-evidence-fallback.jsonl` |
| apparel queries | 5 / 5 PASS | 临时 in-process debug 检查 |
| comparison queries | 3 / 3 PASS | `/private/tmp/bytedance-rag-comparison-evidence-fallback.jsonl` |
| secret scan | PASS | 269 files checked |

关键变化：

- `GRD-07` 商业承诺陷阱现在会推荐 The Ordinary 的 59 元控油精华，但不会补库存、优惠券、现货、下单等资料外信息。
- `GRD-L01` 能在“预算放到 300”时明确：这轮只放宽预算，仍然保留酒精和刺激排除条件。
- `GRD-L02` 能把 The Ordinary 的烟酰胺/锌、非水杨酸、不能当刷酸，以及修护面霜不能保证去闭口区分开。
- `GRD-L03` 能区分芳珂卸妆油的官方无添加资料和用户评价里的孕期/不堵塞体验，不把用户反馈当成官方安全保证。

## 当前边界

1. Guardrail V1 是规则校验，不是完整 groundedness judge。
2. Evidence-aware fallback 能覆盖当前 benchmark 中的关键证据边界，但尚未对所有模型生成 claim 做细粒度证据匹配。
3. Android 端真实 Doubao 已完成第一轮复验；自动滚动已完成一轮模拟器复验，后续录屏前仍需做一次人工检查。
4. Chroma 当前已索引 30 条 enriched 商品，其中美妆 25 条、服饰 5 条；数码和食品仍未进入 enriched。

## 下一步

1. 设计用户反馈闭环的最小记录结构。
2. 把被 guardrail 拦截的真实输出继续沉淀为 failure cases。
3. 扩展多商品对比到更多品类和更复杂约束。
4. 进一步设计 groundedness judge，对功效声明做更细粒度证据校验。
