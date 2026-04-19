package com.ai.content

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
 * Content Manager AI — Android MainActivity
 * WebView → FastAPI backend (port 8004) via JavaScript Bridge
 * Features: AI drafting, scheduling, article summarisation, digest
 */
class ContentMainActivity : AppCompatActivity() {

    private lateinit var webView: WebView
    private val httpClient = OkHttpClient.Builder()
        .connectTimeout(30, java.util.concurrent.TimeUnit.SECONDS)
        .readTimeout(60, java.util.concurrent.TimeUnit.SECONDS)
        .build()
    private val scope = CoroutineScope(Dispatchers.Main + SupervisorJob())
    private val BACKEND_URL = "http://10.0.2.2:8004"

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
        webView = findViewById(R.id.webView)

        webView.settings.apply {
            javaScriptEnabled = true; domStorageEnabled = true
            allowFileAccess = true; mixedContentMode = WebSettings.MIXED_CONTENT_ALWAYS_ALLOW
            useWideViewPort = true; loadWithOverviewMode = true
        }
        webView.addJavascriptInterface(ContentBridge(), "AndroidBridge")
        webView.webViewClient = object : WebViewClient() {
            override fun onPageFinished(view: WebView?, url: String?) {
                webView.evaluateJavascript("window.BACKEND_URL = '$BACKEND_URL';", null)
            }
        }
        webView.loadUrl("file:///android_asset/www/index.html")
    }

    private fun apiGet(ep: String): String =
        httpClient.newCall(Request.Builder().url("$BACKEND_URL$ep").get().build())
            .execute().use { it.body?.string() ?: "{}" }

    private fun apiPost(ep: String, body: String): String {
        val rb = body.toRequestBody("application/json".toMediaType())
        return httpClient.newCall(Request.Builder().url("$BACKEND_URL$ep").post(rb).build())
            .execute().use { it.body?.string() ?: "{}" }
    }

    inner class ContentBridge {
        @JavascriptInterface fun draftContent(topic: String, platform: String, tone: String): Unit = scope.launch {
            val body = """{"topic":"${topic.replace("\"","\\\"")}","platform":"$platform","tone":"$tone"}"""
            val result = withContext(Dispatchers.IO) { apiPost("/content/draft", body) }
            webView.evaluateJavascript("if(typeof onDraftReady === 'function') onDraftReady($result);", null)
        }.let {}

        @JavascriptInterface fun rewriteContent(content: String, platform: String, tone: String): Unit = scope.launch {
            val body = """{"content":"${content.replace("\"","\\\"")}","platform":"$platform","tone":"$tone"}"""
            val result = withContext(Dispatchers.IO) { apiPost("/content/rewrite", body) }
            webView.evaluateJavascript("if(typeof onRewriteReady === 'function') onRewriteReady($result);", null)
        }.let {}

        @JavascriptInterface fun summariseArticle(articleId: String): Unit = scope.launch {
            val result = withContext(Dispatchers.IO) { apiPost("/articles/summarise", """{"article_id":"$articleId"}""") }
            webView.evaluateJavascript("if(typeof onSummaryReady === 'function') onSummaryReady($result);", null)
        }.let {}

        @JavascriptInterface fun getDigest(): String =
            runBlocking { withContext(Dispatchers.IO) { apiGet("/digest") } }

        @JavascriptInterface fun getQueue(): String =
            runBlocking { withContext(Dispatchers.IO) { apiGet("/content/queue") } }

        @JavascriptInterface fun getAnalytics(): String =
            runBlocking { withContext(Dispatchers.IO) { apiGet("/analytics") } }

        @JavascriptInterface fun research(query: String): Unit = scope.launch {
            val result = withContext(Dispatchers.IO) { apiPost("/research", """{"query":"${query.replace("\"","\\\"")}"}""") }
            webView.evaluateJavascript("if(typeof onResearchReady === 'function') onResearchReady($result);", null)
        }.let {}

        @JavascriptInterface fun showToast(msg: String) =
            runOnUiThread { Toast.makeText(this@ContentMainActivity, msg, Toast.LENGTH_SHORT).show() }
    }

    override fun onBackPressed() { if (webView.canGoBack()) webView.goBack() else super.onBackPressed() }
    override fun onDestroy() { scope.cancel(); super.onDestroy() }
}
