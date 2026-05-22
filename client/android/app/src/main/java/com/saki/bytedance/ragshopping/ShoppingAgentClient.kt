package com.saki.bytedance.ragshopping

import android.util.Log
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONObject
import java.util.concurrent.TimeUnit

sealed interface StreamEvent {
    data class Status(val value: String) : StreamEvent
    data class Token(val value: String) : StreamEvent
    data class Products(val value: List<ProductCard>) : StreamEvent
    data object Done : StreamEvent
    data class Error(val message: String) : StreamEvent
}

class ShoppingAgentClient(
    private val baseUrl: String = "http://10.0.2.2:8000",
    private val okHttpClient: OkHttpClient = OkHttpClient.Builder()
        .connectTimeout(15, TimeUnit.SECONDS)
        .writeTimeout(15, TimeUnit.SECONDS)
        .readTimeout(0, TimeUnit.MILLISECONDS)
        .build(),
) {
    private val jsonMediaType = "application/json; charset=utf-8".toMediaType()

    suspend fun streamChat(message: String, onEvent: suspend (StreamEvent) -> Unit) {
        withContext(Dispatchers.IO) {
            try {
                val payload = JSONObject()
                    .put("message", message)
                    .put("conversation_id", "android-demo")
                    .put("history", JSONArray())
                    .toString()
                val request = Request.Builder()
                    .url("$baseUrl/api/chat/stream")
                    .post(payload.toRequestBody(jsonMediaType))
                    .build()

                Log.d(TAG, "POST $baseUrl/api/chat/stream")
                okHttpClient.newCall(request).execute().use { response ->
                    if (!response.isSuccessful) {
                        val messageText = "HTTP ${response.code}"
                        Log.w(TAG, messageText)
                        onEvent(StreamEvent.Error(messageText))
                        return@withContext
                    }
                    val source = response.body?.source()
                    if (source == null) {
                        Log.w(TAG, "Empty response body")
                        onEvent(StreamEvent.Error("Empty response body"))
                        return@withContext
                    }

                    var completed = false
                    var eventName = ""
                    val dataLines = mutableListOf<String>()
                    while (!completed && !source.exhausted()) {
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
            } catch (exception: Exception) {
                Log.e(TAG, "Chat stream failed", exception)
                onEvent(StreamEvent.Error(exception.localizedMessage ?: "Network request failed"))
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
}
