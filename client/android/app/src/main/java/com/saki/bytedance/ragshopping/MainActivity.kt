package com.saki.bytedance.ragshopping

import android.net.Uri
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import coil.compose.SubcomposeAsyncImage
import coil.compose.SubcomposeAsyncImageContent

private const val AssetBaseUrl = "http://10.0.2.2:8000/assets"

private val DemoPrompts = listOf(
    "油皮通勤防晒" to "我是油皮，想要200元以内通勤防晒",
    "敏感肌修护" to "敏感肌，最近屏障不稳定，想找修护面霜，不要酒精味太重或者刺激感强的产品",
    "信息不足追问" to "我想买护肤品，你推荐什么？",
    "洁面" to "预算100以内，混合肌日常温和洁面，洗后不要太拔干",
    "眼霜" to "眼周干燥卡粉，有没有350元以内的保湿眼霜",
    "蜜粉" to "油皮夏天想要150元以内控油定妆蜜粉",
    "唇釉" to "学生党想要150元以内日常通勤唇釉，滋润一点",
    "眉笔" to "新手想要100元以内自然防晕染眉笔",
    "卸妆" to "敏感肌想要200元以内温和卸妆，不要酒精",
)

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            MaterialTheme {
                ShoppingAgentApp()
            }
        }
    }
}

@Composable
fun ShoppingAgentApp(viewModel: ChatViewModel = viewModel()) {
    val state by viewModel.state.collectAsState()
    val listState = rememberLazyListState()
    var selectedProduct by remember { mutableStateOf<ProductCard?>(null) }
    val latestMessage = state.messages.lastOrNull()

    LaunchedEffect(state.messages.size, latestMessage?.content?.length, latestMessage?.products?.size) {
        listState.scrollToItem(state.messages.size)
    }

    Surface(color = Color(0xFFF3FBF6), modifier = Modifier.fillMaxSize()) {
        Column(modifier = Modifier.fillMaxSize()) {
            Header()
            LazyColumn(
                state = listState,
                modifier = Modifier
                    .weight(1f)
                    .fillMaxWidth(),
                contentPadding = PaddingValues(16.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                items(state.messages) { message ->
                    MessageBubble(message = message, onProductClick = { selectedProduct = it })
                }
                item("bottom-anchor") {
                    Spacer(modifier = Modifier.height(1.dp))
                }
            }
            InputBar(
                value = state.input,
                isLoading = state.isLoading,
                statusText = state.statusText,
                onValueChange = viewModel::updateInput,
                onSend = viewModel::send,
                onQuickPrompt = viewModel::sendPrompt,
            )
        }
        selectedProduct?.let { product ->
            ProductDetailDialog(product = product, onDismiss = { selectedProduct = null })
        }
    }
}

@Composable
private fun Header() {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .background(Color.White)
            .padding(horizontal = 20.dp, vertical = 16.dp),
    ) {
        Text("RAG 美妆导购", fontWeight = FontWeight.Bold, style = MaterialTheme.typography.titleLarge)
        Text("肤质、预算、场景和排除条件都可以直接说", color = Color(0xFF5D6B63))
    }
}

@Composable
private fun MessageBubble(message: ChatMessage, onProductClick: (ProductCard) -> Unit) {
    val alignment = if (message.role == Role.User) Alignment.End else Alignment.Start
    val background = when (message.role) {
        Role.User -> Color(0xFF0BAE5C)
        Role.Assistant -> Color.White
        Role.Status -> Color(0xFFE4F6EA)
        Role.Error -> Color(0xFFFFECE8)
    }
    val textColor = if (message.role == Role.User) Color.White else Color(0xFF1F2937)

    Column(horizontalAlignment = alignment, modifier = Modifier.fillMaxWidth()) {
        Card(
            colors = CardDefaults.cardColors(containerColor = background),
            shape = RoundedCornerShape(14.dp),
            modifier = Modifier.fillMaxWidth(if (message.role == Role.User) 0.86f else 1f),
        ) {
            Column(modifier = Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                if (message.content.isNotBlank()) {
                    Text(message.content, color = textColor)
                }
                message.products.forEach { ProductCardView(product = it, onClick = { onProductClick(it) }) }
            }
        }
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun ProductCardView(product: ProductCard, onClick: () -> Unit) {
    Card(
        colors = CardDefaults.cardColors(containerColor = Color(0xFFF8FFFA)),
        shape = RoundedCornerShape(12.dp),
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick),
    ) {
        Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                Box(
                    modifier = Modifier
                        .size(52.dp)
                        .clip(CircleShape),
                ) {
                    ProductImage(
                        product = product,
                        modifier = Modifier.fillMaxSize(),
                        fallbackText = product.brand.take(1),
                    )
                }
                Column(modifier = Modifier.weight(1f)) {
                    Text(product.brand, color = Color(0xFF087A42), fontWeight = FontWeight.Bold)
                    Text(product.title, maxLines = 2, style = MaterialTheme.typography.bodySmall)
                }
                Text("¥${product.price.toInt()}", color = Color(0xFFE87800), fontWeight = FontWeight.Bold)
            }
            FlowRow(horizontalArrangement = Arrangement.spacedBy(6.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                product.tags.forEach { tag ->
                    Text(
                        text = tag,
                        modifier = Modifier
                            .background(Color(0xFFFFF1D8), RoundedCornerShape(999.dp))
                            .padding(horizontal = 8.dp, vertical = 3.dp),
                        color = Color(0xFF9A4B00),
                        style = MaterialTheme.typography.labelSmall,
                    )
                }
            }
            Text(product.reason, color = Color(0xFF53635A), style = MaterialTheme.typography.bodySmall)
        }
    }
}

@Composable
private fun ProductDetailDialog(product: ProductCard, onDismiss: () -> Unit) {
    AlertDialog(
        onDismissRequest = onDismiss,
        confirmButton = {
            TextButton(onClick = onDismiss) {
                Text("关闭", color = Color(0xFF087A42))
            }
        },
        title = {
            Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Text(product.brand, color = Color(0xFF087A42), fontWeight = FontWeight.Bold)
                Text(product.title, style = MaterialTheme.typography.titleSmall)
            }
        },
        text = {
            Column(
                modifier = Modifier.verticalScroll(rememberScrollState()),
                verticalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                ProductImage(
                    product = product,
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(150.dp)
                        .clip(RoundedCornerShape(12.dp)),
                    fallbackText = product.brand.take(1),
                )
                Row(horizontalArrangement = Arrangement.spacedBy(10.dp), verticalAlignment = Alignment.CenterVertically) {
                    Text("¥${product.price.toInt()}", color = Color(0xFFE87800), fontWeight = FontWeight.Bold)
                    Text("${product.category} / ${product.subCategory}", color = Color(0xFF53635A))
                }
                DetailSection("推荐理由", listOf(product.reason))
                DetailSection("适合", product.suitableFor.ifEmpty { product.targetUsers })
                DetailSection("使用场景", product.useCases)
                DetailSection("卖点", product.sellingPoints)
                DetailSection("注意事项", product.cautions)
                DetailSection("不适合", product.avoidFor)
                if (product.description.isNotBlank()) {
                    Text("资料依据", color = Color(0xFF087A42), fontWeight = FontWeight.Bold)
                    Text(product.description, color = Color(0xFF53635A), style = MaterialTheme.typography.bodySmall)
                }
            }
        },
        containerColor = Color.White,
    )
}

@Composable
private fun ProductImage(product: ProductCard, modifier: Modifier, fallbackText: String) {
    SubcomposeAsyncImage(
        model = product.imageUrl(),
        contentDescription = product.title,
        contentScale = ContentScale.Crop,
        modifier = modifier.background(Color(0xFFDFF5E8)),
        loading = { ProductImageFallback(fallbackText) },
        error = { ProductImageFallback(fallbackText) },
        success = { SubcomposeAsyncImageContent() },
    )
}

@Composable
private fun ProductImageFallback(text: String) {
    Box(
        modifier = Modifier.fillMaxSize(),
        contentAlignment = Alignment.Center,
    ) {
        Text(text, fontWeight = FontWeight.Bold, color = Color(0xFF087A42))
    }
}

private fun ProductCard.imageUrl(): String {
    val encodedPath = imagePath
        .split("/")
        .joinToString("/") { segment -> Uri.encode(segment) }
    return "$AssetBaseUrl/$encodedPath"
}

@Composable
private fun DetailSection(title: String, values: List<String>) {
    val visibleValues = values.filter { it.isNotBlank() }
    if (visibleValues.isEmpty()) return

    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Text(title, color = Color(0xFF087A42), fontWeight = FontWeight.Bold)
        visibleValues.forEach { value ->
            Text("• $value", color = Color(0xFF53635A), style = MaterialTheme.typography.bodySmall)
        }
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun InputBar(
    value: String,
    isLoading: Boolean,
    statusText: String?,
    onValueChange: (String) -> Unit,
    onSend: () -> Unit,
    onQuickPrompt: (String) -> Unit,
) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .background(Color.White)
            .padding(12.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        if (statusText != null) {
            Text(
                text = statusText,
                modifier = Modifier
                    .fillMaxWidth()
                    .background(Color(0xFFE4F6EA), RoundedCornerShape(10.dp))
                    .padding(horizontal = 12.dp, vertical = 8.dp),
                color = Color(0xFF087A42),
                style = MaterialTheme.typography.bodySmall,
            )
        }
        FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            DemoPrompts.forEach { (label, prompt) ->
                Text(
                    text = label,
                    modifier = Modifier
                        .background(Color(0xFFE4F6EA), RoundedCornerShape(999.dp))
                        .clickable(enabled = !isLoading) { onQuickPrompt(prompt) }
                        .padding(horizontal = 10.dp, vertical = 6.dp),
                    color = Color(0xFF087A42),
                    style = MaterialTheme.typography.labelMedium,
                )
            }
        }
        Row(
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            OutlinedTextField(
                value = value,
                onValueChange = onValueChange,
                modifier = Modifier.weight(1f),
                minLines = 1,
                maxLines = 3,
                placeholder = { Text("例如：我是油皮，想要200元以内通勤防晒") },
            )
            Button(
                onClick = onSend,
                enabled = !isLoading && value.isNotBlank(),
                colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF0BAE5C)),
            ) {
                Text(if (isLoading) "中" else "发")
            }
        }
    }
    Spacer(modifier = Modifier.height(4.dp))
}
