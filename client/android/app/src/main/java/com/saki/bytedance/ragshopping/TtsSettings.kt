package com.saki.bytedance.ragshopping

import android.content.Context

data class TtsSettings(
    val autoSpeak: Boolean = true,
)

object TtsSettingsStore {
    private const val PreferencesName = "rag_shopping_tts_settings"
    private const val AutoSpeakKey = "auto_speak"

    fun load(context: Context): TtsSettings {
        val preferences = context.getSharedPreferences(PreferencesName, Context.MODE_PRIVATE)
        return TtsSettings(
            autoSpeak = preferences.getBoolean(AutoSpeakKey, true),
        )
    }

    fun save(context: Context, settings: TtsSettings) {
        context.getSharedPreferences(PreferencesName, Context.MODE_PRIVATE)
            .edit()
            .putBoolean(AutoSpeakKey, settings.autoSpeak)
            .apply()
    }
}
