# 进阶路线调研顺序与取舍方案

日期：2026-06-06

## 背景

这份文档用于把后续“进阶采分路线”的调研顺序先固定下来。讨论里有一个关键判断：官方给出的进阶路线通常不是孤立功能点，而是一条完整链路。如果选择某条路线，就应尽量从入口识别、目标解析、状态/工具执行、UI 反馈、异常处理、trace/eval 走到底。

当前项目已经在以下路线走得比较深：

- 商品对比：Planner 识别对比意图，后端校验目标商品，LLM 输出 Markdown 表格，Android 渲染。
- 多轮指代与排除：通过 history、answer directive 和 retrieval trace 支撑“前两个 / 第一和第三 / 不要某类”。
- 可追溯反馈闭环：runtime trace 与 feedback 通过 `trace_id` 关联，方便把现场失败转成 benchmark。

因此，后续调研不应平均撒点，而应先评估哪些路线值得继续深挖。

## 调研顺序

| 顺序 | 路线 | 为什么放在这里 | 当前建议 |
| --- | --- | --- | --- |
| 1 | 购物车 / 下单 Action | 用户已经明确提出这一条；它看起来像 UI 功能，实际难点是 action safety、状态一致性、库存/价格重校验和确认链路，适合先判断是否值得做。 | 先做调研与方案边界；如实现，只做 mock cart MVP。 |
| 2 | 拍照找货 / 多模态 | 豆包模型支持多模态输入，但“拍照找货”可以走 VLM 标签、图像 embedding、文本召回或混合 rerank，技术路线分歧较大，需要单独调研。 | 第二阶段调研，先区分 demo MVP 和真实相似商品检索。 |
| 3 | 语音输入 | 可能实现成本较低，但采分深度取决于是否只是 ASR 输入，还是能处理口语化购物意图、纠错和确认。 | 第三阶段调研，判断是否作为低风险体验增强。 |
| 4 | 端侧体验 / 性能与交互打磨 | 现有 Android UI 已经有卡片、详情、Markdown、表格和 trace；继续打磨能提升 demo 观感，但不一定形成新的深链路。 | 作为收尾优化，不抢主线调研时间。 |

## 路线评估模板

每条路线都按同一套问题评估：

1. 官方链路/场景入口是什么。
2. 用户一句话触发后，系统要识别什么 intent。
3. 是否需要解析具体商品、SKU、数量、规格或图片对象。
4. 是否需要状态或工具执行。
5. UI 最小闭环是什么。
6. 失败时是否能追问、拒绝或回滚。
7. trace / eval 如何证明这条链路真的跑通。
8. 如果不实现，是否能把调研结论作为取舍证据。

## 第一条路线：购物车 / 下单 Action

### 外部参考

Shopify Storefront API 把 `Cart` 定义为买家在会话中打算购买的商品及其预估费用，并提供 `lines`、`cost`、`totalQuantity`、`checkoutUrl` 等字段。它同时提供 `cartCreate`、`cartLinesAdd`、`cartLinesUpdate`、`cartLinesRemove` 等 mutation。这说明真实电商购物车不是一个前端弹窗，而是一个会话级状态对象，且每次变更都需要通过明确 mutation 更新。参考：[Shopify Cart object](https://shopify.dev/docs/api/storefront/latest/objects/Cart) 和 [Manage a cart with the Storefront API](https://shopify.dev/docs/storefronts/headless/building-with-the-storefront-api/cart/manage)。

Shopify 还明确 `cost` 是 checkout 时买家将支付的预估费用，并且费用可能变化。这对本项目的启发是：即使 demo 里没有真实支付，进入“下单”前也应重新校验价格、库存、SKU 是否仍有效。

Stripe 文档也能作为支付侧边界参考：Stripe 当前建议多数集成优先使用 Checkout Sessions；PaymentIntent 则用于处理状态会变化的复杂支付流程，并跟踪从创建到 checkout 的支付生命周期。参考：[Stripe Payment Intents](https://docs.stripe.com/payments/payment-intents)。这说明如果路线推进到“支付/下单”，它就不再是普通生成回答，而是状态机和确认流程。

### 工程实践补充调研

从成熟电商 API 和支付 API 来看，购物车 / 下单 Action 的工程实践有几个共性。

| 实践来源 | 现成工作 | 对本项目的启发 |
| --- | --- | --- |
| Shopify Storefront API | `Cart` 是 buyer session 里的商品和预估费用状态对象，包含 `lines`、`cost`、`checkoutUrl`，通过 `cartCreate`、`cartLinesAdd`、`cartLinesUpdate`、`cartLinesRemove` 等 mutation 改变状态。 | 商品卡上的“加入购物车”不应只是 UI 文字，而应产生明确 action event，并改变 cart state。 |
| Shopify checkout URL | Cart 提供 `checkoutUrl`，用于把买家导向 checkout 完成购买。`cost` 是预估费用，checkout 时可能变化。 | 推荐链路和 checkout 链路要分层；结算前要重新校验价格、SKU 和可购买状态。 |
| commercetools Carts / Orders | Line Item 是加入购物车时 Product Variant 的 snapshot；更新 Cart 时系统会移除无效商品、更新价格、折扣、税费、库存数量限制等；Cart 可以 freeze/lock；Order 通常从 Cart 创建。参考：[Carts and Orders overview](https://docs.commercetools.com/api/carts-orders-overview)。 | SKU 要落到 line item；mock cart 也应记录 `variant_id`、`unit_price`、`quantity`。如果模拟 checkout，要有 `recalculate` / `validate` 步骤。 |
| commercetools Checkout | Checkout 被拆成 Complete Checkout 和 Payment Only；Checkout Application 会读取/更新 Cart 和 Order 数据、连接支付服务商、执行配置。参考：[Checkout overview](https://docs.commercetools.com/checkout/overview)。 | 即使不接真实支付，也应把“购物车更新”和“支付/下单确认”拆成不同阶段。 |
| Stripe Checkout Sessions | Stripe 建议多数支付集成优先使用 Checkout Sessions，因为它管理 checkout lifecycle、session state、认证、重复扣款等复杂问题。参考：[Checkout Sessions API](https://docs.stripe.com/payments/checkout-sessions)。 | 本项目不应实现真实支付；如果展示“下单”，最多做到 mock confirmation，并明确不可真实支付。 |

工程侧结论：

- 购物车是状态对象，不是回答文本。
- 加购、改数量、删除、结算都应是 action/mutation，不应由 LLM 直接编写结果。
- SKU/variant 是购物车行项目的核心粒度，不能只存 parent product。
- checkout 前必须有重校验：价格、库存、SKU 有效性、数量限制。
- 真实支付最好交给专门 checkout/payment 系统；demo 阶段只做 mock confirmation。
- Debug 需要记录 action trace：请求、解析出的目标、执行前 state、执行后 state、失败原因。

### 科研实践补充调研

科研侧已有不少和“购物 agent / web action / retail tool use”相关的工作，但它们分成两条路线。

#### 路线 A：网页操作型购物 agent

这类工作让 agent 像用户一样操作网页，完成搜索、筛选、加入购物车、购买或 checkout。

| 工作 | 相关性 | 对本项目的启发 |
| --- | --- | --- |
| WebShop | 模拟电商网站，包含 118 万真实商品和 12,087 条众包文本指令；agent 需要浏览页面、执行多种动作、找到/定制/购买商品。最佳模型成功率 29%，人类专家 59%。参考：[WebShop](https://arxiv.org/abs/2207.01206)。 | 证明“找货 + 操作 + 购买”是一条经典研究路线，但完整网页操作成本高，不适合作为当前 Android MVP 主线。 |
| WebArena | 构造可复现的真实感网站环境，包含电商等四个域，评估长程网页任务的 functional correctness；最佳 GPT-4 agent 端到端成功率 14.41%，人类 78.24%。参考：[WebArena](https://arxiv.org/abs/2307.13854)。 | 长程网页操作非常容易失败；如果我们要做加购，最好用结构化 API 而不是让 agent 点真实网页。 |
| Mind2Web | 从 137 个真实网站、31 个领域采集 2000+ 开放任务和人工动作序列，研究 generalist web agent。参考：[Mind2Web](https://arxiv.org/abs/2306.06070)。 | 真实网页 HTML 太大、操作模式复杂；不适合短期把 Android 项目扩成浏览器自动化。 |
| DeepShop | 面向复杂购物搜索的 benchmark，关注多维商品属性、搜索过滤、排序偏好，并做细粒度/整体评估。参考：[DeepShop](https://arxiv.org/abs/2506.02839)。 | 说明购物任务的难点不仅是下单，也包括过滤、排序和属性约束；我们的 eval 可以借鉴“细粒度失败原因”。 |
| ShoppingBench | 构造 250 万真实商品的购物 sandbox，覆盖优惠券、预算、多商品同商家等复杂 grounded intent；GPT-4.1 等强 agent 成功率低于 50%。参考：[ShoppingBench](https://arxiv.org/abs/2508.04266)。 | 复杂购物 action 需要显式约束检查；不要只靠模型一次性规划。 |
| WebMall | 多店铺 offline benchmark，覆盖找具体商品、比价、替代/互补商品和 checkout；强调多店异构商品数据。参考：[WebMall](https://arxiv.org/abs/2508.13024)。 | 如果未来走“比价 + 下单”，会比当前单数据源复杂很多；当前不应跨店扩张。 |

#### 路线 B：工具/API + 政策约束型 retail agent

这类工作不要求 agent 点网页，而是给 agent 一组 API tool 和业务 policy，让它在多轮对话中正确改状态。

| 工作 | 相关性 | 对本项目的启发 |
| --- | --- | --- |
| tau-bench | 模拟用户和工具 agent 的动态对话；agent 拿到 domain-specific API tools 和 policy guidelines，最终用数据库目标状态评估。论文指出 GPT-4o 等 function calling agent 在任务上成功率低于 50%，retail pass^8 低于 25%。参考：[tau-bench](https://arxiv.org/abs/2406.12045)。 | 这是我们最应该借鉴的方向：用工具/API、业务规则、最终状态差异和 pass^k 来评估 action reliability。 |

科研侧结论：

- 如果目标是加分展示，“API/tool + policy + trace/eval”比“完整网页自动化”更适合当前项目。
- 购物 action 的评估不应只看回答是否好听，而应看最终 state 是否正确。
- 需要把失败拆成可诊断类别：目标解析错、SKU 错、数量错、约束未满足、库存/价格失效、未确认就执行。
- 可以把我们现有 runtime trace 扩展成 action trace，形成和 tau-bench 类似的 state-based eval。

### 是否有现成工作可直接用

可直接借鉴的有：

- Shopify / commercetools 的 cart 数据模型和 checkout 分层。
- Stripe Checkout Sessions 的“支付交给 checkout 系统，应用只创建 session / 监听结果”思路。
- tau-bench 的“工具调用 + policy + 最终数据库状态评估”范式。
- WebShop / ShoppingBench 的购物任务分类和失败分析。

不适合直接照搬的有：

- 完整浏览器自动下单：工程成本高，和当前 Android RAG demo 偏离较远。
- 真实支付：安全、合规、账号、密钥和退款链路都超出本阶段范围。
- 复杂优惠券/跨店比价：会把 retrieval、库存、价格和商家约束全部放大。

因此，更合理的现成路线是：

```text
Shopping Agent 推荐
  -> 结构化 action_plan
  -> mock cart tool
  -> cart state before/after
  -> checkout confirmation only
  -> action trace + state-based eval
```

### 用户理解是否正确

用户的直觉基本正确：购物车路线的表层形态可以是“加入购物车后弹出已添加、点开购物车查看商品和总价”。但它的主要难点不在弹窗，而在下面这些链路：

- 意图识别：用户可能说“帮我加这个”“第一款来一件”“把那个 40ml 加购物车”“不要第二个了”。
- 目标解析：必须知道指的是哪张商品卡、哪个 SKU、数量是多少。
- 状态执行：加入、更新数量、删除、查看都要改变 cart state。
- 失效处理：价格变动、库存不足、SKU 已下架时要阻止继续下单。
- 安全确认：真正下单或支付前必须显式确认，不能由 LLM 自行执行不可逆操作。
- 可追溯：需要记录 action 前后的 cart state，否则很难证明“加对了哪一件”。

### 完整链路

```text
用户请求
  -> Action intent 识别
  -> 商品 / SKU / 数量解析
  -> 歧义检查，必要时追问
  -> cart mutation
  -> UI 状态反馈
  -> 结算前重校验
  -> 用户二次确认
  -> checkout / mock checkout
  -> runtime trace + action eval
```

### MVP 范围

如果要实现，建议只做 mock cart，不接真实支付、不接真实库存系统：

- Android 本地或后端 session 级 mock cart。
- 商品卡和详情页增加“加入购物车”入口。
- 支持 add / view / update quantity / remove。
- 购物车 sheet 展示商品、SKU、数量、小计和总价。
- “去结算”只进入确认页或确认弹窗，不生成真实订单。
- mock 后端可以模拟 `price_changed`、`out_of_stock`、`sku_invalid` 三类失败。
- 每次 action 写入 runtime trace：`action_type`、`target_product_id`、`target_variant_id`、`quantity`、`cart_before`、`cart_after`、`failure_reason`。

### 不建议本阶段做的内容

- 真实支付。
- 真实库存扣减。
- 地址、优惠券、运费、税费、登录态。
- 多端购物车同步。
- LLM 直接决定下单。

这些内容会把项目从 RAG shopping agent 扩展成电商交易系统，投入大且容易偏离当前主线。

### 技术方案草案

#### 1. Intent schema

Planner 或后端 action parser 可以输出：

```json
{
  "action_plan": {
    "enabled": true,
    "action_type": "add_to_cart",
    "target_policy": "mentioned_product_index",
    "target_product_ids": ["p_food_022"],
    "target_variant_ids": ["s_p_food_022_1"],
    "quantity": 1,
    "needs_confirmation": false,
    "needs_clarification": false,
    "clarification_question": null
  }
}
```

边界规则：

- Planner 只做意图和目标解析，不执行 mutation。
- 后端或 Android action layer 校验目标是否来自当前可见商品卡。
- SKU 不明确时必须追问，例如“你要 6 颗装还是 12 颗装？”。
- checkout / order 类 action 必须 `needs_confirmation=true`。

#### 2. Cart state

mock cart 最小结构：

```json
{
  "cart_id": "local-session",
  "items": [
    {
      "product_id": "p_food_022",
      "variant_id": "s_p_food_022_1",
      "title": "三顿半冷萃超即溶黑咖啡",
      "variant_label": "6颗装 / 冷萃黑咖",
      "unit_price": 58,
      "quantity": 1,
      "line_total": 58
    }
  ],
  "subtotal": 58,
  "updated_at": "2026-06-06T00:00:00+08:00"
}
```

#### 3. UI 闭环

- 商品卡：增加购物车图标按钮或详情页内的“加入购物车”按钮。
- action 成功：轻提示“已加入购物车”，同时可打开购物车 sheet。
- 购物车 sheet：商品列表、数量 stepper、删除、总价、结算按钮。
- 结算按钮：弹出确认态；如果 mock 失败，显示明确原因。

#### 4. Trace / eval

新增 action eval case：

| Case | 用户请求 | 预期 |
| --- | --- | --- |
| C1 | 把第一款加入购物车 | cart 增加上一轮第 1 个商品，数量 1。 |
| C2 | 40ml 那个加购物车 | 解析到对应 variant；如果不存在则追问。 |
| C3 | 第二款来两件 | cart line quantity = 2。 |
| C4 | 不要刚才那个了 | 删除最近加入或追问目标。 |
| C5 | 去结算 | 进入确认态，不直接下单。 |
| C6 | 后端模拟库存不足 | 阻止 checkout，trace 记录 `out_of_stock`。 |

## 当前决策

购物车 / Action 路线有调研和展示价值，但不建议作为当前主线立刻完整实现。

建议决策：

- 主线继续放在 RAG 正确性、商品对比、trace/eval 和 Android 展示。
- 购物车路线先作为“已评估的 Action Agent 方向”进入文档。
- 如果后续还有时间，可实现 mock cart MVP，用来展示 agent 从推荐走向 action 的能力。
- 即使实现，也必须明确标注为 mock，不宣称真实下单、真实库存或真实支付。

## 第二条路线：拍照找货 / 多模态

### 用户问题

拍照找货看起来像“上传一张图片，系统找相似商品”，但它内部有几条不同路线：

1. 视觉相似度：把用户图片和商品图片都转成 image embedding，做向量相似度检索。
2. 文本理解：用 VLM / OCR 把图片转成品牌、品类、颜色、包装文字、使用场景等结构化文本，再走文本检索。
3. 混合检索：先用视觉 embedding 找候选，再用 OCR、商品属性、价格/品类过滤和 reranker 做精排。

用户的直觉是对的，但工程上通常不是“图片相似度 vs 文本理解”二选一。更稳的生产方案往往是 hybrid：视觉召回负责“看起来像”，文本/属性负责“语义和约束对”，最后再用结构化规则或 reranker 兜底。

### 工程实践调研

| 实践来源 | 现成做法 | 对本项目的启发 |
| --- | --- | --- |
| Google Cloud Vision Product Search | 需要先创建 product set 并索引 reference images；查询时传入 GCS URI、web URL 或 base64 图片，返回相似产品、score、product labels 和 reference image。该功能当前处于 maintenance mode，Google 建议更大规模场景使用 Vision Warehouse。参考：[Vision API Product Search](https://docs.cloud.google.com/vision/product-search/docs/searching)。 | 真实“拍照找货”通常是 against own catalog，不是直接搜全网；必须先有商品图索引和 product labels。 |
| Google / Vertex 多模态 embedding | 多模态 embedding 会把图片、文本、视频映射到同一语义空间，可用于 text 搜 image、image 搜 video 等；文档也提醒相似度不是校准概率，并且图片中的文字需要区分“画面内容”和“图中文字”。参考：[Get multimodal embeddings](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/embeddings/get-multimodal-embeddings)。 | 可以把商品图和用户图放到同一 embedding 空间做相似度检索，但不能把分数当成置信概率；OCR/包装文字要单独处理。 |
| Weaviate `multi2vec-clip` | 支持用 CLIP/SigLIP 等模型把 image field 和 text field 共同向量化，提供 near text、near image、hybrid search 等能力。参考：[Weaviate multimodal embeddings](https://docs.weaviate.io/weaviate/modules/retriever-vectorizer-modules/multi2vec-clip)。 | 开源/自建路线可行：商品图和标题/标签可以共建向量；上传图走 near image，用户文字补充条件走 hybrid search。 |
| VLM / 图片理解 API | 多模态模型可以把图片、视频、文本输入转为结构化文本输出；例如火山引擎文档中也把多模态输入用于图片/视频理解和结构化文本生成。参考：[火山引擎多模态深度思考](https://www.volcengine.com/docs/6492/2165109)。 | VLM 很适合抽取标签、OCR、包装文字和场景，但它不是检索库；必须把抽取结果再接到商品库检索和 guardrail。 |

工程侧可以归纳成四种架构。

#### 1. Text-first MVP

```text
用户上传图片
  -> VLM/OCR 抽取品类、品牌、颜色、包装文字、场景
  -> 拼成 retrieval query
  -> 复用现有 RAG 检索与 ProductCard
  -> 回答中说明“根据图片识别到的线索”
```

优点：

- 最容易接入当前系统。
- 不需要先训练或部署视觉向量模型。
- 可以直接复用现有文本检索、Planner、ProductCard、trace 和 guardrail。

缺点：

- 本质是“看图生成文本后再搜”，不是真正的视觉相似商品检索。
- 对相似包装、相似外观、同款不同角度的能力弱。
- VLM 可能误识别品牌、容量、型号，需要低置信追问。

#### 2. Image-embedding MVP

```text
离线：商品 image_path -> image embedding -> vector index
在线：用户图片 -> image embedding -> topK visually similar products
      -> ProductCard / answer_directive
```

优点：

- 更接近用户理解里的“拍照找相似”。
- 对包装、形状、颜色、商品外观相似度更敏感。
- 当前数据已经有 `image_path`，可以先做一个小型本地索引。

缺点：

- 商品图数量少时效果有限。
- 用户实拍图和商品白底图分布差异大，可能召回不稳定。
- 相似度分数不是事实依据，仍需要商品资料校验。

#### 3. Hybrid 推荐方案

```text
用户上传图片 + 可选文字需求
  -> 图像预处理 / 多物体检测或裁剪
  -> image embedding 召回 topK
  -> VLM/OCR 抽取品牌、品类、包装文字、颜色、使用场景
  -> 商品 metadata filter：品类、品牌、预算、库存/可购状态
  -> reranker / LLM grounded explanation
  -> ProductCard + trace
```

优点：

- 视觉召回负责“像不像”，文本和 metadata 负责“是不是用户要的东西”。
- 可以处理“拍这个包装，找同款/替代品”和“拍这个物体，找类似功能商品”两类需求。
- 更容易把失败原因写进 trace：图片识别错、embedding 召回错、metadata 过滤错、rerank 解释错。

缺点：

- 工程量明显高于 text-first。
- 需要决定图片存储、隐私、向量索引、低置信追问和多物体裁剪策略。

#### 4. 特殊精确匹配路线

如果图片里有条形码、二维码、明显品牌 logo、型号、包装文字，应该优先走 OCR / barcode / exact match，而不是只靠相似度。

原因很简单：对包装商品来说，“巴黎欧莱雅 30ml”这类文字线索往往比纯视觉相似度更可靠。

### 科研实践调研

| 工作 | 做法 | 对本项目的启发 |
| --- | --- | --- |
| CLIP | 通过预测 image-caption pair 学习图文共同表示空间；自然语言可以引用视觉概念，并迁移到 OCR、细粒度分类等任务。参考：[CLIP](https://arxiv.org/abs/2103.00020)。 | image-text shared embedding 是拍照找货的基础范式；可用于“图搜图 / 文搜图 / 图文混搜”。 |
| DeepFashion | 服饰检索数据集包含 80 万+ 图片、属性、landmarks 和跨场景对应关系；论文强调属性和 landmarks 有助于服饰识别与检索。参考：[DeepFashion](https://openaccess.thecvf.com/content_cvpr_2016/html/Liu_DeepFashion_Powering_Robust_CVPR_2016_paper.html)。 | 服饰类不是只靠全局相似度，属性、关键区域和场景差异很重要。 |
| Product1M | 面向真实电商的多模态商品检索，包含 100 万+ image-caption pairs，覆盖化妆品、细粒度品类、多商品组合和模糊图文对应；提出跨模态预训练方法。参考：[Product1M](https://arxiv.org/abs/2107.14572)。 | 对本项目尤其相关：美妆包装和 SKU 细粒度差异需要图文共同建模，不能只靠商品标题或单张图。 |
| Visually Similar Products Retrieval for Shopsy | 使用属性分类、triplet ranking、VAE 的多任务方案，并在生产中使用 ANN index；论文强调电商属性能改善视觉搜索，还处理压缩、裁剪、涂画等真实用户图问题。参考：[Shopsy visual retrieval](https://arxiv.org/abs/2210.04560)。 | 这直接支持 hybrid 方案：视觉 embedding + 商品属性 + ANN 检索，而不是单一路线。 |
| PRISM | 面向零售场景的三阶段 hybrid 方法：先用 SigLIP 召回语义相似 topK，再用 YOLO-E 分割去除背景，最后用 LightGlue 做细粒度像素匹配。参考：[PRISM](https://arxiv.org/abs/2509.14985)。 | 如果要做高精度同款识别，后期可能需要“全局语义召回 + 局部/像素级精排”；MVP 阶段不做。 |

科研侧结论：

- 基础范式是 contrastive image-text embedding，例如 CLIP / SigLIP。
- 电商检索不是普通图片检索，商品属性、SKU、包装文字、局部细节和用户实拍噪声都很关键。
- 真实系统往往要结合 ANN 向量索引、属性分类、OCR、检测/裁剪和精排。
- 对当前项目来说，直接做 VLM 文本抽取最便宜；做 image embedding index 更像真正拍照找货；hybrid 最有展示价值但也最费时间。

### 推荐落地方案

本项目当前最适合分三阶段：

#### 阶段 1：Text-first 图片理解 MVP

新增一个图片输入入口，后端接收图片后调用多模态模型抽取结构化线索：

```json
{
  "image_plan": {
    "enabled": true,
    "mode": "image_to_text_retrieval",
    "detected_category": "防晒",
    "detected_brand": "巴黎欧莱雅",
    "visible_text": ["SPF50+", "30ml"],
    "visual_attributes": ["白色瓶身", "泵头包装"],
    "confidence": "medium",
    "needs_clarification": false
  }
}
```

再把这些线索拼成现有 retrieval query，例如：

```text
图片识别线索：巴黎欧莱雅，防晒，SPF50+，30ml，白色瓶身，泵头包装。
用户补充需求：油皮通勤，200元以内。
```

验收重点：

- 能把图片里的品牌/品类/包装文字转成检索条件。
- 能复用现有商品卡和详情页。
- 低置信时追问，例如“我看不清品牌，你是想找防晒还是隔离？”。
- trace 中记录 `image_plan`，但不把用户原图提交到 Git。

#### 阶段 2：小型商品图向量索引

用当前 catalog 的 `image_path` 生成离线 embedding：

```text
data/raw/.../images/*.jpg
  -> image_embedding
  -> data/tmp/image_index.jsonl 或本地 vector index
```

在线时：

```text
uploaded_image -> image_embedding -> topK product_ids -> ProductCard
```

验收重点：

- 上传与 catalog 商品图相近的图片时，topK 包含对应商品。
- 上传不在 catalog 的图片时，不强行编造，给出“当前商品库没有足够相似结果”。
- 相似度只作为召回信号，不作为商品事实。

#### 阶段 3：Hybrid rerank

把阶段 1 和阶段 2 合并：

- image embedding 召回 topK。
- VLM/OCR 抽取品牌、品类、包装文字。
- 用 category / brand / budget / avoid_for 过滤。
- LLM 只负责解释“为什么这些候选和图片线索匹配”，不能编造图片中没有的成分或功效。

### 当前决策

拍照找货 / 多模态路线值得继续调研，也可以作为可选加分路线，但实现优先级应低于当前已经走深的文本 RAG、商品对比和 trace/eval。

建议决策：

- 如果时间有限：只落阶段 1，作为“多模态输入 -> grounded text retrieval”的轻量闭环。
- 如果还有 1-2 天：尝试阶段 2，用现有 `image_path` 建小型本地 image embedding index。
- 如果要做展示亮点：阶段 3 hybrid 是最完整路线，但需要控制 scope，只做 catalog 内检索，不做全网识图。
- 不建议本阶段做：Google Lens 式全网找货、真实同款比价、跨平台商品抓取、复杂图像分割/局部匹配。

## 第三条路线：语音输入 / ASR

### 用户问题

语音输入表面上是“加一个麦克风按钮”，但对购物 Agent 来说，它至少包含三层问题：

1. ASR 层：把用户语音转成文字，是录完后一次性返回，还是说话时实时出 partial transcript。
2. 语义层：转写后的文字能否被现有 Planner 正确理解，例如“第一款和第三款”“不要含酒精”“预算一百五以内”。
3. 安全层：如果用户说的是加购、结算、下单类意图，ASR 错一个数字或商品名就可能执行错 action，因此不能直接自动提交不可逆操作。

用户提到的两个体验参照也有帮助：

- 豆包输入法的体验重点是“边说边出字、标点和停顿处理自然、用户可以继续编辑后再发送”。这可以作为 UI/UX 参考，但不应逆向专有客户端。
- WeFlow 是否内置 Whisper 版本，本项目当前不能直接确认；如果后续要验证，建议只看公开设置、日志、配置和可见网络行为，不做二进制逆向。

### 工程实践调研

| 实践来源 | 现成做法 | 对本项目的启发 |
| --- | --- | --- |
| OpenAI Whisper / Speech-to-text | Whisper 是多语言 ASR，OpenAI 介绍其使用 68 万小时多语言、多任务监督数据训练，并支持转写和翻译；当前 OpenAI Speech-to-text 文档还提供 `gpt-4o-transcribe`、`gpt-4o-mini-transcribe` 等更高质量转写模型。参考：[Introducing Whisper](https://openai.com/index/whisper/) 和 [Speech to text](https://developers.openai.com/api/docs/guides/speech-to-text)。 | 适合“录音后转写”或服务端批量转写；可以用 prompt 提高商品名、品牌名、中文书写风格的稳定性。 |
| OpenAI Realtime transcription | Realtime transcription 用于实时语音转文字；`gpt-realtime-whisper` 面向 live audio 和 transcript deltas，文档明确它与 `whisper-1` 的非原生实时形态不同，并提供 delay 档位做 latency / accuracy tradeoff。参考：[Realtime transcription](https://developers.openai.com/api/docs/guides/realtime-transcription)。 | 如果追求“边说边出字”，应走 realtime transcription/WebSocket/WebRTC，而不是把普通文件转写硬切成小块。 |
| Android `SpeechRecognizer` | Android 系统 API 支持 `RecognitionListener.onPartialResults`，可通过 `RecognizerIntent.EXTRA_PARTIAL_RESULTS` 请求 partial result；结果从 `SpeechRecognizer.RESULTS_RECOGNITION` 读取，置信度字段是可选的。参考：[SpeechRecognizer](https://developer.android.com/reference/android/speech/SpeechRecognizer) 和 [RecognitionListener](https://developer.android.com/reference/android/speech/RecognitionListener)。 | 当前 Android MVP 可以先用系统识别做最低成本入口；缺点是依赖设备服务、系统版本和网络/本地模型能力。 |
| Google Cloud Speech-to-Text | Streaming Recognition 通过 gRPC 双向流处理实时麦克风音频，并能返回 interim / final results；`isFinal=false` 表示中间结果，`stability` 表示 partial 是否可能变化。参考：[Cloud STT requests](https://docs.cloud.google.com/speech-to-text/docs/v1/speech-to-text-requests) 和 [StreamingRecognitionResult](https://docs.cloud.google.com/speech-to-text/docs/reference/rest/v2/StreamingRecognitionResult)。 | 生产型 streaming ASR 通常显式区分 interim 与 final；UI 需要能修正 partial 文本，不要把 partial 当最终指令执行。 |
| Azure Speech SDK | Azure 支持实时 speech-to-text；continuous recognition 需要订阅 `Recognizing`、`Recognized`、`Canceled` 等事件，分别处理 intermediate 和 final result。参考：[How to recognize speech](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/how-to-recognize-speech)。 | 云端 ASR SDK 的常见模式是事件流；Android 如果接云端，也应把 transcript state 作为独立输入状态管理。 |
| 火山 / BytePlus ASR | 火山引擎 / BytePlus 文档提供流式 ASR、音频文件 ASR、WebSocket 协议和 partial / delta 结果；火山 ASR 产品页也强调短语音可“边说话边出文字”。参考：[火山流式语音识别](https://www.volcengine.com/docs/6561/80818?lang=en)、[火山 ASR 产品页](https://www.volcengine.com/product/asr)、[BytePlus ASR-Streaming](https://docs.byteplus.com/zh-CN/docs/byteplusvoice/asrstreaming)。 | 如果项目已有火山/豆包生态和 key，接同一厂商 ASR 的讲述会更顺；但要单独确认账号、权限、SDK 和实时接口成本。 |

工程侧可以先分成三种模式。

#### 1. 录音后转写

```text
用户按住/点击麦克风
  -> Android 录音
  -> 结束录音
  -> 本地或服务端 ASR 返回完整 transcript
  -> transcript 填入输入框
  -> 用户确认后发送
```

优点：

- 最容易实现和调试。
- 可以接 OpenAI Speech-to-text、Whisper、火山音频文件 ASR 或 Android 系统识别。
- ASR 错了用户还能编辑，不会直接触发错误 action。

缺点：

- 体验不如豆包输入法那种实时出字。
- 用户不知道系统是否正在听、是否识别到了内容，需要清晰的录音中状态。

#### 2. 实时 partial transcript

```text
用户开始说话
  -> ASR 返回 partial/delta
  -> 输入框实时显示临时转写
  -> final result 覆盖或合并 partial
  -> 用户确认后发送
```

优点：

- 体验更接近用户期待的“边说边出文字”。
- 用户可以中途看到错字并停下修正。

缺点：

- partial 可能回滚或改变，UI 状态要能处理“临时文本”和“最终文本”。
- 需要处理权限、麦克风占用、网络断开、静音、取消、超时。
- 如果用服务端 streaming，需要 WebSocket/WebRTC、音频编码、VAD 或手动 commit。

#### 3. 实时自动提交

不建议本阶段做。

原因：

- 购物场景里商品名、序号、预算数字、否定词都很关键。
- ASR 把“一百五”识别成“一百”或把“第一和第三”识别成“第二和第三”，后续检索和 action 都会错。
- 即使未来支持加购/下单，也必须先显示 transcript 和 action summary，让用户确认。

### 科研实践调研

| 工作 | 做法 | 对本项目的启发 |
| --- | --- | --- |
| Whisper | 使用大规模多语言、多任务监督数据训练 encoder-decoder Transformer；音频会被切成 30 秒 chunk，支持语言识别、转写、翻译等任务。参考：[Whisper](https://openai.com/index/whisper/)。 | Whisper 很适合鲁棒离线转写，但它的基础架构不是为了最低延迟 streaming 设计；实时体验通常需要专门 realtime 模型或 chunk/VAD 工程。 |
| Streaming E2E ASR for Mobile Devices | Google 研究用 RNN-T 构建端侧 streaming ASR，强调真正有用的移动端 ASR 需要实时解码、长尾鲁棒性、个性化上下文和极高准确率。参考：[Google Research](https://research.google/pubs/streaming-end-to-end-speech-recognition-for-mobile-devices/) 和 [arXiv:1811.06621](https://arxiv.org/abs/1811.06621)。 | “边说边出字”不是简单把模型跑快，而是一整套 streaming 架构；短期不要自己训练端侧 ASR。 |
| 云端 streaming ASR 实践 | Google/Azure/OpenAI/火山都把 realtime ASR 设计成事件流：delta/interim、final/completed、stability/confidence、turn/VAD 等。 | 本项目要研究的是“把 ASR 作为输入模态接进 Agent”，而不是重新发明 ASR 模型。 |

科研侧结论：

- 如果要展示工程深度，重点应放在 input modality + agent correctness，而不是 ASR 模型本身。
- ASR 评测不能只看 WER；购物场景更关心品牌、SKU、价格数字、商品序号、否定词和场景词是否正确。
- 对 code-switching、中文品牌名、外文品牌中文读法，必须做 domain eval，例如“巴黎欧莱雅 / L'Oreal”“安热沙 / Anessa”“第一款和第三款”。

### 当前项目现状

当前 Android Manifest 只有网络权限：

```xml
<uses-permission android:name="android.permission.INTERNET" />
```

也就是说，如果后续实现语音输入，至少需要：

- 增加 `android.permission.RECORD_AUDIO`。
- 在输入栏旁增加麦克风按钮。
- 增加录音 / 识别中 / 可取消 / 识别失败 / 已转写状态。
- 将最终 transcript 填回现有文本输入框，复用当前聊天发送链路。
- trace 记录 ASR 过程，但默认不保存原始音频。

### 推荐落地方案

本项目最合理的分阶段方案如下。

#### 阶段 1：Android 系统 ASR 输入 MVP

目标：最少改动跑通语音入口。

```text
麦克风按钮
  -> Android SpeechRecognizer
  -> partial result 可选显示
  -> final result 填入输入框
  -> 用户手动点击发送
```

验收重点：

- 中文普通口语能转成文本并填入输入框。
- 用户仍然可以编辑后再发送。
- 识别失败、没权限、无语音输入、用户取消都有 UI 状态。
- 不改 Planner/RAG 主链路，只把语音作为输入方式。

#### 阶段 2：服务端 ASR endpoint

目标：避免设备差异，提升 demo 稳定性。

```text
Android 录音
  -> 上传音频到 `/api/asr/transcribe`
  -> 服务端调用 OpenAI / 火山 / 其他 ASR
  -> 返回 transcript + trace_id
  -> Android 填入输入框
```

验收重点：

- 服务端 trace 记录 provider、模型、耗时、错误码、final transcript。
- 可以给 ASR prompt 加商品领域词表，提高品牌/SKU/单位识别。
- 不把音频提交到 Git；如需临时保存，只放 `data/tmp/` 并加忽略规则。

#### 阶段 3：Realtime ASR

目标：实现接近输入法的“边说边出字”。

```text
Android 采集 PCM audio chunk
  -> WebSocket / WebRTC streaming ASR
  -> transcript delta / partial
  -> final transcript
  -> 用户确认发送
```

验收重点：

- partial 文本可以被 final 文本修正。
- UI 明确区分“识别中”和“已确认文本”。
- 长句、停顿、背景噪音、取消、网络断开都有 fallback。
- 不做自动加购/下单；涉及 action 时仍要二次确认。

### Trace / eval 设计

新增 `voice_trace`，可以挂到现有 runtime trace 下：

```json
{
  "voice_trace": {
    "provider": "android_speech_recognizer",
    "mode": "partial_then_final",
    "language_hint": "zh-CN",
    "duration_ms": 4200,
    "partial_count": 6,
    "final_transcript": "帮我对比第一款和第三款",
    "normalized_transcript": "帮我对比第一款和第三款",
    "confidence": null,
    "error": null,
    "submitted": true
  }
}
```

语音 eval 不只测“转写像不像”，而是测最终购物任务是否仍然正确：

| Case | 语音内容 | 重点 |
| --- | --- | --- |
| V1 | 预算一百五以内的防晒 | 数字、预算约束不能错。 |
| V2 | 巴黎欧莱雅和安热沙对比一下 | 中文品牌名和外文品牌中文读法要识别。 |
| V3 | 第一款和第三款帮我对比 | 商品序号不能错。 |
| V4 | 不要含酒精，敏感肌能用的 | 否定词和肤质约束不能丢。 |
| V5 | 早八提神咖啡，方便带去教室 | 口语化场景能进入现有需求解析。 |
| V6 | 把 40ml 那个加入购物车 | action 类意图必须先显示 transcript/action summary，不能自动下单。 |

### 当前决策

语音输入路线值得作为“低风险体验增强 + 可追溯输入模态”保留，但不建议抢当前主线时间去做完整 realtime ASR。

建议决策：

- 如果只剩很少时间：不实现，只保留调研和设计。
- 如果有半天到一天：做阶段 1，Android 系统 ASR，final transcript 填入输入框。
- 如果需要稳定 demo：做阶段 2，服务端录音转写 endpoint，用户确认后发送。
- 如果要冲体验亮点：再做阶段 3 realtime ASR，但必须保留确认发送，不做自动执行 action。

不建议本阶段做：

- 逆向豆包输入法或 WeFlow 客户端。
- 自训练 ASR 模型。
- 未确认 transcript 就自动提交、加购或下单。
- 默认保存用户原始音频。

## 第四条路线：端侧体验 / 性能与交互打磨

### 用户问题

端侧体验听起来像“把 UI 做好看一点”，但在当前项目里，它其实包含三件不同的事：

1. 感知等待：用户点发送后，多久看到商品卡、首个 token、思考中状态和最终结果。
2. 真实性能：Android 是否掉帧、Markdown/表格/商品卡是否重复解析和重组、图片和卡片是否导致滚动卡顿。
3. Agent 链路效率：Planner、retrieval、LLM、guardrail、prompt 组织和流式事件是否能减少无意义等待。

用户提到的“并行”和“prompt 优化”可以这样理解：

- 并行不是把所有东西同时跑，而是把不互相依赖的等待重叠起来。例如 Android UI 渲染和网络读取可以并行；baseline retrieval 和 planner 可以做 speculative 并行；但如果 retrieval 必须依赖 planner 的过滤结果，就不能硬并行。
- prompt 优化不是把提示词写得更玄，而是让输入更短、更稳定、更可缓存、更容易被 eval 验证。例如固定 system prompt 放前面，动态商品资料放后面，减少无关字段，固定输出 schema。

### 工程实践调研

| 实践来源 | 现成做法 | 对本项目的启发 |
| --- | --- | --- |
| Android Compose performance | Compose 会根据参数稳定性决定是否跳过 recomposition；不稳定参数会导致父组件重组时子组件也重组。官方也建议把昂贵计算移出 composable 或用 `remember`，Lazy list 使用稳定 key。参考：[Compose stability](https://developer.android.com/develop/ui/compose/performance/stability) 和 [Compose performance best practices](https://developer.android.com/develop/ui/compose/performance/bestpractices)。 | 聊天消息、商品卡、SKU tab、Markdown AST、对比表格都应有稳定 id 和稳定 UI model；Markdown/表格解析不要在每次 recomposition 里重新跑。 |
| Android coroutines | Android 官方推荐用 Kotlin coroutines 管理异步任务，避免长任务阻塞 main thread；structured concurrency 能让相关任务一起取消，减少泄漏。参考：[Kotlin coroutines on Android](https://developer.android.com/kotlin/coroutines)。 | SSE 读取、图片加载、Markdown 解析、trace 写入都不应阻塞主线程；用户离开页面或重新发送时，要能取消旧请求。 |
| Android benchmarking / JankStats | Macrobenchmark 用于测启动、滚动、动画等用户级交互；JankStats 可以逐帧上报 jank，并带上 UI context；Baseline Profiles 可优化首启和关键交互，官方称常见性能提升约 30%。参考：[Benchmark your app](https://developer.android.com/topic/performance/benchmarking/benchmarking-overview)、[JankStats](https://developer.android.com/reference/androidx/metrics/performance/JankStats)、[Baseline Profiles](https://developer.android.com/topic/performance/baselineprofiles/overview)。 | 端侧优化要先测：聊天滚动、流式插卡、打开详情页、切换 SKU、横/竖表格渲染。否则容易优化错地方。 |
| OpenAI latency optimization | 官方建议减少 token、减少请求、并行化独立步骤、使用 speculative execution、streaming/chunking、展示步骤和 loading state；也提醒不要默认所有事情都交给 LLM，能用传统代码和 UI 表达的就用传统方法。参考：[Latency optimization](https://developers.openai.com/api/docs/guides/latency-optimization)。 | 当前系统已经做了 `products -> token...`，这是很好的感知优化；后续应继续把结构化卡片、对比表格、标准确认语交给代码/UI，而不是全靠 LLM 文本。 |
| Prompt caching | Prompt caching 依赖完全一致的 prompt prefix；静态指令、示例和工具定义应放在前面，用户输入、history、RAG 结果等动态内容放后面。参考：[Prompt caching](https://developers.openai.com/api/docs/guides/prompt-caching)。 | 如果 prompt 很长，应把稳定的系统规则和输出格式固定在前缀，动态商品资料放末尾；这样既更可缓存，也更容易 diff 和评测。 |

工程侧可以归纳成五类优化。

#### 1. 感知性能：先让用户看到进展

当前项目已经有一个关键优势：`products` 事件在 token 前发送。这个设计应该保留，因为它能让 Android 在模型完整回答前就拿到结构化卡片。

后续可以继续做：

- 用户点击发送后立刻进入“发送中 / 思考中”状态。
- 如果有商品卡，优先插入相关卡片，再继续流式展示文本。
- 如果是对比请求，优先展示“正在对比 N 个商品”的轻量状态，再流式出表格。
- 如果 retrieval 为空或低置信，尽早显示澄清问题，而不是等完整长回答。

#### 2. Android 渲染：减少不必要 recomposition

当前 Android UI 已经承载了商品卡、同系列 SKU tab、Markdown、表格和详情页。容易出现的问题是：

- 消息列表新增 token 时，整条消息、所有卡片或整张表格反复重组。
- Markdown 每次 token 更新都重新 parse 全文。
- LazyColumn 没有稳定 key，导致卡片顺序变动时重组过多。
- 商品卡 state 放在父级大状态里，切换一个 SKU tab 触发整屏刷新。

建议：

- 每条 message、每张 ProductCard、每个 variant 都使用稳定 id。
- Markdown parse 结果用 `remember(message.id, finalText)` 或 ViewModel cache；流式中只对正在增长的最后一段做轻量处理。
- ProductCard 内部维护局部 selectedVariant state，避免影响整个消息列表。
- 对比表格使用结构化 UI model，不把大段 Markdown table 当普通文本反复解析。

#### 3. 链路并行：只并行不互相依赖的步骤

可以考虑的并行点：

```text
用户请求
  -> 同时开始：轻量 baseline retrieval + Planner
  -> Planner 成功：使用 planned retrieval / filters
  -> Planner 失败或超时：回退 baseline retrieval
```

这个叫 speculative execution，适合 Planner 经常成功但偶尔慢的场景。注意它不是必做项，只有 trace 显示 Planner/retrieval 是瓶颈时才值得做。

还可以并行：

- Android 收 SSE 的同时渲染已到达 token。
- 后端做 guardrail 允许集合准备时，同时准备 prompt 中的商品摘要。
- 图片预加载与文本渲染分开，不让图片阻塞首屏文字。

不建议并行：

- 让两个 LLM 同时生成两个答案再硬合并。
- 在目标商品未确认时并行生成详情或加购 action。
- 为了并行改乱 trace，导致之后无法复盘是谁出错。

#### 4. Prompt 优化：从“手写玄学”改成“可测配置”

本项目里的 prompt 优化应围绕四个目标：

- 更短：只放回答需要的商品字段，不把完整 raw data 全塞进去。
- 更稳：固定输出规则，例如不要输出 product_id、对比表格按产品列展示、同 SKU 说成同系列规格。
- 更可缓存：静态系统规则在前，动态 history / RAG / product facts 在后。
- 更可评测：每次 prompt 变化都跑固定 eval case，而不是只看一次手测。

可落地做法：

- 把 prompt 拆成 `static_instructions`、`task_policy`、`product_facts`、`conversation_context`。
- 为对比、SKU、购物车 action、语音输入分别写小型 eval case。
- trace 里记录 prompt version、input token、output token、首 token 时间和模型耗时。
- 如果出现“输出 product_id”“比较错第 1 和第 3 个商品”，先加 eval，再改 prompt。

#### 5. 可观测性：把体验问题变成数字

建议新增或扩展一组 client/server timing 字段：

```json
{
  "experience_trace": {
    "request_id": "trace-...",
    "client_send_tap_ms": 0,
    "server_request_start_ms": 42,
    "planner_done_ms": 180,
    "retrieval_done_ms": 260,
    "products_event_ms": 310,
    "first_token_ms": 780,
    "done_ms": 4200,
    "first_card_render_ms": 360,
    "markdown_parse_ms": 14,
    "jank_frames": 0,
    "prompt_version": "comparison_v3",
    "input_tokens": 3200,
    "output_tokens": 680,
    "cached_input_tokens": 1800
  }
}
```

验收时看这些指标：

| 指标 | 含义 |
| --- | --- |
| `products_event_ms` | 商品卡多久到达 Android。 |
| `first_token_ms` | 用户多久看到第一段模型文字。 |
| `first_card_render_ms` | 卡片多久真正渲染出来。 |
| `done_ms` | 完整回答耗时。 |
| `markdown_parse_ms` | Markdown/表格解析是否成为 UI 瓶颈。 |
| `jank_frames` | 流式、滚动、详情页是否卡顿。 |
| `prompt_version` | 哪版 prompt 导致当前效果。 |
| `cached_input_tokens` | prompt caching 是否生效。 |

### 科研实践调研

| 工作 | 做法 | 对本项目的启发 |
| --- | --- | --- |
| Automatic Prompt Engineer (APE) | 把 instruction 当作 program，让 LLM 生成候选 prompt，再用 score function 选择表现最好的 prompt。参考：[Large Language Models Are Human-Level Prompt Engineers](https://arxiv.org/abs/2211.01910)。 | prompt 优化可以变成“候选生成 + eval 打分”，不是靠手感反复改。 |
| DSPy | 把 LM pipeline 抽象成可优化的模块和图，用 compiler 根据指标自动优化 prompt、demo、reasoning/augmentation 组合。参考：[DSPy](https://arxiv.org/abs/2310.03714)。 | 如果后续要系统化优化 Planner/retrieval/answer pipeline，可以借鉴 DSPy 的思想：先定义任务签名和指标，再优化提示。 |
| TextGrad | 用 LLM 提供自然语言反馈，像反向传播一样改进 compound AI system 的组件、prompt 或代码。参考：[TextGrad](https://arxiv.org/abs/2406.07496)。 | 可以把失败 trace 变成“文本梯度”：为什么错、应改哪个规则、改完 eval 是否通过。短期不需要引入框架，但可以借鉴循环。 |
| Speculative decoding | 用小模型或近似模型先生成多个 token，再让大模型并行验证，从而在不改变输出分布的情况下加速解码。参考：[Fast Inference from Transformers via Speculative Decoding](https://arxiv.org/abs/2211.17192)。 | 这是模型服务端优化，不适合本项目自己实现；但它解释了为什么 provider/serving 层能优化 token 延迟，也支持我们在应用层做 speculative retrieval。 |
| vLLM / PagedAttention | 通过更高效管理 KV cache，减少碎片和重复，提升 LLM serving 吞吐。参考：[PagedAttention](https://arxiv.org/abs/2309.06180)。 | 如果未来自部署模型才需要关注；当前使用 API 时更现实的是减少 token、prompt caching、streaming 和 trace。 |

科研侧结论：

- prompt 优化的研究趋势是 metric-driven：先有 eval，再自动或半自动改 prompt。
- 推理加速的研究趋势在模型服务层：KV cache、speculative decoding、batching、PagedAttention。当前 API 项目不应自己做这些底层优化。
- 对当前项目最有价值的是把 trace/eval 和 prompt 版本绑定起来，形成“失败样本 -> prompt/schema 修改 -> regression eval”的闭环。

### 推荐落地方案

#### 阶段 1：先补体验 trace，不急着改架构

目标：知道慢在哪里。

- 后端记录 planner、retrieval、prompt build、LLM first token、LLM done、guardrail latency。
- Android 记录 send tap、products received、first token rendered、first card rendered、detail opened。
- 记录 prompt version、token 数、是否命中缓存字段。

验收重点：

- 一次请求能看出是 Planner 慢、retrieval 慢、LLM 慢，还是 Android 渲染慢。
- 能复盘“为什么用户感觉卡住了”。

#### 阶段 2：低风险 UI 性能优化

目标：不改业务逻辑，只减少卡顿。

- LazyColumn 使用稳定 key。
- Markdown parse / table parse 做 cache。
- 商品卡和详情页使用稳定 UI model。
- SKU tab 的 selected state 局部化。
- 图片加载不阻塞文字和卡片骨架。

验收重点：

- 流式长回答时滚动不卡。
- 表格和商品卡不因为 token 更新反复闪动。
- 打开详情页和切换 SKU 没有明显停顿。

#### 阶段 3：Prompt / schema 优化

目标：减少错答和无效 token。

- 固定 prompt 前缀，动态数据后置。
- 删除 prompt 中不需要给 LLM 看的字段，例如内部 `product_id`，除非用于后端 guardrail。
- 为“不要输出 ID”“第一和第三”“同系列 SKU”“表格按列展示”写 eval。
- 只在 eval 通过后合并 prompt 改动。

验收重点：

- 不再把 product_id 写给用户。
- 指代商品顺序不混乱。
- 表格结构更稳定，少横向拖动。
- token 数下降或首 token 变快。

#### 阶段 4：小范围 speculative 并行

目标：只优化 trace 已证明的瓶颈。

可尝试：

```text
raw_query baseline retrieval
  与 Planner 并行
Planner 成功且未超时 -> planned retrieval
Planner 超时/失败 -> baseline retrieval
```

验收重点：

- 首卡片时间下降。
- 失败时 trace 清楚写出用了 baseline 还是 planned。
- 不能牺牲商品正确性和可追溯性。

### 当前决策

端侧体验 / 性能与交互打磨值得做，但它更适合作为“支撑主线的收尾路线”，不是新的大功能路线。

建议决策：

- 最高优先：体验 trace + prompt/schema eval，因为这直接服务当前对比、SKU、trace 主线。
- 次优先：Android UI 稳定性和 Markdown/表格缓存，因为它能改善 demo 观感。
- 暂缓：复杂并行、自动 prompt optimizer、自部署 LLM serving。
- 不建议本阶段做：为了性能大改架构、引入重型框架、无 trace 的视觉微调、自己实现 speculative decoding 或 vLLM。

## 总体取舍

综合评分收益、工程风险、实现时间和已有完成度，后续不建议平均推进所有路线。更稳的策略是：先把已经走通的“商品对比 / SKU / trace / eval”做深，再用端侧体验和可观测性把 demo 观感补强，最后视时间选择一个新入口或 action mock。

### 实施优先级

| 优先级 | 路线 | 建议 | 评分收益 | 工程风险 | 原因 |
| --- | --- | --- | --- | --- | --- |
| P0 | 商品对比 + SKU + trace/eval 主线 | 必做，先收口 | 高 | 低到中 | 已经最接近完整链路：Planner 识别、商品定位、Markdown 表格、结构化卡片、详情页、trace 和回归 case 都有基础。继续做深最容易证明“不是只做了 UI，而是完成了一条可追溯购物推理链”。 |
| P1 | 端侧体验 / 性能 / prompt-schema 打磨 | 紧接着做 | 中到高 | 低 | 它是所有路线的放大器：首卡片、首 token、Markdown/表格稳定、prompt 不泄露 ID、latency trace、prompt version，都能让现有主线看起来更成熟。 |
| P2 | 购物车 / 下单 Action mock | 有时间就做 mock MVP | 高 | 中到高 | 最像“Agent 能行动”的加分路线。只要严格控制成 mock cart，不接真实支付/库存，就能展示 intent -> SKU 解析 -> cart mutation -> UI 反馈 -> action trace。 |
| P3 | 语音输入 Stage 1 | 可作为低风险加分项 | 中 | 低到中 | Android 系统 ASR 填入输入框实现成本相对低，体验加分明显；但如果只做到语音转文字，链路深度不如购物车。 |
| P4 | 拍照找货 / 多模态 Stage 1 | 最后再考虑 | 中到高 | 高 | 新颖度高，但工程不确定性最大。短期只建议做 text-first VLM/OCR -> 现有 RAG，不建议做完整 image embedding/hybrid。 |

### 推荐实施节奏

```text
第 1 段：收口现有主线
  对比正确性 / SKU 展示 / Markdown 表格 / product_id 不泄露 / 指代 eval / trace

第 2 段：补体验与可观测
  experience_trace / 首 token / 首卡片 / Markdown 表格缓存 / prompt version / 小型回归集

第 3 段：做一个新能力
  优先 mock cart action；如果时间不够，就做语音输入 Stage 1

第 4 段：只做调研或极轻量多模态
  图片上传 -> VLM 抽标签 -> 复用现有检索
```

### 评分取舍判断

1. 深度优先于广度。官方进阶路线更像完整链路，不是功能清单。对比 / SKU / trace/eval 已经走得最深，应优先收口。
2. 可证明优先于“看起来很酷”。端侧 trace、action trace、eval case 能把现场 bug 变成可复盘证据，这比临时多做一个入口更稳。
3. 低风险体验优化应该贴着主线做。Markdown、表格、卡片插入、首 token、首卡片等优化直接改善已有 demo，不会引入新的大范围数据/schema 风险。
4. 新能力只选一个冲刺。购物车 mock 和语音输入都可做，但如果时间紧，优先购物车 mock，因为它展示的是 agent action，而不只是输入方式。
5. 多模态先别重投入。拍照找货最有新颖感，但完整工程链路很长，容易做成“能演示一次，但不够稳定”的功能。

当前最稳的策略是：

```text
继续强化：对比 / SKU / trace / eval
  -> 补体验 trace 和 UI 性能
  -> 优先选择 mock cart action
  -> 时间不足时改做语音输入 Stage 1
  -> 多模态保留调研或轻量 text-first MVP
```
