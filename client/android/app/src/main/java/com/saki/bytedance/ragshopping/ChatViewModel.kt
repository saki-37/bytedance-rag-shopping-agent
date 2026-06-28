package com.saki.bytedance.ragshopping

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import java.io.File

/** 会话摘要：用于会话列表 UI（标题 + 时间 + 当前标记）。 */
data class ChatSessionSummary(
    val id: String,
    val title: String,
    val createdAtMillis: Long,
    val messageCount: Int,
    val isCurrent: Boolean,
)

data class ChatUiState(
    val input: String = "",
    val backendBaseUrl: String = BackendConfig.DefaultBaseUrl,
    // 演示级本地身份：仅存在 SharedPreferences，透传给后端做记忆隔离
    val userId: String = DemoIdentityStore.DefaultUserId,
    val userDisplayName: String = DemoIdentityStore.DefaultDisplayName,
    // 当前会话 id，同时作为后端 conversation_id
    val conversationId: String = "",
    val sessions: List<ChatSessionSummary> = emptyList(),
    val pendingProducts: List<ProductCard> = emptyList(),
    val recipients: List<RecipientProfile> = listOf(defaultRecipientProfile()),
    val selectedRecipientId: String = "self",
    val recipientsLoading: Boolean = false,
    val recipientsSaving: Boolean = false,
    val recipientError: String? = null,
    val messages: List<ChatMessage> = initialSessionMessages(),
    val activeConstraintChips: List<ConstraintChip> = emptyList(),
    val constraintStatusText: String? = null,
    val isLoading: Boolean = false,
    val statusText: String? = null,
    val isTranscribing: Boolean = false,
    val asrStatusText: String? = null,
)

class ChatViewModel @JvmOverloads constructor(
    application: Application,
    private val client: ShoppingAgentClient = ShoppingAgentClient(),
) : AndroidViewModel(application) {
    private val _state = MutableStateFlow(ChatUiState())
    val state: StateFlow<ChatUiState> = _state
    private var quickReplyTypingJob: Job? = null

    /**
     * 本地多会话（仅内存态，App 重启后只保留当前会话的初始状态）。
     * key = 会话 id（同时作为后端 conversation_id）。
     */
    private class SessionRecord(
        val id: String,
        val createdAtMillis: Long,
        var messages: List<ChatMessage>,
    )

    private val sessionRecords = linkedMapOf<String, SessionRecord>()
    private var sessionCounter = 0

    init {
        val identity = DemoIdentityStore.load(application)
        val firstSession = createSessionRecord()
        _state.update {
            it.copy(
                userId = identity.userId,
                userDisplayName = identity.displayName,
                conversationId = firstSession.id,
                sessions = buildSessionSummaries(firstSession.id),
            )
        }
        loadRecipients()
    }

    // ---------- 会话切换（本地内存态） ----------

    /** 新建会话；当前会话还没有用户消息时直接复用，避免堆积空会话。 */
    fun newSession() {
        val snapshot = state.value
        if (snapshot.isLoading || snapshot.isTranscribing) return
        val hasUserMessage = snapshot.messages.any { it.role == Role.User && it.content.isNotBlank() }
        if (!hasUserMessage) return

        archiveCurrentSession()
        val record = createSessionRecord()
        _state.update {
            it.copy(
                input = "",
                conversationId = record.id,
                messages = record.messages,
                pendingProducts = emptyList(),
                activeConstraintChips = emptyList(),
                constraintStatusText = null,
                statusText = null,
                asrStatusText = null,
                sessions = buildSessionSummaries(record.id),
            )
        }
    }

    /** 切换到已有会话。流式回复进行中禁止切换，避免把 token 写进错误会话。 */
    fun switchSession(sessionId: String) {
        val snapshot = state.value
        if (snapshot.isLoading || snapshot.isTranscribing) return
        if (sessionId == snapshot.conversationId) return
        val target = sessionRecords[sessionId] ?: return

        archiveCurrentSession()
        _state.update {
            it.copy(
                input = "",
                conversationId = target.id,
                messages = target.messages,
                pendingProducts = emptyList(),
                activeConstraintChips = emptyList(),
                constraintStatusText = null,
                statusText = null,
                asrStatusText = null,
                sessions = buildSessionSummaries(target.id),
            )
        }
    }

    /**
     * 切换演示身份（本地 user_id，不是真实登录）。
     * 切换后：持久化身份、清空本地会话、重新拉取该用户的常用对象。
     */
    fun switchUser(rawInput: String) {
        val snapshot = state.value
        if (snapshot.isLoading || snapshot.isTranscribing) return
        val identity = if (rawInput.isBlank()) DemoIdentity() else DemoIdentityStore.deriveIdentity(rawInput)
        DemoIdentityStore.save(getApplication<Application>(), identity)
        if (identity.userId == snapshot.userId) {
            _state.update { it.copy(userDisplayName = identity.displayName) }
            return
        }

        sessionRecords.clear()
        val record = createSessionRecord()
        _state.update {
            it.copy(
                input = "",
                userId = identity.userId,
                userDisplayName = identity.displayName,
                conversationId = record.id,
                messages = record.messages,
                pendingProducts = emptyList(),
                activeConstraintChips = emptyList(),
                constraintStatusText = null,
                statusText = null,
                asrStatusText = null,
                sessions = buildSessionSummaries(record.id),
                recipients = listOf(defaultRecipientProfile()),
                selectedRecipientId = "self",
            )
        }
        loadRecipients()
    }

    private fun createSessionRecord(): SessionRecord {
        sessionCounter += 1
        val record = SessionRecord(
            id = "android-${System.currentTimeMillis()}-$sessionCounter",
            createdAtMillis = System.currentTimeMillis(),
            messages = initialSessionMessages(),
        )
        sessionRecords[record.id] = record
        return record
    }

    /** 把当前 UI 消息列表写回对应会话记录，防止切换时丢消息。 */
    private fun archiveCurrentSession() {
        val snapshot = state.value
        sessionRecords[snapshot.conversationId]?.messages = snapshot.messages
    }

    /** 只读取会话记录生成摘要；调用前需先 archiveCurrentSession() 保证记录是最新的。 */
    private fun buildSessionSummaries(currentSessionId: String): List<ChatSessionSummary> {
        return sessionRecords.values
            .map { record ->
                ChatSessionSummary(
                    id = record.id,
                    title = sessionTitle(record.messages),
                    createdAtMillis = record.createdAtMillis,
                    messageCount = record.messages.count { it.role == Role.User && it.content.isNotBlank() },
                    isCurrent = record.id == currentSessionId,
                )
            }
            .sortedByDescending { it.createdAtMillis }
    }

    private fun sessionTitle(messages: List<ChatMessage>): String {
        val firstUserMessage = messages.firstOrNull { it.role == Role.User && it.content.isNotBlank() }
            ?: return "新会话"
        val text = firstUserMessage.content.trim().replace("\n", " ")
        return if (text.length <= 14) text else text.take(14) + "…"
    }

    /** 先把当前消息写回记录，再刷新会话摘要（标题随首条用户消息变化）。 */
    private fun refreshSessionSummaries() {
        archiveCurrentSession()
        _state.update { it.copy(sessions = buildSessionSummaries(it.conversationId)) }
    }

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

    fun sendWithImage(
        message: String,
        localImageFile: File,
        localPreviewUri: String?,
        source: ImageSource,
    ) {
        if (state.value.isLoading) return

        val cleanMessage = message.trim()
        val fallbackMessage = cleanMessage.ifBlank { "我上传了一张图片，帮我看看并推荐类似商品" }

        cancelQuickReplyTyping()

        val history = state.value.messages
            .filter {
                it.content.isNotBlank() &&
                    !it.isEphemeral &&
                    it.role in setOf(Role.User, Role.Assistant)
            }
            .drop(1)

        val localImage = ChatImage(
            localUri = localPreviewUri,
            source = source,
        )

        _state.update {
            it.copy(
                input = "",
                isLoading = true,
                statusText = null,
                constraintStatusText = null,
                asrStatusText = null,
                pendingProducts = emptyList(),
                messages = it.messages + ChatMessage(Role.User, fallbackMessage, images = listOf(localImage)) + ChatMessage(Role.Assistant, ""),
            )
        }

        refreshSessionSummaries()

        viewModelScope.launch {
            try {
                val uploaded = client.uploadImage(
                    imageFile = localImageFile,
                    userId = state.value.userId,
                    conversationId = state.value.conversationId,
                )
                val uploadedImage = ChatImage(
                    localUri = localPreviewUri,
                    previewUrl = uploaded.previewUrl,
                    imageId = uploaded.imageId,
                    mimeType = uploaded.mimeType,
                    source = source,
                    summary = uploaded.summary,
                    queryText = uploaded.queryText,
                    imagePlanJson = uploaded.imagePlan.toString(),
                )

                client.streamChat(
                    message = fallbackMessage,
                    history = history,
                    recipientId = state.value.selectedRecipientId,
                    images = listOf(uploadedImage),
                    userId = state.value.userId,
                    conversationId = state.value.conversationId,
                    onEvent = { event ->
                        when (event) {
                            is StreamEvent.Connection -> _state.update { it.copy(backendBaseUrl = event.baseUrl) }
                            is StreamEvent.Status -> appendStatus(event.value)
                            is StreamEvent.Products -> rememberProducts(event.value)
                            is StreamEvent.Constraints -> updateConstraintChips(event.value)
                            is StreamEvent.QuickReply -> appendQuickReply(event.text, event.ephemeral)
                            is StreamEvent.Token -> appendToken(event.value)
                            is StreamEvent.Error -> appendError(event.message)
                            StreamEvent.Done -> finishAssistantTurn()
                        }
                    }
                )
            } catch (error: Exception) {
                appendError(error.localizedMessage ?: "图片上传或发送失败")
            } finally {
                localImageFile.delete()
            }
        }
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
                    conversationId = snapshot.conversationId,
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
                val result = client.transcribeAudio(
                    audioFile = audioFile,
                    conversationId = state.value.conversationId,
                )
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

    fun removeConstraint(chip: ConstraintChip) {
        if (!chip.removable) return
        val snapshot = state.value
        val previousChips = snapshot.activeConstraintChips
        val nextChips = previousChips.filterNot { it.id == chip.id }
        _state.update {
            it.copy(
                activeConstraintChips = nextChips,
                constraintStatusText = "已移除条件：${chip.label}",
            )
        }
        viewModelScope.launch {
            runCatching {
                client.removeConstraint(
                    conversationId = snapshot.conversationId,
                    constraintId = chip.id,
                    userId = snapshot.userId,
                    recipientId = snapshot.selectedRecipientId,
                )
            }.onFailure { error ->
                _state.update {
                    it.copy(
                        activeConstraintChips = previousChips,
                        constraintStatusText = "条件更新失败：${error.localizedMessage ?: "请稍后重试"}",
                    )
                }
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
                constraintStatusText = null,
                asrStatusText = null,
                pendingProducts = emptyList(),
                messages = it.messages + ChatMessage(Role.User, message) + ChatMessage(Role.Assistant, ""),
            )
        }

        refreshSessionSummaries()

        viewModelScope.launch {
            client.streamChat(
                message = message,
                history = history,
                recipientId = state.value.selectedRecipientId,
                userId = state.value.userId,
                conversationId = state.value.conversationId,
                onEvent = { event ->
                    when (event) {
                        is StreamEvent.Connection -> _state.update { it.copy(backendBaseUrl = event.baseUrl) }
                        is StreamEvent.Status -> appendStatus(event.value)
                        is StreamEvent.Products -> rememberProducts(event.value)
                        is StreamEvent.Constraints -> updateConstraintChips(event.value)
                        is StreamEvent.QuickReply -> appendQuickReply(event.text, event.ephemeral)
                        is StreamEvent.Token -> appendToken(event.value)
                        is StreamEvent.Error -> appendError(event.message)
                        StreamEvent.Done -> finishAssistantTurn()
                    }
                }
            )
        }
    }

    fun loadRecipients() {
        // 记录发起请求时的 user_id；若返回前身份已切换，丢弃旧响应防止串数据
        val requestUserId = state.value.userId
        _state.update { it.copy(recipientsLoading = true, recipientError = null) }
        viewModelScope.launch {
            runCatching {
                client.getRecipients(requestUserId)
            }.onSuccess { response ->
                if (state.value.userId != requestUserId) return@launch
                val normalizedRecipients = normalizeRecipientProfiles(response.recipients)
                _state.update { current ->
                    current.copy(
                        recipients = normalizedRecipients,
                        selectedRecipientId = resolveSelectedRecipientId(normalizedRecipients, response.selectedRecipientId),
                        recipientsLoading = false,
                        recipientError = null,
                    )
                }
            }.onFailure { error ->
                if (state.value.userId != requestUserId) return@launch
                val fallback = normalizeRecipientProfiles(_state.value.recipients)
                _state.update { current ->
                    current.copy(
                        recipients = fallback,
                        selectedRecipientId = resolveSelectedRecipientId(fallback, current.selectedRecipientId),
                        recipientsLoading = false,
                        recipientError = error.localizedMessage ?: "获取常用对象失败",
                    )
                }
            }
        }
    }

    fun selectRecipient(recipientId: String) {
        val currentState = _state.value
        val normalizedRecipients = normalizeRecipientProfiles(currentState.recipients)
        val nextRecipientId = resolveSelectedRecipientId(normalizedRecipients, recipientId)
        if (currentState.selectedRecipientId == nextRecipientId) return

        _state.update {
            it.copy(
                selectedRecipientId = nextRecipientId,
                recipientsSaving = true,
                recipientError = null,
            )
        }
        viewModelScope.launch {
            runCatching {
                client.putSelectedRecipient(userId = state.value.userId, selectedRecipientId = nextRecipientId)
            }.onSuccess { response ->
                val normalized = normalizeRecipientProfiles(response.recipients)
                _state.update { current ->
                    current.copy(
                        recipients = normalized,
                        selectedRecipientId = resolveSelectedRecipientId(normalized, response.selectedRecipientId),
                        recipientsSaving = false,
                        recipientError = null,
                    )
                }
            }.onFailure { error ->
                _state.update { current ->
                    current.copy(
                        selectedRecipientId = resolveSelectedRecipientId(normalizedRecipients, current.selectedRecipientId),
                        recipientsSaving = false,
                        recipientError = error.localizedMessage ?: "切换对象失败",
                    )
                }
            }
        }
    }

    fun saveRecipients(updatedRecipients: List<RecipientProfile>, selectedRecipientId: String?) {
        val normalizedRecipients = normalizeRecipientProfiles(updatedRecipients)
        val normalizedSelection = resolveSelectedRecipientId(normalizedRecipients, selectedRecipientId)
        _state.update {
            it.copy(
                recipientsSaving = true,
                recipientError = null,
            )
        }
        viewModelScope.launch {
            runCatching {
                client.putRecipients(
                    userId = state.value.userId,
                    recipients = normalizedRecipients,
                    selectedRecipientId = normalizedSelection,
                )
            }.onSuccess { response ->
                val normalized = normalizeRecipientProfiles(response.recipients)
                _state.update { current ->
                    current.copy(
                        recipients = normalized,
                        selectedRecipientId = resolveSelectedRecipientId(normalized, response.selectedRecipientId),
                        recipientsSaving = false,
                        recipientError = null,
                    )
                }
            }.onFailure { error ->
                _state.update { current ->
                    current.copy(
                        recipientsSaving = false,
                        recipientError = error.localizedMessage ?: "保存常用对象失败",
                    )
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

    private fun updateConstraintChips(chips: List<ConstraintChip>) {
        _state.update {
            it.copy(
                activeConstraintChips = chips,
                constraintStatusText = null,
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
        // 一轮结束后回写会话记录并刷新会话列表摘要
        refreshSessionSummaries()
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

private fun normalizeRecipientProfiles(input: List<RecipientProfile>): List<RecipientProfile> {
    val deduped = linkedMapOf<String, RecipientProfile>()
    input.forEach { candidate ->
        val trimmedId = candidate.recipientId.trim()
        if (trimmedId.isBlank()) return@forEach
        deduped[trimmedId] = candidate.copy(
            recipientId = trimmedId,
            displayName = candidate.displayName.ifBlank { trimmedId },
        )
    }
    if (!deduped.containsKey("self")) {
        deduped["self"] = defaultRecipientProfile()
    }
    return deduped.values.toList()
}

private fun resolveSelectedRecipientId(
    recipients: List<RecipientProfile>,
    selectedRecipientId: String?,
): String {
    val candidate = selectedRecipientId?.trim().orEmpty()
    if (candidate.isNotBlank() && recipients.any { it.recipientId == candidate }) {
        return candidate
    }
    return recipients.firstOrNull { it.recipientId == "self" }?.recipientId
        ?: recipients.firstOrNull()?.recipientId
        ?: "self"
}

private fun defaultRecipientProfile() = RecipientProfile(
    recipientId = "self",
    displayName = "自己",
    relationship = "self",
)

/** 每个新会话的开场白（不计入发给后端的 history，发送时会 drop(1)）。 */
internal fun initialSessionMessages(): List<ChatMessage> = listOf(
    ChatMessage(
        role = Role.Assistant,
        content = "你好，我是你的导购小助手。你可以告诉我想买什么、预算、使用场景和不想踩的雷；我会先查商品资料，再帮你筛选、对比和解释推荐依据。",
    )
)
