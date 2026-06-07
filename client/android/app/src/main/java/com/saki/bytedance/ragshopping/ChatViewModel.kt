package com.saki.bytedance.ragshopping

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

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
)

class ChatViewModel(
    private val client: ShoppingAgentClient = ShoppingAgentClient(),
) : ViewModel() {
    private val _state = MutableStateFlow(ChatUiState())
    val state: StateFlow<ChatUiState> = _state

    fun updateInput(value: String) {
        _state.update { it.copy(input = value) }
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
            .filter { it.content.isNotBlank() && it.role in setOf(Role.User, Role.Assistant) }
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

    private fun sendMessage(message: String) {
        if (message.isEmpty() || state.value.isLoading) return
        val history = state.value.messages
            .filter { it.content.isNotBlank() && it.role in setOf(Role.User, Role.Assistant) }
            .drop(1)

        _state.update {
            it.copy(
                input = "",
                isLoading = true,
                statusText = null,
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

    private fun rememberProducts(products: List<ProductCard>) {
        _state.update { current ->
            current.copy(
                pendingProducts = products,
                messages = current.messages.mapLastAssistant { it.copy(products = products) },
            )
        }
    }

    private fun finishAssistantTurn() {
        _state.update { current ->
            val lastAssistant = current.messages.lastOrNull { it.role == Role.Assistant }
            val messages = if (current.pendingProducts.isEmpty() || lastAssistant?.products?.isNotEmpty() == true) {
                current.messages
            } else {
                current.messages.mapLastAssistant { it.copy(products = current.pendingProducts) }
            }
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
        _state.update {
            it.copy(
                isLoading = false,
                statusText = null,
                pendingProducts = emptyList(),
                messages = it.messages + ChatMessage(Role.Error, "请求失败：$message"),
            )
        }
    }

    private fun List<ChatMessage>.mapLastAssistant(transform: (ChatMessage) -> ChatMessage): List<ChatMessage> {
        val index = indexOfLast { it.role == Role.Assistant }
        if (index < 0) return this
        return mapIndexed { itemIndex, item -> if (itemIndex == index) transform(item) else item }
    }

    private fun List<ChatMessage>.mapMessageById(
        messageId: String,
        transform: (ChatMessage) -> ChatMessage,
    ): List<ChatMessage> {
        return map { message -> if (message.id == messageId) transform(message) else message }
    }
}
