# RAG 检索策略调研与设计

日期：2026-05-26  
用途：明确本项目的 RAG 不等于单纯向量检索，而是围绕电商导购场景设计一条可解释、可评测、能处理硬约束的混合检索链路。

## 结论先行

本项目不建议只做 `Chroma vector search -> LLM` 的朴素 RAG。电商导购里有很多硬约束：

1. 预算：200 元以内、300 元以内。
2. 类目：防晒、面霜、精华、底妆。
3. 肤质：油皮、干皮、敏感肌。
4. 功效：控油、修护、保湿、抗初老、提亮。
5. 排除条件：不要酒精、不要刺激、不要太油、不要某品牌。
6. 商品事实：价格、库存、优惠、功效不能编造。

这些约束不能只交给 prompt 或 embedding 相似度处理。当前建议路线是：

> Product Graph-Aware Hybrid RAG = 结构化硬过滤 + 属性图匹配 + 向量召回 + 多路融合排序 + 证据约束生成 + 生成后校验。

第一版先实现轻量版本，不直接引入重型 GraphRAG 框架。

## 关键澄清

### Query Parser / Planner 的主流做法

目前常见方案不是某一个固定算法，而是几类方法组合：

| 方法 | 适合内容 | 优点 | 风险 | 本项目策略 |
| --- | --- | --- | --- | --- |
| 规则解析 | 价格、预算、明确否定词、品牌名 | 稳定、可解释、不会乱抽字段 | 覆盖不了复杂表达 | MVP 主线 |
| LLM structured output | 将自然语言解析成固定 JSON schema | 覆盖复杂表达，扩展性好 | 需要模型稳定输出；可能误抽 | 后续增强 |
| Self-query retriever | 让 LLM 生成 query + metadata filter | 适合有明确 metadata 的检索库 | 引入框架和调试成本 | 作为参考，不直接依赖 |
| Router / planner | 决定走哪个 retriever 或品类路径 | 多品类、多检索源时有用 | 早期会增加复杂度 | 多品类阶段加入 |
| Query rewriting / multi-query | 扩展模糊 query，提高召回 | 能补语义召回不足 | 可能引入噪音 | 作为后续召回增强 |

因此第一版 Query Parser 不追求“全智能”，而是采用：

> 规则解析硬约束 + 结构化意图对象 + 后续可替换为 LLM structured output。

预算、明确排除条件、类目这类会影响扣分的字段，优先用规则和词典解析；复杂偏好再逐步交给 LLM 或 router。

### Chroma / Qdrant / Pinecone 的定位

Chroma、Qdrant、Pinecone 都属于向量数据库或 vector store。它们通常同时支持两类能力：

1. **软检索**：根据 embedding 相似度找语义相近内容。
2. **硬过滤**：根据 metadata/payload 过滤，例如 `price <= 200`、`category == 防晒`。

因此“向量数据库”不等于“只能做软检索”。只要使用 metadata filter，它也可以承担一部分硬约束。

本项目当前选择：

| 方案 | 是否采用 | 原因 |
| --- | --- | --- |
| Chroma | 继续作为 MVP 向量库 | 本地轻量，已有依赖，足够支撑 100-500 条商品 demo |
| Qdrant | 保留备选 | payload filter 和工程化能力更强，适合约束复杂后迁移 |
| Pinecone | 暂不采用 | 云服务依赖和配置成本较高，不适合当前本地比赛节奏 |

第一版建议：**Python 层做 hard filter，Chroma 做 vector recall**。这样更透明，也更容易解释。后续如果字段复杂度上升，再把一部分 filter 下推到 Chroma/Qdrant。

### 硬约束、软约束和追问 Gate

不是所有条件都应该变成分数。需要区分三类：

| 类型 | 示例 | 处理方式 |
| --- | --- | --- |
| 硬约束 | “200 元以内” | 直接过滤，超预算不进入候选 |
| 强排除 | “不要酒精”“不要刺激感强” | 如果数据明确命中，则过滤或极强降权 |
| 软偏好 | “最好便宜点”“清爽一点” | 加权排序，不直接排除 |
| 信息不足 | “我想买护肤品” | 不进入普通推荐，先追问 |

信息不足不应该作为普通 `constraint_violation_penalty` 混进分数，而应该是单独 gate：

```text
if intent.needs_clarification:
    return clarification_question
else:
    retrieve_and_rank
```

预算也不应该只是加一个很大的负分。用户明确说“200 元以内”时，超预算商品应该直接排除；只有“最好 200 左右”这种表达才适合软降权。

### Embedding 选择

Embedding 需要 benchmark，而不是凭感觉选。第一阶段可比较：

| Embedding | 优点 | 风险 | 用途 |
| --- | --- | --- | --- |
| `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` | 轻量、当前已接入、下载和运行成本低 | 中文商品细粒度语义可能一般 | MVP baseline |
| `BAAI/bge-small-zh-v1.5` | 中文检索常用，模型较轻 | 仍需下载和验证 | 中文检索候选 |
| `BAAI/bge-m3` | 多语言、多粒度检索能力更强 | 模型更大，运行成本更高 | 后续增强候选 |

小 benchmark 需要比较 Recall@K、约束违反次数和响应延迟。只有当新 embedding 明显提升召回且成本可接受时，才替换默认方案。

## 为什么纯向量 RAG 不够

纯向量检索适合处理语义相近的自然语言，例如：

- “清爽一点的防晒”
- “不要闷脸”
- “日常上班用”

但它不擅长稳定执行以下条件：

- `价格 <= 200`
- `category == 防晒`
- `不含/不推荐某类刺激因素`
- `必须来自商品库`
- `只能推荐召回商品`

向量相似度会把“看起来相关”的商品召回，但它不保证满足预算、否定条件、成分禁忌和事实一致性。因此我们的 RAG 需要把“语义相似”和“业务规则”拆开处理。

## 相关方法调研

| 方法 | 解决什么问题 | 对本项目的启发 | 是否现在接入 |
| --- | --- | --- | --- |
| Naive Vector RAG | 从文本中找语义相似内容 | 适合召回商品描述、FAQ、用户评价 | 作为一层保留 |
| Metadata Filtering | 用结构化字段限制向量检索范围 | 预算、类目、品牌、肤质、功效应做硬过滤 | 立即采用 |
| Hybrid Search | 结合向量、关键词、结构化条件 | 商品名/品牌/成分适合 keyword，模糊需求适合 vector | 立即采用轻量版 |
| GraphRAG | 用实体和关系组织知识 | 商品-品牌-功效-肤质-场景天然适合图结构 | 借鉴思想，不直接上重框架 |
| LightRAG | 轻量图增强 RAG，含图存储、向量存储、混合查询 | 可作为后续 benchmark 或替代实现参考 | 暂不接入主线 |
| CRAG | 评价检索结果质量，必要时纠正 | 可做 retrieval evaluator：召回不可信时追问或重检索 | 后续加入 |
| Self-RAG | 模型决定是否检索并自我 critique | 思想适合“信息不足先追问” | 不训练模型，只借鉴控制流程 |
| Guardrails / Groundedness | 输出后检查是否基于证据 | 可用于反幻觉、拒绝无依据回答 | 先做规则版，后续考虑工具 |
| Ragas 指标 | 评测 context precision、faithfulness 等 | 可用于后续评测报告 | 先做手工小 benchmark |

## 强约束 RAG 的常见处理方式

调研下来，“强约束”通常不是靠单个 RAG 算法解决，而是靠多层防线。

### 1. 检索前：Query Parser / Planner

先把用户自然语言拆成结构化意图：

```json
{
  "category_candidates": ["beauty"],
  "universal_constraints": {
    "budget_max": 200,
    "brand_exclude": []
  },
  "facets": {
    "skin_type": ["油皮"],
    "effect": ["防晒"],
    "use_case": ["通勤"],
    "exclude_terms": ["刺激感强", "太油"]
  },
  "needs_clarification": false,
  "confidence": 0.82
}
```

这一层决定后面走哪些检索策略：

- 信息不足：先追问。
- 有预算：做价格硬过滤。
- 有排除条件：做 deny-list 过滤或降权。
- 有对比对象：进入多商品对比流程。

### 2. 检索中：Metadata / SQL / Payload Filter

硬约束要尽量在检索阶段处理，而不是等模型生成时再提醒。

向量数据库本身通常支持 metadata/payload filter。例如：

- Pinecone 支持 metadata filter，用 `$eq`、`$lte`、`$in`、`$and`、`$or` 等限制搜索结果。
- Qdrant 用 payload filter 把数据库式条件和向量搜索结合。
- Chroma 支持 `where` metadata filter 和 document filter。

对我们来说，第一版可以不依赖数据库的全部 filter 能力，而是在 Python 检索层先做确定性过滤：

```text
if budget_max is not None:
    candidate = candidate where price <= budget_max

if category is not None:
    candidate = candidate where category/sub_category matches category

if exclude contains "酒精" or "刺激":
    candidate = candidate downrank or exclude if cautions/avoid_for hits
```

### 3. 检索后：Rerank / Evidence Selection

多路召回后，需要重新排序。但排序只处理已经通过硬约束的候选，不负责挽救明确违反硬约束的商品。建议第一版融合这些分数：

```text
final_score =
  structured_match_score
  + graph_relation_score
  + vector_score
  + keyword_score
  - constraint_violation_penalty
```

其中：

- `structured_match_score`：预算、类目、肤质、功效命中。
- `graph_relation_score`：商品和用户需求节点之间的关系命中数。
- `vector_score`：Chroma 相似度。
- `keyword_score`：品牌名、商品名、成分词、功效词命中。
- `constraint_violation_penalty`：只用于软约束或不确定约束；明确超预算直接排除。

### 4. 生成时：Evidence-Bound Prompt

模型不应该看到整个商品库，而只看到最终候选商品和证据字段。

Prompt 需要明确：

1. 只能推荐候选商品。
2. 价格、品牌、图片、库存、优惠不能自行生成。
3. 如果证据里没有某个功效或成分，必须说“资料中未说明”。
4. 信息不足时先追问，不要强行推荐。

### 5. 生成后：Verifier / Guardrail

输出后再做校验：

1. 是否出现不在候选商品中的商品名。
2. 是否出现数据源没有的价格、优惠、库存。
3. 是否推荐了超预算商品。
4. 是否把“资料中未说明”的内容说成确定事实。
5. 是否在信息不足 query 中没有追问而直接推荐。

第一版可以用规则检查；后续再考虑 LLM-as-judge 或 Ragas。

## 我们自己的算法路线

### V0：当前 Baseline

当前已有：

1. 预算简单解析。
2. 关键词和结构化 bonus。
3. 可选 Chroma vector rank。
4. 商品卡字段来自 raw/enriched 数据。
5. Prompt 约束模型不能编造。

问题：

1. Chroma 还不是稳定主链路。
2. 没有 retrieval trace。
3. 没有明确 graph/attribute relation scoring。
4. 否定条件和信息不足处理还弱。

### V1：Constraint-Aware Hybrid Retrieval

第一阶段先补强约束和可解释性，不急着引入属性图。

目标：

1. 把用户 query 解析成 `QueryIntent`。
2. 明确区分硬约束、软偏好、信息不足。
3. 预算、类目、明确排除条件在检索前处理。
4. Chroma 作为向量召回通道进入主链路。
5. 输出 retrieval trace。

这一阶段完成后，系统应该能回答：

> 用户需求被解析成什么？哪些商品被过滤掉？哪些商品被向量召回？最后为什么推荐这几个？

### V2：Graph-Aware Retrieval

先不接 Neo4j，用本地数据结构构建轻量属性图：

```text
product -> brand
product -> category
product -> sub_category
product -> universal_facet
product -> category_specific_facet
product -> price_bucket
product -> evidence_text
```

这张图需要支持多品类，而不是只写死美妆。设计上分两层：

通用字段：

```text
product_id
title
brand
category
sub_category
price
image_path
description
reviews
```

品类特定字段：

```text
beauty:
  skin_type, effect, ingredient, caution, use_case

digital:
  spec, battery, compatibility, use_case, performance

clothes:
  material, size, season, style, fit, sport_type

food:
  flavor, ingredient, allergen, package, use_case
```

如果用户描述无法落到单一品类，不强行单选：

1. 置信度低时先追问。
2. 多个品类都合理时并行召回。
3. 跨品类场景，如旅行搭配，再进入组合推荐逻辑。

示例：

```text
p_beauty_006 -> category: 防晒
p_beauty_006 -> skin_type: 油皮
p_beauty_006 -> use_case: 通勤
p_beauty_006 -> effect: 防晒 / 提亮 / 妆前
p_beauty_006 -> caution: 敏感肌先测试
```

用户 query 也解析成节点：

```text
query -> skin_type: 油皮
query -> budget_max: 200
query -> use_case: 通勤
query -> effect/category: 防晒
```

图匹配分：

```text
graph_relation_score = matched_relation_count * weight
```

### V3：Verifier + Benchmark Loop

这一阶段补生成后校验和 benchmark，让系统不仅能推荐，还能知道自己哪里错。

生成后做规则校验：

1. 超预算则拒绝该推荐或重写。
2. 非候选商品名则标记 hallucination。
3. 没有证据的优惠/库存/功效则标记 hallucination。
4. 信息不足但未追问则标记 clarification failure。

### 多路召回定义

最终候选商品来自多路召回：

1. Structured filter candidate set。
2. Attribute graph top-k。
3. Chroma vector top-k。
4. Keyword/BM25-like top-k。

然后做融合排序：

```text
candidate_pool = union(structured, graph, vector, keyword)
ranked = rerank(candidate_pool, constraints, query_intent)
```

第一版可以用手写分数，不必马上引入复杂 reranker。

### Constraint-Aware Generation

生成前组装 context：

```text
候选商品:
- 商品 A: title, brand, price, tags, suitable_for, avoid_for, cautions, description
- 商品 B: ...

硬约束:
- budget_max: 200
- exclude: 酒精/刺激
- query_needs: 油皮, 通勤, 防晒
```

## 小 Benchmark 设计

第一版 benchmark 不追求论文级，只要能稳定帮助我们迭代。

### Query 集合

先使用 `docs/05_golden_queries.md` 的 8 条：

| 类型 | 示例 | 重点检查 |
| --- | --- | --- |
| 预算 + 肤质 + 场景 | 油皮 200 元以内通勤防晒 | 是否超预算，是否命中油皮/通勤/防晒 |
| 肤质 + 功效 | 敏感肌屏障修护面霜 | 是否推荐修护类，是否提示测试 |
| 反选 | 不要酒精味太重或刺激感强 | 是否排除/降权刺激风险 |
| 预算 + 功效 | 300 内抗初老/提亮精华 | 是否排除超预算 |
| 负面约束 | 干皮保湿，不想拔干 | 是否避免控油拔干产品 |
| 子类目 | 控油底妆/定妆 | 是否召回底妆/蜜粉 |
| 对比 | 欧莱雅防晒和安热沙防晒更适合谁 | 是否结构化对比 |
| 信息不足 | 我想买护肤品 | 是否主动追问 |

### 对比版本

| 版本 | 描述 | 目的 |
| --- | --- | --- |
| B0 | 当前关键词/结构化 baseline | 记录当前能力 |
| B1 | 纯 Chroma vector top-k | 看纯向量是否会违反硬约束 |
| B2 | Constraint-aware hybrid retrieval | 验证硬过滤和 trace 价值 |
| B3 | Graph-aware hybrid retrieval | 验证属性图关系分价值 |
| B4 | B3 + 生成后 verifier | 验证反幻觉和约束遵守 |

### 指标

| 指标 | 说明 |
| --- | --- |
| Recall@K | 期望商品是否在 top-k 内 |
| Precision@K | top-k 中相关商品比例 |
| Constraint Violation Count | 超预算、命中排除条件、错类目次数 |
| Hallucination Count | 编造商品、价格、优惠、库存、功效次数 |
| Clarification Accuracy | 信息不足时是否追问 |
| Trace Completeness | 是否输出 query parse、过滤、召回、排序理由 |
| Latency | 首 token 时间和总响应时间 |

### 评测记录格式

```json
{
  "query_id": "GQ-01",
  "query": "我是油皮，想要 200 元以内的通勤防晒",
  "parsed_constraints": {
    "skin_type": "油皮",
    "budget_max": 200,
    "use_case": "通勤",
    "category_or_effect": "防晒"
  },
  "expected_products": ["p_beauty_006"],
  "retrieved_products": ["p_beauty_006", "p_beauty_010"],
  "constraint_violations": [],
  "hallucinations": [],
  "needs_clarification": false,
  "actual_clarification": false,
  "notes": "推荐理由需要明确价格来自数据源"
}
```

## 接下来调研方向

### 方向 1：结构化过滤与向量数据库 filter

目标：确认 Chroma 是否够用，还是后续需要 Qdrant。

要看：

1. Chroma `where` filter 是否支持我们的字段类型。
2. 如果字段复杂，是否更适合先在 Python/SQLite 过滤，再调用 Chroma。
3. Qdrant payload filter 是否更适合后续复杂约束。

结论倾向：

> MVP 继续用 Chroma + Python hard filter；如果 filter 复杂度上升，再评估 Qdrant。

### 方向 2：Graph-aware RAG 的轻量实现

目标：不是接完整 GraphRAG，而是提取可解释关系分。

要看：

1. Microsoft GraphRAG 的 indexing/query 思路。
2. LightRAG 的 local/global/hybrid query 思路。
3. 是否需要 NetworkX 做本地图，还是用 dict 就够。

结论倾向：

> 当前数据量小，用 dict/JSON 构建 product attribute graph 即可；GraphRAG/LightRAG 作为参考和后续扩展。

### 方向 3：强约束与反幻觉

目标：找到最适合比赛项目的低成本防线。

要看：

1. CRAG 的 retrieval evaluator 思路。
2. Self-RAG 的 retrieve/generate/critique 思路。
3. Guardrails 的 groundedness/output rail 思路。
4. Ragas 的 faithfulness/context precision 指标。

结论倾向：

> 第一版用规则 verifier + 小 benchmark；后续再接 LLM judge 或 Ragas。

### 方向 4：可解释 Trace

目标：让每次推荐都能回答“为什么是这个商品”。

需要设计：

1. query parse trace。
2. structured filter trace。
3. vector retrieval trace。
4. graph relation trace。
5. final rerank trace。
6. generation guardrail trace。

这会直接服务答辩，也能帮助我们 debug。

## 第一版实现建议

下一步代码层面建议：

1. 新增 `QueryIntent` 数据结构：
   - `category_candidates`
   - `universal_constraints`
   - `facets`
   - `hard_constraints`
   - `soft_preferences`
   - `exclude_terms`
   - `needs_clarification`
   - `confidence`
2. 新增 `RetrievalTrace` 数据结构：
   - `parsed_intent`
   - `hard_filtered_out`
   - `vector_hits`
   - `keyword_hits`
   - `graph_hits`
   - `final_scores`
   - `guardrail_checks`
3. 重构 `retrieve()`：
   - parse query
   - hard filter
   - vector score
   - keyword score
   - graph score
   - rerank
   - return cards + context + trace
4. 新增 debug 输出：
   - 后端日志先够用。
   - 后续可加 `/api/debug/retrieve`。
5. 新增 `docs/11_evaluation_report.md`：
   - 先人工记录 8 条 golden queries。

### RetrievalTrace 草案

第一版 trace 不要只服务美妆，需要为多品类预留空间：

```json
{
  "query": "我是油皮，想要 200 元以内的通勤防晒",
  "parsed_intent": {
    "category_candidates": ["beauty"],
    "universal_constraints": {
      "budget_max": 200,
      "brand_exclude": []
    },
    "facets": {
      "skin_type": ["油皮"],
      "effect": ["防晒"],
      "use_case": ["通勤"],
      "exclude_terms": []
    },
    "needs_clarification": false,
    "confidence": 0.82
  },
  "filters": {
    "hard_filtered_out": [
      {
        "product_id": "p_xxx",
        "reason": "price > 200"
      }
    ]
  },
  "retrieval_channels": {
    "keyword": [],
    "vector": [],
    "graph": []
  },
  "final_ranking": [
    {
      "product_id": "p_beauty_006",
      "score": 12.4,
      "reasons": ["price_match", "skin_type_match", "vector_hit"]
    }
  ],
  "guardrail_checks": {
    "over_budget": false,
    "unknown_product": false,
    "unsupported_claim": false
  }
}
```

这个 trace 后续可用于 debug、benchmark、failure case 复盘、答辩展示，也可以积累成未来 fine-tuning 或规则优化数据。

## 参考资料

- RAG survey: https://arxiv.org/abs/2312.10997
- Microsoft GraphRAG: https://github.com/microsoft/graphrag
- Microsoft GraphRAG outputs: https://microsoft.github.io/graphrag/index/outputs/
- LightRAG: https://github.com/HKUDS/LightRAG
- Pinecone metadata filtering: https://docs.pinecone.io/guides/search/filter-by-metadata
- Qdrant filtering/search: https://qdrant.tech/documentation/search/
- Chroma filters: https://docs.trychroma.com/reference/where-filter
- Corrective RAG paper: https://arxiv.org/abs/2401.15884
- Corrective RAG code: https://github.com/HuskyInSalt/CRAG
- Self-RAG paper: https://arxiv.org/abs/2310.11511
- Self-RAG code: https://github.com/akariasai/self-rag
- NVIDIA NeMo Guardrails: https://docs.nvidia.com/nemo-guardrails/index.html
- Ragas metrics: https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/
