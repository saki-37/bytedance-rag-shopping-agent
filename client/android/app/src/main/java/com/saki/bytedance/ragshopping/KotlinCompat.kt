package com.saki.bytedance.ragshopping

/**
 * Local nullable-string helper used by older Compose UI code.
 *
 * Kotlin stdlib has String?.orEmpty(), but not orBlank().  Keeping this
 * extension in the app package fixes existing call sites without touching the
 * large MainActivity.kt file and treats whitespace-only values as empty.
 */
fun String?.orBlank(): String {
    return this?.takeIf { it.isNotBlank() } ?: ""
}
