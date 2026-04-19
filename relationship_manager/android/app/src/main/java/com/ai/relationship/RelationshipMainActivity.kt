package com.ai.relationship

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
 * Relationship Manager AI — Android MainActivity
 * WebView → FastAPI backend (port 8005) via JavaScript Bridge
 * Features: Mem0 memory, AI message drafting, birthday reminders
 */
class RelationshipMainActivity : AppCompatActivity() {

    private lateinit var webView: WebView
    private val httpClient = OkHttpClient.Builder()
        .connectTimeout(30, java.util.concurrent.TimeUnit.SECONDS)
        .readTimeout(60, java.util.concurrent.TimeUnit.SECONDS)
        .build()
    private val scope = CoroutineScope(Dispatchers.Main + SupervisorJob())
    private val BACKEND_URL = "http://10.0.2.2:8005"

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
        webView.addJavascriptInterface(RelationshipBridge(), "AndroidBridge")
        webView.webViewClient = object : WebViewClient() {
            override fun onPageFinished(view: WebView?, url: String?) {
                webView.evaluateJavascript("window.BACKEND_URL = '$BACKEND_URL';", null)
                scope.launch {
                    val dash = withContext(Dispatchers.IO) { apiGet("/dashboard") }
                    webView.evaluateJavascript("if(typeof updateDashboard === 'function') updateDashboard($dash);", null)
                    val contacts = withContext(Dispatchers.IO) { apiGet("/contacts") }
                    webView.evaluateJavascript("if(typeof loadContacts === 'function') loadContacts($contacts);", null)
                }
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

    inner class RelationshipBridge {
        @JavascriptInterface fun draftMessage(contactId: String, msgType: String, extraContext: String): Unit = scope.launch {
            val body = """{"contact_id":"$contactId","message_type":"$msgType","extra_context":"${extraContext.replace("\"","\\\"")}"}"""
            val result = withContext(Dispatchers.IO) { apiPost("/message/draft", body) }
            webView.evaluateJavascript("if(typeof onMessageDraft === 'function') onMessageDraft($result);", null)
        }.let {}

        @JavascriptInterface fun getContacts(): String =
            runBlocking { withContext(Dispatchers.IO) { apiGet("/contacts") } }

        @JavascriptInterface fun getMemories(contactId: String): String =
            runBlocking { withContext(Dispatchers.IO) { apiGet("/memory/$contactId") } }

        @JavascriptInterface fun addMemory(contactId: String, fact: String, context: String): String =
            runBlocking { withContext(Dispatchers.IO) {
                apiPost("/memory", """{"contact_id":"$contactId","fact":"${fact.replace("\"","\\\"")}","context":"$context"}""")
            }}

        @JavascriptInterface fun logInteraction(contactId: String, notes: String, medium: String): String =
            runBlocking { withContext(Dispatchers.IO) {
                apiPost("/interaction/log", """{"contact_id":"$contactId","notes":"${notes.replace("\"","\\\"")}","medium":"$medium"}""")
            }}

        @JavascriptInterface fun getBirthdays(): String =
            runBlocking { withContext(Dispatchers.IO) { apiGet("/birthdays") } }

        @JavascriptInterface fun getOverdue(): String =
            runBlocking { withContext(Dispatchers.IO) { apiGet("/overdue") } }

        @JavascriptInterface fun getGiftIdeas(contactId: String, budget: String): Unit = scope.launch {
            val result = withContext(Dispatchers.IO) { apiPost("/gift-ideas", """{"contact_id":"$contactId","budget":"$budget"}""") }
            webView.evaluateJavascript("if(typeof onGiftIdeas === 'function') onGiftIdeas($result);", null)
        }.let {}

        @JavascriptInterface fun recalculateHealth(): String =
            runBlocking { withContext(Dispatchers.IO) { apiPost("/health/recalculate", "{}") } }

        @JavascriptInterface fun showToast(msg: String) =
            runOnUiThread { Toast.makeText(this@RelationshipMainActivity, msg, Toast.LENGTH_SHORT).show() }
    }

    override fun onBackPressed() { if (webView.canGoBack()) webView.goBack() else super.onBackPressed() }
    override fun onDestroy() { scope.cancel(); super.onDestroy() }
}
