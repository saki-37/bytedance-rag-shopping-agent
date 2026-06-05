package com.saki.bytedance.ragshopping

import android.util.Log
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.ConnectionPool
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONObject
import java.io.IOException
import java.util.concurrent.TimeUnit

sealed interface StreamEvent {
    data class Status(val value: String) : StreamEvent
    data class Token(val value: String) : StreamEvent
    data class Products(val value: List<ProductCard>) : StreamEvent
    data object Done : StreamEvent
    data class Error(val message: String) : StreamEvent
    data class Connection(val baseUrl: String) : StreamEvent
}

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
    @Volatile
    private var activeBaseUrl: String = baseUrls.firstOrNull() ?: BackendConfig.DefaultBaseUrl

    suspend fun streamChat(
        message: String,
        history: List<ChatMessage> = emptyList(),
        onEvent: suspend (StreamEvent) -> Unit,
    ) {
        withContext(Dispatchers.IO) {
            val payload = JSONObject()
                .put("message", message)
                .put("conversation_id", "android-demo")
                .put("history", history.toPayloadHistory())
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

    suspend fun submitFeedback(
        feedback: FeedbackType,
        userMessage: String,
        assistantAnswer: String,
        products: List<ProductCard>,
        history: List<ChatMessage>,
        turnId: String,
    ): String {
        return withContext(Dispatchers.IO) {
            val payload = JSONObject()
                .put("conversation_id", "android-demo")
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
            "done" -> StreamEvent.Done
            "error" -> StreamEvent.Error(json.optString("message", "Unknown error"))
            else -> null
        }
    }

    private fun List<ChatMessage>.toPayloadHistory(): JSONArray {
        val array = JSONArray()
        takeLast(8)
            .filter { it.content.isNotBlank() && it.role in setOf(Role.User, Role.Assistant) }
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
                    )
                )
            }
        }
    }

    private fun parseStringList(array: JSONArray?): List<String> {
        if (array == null) return emptyList()
        return List(array.length()) { index -> array.optString(index) }.filter { it.isNotBlank() }
    }

    private companion object {
        const val TAG = "ShoppingAgentClient"
    }

    private fun orderedBaseUrls(): List<String> {
        return (listOf(activeBaseUrl) + baseUrls).distinct()
    }

    private fun userFacingNetworkError(exception: IOException?): String {
        val rawMessage = exception?.localizedMessage ?: "Network request failed"
        return (
            "连接后端失败：请确认 FastAPI 正在 8000 端口运行。"
                + "模拟器可先执行 adb reverse tcp:8000 tcp:8000；"
                + "若不使用 adb reverse，请确认 10.0.2.2:8000 可访问。"
                + "原始错误：$rawMessage"
            )
    }
}
