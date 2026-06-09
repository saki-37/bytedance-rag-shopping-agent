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
import android.graphics.Bitmap
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
import androidx.compose.foundation.gestures.detectVerticalDragGestures
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.IntrinsicSize
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
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
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
import androidx.compose.ui.graphics.asImageBitmap
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
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.DpOffset
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.PopupProperties
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
private const val InputStatusAutoDismissMillis = 5_000L
private val RecipientMenuOffsetX = (-56).dp
private val RecipientMenuOffsetY = 8.dp
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
private val TablerPlusIcon: ImageVector = ImageVector.Builder(
    name = "TablerPlus",
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
        moveTo(12f, 5f)
        verticalLineTo(19f)
        moveTo(5f, 12f)
        horizontalLineTo(19f)
    }
}.build()
private val TablerAlertTriangleIcon: ImageVector = ImageVector.Builder(
    name = "TablerAlertTriangle",
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
        moveTo(12f, 4f)
        lineTo(20f, 20f)
        lineTo(4f, 20f)
        close()
        moveTo(12f, 9f)
        lineTo(12f, 13f)
        moveTo(12f, 16f)
        lineTo(12f, 16.01f)
    }
}.build()
private val TablerChevronDownIcon: ImageVector = ImageVector.Builder(
    name = "TablerChevronDown",
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
        moveTo(6f, 9f)
        lineTo(12f, 15f)
        lineTo(18f, 9f)
    }
}.build()
private val TablerArrowUpIcon: ImageVector = ImageVector.Builder(
    name = "TablerArrowUp",
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
        moveTo(12f, 19f)
        verticalLineTo(5f)
        moveTo(5f, 12f)
        lineTo(12f, 5f)
        lineTo(19f, 12f)
    }
}.build()
private val TablerCameraIcon: ImageVector = ImageVector.Builder(
    name = "TablerCamera",
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
        moveTo(5f, 7f)
        horizontalLineTo(8f)
        lineTo(10f, 5f)
        horizontalLineTo(14f)
        lineTo(16f, 7f)
        horizontalLineTo(19f)
        curveTo(20.1f, 7f, 21f, 7.9f, 21f, 9f)
        verticalLineTo(18f)
        curveTo(21f, 19.1f, 20.1f, 20f, 19f, 20f)
        horizontalLineTo(5f)
        curveTo(3.9f, 20f, 3f, 19.1f, 3f, 18f)
        verticalLineTo(9f)
        curveTo(3f, 7.9f, 3.9f, 7f, 5f, 7f)
        close()
        moveTo(12f, 11f)
        curveTo(10.3f, 11f, 9f, 12.3f, 9f, 14f)
        curveTo(9f, 15.7f, 10.3f, 17f, 12f, 17f)
        curveTo(13.7f, 17f, 15f, 15.7f, 15f, 14f)
        curveTo(15f, 12.3f, 13.7f, 11f, 12f, 11f)
        close()
    }
}.build()
private val TablerPhotoIcon: ImageVector = ImageVector.Builder(
    name = "TablerPhoto",
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
        moveTo(5f, 5f)
        horizontalLineTo(19f)
        curveTo(20.1f, 5f, 21f, 5.9f, 21f, 7f)
        verticalLineTo(19f)
        curveTo(21f, 20.1f, 20.1f, 21f, 19f, 21f)
        horizontalLineTo(5f)
        curveTo(3.9f, 21f, 3f, 20.1f, 3f, 19f)
        verticalLineTo(7f)
        curveTo(3f, 5.9f, 3.9f, 5f, 5f, 5f)
        close()
        moveTo(8f, 10f)
        curveTo(8.6f, 10f, 9f, 9.6f, 9f, 9f)
        curveTo(9f, 8.4f, 8.6f, 8f, 8f, 8f)
        curveTo(7.4f, 8f, 7f, 8.4f, 7f, 9f)
        curveTo(7f, 9.6f, 7.4f, 10f, 8f, 10f)
        close()
        moveTo(21f, 16f)
        lineTo(16f, 12f)
        lineTo(5f, 21f)
    }
}.build()
private val TablerStopIcon: ImageVector = ImageVector.Builder(
    name = "TablerStop",
    defaultWidth = 24.dp,
    defaultHeight = 24.dp,
    viewportWidth = 24f,
    viewportHeight = 24f,
).apply {
    path(fill = SolidColor(Color.Black)) {
        moveTo(8f, 7f)
        horizontalLineTo(16f)
        curveTo(16.6f, 7f, 17f, 7.4f, 17f, 8f)
        verticalLineTo(16f)
        curveTo(17f, 16.6f, 16.6f, 17f, 16f, 17f)
        horizontalLineTo(8f)
        curveTo(7.4f, 17f, 7f, 16.6f, 7f, 16f)
        verticalLineTo(8f)
        curveTo(7f, 7.4f, 7.4f, 7f, 8f, 7f)
        close()
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
private val TablerVolumeIcon: ImageVector = ImageVector.Builder(
    name = "TablerVolume",
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
        moveTo(4f, 10f)
        horizontalLineTo(8f)
        lineTo(13f, 5f)
        verticalLineTo(19f)
        lineTo(8f, 14f)
        horizontalLineTo(4f)
        close()
        moveTo(16f, 9f)
        curveTo(17.2f, 10.2f, 17.2f, 13.8f, 16f, 15f)
        moveTo(18.5f, 6.5f)
        curveTo(21.5f, 9.5f, 21.5f, 14.5f, 18.5f, 17.5f)
    }
}.build()
private val TablerVolumeOffIcon: ImageVector = ImageVector.Builder(
    name = "TablerVolumeOff",
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
        moveTo(4f, 10f)
        horizontalLineTo(8f)
        lineTo(13f, 5f)
        verticalLineTo(19f)
        lineTo(8f, 14f)
        horizontalLineTo(4f)
        close()
        moveTo(18f, 9f)
        lineTo(22f, 13f)
        moveTo(22f, 9f)
        lineTo(18f, 13f)
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
    val context = LocalContext.current
    val state by viewModel.state.collectAsState()
    val listState = rememberLazyListState()
    var selectedProduct by remember { mutableStateOf<ProductCard?>(null) }
    var showTtsSettings by remember { mutableStateOf(false) }
    var showRecipientManager by remember { mutableStateOf(false) }
    var ttsSettings by remember(context) { mutableStateOf(TtsSettingsStore.load(context)) }
    var autoSpokenMessageIds by remember { mutableStateOf(emptySet<String>()) }
    var stoppedSpeechMessageIds by remember { mutableStateOf(emptySet<String>()) }
    var speechHintText by remember { mutableStateOf<String?>(null) }
    var isLastSpeechStateSpeaking by remember { mutableStateOf(false) }
    var wasManuallyStopped by remember { mutableStateOf(false) }
    val ttsSpeaker = remember(context) { TtsSpeaker(context) }
    val ttsPlaybackState by ttsSpeaker.state.collectAsState()
    val speakingMessageId = (ttsPlaybackState as? TtsPlaybackState.Speaking)?.messageId
    val speechEnabled = ttsSettings.ttsEnabled
    val latestMessage = state.messages.lastOrNull()
    val latestSpeakableAssistant = state.messages.lastOrNull {
        it.role == Role.Assistant && it.content.isNotBlank()
    }
    val assetBaseUrl = "${state.backendBaseUrl.trimEnd('/')}/assets"
    val density = androidx.compose.ui.platform.LocalDensity.current
    val contentFontScale = when (ttsSettings.fontScaleMode) {
        FontScaleMode11x -> 1.1f
        FontScaleMode125x -> 1.25f
        FontScaleMode15x -> 1.5f
        else -> 1f
    }
    val adjustedDensity = androidx.compose.ui.unit.Density(
        density = density.density,
        fontScale = density.fontScale * contentFontScale,
    )
    val asrStatusDisplayText = if (ttsSettings.speechHintVisibility) {
        when (val source = state.asrStatusText) {
            null -> null
            "正在本地转写..." -> if (ttsSettings.ttsStatusAnnouncementEnabled) "转写中，请稍候" else "转写中"
            "已转写，可修改后发送" -> if (ttsSettings.ttsStatusAnnouncementEnabled) "转写完成，可修改后发送" else "已转写"
            else -> if (ttsSettings.ttsStatusAnnouncementEnabled) source else source.trim()
        }
    } else {
        null
    }

    val selectedRecipientName = state.recipients.firstOrNull { it.recipientId == state.selectedRecipientId }?.displayName
        .cleanEditorValue()
        ?.ifBlank { "对象" }
        ?: "对象"
    var openRecipientManagerAfterSettingsClose by remember { mutableStateOf(false) }

    LaunchedEffect(showRecipientManager) {
        if (showRecipientManager) {
            viewModel.loadRecipients()
        }
    }

    fun updateTtsSettings(nextSettings: TtsSettings) {
        ttsSettings = nextSettings
        TtsSettingsStore.save(context, nextSettings)
        if (!nextSettings.ttsEnabled) {
            ttsSpeaker.stop()
            speechHintText = if (nextSettings.ttsStatusAnnouncementEnabled) {
                "语音播报已关闭"
            } else {
                "播报关闭"
            }
        } else {
            speechHintText = null
        }
    }

    fun speakMessage(message: ChatMessage) {
        if (message.role != Role.Assistant || message.content.isBlank()) return
        stoppedSpeechMessageIds = stoppedSpeechMessageIds - message.id
        autoSpokenMessageIds = autoSpokenMessageIds + message.id
        wasManuallyStopped = false
        speechHintText = if (ttsSettings.ttsStatusAnnouncementEnabled) {
            "正在播放 AI 回复"
        } else {
            "播放中"
        }
        ttsSpeaker.speak(
            messageId = message.id,
            rawText = message.content,
            verboseMode = ttsSettings.ttsVerboseMode,
            speechRate = ttsSettings.ttsSpeechRate,
        )
    }

    fun toggleMessageSpeech(message: ChatMessage) {
        if (speakingMessageId == message.id) {
            stoppedSpeechMessageIds = stoppedSpeechMessageIds + message.id
            wasManuallyStopped = true
            ttsSpeaker.stop()
        } else {
            speakMessage(message)
        }
    }

    fun stopAnySpeech() {
        wasManuallyStopped = true
        ttsSpeaker.stop()
    }

    DisposableEffect(ttsSpeaker) {
        onDispose {
            ttsSpeaker.shutdown()
        }
    }

    LaunchedEffect(
        ttsPlaybackState,
        ttsSettings.ttsStatusAnnouncementEnabled,
        ttsSettings.speechHintVisibility,
    ) {
        if (!ttsSettings.speechHintVisibility) {
            speechHintText = if (!speechEnabled) {
                if (ttsSettings.ttsStatusAnnouncementEnabled) "语音播报已关闭" else "播报关闭"
            } else {
                null
            }
            isLastSpeechStateSpeaking = false
            return@LaunchedEffect
        }

        when (val state = ttsPlaybackState) {
            is TtsPlaybackState.Speaking -> {
                isLastSpeechStateSpeaking = true
                speechHintText = if (ttsSettings.ttsStatusAnnouncementEnabled) {
                    "正在播放语音反馈"
                } else {
                    "播放中"
                }
            }
            is TtsPlaybackState.Idle -> {
                if (isLastSpeechStateSpeaking) {
                    speechHintText = if (wasManuallyStopped) {
                        wasManuallyStopped = false
                        if (ttsSettings.ttsStatusAnnouncementEnabled) "播放已停止" else "已停止"
                    } else {
                        if (ttsSettings.ttsStatusAnnouncementEnabled) "播放完成" else "已结束"
                    }
                }
                isLastSpeechStateSpeaking = false
            }
            is TtsPlaybackState.Error -> {
                isLastSpeechStateSpeaking = false
                speechHintText = if (ttsSettings.ttsStatusAnnouncementEnabled) {
                    "播放失败：${state.message}"
                } else {
                    "播放失败"
                }
            }
            is TtsPlaybackState.Initializing -> {
                speechHintText = if (ttsSettings.ttsStatusAnnouncementEnabled) "语音服务初始化中" else "语音服务中"
            }
        }
    }

    LaunchedEffect(
        latestSpeakableAssistant?.id,
        state.isLoading,
        ttsSettings.ttsEnabled,
    ) {
        val assistantMessage = latestSpeakableAssistant ?: return@LaunchedEffect
        if (
            !state.isLoading &&
            speechEnabled &&
            assistantMessage.id !in autoSpokenMessageIds &&
            assistantMessage.id !in stoppedSpeechMessageIds
        ) {
            speakMessage(assistantMessage)
        }
    }

    LaunchedEffect(state.messages.size, latestMessage?.content?.length, latestMessage?.products?.size) {
        listState.scrollToItem(state.messages.size)
    }

    androidx.compose.runtime.CompositionLocalProvider(
        androidx.compose.ui.platform.LocalDensity provides adjustedDensity,
    ) {
        Surface(color = AppGreen, modifier = Modifier.fillMaxSize()) {
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .blur(if (selectedProduct != null) DetailBackdropBlurRadius else 0.dp),
            ) {
                Header(
                    ttsSettings = ttsSettings,
                    onTtsSettingsClick = { showTtsSettings = true },
                )
                Box(
                    modifier = Modifier
                        .weight(1f)
                        .fillMaxWidth(),
                ) {
                    LazyColumn(
                        state = listState,
                        modifier = Modifier.fillMaxSize(),
                        contentPadding = PaddingValues(
                            start = 16.dp,
                            top = 16.dp,
                            end = 16.dp,
                            bottom = 190.dp,
                        ),
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
                                showFeedback = !state.isLoading && hasPriorUserMessage && !message.isEphemeral,
                                isThinking = isThinking,
                                isStreaming = isAssistantStreaming,
                                isSpeaking = message.id == speakingMessageId,
                                assetBaseUrl = assetBaseUrl,
                                onProductClick = { selectedProduct = it },
                                onFeedback = viewModel::submitFeedback,
                                onSpeechToggle = ::toggleMessageSpeech,
                            )
                        }
                        item("bottom-anchor") {
                            Spacer(modifier = Modifier.height(1.dp))
                        }
                    }
                    InputBar(
                        modifier = Modifier
                            .align(Alignment.BottomCenter)
                            .fillMaxWidth(),
                        value = state.input,
                        isLoading = state.isLoading,
                        isTranscribing = state.isTranscribing,
                        recipients = state.recipients,
                        selectedRecipientId = state.selectedRecipientId,
                        currentRecipientName = selectedRecipientName,
                        statusText = state.statusText,
                        asrStatusText = asrStatusDisplayText,
                        speechStatusText = speechHintText,
                        speechStatusIsError = speechHintText?.contains("失败") == true,
                        recipientsLoading = state.recipientsLoading,
                        recipientsSaving = state.recipientsSaving,
                        recipientError = state.recipientError,
                        onValueChange = viewModel::updateInput,
                        onSend = { overrideMessage, pendingImage ->
                            stopAnySpeech()
                            if (pendingImage != null) {
                                viewModel.sendWithImage(
                                    message = overrideMessage ?: state.input,
                                    localImageFile = pendingImage.uploadFile,
                                    localPreviewUri = pendingImage.localUri,
                                    source = pendingImage.source,
                                )
                            } else if (overrideMessage != null) {
                                viewModel.sendPrompt(overrideMessage)
                            } else {
                                viewModel.send()
                            }
                        },
                        onQuickPrompt = { prompt ->
                            stopAnySpeech()
                            viewModel.sendPrompt(prompt)
                        },
                        onAudioRecorded = viewModel::transcribeAudio,
                        onRecipientSelected = viewModel::selectRecipient,
                        onOpenRecipientManagement = { showRecipientManager = true },
                    )
                }
            }
            selectedProduct?.let { product ->
                ProductDetailOverlay(product = product, assetBaseUrl = assetBaseUrl, onDismiss = { selectedProduct = null })
            }
            if (showTtsSettings) {
                TtsSettingsDialog(
                    settings = ttsSettings,
                    onSettingsChange = ::updateTtsSettings,
                    onDismiss = {
                        showTtsSettings = false
                        if (openRecipientManagerAfterSettingsClose) {
                            showRecipientManager = true
                            openRecipientManagerAfterSettingsClose = false
                        }
                    },
                    onRecipientManagerClick = {
                        openRecipientManagerAfterSettingsClose = true
                    },
                )
            }

            if (showRecipientManager) {
                RecipientManagementDialog(
                    recipients = state.recipients,
                    selectedRecipientId = state.selectedRecipientId,
                    isLoading = state.recipientsLoading,
                    isSaving = state.recipientsSaving,
                    error = state.recipientError,
                    onDismiss = { showRecipientManager = false },
                    onSave = { updatedRecipients, selectedId ->
                        viewModel.saveRecipients(updatedRecipients, selectedId)
                        showRecipientManager = false
                    },
                )
            }
        }
    }
}

@Composable
private fun Header(
    ttsSettings: TtsSettings,
    onTtsSettingsClick: () -> Unit,
) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .background(AppGreen)
            .padding(horizontal = 20.dp, vertical = 14.dp),
        verticalArrangement = Arrangement.spacedBy(6.dp),
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Text(
                text = "RAG智能导购",
                color = Ink,
                fontWeight = FontWeight.Bold,
                style = MaterialTheme.typography.headlineSmall,
                modifier = Modifier.weight(1f),
            )
            TextButton(onClick = onTtsSettingsClick) {
                Text(
                    text = "设置",
                    color = Ink,
                    fontWeight = FontWeight.Bold,
                    style = MaterialTheme.typography.labelLarge,
                )
            }
        }
        Text(
            text = "美妆、服饰、数码和食品生活都能问，预算、场景和避雷点可以直接说",
            color = AccentGreenDark,
            style = MaterialTheme.typography.bodyMedium,
        )
    }
}

@Composable
private fun TtsSettingsDialog(
    settings: TtsSettings,
    onSettingsChange: (TtsSettings) -> Unit,
    onDismiss: () -> Unit,
    onRecipientManagerClick: () -> Unit,
) {
    val speechRateOptions = listOf(0.75f, 1.0f, 1.25f, 1.5f)
    val fontScaleOptions = listOf(FontScaleModeSystem, FontScaleMode11x, FontScaleMode125x, FontScaleMode15x)

    ReusableBottomSheetOverlay(
        sheetKey = "tts-settings",
        maxHeightFraction = 0.90f,
        onDismiss = onDismiss,
    ) { requestDismiss ->
        ReusableBottomSheetCard(
            maxHeightFraction = 0.90f,
            onDismiss = requestDismiss,
        ) {
            BottomSheetHeader(
                title = "设置",
                subtitle = null,
                onDismiss = requestDismiss,
            )
            Column(
                modifier = Modifier
                    .weight(1f)
                    .verticalScroll(rememberScrollState())
                    .padding(horizontal = 24.dp, vertical = 8.dp),
                verticalArrangement = Arrangement.spacedBy(18.dp),
            ) {
                Text(
                    text = "语音与可访问性",
                    color = Ink,
                    fontWeight = FontWeight.Bold,
                    style = MaterialTheme.typography.bodyMedium,
                )
                SettingRow(
                    title = "语音播报",
                    description = if (settings.ttsEnabled) "开启后新回复自动播报" else "关闭后仍可手动朗读单条回复",
                    checked = settings.ttsEnabled,
                    onCheckedChange = { checked ->
                        onSettingsChange(settings.copy(ttsEnabled = checked))
                    },
                )
                SettingRow(
                    title = "详细播报（视障友好）",
                    description = "增加更多结构化提示",
                    checked = settings.ttsVerboseMode,
                    onCheckedChange = { checked ->
                        onSettingsChange(settings.copy(ttsVerboseMode = checked))
                    },
                )
                SettingRow(
                    title = "状态播报（听障文字化）",
                    description = "开启后显示转写与播放状态文字",
                    checked = settings.ttsStatusAnnouncementEnabled,
                    onCheckedChange = { checked ->
                        onSettingsChange(settings.copy(ttsStatusAnnouncementEnabled = checked))
                    },
                )
                Text(
                    text = "语音速度",
                    color = Ink,
                    fontWeight = FontWeight.Medium,
                    style = MaterialTheme.typography.bodyMedium,
                )
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    speechRateOptions.forEach { rate ->
                        val selected = kotlin.math.abs(settings.ttsSpeechRate - rate) < 0.001f
                        Text(
                            text = when (rate) {
                                0.75f -> "慢速"
                                1.0f -> "正常"
                                1.25f -> "偏快"
                                else -> "快速"
                            },
                            color = if (selected) SurfaceWhite else Ink,
                            textAlign = androidx.compose.ui.text.style.TextAlign.Center,
                            style = MaterialTheme.typography.labelLarge,
                            modifier = Modifier
                                .weight(1f)
                                .clip(RoundedCornerShape(20.dp))
                                .background(if (selected) AccentGreenDark else AppGreenSoft)
                                .clickable { onSettingsChange(settings.copy(ttsSpeechRate = rate)) }
                                .padding(vertical = 10.dp),
                        )
                    }
                }
                Spacer(
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(1.dp)
                        .background(BorderGreen.copy(alpha = 0.35f)),
                )
                Text(
                    text = "字号策略",
                    color = Ink,
                    fontWeight = FontWeight.Bold,
                    style = MaterialTheme.typography.bodyMedium,
                )
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    fontScaleOptions.forEach { fontScale ->
                        val selected = settings.fontScaleMode == fontScale
                        Text(
                            text = when (fontScale) {
                                FontScaleModeSystem -> "跟随系统"
                                FontScaleMode11x -> "1.1x"
                                FontScaleMode125x -> "1.25x"
                                else -> "1.5x"
                            },
                            color = if (selected) SurfaceWhite else Ink,
                            textAlign = androidx.compose.ui.text.style.TextAlign.Center,
                            style = MaterialTheme.typography.labelLarge,
                            modifier = Modifier
                                .weight(1f)
                                .clip(RoundedCornerShape(20.dp))
                                .background(if (selected) AccentGreenDark else AppGreenSoft)
                                .clickable {
                                    onSettingsChange(settings.copy(fontScaleMode = fontScale))
                                }
                                .padding(vertical = 10.dp),
                        )
                    }
                }
                SettingRow(
                    title = "语音状态说明",
                    description = "开启后显示关键状态文本提示",
                    checked = settings.speechHintVisibility,
                    onCheckedChange = { checked ->
                        onSettingsChange(settings.copy(speechHintVisibility = checked))
                    },
                )
                Text(
                    text = "示例：请说出你的问题后点发送。转写中…已转写：...。正在播放…已停止播放。",
                    color = MutedText,
                    style = MaterialTheme.typography.labelSmall,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                )
                TextButton(onClick = {
                    requestDismiss()
                    onRecipientManagerClick()
                }) {
                    Text(
                        text = "常用购买对象",
                        color = AccentGreenDark,
                        fontWeight = FontWeight.Bold,
                    )
                }
            }
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 24.dp, vertical = 14.dp),
                horizontalArrangement = Arrangement.End,
            ) {
                TextButton(onClick = requestDismiss) {
                    Text(text = "完成", color = AccentGreenDark, fontWeight = FontWeight.Bold)
                }
            }
        }
    }
}

@Composable
private fun SettingRow(
    title: String,
    description: String,
    checked: Boolean,
    onCheckedChange: (Boolean) -> Unit,
) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Column(modifier = Modifier.weight(1f)) {
            Text(
                text = title,
                color = Ink,
                fontWeight = FontWeight.Bold,
                style = MaterialTheme.typography.bodyMedium,
            )
            Text(
                text = description,
                color = MutedText,
                style = MaterialTheme.typography.labelSmall,
            )
        }
        Switch(
            checked = checked,
            onCheckedChange = onCheckedChange,
        )
    }
}

@Composable
private fun MessageBubble(
    message: ChatMessage,
    showFeedback: Boolean,
    isThinking: Boolean,
    isStreaming: Boolean,
    isSpeaking: Boolean,
    assetBaseUrl: String,
    onProductClick: (ProductCard) -> Unit,
    onFeedback: (String, FeedbackType) -> Unit,
    onSpeechToggle: (ChatMessage) -> Unit,
) {
    val alignment = if (message.role == Role.User) Alignment.End else Alignment.Start
    val background = when (message.role) {
        Role.User -> Ink
        Role.Assistant -> if (message.isQuickReply) AppGreenSoft else SurfaceCream
        Role.Status -> AppGreenSoft
        Role.Error -> ErrorSurface
    }
    val textColor = when (message.role) {
        Role.User -> SurfaceWhite
        Role.Error -> ErrorText
        Role.Assistant -> if (message.isQuickReply) MutedText else Ink
        else -> Ink
    }
    val border = if (message.role == Role.User) null else BorderStroke(1.dp, BorderGreen)
    val cardContent: @Composable () -> Unit = {
        val contentPadding = if (message.isQuickReply) 12.dp else 14.dp
        Column(modifier = Modifier.padding(contentPadding), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            when {
                message.role == Role.Assistant && message.isQuickReply -> {
                    Text(
                        text = message.content,
                        color = textColor,
                        style = MaterialTheme.typography.bodySmall,
                    )
                }

                message.role == Role.Assistant && message.products.isNotEmpty() -> {
                    AssistantMessageContent(
                        content = message.content,
                        products = message.products,
                        isStreaming = isStreaming,
                        assetBaseUrl = assetBaseUrl,
                        onProductClick = onProductClick,
                    )
                    if (isThinking) {
                        ThinkingIndicator()
                    }
                }

                message.role == Role.User && message.images.isNotEmpty() -> {
                    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        message.images.forEach { image ->
                            UserMessageImage(
                                image = image,
                                assetBaseUrl = assetBaseUrl,
                            )
                        }
                        if (message.content.isNotBlank()) {
                            Text(
                                text = message.content,
                                color = textColor,
                                style = MaterialTheme.typography.bodyMedium,
                            )
                        }
                    }
                }

                isThinking -> {
                    ThinkingIndicator()
                }

                message.content.isNotBlank() && message.role == Role.Assistant -> {
                    MarkdownText(markdown = message.content, color = textColor)
                }

                message.content.isNotBlank() -> {
                    Text(
                        text = message.content,
                        color = textColor,
                        style = MaterialTheme.typography.bodyMedium,
                    )
                }
            }
            if (message.role == Role.Assistant && message.content.isNotBlank() && showFeedback && !message.isQuickReply) {
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
                AssistantAvatarControl(
                    isSpeaking = isSpeaking,
                    enabled = message.content.isNotBlank(),
                    onClick = { onSpeechToggle(message) },
                    modifier = Modifier
                        .padding(top = 2.dp),
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
private fun UserMessageImage(
    image: ChatImage,
    assetBaseUrl: String,
) {
    val model = when {
        !image.localUri.isNullOrBlank() -> image.localUri
        !image.previewUrl.isNullOrBlank() -> "${assetBaseUrl.trimEnd('/')}${image.previewUrl}"
        else -> null
    }

    if (model == null) return

    SubcomposeAsyncImage(
        model = model,
        contentDescription = "用户上传图片",
        contentScale = ContentScale.Crop,
        modifier = Modifier
            .fillMaxWidth()
            .height(160.dp)
            .clip(RoundedCornerShape(16.dp))
            .background(SurfaceWhite.copy(alpha = 0.12f)),
        loading = { ProductImageFallback("图") },
        error = { ProductImageFallback("图") },
        success = { SubcomposeAsyncImageContent() },
    )
}

@Composable
private fun AssistantAvatarControl(
    isSpeaking: Boolean,
    enabled: Boolean,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val transition = rememberInfiniteTransition(label = "assistant-speaking")
    val phase by transition.animateFloat(
        initialValue = 0f,
        targetValue = 1f,
        animationSpec = infiniteRepeatable(
            animation = tween(durationMillis = 900, easing = LinearEasing),
        ),
        label = "assistant-speaking-phase",
    )
    val pulse = if (phase <= 0.5f) phase * 2f else (1f - phase) * 2f

    Box(
        modifier = modifier
            .size(38.dp)
            .clip(RoundedCornerShape(13.dp))
            .clickable(enabled = enabled, onClick = onClick),
        contentAlignment = Alignment.Center,
    ) {
        if (isSpeaking) {
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .clip(RoundedCornerShape(13.dp))
                    .background(AppGreenSoft.copy(alpha = 0.52f + 0.28f * pulse)),
            )
        }
        GuideAssistantImage(
            modifier = Modifier
                .size(MessageAssistantAvatarSize)
                .align(Alignment.Center),
            cornerRadius = 10.dp,
        )
        if (isSpeaking) {
            Row(
                modifier = Modifier
                    .align(Alignment.BottomCenter)
                    .padding(bottom = 2.dp),
                horizontalArrangement = Arrangement.spacedBy(2.dp),
                verticalAlignment = Alignment.Bottom,
            ) {
                repeat(3) { index ->
                    val barPhase = ((phase + index * 0.22f) % 1f)
                    val barPulse = if (barPhase <= 0.5f) barPhase * 2f else (1f - barPhase) * 2f
                    Box(
                        modifier = Modifier
                            .width(3.dp)
                            .height((4 + 6 * barPulse).dp)
                            .clip(RoundedCornerShape(999.dp))
                            .background(AccentGreenDark.copy(alpha = 0.45f)),
                    )
                }
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

private data class PendingInputImage(
    val preview: Any,
    val uploadFile: File,
    val localUri: String?,
    val source: ImageSource,
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
    if (textBlocks.isEmpty()) {
        return listOf(AssistantContentBlock(text = "", products = products))
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
private fun VoiceWaveform(
    levels: List<Float>,
    color: Color,
    modifier: Modifier = Modifier,
) {
    Row(
        modifier = modifier.width(82.dp),
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
            .size(40.dp)
            .clip(RoundedCornerShape(999.dp))
            .background(
                when {
                    isRecording -> ErrorSurface
                    isTranscribing -> AppGreenSoft
                    else -> Color.Transparent
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
                tint = when {
                    isRecording -> ErrorText
                    buttonEnabled -> MutedText
                    else -> MutedText.copy(alpha = 0.32f)
                },
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
                softWrap = true,
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
    ReusableBottomSheetOverlay(
        sheetKey = product.productId,
        onDismiss = onDismiss,
        sheetContent = { requestDismiss ->
            ProductDetailSheet(
                product = product,
                assetBaseUrl = assetBaseUrl,
                onDismiss = requestDismiss,
            )
        },
    )
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

    ReusableBottomSheetCard(
        maxHeightFraction = DetailSheetMaxHeight,
        onDismiss = onDismiss,
    ) {
        BottomSheetHeader(
            title = selectedVariant?.label?.takeIf { it.isNotBlank() } ?: product.title,
            subtitle = product.brand,
            onDismiss = onDismiss,
        )
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

@Composable
private fun ReusableBottomSheetOverlay(
    sheetKey: Any,
    maxHeightFraction: Float = DetailSheetMaxHeight,
    onDismiss: () -> Unit,
    sheetContent: @Composable (requestDismiss: () -> Unit) -> Unit,
) {
    val visibilityState = remember(sheetKey) {
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
            sheetContent(::requestDismiss)
        }
    }
}

@Composable
private fun ReusableBottomSheetCard(
    maxHeightFraction: Float,
    onDismiss: () -> Unit,
    modifier: Modifier = Modifier,
    content: @Composable ColumnScope.() -> Unit,
) {
    val density = LocalDensity.current
    val dismissThresholdPx = density.run { 80.dp.toPx() }
    var dragOffset by remember { mutableStateOf(0f) }

    Card(
        modifier = modifier
            .fillMaxWidth()
            .fillMaxHeight(maxHeightFraction)
            .padding(start = 10.dp, top = 28.dp, end = 10.dp, bottom = 8.dp)
            .navigationBarsPadding()
            .pointerInput(onDismiss) {
                detectVerticalDragGestures(
                    onVerticalDrag = { _, dragAmount ->
                        dragOffset = (dragOffset + dragAmount).coerceAtLeast(0f)
                        if (dragOffset > dismissThresholdPx) {
                            onDismiss()
                        }
                    },
                    onDragEnd = { dragOffset = 0f },
                    onDragCancel = { dragOffset = 0f },
                )
            }
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
            content()
        }
    }
}

@Composable
private fun BottomSheetHeader(
    title: String,
    subtitle: String?,
    onDismiss: () -> Unit,
) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(start = 24.dp, top = 12.dp, end = 16.dp, bottom = 8.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        Box(
            modifier = Modifier
                .width(42.dp)
                .height(4.dp)
                .clip(RoundedCornerShape(999.dp))
                .background(BorderGreen.copy(alpha = 0.8f))
                .align(Alignment.CenterHorizontally),
        )
        Row(
            horizontalArrangement = Arrangement.spacedBy(12.dp),
            verticalAlignment = Alignment.Top,
        ) {
            Column(modifier = Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                title.takeIf { it.isNotBlank() }?.let {
                    Text(
                        text = it,
                        color = Ink,
                        style = MaterialTheme.typography.titleMedium,
                    )
                }
                if (!subtitle.isNullOrBlank()) {
                    Text(
                        text = subtitle,
                        color = AccentGreenDark,
                        fontWeight = FontWeight.Bold,
                        style = MaterialTheme.typography.labelLarge,
                    )
                }
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
                        softWrap = true,
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
    modifier: Modifier = Modifier,
    value: String,
    isLoading: Boolean,
    isTranscribing: Boolean,
    recipients: List<RecipientProfile>,
    selectedRecipientId: String,
    currentRecipientName: String,
    statusText: String?,
    asrStatusText: String?,
    speechStatusText: String?,
    speechStatusIsError: Boolean,
    recipientsLoading: Boolean,
    recipientsSaving: Boolean,
    recipientError: String?,
    onValueChange: (String) -> Unit,
    onSend: (String?, PendingInputImage?) -> Unit,
    onQuickPrompt: (String) -> Unit,
    onAudioRecorded: (File) -> Unit,
    onRecipientSelected: (String) -> Unit,
    onOpenRecipientManagement: () -> Unit,
) {
    val context = LocalContext.current
    var recordingSession by remember { mutableStateOf<VoiceRecordingSession?>(null) }
    var voiceError by remember { mutableStateOf<String?>(null) }
    var showAttachmentMenu by remember { mutableStateOf(false) }
    var showRecipientMenu by remember { mutableStateOf(false) }
    var attachmentStatusText by remember { mutableStateOf<String?>(null) }
    var dismissedInputStatusKeys by remember { mutableStateOf(emptySet<String>()) }
    var pendingImage by remember { mutableStateOf<PendingInputImage?>(null) }
    var recordingElapsedSeconds by remember { mutableStateOf(0) }
    var waveformLevels by remember {
        mutableStateOf(List(VoiceWaveformBarCount) { 0.03f })
    }
    val galleryLauncher = rememberLauncherForActivityResult(ActivityResultContracts.GetContent()) { uri: Uri? ->
        showAttachmentMenu = false
        if (uri != null) {
            runCatching {
                val file = copyUriToCacheImage(context, uri)
                pendingImage?.uploadFile?.delete()
                pendingImage = PendingInputImage(
                    preview = uri,
                    uploadFile = file,
                    localUri = uri.toString(),
                    source = ImageSource.Gallery,
                )
                attachmentStatusText = "已选择图片"
            }.onFailure { error ->
                attachmentStatusText = "图片读取失败：${error.localizedMessage ?: "请重新选择"}"
            }
        } else {
            attachmentStatusText = "没有选择图片"
        }
    }
    val cameraLauncher = rememberLauncherForActivityResult(ActivityResultContracts.TakePicturePreview()) { bitmap: Bitmap? ->
        showAttachmentMenu = false
        if (bitmap != null) {
            runCatching {
                val file = writeBitmapToCacheImage(context, bitmap)
                pendingImage?.uploadFile?.delete()
                pendingImage = PendingInputImage(
                    preview = bitmap,
                    uploadFile = file,
                    localUri = null,
                    source = ImageSource.Camera,
                )
                attachmentStatusText = "已拍摄图片"
            }.onFailure { error ->
                attachmentStatusText = "拍照图片保存失败：${error.localizedMessage ?: "请重新拍摄"}"
            }
        } else {
            attachmentStatusText = "没有完成拍照"
        }
    }

    fun startRecording() {
        if (isLoading || isTranscribing || recordingSession != null) return
        showAttachmentMenu = false
        attachmentStatusText = null
        voiceError = null
        runCatching {
            startVoiceRecording(context)
        }.onSuccess { session ->
            waveformLevels = List(VoiceWaveformBarCount) { 0.03f }
            recordingElapsedSeconds = 0
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

    BackHandler(enabled = showAttachmentMenu || showRecipientMenu) {
        if (showAttachmentMenu) {
            showAttachmentMenu = false
        } else {
            showRecipientMenu = false
        }
    }

    DisposableEffect(Unit) {
        onDispose {
            recordingSession?.discard()
        }
    }

    LaunchedEffect(recordingSession) {
        val session = recordingSession ?: return@LaunchedEffect
        val startedAtMillis = System.currentTimeMillis()
        while (recordingSession === session) {
            waveformLevels = (waveformLevels + session.amplitudeLevel()).takeLast(VoiceWaveformBarCount)
            recordingElapsedSeconds = ((System.currentTimeMillis() - startedAtMillis) / 1000L).toInt()
            delay(VoiceWaveformSampleMillis)
        }
    }

    data class InputStatusLine(
        val key: String,
        val text: String,
        val isError: Boolean,
    )
    val currentVoiceError = voiceError
    val rawInputStatusLines = buildList {
        if (isTranscribing) {
            add(InputStatusLine("asr-transcribing", "正在本地转写...", false))
        }
        if (currentVoiceError != null) {
            add(InputStatusLine("voice-error:$currentVoiceError", currentVoiceError, true))
        } else {
            asrStatusText?.let { add(InputStatusLine("asr:$it", it, it.startsWith("转写失败"))) }
            speechStatusText?.let { add(InputStatusLine("speech:$it", it, speechStatusIsError)) }
            attachmentStatusText?.let { add(InputStatusLine("attachment:$it", it, false)) }
        }
    }
    LaunchedEffect(rawInputStatusLines.map { it.key }) {
        val activeKeys = rawInputStatusLines.map { it.key }.toSet()
        dismissedInputStatusKeys = dismissedInputStatusKeys.intersect(activeKeys)
    }
    val inputStatusLines = rawInputStatusLines.filter { it.key !in dismissedInputStatusKeys }
    val isRecording = recordingSession != null
    val canUseInputTools = !isLoading && !isTranscribing
    val hasPendingImage = pendingImage != null
    val canSendText = !isLoading && (value.isNotBlank() || hasPendingImage) && !isRecording

    Box(
        modifier = modifier
            .navigationBarsPadding()
            .padding(horizontal = 12.dp, vertical = 10.dp),
    ) {
        Column(
            modifier = Modifier.fillMaxWidth(),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            if (statusText != null) {
                LoadingStatusCard(statusText = statusText)
            }
            FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                DemoPrompts.forEach { (label, prompt) ->
                    Text(
                        text = label,
                        modifier = Modifier
                            .background(AppGreenSoft, RoundedCornerShape(999.dp))
                            .clickable(enabled = !isLoading) {
                                showAttachmentMenu = false
                                onQuickPrompt(prompt)
                            }
                            .padding(horizontal = 10.dp, vertical = 6.dp),
                        color = AccentGreenDark,
                        style = MaterialTheme.typography.labelMedium,
                    )
                }
            }
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .height(IntrinsicSize.Min),
            ) {
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    colors = CardDefaults.cardColors(containerColor = SurfaceCream),
                    shape = RoundedCornerShape(30.dp),
                    border = BorderStroke(1.dp, BorderGreen.copy(alpha = 0.9f)),
                    elevation = CardDefaults.cardElevation(defaultElevation = 0.dp),
                ) {
                    if (isRecording) {
                        RecordingInputRow(
                            waveformLevels = waveformLevels,
                            elapsedSeconds = recordingElapsedSeconds,
                            onStop = ::stopRecording,
                        )
                    } else {
                        Column(
                            modifier = Modifier.padding(horizontal = 12.dp, vertical = 10.dp),
                            verticalArrangement = Arrangement.spacedBy(6.dp),
                        ) {
                            pendingImage?.let { image ->
                                PendingInputImagePreview(
                                    preview = image.preview,
                                    onRemove = {
                                        image.uploadFile.delete()
                                        pendingImage = null
                                        attachmentStatusText = null
                                    },
                                )
                            }
                            BasicTextField(
                                value = value,
                                onValueChange = {
                                    attachmentStatusText = null
                                    onValueChange(it)
                                },
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .heightIn(min = 76.dp, max = 152.dp)
                                    .padding(horizontal = 4.dp, vertical = 4.dp),
                                minLines = 2,
                                maxLines = 5,
                                textStyle = MaterialTheme.typography.bodyLarge.copy(color = Ink),
                                cursorBrush = SolidColor(AccentGreenDark),
                                decorationBox = { innerTextField ->
                                    Box(
                                        modifier = Modifier.fillMaxWidth(),
                                        contentAlignment = Alignment.TopStart,
                                    ) {
                                        if (value.isBlank() && !hasPendingImage) {
                                            Text(
                                                text = "说说想买什么、预算或要避开的点",
                                                color = MutedText.copy(alpha = 0.32f),
                                                style = MaterialTheme.typography.titleMedium,
                                            )
                                        }
                                        innerTextField()
                                    }
                                },
                            )
                            if (inputStatusLines.isNotEmpty()) {
                                Column(
                                    verticalArrangement = Arrangement.spacedBy(4.dp),
                                ) {
                                    inputStatusLines.forEach { status ->
                                        val leadingIcon = when {
                                            status.isError -> TablerAlertTriangleIcon
                                            status.key.startsWith("speech:") -> TablerVolumeIcon
                                            status.key.startsWith("asr") -> TablerMicrophoneIcon
                                            else -> TablerPhotoIcon
                                        }
                                        DismissibleInputStatusPill(
                                            text = status.text,
                                            isError = status.isError,
                                            leadingIcon = leadingIcon,
                                            autoDismiss = status.key != "asr-transcribing",
                                            onDismiss = {
                                                dismissedInputStatusKeys = dismissedInputStatusKeys + status.key
                                            },
                                        )
                                    }
                                }
                            }
                            Row(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .height(44.dp),
                                verticalAlignment = Alignment.CenterVertically,
                                horizontalArrangement = Arrangement.spacedBy(8.dp),
                            ) {
                                InputToolbarButton(
                                    imageVector = TablerPlusIcon,
                                    contentDescription = "添加图片",
                                    enabled = canUseInputTools,
                                    selected = showAttachmentMenu,
                                    onClick = { showAttachmentMenu = !showAttachmentMenu },
                                )
                                Box {
                                    AssistantInputChip(
                                        label = currentRecipientName,
                                        enabled = !isLoading && !isTranscribing,
                                        onClick = {
                                            showAttachmentMenu = false
                                            showRecipientMenu = !showRecipientMenu
                                        },
                                    )
                                    RecipientSelectionMenu(
                                        visible = showRecipientMenu,
                                        recipients = recipients,
                                        selectedRecipientId = selectedRecipientId,
                                        isLoading = recipientsLoading,
                                        isSaving = recipientsSaving,
                                        error = recipientError,
                                        onDismiss = {
                                            showRecipientMenu = false
                                        },
                                        onSelect = { recipientId ->
                                            showRecipientMenu = false
                                            onRecipientSelected(recipientId)
                                        },
                                        onManageRecipients = {
                                            showRecipientMenu = false
                                            onOpenRecipientManagement()
                                        },
                                    )
                                }
                                Spacer(modifier = Modifier.weight(1f))
                                VoiceRecordButton(
                                    isRecording = false,
                                    isTranscribing = isTranscribing,
                                    enabled = canUseInputTools,
                                    onClick = ::toggleRecording,
                                )
                                SendRoundButton(
                                    isLoading = isLoading,
                                    enabled = canSendText,
                                    onClick = {
                                        showAttachmentMenu = false
                                        val imageToSend = pendingImage
                                        val overrideMessage = if (value.isBlank() && imageToSend != null) {
                                            "我上传了一张图片，帮我看看并推荐类似商品"
                                        } else {
                                            null
                                        }
                                        pendingImage = null
                                        attachmentStatusText = null
                                        onSend(overrideMessage, imageToSend)
                                    },
                                )
                            }
                        }
                    }
                }
            }
            AttachmentActionMenu(
                visible = showAttachmentMenu,
                modifier = Modifier
                    .padding(start = 8.dp, bottom = 56.dp),
                onCameraClick = {
                    cameraLauncher.launch(null)
                },
                onGalleryClick = {
                    galleryLauncher.launch("image/*")
                },
            )
        }
    }
}

@Composable
private fun RecipientSelectionMenu(
    visible: Boolean,
    recipients: List<RecipientProfile>,
    selectedRecipientId: String,
    isLoading: Boolean,
    isSaving: Boolean,
    error: String?,
    modifier: Modifier = Modifier,
    onDismiss: () -> Unit,
    onSelect: (String) -> Unit,
    onManageRecipients: () -> Unit,
) {
    DropdownMenu(
        expanded = visible,
        onDismissRequest = onDismiss,
        modifier = modifier.width(260.dp),
        offset = DpOffset(RecipientMenuOffsetX, RecipientMenuOffsetY),
        properties = PopupProperties(focusable = false),
        shape = RoundedCornerShape(22.dp),
        containerColor = SurfaceWhite,
        shadowElevation = 0.dp,
        tonalElevation = 0.dp,
        border = BorderStroke(1.dp, BorderGreen),
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(10.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            Text(
                text = "切换购买对象",
                color = Ink,
                fontWeight = FontWeight.Bold,
                style = MaterialTheme.typography.bodyLarge,
            )
            if (isLoading && recipients.isEmpty()) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.Center,
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    CircularProgressIndicator(
                        color = AccentGreenDark,
                        modifier = Modifier.size(16.dp),
                        strokeWidth = 2.dp,
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    Text(text = "加载常用对象中...", color = Ink)
                }
            }
            if (recipients.isNotEmpty()) {
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .heightIn(max = 280.dp)
                        .verticalScroll(rememberScrollState()),
                    verticalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    recipients.forEach { recipient ->
                        val isCurrent = recipient.recipientId == selectedRecipientId
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .clip(RoundedCornerShape(16.dp))
                                .background(if (isCurrent) AppGreenSoft else SurfaceWhite)
                                .clickable { onSelect(recipient.recipientId) }
                                .padding(12.dp),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            Column {
                                val displayName = recipient.displayName.cleanEditorValue().ifBlank { "对象" }
                                val relationship = recipient.relationship.cleanEditorValue().ifBlank { "关系未填写" }
                                Text(
                                    text = displayName,
                                    color = Ink,
                                    fontWeight = FontWeight.Bold,
                                    style = MaterialTheme.typography.bodyMedium,
                                )
                                Text(
                                    text = relationship,
                                    color = MutedText,
                                    style = MaterialTheme.typography.labelSmall,
                                )
                            }
                            if (isCurrent) {
                                Text(
                                    text = "当前",
                                    color = AccentGreenDark,
                                    fontWeight = FontWeight.Bold,
                                    style = MaterialTheme.typography.labelSmall,
                                )
                            }
                        }
                    }
                }
            }
            if (error != null) {
                Text(
                    text = "状态：$error",
                    color = ErrorText,
                    style = MaterialTheme.typography.labelSmall,
                )
            }
            if (!isLoading && recipients.isEmpty() && error == null) {
                Text(
                    text = "暂无常用购买对象，请先到设置中创建",
                    color = MutedText,
                    style = MaterialTheme.typography.labelSmall,
                )
            }
            HorizontalDivider()
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 14.dp, vertical = 10.dp),
                horizontalArrangement = Arrangement.End,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                TextButton(onClick = onManageRecipients, enabled = !isSaving) {
                    Text(
                        text = "管理常用对象",
                        color = AccentGreenDark,
                        fontWeight = FontWeight.Bold,
                    )
                }
            }
        }
    }
}

@Composable
private fun PendingInputImagePreview(
    preview: Any,
    onRemove: () -> Unit,
) {
    Box(
        modifier = Modifier
            .size(76.dp)
            .clip(RoundedCornerShape(18.dp))
            .background(AppGreenSoft),
    ) {
        when (preview) {
            is Uri -> {
                SubcomposeAsyncImage(
                    model = preview,
                    contentDescription = "已选择图片",
                    contentScale = ContentScale.Crop,
                    modifier = Modifier.fillMaxSize(),
                    loading = { ProductImageFallback("图") },
                    error = { ProductImageFallback("图") },
                    success = { SubcomposeAsyncImageContent() },
                )
            }

            is Bitmap -> {
                Image(
                    bitmap = preview.asImageBitmap(),
                    contentDescription = "已拍摄图片",
                    contentScale = ContentScale.Crop,
                    modifier = Modifier.fillMaxSize(),
                )
            }
        }

        Box(
            modifier = Modifier
                .align(Alignment.TopEnd)
                .padding(4.dp)
                .size(22.dp)
                .clip(RoundedCornerShape(999.dp))
                .background(SurfaceWhite.copy(alpha = 0.92f))
                .clickable(onClick = onRemove),
            contentAlignment = Alignment.Center,
        ) {
            Icon(
                imageVector = TablerXIcon,
                contentDescription = "移除图片",
                tint = Ink,
                modifier = Modifier.size(14.dp),
            )
        }
    }
}

@Composable
private fun DismissibleInputStatusPill(
    text: String,
    isError: Boolean,
    leadingIcon: ImageVector,
    autoDismiss: Boolean,
    onDismiss: () -> Unit,
) {
    if (autoDismiss) {
        LaunchedEffect(text, isError) {
            delay(InputStatusAutoDismissMillis)
            onDismiss()
        }
    }

    InputStatusPill(
        text = text,
        isError = isError,
        leadingIcon = leadingIcon,
        onDismiss = onDismiss,
    )
}

@Composable
private fun InputStatusPill(
    text: String,
    isError: Boolean,
    leadingIcon: ImageVector,
    onDismiss: () -> Unit,
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .background(if (isError) ErrorSurface else AppGreenSoft.copy(alpha = 0.72f), RoundedCornerShape(999.dp))
            .padding(horizontal = 10.dp, vertical = 6.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        Icon(
            imageVector = leadingIcon,
            contentDescription = null,
            tint = if (isError) ErrorText else AccentGreenDark,
            modifier = Modifier.size(15.dp),
        )
        Text(
            text = text,
            color = if (isError) ErrorText else MutedText,
            softWrap = true,
            maxLines = 2,
            overflow = TextOverflow.Visible,
            style = MaterialTheme.typography.labelSmall,
            modifier = Modifier.weight(1f),
        )
        Icon(
            imageVector = TablerXIcon,
            contentDescription = "关闭提示",
            tint = if (isError) ErrorText else MutedText,
            modifier = Modifier
                .size(15.dp)
                .clickable(onClick = onDismiss),
        )
    }
}

@Composable
private fun AttachmentActionMenu(
    visible: Boolean,
    modifier: Modifier = Modifier,
    onCameraClick: () -> Unit,
    onGalleryClick: () -> Unit,
) {
    AnimatedVisibility(
        visible = visible,
        modifier = modifier,
        enter = fadeIn(animationSpec = tween(140)) + slideInVertically(initialOffsetY = { it / 2 }),
        exit = fadeOut(animationSpec = tween(100)) + slideOutVertically(targetOffsetY = { it / 2 }),
    ) {
        Card(
            modifier = Modifier.width(188.dp),
            colors = CardDefaults.cardColors(containerColor = SurfaceWhite),
            shape = RoundedCornerShape(18.dp),
            border = BorderStroke(1.dp, BorderGreen),
            elevation = CardDefaults.cardElevation(defaultElevation = 6.dp),
        ) {
            Column(
                modifier = Modifier.padding(vertical = 8.dp),
            ) {
                AttachmentActionRow(
                    icon = TablerCameraIcon,
                    text = "拍照",
                    onClick = onCameraClick,
                )
                AttachmentActionRow(
                    icon = TablerPhotoIcon,
                    text = "从相册选择",
                    onClick = onGalleryClick,
                )
            }
        }
    }
}

@Composable
private fun AttachmentActionRow(
    icon: ImageVector,
    text: String,
    onClick: () -> Unit,
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick)
            .padding(horizontal = 14.dp, vertical = 10.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        Icon(
            imageVector = icon,
            contentDescription = null,
            tint = AccentGreenDark,
            modifier = Modifier.size(20.dp),
        )
        Text(
            text = text,
            color = Ink,
            fontWeight = FontWeight.Medium,
            style = MaterialTheme.typography.bodyMedium,
        )
    }
}

@Composable
private fun AssistantInputChip(
    label: String,
    enabled: Boolean,
    onClick: () -> Unit,
) {
    Row(
        modifier = Modifier
            .height(34.dp)
            .clip(RoundedCornerShape(999.dp))
            .background(AppGreenSoft.copy(alpha = 0.86f))
            .clickable(enabled = enabled, onClick = onClick)
            .padding(start = 6.dp, end = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(5.dp),
    ) {
        GuideAssistantImage(
            modifier = Modifier.size(22.dp),
            cornerRadius = 8.dp,
        )
        Text(
            text = label,
            color = if (enabled) AccentGreenDark else MutedText,
            fontWeight = FontWeight.Bold,
            style = MaterialTheme.typography.labelMedium,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
        )
        Icon(
            imageVector = TablerChevronDownIcon,
            contentDescription = "切换购买对象上下文",
            tint = if (enabled) AccentGreenDark else MutedText,
            modifier = Modifier.size(15.dp),
        )
    }
}

@Composable
private fun RecipientManagementDialog(
    recipients: List<RecipientProfile>,
    selectedRecipientId: String,
    isLoading: Boolean,
    isSaving: Boolean,
    error: String?,
    onDismiss: () -> Unit,
    onSave: (List<RecipientProfile>, String) -> Unit,
) {
    val normalizedRecipients = remember(recipients) { normalizeRecipientProfilesForEditor(recipients) }
    var draftRecipients by remember(normalizedRecipients) {
        mutableStateOf(normalizedRecipients.map { it.toRecipientEditorState() })
    }
    var draftSelectedRecipientId by remember {
        mutableStateOf(resolveSelectedRecipientIdForEditor(normalizedRecipients, selectedRecipientId))
    }

    LaunchedEffect(normalizedRecipients, selectedRecipientId) {
        draftRecipients = normalizedRecipients.map { it.toRecipientEditorState() }
        draftSelectedRecipientId = resolveSelectedRecipientIdForEditor(normalizedRecipients, selectedRecipientId)
    }

    fun updateRecipient(index: Int, transform: (RecipientEditorState) -> RecipientEditorState) {
        val next = draftRecipients.toMutableList()
        if (index in draftRecipients.indices) {
            next[index] = transform(draftRecipients[index])
            draftRecipients = next
        }
    }

    fun addRecipient() {
        val newRecipientId = "custom-${System.currentTimeMillis()}"
        draftRecipients = draftRecipients + RecipientEditorState(
            recipientId = newRecipientId,
            displayName = "自定义对象",
            relationship = "",
            allergies = "",
            avoidTerms = "",
            brandExclude = "",
            budgetMax = "",
            accessibilityNeeds = "",
            preferredCategories = "",
            preferredTags = "",
            priceSensitivity = "",
            skinType = "",
            shoeSize = "",
            clothingSize = "",
            phone = "",
            address = "",
        )
        draftSelectedRecipientId = newRecipientId
    }

    fun deleteRecipient(index: Int) {
        val targetId = draftRecipients.getOrNull(index)?.recipientId ?: return
        if (targetId == "self") return

        val next = draftRecipients.toMutableList().apply { removeAt(index) }
        if (next.isEmpty()) {
            next += RecipientProfile(recipientId = "self", displayName = "自己", relationship = "self").toRecipientEditorState()
        }
        draftRecipients = next
        if (draftSelectedRecipientId == targetId) {
            draftSelectedRecipientId = resolveSelectedRecipientIdForEditor(
                next.map { it.toRecipientProfile() },
                draftSelectedRecipientId,
            )
        }
    }

    fun save(requestDismiss: () -> Unit) {
        val normalized = normalizeRecipientProfilesForEditor(draftRecipients.map { it.toRecipientProfile() })
        draftRecipients = normalized.map { it.toRecipientEditorState() }
        draftSelectedRecipientId = resolveSelectedRecipientIdForEditor(normalized, draftSelectedRecipientId)
        onSave(normalized, draftSelectedRecipientId)
        requestDismiss()
    }

    ReusableBottomSheetOverlay(
        sheetKey = "recipient-management",
        maxHeightFraction = 0.92f,
        onDismiss = onDismiss,
    ) { requestDismiss ->
        ReusableBottomSheetCard(
            maxHeightFraction = 0.92f,
            onDismiss = requestDismiss,
        ) {
            BottomSheetHeader(
                title = "常用购买对象",
                subtitle = null,
                onDismiss = requestDismiss,
            )
            Column(
                modifier = Modifier
                    .weight(1f)
                    .verticalScroll(rememberScrollState())
                    .padding(horizontal = 24.dp, vertical = 8.dp),
                verticalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                if (isLoading && draftRecipients.isEmpty()) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.Center,
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        CircularProgressIndicator(
                            color = AccentGreenDark,
                            modifier = Modifier.size(16.dp),
                            strokeWidth = 2.dp,
                        )
                        Spacer(modifier = Modifier.width(8.dp))
                        Text(text = "加载常用对象中...", color = Ink)
                    }
                }

                draftRecipients.forEachIndexed { index, recipient ->
                    val isCurrent = recipient.recipientId == draftSelectedRecipientId
                    Card(
                        modifier = Modifier.fillMaxWidth(),
                        colors = CardDefaults.cardColors(containerColor = SurfaceWhite),
                        shape = RoundedCornerShape(16.dp),
                        border = BorderStroke(1.dp, BorderGreen.copy(alpha = 0.7f)),
                    ) {
                        Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically,
                            ) {
                                Column(modifier = Modifier.weight(1f)) {
                                    RecipientField(
                                        label = "显示名",
                                        value = recipient.displayName.cleanEditorValue(),
                                        onValueChange = { value ->
                                            updateRecipient(index) { it.copy(displayName = value.cleanEditorValue()) }
                                        },
                                    )
                                    RecipientField(
                                        label = "关系",
                                        value = recipient.relationship.cleanEditorValue(),
                                        onValueChange = { value ->
                                            updateRecipient(index) { it.copy(relationship = value.cleanEditorValue()) }
                                        },
                                    )
                                }
                                if (recipient.recipientId == "self") {
                                    Text(
                                        text = "自己",
                                        color = AccentGreenDark,
                                        fontWeight = FontWeight.Bold,
                                        style = MaterialTheme.typography.labelMedium,
                                    )
                                } else {
                                    if (!isCurrent) {
                                        TextButton(onClick = { draftSelectedRecipientId = recipient.recipientId }) {
                                            Text(text = "设为当前")
                                        }
                                    } else {
                                        Text(
                                            text = "当前",
                                            color = AccentGreenDark,
                                            fontWeight = FontWeight.Bold,
                                            style = MaterialTheme.typography.labelSmall,
                                        )
                                    }
                                }
                            }
                            HorizontalDivider()
                            Text(
                                text = "收货信息",
                                color = Ink,
                                fontWeight = FontWeight.Bold,
                                style = MaterialTheme.typography.bodySmall,
                            )
                            RecipientField(
                                label = "电话",
                                value = recipient.phone.cleanEditorValue(),
                                onValueChange = { value ->
                                    updateRecipient(index) { it.copy(phone = value.cleanEditorValue()) }
                                },
                            )
                            RecipientField(
                                label = "地址",
                                value = recipient.address.cleanEditorValue(),
                                singleLine = false,
                                minLines = 2,
                                onValueChange = { value ->
                                    updateRecipient(index) { it.copy(address = value.cleanEditorValue()) }
                                },
                            )

                            if (recipient.recipientId != "self") {
                                TextButton(
                                    onClick = { deleteRecipient(index) },
                                    enabled = !isSaving,
                                ) {
                                    Text(
                                        text = "删除",
                                        color = ErrorText,
                                    )
                                }
                            }
                        }
                    }
                }

                if (!isLoading) {
                    TextButton(
                        onClick = { addRecipient() },
                        enabled = !isSaving,
                    ) {
                        Text(text = "新增对象")
                    }
                }

                if (error != null) {
                    Text(
                        text = "状态：$error",
                        color = ErrorText,
                        style = MaterialTheme.typography.labelSmall,
                    )
                }
            }
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 24.dp, vertical = 14.dp),
                horizontalArrangement = Arrangement.End,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                TextButton(onClick = { save(requestDismiss) }, enabled = !isSaving) {
                    Text(
                        text = if (isSaving) "保存中..." else "保存",
                        color = AccentGreenDark,
                    )
                }
            }
        }
    }
}

@Composable
private fun RecipientField(
    label: String,
    value: String,
    singleLine: Boolean = true,
    minLines: Int = 1,
    enabled: Boolean = true,
    onValueChange: (String) -> Unit,
) {
    val cleanedValue = value.cleanEditorValue()

    Column(
        modifier = Modifier.fillMaxWidth(),
        verticalArrangement = Arrangement.spacedBy(4.dp),
    ) {
        Text(
            text = label,
            color = Ink,
            style = MaterialTheme.typography.labelMedium,
        )
        BasicTextField(
            value = cleanedValue,
            enabled = enabled,
            onValueChange = onValueChange,
            modifier = Modifier
                .fillMaxWidth()
                .clip(RoundedCornerShape(10.dp))
                .background(if (enabled) SurfaceWhite else SurfaceWhite.copy(alpha = 0.45f))
                .padding(10.dp)
                .heightIn(min = 30.dp),
            textStyle = MaterialTheme.typography.bodyMedium.copy(color = Ink),
            cursorBrush = SolidColor(AccentGreenDark),
            minLines = minLines,
            maxLines = if (singleLine) 1 else 4,
            decorationBox = { innerTextField ->
                Box {
                    if (cleanedValue.isBlank()) {
                        Text(
                            text = "未填写",
                            color = MutedText.copy(alpha = 0.42f),
                            style = MaterialTheme.typography.bodyMedium,
                        )
                    }
                    innerTextField()
                }
            },
        )
    }
}

@Composable
private fun RecordingInputRow(
    waveformLevels: List<Float>,
    elapsedSeconds: Int,
    onStop: () -> Unit,
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .height(68.dp)
            .padding(start = 8.dp, end = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        InputToolbarButton(
            imageVector = TablerPlusIcon,
            contentDescription = "录音中暂不可添加图片",
            enabled = false,
            onClick = {},
        )
        Row(
            modifier = Modifier.weight(1f),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            VoiceDottedRail(modifier = Modifier.weight(1f))
            VoiceWaveform(
                levels = waveformLevels,
                color = MutedText,
                modifier = Modifier.width(82.dp),
            )
            Text(
                text = formatVoiceDuration(elapsedSeconds),
                color = MutedText,
                style = MaterialTheme.typography.titleMedium,
            )
        }
        InputToolbarButton(
            imageVector = TablerStopIcon,
            contentDescription = "停止录音并转写",
            containerColor = SurfaceWhite,
            contentColor = MutedText,
            onClick = onStop,
        )
        SendRoundButton(
            isLoading = false,
            enabled = true,
            onClick = onStop,
        )
    }
}

@Composable
private fun VoiceDottedRail(modifier: Modifier = Modifier) {
    Row(
        modifier = modifier.height(24.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(5.dp),
    ) {
        repeat(18) {
            Box(
                modifier = Modifier
                    .weight(1f)
                    .height(1.dp)
                    .background(BorderGreen.copy(alpha = 0.72f), RoundedCornerShape(999.dp)),
            )
        }
    }
}

@Composable
private fun InputToolbarButton(
    imageVector: ImageVector,
    contentDescription: String,
    enabled: Boolean = true,
    selected: Boolean = false,
    containerColor: Color = if (selected) AppGreenSoft else Color.Transparent,
    contentColor: Color = MutedText,
    onClick: () -> Unit,
) {
    Box(
        modifier = Modifier
            .size(40.dp)
            .clip(RoundedCornerShape(999.dp))
            .background(if (enabled) containerColor else Color.Transparent)
            .clickable(enabled = enabled, onClick = onClick),
        contentAlignment = Alignment.Center,
    ) {
        Icon(
            imageVector = imageVector,
            contentDescription = contentDescription,
            tint = if (enabled) contentColor else MutedText.copy(alpha = 0.28f),
            modifier = Modifier.size(22.dp),
        )
    }
}

@Composable
private fun SendRoundButton(
    isLoading: Boolean,
    enabled: Boolean,
    onClick: () -> Unit,
) {
    val canClick = enabled && !isLoading
    Box(
        modifier = Modifier
            .size(46.dp)
            .clip(RoundedCornerShape(999.dp))
            .background(if (canClick) MutedText else BorderGreen.copy(alpha = 0.65f))
            .clickable(enabled = canClick, onClick = onClick),
        contentAlignment = Alignment.Center,
    ) {
        if (isLoading) {
            CircularProgressIndicator(
                modifier = Modifier.size(20.dp),
                color = SurfaceWhite,
                strokeWidth = 2.dp,
            )
        } else {
            Icon(
                imageVector = TablerArrowUpIcon,
                contentDescription = "发送",
                tint = if (canClick) SurfaceWhite else MutedText.copy(alpha = 0.64f),
                modifier = Modifier.size(24.dp),
            )
        }
    }
}

private data class RecipientEditorState(
    val recipientId: String,
    val displayName: String,
    val relationship: String,
    val allergies: String,
    val avoidTerms: String,
    val brandExclude: String,
    val budgetMax: String,
    val accessibilityNeeds: String,
    val preferredCategories: String,
    val preferredTags: String,
    val priceSensitivity: String,
    val skinType: String,
    val shoeSize: String,
    val clothingSize: String,
    val phone: String,
    val address: String,
)

private fun normalizeRecipientProfilesForEditor(input: List<RecipientProfile>): List<RecipientProfile> {
    val deduped = linkedMapOf<String, RecipientProfile>()
    input.forEach { candidate ->
        val trimmedId = candidate.recipientId.trim()
        if (trimmedId.isBlank()) return@forEach
        deduped[trimmedId] = candidate.copy(recipientId = trimmedId)
    }
    if (!deduped.containsKey("self")) {
        deduped["self"] = RecipientProfile(recipientId = "self", displayName = "自己", relationship = "self")
    }
    return deduped.values.toList()
}

private fun String?.cleanEditorValue(): String {
    val trimmed = this?.trim().orEmpty()
    return if (trimmed.equals("null", ignoreCase = true)) "" else trimmed
}

private fun resolveSelectedRecipientIdForEditor(
    recipients: List<RecipientProfile>,
    selectedRecipientId: String,
): String {
    val safeRecipients = normalizeRecipientProfilesForEditor(recipients)
    val candidate = selectedRecipientId.trim()
    if (candidate.isNotBlank() && safeRecipients.any { it.recipientId == candidate }) {
        return candidate
    }
    return safeRecipients.firstOrNull { it.recipientId == "self" }?.recipientId
        ?: safeRecipients.firstOrNull()?.recipientId
        ?: "self"
}

private fun parseRecipientStringList(raw: String): List<String> {
    return raw.split(";", "；", ",", "，", "\n")
        .asSequence()
        .map { it.trim() }
        .filter { it.isNotBlank() }
        .toList()
}

private fun parseRecipientDouble(raw: String): Double? {
    return raw.trim().toDoubleOrNull()
}

private fun parseRecipientPreferenceMap(raw: String): Map<String, Double> {
    val map = linkedMapOf<String, Double>()
    raw.split(";", "；", ",", "，", "\n").forEach { token ->
        val trimmedToken = token.trim()
        if (trimmedToken.isBlank()) return@forEach

        val sepIndex = trimmedToken.indexOf(':').takeIf { it >= 0 }
            ?: trimmedToken.indexOf('=').takeIf { it >= 0 }
        if (sepIndex != null && sepIndex >= 0) {
            val key = trimmedToken.substring(0, sepIndex).trim()
            val value = parseRecipientDouble(trimmedToken.substring(sepIndex + 1))
            if (key.isNotBlank()) {
                map[key] = value ?: 1.0
            }
        } else {
            map[trimmedToken] = 1.0
        }
    }
    return map
}

private fun formatRecipientPreferenceMap(input: Map<String, Double>): String {
    return input.entries.joinToString(", ") { (key, value) ->
        if (value.isNaN() || value == 1.0) key else "$key: $value"
    }
}

private fun RecipientProfile.toRecipientEditorState(): RecipientEditorState {
    return RecipientEditorState(
        recipientId = recipientId,
        displayName = displayName.cleanEditorValue(),
        relationship = relationship.cleanEditorValue(),
        allergies = constraints.allergies.joinToString(", ").cleanEditorValue(),
        avoidTerms = constraints.avoidTerms.joinToString(", ").cleanEditorValue(),
        brandExclude = constraints.brandExclude.joinToString(", ").cleanEditorValue(),
        budgetMax = constraints.budgetMax?.toString().orEmpty().cleanEditorValue(),
        accessibilityNeeds = constraints.accessibilityNeeds.joinToString(", ").cleanEditorValue(),
        preferredCategories = formatRecipientPreferenceMap(longTermPreferences.preferredCategories).cleanEditorValue(),
        preferredTags = formatRecipientPreferenceMap(longTermPreferences.preferredTags).cleanEditorValue(),
        priceSensitivity = longTermPreferences.priceSensitivity?.toString().orEmpty().cleanEditorValue(),
        skinType = bodyProfile.skinType.cleanEditorValue(),
        shoeSize = bodyProfile.shoeSize.cleanEditorValue(),
        clothingSize = bodyProfile.clothingSize.cleanEditorValue(),
        phone = shipping.phone.cleanEditorValue(),
        address = shipping.address.cleanEditorValue(),
    )
}

private fun RecipientEditorState.toRecipientProfile(): RecipientProfile {
    return RecipientProfile(
        recipientId = recipientId.ifBlank { "custom-${System.currentTimeMillis()}" },
        displayName = displayName.cleanEditorValue().ifBlank { recipientId.ifBlank { "对象" } },
        relationship = relationship.cleanEditorValue().ifBlank { null },
        constraints = RecipientConstraints(
            allergies = parseRecipientStringList(allergies.cleanEditorValue()),
            avoidTerms = parseRecipientStringList(avoidTerms.cleanEditorValue()),
            brandExclude = parseRecipientStringList(brandExclude.cleanEditorValue()),
            budgetMax = parseRecipientDouble(budgetMax.cleanEditorValue()),
            accessibilityNeeds = parseRecipientStringList(accessibilityNeeds.cleanEditorValue()),
        ),
        longTermPreferences = RecipientLongTermPreferences(
            preferredCategories = parseRecipientPreferenceMap(preferredCategories.cleanEditorValue()),
            preferredTags = parseRecipientPreferenceMap(preferredTags.cleanEditorValue()),
            priceSensitivity = parseRecipientDouble(priceSensitivity.cleanEditorValue()),
        ),
        shipping = RecipientShipping(
            addressLabel = null,
            recipientName = null,
            phone = phone.cleanEditorValue().ifBlank { null },
            address = address.cleanEditorValue().ifBlank { null },
        ),
        bodyProfile = RecipientBodyProfile(
            skinType = skinType.cleanEditorValue().ifBlank { null },
            shoeSize = shoeSize.cleanEditorValue().ifBlank { null },
            clothingSize = clothingSize.cleanEditorValue().ifBlank { null },
        ),
    )
}

private fun formatVoiceDuration(seconds: Int): String {
    val safeSeconds = seconds.coerceAtLeast(0)
    return "${safeSeconds / 60}:${(safeSeconds % 60).toString().padStart(2, '0')}"
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

private fun copyUriToCacheImage(context: Context, uri: Uri): File {
    val outputFile = File.createTempFile("pending_image_", ".jpg", context.cacheDir)
    context.contentResolver.openInputStream(uri).use { input ->
        requireNotNull(input) { "无法读取图片" }
        outputFile.outputStream().use { output ->
            input.copyTo(output)
        }
    }
    return outputFile
}

private fun writeBitmapToCacheImage(context: Context, bitmap: Bitmap): File {
    val outputFile = File.createTempFile("pending_camera_", ".jpg", context.cacheDir)
    outputFile.outputStream().use { output ->
        bitmap.compress(Bitmap.CompressFormat.JPEG, 92, output)
    }
    return outputFile
}

private fun hasRecordAudioPermission(context: Context): Boolean {
    return context.checkSelfPermission(Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED
}
