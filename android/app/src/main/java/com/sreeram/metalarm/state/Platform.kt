// What AppModel needs from the phone, behind interfaces so unit tests run on
// the JVM with spies: settings storage, the offline set queue, notifications
// and Health Connect. The Android implementations live in platform/. Mirrors
// the iOS app's State/PendingSetStore.swift, Notifications.swift and
// HealthStore.swift.

package com.sreeram.metalarm.state

import com.sreeram.metalarm.api.MetalArmJson
import com.sreeram.metalarm.api.WeightUnit
import kotlinx.serialization.Serializable
import kotlinx.serialization.builtins.ListSerializer
import java.io.File
import java.time.Instant
import java.time.ZoneId
import java.time.ZonedDateTime
import java.util.UUID

// MARK: Settings storage

/** A small key-value store: SharedPreferences in the app, a map in tests. */
interface Prefs {
    fun getBoolean(key: String): Boolean?
    fun putBoolean(key: String, value: Boolean)
    fun getString(key: String): String?
    fun putString(key: String, value: String)
}

class MemoryPrefs : Prefs {
    private val values = mutableMapOf<String, Any>()
    override fun getBoolean(key: String) = values[key] as? Boolean
    override fun putBoolean(key: String, value: Boolean) { values[key] = value }
    override fun getString(key: String) = values[key] as? String
    override fun putString(key: String, value: String) { values[key] = value }
}

// MARK: The offline set queue

/**
 * A set logged while the phone had no connection (gyms often have none). It
 * keeps the client_set_id from the tap, so sending it again - even after a
 * response lost on the way back - can never log it twice.
 */
@Serializable
data class PendingSet(
    val clientSetId: String,
    val sessionId: String,
    val exerciseId: String,
    val weight: Double,
    val unit: String,
    val reps: Int,
) {
    val id: String get() = clientSetId
    val weightUnit: WeightUnit get() = WeightUnit.of(unit)
    /** For showing the queued set beside the logged ones, which are in kg. */
    val weightKg: Double get() = weightUnit.toKilograms(weight)

    companion object {
        fun create(sessionId: String, exerciseId: String, weight: Double, unit: WeightUnit, reps: Int) =
            PendingSet(UUID.randomUUID().toString(), sessionId, exerciseId, weight, unit.raw, reps)
    }
}

/** Keeps the queue in a file so it survives the app closing. With no file
 *  (tests, UI tests on the mock backend) it lives only in memory. */
class PendingSetStore(private val file: File?) {
    private val serializer = ListSerializer(PendingSet.serializer())

    fun load(): List<PendingSet> {
        val file = file ?: return emptyList()
        if (!file.exists()) return emptyList()
        return runCatching { MetalArmJson.decodeFromString(serializer, file.readText()) }.getOrDefault(emptyList())
    }

    fun save(sets: List<PendingSet>) {
        val file = file ?: return
        if (sets.isEmpty()) {
            file.delete()
        } else {
            val temp = File(file.parentFile, file.name + ".tmp")
            temp.writeText(MetalArmJson.encodeToString(serializer, sets))
            temp.renameTo(file)
        }
    }

    companion object {
        val inMemory get() = PendingSetStore(null)
    }
}

// MARK: Notifications

data class LocalNotification(val id: String, val title: String, val body: String, val afterSeconds: Long)

object NotificationId {
    const val REST_DONE = "rest-done"
    const val STREAK_AT_RISK = "streak-at-risk"
}

interface Notifier {
    /** True once the user has allowed notifications. */
    suspend fun isAuthorized(): Boolean
    /** Asks, and reports what the user chose. */
    suspend fun requestAuthorization(): Boolean
    suspend fun schedule(notification: LocalNotification)
    suspend fun cancel(ids: List<String>)
}

data class NotificationSettings(
    val restAlerts: Boolean = true,
    val streakReminders: Boolean = true,
    /** The permission prompt has already been shown, so a decline isn't re-asked. */
    val asked: Boolean = false,
) {
    fun save(prefs: Prefs) {
        prefs.putBoolean(REST, restAlerts)
        prefs.putBoolean(STREAK, streakReminders)
        prefs.putBoolean(ASKED, asked)
    }

    companion object {
        private const val REST = "notifications.restAlerts"
        private const val STREAK = "notifications.streakReminders"
        private const val ASKED = "notifications.asked"

        // Absent means "not chosen yet", and the default is on.
        fun load(prefs: Prefs) = NotificationSettings(
            restAlerts = prefs.getBoolean(REST) ?: true,
            streakReminders = prefs.getBoolean(STREAK) ?: true,
            asked = prefs.getBoolean(ASKED) ?: false,
        )
    }
}

object StreakReminder {
    /** Tonight's reminder fires at 19:00 local time. */
    const val HOUR = 19

    /** Seconds from `now` until tonight's reminder, or null once it has passed. */
    fun secondsUntilTonight(now: Instant, zone: ZoneId = ZoneId.systemDefault()): Long? {
        val local = ZonedDateTime.ofInstant(now, zone)
        val fireAt = local.withHour(HOUR).withMinute(0).withSecond(0).withNano(0)
        if (!fireAt.isAfter(local)) return null
        return fireAt.toEpochSecond() - local.toEpochSecond()
    }
}

// MARK: Health Connect

/** What a finished session looks like to Health Connect. */
data class FinishedWorkout(
    /** The MetalArm session id: the record's clientRecordId, so the same
     *  workout can never land twice. */
    val sessionId: String,
    val start: Instant,
    val end: Instant,
    val volumeKg: Double,
    val workingSets: Int,
)

sealed class HealthWriteResult {
    data object Saved : HealthWriteResult()
    data object AlreadySaved : HealthWriteResult()
    data object Unavailable : HealthWriteResult()
    data object NotAuthorized : HealthWriteResult()
    data class Failed(val reason: String) : HealthWriteResult()

    val isSuccess: Boolean get() = this == Saved || this == AlreadySaved

    val message: String
        get() = when (this) {
            Saved, AlreadySaved -> ""
            Unavailable -> "Health Connect isn't available on this phone."
            NotAuthorized -> "Health Connect hasn't allowed workouts. Change it in Health Connect › App permissions."
            is Failed -> "Health Connect couldn't save that workout: $reason"
        }
}

interface HealthWriter {
    val isAvailable: Boolean
    /** Judged from the granted permissions - never from a request returning. */
    suspend fun isAuthorized(): Boolean
    suspend fun requestAuthorization(): Boolean
    suspend fun save(workout: FinishedWorkout): HealthWriteResult
}

data class HealthSettings(
    val enabled: Boolean = false,
    val asked: Boolean = false,
    val lastSavedSessionId: String = "",
) {
    fun save(prefs: Prefs) {
        prefs.putBoolean(ENABLED, enabled)
        prefs.putBoolean(ASKED, asked)
        prefs.putString(LAST_SAVED, lastSavedSessionId)
    }

    companion object {
        private const val ENABLED = "health.enabled"
        private const val ASKED = "health.asked"
        private const val LAST_SAVED = "health.lastSavedSessionID"

        fun load(prefs: Prefs) = HealthSettings(
            enabled = prefs.getBoolean(ENABLED) ?: false,
            asked = prefs.getBoolean(ASKED) ?: false,
            lastSavedSessionId = prefs.getString(LAST_SAVED) ?: "",
        )
    }
}

/** Does nothing: for previews and the unit-test default. */
object NoopNotifier : Notifier {
    override suspend fun isAuthorized() = false
    override suspend fun requestAuthorization() = false
    override suspend fun schedule(notification: LocalNotification) {}
    override suspend fun cancel(ids: List<String>) {}
}

object UnavailableHealth : HealthWriter {
    override val isAvailable = false
    override suspend fun isAuthorized() = false
    override suspend fun requestAuthorization() = false
    override suspend fun save(workout: FinishedWorkout) = HealthWriteResult.Unavailable
}
