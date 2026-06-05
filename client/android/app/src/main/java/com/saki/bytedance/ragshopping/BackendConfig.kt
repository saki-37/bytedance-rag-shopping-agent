package com.saki.bytedance.ragshopping

object BackendConfig {
    const val DefaultBaseUrl = "http://127.0.0.1:8000"

    val CandidateBaseUrls = listOf(
        DefaultBaseUrl,
        "http://10.0.2.2:8000",
    )
}
