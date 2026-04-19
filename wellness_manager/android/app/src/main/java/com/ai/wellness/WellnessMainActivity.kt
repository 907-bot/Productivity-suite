package com.ai.wellness

import android.annotation.SuppressLint
import android.os.Bundle
import android.webkit.*
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import kotlinx.coroutines.*
import okhttp3.*
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody.Companion.toRequestBody

/**
 * Wellness Manager AI — Android MainActivity
 * WebView → FastAPI backend (port 8002) via JavaScript Bridge
 * Features: mood logging, sleep tracking, burnout detection, voice journal
 */
class WellnessMainActivity : AppCompatActivity() {

    private lateinit var webView: WebView
    private val httpClient = OkHttpClient()
    private val scope = CoroutineScope(Dispatchers.Main + SupervisorJob())
    private val BACKEND_URL = "http://10.0.2.2:8002"

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
        webView = findViewById(R.id.webView)

        webView.settings.apply {
            javaScriptEnabled = true
            domStorageEnabled = true
            allowFileAccess = true
            mixedContentMode = WebSettings.MIXED_CONTENT_ALWAYS_ALLOW
            useWideViewPort = true
            loadWithOverviewMode = true
        }

        webView.addJavascriptInterface(WellnessBridge(), "AndroidBridge")

        webView.webViewClient = object : WebViewClient() {
            override fun onPageFinished(view: WebView?, url: String?) {
                webView.evaluateJavascript("window.BACKEND_URL = '$BACKEND_URL';", null)
                fetchDashboard()
            }
        }
        webView.loadUrl("file:///android_asset/www/index.html")
    }

    private fun fetchDashboard() {
        scope.launch {
            try {
                val data = withContext(Dispatchers.IO) { apiGet("/dashboard") }
                webView.evaluateJavascript("if(typeof updateDashboard === 'function') updateDashboard($data);", null)
            } catch (e: Exception) { /* silent fail */ }
        }
    }

    private fun apiGet(ep: String): String {
        val r = Request.Builder().url("$BACKEND_URL$ep").get().build()
        return httpClient.newCall(r).execute().use { it.body?.string() ?: "{}" }
    }
    private fun apiPost(ep: String, body: String): String {
        val rb = body.toRequestBody("application/json".toMediaType())
        val r = Request.Builder().url("$BACKEND_URL$ep").post(rb).build()
        return httpClient.newCall(r).execute().use { it.body?.string() ?: "{}" }
    }

    inner class WellnessBridge {
        @JavascriptInterface fun logMood(score: Float, emoji: String, notes: String): String =
            runBlocking { withContext(Dispatchers.IO) { apiPost("/mood", """{"score":$score,"emoji":"$emoji","notes":"$notes"}""") } }

        @JavascriptInterface fun logSleep(hours: Float, quality: String): String =
            runBlocking { withContext(Dispatchers.IO) { apiPost("/sleep", """{"hours":$hours,"quality":"$quality"}""") } }

        @JavascriptInterface fun logWater(cups: Int): String =
            runBlocking { withContext(Dispatchers.IO) { apiPost("/water/log", """{"cups":$cups}""") } }

        @JavascriptInterface fun getBurnout(): String =
            runBlocking { withContext(Dispatchers.IO) { apiGet("/burnout") } }

        @JavascriptInterface fun analyseJournal(text: String): Unit = scope.launch {
            val result = withContext(Dispatchers.IO) { apiPost("/journal/analyse", """{"text":"${text.replace("\"","\\\"")}"}""") }
            webView.evaluateJavascript("if(typeof onJournalAnalysis === 'function') onJournalAnalysis($result);", null)
        }.let {}

        @JavascriptInterface fun getSuggestions(): String =
            runBlocking { withContext(Dispatchers.IO) { apiGet("/routines/suggest") } }

        @JavascriptInterface fun showToast(msg: String) =
            runOnUiThread { Toast.makeText(this@WellnessMainActivity, msg, Toast.LENGTH_SHORT).show() }
    }

    override fun onBackPressed() { if (webView.canGoBack()) webView.goBack() else super.onBackPressed() }
    override fun onDestroy() { scope.cancel(); super.onDestroy() }
}
