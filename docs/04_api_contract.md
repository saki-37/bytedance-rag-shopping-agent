# API 契约

## GET `/health`

用于客户端和脚本检查后端是否可用。

响应：

```json
{
  "status": "ok",
  "catalog_size": 5,
  "mock_llm": true
}
```

## POST `/api/chat/stream`

SSE 流式聊天接口。

请求：

```json
{
  "message": "我是油皮，想要200元以内的通勤防晒",
  "conversation_id": "local-demo",
  "history": [
    {"role": "user", "content": "我想找防晒"},
    {"role": "assistant", "content": "你更在意通勤还是户外？"}
  ]
}
```

事件类型：

- `status`：阶段状态，`retrieving` 或 `generating`。
- `products`：本轮召回并展示的商品卡片。
- `token`：模型输出文本片段。
- `done`：流结束。
- `error`：可恢复错误。

`products` 事件示例：

```json
{
  "products": [
    {
      "product_id": "p_beauty_006",
      "title": "巴黎欧莱雅新多重防护隔离露水感轻薄高倍防晒修护提亮30ml",
      "brand": "巴黎欧莱雅",
      "category": "美妆护肤",
      "sub_category": "防晒",
      "price": 170.0,
      "image_path": "1_美妆护肤/images/p_beauty_006_live.jpg",
      "tags": ["油皮", "通勤", "防晒"],
      "reason": "SPF50+ PA++++，质地轻薄，价格在200元以内。"
    }
  ]
}
```

约束：

- 商品卡片中的价格、品牌、标题、图片路径必须来自数据源。
- 模型只能解释已召回商品，不允许编造优惠、库存、价格或未提供功效。
