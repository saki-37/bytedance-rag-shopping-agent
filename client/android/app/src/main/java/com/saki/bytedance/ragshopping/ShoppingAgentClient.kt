package com.saki.bytedance.ragshopping

import android.util.Log
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.ConnectionPool
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.asRequestBody
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.io.IOException
import java.net.URLEncoder
import java.util.concurrent.TimeUnit
import kotlin.text.Charsets.UTF_8

sealed interface StreamEvent {
    data class Status(val value: String) : StreamEvent
    data class Token(val value: String) : StreamEvent
    data class Products(val value: List<ProductCard>) : StreamEvent
    data class Constraints(val value: List<ConstraintChip>) : StreamEvent
    data class QuickReply(val text: String, val ephemeral: Boolean, val source: String) : StreamEvent
    data object Done : StreamEvent
    data class Error(val message: String) : StreamEvent
    data class Connection(val baseUrl: String) : StreamEvent
}

data class UploadedChatImage(
    val imageId: String,
    val mimeType: String,
    val previewUrl: String,
    val summary: String,
    val queryText: String,
    val imagePlan: JSONObject,
)

class ShoppingAgentClient(
    private val baseUrls: List<String> = BackendConfig.CandidateBaseUrls,
    private val okHttpClient: OkHttpClient = OkHttpClient.Builder()
        .connectTimeout(15, TimeUnit.SECONDS)
        .writeTimeout(15, TimeUnit.SECONDS)
        .readTimeout(0, TimeUnit.MILLISECONDS)
        .connectionPool(ConnectionPool(0, 1, TimeUnit.NANOSECONDS))
        .retryOnConnectionFailure(true)
        .build(),
) {
    private val jsonMediaType = "application/json; charset=utf-8".toMediaType()
    private val m4aMediaType = "audio/mp4".toMediaType()
    @Volatile
    private var activeBaseUrl: String = baseUrls.firstOrNull() ?: BackendConfig.DefaultBaseUrl

    suspend fun streamChat(
        message: String,
        history: List<ChatMessage> = emptyList(),
        recipientId: String? = null,
        images: List<ChatImage> = emptyList(),
        userId: String = DEFAULT_USER_ID,
        conversationId: String = DEFAULT_CONVERSATION_ID,
        onEvent: suspend (StreamEvent) -> Unit,
    ) {
        withContext(Dispatchers.IO) {
            val payload = JSONObject()
                .put("message", message)
                .put("user_id", userId.ifBlank { DEFAULT_USER_ID })
                .put("conversation_id", conversationId.ifBlank { DEFAULT_CONVERSATION_ID })
                .put("history", history.toPayloadHistory())
                .put("images", images.toPayloadImages())
                .apply {
                    if (!recipientId.isNullOrBlank()) {
                        put("recipient_id", recipientId)
                    }
                }
                .toString()
            var lastError: IOException? = null
            for (baseUrl in orderedBaseUrls()) {
                var emittedEvent = false
                try {
                    streamChatFromBaseUrl(baseUrl, payload) { event ->
                        emittedEvent = true
                        onEvent(event)
                    }
                    activeBaseUrl = baseUrl
                    return@withContext
                } catch (exception: IOException) {
                    Log.w(TAG, "Chat stream failed for $baseUrl", exception)
                    if (emittedEvent) {
                        onEvent(StreamEvent.Error(userFacingNetworkError(exception)))
                        return@withContext
                    }
                    lastError = exception
                } catch (exception: Exception) {
                    Log.e(TAG, "Chat stream failed", exception)
                    onEvent(StreamEvent.Error(exception.localizedMessage ?: "Network request failed"))
                    return@withContext
                }
            }
            onEvent(StreamEvent.Error(userFacingNetworkError(lastError)))
        }
    }

    suspend fun uploadImage(
        imageFile: File,
        mimeType: String = "image/jpeg",
        userId: String = DEFAULT_USER_ID,
        conversationId: String = DEFAULT_CONVERSATION_ID,
    ): UploadedChatImage {
        return withContext(Dispatchers.IO) {
            val mediaType = mimeType.toMediaType()
            var lastError: IOException? = null

            for (baseUrl in orderedBaseUrls()) {
                val requestBody = MultipartBody.Builder()
                    .setType(MultipartBody.FORM)
                    .addFormDataPart("user_id", userId.ifBlank { DEFAULT_USER_ID })
                    .addFormDataPart("conversation_id", conversationId.ifBlank { DEFAULT_CONVERSATION_ID })
                    .addFormDataPart("file", imageFile.name, imageFile.asRequestBody(mediaType))
                    .build()

                val request = Request.Builder()
                    .url("$baseUrl/api/multimodal/images")
                    .header("Connection", "close")
                    .post(requestBody)
                    .build()

                Log.d(TAG, "POST $baseUrl/api/multimodal/images")

                try {
                    okHttpClient.newCall(request).execute().use { response ->
                        val body = response.body?.string().orEmpty()
                        if (!response.isSuccessful) {
                            val messageText = "HTTP ${response.code}"
                            Log.w(TAG, "$messageText $body")
                            throw IllegalStateException(messageText)
                        }
                        activeBaseUrl = baseUrl
                        val json = JSONObject(body)
                        return@withContext UploadedChatImage(
                            imageId = json.optString("image_id"),
                            mimeType = json.optString("mime_type", mimeType),
                            previewUrl = json.optString("preview_url"),
                            summary = json.optString("summary"),
                            queryText = json.optString("query_text"),
                            imagePlan = json.optJSONObject("image_plan") ?: JSONObject(),
                        )
                    }
                } catch (exception: IOException) {
                    Log.w(TAG, "Image upload failed for $baseUrl", exception)
                    lastError = exception
                }
            }

            throw IllegalStateException(userFacingNetworkError(lastError))
        }
    }

    suspend fun getRecipients(userId: String = DEFAULT_USER_ID): RecipientsResponse {
        return withContext(Dispatchers.IO) {
            val encodedUserId = encodeUserId(userId)
            var lastError: IOException? = null
            for (baseUrl in orderedBaseUrls()) {
                val request = Request.Builder()
                    .url("$baseUrl/api/user-memory/$encodedUserId/recipients")
                    .header("Connection", "close")
                    .get()
                    .build()
                try {
                    okHttpClient.newCall(request).execute().use { response ->
                        val body = response.body?.string().orEmpty()
                        if (!response.isSuccessful) {
                            val messageText = "HTTP ${response.code}"
                            Log.w(TAG, "$messageText $body")
                            throw IllegalStateException(messageText)
                        }
                        activeBaseUrl = baseUrl
                        return@withContext parseRecipientsResponse(JSONObject(body))
                    }
                } catch (exception: IOException) {
                    Log.w(TAG, "Recipients query failed for $baseUrl", exception)
                    lastError = exception
                }
            }
            throw IllegalStateException(userFacingNetworkError(lastError))
        }
    }

    suspend fun putRecipients(
        userId: String = DEFAULT_USER_ID,
        recipients: List<RecipientProfile>,
        selectedRecipientId: String? = null,
    ): RecipientsResponse {
        return withContext(Dispatchers.IO) {
            val encodedUserId = encodeUserId(userId)
            val requestPayload = JSONObject()
                .put("recipients", recipients.toPayloadRecipients())
                .apply {
                    if (selectedRecipientId != null) {
                        put("selected_recipient_id", selectedRecipientId)
                    }
                }
                .toString()
            var lastError: IOException? = null
            for (baseUrl in orderedBaseUrls()) {
                val request = Request.Builder()
                    .url("$baseUrl/api/user-memory/$encodedUserId/recipients")
                    .header("Connection", "close")
                    .put(requestPayload.toRequestBody(jsonMediaType))
                    .build()
                try {
                    okHttpClient.newCall(request).execute().use { response ->
                        val body = response.body?.string().orEmpty()
                        if (!response.isSuccessful) {
                            val messageText = "HTTP ${response.code}"
                            Log.w(TAG, "$messageText $body")
                            throw IllegalStateException(messageText)
                        }
                        activeBaseUrl = baseUrl
                        return@withContext parseRecipientsResponse(JSONObject(body))
                    }
                } catch (exception: IOException) {
                    Log.w(TAG, "Recipients save failed for $baseUrl", exception)
                    lastError = exception
                }
            }
            throw IllegalStateException(userFacingNetworkError(lastError))
        }
    }

    suspend fun putSelectedRecipient(
        userId: String = DEFAULT_USER_ID,
        selectedRecipientId: String,
    ): RecipientsResponse {
        return withContext(Dispatchers.IO) {
            val encodedUserId = encodeUserId(userId)
            val requestPayload = RecipientSelectionRequest(selectedRecipientId = selectedRecipientId).toJsonPayload().toString()
            var lastError: IOException? = null
            for (baseUrl in orderedBaseUrls()) {
                val request = Request.Builder()
                    .url("$baseUrl/api/user-memory/$encodedUserId/selected-recipient")
                    .header("Connection", "close")
                    .put(requestPayload.toRequestBody(jsonMediaType))
                    .build()
                try {
                    okHttpClient.newCall(request).execute().use { response ->
                        val body = response.body?.string().orEmpty()
                        if (!response.isSuccessful) {
                            val messageText = "HTTP ${response.code}"
                            Log.w(TAG, "$messageText $body")
                            throw IllegalStateException(messageText)
                        }
                        activeBaseUrl = baseUrl
                        return@withContext parseRecipientsResponse(JSONObject(body))
                    }
                } catch (exception: IOException) {
                    Log.w(TAG, "Recipient switch failed for $baseUrl", exception)
                    lastError = exception
                }
            }
            throw IllegalStateException(userFacingNetworkError(lastError))
        }
    }

    suspend fun removeConstraint(
        conversationId: String,
        constraintId: String,
        userId: String = DEFAULT_USER_ID,
        recipientId: String? = null,
    ): List<String> {
        return withContext(Dispatchers.IO) {
            val encodedConversationId = encodeUserId(conversationId.ifBlank { DEFAULT_CONVERSATION_ID })
            val requestPayload = JSONObject()
                .put("user_id", userId.ifBlank { DEFAULT_USER_ID })
                .put("action", "remove")
                .put("constraint_id", constraintId)
                .apply {
                    if (!recipientId.isNullOrBlank()) {
                        put("recipient_id", recipientId)
                    }
                }
                .toString()
            var lastError: IOException? = null
            for (baseUrl in orderedBaseUrls()) {
                val request = Request.Builder()
                    .url("$baseUrl/api/conversations/$encodedConversationId/constraint-actions")
                    .header("Connection", "close")
                    .post(requestPayload.toRequestBody(jsonMediaType))
                    .build()
                try {
                    okHttpClient.newCall(request).execute().use { response ->
                        val body = response.body?.string().orEmpty()
                        if (!response.isSuccessful) {
                            val messageText = "HTTP ${response.code}"
                            Log.w(TAG, "$messageText $body")
                            throw IllegalStateException(messageText)
                        }
                        activeBaseUrl = baseUrl
                        return@withContext parseStringList(JSONObject(body).optJSONArray("removed_constraint_ids"))
                    }
                } catch (exception: IOException) {
                    Log.w(TAG, "Constraint action failed for $baseUrl", exception)
                    lastError = exception
                }
            }
            throw IllegalStateException(userFacingNetworkError(lastError))
        }
    }

    suspend fun submitFeedback(
        feedback: FeedbackType,
        userMessage: String,
        assistantAnswer: String,
        products: List<ProductCard>,
        history: List<ChatMessage>,
        turnId: String,
        conversationId: String = DEFAULT_CONVERSATION_ID,
    ): String {
        return withContext(Dispatchers.IO) {
            val payload = JSONObject()
                .put("conversation_id", conversationId.ifBlank { DEFAULT_CONVERSATION_ID })
                .put("turn_id", turnId)
                .put("feedback", feedback.apiValue)
                .put("message", userMessage)
                .put("retrieval_message", userMessage)
                .put("answer", assistantAnswer)
                .put("history", history.toPayloadHistory())
                .put("products", products.toPayloadProducts())
                .put("trace", JSONObject.NULL)
                .toString()
            var lastError: IOException? = null
            for (baseUrl in orderedBaseUrls()) {
                val request = Request.Builder()
                    .url("$baseUrl/api/feedback")
                    .header("Connection", "close")
                    .post(payload.toRequestBody(jsonMediaType))
                    .build()

                Log.d(TAG, "POST $baseUrl/api/feedback")
                try {
                    okHttpClient.newCall(request).execute().use { response ->
                        val body = response.body?.string().orEmpty()
                        if (!response.isSuccessful) {
                            val messageText = "HTTP ${response.code}"
                            Log.w(TAG, "$messageText $body")
                            throw IllegalStateException(messageText)
                        }
                        activeBaseUrl = baseUrl
                        return@withContext JSONObject(body).optString("record_id")
                    }
                } catch (exception: IOException) {
                    Log.w(TAG, "Feedback request failed for $baseUrl", exception)
                    lastError = exception
                }
            }
            throw IllegalStateException(userFacingNetworkError(lastError))
        }
    }

    suspend fun transcribeAudio(
        audioFile: File,
        profile: String = "bilingual",
        conversationId: String = DEFAULT_CONVERSATION_ID,
    ): AsrTranscriptionResult {
        return withContext(Dispatchers.IO) {
            var lastError: IOException? = null
            for (baseUrl in orderedBaseUrls()) {
                val requestBody = MultipartBody.Builder()
                    .setType(MultipartBody.FORM)
                    .addFormDataPart("profile", profile)
                    .addFormDataPart("conversation_id", conversationId.ifBlank { DEFAULT_CONVERSATION_ID })
                    .addFormDataPart("file", audioFile.name, audioFile.asRequestBody(m4aMediaType))
                    .build()
                val request = Request.Builder()
                    .url("$baseUrl/api/asr/transcribe")
                    .header("Connection", "close")
                    .post(requestBody)
                    .build()

                Log.d(TAG, "POST $baseUrl/api/asr/transcribe")
                try {
                    okHttpClient.newCall(request).execute().use { response ->
                        val body = response.body?.string().orEmpty()
                        if (!response.isSuccessful) {
                            val messageText = "HTTP ${response.code}"
                            Log.w(TAG, "$messageText $body")
                            throw IllegalStateException(messageText)
                        }
                        activeBaseUrl = baseUrl
                        return@withContext parseAsrResult(JSONObject(body))
                    }
                } catch (exception: IOException) {
                    Log.w(TAG, "ASR request failed for $baseUrl", exception)
                    lastError = exception
                }
            }
            throw IllegalStateException(userFacingNetworkError(lastError))
        }
    }

    private suspend fun streamChatFromBaseUrl(
        baseUrl: String,
        payload: String,
        onEvent: suspend (StreamEvent) -> Unit,
    ) {
        val request = Request.Builder()
            .url("$baseUrl/api/chat/stream")
            .header("Accept", "text/event-stream")
            .header("Connection", "close")
            .post(payload.toRequestBody(jsonMediaType))
            .build()

        Log.d(TAG, "POST $baseUrl/api/chat/stream")
        okHttpClient.newCall(request).execute().use { response ->
            if (!response.isSuccessful) {
                val messageText = "HTTP ${response.code}"
                Log.w(TAG, messageText)
                onEvent(StreamEvent.Error(messageText))
                return
            }
            activeBaseUrl = baseUrl
            onEvent(StreamEvent.Connection(baseUrl))
            val source = response.body?.source()
            if (source == null) {
                Log.w(TAG, "Empty response body")
                onEvent(StreamEvent.Error("Empty response body"))
                return
            }

            var completed = false
            var eventName = ""
            val dataLines = mutableListOf<String>()
            while (!completed) {
                val line = source.readUtf8Line() ?: break
                when {
                    line.startsWith("event:") -> eventName = line.removePrefix("event:").trim()
                    line.startsWith("data:") -> dataLines += line.removePrefix("data:").trim()
                    line.isBlank() && eventName.isNotBlank() -> {
                        parseEvent(eventName, dataLines.joinToString("\n"))?.let { event ->
                            onEvent(event)
                            completed = event is StreamEvent.Done
                        }
                        eventName = ""
                        dataLines.clear()
                    }
                }
            }
            if (!completed) {
                onEvent(StreamEvent.Done)
            }
        }
    }

    private fun parseEvent(eventName: String, data: String): StreamEvent? {
        val json = if (data.isBlank()) JSONObject() else JSONObject(data)
        return when (eventName) {
            "status" -> StreamEvent.Status(json.optString("status"))
            "token" -> StreamEvent.Token(json.optString("token"))
            "products" -> StreamEvent.Products(parseProducts(json.optJSONArray("products") ?: JSONArray()))
            "constraints" -> StreamEvent.Constraints(parseConstraintChips(json.optJSONArray("constraints") ?: JSONArray()))
            "quick_reply" -> StreamEvent.QuickReply(
                text = json.optString("text"),
                ephemeral = json.optBoolean("ephemeral", true),
                source = json.optString("source", "template"),
            )
            "done" -> StreamEvent.Done
            "error" -> StreamEvent.Error(json.optString("message", "Unknown error"))
            else -> null
        }
    }

    private fun parseAsrResult(json: JSONObject): AsrTranscriptionResult {
        return AsrTranscriptionResult(
            ok = json.optBoolean("ok"),
            text = json.optString("text"),
            error = json.optString("error").takeIf { it.isNotBlank() && it != "null" },
            traceId = json.optString("asr_trace_id").takeIf { it.isNotBlank() },
        )
    }

    private fun List<ChatMessage>.toPayloadHistory(): JSONArray {
        val array = JSONArray()
        takeLast(8)
            .filter {
                it.content.isNotBlank() &&
                    !it.isEphemeral &&
                    it.role in setOf(Role.User, Role.Assistant)
            }
            .forEach { message ->
                val role = when (message.role) {
                    Role.User -> "user"
                    Role.Assistant -> "assistant"
                    else -> return@forEach
                }
                array.put(
                    JSONObject()
                        .put("role", role)
                        .put("content", message.content)
                        .put("product_ids", JSONArray(message.products.map { it.productId }))
                )
            }
        return array
    }

    private fun List<ChatImage>.toPayloadImages(): JSONArray {
        val array = JSONArray()
        forEach { image ->
            val item = JSONObject()
                .put("image_id", image.imageId.orEmpty())
                .put("mime_type", image.mimeType ?: JSONObject.NULL)
                .put("source", image.source.apiValue)
                .put("preview_url", image.previewUrl ?: JSONObject.NULL)
                .put("summary", image.summary ?: JSONObject.NULL)
                .put("query_text", image.queryText ?: JSONObject.NULL)

            val plan = image.imagePlanJson
                ?.takeIf { it.isNotBlank() }
                ?.let { runCatching { JSONObject(it) }.getOrNull() }
                ?: JSONObject()

            item.put("image_plan", plan)
            array.put(item)
        }
        return array
    }

    private fun List<ProductCard>.toPayloadProducts(): JSONArray {
        val array = JSONArray()
        forEach { product ->
            array.put(product.toPayloadJson())
        }
        return array
    }

    private fun ProductCard.toPayloadJson(): JSONObject {
        return JSONObject()
            .put("product_id", productId)
            .put("title", title)
            .put("brand", brand)
            .put("category", category)
            .put("sub_category", subCategory)
            .put("price", price)
            .put("image_path", imagePath)
            .put("tags", JSONArray(tags))
            .put("reason", reason)
            .put("target_users", JSONArray(targetUsers))
            .put("use_cases", JSONArray(useCases))
            .put("selling_points", JSONArray(sellingPoints))
            .put("cautions", JSONArray(cautions))
            .put("suitable_for", JSONArray(suitableFor))
            .put("avoid_for", JSONArray(avoidFor))
            .put("description", description)
            .put("variants", variants.toPayloadVariants())
    }

    private fun List<ProductVariantCard>.toPayloadVariants(): JSONArray {
        val array = JSONArray()
        forEach { variant ->
            array.put(
                JSONObject()
                    .put("variant_id", variant.variantId)
                    .put("parent_product_id", variant.parentProductId)
                    .put("label", variant.label)
                    .put("properties", JSONObject(variant.properties))
                    .put("price", variant.price)
                    .put("image_path", variant.imagePath)
                    .put("reason", variant.reason)
            )
        }
        return array
    }

    private fun parseProducts(array: JSONArray): List<ProductCard> {
        return buildList {
            for (index in 0 until array.length()) {
                val item = array.getJSONObject(index)
                val tags = item.optJSONArray("tags") ?: JSONArray()
                add(
                    ProductCard(
                        productId = item.getString("product_id"),
                        title = item.getString("title"),
                        brand = item.getString("brand"),
                        category = item.getString("category"),
                        subCategory = item.getString("sub_category"),
                        price = item.getDouble("price"),
                        imagePath = item.optString("image_path"),
                        tags = parseStringList(tags),
                        reason = item.optString("reason"),
                        targetUsers = parseStringList(item.optJSONArray("target_users")),
                        useCases = parseStringList(item.optJSONArray("use_cases")),
                        sellingPoints = parseStringList(item.optJSONArray("selling_points")),
                        cautions = parseStringList(item.optJSONArray("cautions")),
                        suitableFor = parseStringList(item.optJSONArray("suitable_for")),
                        avoidFor = parseStringList(item.optJSONArray("avoid_for")),
                        description = item.optString("description"),
                        variants = parseVariants(item.optJSONArray("variants")),
                    )
                )
            }
        }
    }

    private fun parseConstraintChips(array: JSONArray): List<ConstraintChip> {
        return buildList {
            for (index in 0 until array.length()) {
                val item = array.getJSONObject(index)
                add(
                    ConstraintChip(
                        id = item.optString("id"),
                        type = item.optString("type"),
                        label = item.optString("label"),
                        value = item.opt("value")?.toString().orEmpty(),
                        source = item.optString("source", "effective"),
                        scope = item.optString("scope", "session"),
                        removable = item.optBoolean("removable", true),
                    )
                )
            }
        }.filter { it.id.isNotBlank() && it.label.isNotBlank() }
    }

    private fun parseVariants(array: JSONArray?): List<ProductVariantCard> {
        if (array == null) return emptyList()
        return buildList {
            for (index in 0 until array.length()) {
                val item = array.getJSONObject(index)
                add(
                    ProductVariantCard(
                        variantId = item.optString("variant_id"),
                        parentProductId = item.optString("parent_product_id"),
                        label = item.optString("label"),
                        properties = parseStringMap(item.optJSONObject("properties")),
                        price = item.optDouble("price"),
                        imagePath = item.optString("image_path"),
                        reason = item.optString("reason"),
                    )
                )
            }
        }
    }

    private fun parseStringList(array: JSONArray?): List<String> {
        if (array == null) return emptyList()
        return List(array.length()) { index -> array.optString(index) }.filter { it.isNotBlank() }
    }

    private fun parseRecipientConstraintList(array: JSONArray?): List<String> {
        return parseStringList(array)
    }

    private fun parseRecipientFloatMap(json: JSONObject?): Map<String, Double> {
        if (json == null) return emptyMap()
        val result = mutableMapOf<String, Double>()
        val keys = json.keys()
        while (keys.hasNext()) {
            val key = keys.next()
            val raw = json.optDouble(key)
            result[key] = if (raw.isFinite()) raw else 1.0
        }
        return result
    }

    private fun parseRecipientConstraints(json: JSONObject?): RecipientConstraints {
        if (json == null) return RecipientConstraints()
        return RecipientConstraints(
            allergies = parseRecipientConstraintList(json.optJSONArray("allergies")),
            avoidTerms = parseRecipientConstraintList(json.optJSONArray("avoid_terms")),
            brandExclude = parseRecipientConstraintList(json.optJSONArray("brand_exclude")),
            budgetMax = json.optDouble("budget_max").takeIf { it.isFinite() && !json.isNull("budget_max") },
            accessibilityNeeds = parseRecipientConstraintList(json.optJSONArray("accessibility_needs")),
        )
    }

    private fun parseRecipientLongTermPreferences(json: JSONObject?): RecipientLongTermPreferences {
        if (json == null) return RecipientLongTermPreferences()
        return RecipientLongTermPreferences(
            preferredCategories = parseRecipientFloatMap(json.optJSONObject("preferred_categories")),
            preferredTags = parseRecipientFloatMap(json.optJSONObject("preferred_tags")),
            priceSensitivity = json.optDouble("price_sensitivity").takeIf { it.isFinite() && !json.isNull("price_sensitivity") },
        )
    }

    private fun parseRecipientBodyProfile(json: JSONObject?): RecipientBodyProfile {
        if (json == null) return RecipientBodyProfile()
        return RecipientBodyProfile(
            skinType = json.optString("skin_type").takeIf { it.isNotBlank() },
            shoeSize = json.optString("shoe_size").takeIf { it.isNotBlank() },
            clothingSize = json.optString("clothing_size").takeIf { it.isNotBlank() },
        )
    }

    private fun parseRecipientShipping(json: JSONObject?): RecipientShipping {
        if (json == null) return RecipientShipping()
        return RecipientShipping(
            phone = json.optString("phone").takeIf { it.isNotBlank() },
            address = json.optString("address").takeIf { it.isNotBlank() },
        )
    }

    private fun parseRecipientProfiles(array: JSONArray?): List<RecipientProfile> {
        if (array == null) return emptyList()
        return buildList {
        for (index in 0 until array.length()) {
                val item = array.optJSONObject(index) ?: continue
                val displayName = item.optString("display_name").ifBlank { "对象" }
                val isDefaultSelf = displayName == "自己" || item.optString("relationship") == "self"
                val fallbackId = if (isDefaultSelf) {
                    "self"
                } else {
                    "recipient-${index}"
                }
                add(
                    RecipientProfile(
                        recipientId = fallbackId,
                        displayName = displayName,
                        relationship = item.optString("relationship").takeIf { it.isNotBlank() },
                        constraints = parseRecipientConstraints(item.optJSONObject("constraints")),
                        longTermPreferences = parseRecipientLongTermPreferences(item.optJSONObject("long_term_preferences")),
                        shipping = parseRecipientShipping(item.optJSONObject("shipping")),
                        bodyProfile = parseRecipientBodyProfile(item.optJSONObject("body_profile")),
                        updatedAt = item.optString("updated_at").takeIf { it.isNotBlank() },
                    )
                )
            }
        }
    }

    private fun parseRecipientsResponse(json: JSONObject): RecipientsResponse {
        return RecipientsResponse(
            userId = json.optString("user_id"),
            selectedRecipientId = json.optString("selected_recipient_id"),
            recipients = parseRecipientProfiles(json.optJSONArray("recipients")),
            updatedAt = json.optString("updated_at").takeIf { it.isNotBlank() },
        )
    }

    private fun RecipientConstraints.toPayloadJson(): JSONObject {
        return JSONObject()
            .put("allergies", JSONArray(allergies))
            .put("avoid_terms", JSONArray(avoidTerms))
            .put("brand_exclude", JSONArray(brandExclude))
            .put(
                "budget_max",
                budgetMax
                    ?.let { it }
                    ?: JSONObject.NULL,
            )
            .put("accessibility_needs", JSONArray(accessibilityNeeds))
    }

    private fun RecipientLongTermPreferences.toPayloadJson(): JSONObject {
        return JSONObject()
            .put("preferred_categories", JSONObject(preferredCategories))
            .put("preferred_tags", JSONObject(preferredTags))
            .put(
                "price_sensitivity",
                priceSensitivity
                    ?.let { it }
                    ?: JSONObject.NULL,
            )
    }

    private fun RecipientBodyProfile.toPayloadJson(): JSONObject {
        return JSONObject()
            .put(
                "skin_type",
                skinType
                    ?.let { it }
                    ?: JSONObject.NULL,
            )
            .put(
                "shoe_size",
                shoeSize
                    ?.let { it }
                    ?: JSONObject.NULL,
            )
            .put(
                "clothing_size",
                clothingSize
                    ?.let { it }
                    ?: JSONObject.NULL,
            )
    }

    private fun RecipientShipping.toPayloadJson(): JSONObject {
        return JSONObject()
            .put(
                "address_label",
                addressLabel
                    ?.let { it }
                    ?: JSONObject.NULL,
            )
            .put(
                "recipient_name",
                recipientName
                    ?.let { it }
                    ?: JSONObject.NULL,
            )
            .put(
                "phone",
                phone
                    ?.let { it }
                    ?: JSONObject.NULL,
            )
            .put(
                "address",
                address
                    ?.let { it }
                    ?: JSONObject.NULL,
            )
    }

    private fun RecipientShipping.toManagementPayloadJson(): JSONObject {
        return JSONObject()
            .put(
                "phone",
                phone
                    ?.let { it }
                    ?: JSONObject.NULL,
            )
            .put(
                "address",
                address
                    ?.let { it }
                    ?: JSONObject.NULL,
            )
    }

    private fun RecipientProfile.toPayloadJson(): JSONObject {
        return JSONObject()
            .put("display_name", displayName)
            .put(
                "relationship",
                relationship
                    ?.let { it }
                    ?: JSONObject.NULL,
            )
            .put("shipping", shipping.toManagementPayloadJson())
    }

    private fun List<RecipientProfile>.toPayloadRecipients(): JSONArray {
        return JSONArray().apply {
            forEach { recipient ->
                put(recipient.toPayloadJson())
            }
        }
    }

    private fun RecipientSelectionRequest.toJsonPayload(): JSONObject {
        return JSONObject().put("selected_recipient_id", selectedRecipientId)
    }

    private fun encodeUserId(userId: String): String {
        return try {
            URLEncoder.encode(userId, UTF_8.name())
        } catch (exception: Exception) {
            userId
        }
    }

    private fun parseStringMap(json: JSONObject?): Map<String, String> {
        if (json == null) return emptyMap()
        val values = mutableMapOf<String, String>()
        val keys = json.keys()
        while (keys.hasNext()) {
            val key = keys.next()
            values[key] = json.optString(key)
        }
        return values.filterValues { it.isNotBlank() }
    }

    companion object {
        // 与后端 user_memory.DEFAULT_MEMORY_USER_ID 对齐的演示默认身份。
        const val DEFAULT_USER_ID = DemoIdentityStore.DefaultUserId
        const val DEFAULT_CONVERSATION_ID = "android-demo"
        const val TAG = "ShoppingAgentClient"
    }

    private fun orderedBaseUrls(): List<String> {
        return (listOf(activeBaseUrl) + baseUrls).distinct()
    }

    private fun userFacingNetworkError(exception: IOException?): String {
        val rawMessage = exception?.localizedMessage ?: "Network request failed"
        return (
            "连接后端失败：请确认 FastAPI 正在 8000 端口运行。"
                + "真机局域网调试请确认手机与电脑同一 Wi-Fi，且 local.properties 的 backend.lan.url 是电脑当前 IP；"
                + "USB/模拟器可执行 adb reverse tcp:8000 tcp:8000。"
                + "已尝试地址：${baseUrls.joinToString("、")}。"
                + "原始错误：$rawMessage"
            )
    }
}
