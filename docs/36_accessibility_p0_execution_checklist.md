# 安卓无障碍 P0 工单执行清单（AI 伙伴执行版）

创建时间：2026-06-09  
用途：从“决策文档”转为“可执行工单”。按此清单可直接逐条实现，不需要额外澄清。

## 0）默认约定

- 仅聚焦本次 P0：语音可控（含详细播报）、状态可见、低视力字号。
- 先不做复杂色觉重构、表格完整无障碍语义、离线 TTS。
- 默认值采用先前计划文件：
  - `ttsEnabled = true`
  - `ttsVerboseMode = false`
  - `ttsSpeechRate = 1.0`
  - `ttsStatusAnnouncementEnabled = true`
  - `fontScaleMode = system`
  - `speechHintVisibility = true`

---

## 1）新增设置数据层（阻塞最小）

- [ ] **T1.1 定义设置键与默认值**
  - 文件：`client/android/app/src/main/java/com/saki/bytedance/ragshopping/TtsSettings.kt`
  - 变更：
    - 新增 `ttsEnabled`、`ttsVerboseMode`、`ttsSpeechRate`、`ttsStatusAnnouncementEnabled`
    - 新增 `fontScaleMode`、`speechHintVisibility`
    - 提供 `StateFlow` / `MutableStateFlow` 或等价可观测状态。
  - AC：
    - 以上字段可读写，持久化后重启生效。
    - 读取缺省值时使用上文默认值。

- [ ] **T1.2 文案与类型约束**
  - 文件：`TtsSettings.kt`
  - 变更：
    - `ttsSpeechRate` 使用受控枚举或常量（`0.75,1.0,1.25,1.5`）。
    - `fontScaleMode` 使用字符串枚举（`system, 1.1, 1.25, 1.5`）。
  - AC：
    - 设置值无效时回退到默认值，不崩溃。

---

## 2）语音开关与详细播报接入

- [ ] **T2.1 引入“语音播报总开关”分支**
  - 文件：`client/android/app/src/main/java/com/saki/bytedance/ragshopping/MainActivity.kt`
  - 变更：
    - 自动播报触发前判断 `ttsEnabled`。
    - 关闭时不自动调用 `speaker.speak`。
  - AC：
    - 切为关闭后，后续新消息不会自动播报。

- [ ] **T2.2 引入“详细播报（Blind-friendly）”分支**
  - 文件：`client/android/app/src/main/java/com/saki/bytedance/ragshopping/TtsSpeaker.kt`
  - 变更：
    - 新增 `speak(message, verboseMode:Boolean, ...)` 文本分支。
    - 详细模式下拼接结构化句式（例如“你收到一条...助手回复：...”）。
  - AC：
    - `ttsVerboseMode=true` 与 `false` 的播报内容明显有“句式长度差异”。

- [ ] **T2.3 语速设置接入**
  - 文件：`TtsSpeaker.kt`
  - 变更：
    - `speak` 前设置 `setSpeechRate(ttsSpeechRate)`。
  - AC：
    - 语速滑块/选择变化后，随后的播报节奏变化可感知。

- [ ] **T2.4 当前条停止仍保留全局设置**
  - 文件：`MainActivity.kt` + `TtsSpeaker.kt`
  - 变更：
    - 停止按钮只标记当前 `messageId` 为已停；不影响 `ttsEnabled`。
  - AC：
    - 停止本条后，下一条新消息仍按 `ttsEnabled` 执行自动播报。

---

## 3）新增设置页（右上角设置入口）

- [ ] **T3.1 入口改为设置**
  - 文件：`client/android/app/src/main/java/com/saki/bytedance/ragshopping/MainActivity.kt`
  - 变更：
    - 顶栏动作按钮文案改为“设置”并跳转到语音与可访问性设置界面。
  - AC：
    - 无障碍/触控可达：按钮可点、状态可见。

- [ ] **T3.2 设置 UI（语音 + 字号）**
  - 文件：同上，新增 composable 页面/弹窗（按现有导航结构实现）
  - 变更：
    - 语音组：`ttsEnabled` 开关、`ttsVerboseMode` 开关、`ttsSpeechRate` 选择器、`ttsStatusAnnouncementEnabled` 开关。
    - 字号组：`fontScaleMode` 单选（system / 1.1 / 1.25 / 1.5）。
    - 提供语音与字号小样本预览文本。
  - AC：
    - 任一设置变更即刻生效（至少下次回复可体现）。
    - 关闭并返回主界面后保持可见。

- [ ] **T3.3 听障友好状态展示开关**
  - 文件：`MainActivity.kt`
  - 变更：
    - 加入 `speechHintVisibility` 作为状态文案显示总开关。
  - AC：
    - 打开后，输入与播放状态提示能稳定显示。

---

## 4）状态提示文字化（听障友好）

- [ ] **T4.1 ASR 与 TTS 状态文案统一**
  - 文件：`client/android/app/src/main/java/com/saki/bytedance/ragshopping/MainActivity.kt`
  - 变更：
    - 在转写开始/成功/失败、播放开始/结束/失败/停止增加可见文案。
    - 与 `ttsStatusAnnouncementEnabled` 挂钩：关则只保留关键最小文本。
  - AC：
    - 用户可不听语音理解完整流程：开始录音、转写中、识别成功、开始播报、已停止。

- [ ] **T4.2 文本提示不依赖颜色**
  - 文件：相关状态提示区域
  - 变更：
    - 对关键状态加入“文字 + 图标/颜色”，非仅颜色表示。
  - AC：
    - 文字可见时也能识别状态，无需依赖色彩区分。

---

## 5）低视力字号与大字号兼容

- [ ] **T5.1 建立字体倍率应用入口**
  - 文件：`client/android/app/src/main/java/com/saki/bytedance/ragshopping/MainActivity.kt`
  - 变更：
    - 计算并应用全局 `fontScaleMode` 缩放系数（推荐在文本样式层统一生效）。
  - AC：
    - `system` 与自定义倍率切换后，主聊天界面文字有可见变化。

- [ ] **T5.2 清理易截断文本**
  - 文件：`MainActivity.kt`
  - 变更：
    - 检查并修正 `maxLines=1` + `softWrap=false` 在消息正文/按钮/标题中的组合。
    - 对关键文案允许换行、允许扩展高度。
  - AC：
    - 在大字号下，主要文本不再出现大量“...”截断。

- [ ] **T5.3 语音状态与设置页布局弹性修复**
  - 文件：同上/相关布局文件
  - 变更：
    - 调整 padding/margin/行高，避免图标与文字重叠。
  - AC：
    - 高字号下控制按钮仍可完整点击，布局不抖动、不重叠。

---

## 6）串联验收（交付前必须通过）

- [ ] **T6.1 端到端冒烟**
  - 场景 A：`ttsEnabled` 开/关切换 + 新消息播报行为。
  - 场景 B：`ttsVerboseMode` 开/关播报文案差异。
  - 场景 C：速度 0.75 / 1.5 切换生效。
  - 场景 D：单条停止后不影响下一条自动播报。
  - 场景 E：`fontScaleMode=1.5` 与系统“大字号”下，关键页面无明显截断。

- [ ] **T6.2 可达性冒烟**
  - 验证：
    - 状态提示可见
    - 关闭语音时仍能理解流程
    - 设置页开关状态可读、可切换、可返回

- [ ] **T6.3 回归清单（快速）**
  - 送达/加载态、快速回复、ASR 录音、商品卡片点击不受影响。

---

## 7）AI 伙伴交付产物要求

每次提交需同步提交以下三类：

1. 变更文件清单（含修改文件名）。
2. 每个 AC 的截图或文字结果（至少 3 组：语音开关、详细播报、字号倍率）。
3. 未完成项说明（如果有，需给出 blocker/原因和下一步）。

---

## 8）建议实现顺序（按依赖）

1. `T1`（设置数据层）  
2. `T3`（入口 + 设置页）  
3. `T2`（语音逻辑）  
4. `T4`（状态提示）  
5. `T5`（字号与布局）  
6. `T6`（验收）

