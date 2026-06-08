package com.saki.bytedance.ragshopping

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.media.MediaRecorder
import android.net.Uri
import android.os.Build
import android.os.Bundle
import androidx.activity.compose.BackHandler
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.slideInVertically
import androidx.compose.animation.slideOutVertically
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.MutableTransitionState
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Image
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
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
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.blur
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.StrokeJoin
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.graphics.vector.path
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.platform.LocalContext
import androidx.lifecycle.viewmodel.compose.viewModel
import coil.compose.SubcomposeAsyncImage
import coil.compose.SubcomposeAsyncImageContent
import kotlinx.coroutines.delay
import java.io.File
import kotlin.math.sqrt

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
private const val ScrollableVariantTabThreshold = 2
private const val LongVariantTabLabelLength = 8
private val ScrollableVariantTabMinWidth = 96.dp
private const val DetailSheetAnimationMillis = 200
private val DetailSheetMaxHeight = 0.92f
private val DetailBackdropBlurRadius = 3.dp
private val ProductTagChipMinWidth = 56.dp
private val DetailInfoChipMinWidth = 64.dp
private val MessageAssistantAvatarSize = 30.dp
private const val VoiceWaveformBarCount = 18
private const val VoiceWaveformSampleMillis = 80L
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
private val TablerXIcon: ImageVector = ImageVector.Builder(
    name = "TablerX",
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
        moveTo(18f, 6f)
        lineTo(6f, 18f)
        moveTo(6f, 6f)
        lineTo(18f, 18f)
    }
}.build()
private val TablerMicrophoneIcon: ImageVector = ImageVector.Builder(
    name = "TablerMicrophone",
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
        moveTo(12f, 3f)
        curveTo(10.3f, 3f, 9f, 4.3f, 9f, 6f)
        verticalLineTo(11f)
        curveTo(9f, 12.7f, 10.3f, 14f, 12f, 14f)
        curveTo(13.7f, 14f, 15f, 12.7f, 15f, 11f)
        verticalLineTo(6f)
        curveTo(15f, 4.3f, 13.7f, 3f, 12f, 3f)
        close()
        moveTo(5f, 10f)
        curveTo(5f, 13.9f, 8.1f, 17f, 12f, 17f)
        curveTo(15.9f, 17f, 19f, 13.9f, 19f, 10f)
        moveTo(12f, 17f)
        verticalLineTo(21f)
        moveTo(8f, 21f)
        horizontalLineTo(16f)
    }
}.build()

private val DemoPrompts = listOf(
    "油皮通勤防晒" to "我是油皮，想要200元以内通勤防晒",
    "学生平板" to "预算5000以内，适合学生做笔记和看网课的平板",
    "早八咖啡" to "早八想提神，想要便携咖啡，不要太甜",
    "慢跑鞋" to "日常慢跑鞋，想要缓震舒服",
    "T 恤对比" to "AIRism和DRY-EX两件T恤哪个更适合夏天通勤和运动？",
    "下午茶零食" to "办公室下午茶零食，预算100以内，最好独立小包装",
    "敏感修护" to "敏感肌，最近屏障不稳定，想找修护面霜，不要酒精味太重或者刺激感强的产品",
    "信息不足追问" to "我想买护肤品，你推荐什么？",
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
        Column(
            modifier = Modifier
                .fillMaxSize()
                .blur(if (selectedProduct != null) DetailBackdropBlurRadius else 0.dp),
        ) {
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
                    val isAssistantStreaming = state.isLoading &&
                        index == state.messages.lastIndex &&
                        message.role == Role.Assistant
                    MessageBubble(
                        message = message,
                        showFeedback = !state.isLoading && hasPriorUserMessage,
                        isThinking = isThinking,
                        isStreaming = isAssistantStreaming,
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
                isTranscribing = state.isTranscribing,
                statusText = state.statusText,
                asrStatusText = state.asrStatusText,
                onValueChange = viewModel::updateInput,
                onSend = viewModel::send,
                onQuickPrompt = viewModel::sendPrompt,
                onAudioRecorded = viewModel::transcribeAudio,
            )
        }
        selectedProduct?.let { product ->
            ProductDetailOverlay(product = product, assetBaseUrl = assetBaseUrl, onDismiss = { selectedProduct = null })
        }
    }
}

@Composable
private fun Header() {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .background(AppGreen)
            .padding(horizontal = 20.dp, vertical = 14.dp),
        verticalArrangement = Arrangement.spacedBy(6.dp),
    ) {
        Text(
            text = "RAG智能导购",
            color = Ink,
            fontWeight = FontWeight.Bold,
            style = MaterialTheme.typography.headlineSmall,
        )
        Text(
            text = "美妆、服饰、数码和食品生活都能问，预算、场景和避雷点可以直接说",
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
    isStreaming: Boolean,
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
    val cardContent: @Composable () -> Unit = {
        Column(modifier = Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            if (isThinking) {
                ThinkingIndicator()
            } else if (message.content.isNotBlank()) {
                if (message.role == Role.Assistant && message.products.isNotEmpty()) {
                    AssistantMessageContent(
                        content = message.content,
                        products = message.products,
                        isStreaming = isStreaming,
                        assetBaseUrl = assetBaseUrl,
                        onProductClick = onProductClick,
                    )
                } else {
                    if (message.role == Role.Assistant) {
                        MarkdownText(markdown = message.content, color = textColor)
                    } else {
                        Text(
                            text = message.content,
                            color = textColor,
                            style = MaterialTheme.typography.bodyMedium,
                        )
                    }
                }
            }
            if (message.role == Role.Assistant && message.content.isNotBlank() && showFeedback) {
                FeedbackControls(message = message, onFeedback = onFeedback)
            }
        }
    }

    Column(horizontalAlignment = alignment, modifier = Modifier.fillMaxWidth()) {
        if (message.role == Role.Assistant) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalAlignment = Alignment.Top,
            ) {
                GuideAssistantImage(
                    modifier = Modifier
                        .size(MessageAssistantAvatarSize)
                        .padding(top = 2.dp),
                    cornerRadius = 10.dp,
                )
                Card(
                    colors = CardDefaults.cardColors(containerColor = background),
                    shape = RoundedCornerShape(22.dp),
                    border = border,
                    elevation = CardDefaults.cardElevation(defaultElevation = 0.dp),
                    modifier = Modifier.weight(1f),
                ) {
                    cardContent()
                }
            }
        } else {
            Card(
                colors = CardDefaults.cardColors(containerColor = background),
                shape = RoundedCornerShape(22.dp),
                border = border,
                elevation = CardDefaults.cardElevation(defaultElevation = 0.dp),
                modifier = Modifier.fillMaxWidth(if (message.role == Role.User) 0.86f else 1f),
            ) {
                cardContent()
            }
        }
    }
}

@Composable
private fun GuideAssistantImage(
    modifier: Modifier = Modifier,
    cornerRadius: Dp,
) {
    Image(
        painter = painterResource(id = R.drawable.guide_assistant),
        contentDescription = "导购小助手",
        contentScale = ContentScale.Crop,
        modifier = modifier
            .clip(RoundedCornerShape(cornerRadius))
            .background(Ink),
    )
}

@Composable
private fun AssistantMessageContent(
    content: String,
    products: List<ProductCard>,
    isStreaming: Boolean,
    assetBaseUrl: String,
    onProductClick: (ProductCard) -> Unit,
) {
    val blocks = remember(content, products, isStreaming) {
        buildAssistantContentBlocks(content, products, isStreaming)
    }
    val pendingText = mutableListOf<String>()

    fun flushText() {
        if (pendingText.isNotEmpty()) {
            pendingText.clear()
        }
    }

    blocks.forEach { block ->
        if (block.text.isNotBlank()) {
            pendingText += block.text
        }
        if (block.products.isNotEmpty()) {
            if (pendingText.isNotEmpty()) {
                MarkdownText(markdown = pendingText.joinToString("\n"), color = Ink)
                flushText()
            }
            block.products.forEach { product ->
                ProductCardView(
                    product = product,
                    assetBaseUrl = assetBaseUrl,
                    onClick = { onProductClick(product) },
                )
            }
        }
    }
    if (pendingText.isNotEmpty()) {
        MarkdownText(markdown = pendingText.joinToString("\n"), color = Ink)
    }
}

@Composable
private fun MarkdownText(markdown: String, color: Color) {
    val blocks = remember(markdown) { parseMarkdownBlocks(markdown) }
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        blocks.forEach { block ->
            when (block) {
                is MarkdownBlock.Heading -> MarkdownHeading(block = block, color = color)
                is MarkdownBlock.ListItem -> MarkdownListItem(block = block, color = color)
                is MarkdownBlock.Paragraph -> MarkdownParagraph(block.text, color)
                is MarkdownBlock.Table -> MarkdownTable(block = block, color = color)
            }
        }
    }
}

@Composable
private fun MarkdownHeading(block: MarkdownBlock.Heading, color: Color) {
    val style = when (block.level) {
        1 -> MaterialTheme.typography.titleMedium
        2 -> MaterialTheme.typography.titleSmall
        else -> MaterialTheme.typography.bodyLarge
    }
    Text(
        text = parseInlineMarkdown(block.text),
        color = color,
        fontWeight = FontWeight.Bold,
        style = style,
    )
}

@Composable
private fun MarkdownParagraph(text: String, color: Color) {
    Text(
        text = parseInlineMarkdown(text),
        color = color,
        style = MaterialTheme.typography.bodyMedium,
    )
}

@Composable
private fun MarkdownListItem(block: MarkdownBlock.ListItem, color: Color) {
    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        Text(
            text = block.marker,
            color = AccentGreenDark,
            fontWeight = FontWeight.Bold,
            style = MaterialTheme.typography.bodyMedium,
        )
        Text(
            text = parseInlineMarkdown(block.text),
            color = color,
            modifier = Modifier.weight(1f),
            style = MaterialTheme.typography.bodyMedium,
        )
    }
}

@Composable
private fun MarkdownTable(block: MarkdownBlock.Table, color: Color) {
    val comparisonTable = remember(block) { block.toProductComparisonTableOrNull() }
    if (comparisonTable != null) {
        MarkdownComparisonTable(table = comparisonTable, color = color)
        return
    }

    val columnCount = maxOf(
        block.headers.size,
        block.rows.maxOfOrNull { it.size } ?: 0,
    )
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(14.dp))
            .background(SurfaceWhite)
            .horizontalScroll(rememberScrollState()),
    ) {
        MarkdownTableRow(
            cells = block.headers,
            columnCount = columnCount,
            isHeader = true,
            color = color,
        )
        block.rows.forEachIndexed { index, row ->
            MarkdownTableRow(
                cells = row,
                columnCount = columnCount,
                isHeader = false,
                color = color,
                rowIndex = index,
            )
        }
    }
}

@Composable
private fun MarkdownComparisonTable(table: ProductComparisonTable, color: Color) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(14.dp))
            .background(SurfaceWhite),
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .background(AppGreenSoft),
        ) {
            ComparisonTableCell(
                text = "对比项",
                color = AccentGreenDark,
                isStrong = true,
                modifier = Modifier.width(68.dp),
            )
            table.productNames.forEach { productName ->
                ComparisonTableCell(
                    text = productName,
                    color = AccentGreenDark,
                    isStrong = true,
                    modifier = Modifier.weight(1f),
                )
            }
        }
        table.dimensions.forEachIndexed { index, dimension ->
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .background(if (index % 2 == 0) SurfaceWhite else WarmSurface),
            ) {
                ComparisonTableCell(
                    text = dimension.label,
                    color = AccentGreenDark,
                    isStrong = true,
                    modifier = Modifier.width(68.dp),
                )
                dimension.values.forEach { value ->
                    ComparisonTableCell(
                        text = value,
                        color = color,
                        isStrong = false,
                        modifier = Modifier.weight(1f),
                    )
                }
            }
        }
    }
}

@Composable
private fun ComparisonTableCell(
    text: String,
    color: Color,
    isStrong: Boolean,
    modifier: Modifier = Modifier,
) {
    Box(
        modifier = modifier.padding(horizontal = 7.dp, vertical = 8.dp),
    ) {
        Text(
            text = parseInlineMarkdown(text),
            color = color,
            fontWeight = if (isStrong) FontWeight.Bold else FontWeight.Normal,
            style = MaterialTheme.typography.bodySmall,
        )
    }
}

@Composable
private fun MarkdownTableRow(
    cells: List<String>,
    columnCount: Int,
    isHeader: Boolean,
    color: Color,
    rowIndex: Int = 0,
) {
    Row {
        repeat(columnCount) { index ->
            val cellText = cells.getOrNull(index).orEmpty()
            Box(
                modifier = Modifier
                    .width(124.dp)
                    .background(
                        when {
                            isHeader -> AppGreenSoft
                            rowIndex % 2 == 0 -> SurfaceWhite
                            else -> WarmSurface
                        }
                    )
                    .padding(horizontal = 8.dp, vertical = 7.dp),
            ) {
                Text(
                    text = parseInlineMarkdown(cellText),
                    color = if (isHeader) AccentGreenDark else color,
                    fontWeight = if (isHeader) FontWeight.Bold else FontWeight.Normal,
                    style = MaterialTheme.typography.bodySmall,
                )
            }
        }
    }
}

private data class AssistantContentBlock(
    val text: String,
    val products: List<ProductCard> = emptyList(),
)

private sealed class MarkdownBlock {
    data class Heading(val level: Int, val text: String) : MarkdownBlock()
    data class Paragraph(val text: String) : MarkdownBlock()
    data class ListItem(val marker: String, val text: String) : MarkdownBlock()
    data class Table(val headers: List<String>, val rows: List<List<String>>) : MarkdownBlock()
}

private data class ProductComparisonTable(
    val productNames: List<String>,
    val dimensions: List<ProductComparisonDimension>,
)

private data class ProductComparisonDimension(
    val label: String,
    val values: List<String>,
)

private val MarkdownHeadingRegex = Regex("""^\s*(#{1,6})\s+(.+)$""")
private val MarkdownOrderedListRegex = Regex("""^\s*(\d+)[.)]\s+(.+)$""")
private val MarkdownUnorderedListRegex = Regex("""^\s*[-*•]\s+(.+)$""")
private val MarkdownBoldRegex = Regex("""(\*\*[^*]+\*\*|__[^_]+__)""")
private val InternalProductIdInParenthesesRegex = Regex("""\s*[\(（]\s*`?(?:p|s)_[A-Za-z0-9_]+`?\s*[\)）]""")
private val StandaloneInternalProductIdRegex = Regex("""\s+`?(?:p|s)_[A-Za-z0-9_]+`?""")

private fun parseMarkdownBlocks(markdown: String): List<MarkdownBlock> {
    val lines = markdown
        .replace("\r\n", "\n")
        .replace("\r", "\n")
        .split("\n")
    val blocks = mutableListOf<MarkdownBlock>()
    var index = 0

    while (index < lines.size) {
        val line = lines[index].trim()
        if (line.isBlank()) {
            index += 1
            continue
        }

        if (index + 1 < lines.size && isMarkdownTableRow(line) && isMarkdownTableSeparator(lines[index + 1])) {
            val headers = parseMarkdownTableRow(line)
            val rows = mutableListOf<List<String>>()
            index += 2
            while (index < lines.size && isMarkdownTableRow(lines[index])) {
                rows += parseMarkdownTableRow(lines[index])
                index += 1
            }
            blocks += MarkdownBlock.Table(headers = headers, rows = rows)
            continue
        }

        val headingMatch = MarkdownHeadingRegex.matchEntire(line)
        if (headingMatch != null) {
            blocks += MarkdownBlock.Heading(
                level = headingMatch.groupValues[1].length,
                text = headingMatch.groupValues[2].trim(),
            )
            index += 1
            continue
        }

        val orderedListMatch = MarkdownOrderedListRegex.matchEntire(line)
        if (orderedListMatch != null) {
            blocks += MarkdownBlock.ListItem(
                marker = "${orderedListMatch.groupValues[1]}.",
                text = orderedListMatch.groupValues[2].trim(),
            )
            index += 1
            continue
        }

        val unorderedListMatch = MarkdownUnorderedListRegex.matchEntire(line)
        if (unorderedListMatch != null) {
            blocks += MarkdownBlock.ListItem(marker = "•", text = unorderedListMatch.groupValues[1].trim())
            index += 1
            continue
        }

        val paragraphLines = mutableListOf(line)
        index += 1
        while (index < lines.size && shouldMergeIntoParagraph(lines[index])) {
            paragraphLines += lines[index].trim()
            index += 1
        }
        blocks += MarkdownBlock.Paragraph(paragraphLines.joinToString("\n"))
    }

    return blocks
}

private fun MarkdownBlock.Table.toProductComparisonTableOrNull(): ProductComparisonTable? {
    if (headers.size < 3) return null
    val productHeader = headers.firstOrNull()?.trim().orEmpty()
    if (isProductComparisonHeader(productHeader)) {
        if (rows.size !in 2..3) return null

        val productNames = rows
            .map { row -> cleanComparisonProductName(row.firstOrNull()?.trim().orEmpty()) }
            .filter { it.isNotBlank() }
        if (productNames.size != rows.size) return null

        val dimensions = headers.drop(1).mapIndexedNotNull { dimensionIndex, header ->
            val label = header.trim()
            if (label.isBlank()) return@mapIndexedNotNull null
            ProductComparisonDimension(
                label = label,
                values = rows.map { row ->
                    row.getOrNull(dimensionIndex + 1)
                        ?.trim()
                        ?.takeIf { it.isNotBlank() }
                        ?: "资料未明确"
                },
            )
        }
        if (dimensions.isEmpty()) return null

        return ProductComparisonTable(productNames = productNames, dimensions = dimensions)
    }

    if (!isDimensionComparisonHeader(productHeader)) return null
    val productNames = headers.drop(1).map { cleanComparisonProductName(it.trim()) }
    if (productNames.size !in 2..3 || productNames.any { it.isBlank() }) return null

    val dimensions = rows.mapNotNull { row ->
        val label = row.firstOrNull()?.trim().orEmpty()
        if (label.isBlank()) return@mapNotNull null
        ProductComparisonDimension(
            label = label,
            values = productNames.mapIndexed { productIndex, _ ->
                row.getOrNull(productIndex + 1)
                    ?.trim()
                    ?.takeIf { it.isNotBlank() }
                    ?: "资料未明确"
            },
        )
    }
    if (dimensions.isEmpty()) return null

    return ProductComparisonTable(productNames = productNames, dimensions = dimensions)
}

private fun isProductComparisonHeader(header: String): Boolean {
    return listOf("商品", "产品", "款式", "SKU", "sku").any { token -> header.contains(token) }
}

private fun isDimensionComparisonHeader(header: String): Boolean {
    return listOf("对比项", "维度", "比较项", "项目").any { token -> header.contains(token) }
}

private fun cleanComparisonProductName(name: String): String {
    val cleaned = name
        .replace(InternalProductIdInParenthesesRegex, "")
        .replace(StandaloneInternalProductIdRegex, "")
        .trim()
        .trim('｜', '|', '-', '—', ':', '：')
        .trim()
    return cleaned.ifBlank { name }
}

private fun shouldMergeIntoParagraph(line: String): Boolean {
    val trimmed = line.trim()
    if (trimmed.isBlank()) return false
    if (MarkdownHeadingRegex.matches(trimmed)) return false
    if (MarkdownOrderedListRegex.matches(trimmed)) return false
    if (MarkdownUnorderedListRegex.matches(trimmed)) return false
    if (isMarkdownTableRow(trimmed)) return false
    return true
}

private fun parseInlineMarkdown(text: String): AnnotatedString {
    return buildAnnotatedString {
        var cursor = 0
        MarkdownBoldRegex.findAll(text).forEach { match ->
            append(text.substring(cursor, match.range.first))
            val boldText = match.value.substring(2, match.value.length - 2)
            pushStyle(SpanStyle(fontWeight = FontWeight.Bold))
            append(boldText)
            pop()
            cursor = match.range.last + 1
        }
        append(text.substring(cursor))
    }
}

private fun isMarkdownTableRow(line: String): Boolean {
    val trimmed = line.trim()
    return trimmed.contains("|") && parseMarkdownTableRow(trimmed).size >= 2
}

private fun isMarkdownTableSeparator(line: String): Boolean {
    val cells = parseMarkdownTableRow(line)
    if (cells.size < 2) return false
    return cells.all { it.matches(Regex(""":?-{3,}:?""")) }
}

private fun parseMarkdownTableRow(line: String): List<String> {
    return line
        .trim()
        .trim('|')
        .split("|")
        .map { it.trim() }
}

private data class AssistantTextBlock(
    val text: String,
    val isComplete: Boolean,
)

private data class ProductTextAnchor(
    val blockIndex: Int,
    val offset: Int,
)

private data class ProductPlacement(
    val product: ProductCard,
    val anchor: ProductTextAnchor?,
    val originalIndex: Int,
)

private val InlineRecommendationMarkerRegex =
    Regex("""(?:^|[\s，,；;。:：])(?:[1-9][.、)]|第[一二三四五六七八九123456789](?:个|款|件)?[：:、.])""")
private val RecommendationBlockStartRegex =
    Regex("""^\s*(?:[1-9][.、)]|第[一二三四五六七八九123456789](?:个|款|件)?[：:、.]?)""")

private fun buildAssistantContentBlocks(
    content: String,
    products: List<ProductCard>,
    isStreaming: Boolean,
): List<AssistantContentBlock> {
    val textBlocks = splitAssistantText(content, isStreaming)
    if (products.isEmpty()) {
        return textBlocks.map { AssistantContentBlock(text = it.text) }
    }
    if (containsMarkdownTable(content)) {
        return listOf(
            AssistantContentBlock(
                text = content.trim(),
                products = if (isStreaming) emptyList() else products,
            )
        )
    }

    val occupiedWeakMatchBlocks = mutableSetOf<Int>()
    val placements = products.mapIndexed { index, product ->
        val anchor = findProductTextAnchor(
            product = product,
            textBlocks = textBlocks,
            occupiedWeakMatchBlocks = occupiedWeakMatchBlocks,
        )
        anchor?.let { occupiedWeakMatchBlocks += it.blockIndex }
        ProductPlacement(
            product = product,
            anchor = anchor,
            originalIndex = index,
        )
    }
    val productsByBlock = mutableMapOf<Int, MutableList<ProductCard>>()
    val assignedProductIndexes = mutableSetOf<Int>()
    placements
        .filter { it.anchor != null }
        .sortedWith(
            compareBy<ProductPlacement>(
                { it.anchor?.blockIndex ?: Int.MAX_VALUE },
                { it.anchor?.offset ?: Int.MAX_VALUE },
                { it.originalIndex },
            )
        )
        .forEach { placement ->
            val blockIndex = placement.anchor?.blockIndex ?: return@forEach
            if (productsByBlock.appendProduct(blockIndex, placement.product)) {
                assignedProductIndexes += placement.originalIndex
            }
        }

    val recommendationBlockIndexes = completedRecommendationBlockIndexes(textBlocks)
    placements
        .filter { it.anchor == null }
        .sortedBy { it.originalIndex }
        .forEach { placement ->
            val blockIndex = recommendationBlockIndexes.firstOrNull { productsByBlock[it].isNullOrEmpty() }
            if (blockIndex != null && productsByBlock.appendProduct(blockIndex, placement.product)) {
                assignedProductIndexes += placement.originalIndex
            }
        }

    val fallbackProducts = if (isStreaming) {
        emptyList()
    } else {
        placements
            .filter { it.originalIndex !in assignedProductIndexes }
            .sortedBy { it.originalIndex }
            .map { it.product }
    }

    val blocks = textBlocks.mapIndexed { index, block ->
        AssistantContentBlock(text = block.text, products = productsByBlock[index].orEmpty())
    }.toMutableList()

    if (fallbackProducts.isNotEmpty()) {
        blocks += AssistantContentBlock(text = "", products = fallbackProducts)
    }

    return blocks
}

private fun completedRecommendationBlockIndexes(textBlocks: List<AssistantTextBlock>): List<Int> {
    return textBlocks.mapIndexedNotNull { index, block ->
        index.takeIf { block.isComplete && RecommendationBlockStartRegex.containsMatchIn(block.text) }
    }
}

private fun MutableMap<Int, MutableList<ProductCard>>.appendProduct(
    blockIndex: Int,
    product: ProductCard,
): Boolean {
    val blockProducts = getOrPut(blockIndex) { mutableListOf() }
    if (blockProducts.any { it.productId == product.productId }) return false
    blockProducts += product
    return true
}

private fun splitAssistantText(content: String, isStreaming: Boolean): List<AssistantTextBlock> {
    val normalizedContent = content
        .replace("\r\n", "\n")
        .replace("\r", "\n")
    val endsWithLineBreak = normalizedContent.endsWith("\n")
    val rawLines = normalizedContent.split("\n")

    return buildList {
        rawLines.forEachIndexed { lineIndex, rawLine ->
            val line = rawLine.trim()
            if (line.isBlank()) return@forEachIndexed

            val lineIsComplete = !isStreaming ||
                lineIndex < rawLines.lastIndex ||
                endsWithLineBreak
            val segments = splitInlineRecommendationBlocks(line)
            segments.forEachIndexed { segmentIndex, segment ->
                add(
                    AssistantTextBlock(
                        text = segment,
                        isComplete = lineIsComplete || segmentIndex < segments.lastIndex,
                    )
                )
            }
        }
    }
}

private fun containsMarkdownTable(content: String): Boolean {
    val lines = content
        .replace("\r\n", "\n")
        .replace("\r", "\n")
        .split("\n")
        .map { it.trim() }
    return lines.windowed(size = 2).any { (current, next) ->
        isMarkdownTableRow(current) && isMarkdownTableSeparator(next)
    }
}

private fun splitInlineRecommendationBlocks(line: String): List<String> {
    val markerIndexes = InlineRecommendationMarkerRegex
        .findAll(line)
        .map { match -> if (match.range.first == 0) 0 else match.range.first + 1 }
        .distinct()
        .toList()

    if (markerIndexes.size <= 1) {
        return listOf(line)
    }

    return buildList {
        var start = 0
        markerIndexes.forEach { markerIndex ->
            if (markerIndex > start) {
                add(line.substring(start, markerIndex).trim())
            }
            start = markerIndex
        }
        if (start < line.length) {
            add(line.substring(start).trim())
        }
    }.filter { it.isNotBlank() }
}

private fun findProductTextAnchor(
    product: ProductCard,
    textBlocks: List<AssistantTextBlock>,
    occupiedWeakMatchBlocks: Set<Int>,
): ProductTextAnchor? {
    if (textBlocks.isEmpty()) return null

    val strongTokens = product.strongMatchTokens()
    findTokenAnchor(strongTokens, textBlocks, excludedBlockIndexes = emptySet())?.let { return it }

    val weakTokens = product.weakMatchTokens()
    return findTokenAnchor(weakTokens, textBlocks, excludedBlockIndexes = occupiedWeakMatchBlocks)
}

private fun findTokenAnchor(
    tokens: List<String>,
    textBlocks: List<AssistantTextBlock>,
    excludedBlockIndexes: Set<Int>,
): ProductTextAnchor? {
    if (tokens.isEmpty()) return null

    textBlocks.forEachIndexed { blockIndex, textBlock ->
        if (!textBlock.isComplete) return@forEachIndexed
        if (blockIndex in excludedBlockIndexes) return@forEachIndexed
        val block = textBlock.text.normalizedForProductMatch()
        val offset = tokens
            .mapNotNull { token ->
                block.indexOf(token).takeIf { it >= 0 }
            }
            .minOrNull()
        if (offset != null) {
            return ProductTextAnchor(blockIndex = blockIndex, offset = offset)
        }
    }
    return null
}

private fun ProductCard.strongMatchTokens(): List<String> {
    val normalizedTitle = title.normalizedForProductMatch()
    val normalizedBrand = brand.normalizedForProductMatch()
    val normalizedSubCategory = subCategory.normalizedForProductMatch()
    val tokens = mutableListOf<String>()

    if (normalizedTitle.length >= 6) {
        tokens += normalizedTitle
        tokens += normalizedTitle.take(12)
    }
    if (normalizedBrand.length >= 2 && normalizedSubCategory.length >= 2) {
        tokens += normalizedBrand + normalizedSubCategory
    }
    tokens += variants.map { it.label.normalizedForProductMatch() }

    return tokens
        .map { it.trim() }
        .filter { it.length >= 4 }
        .distinct()
}

private fun ProductCard.weakMatchTokens(): List<String> {
    return listOf(brand, title.take(8)) + variants.map { it.label.take(6) }
        .map { it.normalizedForProductMatch() }
        .filter { it.length >= 2 }
        .distinct()
}

private fun String.normalizedForProductMatch(): String {
    return lowercase().filter { it.isLetterOrDigit() }
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
private fun LoadingStatusCard(statusText: String) {
    val statusUi = remember(statusText) { statusText.toWorkStatusUi() }
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .background(statusUi.containerColor, RoundedCornerShape(16.dp))
            .padding(horizontal = 10.dp, vertical = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(9.dp),
    ) {
        GuideAssistantImage(
            modifier = Modifier.size(28.dp),
            cornerRadius = 9.dp,
        )
        Column(
            modifier = Modifier.weight(1f),
            verticalArrangement = Arrangement.spacedBy(5.dp),
        ) {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(6.dp),
            ) {
                Text(
                    text = statusUi.title,
                    color = AccentGreenDark,
                    fontWeight = FontWeight.Bold,
                    style = MaterialTheme.typography.labelMedium,
                )
                LoadingDots(color = statusUi.accentColor)
            }
            Text(
                text = statusUi.subtitle,
                color = MutedText,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
                style = MaterialTheme.typography.labelSmall,
            )
        }
    }
}

@Composable
private fun VoiceStatusCard(
    text: String,
    isError: Boolean,
    waveformLevels: List<Float> = emptyList(),
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .background(if (isError) ErrorSurface else AppGreenSoft, RoundedCornerShape(16.dp))
            .padding(horizontal = 10.dp, vertical = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(9.dp),
    ) {
        Icon(
            imageVector = TablerMicrophoneIcon,
            contentDescription = null,
            tint = if (isError) ErrorText else AccentGreenDark,
            modifier = Modifier.size(18.dp),
        )
        Text(
            text = text,
            color = if (isError) ErrorText else MutedText,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
            style = MaterialTheme.typography.labelMedium,
            modifier = Modifier.weight(1f),
        )
        if (waveformLevels.isNotEmpty()) {
            VoiceWaveform(
                levels = waveformLevels,
                color = if (isError) ErrorText else AccentGreenDark,
            )
        }
    }
}

@Composable
private fun VoiceWaveform(levels: List<Float>, color: Color) {
    Row(
        modifier = Modifier.width(82.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(2.dp),
    ) {
        levels.takeLast(VoiceWaveformBarCount).forEach { level ->
            val barHeight = (4 + 18 * level.coerceIn(0f, 1f)).dp
            Box(
                modifier = Modifier
                    .width(3.dp)
                    .height(barHeight)
                    .clip(RoundedCornerShape(999.dp))
                    .background(color.copy(alpha = 0.28f + 0.72f * level.coerceIn(0f, 1f))),
            )
        }
    }
}

@Composable
private fun LoadingDots(color: Color) {
    val transition = rememberInfiniteTransition(label = "loading-dots")
    val phase by transition.animateFloat(
        initialValue = 0f,
        targetValue = 1f,
        animationSpec = infiniteRepeatable(
            animation = tween(durationMillis = 900, easing = LinearEasing),
        ),
        label = "loading-dots-phase",
    )
    val activeIndex = ((phase * 3).toInt()).coerceIn(0, 2)

    Row(horizontalArrangement = Arrangement.spacedBy(3.dp), verticalAlignment = Alignment.CenterVertically) {
        repeat(3) { index ->
            val active = index == activeIndex
            Box(
                modifier = Modifier
                    .size(if (active) 6.dp else 5.dp)
                    .clip(RoundedCornerShape(999.dp))
                    .background(color.copy(alpha = if (active) 1f else 0.32f)),
            )
        }
    }
}

@Composable
private fun VoiceRecordButton(
    isRecording: Boolean,
    isTranscribing: Boolean,
    enabled: Boolean,
    onClick: () -> Unit,
) {
    val buttonEnabled = enabled && !isTranscribing
    Box(
        modifier = Modifier
            .size(46.dp)
            .clip(RoundedCornerShape(18.dp))
            .background(
                when {
                    isRecording -> ErrorSurface
                    buttonEnabled -> AppGreenSoft
                    else -> BorderGreen
                }
            )
            .clickable(enabled = buttonEnabled) { onClick() },
        contentAlignment = Alignment.Center,
    ) {
        if (isTranscribing) {
            CircularProgressIndicator(
                modifier = Modifier.size(20.dp),
                color = MutedText,
                strokeWidth = 2.dp,
            )
        } else {
            Icon(
                imageVector = TablerMicrophoneIcon,
                contentDescription = if (isRecording) "停止录音" else "开始录音",
                tint = if (isRecording) ErrorText else AccentGreenDark,
                modifier = Modifier.size(21.dp),
            )
        }
    }
}

private data class WorkStatusUi(
    val title: String,
    val subtitle: String,
    val containerColor: Color,
    val accentColor: Color,
)

private fun String.toWorkStatusUi(): WorkStatusUi {
    return when {
        contains("检索") -> WorkStatusUi(
            title = "逛商品库中",
            subtitle = "正在捞候选、看预算和避雷点",
            containerColor = AppGreenSoft,
            accentColor = AccentGreenDark,
        )
        contains("生成") -> WorkStatusUi(
            title = "整理推荐中",
            subtitle = "正在把匹配点、对比和风险说清楚",
            containerColor = WarmSurface,
            accentColor = AccentGreen,
        )
        else -> WorkStatusUi(
            title = this,
            subtitle = "小助手正在处理这一步",
            containerColor = AppGreenSoft,
            accentColor = AccentGreenDark,
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
    if (product.variants.isNotEmpty()) {
        VariantStackProductCardView(product = product, assetBaseUrl = assetBaseUrl, onClick = onClick)
    } else {
        StandardProductCardView(product = product, assetBaseUrl = assetBaseUrl, onClick = onClick)
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun VariantStackProductCardView(product: ProductCard, assetBaseUrl: String, onClick: () -> Unit) {
    val variants = product.variants
    var selectedVariantId by remember(product.productId, variants) { mutableStateOf(variants.first().variantId) }
    val selectedVariant = variants.firstOrNull { it.variantId == selectedVariantId } ?: variants.first()
    val useScrollableVariantTabs = variants.shouldUseScrollableVariantTabs()
    val variantTabScrollState = rememberScrollState()

    Box(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(24.dp))
            .background(Ink, RoundedCornerShape(24.dp))
            .padding(4.dp),
    ) {
        Column(modifier = Modifier.fillMaxWidth()) {
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .clip(RoundedCornerShape(topStart = 20.dp, topEnd = 20.dp)),
            ) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .then(
                            if (useScrollableVariantTabs) {
                                Modifier.horizontalScroll(variantTabScrollState)
                            } else {
                                Modifier
                            },
                        ),
                    horizontalArrangement = Arrangement.spacedBy(4.dp),
                    verticalAlignment = Alignment.Bottom,
                ) {
                    variants.forEach { variant ->
                        VariantCardTab(
                            variant = variant,
                            selected = variant.variantId == selectedVariant.variantId,
                            modifier = if (useScrollableVariantTabs) {
                                Modifier.widthIn(min = ScrollableVariantTabMinWidth)
                            } else {
                                Modifier.weight(1f)
                            },
                            onClick = { selectedVariantId = variant.variantId },
                        )
                    }
                }
            }
            Card(
                colors = CardDefaults.cardColors(containerColor = SurfaceWhite),
                shape = RoundedCornerShape(topStart = 0.dp, topEnd = 0.dp, bottomEnd = 20.dp, bottomStart = 20.dp),
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
                            ProductImageFromPath(
                                imagePath = selectedVariant.imagePath.ifBlank { product.imagePath },
                                contentDescription = "${product.title} ${selectedVariant.label}",
                                assetBaseUrl = assetBaseUrl,
                                modifier = Modifier.fillMaxSize(),
                                fallbackText = product.brand.take(1),
                            )
                        }
                        Column(modifier = Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(3.dp)) {
                            Text(
                                text = "${product.brand} · 同系列规格",
                                color = AccentGreenDark,
                                fontWeight = FontWeight.Bold,
                                style = MaterialTheme.typography.labelLarge,
                            )
                            Text(
                                text = selectedVariant.label.ifBlank { product.title },
                                color = Ink,
                                maxLines = 2,
                                style = MaterialTheme.typography.bodySmall,
                            )
                        }
                        Column(horizontalAlignment = Alignment.End, verticalArrangement = Arrangement.spacedBy(4.dp)) {
                            Text(
                                text = "¥${selectedVariant.price.toInt()}",
                                modifier = Modifier
                                    .background(Ink, RoundedCornerShape(999.dp))
                                    .padding(horizontal = 10.dp, vertical = 6.dp),
                                color = SurfaceWhite,
                                fontWeight = FontWeight.Bold,
                                style = MaterialTheme.typography.labelMedium,
                            )
                            Text(
                                text = "详情 >",
                                color = AccentGreenDark,
                                fontWeight = FontWeight.Bold,
                                style = MaterialTheme.typography.labelSmall,
                            )
                        }
                    }
                    FlowRow(
                        horizontalArrangement = Arrangement.spacedBy(6.dp),
                        verticalArrangement = Arrangement.spacedBy(6.dp),
                        maxItemsInEachRow = 4,
                    ) {
                        (listOf("同系列规格") + product.tags).take(6).forEach { tag ->
                            ProductTagChip(tag)
                        }
                    }
                    Text(
                        text = selectedVariant.reason.ifBlank { product.reason },
                        color = MutedText,
                        style = MaterialTheme.typography.bodySmall,
                    )
                }
            }
        }
    }
}

private fun List<ProductVariantCard>.shouldUseScrollableVariantTabs(): Boolean {
    return size > ScrollableVariantTabThreshold ||
        any { variant -> variant.label.trim().length >= LongVariantTabLabelLength }
}

@Composable
private fun ProductTagChip(label: String) {
    Text(
        text = label,
        modifier = Modifier
            .widthIn(min = ProductTagChipMinWidth)
            .background(WarmSurface, RoundedCornerShape(999.dp))
            .padding(horizontal = 8.dp, vertical = 3.dp),
        color = AccentGreenDark,
        maxLines = 1,
        softWrap = false,
        style = MaterialTheme.typography.labelSmall,
    )
}

@Composable
private fun VariantCardTab(
    variant: ProductVariantCard,
    selected: Boolean,
    modifier: Modifier = Modifier,
    onClick: () -> Unit,
) {
    Card(
        colors = CardDefaults.cardColors(containerColor = if (selected) SurfaceWhite else AppGreenSoft),
        shape = if (selected) {
            RoundedCornerShape(topStart = 18.dp, topEnd = 18.dp, bottomEnd = 0.dp, bottomStart = 0.dp)
        } else {
            RoundedCornerShape(topStart = 16.dp, topEnd = 16.dp, bottomEnd = 0.dp, bottomStart = 0.dp)
        },
        elevation = CardDefaults.cardElevation(defaultElevation = 0.dp),
        modifier = modifier
            .height(if (selected) 42.dp else 36.dp)
            .clickable(onClick = onClick),
    ) {
        Column(
            modifier = Modifier
                .fillMaxHeight()
                .padding(horizontal = 10.dp, vertical = 5.dp),
            verticalArrangement = Arrangement.Center,
        ) {
            Text(
                text = variant.label.ifBlank { "默认规格" },
                color = if (selected) Ink else AccentGreenDark,
                fontWeight = if (selected) FontWeight.Bold else FontWeight.Normal,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
                style = MaterialTheme.typography.labelSmall,
            )
            if (selected) {
                Text(
                    text = "¥${variant.price.toInt()}",
                    color = AccentGreenDark,
                    fontWeight = FontWeight.Bold,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                    style = MaterialTheme.typography.labelSmall,
                )
            }
        }
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun StandardProductCardView(product: ProductCard, assetBaseUrl: String, onClick: () -> Unit) {
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
            FlowRow(
                horizontalArrangement = Arrangement.spacedBy(6.dp),
                verticalArrangement = Arrangement.spacedBy(6.dp),
                maxItemsInEachRow = 4,
            ) {
                product.tags.forEach { tag ->
                    ProductTagChip(tag)
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
private fun ProductDetailOverlay(product: ProductCard, assetBaseUrl: String, onDismiss: () -> Unit) {
    val visibilityState = remember(product.productId) {
        MutableTransitionState(false).apply {
            targetState = true
        }
    }

    fun requestDismiss() {
        visibilityState.targetState = false
    }

    LaunchedEffect(visibilityState.isIdle, visibilityState.currentState, visibilityState.targetState) {
        if (visibilityState.isIdle && !visibilityState.currentState && !visibilityState.targetState) {
            onDismiss()
        }
    }

    BackHandler(enabled = visibilityState.currentState || visibilityState.targetState) {
        requestDismiss()
    }

    Box(modifier = Modifier.fillMaxSize()) {
        AnimatedVisibility(
            visibleState = visibilityState,
            enter = fadeIn(animationSpec = tween(DetailSheetAnimationMillis)),
            exit = fadeOut(animationSpec = tween(DetailSheetAnimationMillis)),
        ) {
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .background(Color(0x99000000))
                    .clickable(
                        indication = null,
                        interactionSource = remember { MutableInteractionSource() },
                        onClick = { requestDismiss() },
                    ),
            )
        }
        AnimatedVisibility(
            visibleState = visibilityState,
            modifier = Modifier.align(Alignment.BottomCenter),
            enter = slideInVertically(
                initialOffsetY = { fullHeight -> fullHeight },
                animationSpec = tween(DetailSheetAnimationMillis),
            ) + fadeIn(animationSpec = tween(DetailSheetAnimationMillis)),
            exit = slideOutVertically(
                targetOffsetY = { fullHeight -> fullHeight },
                animationSpec = tween(DetailSheetAnimationMillis),
            ) + fadeOut(animationSpec = tween(DetailSheetAnimationMillis)),
        ) {
            ProductDetailSheet(
                product = product,
                assetBaseUrl = assetBaseUrl,
                onDismiss = { requestDismiss() },
            )
        }
    }
}

@Composable
private fun ProductDetailSheet(
    product: ProductCard,
    assetBaseUrl: String,
    onDismiss: () -> Unit,
) {
    val knowledge = remember(product.description) { product.knowledgeSections() }
    val variants = product.variants
    var selectedVariantId by remember(product.productId, variants) { mutableStateOf(variants.firstOrNull()?.variantId.orEmpty()) }
    val selectedVariant = variants.firstOrNull { it.variantId == selectedVariantId } ?: variants.firstOrNull()

    Card(
        modifier = Modifier
            .fillMaxWidth()
            .fillMaxHeight(DetailSheetMaxHeight)
            .padding(start = 10.dp, top = 28.dp, end = 10.dp, bottom = 8.dp)
            .navigationBarsPadding()
            .clickable(
                indication = null,
                interactionSource = remember { MutableInteractionSource() },
                onClick = {},
            ),
        colors = CardDefaults.cardColors(containerColor = SurfaceCream),
        shape = RoundedCornerShape(28.dp),
        elevation = CardDefaults.cardElevation(defaultElevation = 0.dp),
    ) {
        Column(modifier = Modifier.fillMaxSize()) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(start = 24.dp, top = 20.dp, end = 16.dp, bottom = 8.dp),
                horizontalArrangement = Arrangement.spacedBy(12.dp),
                verticalAlignment = Alignment.Top,
            ) {
                Column(
                    modifier = Modifier.weight(1f),
                    verticalArrangement = Arrangement.spacedBy(6.dp),
                ) {
                    Text(
                        text = product.brand,
                        color = AccentGreenDark,
                        fontWeight = FontWeight.Bold,
                        style = MaterialTheme.typography.labelLarge,
                    )
                    Text(
                        text = selectedVariant?.label?.takeIf { it.isNotBlank() } ?: product.title,
                        color = Ink,
                        style = MaterialTheme.typography.titleMedium,
                    )
                }
                Box(
                    modifier = Modifier
                        .size(32.dp)
                        .background(AppGreenSoft, RoundedCornerShape(999.dp))
                        .clickable(onClick = onDismiss),
                    contentAlignment = Alignment.Center,
                ) {
                    Icon(
                        imageVector = TablerXIcon,
                        contentDescription = "关闭",
                        tint = Ink,
                        modifier = Modifier.size(18.dp),
                    )
                }
            }
            Column(
                modifier = Modifier
                    .weight(1f)
                    .verticalScroll(rememberScrollState())
                    .padding(horizontal = 24.dp, vertical = 8.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                DetailHeroCard(product = product, selectedVariant = selectedVariant, assetBaseUrl = assetBaseUrl)
                if (variants.isNotEmpty()) {
                    VariantSelectorCard(
                        variants = variants,
                        selectedVariant = selectedVariant,
                        onSelect = { selectedVariantId = it.variantId },
                    )
                }
                DetailSectionCard(
                    title = "推荐理由",
                    values = listOf(selectedVariant?.reason ?: product.reason),
                    containerColor = Ink,
                    titleColor = AppGreen,
                    bodyColor = SurfaceWhite,
                    bullet = false,
                )
                if (selectedVariant != null) {
                    DetailSectionCard(
                        title = "规格信息",
                        values = selectedVariant.detailLines(),
                        containerColor = SurfaceWhite,
                        titleColor = AccentGreenDark,
                        bullet = false,
                    )
                }
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
                Spacer(modifier = Modifier.height(12.dp))
            }
        }
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun DetailHeroCard(product: ProductCard, selectedVariant: ProductVariantCard?, assetBaseUrl: String) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = SurfaceWhite),
        shape = RoundedCornerShape(22.dp),
        border = BorderStroke(1.dp, BorderGreen),
        elevation = CardDefaults.cardElevation(defaultElevation = 0.dp),
    ) {
        Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            ProductImageFromPath(
                imagePath = selectedVariant?.imagePath?.ifBlank { product.imagePath } ?: product.imagePath,
                contentDescription = selectedVariant?.label?.takeIf { it.isNotBlank() } ?: product.title,
                assetBaseUrl = assetBaseUrl,
                modifier = Modifier
                    .fillMaxWidth()
                    .height(150.dp)
                    .clip(RoundedCornerShape(18.dp)),
                fallbackText = product.brand.take(1),
            )
            FlowRow(
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp),
                maxItemsInEachRow = 3,
            ) {
                Text(
                    text = "¥${(selectedVariant?.price ?: product.price).toInt()}",
                    modifier = Modifier
                        .background(Ink, RoundedCornerShape(999.dp))
                        .padding(horizontal = 12.dp, vertical = 6.dp),
                    color = SurfaceWhite,
                    fontWeight = FontWeight.Bold,
                    style = MaterialTheme.typography.labelLarge,
                )
                InfoChip(product.category)
                InfoChip(product.subCategory, warm = true)
                selectedVariant?.label?.takeIf { it.isNotBlank() }?.let {
                    InfoChip(it)
                }
            }
        }
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun VariantSelectorCard(
    variants: List<ProductVariantCard>,
    selectedVariant: ProductVariantCard?,
    onSelect: (ProductVariantCard) -> Unit,
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = AppGreenSoft),
        shape = RoundedCornerShape(20.dp),
        border = BorderStroke(1.dp, BorderGreen),
        elevation = CardDefaults.cardElevation(defaultElevation = 0.dp),
    ) {
        Column(modifier = Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Text(
                text = "同系列规格",
                color = AccentGreenDark,
                fontWeight = FontWeight.Bold,
                style = MaterialTheme.typography.labelLarge,
            )
            FlowRow(
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp),
                maxItemsInEachRow = 2,
            ) {
                variants.forEach { variant ->
                    val selected = variant.variantId == selectedVariant?.variantId
                    Text(
                        text = variant.label.ifBlank { "默认规格" },
                        modifier = Modifier
                            .widthIn(min = DetailInfoChipMinWidth)
                            .background(if (selected) Ink else SurfaceWhite, RoundedCornerShape(999.dp))
                            .clickable { onSelect(variant) }
                            .padding(horizontal = 10.dp, vertical = 6.dp),
                        color = if (selected) SurfaceWhite else AccentGreenDark,
                        fontWeight = if (selected) FontWeight.Bold else FontWeight.Normal,
                        maxLines = 1,
                        softWrap = false,
                        style = MaterialTheme.typography.labelMedium,
                    )
                }
            }
        }
    }
}

@Composable
private fun ProductImage(product: ProductCard, assetBaseUrl: String, modifier: Modifier, fallbackText: String) {
    ProductImageFromPath(
        imagePath = product.imagePath,
        contentDescription = product.title,
        assetBaseUrl = assetBaseUrl,
        modifier = modifier,
        fallbackText = fallbackText,
    )
}

@Composable
private fun ProductImageFromPath(
    imagePath: String,
    contentDescription: String,
    assetBaseUrl: String,
    modifier: Modifier,
    fallbackText: String,
) {
    SubcomposeAsyncImage(
        model = imageUrl(assetBaseUrl, imagePath),
        contentDescription = contentDescription,
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
    return imageUrl(assetBaseUrl, imagePath)
}

private fun ProductVariantCard.detailLines(): List<String> {
    val propertyLines = properties.map { (name, value) -> "$name：$value" }
    return listOf("价格：¥${price.toInt()}") + propertyLines
}

private fun imageUrl(assetBaseUrl: String, imagePath: String): String {
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
            FlowRow(
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp),
                maxItemsInEachRow = 3,
            ) {
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
            .widthIn(min = DetailInfoChipMinWidth)
            .background(if (warm) WarmSurface else AppGreenSoft, RoundedCornerShape(999.dp))
            .padding(horizontal = 10.dp, vertical = 5.dp),
        color = if (warm) AccentGreenDark else Ink,
        maxLines = 1,
        softWrap = false,
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
    isTranscribing: Boolean,
    statusText: String?,
    asrStatusText: String?,
    onValueChange: (String) -> Unit,
    onSend: () -> Unit,
    onQuickPrompt: (String) -> Unit,
    onAudioRecorded: (File) -> Unit,
) {
    val context = LocalContext.current
    var recordingSession by remember { mutableStateOf<VoiceRecordingSession?>(null) }
    var voiceError by remember { mutableStateOf<String?>(null) }
    var waveformLevels by remember {
        mutableStateOf(List(VoiceWaveformBarCount) { 0.03f })
    }

    fun startRecording() {
        if (isLoading || isTranscribing || recordingSession != null) return
        voiceError = null
        runCatching {
            startVoiceRecording(context)
        }.onSuccess { session ->
            waveformLevels = List(VoiceWaveformBarCount) { 0.03f }
            recordingSession = session
        }.onFailure { error ->
            voiceError = "录音启动失败：${error.localizedMessage ?: "请检查麦克风权限"}"
        }
    }

    fun stopRecording() {
        val session = recordingSession ?: return
        recordingSession = null
        runCatching {
            session.stop()
        }.onSuccess { audioFile ->
            voiceError = null
            onAudioRecorded(audioFile)
        }.onFailure { error ->
            session.file.delete()
            voiceError = "录音失败：${error.localizedMessage ?: "录音时间太短，请重新试一次"}"
        }
    }

    val permissionLauncher = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        if (granted) {
            startRecording()
        } else {
            voiceError = "需要麦克风权限才能语音输入"
        }
    }

    fun toggleRecording() {
        if (recordingSession != null) {
            stopRecording()
            return
        }
        if (hasRecordAudioPermission(context)) {
            startRecording()
        } else {
            permissionLauncher.launch(Manifest.permission.RECORD_AUDIO)
        }
    }

    DisposableEffect(Unit) {
        onDispose {
            recordingSession?.discard()
        }
    }

    LaunchedEffect(recordingSession) {
        val session = recordingSession ?: return@LaunchedEffect
        while (recordingSession === session) {
            waveformLevels = (waveformLevels + session.amplitudeLevel()).takeLast(VoiceWaveformBarCount)
            delay(VoiceWaveformSampleMillis)
        }
    }

    val voiceStatusText = when {
        recordingSession != null -> "正在录音，再点一次停止"
        isTranscribing -> "正在本地转写..."
        voiceError != null -> voiceError
        asrStatusText != null -> asrStatusText
        else -> null
    }
    val isVoiceStatusError = voiceError != null || asrStatusText?.startsWith("转写失败") == true

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
                LoadingStatusCard(statusText = statusText)
            }
            if (voiceStatusText != null) {
                VoiceStatusCard(
                    text = voiceStatusText,
                    isError = isVoiceStatusError,
                    waveformLevels = if (recordingSession != null) waveformLevels else emptyList(),
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
                VoiceRecordButton(
                    isRecording = recordingSession != null,
                    isTranscribing = isTranscribing,
                    enabled = !isLoading,
                    onClick = ::toggleRecording,
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

private class VoiceRecordingSession(
    private val recorder: MediaRecorder,
    val file: File,
) {
    private var released = false

    fun stop(): File {
        try {
            recorder.stop()
            return file
        } finally {
            release()
        }
    }

    fun discard() {
        if (!released) {
            runCatching { recorder.stop() }
            release()
        }
        file.delete()
    }

    fun amplitudeLevel(): Float {
        if (released) return 0f
        val amplitude = runCatching { recorder.maxAmplitude }.getOrDefault(0)
        if (amplitude <= 0) return 0.03f
        return sqrt(amplitude / 32767f).coerceIn(0.03f, 1f)
    }

    private fun release() {
        if (released) return
        runCatching { recorder.reset() }
        recorder.release()
        released = true
    }
}

private fun startVoiceRecording(context: Context): VoiceRecordingSession {
    val outputFile = File.createTempFile("voice_query_", ".m4a", context.cacheDir)
    val recorder = createMediaRecorder(context)
    recorder.setAudioSource(MediaRecorder.AudioSource.MIC)
    recorder.setOutputFormat(MediaRecorder.OutputFormat.MPEG_4)
    recorder.setAudioEncoder(MediaRecorder.AudioEncoder.AAC)
    recorder.setAudioSamplingRate(16000)
    recorder.setAudioEncodingBitRate(64000)
    recorder.setOutputFile(outputFile.absolutePath)
    recorder.prepare()
    recorder.start()
    return VoiceRecordingSession(recorder = recorder, file = outputFile)
}

private fun createMediaRecorder(context: Context): MediaRecorder {
    return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
        MediaRecorder(context)
    } else {
        @Suppress("DEPRECATION")
        MediaRecorder()
    }
}

private fun hasRecordAudioPermission(context: Context): Boolean {
    return context.checkSelfPermission(Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED
}
