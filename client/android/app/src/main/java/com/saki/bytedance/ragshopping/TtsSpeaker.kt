package com.saki.bytedance.ragshopping

import android.content.Context
import android.os.Bundle
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.update
import java.util.Locale
import java.util.UUID

sealed interface TtsPlaybackState {
    data object Initializing : TtsPlaybackState
    data object Idle : TtsPlaybackState
    data class Speaking(val messageId: String) : TtsPlaybackState
    data class Error(val message: String) : TtsPlaybackState
}

class TtsSpeaker(
    context: Context,
) : TextToSpeech.OnInitListener {
    private val appContext = context.applicationContext
    private val _state = MutableStateFlow<TtsPlaybackState>(TtsPlaybackState.Initializing)
    private val lock = Any()
    private val tts = TextToSpeech(appContext, this)
    private val queuedUtteranceIds = mutableSetOf<String>()
    private var pendingRequest: TtsSpeakRequest? = null
    private var currentMessageId: String? = null
    private var initialized = false

    val state: StateFlow<TtsPlaybackState> = _state

    override fun onInit(status: Int) {
        if (status != TextToSpeech.SUCCESS) {
            _state.value = TtsPlaybackState.Error("语音播报初始化失败")
            return
        }
        initialized = true
        if (!configureVoice()) return
        _state.value = TtsPlaybackState.Idle
        val request = synchronized(lock) {
            pendingRequest.also { pendingRequest = null }
        }
        request?.let {
            speak(
                messageId = it.messageId,
                rawText = it.text,
                verboseMode = it.verboseMode,
                speechRate = it.speechRate,
            )
        }
    }

    fun speak(
        messageId: String,
        rawText: String,
        verboseMode: Boolean,
        speechRate: Float,
    ) {
        val readableText = rawText.toTtsReadableText(verboseMode)
        if (readableText.isBlank()) return
        if (!initialized) {
            synchronized(lock) {
                pendingRequest = TtsSpeakRequest(
                    messageId = messageId,
                    text = rawText,
                    verboseMode = verboseMode,
                    speechRate = speechRate,
                )
            }
            return
        }

        val normalizedRate = normalizeSpeechRate(speechRate)
        val chunks = readableText.toTtsChunks(normalizedRate)
        if (chunks.isEmpty()) return

        tts.setSpeechRate(normalizedRate)
        stop()
        val requestId = UUID.randomUUID().toString()
        val utteranceIds = chunks.mapIndexed { index, _ -> "$requestId:$messageId:$index" }
        synchronized(lock) {
            currentMessageId = messageId
            queuedUtteranceIds.clear()
            queuedUtteranceIds += utteranceIds
        }
        _state.value = TtsPlaybackState.Speaking(messageId)

        chunks.forEachIndexed { index, chunk ->
            val queueMode = if (index == 0) TextToSpeech.QUEUE_FLUSH else TextToSpeech.QUEUE_ADD
            val result = tts.speak(chunk, queueMode, Bundle(), utteranceIds[index])
            if (result == TextToSpeech.ERROR) {
                synchronized(lock) {
                    queuedUtteranceIds.remove(utteranceIds[index])
                }
                _state.value = TtsPlaybackState.Error("语音播报失败")
            }
        }
    }

    fun stop() {
        synchronized(lock) {
            pendingRequest = null
            queuedUtteranceIds.clear()
            currentMessageId = null
        }
        if (initialized) {
            tts.stop()
        }
        _state.update { current ->
            if (current is TtsPlaybackState.Initializing) current else TtsPlaybackState.Idle
        }
    }

    fun shutdown() {
        stop()
        tts.shutdown()
        initialized = false
    }

    private fun configureVoice(): Boolean {
        val languageResult = tts.setLanguage(Locale.CHINA)
        if (
            languageResult == TextToSpeech.LANG_MISSING_DATA ||
            languageResult == TextToSpeech.LANG_NOT_SUPPORTED
        ) {
            _state.value = TtsPlaybackState.Error("当前设备缺少中文语音包")
            return false
        }
        tts.setSpeechRate(1.0f)
        tts.setPitch(1.0f)
        tts.setOnUtteranceProgressListener(object : UtteranceProgressListener() {
            override fun onStart(utteranceId: String?) = Unit

            override fun onDone(utteranceId: String?) {
                finishUtterance(utteranceId)
            }

            @Deprecated("Deprecated in Java")
            override fun onError(utteranceId: String?) {
                finishUtterance(utteranceId)
            }

            override fun onError(utteranceId: String?, errorCode: Int) {
                finishUtterance(utteranceId)
            }
        })
        return true
    }

    private fun finishUtterance(utteranceId: String?) {
        val shouldFinish = synchronized(lock) {
            if (utteranceId == null) {
                queuedUtteranceIds.clear()
            } else {
                queuedUtteranceIds.remove(utteranceId)
            }
            queuedUtteranceIds.isEmpty()
        }
        if (shouldFinish) {
            synchronized(lock) {
                currentMessageId = null
            }
            _state.value = TtsPlaybackState.Idle
        }
    }

    private data class TtsSpeakRequest(
        val messageId: String,
        val text: String,
        val verboseMode: Boolean,
        val speechRate: Float,
    )
}

private fun String.toTtsReadableText(verboseMode: Boolean): String {
    val base = toTtsReadableText()
    if (base.isBlank()) return base
    return if (verboseMode) {
        "以下是一条助手回复：$base"
    } else {
        base
    }
}

private fun String.toTtsReadableText(): String {
    return replace("\r\n", "\n")
        .replace("\r", "\n")
        .lines()
        .filterNot { line -> line.trim().matches(Regex("""^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?$""")) }
        .joinToString("。") { line -> line.trim().trim('|').replace("|", "，") }
        .replace(Regex("`([^`]*)`"), "$1")
        .replace(Regex("(\\*\\*|__)(.*?)(\\*\\*|__)"), "$2")
        .replace(Regex("^\\s*#{1,6}\\s*", RegexOption.MULTILINE), "")
        .replace(Regex("^\\s*[-*•]\\s+", RegexOption.MULTILINE), "")
        .replace(Regex("^\\s*\\d+[.)、]\\s+", RegexOption.MULTILINE), "")
        .replace(Regex("\\s*[\\(（]\\s*(?:p|s)_[A-Za-z0-9_]+\\s*[\\)）]"), "")
        .replace(Regex("\\s+(?:p|s)_[A-Za-z0-9_]+"), "")
        .replace(Regex("[>#*_~]+"), "")
        .replace(Regex("\\s+"), " ")
        .replace(Regex("。{2,}"), "。")
        .trim(' ', '。', '，')
}

private fun String.toTtsChunks(speechRate: Float): List<String> {
    val maxLength = when {
        speechRate >= 1.4f -> (TextToSpeech.getMaxSpeechInputLength() - 260).coerceAtLeast(500)
        speechRate <= 0.8f -> (TextToSpeech.getMaxSpeechInputLength() - 120).coerceAtLeast(500)
        else -> (TextToSpeech.getMaxSpeechInputLength() - 200).coerceAtLeast(500)
    }
    val sentences = split(Regex("(?<=[。！？!?；;])\\s*"))
        .map { it.trim() }
        .filter { it.isNotBlank() }
    if (sentences.isEmpty()) return emptyList()

    val chunks = mutableListOf<String>()
    var current = StringBuilder()
    sentences.forEach { sentence ->
        if (current.length + sentence.length + 1 > maxLength && current.isNotBlank()) {
            chunks += current.toString().trim()
            current = StringBuilder()
        }
        if (sentence.length > maxLength) {
            sentence.chunked(maxLength).forEach { chunks += it }
        } else {
            if (current.isNotEmpty()) current.append(' ')
            current.append(sentence)
        }
    }
    if (current.isNotBlank()) {
        chunks += current.toString().trim()
    }
    return chunks
}

private fun normalizeSpeechRate(rate: Float): Float {
    return when {
        rate <= 0.74f -> 0.75f
        rate <= 0.88f -> 0.75f
        rate <= 1.12f -> 1.0f
        rate <= 1.38f -> 1.25f
        else -> 1.5f
    }
}
