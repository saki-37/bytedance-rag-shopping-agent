# 商品对比表格工作流调研与方案

日期：2026-06-06

## 背景

当前 Android 端已经支持基础 Markdown 渲染，包括标题、加粗、列表和简单表格。下一步希望在用户提出“对比一下这几个商品”“前两个帮我对比”“巴黎欧莱雅和安热沙怎么选”时，回答可以输出结构化对比表，方便用户快速扫价格、适合场景、风险和选择建议。

这个需求有两个核心难点：

1. 对比意图识别：用户可能显式说“对比”，也可能说“哪个更适合我”“这两个怎么选”。
2. 对比目标解析：用户可能指代上一轮商品，例如“这几个”“前两个”“第一款和第三款”，也可能点名品牌或商品名。

## 外部调研

### 购物助手产品形态

Amazon Rufus 是最接近的公开参考。Amazon 官方说明里，Rufus 会基于 Amazon 商品目录、评论、社区 Q&A 和 web 信息回答购物需求、商品问题和 comparison，并支持“trail vs road running shoes”“lip gloss vs lip oil”这类比较问题。官方也提醒生成式 AI 仍可能出错，需要持续改进。参考：[Amazon Rufus announcement](https://www.aboutamazon.com/news/retail/amazon-rufus?type=White+Papers%3Ftype%3DWebinars+and+Videos%3Ftype%3DWhite+Papers%3Ftype%3DWebinars+and+Videos%3Ftype%3DeBooks%3Ftype%3DWhite+Papers%3Ftype%3DWhite+Papers%3Ftype%3DeBooks%3F_rsc%3D11t7q)。

Shopify 生态里也有面向商家的 AI comparison 插件。CompareKit 的公开 FAQ 说明，它会分析店铺公开商品属性、描述、规格和价格，然后生成自然语言对比，帮助用户理解不同商品的优势和差异。参考：[CompareKit FAQ](https://comparekit.app/)。

这些产品资料证明“购物 AI 做商品对比”是合理产品方向，但它们没有公开足够细的后端实现。因此我们不应照抄产品形态，而应借鉴它们的共性：对比必须绑定商品资料、规格、价格和评价/QA 等证据源。

### 工程实践

OpenAI Structured Outputs 文档把结构化输出分成两类：需要连接应用工具/数据时使用 function calling；需要模型响应符合某个 UI schema 时使用 structured response format。它还明确区分 JSON mode 和 schema adherence：JSON mode 只保证 JSON 合法，Structured Outputs 才保证符合 schema。参考：[OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)。

Google Vertex AI 的 structured output 文档也强调，response schema 用于让下游任务稳定拿到合法 JSON；同时提醒 schema 会计入输入 token，且只支持部分字段。参考：[Google structured output](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/capabilities/control-generated-output)。

Anthropic Claude 文档把 structured outputs 用于获得可解析、符合 schema 的 JSON，并说明它可以和 strict tool use 配合；同时也列出 JSON Schema 限制和与部分能力的兼容边界。参考：[Claude structured outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs)。

研究侧，JSONSchemaBench 指出结构化输出已经成为现代 LLM 应用的关键能力，但真实 schema 下仍需要评估效率、覆盖范围和输出质量。参考：[JSONSchemaBench](https://arxiv.org/abs/2501.10868)。

## 调研结论

我们可以采用以下判断：

- 产品层面：商品对比表是合理加分项，已有购物助手和电商插件在做类似体验。
- 工程层面：Planner 适合产出结构化意图，不适合直接生成商品事实或表格内容。
- 正确性层面：表格内容必须由回答 LLM 基于 `context` 和 `ProductCard` 生成，并继续接受 guardrail 校验。
- UI 层面：MVP 可以先输出 Markdown 表格，因为 Android 已能渲染；后续如果体验不够，再升级为结构化 `comparison` 事件或原生对比卡。

## 推荐方案

采用“Planner 识别对比意图 + 后端校验目标商品 + LLM 输出 Markdown 表格”的分层方案。

### 1. Planner 输出 comparison plan

在 `RetrievalPlan` 中新增可选字段：

```json
{
  "comparison_plan": {
    "enabled": true,
    "target_policy": "latest_all_products",
    "target_product_ids": [],
    "target_indexes": [],
    "focus_dimensions": ["price", "skin_type", "use_case", "cautions"],
    "output_format": "markdown_table",
    "needs_clarification": false,
    "clarification_question": null
  }
}
```

字段含义：

- `enabled`：当前轮是否要求对比。
- `target_policy`：目标商品来源，例如 `latest_all_products`、`latest_first_n`、`mentioned_product_ids`、`unknown`。
- `target_product_ids`：Planner 能安全确认的商品 ID；一般只接受历史中出现过的 ID。
- `target_indexes`：用户说“第一款/前两个”时的 index。
- `focus_dimensions`：用户关注的比较维度，例如价格、油皮、通勤、补涂、注意事项。
- `output_format`：MVP 固定为 `markdown_table`。

Planner 的边界：

- 不生成商品事实。
- 不生成价格、功效、库存、优惠。
- 不猜商品 ID。
- 如果目标商品不明确，输出 `unknown` 或 `needs_clarification=true`。

### 2. 后端解析并校验指代

后端根据历史 assistant message 的 `product_ids` 做二次校验：

- “这几个都对比一下” -> 上一轮全部 `product_ids`。
- “前两个对比一下” -> 上一轮前两个 `product_ids`。
- “第一款和第三款” -> 上一轮第 1 和第 3 个。
- “这款和第二款” -> 如果“这款”指代不清，优先追问。
- “巴黎欧莱雅和安热沙” -> 可以在上一轮商品标题/品牌中做精确或弱匹配；匹配不到就追问。
- “比较一下巴黎欧莱雅和安耐晒” -> 如果上一轮或当前召回候选中能唯一匹配这两个品牌/商品名，则按匹配到的商品对比；如果一个品牌对应多个候选，必须追问用户确认具体哪一款。

校验失败时，不进入表格生成，而是返回追问：

> 你想对比哪几款？可以说“前两款”或直接点名品牌/商品名。

### 3. Retrieval 保持目标商品集合

对比场景里，目标商品是硬约束：

- 如果目标来自上一轮商品卡，优先保留这些商品。
- 不应重新召回一批无关商品。
- 输出顺序应跟用户指代顺序一致。

如果用户同时给新条件，例如“前两个按油皮通勤对比”，则新条件进入 `focus_dimensions` 和生成指令，而不是把目标商品替换掉。

### 4. Generation 接收 answer directive

给 `stream_answer` 增加可选 `answer_directive`：

```json
{
  "mode": "compare",
  "output_format": "markdown_table",
  "target_product_ids": ["p_beauty_006", "p_beauty_007"],
  "focus_dimensions": ["价格", "适合肤质", "通勤场景", "补涂方便度", "注意事项"]
}
```

Prompt 增加规则：

- 如果 `mode=compare`，先输出 Markdown 表格。
- 表格列优先使用 `focus_dimensions`；缺省列为：商品、价格、适合人群/肤质、核心优点、注意事项、选择建议。
- 表格单元格只能使用商品资料和 `ProductCard` 字段。
- 不确定的单元格写“资料未明确”。
- 价格只能使用 `ProductCard.price` 或 `variants.price`。
- 表格后输出 1-2 句保守选择建议。

### 5. Guardrail 继续兜底

当前价格、库存、优惠、链接和未授权功效校验应继续保留。对表格场景可以追加：

- 表格里出现的价格必须属于允许价格集合。
- 表格里出现的商品名/品牌必须来自 selected cards。
- `资料未明确` 是允许输出，不算失败。
- 不允许在表格里写“无酒精/不会过敏/不会闷痘”等资料未支持的保证。

### 6. 商品卡片位置

对比回答里不建议把完整 `ProductCard` 塞进 Markdown 表格单元格：

- 表格的核心任务是横向扫描差异；完整卡片会让单元格高度暴涨，破坏表格可读性。
- 商品卡的核心任务是承载图片、标签和详情入口；它更适合作为表格之外的点击目标。
- 移动端横向滚动表格已经占用较多注意力，如果表格内部再放卡片，用户会很难判断是读表格还是点卡片。

推荐分阶段处理：

1. MVP：先输出 Markdown 对比表；对比所涉及的商品卡统一展示在表格之后，作为“查看详情”的入口。这样不会打断表格结构，也复用当前商品卡能力。
2. 下一阶段：如果要更强的对比 UI，可以新增原生 `ComparisonTableCard`，在表格上方做一个紧凑的“对比商品条”：小图、品牌/短标题、价格、详情入口。表格主体只保留文字化属性差异。
3. 不推荐：在每个表格单元格内嵌完整商品卡，或者在表格每一行后插入商品卡。这会让对比阅读变得断裂。

外部参考也支持这个方向：Baymard 把 comparison tool 描述为用户选择商品后进入 side-by-side specification comparison；CompareKit 也强调基于商品属性、描述、规格和价格生成对比，而不是把完整商品详情卡塞进表格。也就是说，表格应承载规格差异，商品入口应作为独立的导航/详情组件。

## MVP 实现范围

第一阶段只做上一轮商品卡的对比：

1. 支持“这几个/它们/前两个/第一和第二/第一款和第三款”。
2. 支持用户点名品牌/商品名，例如“巴黎欧莱雅和安热沙对比一下”；能唯一匹配时进入对比，不能唯一匹配时追问。
3. 支持 Planner 输出 `comparison_plan`。
4. 后端校验上一轮 `product_ids` 并生成 `answer_directive`。
5. 回答 LLM 输出 Markdown 表格。
6. Android 用当前 Markdown table renderer 展示，并将对比商品卡放在表格之后作为详情入口。

暂不做：

- 跨多轮复杂消歧。
- 新商品名搜索 + 对比的混合流程。
- 原生 Android 对比卡。
- 完整结构化 `comparison` SSE event。

## 验收标准

- 用户说“把刚才这几个对比一下”，回答中出现 Markdown 表格。
- 用户说“前两个对比一下，重点看油皮通勤”，表格只比较上一轮前两个商品，并包含油皮/通勤相关列或内容。
- 用户说“第一款和第三款怎么选”，表格按对应顺序展示两个商品。
- 用户说“比较一下巴黎欧莱雅和安热沙”，如果上一轮或当前候选中能唯一匹配两个商品，表格只比较这两个商品。
- 用户点名的品牌/商品名无法唯一匹配时，后端应追问具体哪一款，而不是猜测或扩大召回。
- 如果上一轮没有商品卡，用户说“这几个对比一下”，后端应追问而不是编造。
- 表格价格全部来自 `ProductCard` 或 `variants`。
- 商品卡不插入表格内部；MVP 中商品卡展示在对比表之后，作为详情入口。
- Android 能显示标题、加粗、列表和横向滚动表格。

## 后续增强

- 如果 Markdown 表格视觉不够稳定，新增结构化 SSE 事件：

```json
{
  "event": "comparison",
  "data": {
    "columns": ["商品", "价格", "适合肤质", "注意事项"],
    "rows": [
      {"product_id": "p_beauty_006", "cells": ["巴黎欧莱雅", "¥170", "油皮/通勤", "需补涂"]},
      {"product_id": "p_beauty_007", "cells": ["安热沙", "¥118", "资料未明确", "敏感肌先测试"]}
    ]
  }
}
```

- Android 再渲染为原生 `ComparisonTableCard`。
- 增加 SKU 级对比，例如“30ml 和 40ml 怎么选”。
- 在 eval case 中加入 compare 场景，验证指代、目标商品、价格 groundedness 和表格格式。
