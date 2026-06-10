package com.saki.bytedance.ragshopping

import android.content.Context
import kotlin.math.abs

/**
 * 演示级"本地身份"。
 *
 * 注意：这不是真实账号系统——没有密码、没有服务端鉴权，
 * 只是把一个 user_id 存在本机 SharedPreferences 里，
 * 用于演示"不同用户拥有各自的常用对象 / 记忆 profile"。
 * user_id 会透传给后端 /api/chat/stream、feedback、user-memory 接口。
 */
data class DemoIdentity(
    val userId: String = DemoIdentityStore.DefaultUserId,
    val displayName: String = DemoIdentityStore.DefaultDisplayName,
)

object DemoIdentityStore {
    /** 与后端 user_memory.DEFAULT_MEMORY_USER_ID 保持一致 */
    const val DefaultUserId = "local-demo-user"
    const val DefaultDisplayName = "本地演示用户"

    private const val PreferencesName = "rag_shopping_demo_identity"
    private const val UserIdKey = "userId"
    private const val DisplayNameKey = "displayName"

    /** 与后端 _sanitize_user_id 一致的安全字符集 */
    private val SafeUserIdRegex = Regex("[^0-9a-zA-Z._-]+")

    fun load(context: Context): DemoIdentity {
        val preferences = context.getSharedPreferences(PreferencesName, Context.MODE_PRIVATE)
        val userId = preferences.getString(UserIdKey, null)?.takeIf { it.isNotBlank() }
            ?: DefaultUserId
        val displayName = preferences.getString(DisplayNameKey, null)?.takeIf { it.isNotBlank() }
            ?: defaultDisplayNameFor(userId)
        return DemoIdentity(userId = userId, displayName = displayName)
    }

    fun save(context: Context, identity: DemoIdentity) {
        context.getSharedPreferences(PreferencesName, Context.MODE_PRIVATE)
            .edit()
            .putString(UserIdKey, identity.userId)
            .putString(DisplayNameKey, identity.displayName)
            .apply()
    }

    /**
     * 把用户输入的昵称/ID 转成后端可接受的 user_id。
     * - 英文/数字/._- 直接保留；
     * - 中文等其他字符会被后端替换成下划线，所以这里改用
     *   "demo-<昵称哈希>" 生成稳定 ID（同一昵称每次得到同一 ID）。
     */
    fun deriveIdentity(rawInput: String): DemoIdentity {
        val trimmed = rawInput.trim()
        if (trimmed.isBlank()) return DemoIdentity()
        val sanitized = SafeUserIdRegex.replace(trimmed, "_").trim('_').take(64)
        val userId = if (sanitized.isNotBlank() && sanitized.any { it.isLetterOrDigit() }) {
            sanitized
        } else {
            "demo-${abs(trimmed.hashCode()) % 100000}"
        }
        return DemoIdentity(userId = userId, displayName = trimmed.take(20))
    }

    private fun defaultDisplayNameFor(userId: String): String {
        return if (userId == DefaultUserId) DefaultDisplayName else userId
    }
}
