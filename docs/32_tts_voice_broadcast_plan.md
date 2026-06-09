# TTS 语音播报方案记录

日期：2026-06-09

用途：记录 AI 回复语音朗读的产品交互、技术选型、确认路径和第一版实施拆解。

状态更新：TTS 已进入 Android 第一版实现，关键文件为 `TtsSpeaker.kt`、`TtsSettings.kt` 和 `MainActivity.kt` 中的播报控制。最终提交口径应写成“Android 系统 TTS 已接入，需设备中文语音引擎验证”，不要再写成只停留在方案阶段。

## 一句话目标

给当前 Android 导购助手补上 **AI 回复语音朗读**：用户可以默认听到助手回复，也可以关闭自动朗读；正在朗读时助手头像有轻量说话动画，用户可以停止当前这一段，但不改变下一条回复的全局播报偏好。

## 当前项目上下文

现有 Android 端已经具备：

- 原生 Kotlin + Jetpack Compose 聊天界面。
- AI 回复按 SSE token 流式展示，完成后进入稳定消息态。
- `guide_assistant.png` 助手头像。
- 语音输入/ASR 第一版：输入栏录音、`VoiceWaveform` 波形、后端 `/api/asr/transcribe`。

TTS 和 ASR 应该是两条相邻但独立的体验：

- ASR：用户说话 -> 转成输入文本 -> 用户确认发送。
- TTS：AI 回复完成 -> App 朗读助手回复 -> 用户可停止当前段。

第一版不要让 TTS 占用 ASR 的录音状态，也不要把 TTS 放进后端 RAG 主链路。

## 产品交互模型

### 全局偏好

设置项建议：

| 设置 | 第一版默认 | 说明 |
| --- | --- | --- |
| 自动朗读 AI 回复 | 开 | Demo 场景更能体现语音导购；用户可关闭 |
| 声音偏好 | 系统默认 | 后续可扩展为女声优先、男声优先 |
| 语速 | 标准 | 第一版可先不暴露，代码里保留默认 rate |

“自动朗读 AI 回复”控制后续每条完整 AI 回复是否自动播放。

### 单条控制

正在朗读某条助手消息时：

1. 助手头像出现轻量“说话中”动画。
2. 用户点头像或旁边停止按钮，停止 **当前这一条回复**。
3. 这次停止不等于关闭全局自动朗读；下一条 AI 回复仍按全局偏好播放。

如果全局自动朗读关闭：

1. AI 回复只显示文字。
2. 可以在助手消息旁保留一个轻量朗读按钮，允许用户手动播放单条消息。

### 状态边界

- AI 正在 streaming 时不朗读，避免读到半句、被 guardrail 改写或产品卡片还没落位。
- 收到 `done`、`isLoading=false` 后再朗读最后一条完整助手消息。
- 新一轮用户发送时，应停止正在播报的上一条回复，避免旧内容和新请求混在一起。
- 错误消息不自动朗读，除非后续明确要做无障碍兜底。

## 技术选型建议

### 第一版：Android 系统 TTS

推荐先用 Android 原生 `android.speech.tts.TextToSpeech`。

原因：

1. 当前客户端是原生 Android，系统 TTS 不需要新增后端接口。
2. 不需要新增网络依赖或音频文件缓存。
3. 可以直接用 `speak()` 播放、`stop()` 停止当前播报、`shutdown()` 随生命周期释放。
4. 可以用 `getVoices()` / `setVoice()` 尝试选择可用中文声音。
5. 足够支撑“语音导购体验”的第一版演示。

注意：

- Android 官方文档要求 TextToSpeech 初始化完成后才能合成语音；不再使用时要 `shutdown()`。
- Android 11+ 如果要查询 TTS 服务，应在 manifest `queries` 中声明 `android.intent.action.TTS_SERVICE`。
- Android `Voice` 不保证提供稳定的男声/女声 metadata；“男声优先/女声优先”只能做 best-effort，找不到合适 voice 时回退系统默认，并可用轻微 pitch 调整兜底。

参考：

- Android TextToSpeech API：https://developer.android.com/reference/android/speech/tts/TextToSpeech

### 第二阶段候选：端侧开源 TTS

如果系统 TTS 音色不够稳定或评审设备差异太大，可以调研端侧离线方案。

候选：

1. `sherpa-onnx`
   - 有 Android TTS engine / Android 构建路径。
   - 适合做离线端侧 TTS。
   - 需要确认中文模型、APK 体积、license、集成复杂度和真机性能。
   - 参考：https://k2-fsa.github.io/sherpa/onnx/tts/apk-engine.html
2. Piper
   - 本地神经 TTS，常用于 CPU/边缘设备。
   - 原 `rhasspy/piper` 仓库已归档并提示迁移，适合作为后端 sidecar 候选，不建议第一版直接嵌进 APK。
   - 参考：https://github.com/rhasspy/piper

第一版不推荐 Coqui / XTTS / voice cloning 方向，因为依赖重、模型大、移动端集成和授权边界都更复杂，和当前“轻量语音导购”目标不匹配。

## 需要确认的问题

进入代码实现前，建议先做一轮设备确认。

### 1. 系统 TTS 可用性

在目标模拟器或真机上确认：

- 是否存在中文 TTS engine。
- `Locale.CHINA` / `Locale.SIMPLIFIED_CHINESE` 是否可用。
- `getVoices()` 中是否有本地中文 voice，是否需要网络。
- 语音质量是否能接受。
- `stop()` 是否能稳定中断当前 utterance。

### 2. 声音偏好可行性

确认设备返回的 voice 信息里是否能区分：

- voice name 是否包含 `female`、`male`、`woman`、`man` 等可用线索。
- voice locale 是否为 `zh-CN` 或中文相关 locale。
- voice 是否需要网络。
- 若无法区分男女声，是否接受：
  - 系统默认。
  - 女声优先/男声优先仅作为 best-effort。
  - pitch fallback：女声偏高一点，男声偏低一点，但幅度要保守。

### 3. 回复文本清洗

TTS 不应该直接朗读 Markdown 原文。

需要确认清洗规则：

- 去掉 `#`、`**`、反引号等 Markdown 标记。
- 表格内容第一版可以转成简短摘要，或直接跳过表格符号。
- 去掉内部商品 ID，例如 `p_beauty_001`。
- 将 bullet 和换行转成自然停顿。
- 商品价格、预算、型号保留。
- 超长回复按句子切段播放。

## 第一版实施拆解

### 文件建议

新增：

- `client/android/app/src/main/java/com/saki/bytedance/ragshopping/TtsSpeaker.kt`
  - 封装 `TextToSpeech` 初始化、voice 选择、speak、stop、shutdown。
  - 暴露播放状态：`Idle / Initializing / Speaking(messageId) / Error`。
- `client/android/app/src/main/java/com/saki/bytedance/ragshopping/TtsSettings.kt`
  - 保存全局设置：自动朗读开关、声音偏好。
  - 第一版可用 `SharedPreferences`，后续再换 DataStore。

修改：

- `Models.kt`
  - 增加 TTS 设置枚举，例如 `TtsVoicePreference.SystemDefault / FemalePreferred / MalePreferred`。
- `MainActivity.kt`
  - 在 `ShoppingAgentApp` 中初始化 `TtsSpeaker`。
  - 监听最新完整助手消息，触发自动朗读。
  - 把当前 `speakingMessageId` 传给 `MessageBubble`。
  - 在助手头像处显示说话动画和停止交互。
  - 增加设置入口或轻量设置面板。
- `AndroidManifest.xml`
  - 增加 TTS service query，便于 Android 11+ 查询系统 TTS 服务。

### 播放触发逻辑

建议条件：

```text
自动朗读开启
AND 当前不在 loading
AND 最新消息是 Assistant
AND 最新消息 content 非空
AND 这条 messageId 没有自动朗读过
AND 这条 messageId 没有被用户单条停止过
```

触发时：

```text
cleanText = ttsReadableText(message.content)
speaker.speak(messageId, cleanText)
```

停止当前段：

```text
speaker.stop()
markStoppedForMessage(messageId)
```

注意：`markStoppedForMessage` 只影响当前 messageId，不修改全局设置。

### UI 动画

第一版建议低成本实现：

- 头像外圈：`rememberInfiniteTransition` 做 0.92 -> 1.08 的 scale / alpha 脉冲。
- 小波形：复用现有 `VoiceWaveform` 的视觉语言，但不需要真实音量，只做循环高度。
- 停止按钮：正在朗读时展示小 `X` 或 stop 状态；点击停止当前段。

可以先不引入 Lottie、Rive 或复杂音频可视化库。

## 验收标准

第一版完成后至少验证：

1. App 打开后第一条欢迎语如果符合默认开关，可以朗读；如果觉得打扰，也可只从用户触发后的 AI 回复开始朗读。
2. 发送一条 query，等待 AI 完整回复后自动朗读。
3. 朗读中点助手头像或停止按钮，当前回复立即停止。
4. 停止当前回复后，再发下一条 query，下一条仍会自动朗读。
5. 在设置中关闭自动朗读后，新回复不再自动播放。
6. 关闭自动朗读后，手动朗读单条消息仍可工作。
7. 进入商品详情弹窗、返回、旋转屏幕或退出页面时不会残留播放。
8. ASR 录音/转写和 TTS 播报状态不会互相卡住。

## 暂定结论

先按 Android 系统 TTS 做最小闭环：全局自动朗读开关、完整助手回复后播报、当前条停止、头像说话动画、声音偏好 best-effort。等目标设备上确认系统 TTS 音色和中文支持后，再决定是否需要 sherpa-onnx 或 Piper 这类开源 TTS 方案。
