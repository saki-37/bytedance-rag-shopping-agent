# 电商 Schema 外部参考调研

日期：2026-05-28

用途：整理 Amazon、Google Merchant Center、Schema.org、淘宝开放平台和电商属性抽取研究对本项目多品类 schema 的启发。本文不是字段照搬清单，而是用于校准 V2 多品类 enriched schema、后续属性抽取和 RAG 证据链设计。

## 结论先行

大型电商平台的字段体系主要服务三件事：

1. 商品上架合规：商品属于哪个类目、哪些属性必填、哪些属性可枚举或可自定义。
2. 搜索与展示：标题、描述、图片、价格、品牌、材质、尺码、规格、商品亮点等。
3. 变体与 SKU 管理：颜色、尺码、容量、版本等变体维度，以及父子商品关系。

我们的智能导购不能只照搬这些字段。平台字段回答的是“这是什么商品”，而本项目还要回答“它适合谁、为什么适合、有什么限制、依据来自哪里”。因此更适合采用三层结构：

| 层级 | 作用 | 来自外部平台的启发 | 本项目字段位置 |
| --- | --- | --- | --- |
| 商品事实层 | 稳定事实、上架信息、规格和 SKU | Amazon product type、Google product feed、Schema.org Product/Offer、淘宝类目属性 | raw + `variants` + `attributes.specifications` |
| 导购决策层 | 适合/不适合、场景、偏好、风险、注意事项 | Google product_highlight / product_detail / Q&A，平台评价和 FAQ | `attributes` + `category_attributes` + `display` |
| RAG 证据层 | 检索、trace、guardrail、反幻觉 | 类目必填属性、属性来源、可枚举/可输入边界 | `retrieval` + `source.attribute_provenance` + `graph` |

最重要的设计原则：

1. **类目专属字段要保留**：不同品类的关键字段完全不同，用统一大表会很快变得含混。
2. **变体维度要显式化**：颜色、尺码、容量、版本等不应只埋在 raw `skus` 里，否则后续对比和详情页会很难做。
3. **属性来源要显式化**：RAG 项目最怕模型把“资料未说明”说成“没有”。每个容易影响推荐的字段，都应该能回到 raw/enriched 证据。
4. **导购字段不能只等于平台字段**：`suitable_for`、`avoid_for`、`cautions`、`decision_factors` 是导购系统自己的价值，不是普通商品 feed 的标配。

## 外部参考

### Amazon Product Type Definitions

Amazon Selling Partner API 的 Product Type Definitions 用 JSON Schema 描述不同商品类型的属性要求，并支持按 marketplace、seller 类型和商品名检索/推荐商品类型。

对本项目的启发：

1. 多品类 schema 应该是“通用外壳 + 类目专属字段”，而不是把所有字段摊平成一个巨大的对象。
2. `canonical_category` 可以类比 product type；`category_attributes` 可以类比某个 product type 的字段集合。
3. 变体商品需要关注 parent/child 或 variant family。我们不需要完整实现 Amazon 式上架逻辑，但应该在 enriched 层保留 `variants.variant_dimensions`。

参考：

- Amazon Product Type Definitions API: https://developer-docs.amazon.com/sp-api/lang-en_EN/docs/product-type-definitions-api
- Amazon Product Type Definitions API reference: https://developer-docs.amazon.com/sp-api/docs/product-type-definitions-api-v2020-09-01-reference

### Google Merchant Center Product Data Specification

Google Merchant Center 的 product data specification 更像商品 feed 标准，覆盖商品标题、描述、链接、图片、价格、品牌、材质、尺寸、商品细节、商品亮点、问答、变体选项等字段。

对本项目的启发：

1. `product_detail` 的 section/name/value 结构非常适合抽象成本项目的 `attributes.specifications`，用于数码参数、服饰材质、食品规格等。
2. `product_highlight` 提醒我们：商品卡片亮点应该短、稳定、只描述商品本身，不能塞促销话术或无证据承诺。
3. `question_and_answer` 与官方 FAQ 对应，可以作为 RAG 证据来源；但生成时要避免重复、夸大或把问答当成绝对事实。
4. `variant option` 说明颜色、尺码、容量等变体维度需要显式保存，方便后续详情页和对比。

参考：

- Google Merchant Center Product data specification: https://support.google.com/merchants/answer/7052112/product-data-specification
- Google Merchant API Attributes reference: https://developers.google.com/merchant/api/reference/rest/products_v1beta/Attributes

### Schema.org Product / Offer

Schema.org 的 Product / Offer 模型强调商品标识、品牌、类目、材质、尺寸、SKU、GTIN、报价、评价、正负面说明和相似/相关商品关系。

对本项目的启发：

1. `additionalProperty` 可以承载 schema 没有覆盖的自定义属性；这和我们 `category_attributes` 的思路一致。
2. `positiveNotes` / `negativeNotes` 对应本项目的 `selling_points`、`quality_risks`、`cautions`。
3. `isSimilarTo` / `isRelatedTo` / `isVariantOf` 对后续 graph-aware retrieval 有启发，可转成轻量 relation，而不必接重型图数据库。
4. Schema.org 区分 Product 和 Offer，提醒我们价格、库存、优惠属于交易/报价层，不能让模型自由生成。

参考：

- Schema.org Product: https://schema.org/Product
- Schema.org Offer: https://schema.org/Offer

### 淘宝开放平台商品属性

淘宝开放平台的商品 API 文档体现了中文电商平台常见的类目属性设计：属性可能是销售属性、颜色属性、枚举属性，也可能允许卖家输入。商品发布需要围绕叶子类目、关键属性、销售属性和自定义属性组织。

对本项目的启发：

1. 中文电商里的“类目属性”不只是展示字段，也会影响商品是否能被正确归类和筛选。
2. `retrieval.hard_filter_facets` 可以吸收“销售属性/关键属性”的思想，例如尺码、颜色、材质、容量、口味。
3. `retrieval.soft_preference_facets` 可以吸收“可输入属性”的思想，例如通勤、轻薄、清爽、适合新手等更自然语言化的偏好。
4. 对于枚举字段，要尽量标准化；对于自由输入字段，要保留原文证据，避免过度归一化。

参考：

- 淘宝开放平台 商品类目属性 API: https://open.alitrip.com/docs/api.htm?apiId=121

### 电商属性抽取研究

电商商品属性并不总是完整结构化的。OpenTag、OA-Mine 等工作都在处理从标题、描述、profile 中抽取属性值，尤其是开放世界或低标注场景下的新属性发现问题。

对本项目的启发：

1. 当前 100 条数据规模小，先手工增强是合理的；不需要为了比赛第一版引入复杂属性抽取模型。
2. 后续可以做“LLM 辅助标注 + 人工确认”，把字段来源标成 `llm_assisted` / `manual_verified`。
3. 对新类目扩展，不要假设所有属性事先都知道；可以保留 `attributes.specifications` 和 `source.attribute_provenance` 做开放扩展。

参考：

- OA-Mine: Open-World Attribute Mining for E-Commerce Products with Weak Supervision: https://arxiv.org/abs/2204.13874
- OpenTag: Open Attribute Value Extraction from Product Profiles: https://arxiv.org/abs/1806.01264

## 对本项目 Schema 的直接调整

本次调研后，建议在 `docs/15_multicategory_schema.md` 中吸收三个字段设计：

### 1. `variants`

用于从 raw `skus` 中抽取用户可理解的变体维度。

```json
{
  "variants": {
    "variant_dimensions": [
      {"name": "颜色", "values": ["白色", "黑色"], "affects": ["image", "sku"]},
      {"name": "尺码", "values": ["S", "M", "L"], "affects": ["fit", "sku"]}
    ],
    "raw_sku_summary": "颜色含白色/黑色，尺码含 S/M/L。"
  }
}
```

边界：

1. MVP 不展开成独立 SKU 商品。
2. 如果价格因 SKU 不同而变化，优先展示 raw `base_price`，详情页说明“具体 SKU 价格以数据源为准”。
3. 不从变体字段推断库存。

### 2. `attributes.specifications`

用于保存 section/name/value 形式的商品细节，适合数码参数、服饰材质、食品包装规格。

```json
{
  "attributes": {
    "specifications": [
      {"section": "材质", "name": "面料", "value": "AIRism 混纺棉"},
      {"section": "尺码", "name": "覆盖", "value": "S/M/L"}
    ]
  }
}
```

边界：

1. 只放商品事实，不放导购结论。
2. 导购结论仍放在 `suitable_for`、`avoid_for`、`cautions`、`decision_factors`。

### 3. `source.attribute_provenance`

用于记录字段来自哪里，支持 trace 和 guardrail。

```json
{
  "source": {
    "source_docs": ["raw.rag_knowledge.marketing_description", "raw.rag_knowledge.official_faq"],
    "attribute_provenance": [
      {
        "field": "category_attributes.apparel.materials",
        "source_path": "raw.rag_knowledge.marketing_description",
        "evidence": "AIRism 混纺棉",
        "confidence": "explicit"
      }
    ]
  }
}
```

`confidence` 建议先用三档：

| 值 | 含义 | 能否用于硬约束 |
| --- | --- | --- |
| `explicit` | raw 或人工增强中明确写出 | 可以 |
| `inferred` | 根据上下文合理推断 | 谨慎使用，只做排序 |
| `unknown` | 数据未说明 | 不能当作否定事实 |

## V2-B 落地建议

下一步做 5 条服饰运动 enriched 样例时，建议按这个顺序：

1. 先从 raw `skus` 抽 `variants.variant_dimensions`。
2. 再把商品事实写入 `attributes.specifications`。
3. 再写导购字段：`suitable_for`、`avoid_for`、`cautions`、`decision_factors`。
4. 最后补 `source.attribute_provenance`，至少覆盖硬约束字段：材质、尺码、运动场景、防水、容量、价格。
5. 每条样例保留 2-3 个 `search_aliases`，例如“白 T”“速干衣”“徒步鞋”“通勤背包”。

这样做的好处是：先保证商品事实稳，再做导购解释；后续即使不用图数据库，也能在 trace 里说明“这个推荐命中了哪些字段、哪些字段来自哪里”。
