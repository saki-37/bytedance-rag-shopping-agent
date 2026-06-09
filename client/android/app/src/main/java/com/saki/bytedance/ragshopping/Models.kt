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

data class RecipientConstraints(
    val allergies: List<String> = emptyList(),
    val avoidTerms: List<String> = emptyList(),
    val brandExclude: List<String> = emptyList(),
    val budgetMax: Double? = null,
    val accessibilityNeeds: List<String> = emptyList(),
)

data class RecipientLongTermPreferences(
    val preferredCategories: Map<String, Double> = emptyMap(),
    val preferredTags: Map<String, Double> = emptyMap(),
    val priceSensitivity: Double? = null,
)

data class RecipientBodyProfile(
    val skinType: String? = null,
    val shoeSize: String? = null,
    val clothingSize: String? = null,
)

data class RecipientShipping(
    val addressLabel: String? = null,
    val recipientName: String? = null,
    val phone: String? = null,
    val address: String? = null,
)

data class RecipientProfile(
    val recipientId: String,
    val displayName: String,
    val relationship: String? = null,
    val constraints: RecipientConstraints = RecipientConstraints(),
    val longTermPreferences: RecipientLongTermPreferences = RecipientLongTermPreferences(),
    val shipping: RecipientShipping = RecipientShipping(),
    val bodyProfile: RecipientBodyProfile = RecipientBodyProfile(),
    val updatedAt: String? = null,
)

data class RecipientsResponse(
    val userId: String,
    val selectedRecipientId: String,
    val recipients: List<RecipientProfile> = emptyList(),
    val updatedAt: String? = null,
)

data class RecipientSelectionRequest(
    val selectedRecipientId: String,
)

data class RecipientsUpdateRequest(
    val recipients: List<RecipientProfile> = emptyList(),
    val selectedRecipientId: String? = null,
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
