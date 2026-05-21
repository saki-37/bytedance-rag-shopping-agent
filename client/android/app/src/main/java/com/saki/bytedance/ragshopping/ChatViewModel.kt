package com.saki.bytedance.ragshopping

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class ChatUiState(
    val input: String = "",
    val messages: List<ChatMessage> = listOf(
        ChatMessage(
            role = Role.Assistant,
            content = "你好，我可以先帮你做美妆护肤导购。你可以告诉我肤质、预算、使用场景或想避开的成分。",
        )
    ),
    val isLoading: Boolean = false,
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
        if (message.isEmpty() || state.value.isLoading) return

        _state.update {
            it.copy(
                input = "",
                isLoading = true,
                messages = it.messages + ChatMessage(Role.User, message) + ChatMessage(Role.Assistant, ""),
            )
        }

        viewModelScope.launch {
            client.streamChat(message) { event ->
                when (event) {
                    is StreamEvent.Status -> appendStatus(event.value)
                    is StreamEvent.Products -> attachProducts(event.value)
                    is StreamEvent.Token -> appendToken(event.value)
                    is StreamEvent.Error -> appendError(event.message)
                    StreamEvent.Done -> _state.update { it.copy(isLoading = false) }
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
        _state.update { it.copy(messages = it.messages + ChatMessage(Role.Status, text)) }
    }

    private fun attachProducts(products: List<ProductCard>) {
        _state.update { current ->
            current.copy(messages = current.messages.mapLastAssistant { it.copy(products = products) })
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
                messages = it.messages + ChatMessage(Role.Error, "请求失败：$message"),
            )
        }
    }

    private fun List<ChatMessage>.mapLastAssistant(transform: (ChatMessage) -> ChatMessage): List<ChatMessage> {
        val index = indexOfLast { it.role == Role.Assistant }
        if (index < 0) return this
        return mapIndexed { itemIndex, item -> if (itemIndex == index) transform(item) else item }
    }
}
