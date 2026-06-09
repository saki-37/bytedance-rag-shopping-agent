package com.saki.bytedance.ragshopping

import java.util.UUID

data class ProductCard(
    val productId: String,
    val title: String,
    val brand: String,
    val category: String,
    val subCategory: String,
    val price: Double,
    val imagePath: String,
    val tags: List<String>,
    val reason: String,
    val targetUsers: List<String> = emptyList(),
    val useCases: List<String> = emptyList(),
    val sellingPoints: List<String> = emptyList(),
    val cautions: List<String> = emptyList(),
    val suitableFor: List<String> = emptyList(),
    val avoidFor: List<String> = emptyList(),
    val description: String = "",
    val variants: List<ProductVariantCard> = emptyList(),
)

data class ProductVariantCard(
    val variantId: String,
    val parentProductId: String,
    val label: String,
    val properties: Map<String, String> = emptyMap(),
    val price: Double,
    val imagePath: String,
    val reason: String,
)

data class ChatMessage(
    val role: Role,
    val content: String,
    val products: List<ProductCard> = emptyList(),
    val isEphemeral: Boolean = false,
    val isQuickReply: Boolean = false,
    val feedback: FeedbackType? = null,
    val isFeedbackSending: Boolean = false,
    val feedbackError: String? = null,
    val id: String = UUID.randomUUID().toString(),
)

data class AsrTranscriptionResult(
    val ok: Boolean,
    val text: String,
    val error: String?,
    val traceId: String?,
)

enum class Role {
    User,
    Assistant,
    Status,
    Error,
}

enum class FeedbackType(val apiValue: String, val label: String) {
    Helpful("helpful", "有用"),
    Inaccurate("inaccurate", "不准确"),
}
