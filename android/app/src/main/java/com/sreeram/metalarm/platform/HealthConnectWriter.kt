// Finished workouts written to Health Connect - the twin of the iOS app's
// Apple Health writer. WRITE ONLY: MetalArm asks to add exercise sessions and
// never to read anything. Nothing is written until the user turns it on.
//
// The lesson carried over from iOS: a permission request returning says
// nothing about the answer. Authorization is judged from the granted
// permissions and nothing else.

package com.sreeram.metalarm.platform

import android.content.Context
import androidx.health.connect.client.HealthConnectClient
import androidx.health.connect.client.permission.HealthPermission
import androidx.health.connect.client.records.ExerciseSessionRecord
import androidx.health.connect.client.records.metadata.Metadata
import com.sreeram.metalarm.state.FinishedWorkout
import com.sreeram.metalarm.state.HealthWriteResult
import com.sreeram.metalarm.state.HealthWriter
import java.time.ZoneId

class HealthConnectWriter(
    private val context: Context,
    /** Shows Health Connect's permission screen through the visible activity. */
    var permissionRequester: (suspend (Set<String>) -> Unit)? = null,
) : HealthWriter {
    private val permission = HealthPermission.getWritePermission(ExerciseSessionRecord::class)

    override val isAvailable: Boolean
        get() = HealthConnectClient.getSdkStatus(context) == HealthConnectClient.SDK_AVAILABLE

    private val client: HealthConnectClient? get() = if (isAvailable) HealthConnectClient.getOrCreate(context) else null

    override suspend fun isAuthorized(): Boolean {
        val client = client ?: return false
        return permission in client.permissionController.getGrantedPermissions()
    }

    override suspend fun requestAuthorization(): Boolean {
        if (!isAvailable) return false
        permissionRequester?.invoke(setOf(permission))
        return isAuthorized()
    }

    override suspend fun save(workout: FinishedWorkout): HealthWriteResult {
        val client = client ?: return HealthWriteResult.Unavailable
        if (!isAuthorized()) return HealthWriteResult.NotAuthorized
        if (!workout.end.isAfter(workout.start)) return HealthWriteResult.Failed("the session has no duration")
        val zone = ZoneId.systemDefault().rules
        val record = ExerciseSessionRecord(
            startTime = workout.start,
            startZoneOffset = zone.getOffset(workout.start),
            endTime = workout.end,
            endZoneOffset = zone.getOffset(workout.end),
            exerciseType = ExerciseSessionRecord.EXERCISE_TYPE_STRENGTH_TRAINING,
            title = "MetalArm workout",
            notes = "${workout.workingSets} working sets · ${workout.volumeKg.toInt()} kg lifted",
            // The session id: the same workout can never land twice.
            metadata = Metadata.manualEntry(clientRecordId = workout.sessionId),
        )
        return try {
            client.insertRecords(listOf(record))
            HealthWriteResult.Saved
        } catch (error: Exception) {
            HealthWriteResult.Failed(error.message ?: "unknown error")
        }
    }
}
