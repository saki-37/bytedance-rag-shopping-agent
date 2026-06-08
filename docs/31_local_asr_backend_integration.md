# 本地 ASR 后端接入方案

日期：2026-06-08

用途：给后续接手的 AI 工程伙伴说明，如何把本机 FunASR 音频转文字能力接进当前 ByteDance RAG Shopping Agent：Android 端录音，FastAPI 后端接收音频，本地 ASR 转文字并返回给前端。

## 背景

当前项目已经是本地前后端闭环：

- Android 原生客户端：`client/android/`，Kotlin + Jetpack Compose + OkHttp。
- FastAPI 后端：`server/app/`，已有 `/api/chat/stream`、`/api/debug/retrieve`、`/api/feedback`。
- 后端现有 venv：`server/.venv`，Python `3.13.2`。
- 已验证的本地 ASR 实验环境：`/Users/jia/Documents/个人工具/audio-transcription-lab/`，Python `3.11.4`，FunASR `1.3.9`，已预热 `iic/SenseVoiceSmall + fsmn-vad`。

这次不要把它理解成“个人批量转写脚本”，而是把 ASR 变成后端能力：

```text
Android 录音 -> 上传音频文件 -> FastAPI 后端 -> 本地 ASR -> 返回 text -> Android 填入输入框或直接发起 chat
```

## 推荐结论

第一版推荐做 **ASR sidecar 服务 + RAG 后端代理接口**，不要把 FunASR 直接装进现有 `server/.venv`。

原因：

1. 当前后端是 Python 3.13，FunASR / PyTorch 栈在本机已经用 Python 3.11 跑通；直接混进 3.13 风险更高。
2. ASR 模型大约 900MB，加载慢、占内存，和 RAG 后端同进程会让主服务启动和调试变重。
3. Sidecar 能把重依赖、模型缓存、长音频处理隔离开；RAG 后端只需要一个轻量 HTTP client。
4. 未来如果确认稳定，再考虑合并进同一个 FastAPI app 或改成后台 job queue。

## 第一版接口契约

### Android 调 RAG 后端

新增：

```text
POST /api/asr/transcribe
Content-Type: multipart/form-data
```

请求字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `file` | file | 是 | Android 录音文件，建议 `.m4a` / AAC |
| `profile` | string | 否 | 默认 `bilingual`，中英混合先用它 |
| `hotword` | string | 否 | 可选热词，例如商品名、人名、项目词 |
| `conversation_id` | string | 否 | 方便 trace 归档 |

响应：

```json
{
  "ok": true,
  "text": "我想找一款适合油皮通勤的防晒，预算两百以内。",
  "raw_text": "我想找一款适合油皮通勤的防晒预算两百以内",
  "profile": "bilingual",
  "language": "mixed",
  "duration_ms": 5230,
  "asr_trace_id": "asr_20260608_160000_xxxx",
  "segments": [],
  "punctuation_applied": true,
  "punctuation_model": "ct-punc-c",
  "error": null
}
```

错误响应仍保持 JSON，不要让 Android 端只拿到 HTML/traceback：

```json
{
  "ok": false,
  "text": "",
  "raw_text": null,
  "profile": "bilingual",
  "language": "unknown",
  "duration_ms": null,
  "asr_trace_id": "asr_20260608_160000_xxxx",
  "segments": [],
  "punctuation_applied": false,
  "punctuation_model": null,
  "error": "ASR service busy"
}
```

### RAG 后端调 ASR sidecar

Sidecar 本地监听：

```text
http://127.0.0.1:8765/transcribe
```

RAG 后端的 `/api/asr/transcribe` 负责：

1. 接收 Android `UploadFile`。
2. 保存到 `data/tmp/asr/uploads/`。
3. 调用 `127.0.0.1:8765/transcribe`。
4. 把 sidecar 返回的文字透传给 Android。
5. 写入轻量 trace，不把音频提交进 Git。

## 后端实现建议

### 1. ASR sidecar

建议在 `audio-transcription-lab` 里新增一个轻量服务，例如：

```text
/Users/jia/Documents/个人工具/audio-transcription-lab/asr_service.py
```

职责：

- 启动时或第一次请求时加载 `AutoModel`。
- 优先使用本地缓存路径：
  - `models/modelscope/models/iic/SenseVoiceSmall`
  - `models/modelscope/models/iic/speech_fsmn_vad_zh-cn-16k-common-pytorch`
- 用 `SenseVoiceSmall + fsmn-vad` 做默认 `bilingual` profile。
- 对返回文本做 `rich_transcription_postprocess`，去掉 `<|zh|>`、情绪等模型标签。
- CPU 本地推理先用单并发：`asyncio.Semaphore(1)` 或同步队列，避免两个长音频同时抢内存。

可以复用已验证脚本：

```text
/Users/jia/Documents/个人工具/audio-transcription-lab/scripts/transcribe.py
```

第一版不要做流式 ASR，先做文件级非流式：

```text
音频文件 -> 文本
```

### 2. RAG 后端代理

在当前后端中新增：

```text
server/app/asr_client.py
server/app/asr_routes.py
```

或直接先放进 `server/app/main.py`，但长期建议拆文件。

依赖：

```text
python-multipart
```

FastAPI 接收文件需要它。这个依赖很轻，可以加到 `server/requirements.txt`；不要把 `funasr`、`torch` 直接加进 `server/requirements.txt`，除非决定放弃 sidecar。

实现要点：

- 文件大小先设保守上限，例如 50MB 或 100MB。
- 保存路径用 `data/tmp/asr/uploads/`，该目录应被 `.gitignore` 覆盖。
- 请求 sidecar 的 timeout 要比 chat 长，先设 180s 或 300s。
- 返回 response model，避免 Android 端解析散乱字段。
- 写入 trace：文件名、大小、profile、latency、成功/失败、错误，不记录 API key，不把原始音频长期保留。

### 3. Android 端

第一版交互：

1. 输入框旁加一个录音按钮。
2. 按住或点击开始录音，松开或再次点击结束。
3. 用 `MediaRecorder` 录成 `.m4a` / AAC。
4. OkHttp `MultipartBody` 上传到 `/api/asr/transcribe`。
5. 成功后把 `text` 填入当前输入框。
6. 用户确认后再发送到 `/api/chat/stream`。

不要第一版就自动发送给 chat。先让用户看到转写文本，可以手动改错；这对中文商品名、预算、人称指代更安全。

本地地址：

- Android Emulator 访问宿主机：`http://10.0.2.2:8000`
- 真机调试可用局域网 IP，或用：

```bash
adb reverse tcp:8000 tcp:8000
```

然后真机访问 `http://127.0.0.1:8000`。

## 长音频策略

这个项目里的前端录音通常应是用户 query，建议控制在 5-30 秒。长音频是个人转写工作流，不建议直接塞进导购 chat。

如果确实要支持长音频：

1. 后端先限制同步接口，例如最多 2-3 分钟。
2. 超过限制时返回明确错误，让前端提示“录音太长，请缩短或走批量转写工具”。
3. 后续再做 job 模式：
   - `POST /api/asr/jobs`
   - `GET /api/asr/jobs/{id}`
   - Android 轮询状态。

第一版不要在 `/api/chat/stream` 里隐式做长音频转写，否则 RAG 对话接口会被 ASR 的慢请求拖住。

## Profile 选择

默认：

```text
bilingual = iic/SenseVoiceSmall + fsmn-vad + ct-punc-c postprocess
```

适用：

- 中英混合。
- 用户自然语音 query。
- 需要自动识别语言。
- 第一版默认使用这个 profile；ASR 先输出原始文字，再由中文标点模型恢复逗号、句号、问号。

可选后续对比：

```text
zh = paraformer-zh + fsmn-vad + ct-punc-c
```

适用：

- 几乎全中文。
- 更在意中文标点和普通话准确率。

暂不建议第一版启用 `--speaker` / `cam++`。用户 query 不需要说话人分离，且会额外下载模型、增加推理时间。也不建议默认使用更大的 `ct-punc` 中英大模型；本地第一版中文导购场景里，`ct-punc-c` 的体积和效果更合适。

## 安全与隐私边界

第一版应保持本地闭环：

- ASR sidecar 只绑定 `127.0.0.1`。
- 不把音频上传到外部云服务。
- 不把用户录音提交到 Git。
- 临时音频默认处理后删除；调试期如需保留，放 `data/tmp/asr/` 并写清楚。
- Android 端显示“正在本地转写”即可，不要宣称“完全隐私安全”这类绝对结论，除非确认没有任何外部调用。

## 验收清单

后端：

- `GET /health` 不受 ASR sidecar 是否启动影响。
- Sidecar 未启动时，`POST /api/asr/transcribe` 返回结构化错误。
- ASR 模型只加载一次，不在每个请求里重新下载或重新初始化。
- `.m4a` 短音频能返回中文/英文文本。
- `data/tmp/asr/` 不进入 Git。

Android：

- 能录音生成本地 `.m4a`。
- 能上传到本地后端。
- 转写成功后填入输入框，不自动发送。
- 网络/ASR 失败时输入框内容不丢失。
- Emulator 与真机地址策略分别可用。

演示：

- 中文 query：`我想找一款适合油皮通勤的防晒，预算两百以内。`
- 中英混合 query：`我想找一个 travel friendly 的防晒，最好 two hundred 以内。`
- 失败 case：ASR sidecar 停止时，Android 显示可理解错误。

## 建议实施顺序

1. 在 `audio-transcription-lab` 把 `scripts/transcribe.py` 抽成 `asr_service.py`，提供 `POST /transcribe`。
2. 在 RAG 后端加 `/api/asr/transcribe` 代理，先用 curl 跑通。
3. Android 加录音按钮和 multipart 上传，成功后填入输入框。
4. 做 3 条真实口述 query 回归：中文、英文夹杂、安静/有噪声。
5. 再决定是否需要中文专用 profile、热词、job 模式或流式 ASR。

## 当前第一版实现记录

已新增 sidecar 服务：

```bash
cd /Users/jia/Documents/个人工具/audio-transcription-lab
source .venv/bin/activate
python asr_service.py --port 8765 --keep-uploads
```

版本边界：

- 当前 Git 仓库负责提交 Android 录音 UI、RAG 后端代理接口、依赖和接入文档。
- `asr_service.py` 当前仍放在本机 `audio-transcription-lab` 目录；如果需要多人复现，应把该 sidecar 脚本纳入一个可同步仓库，或后续迁入当前 repo 的 `tools/` / `server/sidecars/` 目录。

默认行为：

- `bilingual` profile 使用 `SenseVoiceSmall` 做 ASR，再用 `ct-punc-c` 做中文标点恢复。
- `zh` profile 的 FunASR 内置标点模型也使用 `ct-punc-c`，避免拉取更大的 `ct-punc` 中英大模型。
- 首次使用标点恢复时会下载 `iic/punc_ct-transformer_zh-cn-common-vocab272727-pytorch`，模型主体约 278MB。
- 如需临时关闭标点恢复，可启动 `python asr_service.py --port 8765 --no-punctuation`。
- `--keep-uploads` 仅建议调试期使用；它会把 Android 上传的录音保存在 `audio-transcription-lab/outputs/service_uploads/`，方便排查“是否录到声音”。

健康检查：

```bash
curl http://127.0.0.1:8765/health
```

RAG 后端已新增代理接口：

```text
POST /api/asr/transcribe
```

本地运行需要两个进程：

```bash
# 1. ASR sidecar
cd /Users/jia/Documents/个人工具/audio-transcription-lab
source .venv/bin/activate
python asr_service.py --port 8765 --keep-uploads

# 2. RAG FastAPI 后端
cd /Users/jia/Developer/bytedance-rag-shopping-agent/server
source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Android 端已新增：

- `RECORD_AUDIO` 权限。
- 输入框旁麦克风按钮：点击开始录音，再次点击停止。
- `MediaRecorder` 录制 `.m4a` / AAC 文件到 app cache。
- 录音时显示波形条，用于确认 AVD 或真机确实有麦克风输入。
- 停止录音后上传到 `/api/asr/transcribe`；转写成功后只填入输入框，不自动发送。
- 网络、权限、录音、ASR 失败时显示状态文案，并保留原输入框内容。

AVD 调试提醒：

- Android Studio Device Manager 的 Refresh 只刷新设备列表，不会修复卡死的 emulator。
- `adb devices -l` 应显示 `device`；如果是 `offline`，需要重启 AVD 或 ADB。
- Emulator Extended Controls -> Microphone 里，应打开 `Virtual microphone uses host audio input`。
- 如用 emulator 访问本机后端，保留默认 `10.0.2.2:8000` 策略；如用真机，可用 `adb reverse tcp:8000 tcp:8000`。

已验证：

- `asr_service.py --help` 和语法编译通过。
- sidecar `/health` 返回 `ok: true`。
- sidecar 未启动时，RAG 代理返回结构化 `ok: false` JSON。
- 使用 FunASR 自带 `SenseVoiceSmall/example/zh.mp3` 通过 RAG 代理完成真实转写，返回 `开饭时间早上九点至下午五点`。
- 使用 Android 录音样本验证 `ct-punc-c` 后处理：原始文本无标点，返回文本包含逗号、句号、问号，且 `punctuation_applied: true`。
- Android `:client:android:app:compileDebugKotlin` 通过。
- `git diff --check` 通过。

## 交给实现者的关键提醒

- 不要把 FunASR 直接装进 `server/.venv`，除非先把后端 Python 降到/重建为 3.11 并确认 PyTorch 可用。
- 不要每个请求重新初始化模型。
- 不要第一版就支持任意长音频。
- 不要把 ASR 和 RAG 检索强耦合；ASR 只负责把声音变成文本，chat 仍走现有 `/api/chat/stream`。
- 不要自动发送转写文本；先让用户确认，这是移动端语音输入更稳的 UX。
