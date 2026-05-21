package com.saki.bytedance.ragshopping

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONObject

sealed interface StreamEvent {
    data class Status(val value: String) : StreamEvent
    data class Token(val value: String) : StreamEvent
    data class Products(val value: List<ProductCard>) : StreamEvent
    data object Done : StreamEvent
    data class Error(val message: String) : StreamEvent
}

class ShoppingAgentClient(
    private val baseUrl: String = "http://10.0.2.2:8000",
    private val okHttpClient: OkHttpClient = OkHttpClient(),
) {
    private val jsonMediaType = "application/json; charset=utf-8".toMediaType()

    suspend fun streamChat(message: String, onEvent: suspend (StreamEvent) -> Unit) {
        withContext(Dispatchers.IO) {
            val payload = JSONObject()
                .put("message", message)
                .put("conversation_id", "android-demo")
                .put("history", JSONArray())
                .toString()
            val request = Request.Builder()
                .url("$baseUrl/api/chat/stream")
                .post(payload.toRequestBody(jsonMediaType))
                .build()

            okHttpClient.newCall(request).execute().use { response ->
                if (!response.isSuccessful) {
                    onEvent(StreamEvent.Error("HTTP ${response.code}"))
                    return@withContext
                }
                val source = response.body?.source()
                if (source == null) {
                    onEvent(StreamEvent.Error("Empty response body"))
                    return@withContext
                }

                var eventName = ""
                val dataLines = mutableListOf<String>()
                while (!source.exhausted()) {
                    val line = source.readUtf8Line() ?: break
                    when {
                        line.startsWith("event:") -> eventName = line.removePrefix("event:").trim()
                        line.startsWith("data:") -> dataLines += line.removePrefix("data:").trim()
                        line.isBlank() && eventName.isNotBlank() -> {
                            parseEvent(eventName, dataLines.joinToString("\n"))?.let { onEvent(it) }
                            eventName = ""
                            dataLines.clear()
                        }
                    }
                }
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
                        tags = List(tags.length()) { tags.getString(it) },
                        reason = item.optString("reason"),
                    )
                )
            }
        }
    }
}
