# 购买对象上下文切换方案

日期：2026-06-09

## 背景

输入框左侧下拉不应表示“切换不同助手”，而应表示本轮购物是在替谁买东西。

典型场景：

- 给自己买：沿用自己的预算、肤质、尺码、口味、常用地址。
- 给妈妈买：可能有过敏、忌口、护肤禁忌、尺码、收货地址。
- 给爸爸买：可能有品牌偏好、健康限制、服饰尺码、收货地址。

因此这个入口本质是 `recipient context switcher`，切换后应影响 Planner / retrieval / answer / 地址预填，而不是换模型或换助手人格。

## 本轮代码处理

- 输入栏左侧 chip 已用于“切换购买对象上下文”，并显示当前对象名。
- 已实现下拉选择列表与“管理常用对象”弹窗。
- 已接入 3 个后端接口（本地 memory provider）用于对象管理与当前对象切换：
  - `GET /api/user-memory/{user_id}/recipients`
  - `PUT /api/user-memory/{user_id}/recipients`
  - `PUT /api/user-memory/{user_id}/selected-recipient`
- 聊天接口已支持 `recipient_id`（以选中对象 token 透传），用于构建本轮 recipient context。
- 设计目标：后端可完整更新对象信息；前端仅展示/持有最小字段。

## 与用户记忆层的关系

这不是替代 [用户记忆与本地偏好层方案](34_user_memory_profile_plan.md)，而是它的一个前端入口扩展。

建议分层：

```text
当前登录用户 user_id
  -> recipient profiles
       - self
       - mom
       - dad
       - custom recipients
  -> selected_recipient_id
  -> chat request / retrieval / trace
```

`user_id` 表示谁在使用 app；`recipient_id` 表示这次替谁买。

## 数据 Schema 建议

可以把购买对象 profile 存在后端本地 memory profile 中，也可以单独放一个 `recipient_profiles` 文件。P0 建议复用 local memory provider，减少新基础设施。

```json
{
  "schema_version": "0.1",
  "user_id": "local-demo-user",
  "selected_recipient_id": "self",
  "recipients": [
    {
      "recipient_id": "self",
      "display_name": "自己",
      "relationship": "self",
      "constraints": {
        "allergies": [],
        "avoid_terms": [],
        "brand_exclude": [],
        "budget_hint": null
      },
      "preferences": {
        "preferred_categories": [],
        "preferred_tags": [],
        "style_notes": []
      },
      "body_profile": {
        "skin_type": null,
        "shoe_size": null,
        "clothing_size": null
      },
      "shipping": {
        "address_label": null,
        "recipient_name": null,
        "phone": null,
        "address": null
      },
      "updated_at": "2026-06-09T00:00:00+08:00"
    }
  ]
}

## 当前实现后的前后端字段边界（2026-06-09 更新）

### 1) 管理对象列表给前端的数据

后端 `RecipientsResponse` 目前返回的是「管理视图模型」：

- `display_name`（展示名）
- `relationship`（关系）
- `shipping.phone`（联系电话）
- `shipping.address`（地址）

前端不再接收/展示这些字段之外的对象属性（包括 `recipient_id`、`address_label`、`recipient_name`、约束/偏好/身体属性等）。

### 2) 选择对象标识

为了避免把真实 `recipient_id` 泄露到前端：

- `selected_recipient_id` / 列表项 id 采用前端可见 token：`self`、`recipient-0`、`recipient-1` ...
- 后端在应用更新/切换时会映射回真实 `recipient_id`。

### 3) 联系方式字段策略

- 管理页和后端保存时，内部仍可保持其他对象字段更新能力（如约束、偏好、体征信息）。
- 但前端不展示、也不直接传递给前端显示：
  - `shipping.address_label`
  - `shipping.recipient_name`
  - `recipient_id`
  - 约束/偏好/体征等完整 profile 子字段
- 对前端可见与回传的联系人字段只保留：
  - `shipping.phone`
  - `shipping.address`

### 4) 安全边界

- 地址电话不写入 trace。
- `trace` 只记录 `recipient_id`（内部真实 ID）与本轮实际生效字段名。
```

隐私边界：

- 地址、电话、过敏、健康限制都必须由用户显式编辑或显式确认。
- 不从普通聊天里自动推断“妈妈过敏 / 爸爸有疾病”并落库。
- trace 中可以记录 `selected_recipient_id` 和已应用字段名，但不要记录完整地址和电话。

## API 建议

P0 可加三个后端接口：

| 接口 | 用途 |
| --- | --- |
| `GET /api/user-memory/{user_id}/recipients` | 返回常用购买对象列表、当前选中对象、可展示摘要 |
| `PUT /api/user-memory/{user_id}/recipients` | 批量保存设置页编辑结果 |
| `PUT /api/user-memory/{user_id}/selected-recipient` | 切换当前购买对象 |

聊天请求增加：

```json
{
  "user_id": "local-demo-user",
  "recipient_id": "mom",
  "message": "给她买一个不过敏的面霜",
  "history": []
}
```

后端处理：

```text
chat_stream
  -> load_user_memory(user_id)
  -> resolve_recipient_profile(recipient_id or selected_recipient_id)
  -> build recipient_context
  -> merge with current user message
  -> planner / retrieval / answer
  -> trace recipient_memory_trace
```

## Android UI 建议

### 输入栏左侧入口

当前默认显示：

```text
[助手头像] 自己 v
```

P0 点击后弹出小菜单：

- 自己
- 妈妈
- 爸爸
- 管理常用对象

点击对象后：

- 更新本地 UI 当前对象。
- 调 `PUT selected-recipient`。
- 下次发送 chat 时带 `recipient_id`。

### 设置页

现有设置弹窗已经承载 TTS 和无障碍设置，建议不要把购买对象编辑强塞在同一个小弹窗里。P0 可以新增一个入口：

```text
设置
  -> 常用购买对象
```

编辑项：

- 展示名：自己 / 妈妈 / 爸爸 / 自定义。
- 关系：self / parent / partner / child / friend / other。
- 购物约束：过敏、忌口、避雷关键词、预算提示。
- 偏好：常买品类、喜欢风格、尺码/肤质等。
- 收货信息：收件人、手机号、地址、地址标签。

设置保存后：

- 后端保存 recipient profiles。
- 输入栏左侧菜单刷新列表。
- 如果当前选中的对象被删除，回退到 `自己`。

## 多模态相关边界

购买对象上下文本身不需要多模态能力，5.3 AI 朋友可以实现大部分 UI / 后端 / 文档。

仍需要多模态模型或当前更强模型处理的部分：

1. 用户上传图片后，识别商品品类、包装文字、品牌、规格。
2. 把图片识别结果和购买对象约束合并，例如“妈妈对酒精味敏感，所以图片里的护肤品要核对成分和刺激性描述”。
3. 低置信图片识别时追问，而不是把图片线索直接写进妈妈/爸爸的长期 profile。
4. 多模态 trace 只记录图片理解摘要和 recipient_id，不记录原图。

## 给 5.3 AI 朋友的任务包

### 任务 A：前端菜单

- 删除右侧 `RAG` chip 后保持底栏对齐。
- 把左侧 chip 做成 recipient switcher。
- 菜单展示后端返回的 recipient 列表。
- 选择后更新当前 chip 文案。

### 任务 B：设置编辑

- 新增“常用购买对象”设置入口。
- 支持新增、编辑、删除 recipient。
- 支持编辑过敏/避雷/偏好/地址字段。
- 保存后刷新输入栏菜单。

### 任务 C：后端本地存储

- 在 local memory provider 中增加 `recipients` 和 `selected_recipient_id`。
- 增加 recipients API。
- chat request 接收 `recipient_id`。
- trace 增加 `recipient_memory_trace`。

### 任务 D：安全与验收

- 不自动推断敏感健康信息。
- 不把地址电话写进 trace。
- 空 profile 不改变推荐结果。
- 切到妈妈后，妈妈的 `avoid_terms` 能进入 retrieval / answer context。
- 删除当前对象后回退到自己。

## 暂不做

- 真实账号体系。
- 真实地址绑定或下单。
- 从聊天自动抽取父母健康信息并落库。
- 跨设备同步。
- 多模态图搜图索引。
