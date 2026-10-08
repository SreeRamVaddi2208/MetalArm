package com.sreeram.metalarm

import android.Manifest
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.SystemBarStyle
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.health.connect.client.PermissionController
import androidx.lifecycle.DefaultLifecycleObserver
import androidx.lifecycle.LifecycleOwner
import androidx.lifecycle.lifecycleScope
import com.sreeram.metalarm.theme.Theme
import com.sreeram.metalarm.ui.RootScreen
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.launch
import androidx.compose.ui.graphics.toArgb

class MainActivity : ComponentActivity() {
    private var notificationAnswer: CompletableDeferred<Boolean>? = null
    private var healthAnswer: CompletableDeferred<Unit>? = null

    private val askNotifications = registerForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        notificationAnswer?.complete(granted)
    }
    private val askHealth = registerForActivityResult(PermissionController.createRequestPermissionResultContract()) {
        healthAnswer?.complete(Unit)
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        enableEdgeToEdge(
            statusBarStyle = SystemBarStyle.dark(Theme.bg.toArgb()),
            navigationBarStyle = SystemBarStyle.dark(Theme.bg.toArgb()),
        )
        super.onCreate(savedInstanceState)
        val model = AppGraph.model(this)

        // Permission prompts need an activity; the notifier and Health
        // Connect writer ask through these and wait for the answer.
        AppGraph.notifier.permissionRequester = {
            val answer = CompletableDeferred<Boolean>().also { notificationAnswer = it }
            askNotifications.launch(Manifest.permission.POST_NOTIFICATIONS)
            answer.await()
        }
        AppGraph.health.permissionRequester = { permissions ->
            val answer = CompletableDeferred<Unit>().also { healthAnswer = it }
            askHealth.launch(permissions)
            answer.await()
        }

        // Back in the foreground: send anything saved offline.
        lifecycle.addObserver(object : DefaultLifecycleObserver {
            override fun onStart(owner: LifecycleOwner) {
                lifecycleScope.launch { model.flushPendingSets() }
            }
        })

        setContent { RootScreen(model) }
    }
}
