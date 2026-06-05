package com.saki.bytedance.ragshopping

import android.net.Uri
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.BorderStroke
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
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
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
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.StrokeJoin
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.graphics.vector.path
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import coil.compose.SubcomposeAsyncImage
import coil.compose.SubcomposeAsyncImageContent
import kotlinx.coroutines.delay

private val AppGreen = Color(0xFFB7D65A)
private val AppGreenSoft = Color(0xFFEAF6D5)
private val SurfaceCream = Color(0xFFFAFFE9)
private val SurfaceWhite = Color(0xFFFFFEF8)
private val Ink = Color(0xFF10130E)
private val AccentGreen = Color(0xFF94B92B)
private val AccentGreenDark = Color(0xFF526D13)
private val BorderGreen = Color(0xFFD4E99A)
private val MutedText = Color(0xFF5F6A4E)
private val WarmSurface = Color(0xFFFFF1D5)
private val ErrorSurface = Color(0xFFFFEAE0)
private val ErrorText = Color(0xFF9E3412)
private val TablerSendIcon: ImageVector = ImageVector.Builder(
    name = "TablerSend",
    defaultWidth = 24.dp,
    defaultHeight = 24.dp,
    viewportWidth = 24f,
    viewportHeight = 24f,
).apply {
    path(
        fill = null,
        stroke = SolidColor(Color.Black),
        strokeLineWidth = 2f,
        strokeLineCap = StrokeCap.Round,
        strokeLineJoin = StrokeJoin.Round,
    ) {
        moveTo(10f, 14f)
        lineTo(21f, 3f)
        moveTo(21f, 3f)
        lineTo(14.5f, 21f)
        arcToRelative(0.55f, 0.55f, 0f, false, true, -1f, 0f)
        lineTo(10f, 14f)
        lineTo(3f, 10.5f)
        arcToRelative(0.55f, 0.55f, 0f, false, true, 0f, -1f)
        lineTo(21f, 3f)
    }
}.build()

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
    val assetBaseUrl = "${state.backendBaseUrl.trimEnd('/')}/assets"

    LaunchedEffect(state.messages.size, latestMessage?.content?.length, latestMessage?.products?.size) {
        listState.scrollToItem(state.messages.size)
    }

    Surface(color = AppGreen, modifier = Modifier.fillMaxSize()) {
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
                itemsIndexed(
                    items = state.messages,
                    key = { _, message -> message.id },
                ) { index, message ->
                    val hasPriorUserMessage = state.messages
                        .take(index)
                        .any { it.role == Role.User && it.content.isNotBlank() }
                    val isThinking = state.isLoading &&
                        index == state.messages.lastIndex &&
                        message.role == Role.Assistant &&
                        message.content.isBlank()
                    MessageBubble(
                        message = message,
                        showFeedback = !state.isLoading && hasPriorUserMessage,
                        isThinking = isThinking,
                        assetBaseUrl = assetBaseUrl,
                        onProductClick = { selectedProduct = it },
                        onFeedback = viewModel::submitFeedback,
                    )
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
            ProductDetailDialog(product = product, assetBaseUrl = assetBaseUrl, onDismiss = { selectedProduct = null })
        }
    }
}

@Composable
private fun Header() {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .background(AppGreen)
            .padding(horizontal = 20.dp, vertical = 18.dp),
        verticalArrangement = Arrangement.spacedBy(6.dp),
    ) {
        Text(
            text = "RAG 美妆导购",
            color = Ink,
            fontWeight = FontWeight.Bold,
            style = MaterialTheme.typography.headlineSmall,
        )
        Text(
            text = "肤质、预算、场景和排除条件都可以直接说",
            color = AccentGreenDark,
            style = MaterialTheme.typography.bodyMedium,
        )
    }
}

@Composable
private fun MessageBubble(
    message: ChatMessage,
    showFeedback: Boolean,
    isThinking: Boolean,
    assetBaseUrl: String,
    onProductClick: (ProductCard) -> Unit,
    onFeedback: (String, FeedbackType) -> Unit,
) {
    val alignment = if (message.role == Role.User) Alignment.End else Alignment.Start
    val background = when (message.role) {
        Role.User -> Ink
        Role.Assistant -> SurfaceCream
        Role.Status -> AppGreenSoft
        Role.Error -> ErrorSurface
    }
    val textColor = when (message.role) {
        Role.User -> SurfaceWhite
        Role.Error -> ErrorText
        else -> Ink
    }
    val border = if (message.role == Role.User) null else BorderStroke(1.dp, BorderGreen)

    Column(horizontalAlignment = alignment, modifier = Modifier.fillMaxWidth()) {
        Card(
            colors = CardDefaults.cardColors(containerColor = background),
            shape = RoundedCornerShape(22.dp),
            border = border,
            elevation = CardDefaults.cardElevation(defaultElevation = 0.dp),
            modifier = Modifier.fillMaxWidth(if (message.role == Role.User) 0.86f else 1f),
        ) {
            Column(modifier = Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                if (isThinking) {
                    ThinkingIndicator()
                } else if (message.content.isNotBlank()) {
                    Text(
                        text = message.content,
                        color = textColor,
                        style = MaterialTheme.typography.bodyMedium,
                    )
                }
                message.products.forEach {
                    ProductCardView(product = it, assetBaseUrl = assetBaseUrl, onClick = { onProductClick(it) })
                }
                if (message.role == Role.Assistant && message.content.isNotBlank() && showFeedback) {
                    FeedbackControls(message = message, onFeedback = onFeedback)
                }
            }
        }
    }
}

@Composable
private fun ThinkingIndicator() {
    var dotCount by remember { mutableStateOf(1) }

    LaunchedEffect(Unit) {
        while (true) {
            delay(420)
            dotCount = dotCount % 3 + 1
        }
    }

    Row(
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        CircularProgressIndicator(
            modifier = Modifier.size(18.dp),
            color = AccentGreenDark,
            strokeWidth = 2.dp,
        )
        Text(
            text = "正在思考中" + ".".repeat(dotCount),
            color = MutedText,
            style = MaterialTheme.typography.bodyMedium,
        )
    }
}

@Composable
private fun FeedbackControls(message: ChatMessage, onFeedback: (String, FeedbackType) -> Unit) {
    when {
        message.feedback != null -> {
            Text(
                text = "已记录：${message.feedback.label}",
                color = AccentGreenDark,
                style = MaterialTheme.typography.labelMedium,
            )
        }

        message.isFeedbackSending -> {
            Text(
                text = "正在记录反馈...",
                color = MutedText,
                style = MaterialTheme.typography.labelMedium,
            )
        }

        else -> {
            Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    FeedbackChip(label = "有用") { onFeedback(message.id, FeedbackType.Helpful) }
                    FeedbackChip(label = "不准确") { onFeedback(message.id, FeedbackType.Inaccurate) }
                }
                if (message.feedbackError != null) {
                    Text(
                        text = "记录失败：${message.feedbackError}",
                        color = ErrorText,
                        style = MaterialTheme.typography.labelSmall,
                    )
                }
            }
        }
    }
}

@Composable
private fun FeedbackChip(label: String, onClick: () -> Unit) {
    Text(
        text = label,
        modifier = Modifier
            .background(AppGreenSoft, RoundedCornerShape(999.dp))
            .clickable(onClick = onClick)
            .padding(horizontal = 10.dp, vertical = 5.dp),
        color = AccentGreenDark,
        style = MaterialTheme.typography.labelMedium,
    )
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun ProductCardView(product: ProductCard, assetBaseUrl: String, onClick: () -> Unit) {
    Card(
        colors = CardDefaults.cardColors(containerColor = SurfaceWhite),
        shape = RoundedCornerShape(20.dp),
        border = BorderStroke(1.dp, BorderGreen),
        elevation = CardDefaults.cardElevation(defaultElevation = 0.dp),
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick),
    ) {
        Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                Box(
                    modifier = Modifier
                        .size(62.dp)
                        .clip(RoundedCornerShape(18.dp)),
                ) {
                    ProductImage(
                        product = product,
                        assetBaseUrl = assetBaseUrl,
                        modifier = Modifier.fillMaxSize(),
                        fallbackText = product.brand.take(1),
                    )
                }
                Column(modifier = Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(3.dp)) {
                    Text(
                        text = product.brand,
                        color = AccentGreenDark,
                        fontWeight = FontWeight.Bold,
                        style = MaterialTheme.typography.labelLarge,
                    )
                    Text(
                        text = product.title,
                        color = Ink,
                        maxLines = 2,
                        style = MaterialTheme.typography.bodySmall,
                    )
                }
                Text(
                    text = "¥${product.price.toInt()}",
                    modifier = Modifier
                        .background(Ink, RoundedCornerShape(999.dp))
                        .padding(horizontal = 10.dp, vertical = 6.dp),
                    color = SurfaceWhite,
                    fontWeight = FontWeight.Bold,
                    style = MaterialTheme.typography.labelMedium,
                )
            }
            FlowRow(horizontalArrangement = Arrangement.spacedBy(6.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                product.tags.forEach { tag ->
                    Text(
                        text = tag,
                        modifier = Modifier
                            .background(WarmSurface, RoundedCornerShape(999.dp))
                            .padding(horizontal = 8.dp, vertical = 3.dp),
                        color = AccentGreenDark,
                        style = MaterialTheme.typography.labelSmall,
                    )
                }
            }
            Text(
                text = product.reason,
                color = MutedText,
                style = MaterialTheme.typography.bodySmall,
            )
        }
    }
}

@Composable
private fun ProductDetailDialog(product: ProductCard, assetBaseUrl: String, onDismiss: () -> Unit) {
    val knowledge = remember(product.description) { product.knowledgeSections() }

    AlertDialog(
        onDismissRequest = onDismiss,
        confirmButton = {
            TextButton(onClick = onDismiss) {
                Text("关闭", color = AccentGreenDark, fontWeight = FontWeight.Bold)
            }
        },
        title = {
            Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                Text(
                    text = product.brand,
                    color = AccentGreenDark,
                    fontWeight = FontWeight.Bold,
                    style = MaterialTheme.typography.labelLarge,
                )
                Text(
                    text = product.title,
                    color = Ink,
                    style = MaterialTheme.typography.titleMedium,
                )
            }
        },
        text = {
            Column(
                modifier = Modifier.verticalScroll(rememberScrollState()),
                verticalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                DetailHeroCard(product = product, assetBaseUrl = assetBaseUrl)
                DetailSectionCard(
                    title = "推荐理由",
                    values = listOf(product.reason),
                    containerColor = Ink,
                    titleColor = AppGreen,
                    bodyColor = SurfaceWhite,
                    bullet = false,
                )
                DetailChipsCard("适合人群", product.suitableFor.ifEmpty { product.targetUsers })
                DetailChipsCard("使用场景", product.useCases, containerColor = AppGreenSoft)
                DetailChipsCard("核心卖点", product.sellingPoints)
                DetailSectionCard("官方 FAQ", knowledge.officialFaq.take(2), numbered = true)
                DetailSectionCard(
                    title = "用户精选评论",
                    values = knowledge.userReviews.take(2),
                    containerColor = AppGreenSoft,
                    titleColor = AccentGreenDark,
                    bullet = false,
                )
                DetailSectionCard(
                    title = "注意和避坑",
                    values = product.cautions + product.avoidFor,
                    containerColor = WarmSurface,
                    titleColor = ErrorText,
                )
                DetailSectionCard(
                    title = "资料依据",
                    values = listOf(knowledge.overview),
                    bullet = false,
                )
            }
        },
        containerColor = SurfaceCream,
        shape = RoundedCornerShape(28.dp),
    )
}

@Composable
private fun DetailHeroCard(product: ProductCard, assetBaseUrl: String) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = SurfaceWhite),
        shape = RoundedCornerShape(22.dp),
        border = BorderStroke(1.dp, BorderGreen),
        elevation = CardDefaults.cardElevation(defaultElevation = 0.dp),
    ) {
        Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            ProductImage(
                product = product,
                assetBaseUrl = assetBaseUrl,
                modifier = Modifier
                    .fillMaxWidth()
                    .height(150.dp)
                    .clip(RoundedCornerShape(18.dp)),
                fallbackText = product.brand.take(1),
            )
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                Text(
                    text = "¥${product.price.toInt()}",
                    modifier = Modifier
                        .background(Ink, RoundedCornerShape(999.dp))
                        .padding(horizontal = 12.dp, vertical = 6.dp),
                    color = SurfaceWhite,
                    fontWeight = FontWeight.Bold,
                    style = MaterialTheme.typography.labelLarge,
                )
                InfoChip(product.category)
                InfoChip(product.subCategory, warm = true)
            }
        }
    }
}

@Composable
private fun ProductImage(product: ProductCard, assetBaseUrl: String, modifier: Modifier, fallbackText: String) {
    SubcomposeAsyncImage(
        model = product.imageUrl(assetBaseUrl),
        contentDescription = product.title,
        contentScale = ContentScale.Crop,
        modifier = modifier.background(AppGreenSoft),
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
        Text(text, fontWeight = FontWeight.Bold, color = AccentGreenDark)
    }
}

private fun ProductCard.imageUrl(assetBaseUrl: String): String {
    val encodedPath = imagePath
        .split("/")
        .joinToString("/") { segment -> Uri.encode(segment) }
    return "${assetBaseUrl.trimEnd('/')}/$encodedPath"
}

@Composable
private fun DetailSectionCard(
    title: String,
    values: List<String>,
    containerColor: Color = SurfaceWhite,
    titleColor: Color = AccentGreenDark,
    bodyColor: Color = MutedText,
    bullet: Boolean = true,
    numbered: Boolean = false,
) {
    val visibleValues = values.filter { it.isNotBlank() }
    if (visibleValues.isEmpty()) return

    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = containerColor),
        shape = RoundedCornerShape(20.dp),
        border = BorderStroke(1.dp, BorderGreen),
        elevation = CardDefaults.cardElevation(defaultElevation = 0.dp),
    ) {
        Column(modifier = Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(
                text = title,
                color = titleColor,
                fontWeight = FontWeight.Bold,
                style = MaterialTheme.typography.labelLarge,
            )
            visibleValues.forEachIndexed { index, value ->
                val prefix = when {
                    numbered -> "${index + 1}. "
                    bullet -> "• "
                    else -> ""
                }
                Text(
                    text = "$prefix$value",
                    color = bodyColor,
                    style = MaterialTheme.typography.bodySmall,
                )
            }
        }
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun DetailChipsCard(
    title: String,
    values: List<String>,
    containerColor: Color = SurfaceWhite,
) {
    val visibleValues = values.filter { it.isNotBlank() }
    if (visibleValues.isEmpty()) return

    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = containerColor),
        shape = RoundedCornerShape(20.dp),
        border = BorderStroke(1.dp, BorderGreen),
        elevation = CardDefaults.cardElevation(defaultElevation = 0.dp),
    ) {
        Column(modifier = Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Text(
                text = title,
                color = AccentGreenDark,
                fontWeight = FontWeight.Bold,
                style = MaterialTheme.typography.labelLarge,
            )
            FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                visibleValues.forEach { value ->
                    InfoChip(value, warm = containerColor == AppGreenSoft)
                }
            }
        }
    }
}

@Composable
private fun InfoChip(label: String, warm: Boolean = false) {
    Text(
        text = label,
        modifier = Modifier
            .background(if (warm) WarmSurface else AppGreenSoft, RoundedCornerShape(999.dp))
            .padding(horizontal = 10.dp, vertical = 5.dp),
        color = if (warm) AccentGreenDark else Ink,
        style = MaterialTheme.typography.labelSmall,
    )
}

private data class KnowledgeSections(
    val overview: String,
    val officialFaq: List<String>,
    val userReviews: List<String>,
)

private fun ProductCard.knowledgeSections(): KnowledgeSections {
    val overview = mutableListOf<String>()
    val officialFaq = mutableListOf<String>()
    val userReviews = mutableListOf<String>()

    description.lines()
        .map { it.trim() }
        .filter { it.isNotBlank() }
        .forEach { line ->
            when {
                line.startsWith("官方FAQ：") -> officialFaq += line.removePrefix("官方FAQ：").trim()
                line.startsWith("用户评价：") -> userReviews += line.removePrefix("用户评价：").trim()
                else -> overview += line
            }
        }

    return KnowledgeSections(
        overview = overview.joinToString("\n"),
        officialFaq = officialFaq,
        userReviews = userReviews,
    )
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
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .padding(12.dp),
        colors = CardDefaults.cardColors(containerColor = SurfaceCream),
        shape = RoundedCornerShape(24.dp),
        border = BorderStroke(1.dp, BorderGreen),
        elevation = CardDefaults.cardElevation(defaultElevation = 0.dp),
    ) {
        Column(
            modifier = Modifier.padding(12.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            if (statusText != null) {
                Text(
                    text = statusText,
                    modifier = Modifier
                        .fillMaxWidth()
                        .background(AppGreenSoft, RoundedCornerShape(14.dp))
                        .padding(horizontal = 12.dp, vertical = 8.dp),
                    color = AccentGreenDark,
                    style = MaterialTheme.typography.bodySmall,
                )
            }
            FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                DemoPrompts.forEach { (label, prompt) ->
                    Text(
                        text = label,
                        modifier = Modifier
                            .background(AppGreenSoft, RoundedCornerShape(999.dp))
                            .clickable(enabled = !isLoading) { onQuickPrompt(prompt) }
                            .padding(horizontal = 10.dp, vertical = 6.dp),
                        color = AccentGreenDark,
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
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedBorderColor = AccentGreenDark,
                        unfocusedBorderColor = BorderGreen,
                        focusedContainerColor = SurfaceWhite,
                        unfocusedContainerColor = SurfaceWhite,
                        cursorColor = Ink,
                    ),
                    shape = RoundedCornerShape(18.dp),
                )
                Button(
                    onClick = onSend,
                    enabled = !isLoading && value.isNotBlank(),
                    contentPadding = PaddingValues(horizontal = 0.dp),
                    colors = ButtonDefaults.buttonColors(
                        containerColor = Ink,
                        contentColor = SurfaceWhite,
                        disabledContainerColor = BorderGreen,
                        disabledContentColor = MutedText,
                    ),
                ) {
                    if (isLoading) {
                        CircularProgressIndicator(
                            modifier = Modifier.size(22.dp),
                            color = MutedText,
                            strokeWidth = 2.dp,
                        )
                    } else {
                        Icon(
                            imageVector = TablerSendIcon,
                            contentDescription = "发送",
                            modifier = Modifier.size(22.dp),
                        )
                    }
                }
            }
        }
    }
    Spacer(modifier = Modifier.height(4.dp))
}
