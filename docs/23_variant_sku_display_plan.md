# SKU 级同系列规格展示方案

日期：2026-06-05

## 问题现象

Android 流式回复中，模型会写出同一商品资料下的两个规格，例如：

- `30ml 水感轻肌款`，价格 `170`
- `40ml 清爽型`，价格 `190`

但商品卡片只展示第一张。用户看到第二段推荐文字后，没有对应的第二个可切换卡片，容易误以为卡片和文字没有对齐。

## 根因

原始数据里 `p_beauty_006` 是一个 parent product，下面有两个 `skus`。当前检索、API 和 Android UI 的卡片粒度原本是 `product_id`，不是 `sku_id`：

- 检索命中的是 parent product。
- `ProductCard` 只带 parent 标题、base price 和图片。
- Android 只能渲染一张商品卡。

这会让“同系列规格对比”的生成文本和“单张 parent 商品卡”的展示粒度不一致。

## 方案

采用“后端按 SKU 展开，前端按同系列堆叠展示”的分阶段 MVP：

1. 后端仍先检索 parent product。
2. 返回 `ProductCard.variants`，每个 variant 对应一个可购买 SKU。
3. 预算过滤按 SKU 价格判断，只保留符合预算的 variants。
4. 生成 prompt 要求把多个 SKU 表达为“同系列规格/款式对比”。
5. Android 普通商品继续展示普通卡；有 variants 的商品展示堆叠式规格卡。
6. 商品详情页提供规格标签切换，价格、规格信息和推荐理由跟随选中 variant 更新。

## 当前边界

- 本阶段不重做 enriched schema，只从 raw `skus` runtime 展开。
- SKU 没有独立图片时复用 parent 图片。
- FAQ、用户评价、注意事项仍作为 parent 共享资料展示。
- 后续如果要更精细地区分“水润/控油”等规格级理由，可以再把 variant 级证据补进 enriched 层。

## 验收标准

- `p_beauty_006` 的 API response 中包含两个 variants：`s_p_beauty_006_1` 和 `s_p_beauty_006_2`。
- `200元以内通勤防晒` 可以展示两个规格；`180元以内通勤防晒` 只展示 `30ml 水感轻肌款`。
- 真实或 mock 生成回答使用“同系列规格/款式”语义，不把两个 SKU 说成无关商品。
- Android 聊天页出现堆叠式同系列规格卡，规格标签可切换。
- 详情页可切换规格，价格、规格信息和推荐理由同步变化。
