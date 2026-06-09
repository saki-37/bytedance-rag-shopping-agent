# 多模态图片输入 MVP 接入方案

日期：2026-06-09

## 目标

把当前 Android 输入框里的 `拍照 / 从相册选择` 入口真正接到后端，让用户可以附带图片和文字发起导购请求。

P0 只做 `Text-first 图片理解 MVP`：

```text
用户图片 + 用户文字
  -> 后端保存临时图片
  -> 多模态模型抽取结构化 image_plan
  -> image_plan 作为上下文进入 Planner / retrieval
  -> 复用现有商品检索、商品卡片、回答、trace
```

暂不做真正的图像向量相似匹配。图搜图 / image embedding / hybrid rerank 仍作为 P1/P2。

## 为什么 P0 先做 Text-first

既有调研 [进阶路线调研顺序与取舍方案](26_advanced_route_research.md) 已经把拍照找货拆成三条路线：

1. 图片理解：VLM / OCR 把图片转成品牌、品类、颜色、包装文字、使用场景等结构化文本，再走现有 RAG。
2. 图像向量匹配：用户图片和商品图片都转成 embedding，做视觉相似召回。
3. Hybrid：视觉召回 + VLM/OCR + metadata filter + rerank。

P0 先做第 1 条，原因：

- 不需要先为全部商品图建 image embedding index。
- 能直接复用现有 Planner、retrieval、商品卡片和 trace。
- 对包装商品来说，品牌、容量、SPF、型号等可见文字通常比纯视觉相似度更可靠。
- 失败时更容易追问：例如“我看不清品牌，你是想找防晒还是隔离？”。

## 图片数量策略

### P0 决策

UI 和协议都按 `images: list` 设计，但 P0 只允许单张图片。

这样做的好处：

- 前端实现简单，避免多图排序、删除、预览状态复杂化。
- 后端和 trace 从第一天就是 list 结构，后续扩到多图不用改大协议。
- 适合当前导购场景：一张商品图或包装图先跑通闭环。

### P1 扩展

支持最多 3 张图片：

- 多角度商品图。
- 包装正面 + 成分表。
- 购买对象的现有物品图 + 用户补充需求。

多图时需要 image_plan 增加 `image_index`，并在 UI 上展示每张图的识别摘要。

## Android 交互设计

### 选择图片

当前输入框已有：

- `+`
- `拍照`
- `从相册选择`

P0 行为：

1. 用户点击 `拍照` 或 `从相册选择`。
2. 成功拿到图片后，图片缩略图显示在输入框文本区上方。
3. P0 最多保留 1 张；再次选择时提示“替换当前图片”或直接替换。
4. 缩略图右上角提供删除按钮。
5. 点击缩略图打开预览。

### 输入框布局

建议结构：

```text
┌──────────────────────────────┐
│ [图片缩略图 x]                │
│ 文字输入区                    │
│                              │
│ +   [自己 v]          mic  ↑  │
└──────────────────────────────┘
```

如果没有图片，就保持当前纯文本输入框。

### 图片预览

点击缩略图后：

- 打开 full-screen 或 bottom-sheet 预览。
- 展示原图。
- 提供“删除 / 关闭”。
- 不在预览里做编辑、裁剪、标注。

### 发送后用户气泡

用户消息气泡需要显示：

```text
[用户上传图片缩略图]
用户输入文字
```

图片应在文字上方，点击可预览。

如果用户只发图片不写文字：

- P0 允许发送。
- 后端用图片理解结果构造 query。
- 如果 image_plan 低置信，助手先追问。

## 推荐的前后端协议

不要把现有 `/api/chat/stream` 改成 multipart SSE。P0 建议做两步：

```text
1. Android 先上传图片 -> 后端返回 image_id
2. Android 调现有 /api/chat/stream -> JSON 里带 image_ids + message
```

这样可以复用现有 JSON 请求和 SSE 流。

### 新增图片上传接口

`POST /api/multimodal/images`

请求：

```text
multipart/form-data
- file: image/jpeg 或 image/png
- user_id: local-demo-user
- conversation_id: android-demo
```

返回：

```json
{
  "image_id": "img_20260609_abcd1234",
  "mime_type": "image/jpeg",
  "width": 1080,
  "height": 1440,
  "size_bytes": 245000,
  "preview_url": "/api/multimodal/images/img_20260609_abcd1234/preview",
  "expires_at": "2026-06-10T00:00:00+08:00"
}
```

存储建议：

```text
data/tmp/user_uploads/{user_id}/{image_id}.jpg
```

`data/tmp/` 不进入 Git。

### 扩展 ChatRequest

在 `server/app/models.py` 的 `ChatRequest` 增加：

```python
class ChatImageRef(BaseModel):
    image_id: str
    mime_type: str | None = None
    source: Literal["camera", "gallery", "unknown"] = "unknown"

class ChatRequest(BaseModel):
    message: str = ""
    images: list[ChatImageRef] = Field(default_factory=list)
    user_id: str | None = None
    recipient_id: str | None = None
    conversation_id: str | None = None
    history: list[ChatMessage] = Field(default_factory=list)
```

注意：如果 `images` 非空，`message` 可以为空；否则仍要求 message 非空。

Android 请求：

```json
{
  "user_id": "local-demo-user",
  "recipient_id": "self",
  "conversation_id": "android-demo",
  "message": "帮我找类似但适合油皮的",
  "images": [
    {
      "image_id": "img_20260609_abcd1234",
      "mime_type": "image/jpeg",
      "source": "gallery"
    }
  ],
  "history": []
}
```

## 后端处理链路

### P0 主链路

```text
chat_stream
  -> resolve_user_id / recipient_id
  -> load image refs
  -> call multimodal provider
  -> build image_plan
  -> emit image_understanding event or quick_reply update
  -> merge image_plan + user message + recipient context
  -> build_planned_retrieval_message
  -> retrieve
  -> stream answer
  -> trace
```

### image_plan schema

建议新增：

```json
{
  "image_plan": {
    "enabled": true,
    "mode": "image_to_text_retrieval",
    "images": [
      {
        "image_id": "img_20260609_abcd1234",
        "image_index": 0,
        "detected_category": "防晒",
        "detected_brand": "巴黎欧莱雅",
        "visible_text": ["SPF50+", "PA++++", "30ml"],
        "visual_attributes": ["白色瓶身", "泵头包装", "蓝色标签"],
        "possible_use_cases": ["通勤防晒", "户外防晒"],
        "uncertain_fields": ["具体系列名"],
        "confidence": "medium",
        "needs_clarification": false,
        "clarification_question": null
      }
    ],
    "retrieval_terms": [
      "防晒",
      "巴黎欧莱雅",
      "SPF50+",
      "30ml",
      "白色瓶身"
    ],
    "query_text": "图片识别线索：防晒，巴黎欧莱雅，SPF50+，PA++++，30ml，白色瓶身，泵头包装。用户补充需求：帮我找类似但适合油皮的。",
    "confidence": "medium",
    "needs_clarification": false
  }
}
```

### Planner 输入

不要让 Planner 直接看原图。Planner 只接收 `image_plan.query_text` 和原始用户文字。

示例：

```text
用户原始请求：帮我找类似但适合油皮的
图片识别线索：防晒，巴黎欧莱雅，SPF50+，PA++++，30ml，白色瓶身，泵头包装。
当前购买对象：自己
```

然后继续沿用现有：

```text
build_planned_retrieval_message
  -> retrieve
  -> stream_answer
```

### 低置信处理

如果满足任一条件，应先追问或弱化检索：

- `confidence = low`
- `detected_category = null`
- 图片里出现多个商品且无法判断主商品
- 用户没有文字补充，图片又无法识别品类
- 可见文字和视觉类别冲突

追问示例：

```text
我能看到这像是护肤/防晒类包装，但品牌和具体系列不清楚。你是想找同款，还是找适合相同场景的替代品？
```

## SSE / 思考气泡设计

用户希望“图片第一步得到的信息可以先返回给用户，作为思考气泡里的内容”。P0 可以新增 SSE 事件：

```text
event: image_understanding
data: {
  "trace_id": "...",
  "text": "我先看到了：防晒、SPF50+、30ml、白色泵头包装；品牌可能是巴黎欧莱雅。",
  "image_plan": {...},
  "ephemeral": true
}
```

Android 处理：

- 作为 assistant ephemeral bubble 显示。
- 不进入 chat history。
- 最终回答仍由正常 token stream 生成。

如果不想新增事件，也可以复用 `quick_reply`：

```json
{
  "source": "image_understanding",
  "ephemeral": true,
  "text": "我先看到了：防晒、SPF50+、30ml..."
}
```

建议 P0 用新增事件，语义更清晰；如果 5.3 朋友想少改前端，可以先复用 `quick_reply`。

## Android 数据模型建议

新增本地状态：

```kotlin
data class PendingInputImage(
    val localUri: Uri,
    val imageId: String? = null,
    val source: ImageSource,
    val uploadState: UploadState,
    val error: String? = null,
)

enum class ImageSource { Camera, Gallery }
enum class UploadState { LocalOnly, Uploading, Uploaded, Failed }
```

`ChatMessage` 可扩展：

```kotlin
data class ChatImage(
    val imageId: String?,
    val localUri: String?,
    val previewUrl: String?,
)

data class ChatMessage(
    ...
    val images: List<ChatImage> = emptyList(),
)
```

P0 注意：

- 用户气泡用 `localUri` 显示即可。
- 后端返回的 `preview_url` 可后续用于跨设备或重启恢复。
- 不要把本地图片复制进 Git-tracked 目录。

## 多模态 Provider 设计

新增薄接口：

```python
class MultimodalProvider(Protocol):
    def analyze_images(
        self,
        images: list[UploadedImage],
        user_message: str,
        recipient_context: str | None = None,
    ) -> ImagePlan:
        ...
```

Provider 配置：

```env
MULTIMODAL_PROVIDER=disabled
MULTIMODAL_MODEL=
MULTIMODAL_MAX_IMAGES=1
MULTIMODAL_TIMEOUT_SECONDS=20
MULTIMODAL_UPLOAD_DIR=data/tmp/user_uploads
```

P0 provider：

- `disabled`：没有图片理解，返回“图片理解未启用”。
- `mock`：用于 UI smoke，固定返回 image_plan。
- `vlm`：真实调用支持图片输入的模型。

注意：如果 Spark 5.3 不支持图片 / 视频输入，不要把它作为 `vlm` provider。它可以接手 UI、后端存储、协议、trace，但不能完成真实 `analyze_images`。

## Trace 设计

runtime trace 增加：

```json
{
  "multimodal_trace": {
    "enabled": true,
    "provider": "vlm",
    "image_count": 1,
    "image_ids": ["img_20260609_abcd1234"],
    "image_plan": {...},
    "latency_ms": 1320,
    "fallback": null
  }
}
```

隐私规则：

- trace 记录 `image_id`，不记录 base64，不记录本地绝对路径。
- 可记录识别出的标签、可见文字、置信度。
- 不把用户上传原图提交进 Git。
- 如果图片可能包含人脸、地址、手机号等敏感信息，image_plan 只写“检测到潜在敏感内容”，不展开原文。

## 与购买对象上下文的关系

如果已接 [购买对象上下文切换方案](38_recipient_context_switch_plan.md)，图片理解结果应该和 `recipient_id` 合并。

示例：

```text
图片：一瓶面霜，VLM 识别到“修护、面霜、含香精不确定”
购买对象：妈妈，avoid_terms=["酒精味太重", "强刺激"]
用户文字：给她买个类似的
```

Planner 输入应变成：

```text
图片识别线索：面霜、修护、白色罐装，品牌不确定。
购买对象约束：妈妈，避开酒精味太重、强刺激。
用户补充需求：给她买个类似的。
```

但不要把图片里的猜测自动写入妈妈的长期 profile。

## 需要当前更强模型处理的部分

这些部分需要真实多模态模型或具备图像理解能力的模型：

1. 根据图片抽取 `image_plan`。
2. 区分“图片里实际可见文字”和“模型根据外观猜测的属性”。
3. 判断低置信、多个物体、识别冲突时是否追问。
4. 图片理解结果和购买对象约束的合并策略。
5. 后续如果做 P1/P2，再设计 image embedding / hybrid rerank。

## 可以交给 5.3 AI 朋友的任务包

### 任务 A：Android 图片输入 UI

- Pending image state。
- 输入框上方缩略图展示。
- 点击缩略图预览。
- 删除/替换图片。
- P0 限制最多 1 张。
- 发送后用户气泡显示图片在文字上方。

### 任务 B：Android 上传与发送

- 新增 `uploadImage(file)`。
- 发送前如果有本地图片，先上传拿 `image_id`。
- `streamChat` payload 增加 `images`。
- 处理上传失败、重试、删除。

### 任务 C：后端图片上传

- 新增 `POST /api/multimodal/images`。
- 校验 MIME、大小、数量。
- 保存到 `data/tmp/user_uploads/`。
- 返回 `image_id` 和 `preview_url`。
- 增加预览接口。

### 任务 D：ChatRequest 与链路

- `ChatRequest` 增加 `images`。
- 支持 `message` 为空但 `images` 非空。
- chat_stream 中加载 image refs。
- 如果 provider disabled，返回明确错误或追问，不 silent fail。

### 任务 E：SSE 与气泡

- 新增 `image_understanding` event，或先复用 `quick_reply`。
- Android 显示 ephemeral image understanding bubble。
- 不把该气泡写入 history。

### 任务 F：Trace 与文档

- 增加 `multimodal_trace`。
- 补 `docs/04_api_contract.md`。
- 补 smoke 测试步骤。
- 明确隐私边界。

## 验收标准

### P0 必须过

1. 从相册选择 1 张图后，缩略图显示在输入框上方。
2. 点击缩略图能预览。
3. 删除后可回到纯文本状态。
4. 发送后用户气泡显示图片 + 文字。
5. 后端收到 image_id 和文字。
6. 多模态 provider 返回 image_plan。
7. 前端出现图片理解思考气泡。
8. 最终回答仍能返回商品卡片。
9. trace 中有 `multimodal_trace.image_plan`。
10. 原图不进入 Git。

### P0 可降级

如果真实 VLM provider 暂时不可用：

- `mock` provider 可以验证 UI / 上传 / SSE / trace。
- 但 Demo 时必须说明“图片理解为 mock”，不能宣称真实多模态识别已接通。

## 不做范围

- 多张图片复杂排序。
- 图片裁剪、标注、局部框选。
- 图像 embedding index。
- 视觉相似商品召回。
- Google Lens 式全网找货。
- 视频理解。
- 自动把图片里的敏感信息写入长期记忆。

## 建议实施顺序

1. Android pending image UI：缩略图、预览、删除。
2. 后端图片上传接口。
3. Android 上传图片拿 image_id。
4. ChatRequest 增加 `images`。
5. mock multimodal provider 先打通全链路。
6. 新增 `image_understanding` SSE 或复用 quick_reply。
7. 接真实 VLM provider。
8. image_plan 进入 Planner / retrieval。
9. trace 和文档补齐。
10. 最后再考虑 P1 image embedding。
