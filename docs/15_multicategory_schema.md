# 多品类 Enriched Schema 设计

日期：2026-05-28

用途：定义 V2 多品类扩展的数据结构，让系统从“美妆垂类 RAG”自然扩展到“可解释的多类目电商导购”。本页是后续第二品类样例、graph-aware retrieval、多商品对比和反馈闭环的共同地基。

外部字段体系调研见 [电商 Schema 外部参考调研](16_ecommerce_schema_references.md)。本页只保留会进入项目 schema 的设计结论。

## 设计目标

1. 保留官方 raw 数据，不改写原始 JSON。
2. 每条 enriched 记录通过 `raw_product_id` 回连 raw 商品。
3. 通用字段服务所有品类，品类专属字段只在对应品类出现。
4. 商品卡片、详情页、检索、trace 和生成 prompt 使用同一份结构化事实。
5. 支持从 25 条美妆扩展到 100 条全品类，但不要求一次性标完 75 条非美妆。

## 非目标

1. 不在 V2-A 阶段引入数据库迁移。
2. 不接 Neo4j 或重型 GraphRAG 框架。
3. 不把所有 SKU 展开成独立商品；SKU 仍保留在 raw 层，必要字段抽象到 enriched 层。
4. 不要求每个字段都完全填满；字段为空时不能被模型当作否定事实。

## Enriched 记录结构

建议从 V2 开始统一使用一条 JSONL 记录对应一个 raw 商品：

```json
{
  "schema_version": "2.0",
  "raw_product_id": "p_clothes_001",
  "canonical_category": "apparel",
  "source": {
    "source_docs": [],
    "attribute_provenance": []
  },
  "variants": {
    "variant_dimensions": [],
    "raw_sku_summary": ""
  },
  "display": {
    "card_reason": "适合夏季通勤和轻运动的凉感棉质 T 恤，价格低，尺码覆盖 S-L。",
    "detail_highlights": [],
    "detail_cautions": []
  },
  "attributes": {},
  "category_attributes": {},
  "retrieval": {},
  "graph": {}
}
```

字段说明：

| 字段 | 作用 | 是否必填 |
| --- | --- | --- |
| `schema_version` | 标记 enriched schema 版本，方便后续迁移 | 是 |
| `raw_product_id` | 回连官方 raw 商品 | 是 |
| `canonical_category` | 统一内部类目：`beauty` / `digital` / `apparel` / `food` | 是 |
| `source` | 字段来源、证据片段和置信度，用于 trace / guardrail | 是 |
| `variants` | 从 raw `skus` 抽取的用户可理解变体维度 | 是 |
| `display` | 卡片、详情、Demo 直接使用的短文本 | 是 |
| `attributes` | 跨品类通用属性 | 是 |
| `category_attributes` | 品类专属属性 | 是 |
| `retrieval` | 检索、rerank、guardrail 使用的结构化信息 | 是 |
| `graph` | 轻量属性图节点和边，可由 attributes 派生，也可显式保存 | 可选 |

## 通用字段

`attributes` 保存跨品类都能理解的导购维度：

```json
{
  "attributes": {
    "target_users": [],
    "use_cases": [],
    "selling_points": [],
    "cautions": [],
    "avoid_for": [],
    "suitable_for": [],
    "tags": [],
    "decision_factors": [],
    "quality_risks": [],
    "care_or_usage_notes": [],
    "specifications": []
  }
}
```

字段用途：

| 字段 | 含义 | 进入卡片 | 进入检索 | 进入 trace | 进入生成 prompt |
| --- | --- | --- | --- | --- | --- |
| `target_users` | 目标用户，例如学生党、通勤人群、户外人群 | 可选 | 是 | 是 | 是 |
| `use_cases` | 使用场景，例如通勤、训练、旅行、早餐 | 可选 | 是 | 是 | 是 |
| `selling_points` | 可证据支持的卖点 | 可选 | 是 | 是 | 是 |
| `cautions` | 使用注意事项 | 详情页 | 是 | 是 | 是 |
| `avoid_for` | 不适合人群或场景 | 详情页 | 是 | 是 | 是 |
| `suitable_for` | 适合人群或场景 | 卡片/详情 | 是 | 是 | 是 |
| `tags` | 简短标签，适合卡片展示 | 卡片 | 是 | 是 | 是 |
| `decision_factors` | 用于对比的核心因素 | 详情/对比 | 是 | 是 | 是 |
| `quality_risks` | 用户评价或 FAQ 暴露的风险 | 详情/对比 | 是 | 是 | 是 |
| `care_or_usage_notes` | 洗护、保存、使用方式 | 详情 | 是 | 是 | 是 |
| `specifications` | section/name/value 形式的商品事实，例如材质、屏幕、容量、包装 | 详情 | 是 | 是 | 是 |

约定：

1. `cautions` 表示“需要注意”，不是绝对禁忌。
2. `avoid_for` 只有在 raw 文本有明确依据时填写。
3. `tags` 应短而稳定，优先用于商品卡片。
4. 不要把“没有提到酒精/糖/防水”等写成 `无酒精` / `无糖` / `防水`，除非 raw 数据明确支持。

`specifications` 建议使用统一形状：

```json
{
  "specifications": [
    {"section": "材质", "name": "面料", "value": "AIRism 混纺棉"},
    {"section": "尺码", "name": "覆盖", "value": "S/M/L"}
  ]
}
```

`specifications` 只放商品事实，不放“适合谁”这类导购结论。导购结论仍放在 `suitable_for`、`avoid_for`、`cautions` 和 `decision_factors`。

## 来源与证据字段

`source` 保存字段来自哪里，避免模型把“资料未说明”说成“没有”：

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

`confidence` 第一版使用三档：

| 值 | 含义 | 检索/生成边界 |
| --- | --- | --- |
| `explicit` | raw 或人工增强中明确写出 | 可用于硬约束、卡片和生成 |
| `inferred` | 根据上下文合理推断 | 只做软排序，生成时需谨慎表达 |
| `unknown` | 数据未说明 | 不能当作否定事实 |

约定：

1. 所有影响硬过滤的字段都应该有 `attribute_provenance`。
2. 生成 prompt 优先引用 `explicit` 证据。
3. guardrail 遇到 `unknown` 时只能表达“资料中未说明”，不能表达“没有”。

## 变体字段

`variants` 从 raw `skus` 中抽取用户可理解的变体维度：

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

约定：

1. MVP 不把每个 SKU 展开成独立商品。
2. 如果 SKU 价格不同，卡片仍展示 raw `base_price`，详情页说明具体 SKU 以数据源为准。
3. 不从变体字段推断库存；库存、优惠、下单承诺都不能由模型生成。

## 展示字段

`display` 保存给前端直接使用的短文本：

```json
{
  "display": {
    "card_reason": "",
    "detail_highlights": [],
    "detail_cautions": [],
    "comparison_summary": ""
  }
}
```

约定：

1. `card_reason` 控制在 1-2 句，适合卡片显示。
2. `detail_highlights` 放结构化亮点，来源必须能回到 raw/enriched。
3. `detail_cautions` 放注意事项，不做医疗、健康或安全承诺。
4. `comparison_summary` 可选，用于多商品对比时快速说明该商品适合谁。

## 检索字段

`retrieval` 是 V2 检索和 trace 的桥：

```json
{
  "retrieval": {
    "hard_filter_facets": [],
    "soft_preference_facets": [],
    "negative_facets": [],
    "search_aliases": [],
    "evidence_fields": []
  }
}
```

字段说明：

| 字段 | 用途 |
| --- | --- |
| `hard_filter_facets` | 可作为硬约束或强约束的属性，例如类目、子类目、价格桶、尺码、材质 |
| `soft_preference_facets` | 可作为排序偏好的属性，例如清爽、轻量、百搭、适合新手 |
| `negative_facets` | 明确不适合或风险因素，例如易起球、咖啡因、糖分高、厚重 |
| `search_aliases` | 用户可能使用的别名，例如“白 T”“速干衣”“通勤包” |
| `evidence_fields` | 生成 prompt 应引用的字段名或证据片段 |

## Graph 字段

V2-C 不接重型图数据库，先用本地轻量属性图：

```json
{
  "graph": {
    "nodes": [
      {"type": "product", "id": "p_clothes_001"},
      {"type": "category", "id": "apparel"},
      {"type": "material", "id": "AIRism混纺棉"}
    ],
    "edges": [
      {"from": "p_clothes_001", "relation": "belongs_to", "to": "apparel"},
      {"from": "p_clothes_001", "relation": "has_material", "to": "AIRism混纺棉"}
    ]
  }
}
```

第一版可以不显式保存 `graph`，而是由 `canonical_category`、`attributes` 和 `category_attributes` 运行时派生。只要 `RetrievalTrace` 最终能展示 graph relation 命中即可。

## 品类专属字段

### Beauty

沿用当前美妆字段，但纳入统一 `category_attributes`：

```json
{
  "category_attributes": {
    "beauty": {
      "skin_types": [],
      "skin_concerns": [],
      "product_effects": [],
      "key_ingredients": [],
      "texture": "",
      "spf": "",
      "pa": "",
      "makeup_compatibility": "",
      "sensitive_skin_note": "",
      "avoid_conditions": []
    }
  }
}
```

主要 query：

1. 油皮 200 元以内通勤防晒。
2. 敏感肌修护面霜。
3. 不要酒精/刺激感强。
4. 控油底妆或定妆。
5. 两款防晒怎么选。

### Digital

```json
{
  "category_attributes": {
    "digital": {
      "device_type": "",
      "usage_scenarios": [],
      "performance_level": "",
      "processor": "",
      "memory_options": [],
      "storage_options": [],
      "screen_features": [],
      "battery_level": "",
      "charging_features": [],
      "camera_features": [],
      "portability": "",
      "ecosystem": [],
      "connectivity": [],
      "compatibility_notes": [],
      "avoid_conditions": []
    }
  }
}
```

主要 query：

1. 预算 5000 内，适合学生做笔记和看网课的平板。
2. 想要轻薄办公笔记本，不打游戏，续航要稳。
3. 拍视频和剪辑比较多，手机存储怎么选。
4. 不想要太重的电脑，通勤背包里要轻一点。

注意：

1. raw 数据中存在模拟未来型号，答辩时需说明数据为比赛脱敏/模拟数据。
2. 数码参数容易诱发模型编造，需要 guardrail 要求“只说数据中出现的参数”。

### Apparel

```json
{
  "category_attributes": {
    "apparel": {
      "item_type": "",
      "materials": [],
      "material_notes": [],
      "fit": "",
      "size_range": [],
      "size_notes": [],
      "colors": [],
      "season": [],
      "style": [],
      "sport_scenarios": [],
      "weather_conditions": [],
      "breathability": "",
      "warmth_level": "",
      "support_level": "",
      "waterproof_level": "",
      "durability_notes": [],
      "care_instructions": [],
      "avoid_conditions": []
    }
  }
}
```

主要 query：

1. 100 元以内，夏天通勤穿，不想太闷的 T 恤。
2. 想要纯棉或棉感，但出汗后别太黏。
3. 跑步训练用，想要速干透气的短袖。
4. 徒步鞋要防水、抓地，预算 1200 内。
5. 180cm 男生，担心衣长压个子，怎么选尺码。

为什么第二品类建议选 apparel：

1. 材质、尺码、运动场景和天气条件都非常适合做结构化约束。
2. 和美妆的肤质/成分逻辑差异明显，能证明系统不是写死美妆规则。
3. 主办方提到的“纯棉”等字段可以自然落到这个品类。
4. 前端卡片无需大改，仍展示品牌、标题、价格、标签和推荐理由即可。

### Food

```json
{
  "category_attributes": {
    "food": {
      "food_type": "",
      "flavors": [],
      "flavor_profile": [],
      "sugar_level": "",
      "caffeine": "",
      "package_type": "",
      "count_or_weight": "",
      "eating_scenarios": [],
      "storage_notes": [],
      "dietary_preferences": [],
      "allergens": [],
      "ingredient_highlights": [],
      "health_claim_cautions": [],
      "avoid_conditions": []
    }
  }
}
```

主要 query：

1. 早八提神，想要便携咖啡，不要太甜。
2. 想要办公室下午茶零食，预算 100 内。
3. 不喝含糖饮料，有什么低糖选择。
4. 送人礼盒装咖啡怎么选。

注意：

1. 食品健康声明需要谨慎，不能把普通商品说成治疗或减肥效果。
2. 糖分、咖啡因、过敏原只有 raw 明确提到时才能确定表达。

## QueryIntent 多品类扩展

V2 的 `QueryIntent` 需要从美妆字段扩展为：

```json
{
  "category_candidates": [
    {"category": "apparel", "confidence": 0.82},
    {"category": "beauty", "confidence": 0.21}
  ],
  "universal_constraints": {
    "budget_max": 200,
    "budget_min": null,
    "brand_include": [],
    "brand_exclude": [],
    "sub_category_include": [],
    "sub_category_exclude": []
  },
  "global_facets": {
    "target_users": [],
    "use_cases": [],
    "materials": [],
    "colors": [],
    "size": [],
    "exclude_terms": []
  },
  "category_facets": {
    "apparel": {
      "materials": ["棉感"],
      "sport_scenarios": ["跑步"],
      "weather_conditions": ["夏天"],
      "fit": ["宽松"]
    }
  },
  "needs_clarification": false,
  "clarification_reason": "",
  "confidence": 0.82
}
```

处理规则：

1. 类目置信度高：进入单品类检索。
2. 类目置信度中等且多个品类合理：并行召回，再按匹配强度排序。
3. 类目置信度低：先追问，不强行推荐。
4. 明确预算：所有品类都做硬过滤。
5. 明确排除：如果数据明确命中，过滤或极强降权；如果数据未说明，不要反向承诺。

## 字段进入链路的边界

| 链路 | 使用字段 | 说明 |
| --- | --- | --- |
| 商品卡片 | raw title/brand/price/image + `display.card_reason` + `attributes.tags` | 卡片保持轻量 |
| 详情弹窗 | raw + `display.detail_*` + `attributes` + `category_attributes` + `variants` | 展示更多证据和变体维度 |
| 检索过滤 | raw category/sub_category/base_price + `retrieval.hard_filter_facets` | 硬约束优先 |
| 排序 | `attributes` + `category_attributes` + vector score + keyword score | 软偏好加权 |
| graph trace | `graph` 或派生 graph relations | 用于解释“为什么推荐” |
| 生成 prompt | 候选商品证据字段 + `source.attribute_provenance` | 模型不能看到全库，优先引用 explicit 证据 |
| guardrail | raw price/brand/title + enriched cautions/avoid_for/evidence + provenance confidence | 防止编造和无证据否定 |

## 第二品类样例计划

建议先标注 5 条服饰运动商品：

| raw_product_id | 子类 | 选择原因 | 样例 query |
| --- | --- | --- | --- |
| `p_clothes_001` | 短袖T恤 | 棉感、凉感、宽松、通勤 | 100 元以内夏天通勤 T 恤，不想太闷 |
| `p_clothes_002` | 短袖T恤 | 速干训练、运动场景 | 跑步训练用，想要速干透气短袖 |
| `p_clothes_007` | 跑步鞋 | 日常训练、缓震、公路跑 | 日常慢跑鞋，想要缓震舒服 |
| `p_clothes_014` | 徒步鞋 | 防水、抓地、户外 | 徒步鞋要防水抓地，预算 1200 内 |
| `p_clothes_018` | 背包 | 通勤/户外双场景、容量 | 通勤也能周末户外用的双肩包 |

这 5 条覆盖：

1. 材质/肤感类约束：棉感、凉感、透气。
2. 尺码/版型类约束：宽松、衣长、S/M/L。
3. 运动场景：跑步、徒步。
4. 天气/户外：夏天、防水、抓地。
5. 容量/携带：通勤背包、户外背包。

## V2-A 完成标准

本页和 [电商 Schema 外部参考调研](16_ecommerce_schema_references.md) 完成后，V2-A 视为完成第一版。进入 V2-B 前需要：

1. 新增或调整数据生成脚本，支持非美妆 enriched 输出。
2. 明确是继续多个 JSONL 文件，还是合并成 `products.jsonl`。
3. 更新 `data_loader.py`，让后端可加载多个 enriched 文件。
4. 新增 apparel query benchmark。
5. 保持现有美妆 golden/subcategory/conversation tests 全部通过。

V2-B 标注 5 条 apparel 样例时，至少要覆盖：

1. `variants.variant_dimensions`：颜色、尺码、容量或版本等。
2. `attributes.specifications`：材质、规格、容量、重量、包装等商品事实。
3. `source.attribute_provenance`：材质、尺码、运动场景、防水、容量等硬约束字段的证据。
