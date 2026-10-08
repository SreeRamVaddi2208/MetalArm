// Local notifications: "Rest done" and "Your streak ends tonight". An alarm
// fires NotificationReceiver at the right moment, which posts the
// notification; re-scheduling the same id replaces the pending alarm, which is
// what a restarted rest timer needs. Inexact alarms are fine for both - a rest
// alert a few seconds late is harmless and needs no exact-alarm permission.

package com.sreeram.metalarm.platform

import android.Manifest
import android.app.AlarmManager
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.SystemClock
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.ContextCompat
import com.sreeram.metalarm.MainActivity
import com.sreeram.metalarm.R
import com.sreeram.metalarm.state.LocalNotification
import com.sreeram.metalarm.state.Notifier

class AndroidNotifier(
    private val context: Context,
    /** Asks for POST_NOTIFICATIONS through the visible activity. */
    var permissionRequester: (suspend () -> Boolean)? = null,
) : Notifier {
    private val alarms = context.getSystemService(AlarmManager::class.java)

    init {
        ensureChannel(context)
    }

    override suspend fun isAuthorized(): Boolean {
        val granted = Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU ||
            ContextCompat.checkSelfPermission(context, Manifest.permission.POST_NOTIFICATIONS) == PackageManager.PERMISSION_GRANTED
        return granted && NotificationManagerCompat.from(context).areNotificationsEnabled()
    }

    override suspend fun requestAuthorization(): Boolean {
        if (isAuthorized()) return true
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU) return false
        permissionRequester?.invoke()
        // Judged by the result, not by the request returning.
        return isAuthorized()
    }

    override suspend fun schedule(notification: LocalNotification) {
        if (notification.afterSeconds <= 0) return
        val at = SystemClock.elapsedRealtime() + notification.afterSeconds * 1_000
        alarms.set(AlarmManager.ELAPSED_REALTIME_WAKEUP, at, pending(notification.id, notification))
    }

    override suspend fun cancel(ids: List<String>) {
        ids.forEach { id ->
            alarms.cancel(pending(id, null))
            NotificationManagerCompat.from(context).cancel(id.hashCode())
        }
    }

    private fun pending(id: String, notification: LocalNotification?): PendingIntent {
        val intent = Intent(context, NotificationReceiver::class.java).setAction(id)
        if (notification != null) {
            intent.putExtra(EXTRA_TITLE, notification.title).putExtra(EXTRA_BODY, notification.body)
        }
        return PendingIntent.getBroadcast(
            context, id.hashCode(), intent, PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
    }

    companion object {
        const val CHANNEL = "workout"
        const val EXTRA_TITLE = "title"
        const val EXTRA_BODY = "body"

        fun ensureChannel(context: Context) {
            val manager = context.getSystemService(NotificationManager::class.java)
            if (manager.getNotificationChannel(CHANNEL) == null) {
                manager.createNotificationChannel(
                    NotificationChannel(CHANNEL, "Workout reminders", NotificationManager.IMPORTANCE_DEFAULT).apply {
                        description = "Rest timer and streak reminders"
                    },
                )
            }
        }
    }
}

/** Posts the notification an alarm was set for. */
class NotificationReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        val id = intent.action ?: return
        if (ContextCompat.checkSelfPermission(context, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED &&
            Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU
        ) return
        AndroidNotifier.ensureChannel(context)
        val open = PendingIntent.getActivity(
            context, 0, Intent(context, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP),
            PendingIntent.FLAG_IMMUTABLE,
        )
        val notification = NotificationCompat.Builder(context, AndroidNotifier.CHANNEL)
            .setSmallIcon(R.drawable.ic_notification)
            .setContentTitle(intent.getStringExtra(AndroidNotifier.EXTRA_TITLE))
            .setContentText(intent.getStringExtra(AndroidNotifier.EXTRA_BODY))
            .setContentIntent(open)
            .setAutoCancel(true)
            .build()
        NotificationManagerCompat.from(context).notify(id.hashCode(), notification)
    }
}
