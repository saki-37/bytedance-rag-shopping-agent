# Android P0 无障碍增强执行计划（可供 AI 伙伴直接执行）

日期：2026-06-09  
适用版本：Android 客户端（Jetpack Compose）

## 目标（P0）

先不追求“全量无障碍改造”，P0 只聚焦三类高价值问题：

1. 盲人用户可控的语音播报（可开可关，可细化播报内容）。
2. 低视力用户的字体可读性（跟随系统大字号 + 应用内字号倍数备选）。
3. 听障用户可理解语音交互流程（完整的文字状态与可见反馈）。

## 结论先行（用户面向）

- 语音播报必须可关闭，避免影响普通用户体验。
- 新增“详细播报”模式，专门给视障用户（打开后读更多上下文）。
- 右上角入口改为“设置”集中配置语音与字号。
- 字号：默认跟随系统；若系统放大不足，用户可在应用内加大 1.1x / 1.25x / 1.5x。

## 一、技术约束与背景前提

1. 系统字体缩放是否生效：只要界面文本使用 `sp`，Android 系统字号会影响显示。  
2. 风险点：`px`、`maxLines = 1`、`softWrap = false`、固定高度容器会让大字号下溢出。  
3. 因此 P0 重点先做“文本弹性布局”而非大规模视觉重构。

## 二、需要新增/变更的持久化字段

建议落地 `SharedPreferences`（或现有设置存储层）：

### 全局语音设置

- `ttsEnabled`：`Boolean`，默认 `true`  
  - 关：不自动播放，不做新播报；手动播放按钮仍可用（可选，见后续）。
- `ttsVerboseMode`：`Boolean`，默认 `false`  
  - 开：对关键消息使用更完整“可听提示句”；  
  - 关：保持简化播报，减少冗余。
- `ttsSpeechRate`：`Float`，默认 `1.0`  
  - 取值建议：`0.75 / 1.0 / 1.25 / 1.5`（对应「慢速/正常/偏快/快」或 slider 档位）
- `ttsStatusAnnouncementEnabled`：`Boolean`，默认 `true`  
  - 开：ASR 与 TTS 的状态变更均有状态播报文案。

### 字号设置

- `fontScaleMode`：`String`，默认 `"system"`  
  - `"system"`：走系统字体缩放（推荐默认）
  - `"1.1"` / `"1.25"` / `"1.5"`：在应用内额外放大倍率

### 听障补强状态提示

- `speechHintVisibility`：`Boolean`，默认 `true`  
  - 开：语音流程中的关键状态始终可见（转写中、识别成功、播放中、播放失败、播放已停止）

## 三、UI 配置页（执行入口）

### 1）入口

- 把右上角动作从当前状态改为“设置”。
- 进入页面名：`AccessibilitySettings`（或同义命名）。

### 2）分组建议

#### A. 语音与无障碍播报

- 开关：`语音播报总开关`（`ttsEnabled`）
- 开关：`详细播报（视障友好）`（`ttsVerboseMode`）
- 滑条/选择器：`语音速度`（`ttsSpeechRate`）
- 开关：`状态播报（听障文字化）`（`ttsStatusAnnouncementEnabled`）

#### B. 字号与可读性

- 切换：`字号策略`
  - `跟随系统字号`
  - `应用大字体 1.1x`
  - `应用大字体 1.25x`
  - `应用大字体 1.5x`
- 展示：在设置页示例文本区预览 1 条样本文案

#### C. 听障友好文案

- 开关：`显示语音状态说明`（`speechHintVisibility`）
- 说明文案示例：
  - “请说出你的问题后点发送”
  - “转写中…”
  - “已转写：...”
  - “正在播放…”
  - “已停止播放”

## 四、各模块落点（给 AI 伙伴）

- `client/android/app/src/main/java/com/saki/bytedance/ragshopping/TtsSettings.kt`
  - 新增/扩展上述字段读写接口，暴露可观测状态（state + setter）。
- `client/android/app/src/main/java/com/saki/bytedance/ragshopping/TtsSpeaker.kt`
  - 接入 `ttsRate`，并在 speak 前动态设置。
  - 支持 `verbose` 下的播报文案生成策略。
  - 保持“当前条停止，不影响全局开关”的行为。
- `client/android/app/src/main/java/com/saki/bytedance/ragshopping/MainActivity.kt`
  - 右上角设置入口改造。
  - 聊天主区接收 `ttsVerboseMode` 与 `ttsSpeechRate`。
  - 实现状态播报（如转写/播放开始/结束）可见/可听。
  - 核实并移除阻塞大字号读取的文本截断。
- `client/android/app/src/main/res/...`（如有）
  - 新增设置页文本、开关、标题、说明文案。
- 可选：新增 `Typography` / 通用 `Text` 样式计算函数
  - 把 `fontScaleMode` 应用到关键文本层级与 Markdown 渲染文本。

## 五、验收标准（P0 明确 AC）

### 语音相关（优先）

1. 有新助手回复且 `ttsEnabled=true` 时，播报触发为“完整助手回复”而非片段文本。  
2. `ttsEnabled=false` 时，自动播报完全关闭。  
3. `ttsVerboseMode=true` 时，播报内容包含角色与结构性提示（如“这是一条助手建议...”）；`false` 时不包含。  
4. 改变 `ttsSpeechRate` 后，下一条播报立即体现（或当前可中断重播）。  
5. ASR/语音相关状态在 UI 上可见：转写中、转写完成、播放中、播放失败、播放已停止。  
6. 关闭 `ttsEnabled` 不影响 UI 信息流，只禁止自动朗读。  

### 字号与低视力（P0）

7. 系统字号变大后，核心文本（标题、消息气泡正文、按钮文案）未明显截断。  
8. `fontScaleMode != system` 时，文本显示明显放大且不破坏行高与点击区域。  
9. 关键页面中不会出现固定宽度/高度导致文字遮挡（重点检查消息列表、设置页、输入区）。

### 听障补强

10. 语音状态可在界面明确读懂（无须听声音也能知道状态）。  
11. 颜色/图标改变时附带文本状态，不出现“只靠颜色沟通意思”的交互提示。

## 六、非 P0（本次不做）

- 全站色觉友好重调色（保留给 P1）。
- 复杂富文本（表格）逐单元可访问语义化（保留给 P2）。
- 自定义音色商用配音（系统 TTS 之外）先不做。

## 七、交付顺序（建议）

1. 先改设置模型（`TtsSettings.kt`）和默认值  
2. 再接右上角“设置”入口  
3. 再接 `ttsEnabled/ttsVerboseMode/ttsSpeechRate` 与现有 `TtsSpeaker`  
4. 再做状态提示文案与听障文本化  
5. 最后做 `fontScaleMode` + 低视力 UI 修复（文本弹性）

## 八、命名与文案建议（可直接复用）

- 语音播报总开关：`语音播报`
- 详细播报：`详细播报（视障友好模式）`
- 语音速度：`语音速度`
- 字号策略：`文本字号`
- 状态播报：`语音状态文字提示`
- 关闭文案：`自动播报已关闭`
- 启用文案：`语音播报已开启，可点击设置选择更详细内容`

