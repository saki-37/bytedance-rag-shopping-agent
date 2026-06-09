package com.saki.bytedance.ragshopping

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import java.io.File

data class ChatUiState(
    val input: String = "",
    val backendBaseUrl: String = BackendConfig.DefaultBaseUrl,
    val pendingProducts: List<ProductCard> = emptyList(),
    val messages: List<ChatMessage> = listOf(
        ChatMessage(
            role = Role.Assistant,
            content = "你好，我是你的导购小助手。你可以告诉我想买什么、预算、使用场景和不想踩的雷；我会先查商品资料，再帮你筛选、对比和解释推荐依据。",
        )
    ),
    val isLoading: Boolean = false,
    val statusText: String? = null,
    val isTranscribing: Boolean = false,
    val asrStatusText: String? = null,
)

class ChatViewModel(
    private val client: ShoppingAgentClient = ShoppingAgentClient(),
) : ViewModel() {
    private val _state = MutableStateFlow(ChatUiState())
    val state: StateFlow<ChatUiState> = _state
    private var quickReplyTypingJob: Job? = null

    fun updateInput(value: String) {
        _state.update { it.copy(input = value, asrStatusText = null) }
    }

    fun send() {
        val message = state.value.input.trim()
        sendMessage(message)
    }

    fun sendPrompt(message: String) {
        sendMessage(message.trim())
    }

    fun submitFeedback(messageId: String, feedback: FeedbackType) {
        val snapshot = state.value
        val assistantIndex = snapshot.messages.indexOfFirst { it.id == messageId }
        if (assistantIndex <= 0) return

        val assistantMessage = snapshot.messages[assistantIndex]
        if (
            assistantMessage.role != Role.Assistant ||
            assistantMessage.content.isBlank() ||
            assistantMessage.isFeedbackSending ||
            assistantMessage.feedback != null
        ) {
            return
        }

        val userMessage = snapshot.messages
            .take(assistantIndex)
            .lastOrNull { it.role == Role.User && it.content.isNotBlank() }
            ?: return
        val history = snapshot.messages
            .take(assistantIndex + 1)
            .filter {
                it.content.isNotBlank() &&
                    !it.isEphemeral &&
                    it.role in setOf(Role.User, Role.Assistant)
            }
            .dropWhile { it.role != Role.User }

        _state.update { current ->
            current.copy(
                messages = current.messages.mapMessageById(messageId) {
                    it.copy(isFeedbackSending = true, feedbackError = null)
                }
            )
        }

        viewModelScope.launch {
            runCatching {
                client.submitFeedback(
                    feedback = feedback,
                    userMessage = userMessage.content,
                    assistantAnswer = assistantMessage.content,
                    products = assistantMessage.products,
                    history = history,
                    turnId = messageId,
                )
            }.onSuccess {
                _state.update { current ->
                    current.copy(
                        messages = current.messages.mapMessageById(messageId) {
                            it.copy(feedback = feedback, isFeedbackSending = false, feedbackError = null)
                        }
                    )
                }
            }.onFailure { error ->
                _state.update { current ->
                    current.copy(
                        messages = current.messages.mapMessageById(messageId) {
                            it.copy(
                                isFeedbackSending = false,
                                feedbackError = error.localizedMessage ?: "反馈记录失败",
                            )
                        }
                    )
                }
            }
        }
    }

    fun transcribeAudio(audioFile: File) {
        if (state.value.isLoading || state.value.isTranscribing) {
            audioFile.delete()
            return
        }

        _state.update {
            it.copy(
                isTranscribing = true,
                asrStatusText = "正在本地转写...",
            )
        }

        viewModelScope.launch {
            try {
                val result = client.transcribeAudio(audioFile)
                _state.update { current ->
                    if (result.ok && result.text.isNotBlank()) {
                        current.copy(
                            input = mergeVoiceInput(current.input, result.text),
                            isTranscribing = false,
                            asrStatusText = "已转写，可修改后发送",
                        )
                    } else {
                        current.copy(
                            isTranscribing = false,
                            asrStatusText = "转写失败：${result.error ?: "没有识别到文字"}",
                        )
                    }
                }
            } catch (error: Exception) {
                _state.update { current ->
                    current.copy(
                        isTranscribing = false,
                        asrStatusText = "转写失败：${error.localizedMessage ?: "网络或 ASR 服务异常"}",
                    )
                }
            } finally {
                audioFile.delete()
            }
        }
    }

    private fun sendMessage(message: String) {
        if (message.isEmpty() || state.value.isLoading) return
        cancelQuickReplyTyping()
        val history = state.value.messages
            .filter {
                it.content.isNotBlank() &&
                    !it.isEphemeral &&
                    it.role in setOf(Role.User, Role.Assistant)
            }
            .drop(1)

        _state.update {
            it.copy(
                input = "",
                isLoading = true,
                statusText = null,
                asrStatusText = null,
                pendingProducts = emptyList(),
                messages = it.messages + ChatMessage(Role.User, message) + ChatMessage(Role.Assistant, ""),
            )
        }

        viewModelScope.launch {
            client.streamChat(message, history) { event ->
                when (event) {
                    is StreamEvent.Connection -> _state.update { it.copy(backendBaseUrl = event.baseUrl) }
                    is StreamEvent.Status -> appendStatus(event.value)
                    is StreamEvent.Products -> rememberProducts(event.value)
                    is StreamEvent.QuickReply -> appendQuickReply(event.text, event.ephemeral)
                    is StreamEvent.Token -> appendToken(event.value)
                    is StreamEvent.Error -> appendError(event.message)
                    StreamEvent.Done -> finishAssistantTurn()
                }
            }
        }
    }

    private fun appendStatus(status: String) {
        val text = when (status) {
            "retrieving" -> "正在检索商品资料..."
            "generating" -> "正在生成推荐..."
            else -> status
        }
        _state.update { it.copy(statusText = text) }
    }

    private fun appendQuickReply(text: String, ephemeral: Boolean) {
        val cleanText = text.trim()
        if (cleanText.isBlank()) return
        quickReplyTypingJob?.cancel()
        val existingQuickReplyId = state.value.messages
            .lastOrNull { it.role == Role.Assistant && it.isQuickReply }
            ?.id
        val newQuickReply = ChatMessage(
            role = Role.Assistant,
            content = "",
            isEphemeral = ephemeral,
            isQuickReply = true,
        )
        val quickReplyId = existingQuickReplyId ?: newQuickReply.id
        _state.update { current ->
            val existingIndex = current.messages.indexOfLast { it.role == Role.Assistant && it.isQuickReply }
            val messages = if (existingIndex >= 0) {
                current.messages.mapIndexed { index, item ->
                    if (index == existingIndex) {
                        item.copy(content = "", isEphemeral = ephemeral, isQuickReply = true)
                    } else {
                        item
                    }
                }
            } else {
                current.messages.insertBeforeLastAssistant(newQuickReply)
            }
            current.copy(
                messages = messages
            )
        }
        quickReplyTypingJob = viewModelScope.launch {
            revealQuickReply(quickReplyId, cleanText)
        }
    }

    private fun rememberProducts(products: List<ProductCard>) {
        _state.update { current ->
            current.copy(
                pendingProducts = products,
                messages = current.messages.mapLastAssistant { it.copy(products = products) },
            )
        }
    }

    private fun finishAssistantTurn() {
        cancelQuickReplyTyping()
        _state.update { current ->
            val lastAssistant = current.messages.lastOrNull { it.role == Role.Assistant }
            val messagesWithProducts = if (current.pendingProducts.isEmpty() || lastAssistant?.products?.isNotEmpty() == true) {
                current.messages
            } else {
                current.messages.mapLastAssistant { it.copy(products = current.pendingProducts) }
            }
            val messages = messagesWithProducts.filterNot { it.isEphemeral && it.isQuickReply }
            current.copy(
                isLoading = false,
                statusText = null,
                pendingProducts = emptyList(),
                messages = messages,
            )
        }
    }

    private fun appendToken(token: String) {
        _state.update { current ->
            current.copy(messages = current.messages.mapLastAssistant { it.copy(content = it.content + token) })
        }
    }

    private fun appendError(message: String) {
        cancelQuickReplyTyping()
        _state.update {
            it.copy(
                isLoading = false,
                statusText = null,
                pendingProducts = emptyList(),
                messages = it.messages
                    .filterNot { item -> item.isEphemeral && item.isQuickReply } +
                    ChatMessage(Role.Error, "请求失败：$message"),
            )
        }
    }

    private suspend fun revealQuickReply(messageId: String, text: String) {
        var visibleText = ""
        for (char in text) {
            visibleText += char
            _state.update { current ->
                current.copy(
                    messages = current.messages.mapMessageById(messageId) {
                        it.copy(content = visibleText)
                    }
                )
            }
            delay(18)
        }
    }

    private fun cancelQuickReplyTyping() {
        quickReplyTypingJob?.cancel()
        quickReplyTypingJob = null
    }

    private fun List<ChatMessage>.insertBeforeLastAssistant(message: ChatMessage): List<ChatMessage> {
        val index = indexOfLast { it.role == Role.Assistant && !it.isQuickReply }
        if (index < 0) return this + message
        return take(index) + message + drop(index)
    }

    private fun List<ChatMessage>.mapLastAssistant(transform: (ChatMessage) -> ChatMessage): List<ChatMessage> {
        val index = indexOfLast { it.role == Role.Assistant && !it.isQuickReply }
        if (index < 0) return this
        return mapIndexed { itemIndex, item -> if (itemIndex == index) transform(item) else item }
    }

    private fun List<ChatMessage>.mapMessageById(
        messageId: String,
        transform: (ChatMessage) -> ChatMessage,
    ): List<ChatMessage> {
        return map { message -> if (message.id == messageId) transform(message) else message }
    }

    private fun mergeVoiceInput(existing: String, recognized: String): String {
        val cleanText = recognized.trim()
        if (existing.isBlank()) return cleanText
        return "${existing.trimEnd()} $cleanText"
    }
}
