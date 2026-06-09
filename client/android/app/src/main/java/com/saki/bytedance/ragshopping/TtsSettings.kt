package com.saki.bytedance.ragshopping

import android.content.Context

data class TtsSettings(
    val autoSpeak: Boolean = true,
    val voicePreference: TtsVoicePreference = TtsVoicePreference.SystemDefault,
)

enum class TtsVoicePreference(val label: String) {
    SystemDefault("系统默认"),
    FemalePreferred("女声优先"),
    MalePreferred("男声优先"),
}

object TtsSettingsStore {
    private const val PreferencesName = "rag_shopping_tts_settings"
    private const val AutoSpeakKey = "auto_speak"
    private const val VoicePreferenceKey = "voice_preference"

    fun load(context: Context): TtsSettings {
        val preferences = context.getSharedPreferences(PreferencesName, Context.MODE_PRIVATE)
        val voicePreference = runCatching {
            TtsVoicePreference.valueOf(
                preferences.getString(VoicePreferenceKey, TtsVoicePreference.SystemDefault.name)
                    ?: TtsVoicePreference.SystemDefault.name
            )
        }.getOrDefault(TtsVoicePreference.SystemDefault)
        return TtsSettings(
            autoSpeak = preferences.getBoolean(AutoSpeakKey, true),
            voicePreference = voicePreference,
        )
    }

    fun save(context: Context, settings: TtsSettings) {
        context.getSharedPreferences(PreferencesName, Context.MODE_PRIVATE)
            .edit()
            .putBoolean(AutoSpeakKey, settings.autoSpeak)
            .putString(VoicePreferenceKey, settings.voicePreference.name)
            .apply()
    }
}
