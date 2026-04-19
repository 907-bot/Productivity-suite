package com.ai.lifeadmin

import android.annotation.SuppressLint
import android.os.Bundle
import android.webkit.*
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import kotlinx.coroutines.*
import okhttp3.*
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject

/**
 * Life Admin Assistant — Android MainActivity
 *
 * Architecture:
 *  ┌─────────────────────────────────────────┐
 *  │  WebView (loads index.html from assets) │
 *  │  ↕ JavaScript Bridge (JavascriptInterface) │
 *  │  ↕ OkHttp → FastAPI Backend (Python)    │
 *  └─────────────────────────────────────────┘
 *
 * The FastAPI backend URL can be:
 *  - Local dev:  http://10.0.2.2:8001  (Android emulator → host machine)
 *  - Production: https://your-api.railway.app
 */
class MainActivity : AppCompatActivity() {

    private lateinit var webView: WebView
    private val httpClient = OkHttpClient()
    private val coroutineScope = CoroutineScope(Dispatchers.Main + SupervisorJob())

    // Change this to your production URL when deploying
    private val BACKEND_URL = "http://10.0.2.2:8001"

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        webView = findViewById(R.id.webView)

        configureWebView()
        loadApp()
    }

    @SuppressLint("SetJavaScriptEnabled")
    private fun configureWebView() {
        webView.settings.apply {
            javaScriptEnabled = true
            domStorageEnabled = true
            allowFileAccess = true
            allowContentAccess = true
            mixedContentMode = WebSettings.MIXED_CONTENT_ALWAYS_ALLOW
            cacheMode = WebSettings.LOAD_DEFAULT
            useWideViewPort = true
            loadWithOverviewMode = true
        }

        // JavaScript bridge — Android.call('method', 'params') from HTML/JS
        webView.addJavascriptInterface(LifeAdminBridge(), "AndroidBridge")

        webView.webViewClient = object : WebViewClient() {
            override fun onPageFinished(view: WebView?, url: String?) {
                // Inject backend URL into the WebView's JS context
                webView.evaluateJavascript(
                    "window.BACKEND_URL = '$BACKEND_URL';", null
                )
                // Fetch initial dashboard data and push to frontend
                fetchAndInjectDashboard()
            }
        }

        webView.webChromeClient = object : WebChromeClient() {
            override fun onConsoleMessage(msg: ConsoleMessage?): Boolean {
                android.util.Log.d("LifeAdmin-JS", msg?.message() ?: "")
                return true
            }
        }
    }

    private fun loadApp() {
        // Load frontend from bundled assets
        webView.loadUrl("file:///android_asset/www/index.html")
    }

    private fun fetchAndInjectDashboard() {
        coroutineScope.launch {
            try {
                val dashboard = withContext(Dispatchers.IO) { apiGet("/dashboard") }
                webView.evaluateJavascript(
                    "if(typeof updateDashboard === 'function') updateDashboard($dashboard);", null
                )
            } catch (e: Exception) {
                android.util.Log.e("LifeAdmin", "Dashboard fetch failed: ${e.message}")
            }
        }
    }

    // ── API helpers ────────────────────────────────────────────────────────────
    private fun apiGet(endpoint: String): String {
        val request = Request.Builder().url("$BACKEND_URL$endpoint").get().build()
        return httpClient.newCall(request).execute().use { it.body?.string() ?: "{}" }
    }

    private fun apiPost(endpoint: String, bodyJson: String): String {
        val body = bodyJson.toRequestBody("application/json".toMediaType())
        val request = Request.Builder().url("$BACKEND_URL$endpoint").post(body).build()
        return httpClient.newCall(request).execute().use { it.body?.string() ?: "{}" }
    }

    // ── JavaScript Bridge ──────────────────────────────────────────────────────
    inner class LifeAdminBridge {

        @JavascriptInterface
        fun chat(message: String, callback: String) {
            coroutineScope.launch {
                try {
                    val response = withContext(Dispatchers.IO) {
                        apiPost("/chat", """{"message": "${message.replace("\"", "\\\"")}"}""")
                    }
                    webView.evaluateJavascript("$callback(${JSONObject(response)})", null)
                } catch (e: Exception) {
                    webView.evaluateJavascript("$callback({reply: 'Connection error: ${e.message}'})", null)
                }
            }
        }

        @JavascriptInterface
        fun runAgent() {
            coroutineScope.launch {
                val result = withContext(Dispatchers.IO) { apiPost("/agent/run", "{}") }
                webView.evaluateJavascript(
                    "if(typeof onAgentComplete === 'function') onAgentComplete($result);", null
                )
            }
        }

        @JavascriptInterface
        fun getTasks(): String = runBlocking { withContext(Dispatchers.IO) { apiGet("/tasks") } }

        @JavascriptInterface
        fun addTask(text: String, priority: String): String = runBlocking {
            withContext(Dispatchers.IO) {
                apiPost("/tasks", """{"text": "$text", "priority": "$priority"}""")
            }
        }

        @JavascriptInterface
        fun toggleTask(taskId: String): String = runBlocking {
            withContext(Dispatchers.IO) {
                val request = Request.Builder()
                    .url("$BACKEND_URL/tasks/$taskId/toggle")
                    .patch("".toRequestBody()).build()
                httpClient.newCall(request).execute().use { it.body?.string() ?: "{}" }
            }
        }

        @JavascriptInterface
        fun getBills(): String = runBlocking { withContext(Dispatchers.IO) { apiGet("/bills") } }

        @JavascriptInterface
        fun showToast(message: String) {
            runOnUiThread { Toast.makeText(this@MainActivity, message, Toast.LENGTH_SHORT).show() }
        }

        @JavascriptInterface
        fun getBackendUrl(): String = BACKEND_URL
    }

    override fun onBackPressed() {
        if (webView.canGoBack()) webView.goBack()
        else super.onBackPressed()
    }

    override fun onDestroy() {
        coroutineScope.cancel()
        super.onDestroy()
    }
}
