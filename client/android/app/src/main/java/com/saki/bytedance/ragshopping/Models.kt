package com.saki.bytedance.ragshopping

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
)

data class ChatMessage(
    val role: Role,
    val content: String,
    val products: List<ProductCard> = emptyList(),
)

enum class Role {
    User,
    Assistant,
    Status,
    Error,
}
