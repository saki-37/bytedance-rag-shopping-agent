package com.saki.bytedance.ragshopping

/**
 * 后端地址唯一配置点。客户端会按 CandidateBaseUrls 顺序逐个尝试，
 * 第一个连通的地址会被记住并优先复用（见 ShoppingAgentClient.orderedBaseUrls）。
 *
 * 三种调试方式（无需改代码）：
 * 1. 真机局域网调试：在仓库根目录 local.properties 配置
 *      backend.lan.url=http://<电脑局域网IP>:8000
 *    重新构建后该地址排在首位。换网络/换 IP 只改这一行。
 * 2. USB 真机 / 模拟器 + adb reverse：adb reverse tcp:8000 tcp:8000，
 *    走 127.0.0.1。
 * 3. 模拟器免 reverse：自动回退 10.0.2.2。
 */
object BackendConfig {
    const val DefaultBaseUrl = "http://127.0.0.1:8000"

    /** local.properties 里的 backend.lan.url，未配置时为空字符串 */
    private val lanBaseUrl: String = BuildConfig.BACKEND_LAN_URL.trim().trimEnd('/')

    val CandidateBaseUrls = buildList {
        if (lanBaseUrl.isNotBlank()) add(lanBaseUrl)
        add(DefaultBaseUrl)
        add("http://10.0.2.2:8000")
    }
}
