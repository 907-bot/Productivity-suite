package com.ai.finance

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
 * Finance Manager AI — Android MainActivity
 * WebView → FastAPI backend (port 8003) via JavaScript Bridge
 * Features: NL queries, Plaid sync, anomaly alerts, receipt scan
 */
class FinanceMainActivity : AppCompatActivity() {

    private lateinit var webView: WebView
    private val httpClient = OkHttpClient()
    private val scope = CoroutineScope(Dispatchers.Main + SupervisorJob())
    private val BACKEND_URL = "http://10.0.2.2:8003"

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
        webView.addJavascriptInterface(FinanceBridge(), "AndroidBridge")
        webView.webViewClient = object : WebViewClient() {
            override fun onPageFinished(view: WebView?, url: String?) {
                webView.evaluateJavascript("window.BACKEND_URL = '$BACKEND_URL';", null)
                scope.launch {
                    val dash = withContext(Dispatchers.IO) { apiGet("/dashboard") }
                    webView.evaluateJavascript("if(typeof updateDashboard === 'function') updateDashboard($dash);", null)
                }
            }
        }
        webView.loadUrl("file:///android_asset/www/index.html")
    }

    private fun apiGet(ep: String): String {
        return httpClient.newCall(Request.Builder().url("$BACKEND_URL$ep").get().build())
            .execute().use { it.body?.string() ?: "{}" }
    }
    private fun apiPost(ep: String, body: String): String {
        val rb = body.toRequestBody("application/json".toMediaType())
        return httpClient.newCall(Request.Builder().url("$BACKEND_URL$ep").post(rb).build())
            .execute().use { it.body?.string() ?: "{}" }
    }

    inner class FinanceBridge {
        @JavascriptInterface fun naturalLanguageQuery(query: String): Unit = scope.launch {
            val result = withContext(Dispatchers.IO) { apiPost("/query", """{"query":"${query.replace("\"","\\\"")}"}""") }
            webView.evaluateJavascript("if(typeof onNLAnswer === 'function') onNLAnswer($result);", null)
        }.let {}

        @JavascriptInterface fun getTransactions(limit: Int = 20): String =
            runBlocking { withContext(Dispatchers.IO) { apiGet("/transactions?limit=$limit") } }

        @JavascriptInterface fun getAnomalies(): String =
            runBlocking { withContext(Dispatchers.IO) { apiGet("/anomalies") } }

        @JavascriptInterface fun getSpendByCategory(): String =
            runBlocking { withContext(Dispatchers.IO) { apiGet("/spend/by-category") } }

        @JavascriptInterface fun getForecast(): String =
            runBlocking { withContext(Dispatchers.IO) { apiGet("/forecast/next-month") } }

        @JavascriptInterface fun getGoals(): String =
            runBlocking { withContext(Dispatchers.IO) { apiGet("/goals") } }

        @JavascriptInterface fun syncPlaid(): String =
            runBlocking { withContext(Dispatchers.IO) { apiGet("/plaid/sync") } }

        @JavascriptInterface fun showToast(msg: String) =
            runOnUiThread { Toast.makeText(this@FinanceMainActivity, msg, Toast.LENGTH_SHORT).show() }
    }

    override fun onBackPressed() { if (webView.canGoBack()) webView.goBack() else super.onBackPressed() }
    override fun onDestroy() { scope.cancel(); super.onDestroy() }
}
