# 场景化组合推荐 Planner 实现记录

日期：2026-06-08

## 背景

真实 Android 复测中出现过一个典型失败：

> 下周去三亚度假，帮我搭配一套从防晒到穿搭的方案

最新 trace 显示，Planner 把这类需求收窄成了 `beauty + 防晒`：

```text
LLM Planner补充：
- 功效：防晒
- 场景：户外
- 子类：防晒
```

后续 metadata filter 和硬过滤继续执行这个窄意图，最终只召回美妆防晒商品。这个结果不符合官方进阶场景里的“场景化组合推荐”：用户要的是跨类目检索和组合编排，而不是单品类防晒推荐。

## 设计决策

这类判断不采用本地 rule-based 关键词覆盖。原因是“旅行、送礼、宿舍、早八、露营、通勤、从 A 到 B”这类表达开放度很高，靠规则容易越补越碎，也不利于展示 Agentic RAG 的结构化规划能力。

本次实现采用分层方案：

1. Planner 判断推荐形态，输出结构化 `recommendation_mode`。
2. Planner 在 `scene_bundle` 下输出 `search_slots`，每个 slot 表示一个检索意图槽。
3. Validator 只接受已有类目和 facet 枚举，不允许 Planner 生成商品事实、价格、库存或功效承诺。
4. Retrieval 只消费 Planner 补充后的结构化行，负责过滤、排序和跨类目选品。

核心原则：

- Planner 决定“这是单品类、对比、follow-up，还是场景组合”。
- Retrieval 不再用自然语言规则判断场景组合，只识别 Planner 补充的 `推荐模式：场景组合`。
- 离线 regression 可以注入模拟 Planner 补充，测试 retrieval 执行层；真实 Planner 质量用 `probe_planner.py` 单独验证。

## 实现内容

### Planner contract

`server/app/planner.py` 新增：

- `recommendation_mode`: `single_category | scene_bundle | comparison | followup | clarify | unknown`
- `PlannerSearchSlot`
  - `label`
  - `category`
  - `sub_categories`
  - `effects`
  - `use_cases`
- `search_slots: list[PlannerSearchSlot]`

Prompt 里新增规则：

- 用户只问明确品类或功效时用 `single_category`。
- 用户要“一套 / 方案 / 清单 / 组合 / 从 A 到 B / 某场景下搭配多个东西”时用 `scene_bundle`。
- `scene_bundle` 必须填写 `search_slots`。
- `search_slots` 是检索意图，不是商品事实。

三亚 case 的期望 Planner 计划大致为：

```json
{
  "recommendation_mode": "scene_bundle",
  "category_patch": {
    "mode": "add",
    "include": ["beauty", "apparel"]
  },
  "search_slots": [
    {
      "label": "三亚度假防晒防护",
      "category": "beauty",
      "sub_categories": ["防晒"],
      "effects": ["防晒"],
      "use_cases": ["户外"]
    },
    {
      "label": "三亚度假户外穿搭",
      "category": "apparel",
      "sub_categories": ["短袖T恤", "速干T恤", "运动短裤", "帽子", "背包"],
      "use_cases": ["户外"]
    }
  ]
}
```

### Validator

Validator 对 Planner 输出做约束：

- 类目必须在 `beauty / apparel / digital / food` 中。
- slot facet 必须来自 `FACET_LEXICON` 枚举。
- `scene_bundle` 没有有效 slot 时，不落地该模式。
- `facets_patch` 仍要求用户信号；但如果同一个枚举已经来自有效 `search_slots`，则允许作为场景组合的检索槽展开，不再报 `facet_without_user_signal` 噪声。

Validator 会把结构化 plan 转成 retrieval 可解析的补充行：

```text
- 推荐模式：场景组合
- 类目：美妆护肤、服饰运动
- 子类：防晒、短袖T恤、速干T恤、运动短裤、帽子、背包
- 功效：防晒
- 场景：户外
- 搜索槽：三亚度假防晒防护 | 类目=美妆护肤 | 子类=防晒 | 功效=防晒 | 场景=户外
- 搜索槽：三亚度假户外穿搭 | 类目=服饰运动 | 子类=短袖T恤,速干T恤,运动短裤,帽子,背包 | 场景=户外
```

### Retrieval execution

`server/app/retrieval.py` 新增执行层逻辑：

- `_planned_recommendation_mode()` 只读取 Planner 补充行。
- `_is_scene_bundle_query()` 只在 `推荐模式：场景组合` 时返回 true。
- `_select_scene_bundle_scored()` 在最终排序后先按 `category_candidates` 覆盖不同类目，再用子类多样性补齐结果。
- 对非美妆商品，`防晒` 不再作为硬 required effect 误杀服饰运动候选；例如帽子、背包可以因为户外穿搭 slot 被召回。

这让三亚 case 从“三张防晒”变成跨类目组合，例如：

```text
p_beauty_010  美妆护肤 / 防晒
p_clothes_025 服饰运动 / 背包
p_clothes_024 服饰运动 / 帽子
```

## 回归与验证

### 离线结构检查

```bash
python3 -m py_compile server/app/retrieval.py server/app/planner.py scripts/run_failure_regression_cases.py scripts/check_planner_contract.py scripts/probe_planner.py
server/.venv/bin/python scripts/check_planner_contract.py
server/.venv/bin/python scripts/run_failure_regression_cases.py
git diff --check
```

结果：

- Planner contract PASS
- failure regression 12/12 PASS
- 新增 `FR-012` PASS
- `git diff --check` PASS

### FR-012

新增 `data/eval/failure_regression_cases.json`:

- `FR-012`: 场景化组合推荐：三亚度假方案不能只召回美妆防晒
- 断言：
  - `expected_category_candidates = ["beauty", "apparel"]`
  - 至少 3 个商品
  - 至少 2 个不同商品类目
  - 商品类目必须包含 `美妆护肤` 和 `服饰运动`
  - 不允许出现 `食品饮料 / 数码电子`

`scripts/run_failure_regression_cases.py` 同步新增：

- `planner_additions` 注入，用于离线测试 Planner 成功后的 retrieval 执行层。
- `min_distinct_product_categories`
- `expected_product_categories_present`
- `expected_product_sub_categories_present`

### 真实 API Planner probe

新增 `scripts/probe_planner.py --case scene_bundle_sanya`。

真实 API 验证记录：

```text
PLANNER_TIMEOUT_SECONDS=30 server/.venv/bin/python scripts/probe_planner.py --case scene_bundle_sanya --repeat 1
```

结果：

```text
[PASS] scene_bundle_sanya round=1 latency_ms=12059 applied=True fallback=None
```

最新 validated plan：

```text
recommendation_mode = scene_bundle
category_patch.include = beauty, apparel
search_slots = 三亚度假防晒防护 + 三亚度假户外穿搭
validation_errors = []
```

随后用真实 Planner 生成的 retrieval message 跑检索，结果跨类目：

```text
p_beauty_010  美妆护肤 / 防晒
p_clothes_025 服饰运动 / 背包
p_clothes_024 服饰运动 / 帽子
```

## 2026-06-09 追加回归：快首屏绕过 Planner

真实 Android trace 中新增一个失败：

```text
能不能分别给我推荐一个防晒霜、一个帽子或者是防晒衣，然后再来个裤子？
```

trace 里 Planner 曾被首屏极速路径的短 deadline 截断：

```text
planner_trace.fallback_reason = planner_fast_first_screen_timeout
parsed_intent.category_candidates = ["beauty"]
products = p_beauty_010, p_beauty_006, p_beauty_023
```

这说明问题已经不是 Planner 语义判断错误，而是复杂跨类目请求没有等 Planner 生效，rule-only fallback 又把类目锁成 `beauty`，导致回答错误地说“暂无帽子、防晒衣、裤子资料”。

当前修正原则：

1. `chat_stream` 不再给 Planner 传首屏短 deadline，也不再为了首屏禁用向量检索；Planner 和 retrieval 都走完整主链路。
2. 首屏 deadline 只作用在 `quick_reply` 体验支线。主链路未及时返回时，先发送 `source=deadline_fallback` 的临时气泡，但不发送 rule-only 商品卡片。

新增回归：

- `FR-013`: 防晒霜 + 帽子/防晒衣 + 裤子，验证 retrieval 执行层必须同时返回美妆护肤和服饰运动。
- `probe_planner.py --case scene_bundle_sunscreen_hat_pants`: 真实 API 验证 Planner 能输出 `scene_bundle` 和 beauty/apparel 搜索槽。

真实 API 复测结果：

```text
[PASS] scene_bundle_sunscreen_hat_pants latency_ms=20282 applied=True fallback=None
recommendation_mode = scene_bundle
search_slots = 防晒霜推荐(beauty/防晒) + 防晒配饰推荐(apparel/帽子) + 裤子推荐(apparel/运动长裤,户外裤)
```

### 收尾复测观察项：物理防晒非化妆品

新增 `probe_planner.py --case physical_sunscreen_non_cosmetic`，记录 2026-06-09 trace 中的观察项：

```text
有没有什么？就是除了化妆品之外，比如说像防晒衣、防晒帽，嗯，就是物理防晒上的一些可以做的，就是推荐的东西。
```

这个 case 暂不作为离线 failure regression，因为当前讨论结论是：它主要暴露 Planner 超时后的降级路径偏窄，而不是主链路语义方案已经确认失败。最后收尾时用真实快速 API 复测：

```bash
PLANNER_TIMEOUT_SECONDS=30 server/.venv/bin/python scripts/probe_planner.py \
  --case physical_sunscreen_non_cosmetic \
  --repeat 1
```

期望不是继续补 keyword 规则，而是确认 Planner 能把“物理防晒 / 除了化妆品”落到 `apparel`，并产生帽子、速干T恤、户外裤、运动长裤或运动短裤等物理防护候选。

## 当前边界与风险

1. Planner 语义方向已验证，但真实 API 延迟有波动。
   - 一次 20 秒默认 timeout 下出现 `planner_timeout`。
   - 30 秒复测通过，实际耗时约 12.1 秒。
   - 不建议为了单个 case 直接把默认 timeout 加大；Android 体感慢时优先考虑 Router-gated Planner 或 speculative retrieval。

2. `search_slots` 目前用于扩展类目和 facet，不直接生成独立卡片组或套装 UI。
   - Android 仍展示普通商品卡。
   - 后续如果要做“方案分组卡”，可以复用 `search_slots` 作为 UI 分组来源。

3. Planner 仍不能生成商品事实。
   - slot 只能表达检索意图。
   - 最终推荐理由、价格、SKU、注意事项仍必须来自商品数据和 guardrail。

4. 当前回归把 Planner 与 retrieval 分层测试。
   - `FR-012` 通过 `planner_additions` 固定执行层。
   - `probe_planner.py` 单独验证真实 Planner 是否能输出正确结构。

## 答辩口径

这条实现可以作为“Agentic RAG / Planner 不只是加 prompt”的例子：

- 失败不是生成层胡说，而是检索计划把场景方案误压成单一防晒品类。
- 我们没有继续堆关键词规则，而是让 Planner 输出可校验的结构化 plan。
- Retrieval 只执行结构化计划，并通过 trace / regression 证明跨类目召回。
- 真实 API probe 证明 Planner 可以把“三亚度假从防晒到穿搭”拆成美妆防晒和服饰穿搭两个检索槽。
