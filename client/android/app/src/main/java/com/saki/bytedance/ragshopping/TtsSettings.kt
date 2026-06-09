package com.saki.bytedance.ragshopping

import android.content.Context
import kotlin.math.abs

const val FontScaleModeSystem = "system"
const val FontScaleMode11x = "1.1"
const val FontScaleMode125x = "1.25"
const val FontScaleMode15x = "1.5"

data class TtsSettings(
    val ttsEnabled: Boolean = true,
    val ttsVerboseMode: Boolean = false,
    val ttsSpeechRate: Float = 1.0f,
    val ttsStatusAnnouncementEnabled: Boolean = true,
    val fontScaleMode: String = FontScaleModeSystem,
    val speechHintVisibility: Boolean = true,
)

object TtsSettingsStore {
    private const val PreferencesName = "rag_shopping_tts_settings"
    private const val LegacyAutoSpeakKey = "auto_speak"
    private const val TtsEnabledKey = "ttsEnabled"
    private const val TtsVerboseModeKey = "ttsVerboseMode"
    private const val TtsSpeechRateKey = "ttsSpeechRate"
    private const val TtsStatusAnnouncementEnabledKey = "ttsStatusAnnouncementEnabled"
    private const val FontScaleModeKey = "fontScaleMode"
    private const val SpeechHintVisibilityKey = "speechHintVisibility"

    private val AllowedSpeechRates = listOf(0.75f, 1.0f, 1.25f, 1.5f)
    private val AllowedFontScaleModes = setOf(FontScaleModeSystem, FontScaleMode11x, FontScaleMode125x, FontScaleMode15x)

    fun load(context: Context): TtsSettings {
        val preferences = context.getSharedPreferences(PreferencesName, Context.MODE_PRIVATE)
        val savedEnabled = if (preferences.contains(TtsEnabledKey)) {
            preferences.getBoolean(TtsEnabledKey, true)
        } else {
            preferences.getBoolean(LegacyAutoSpeakKey, true)
        }

        return TtsSettings(
            ttsEnabled = savedEnabled,
            ttsVerboseMode = preferences.getBoolean(TtsVerboseModeKey, false),
            ttsSpeechRate = normalizeSpeechRate(preferences.getFloat(TtsSpeechRateKey, 1.0f)),
            ttsStatusAnnouncementEnabled = preferences.getBoolean(TtsStatusAnnouncementEnabledKey, true),
            fontScaleMode = normalizeFontScale(preferences.getString(FontScaleModeKey, FontScaleModeSystem)),
            speechHintVisibility = preferences.getBoolean(SpeechHintVisibilityKey, true),
        )
    }

    fun save(context: Context, settings: TtsSettings) {
        context.getSharedPreferences(PreferencesName, Context.MODE_PRIVATE)
            .edit()
            .putBoolean(TtsEnabledKey, settings.ttsEnabled)
            .putBoolean(TtsVerboseModeKey, settings.ttsVerboseMode)
            .putFloat(TtsSpeechRateKey, normalizeSpeechRate(settings.ttsSpeechRate))
            .putBoolean(TtsStatusAnnouncementEnabledKey, settings.ttsStatusAnnouncementEnabled)
            .putString(FontScaleModeKey, normalizeFontScale(settings.fontScaleMode))
            .putBoolean(SpeechHintVisibilityKey, settings.speechHintVisibility)
            .apply()
    }

    private fun normalizeSpeechRate(value: Float): Float {
        return AllowedSpeechRates.firstOrNull { abs(it - value) < 0.0001f } ?: 1.0f
    }

    private fun normalizeFontScale(value: String?): String {
        val normalized = value ?: FontScaleModeSystem
        return if (AllowedFontScaleModes.contains(normalized)) normalized else FontScaleModeSystem
    }
}
