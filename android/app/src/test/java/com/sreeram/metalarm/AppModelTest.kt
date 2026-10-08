package com.sreeram.metalarm

import com.sreeram.metalarm.api.ApiException
import com.sreeram.metalarm.api.ContractFixtures
import com.sreeram.metalarm.api.Exercise
import com.sreeram.metalarm.api.FinishResult
import com.sreeram.metalarm.api.Me
import com.sreeram.metalarm.api.MetalArmJson
import com.sreeram.metalarm.api.MockApi
import com.sreeram.metalarm.api.Motivation
import com.sreeram.metalarm.api.WeightUnit
import com.sreeram.metalarm.state.AppModel
import com.sreeram.metalarm.state.FinishedWorkout
import com.sreeram.metalarm.state.HealthSettings
import com.sreeram.metalarm.state.HealthWriteResult
import com.sreeram.metalarm.state.HealthWriter
import com.sreeram.metalarm.state.LocalNotification
import com.sreeram.metalarm.state.MemoryPrefs
import com.sreeram.metalarm.state.NotificationId
import com.sreeram.metalarm.state.Notifier
import com.sreeram.metalarm.state.PendingSet
import com.sreeram.metalarm.state.PendingSetStore
import com.sreeram.metalarm.state.StreakReminder
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.TestScope
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File
import java.io.IOException
import java.time.LocalDateTime
import java.time.ZoneId

/** Records what WOULD be shown. */
class SpyNotifier(var authorized: Boolean = true) : Notifier {
    var asked = 0
    val scheduled = mutableListOf<LocalNotification>()
    val cancelled = mutableListOf<String>()
    override suspend fun isAuthorized() = authorized
    override suspend fun requestAuthorization(): Boolean { asked++; return authorized }
    override suspend fun schedule(notification: LocalNotification) { scheduled += notification }
    override suspend fun cancel(ids: List<String>) { cancelled += ids }
}

/** Records what WOULD reach Health Connect. */
class SpyHealthWriter : HealthWriter {
    var available = true
    /** What the user "taps" on the permission sheet. */
    var allow = true
    /** Set independently to mimic permission revoked elsewhere. */
    var authorized: Boolean? = null
    var askedCount = 0
    val saved = mutableListOf<FinishedWorkout>()
    var result: HealthWriteResult = HealthWriteResult.Saved

    override val isAvailable get() = available
    override suspend fun isAuthorized() = authorized ?: (allow && askedCount > 0)
    override suspend fun requestAuthorization(): Boolean { askedCount++; return allow }
    override suspend fun save(workout: FinishedWorkout): HealthWriteResult {
        if (result.isSuccess) saved += workout
        return result
    }
}

/** The only way a test should make an AppModel: spies, fresh settings. */
fun TestScope.testModel(api: MockApi = MockApi(), store: PendingSetStore = PendingSetStore.inMemory) =
    AppModel(api, backgroundScope as CoroutineScope, store, MemoryPrefs(), SpyNotifier(), SpyHealthWriter())

@OptIn(ExperimentalCoroutinesApi::class)
class AppModelTest {
    private suspend fun bench(api: MockApi): Exercise = api.searchExercises("bench").first()

    @Test fun signingInThenLoadingHome() = runTest {
        val model = testModel(MockApi(signedIn = false))
        assertFalse(model.isSignedIn)
        model.signIn(" sree@metalarm.dev ", MockApi.PASSWORD)
        assertTrue(model.isSignedIn)
        model.loadHome()
        assertEquals(14, model.me?.progress?.currentLevel)
        assertEquals(185, model.points?.thisWeekPoints)
        assertFalse(model.sessionActive)
    }

    @Test fun wrongPasswordStaysSignedOut() = runTest {
        val model = testModel(MockApi(signedIn = false))
        model.signIn("sree@metalarm.dev", "wrong-password")
        assertFalse(model.isSignedIn)
        assertEquals("Couldn't sign in: Incorrect email or password", model.errorMessage)
    }

    @Test fun workoutLoopFromStartToSummary() = runTest {
        val api = MockApi()
        val model = testModel(api)
        model.startWorkout()
        assertTrue(model.sessionActive)
        assertNull(model.selectedExercise)

        model.addExercise(bench(api))
        // Prefilled from last session's first set (the ghost values).
        assertEquals("80", model.weightInput)
        assertEquals("8", model.repsInput)

        model.logSet()
        assertEquals(1, model.setsLoggedCount)
        assertTrue(model.pendingExercises.isEmpty())
        assertTrue(model.prHint.startsWith("New heaviest Barbell Bench Press: 80 kg\n"))
        assertTrue(model.prHint.split("\n")[1] in Motivation.lines)
        assertTrue(model.resting)
        assertEquals("1:30", model.restDisplay)

        model.finishWorkout()
        assertTrue(model.showingSummary)
        assertFalse(model.sessionActive)
        assertFalse(model.resting)
        assertEquals(false, model.finishResult?.qualified)
        assertEquals(0, model.finishResult?.breakdown?.sessionBonus)
        assertEquals(50, model.finishResult?.breakdown?.prBonus)
    }

    @Test fun invalidInputIsRejectedWithoutLogging() = runTest {
        val api = MockApi()
        val model = testModel(api)
        model.startWorkout()
        model.addExercise(bench(api))
        model.weightInput = "heavy"
        model.logSet()
        assertEquals("Enter a weight and a number of reps.", model.errorMessage)
        assertEquals(0, model.setsLoggedCount)
    }

    @Test fun poundsAreShownAndSentAsPounds() = runTest {
        val api = MockApi()
        val model = testModel(api)
        model.loadHome()
        model.setWeightUnit(WeightUnit.Lb)
        assertEquals(WeightUnit.Lb, model.weightUnit)
        model.startWorkout()
        model.addExercise(bench(api))
        assertEquals("176.4", model.weightInput)
        model.logSet()
        val kilograms = model.session!!.exercises.first().sets.first().weightKg
        assertEquals(80.0, kilograms, 0.05)
    }

    @Test fun startingWhileOneIsLiveResumesIt() = runTest {
        val api = MockApi()
        val model = testModel(api)
        model.startWorkout()
        val otherDevice = testModel(api)
        otherDevice.startWorkout()
        assertEquals(model.session?.id, otherDevice.session?.id)
        assertEquals("", otherDevice.errorMessage)
    }

    @Test fun discardingEndsTheWorkout() = runTest {
        val model = testModel()
        model.startWorkout()
        model.abandonWorkout()
        assertFalse(model.sessionActive)
    }

    // Offline logging

    @Test fun aSetLoggedOfflineIsQueuedAndSyncsLater() = runTest {
        val api = MockApi()
        val model = testModel(api)
        model.startWorkout()
        model.addExercise(bench(api))

        api.failure = IOException("offline")
        model.logSet()
        assertEquals(1, model.pendingSets.size)
        assertEquals("", model.errorMessage)
        assertEquals(0, model.setsLoggedCount)
        assertTrue(model.resting)

        api.failure = null
        model.flushPendingSets()
        assertTrue(model.pendingSets.isEmpty())
        assertEquals(1, model.setsLoggedCount)
    }

    @Test fun queuedSetsSyncInTheOrderTheyWereDone() = runTest {
        val api = MockApi()
        val model = testModel(api)
        model.startWorkout()
        model.addExercise(bench(api))

        api.failure = IOException("offline")
        for (weight in listOf("80", "82.5", "85")) {
            model.weightInput = weight
            model.repsInput = "5"
            model.logSet()
        }
        assertEquals(listOf(80.0, 82.5, 85.0), model.pendingSets.map { it.weight })

        api.failure = null
        model.flushPendingSets()
        assertEquals(listOf(80.0, 82.5, 85.0), model.session!!.exercises.first().sets.map { it.weightKg })
    }

    @Test fun aLostReplyIsResentWithoutLoggingTwice() = runTest {
        val api = MockApi()
        val model = testModel(api)
        model.startWorkout()
        model.addExercise(bench(api))

        api.dropNextLogSetResponse = true
        model.logSet()
        assertEquals(1, model.pendingSets.size)

        model.flushPendingSets()
        assertTrue(model.pendingSets.isEmpty())
        assertEquals(1, model.setsLoggedCount)
    }

    @Test fun finishingWaitsForQueuedSets() = runTest {
        val api = MockApi()
        val model = testModel(api)
        model.startWorkout()
        model.addExercise(bench(api))

        api.failure = IOException("offline")
        model.logSet()
        model.finishWorkout()
        assertTrue(model.sessionActive)
        assertFalse(model.showingSummary)
        assertEquals("1 set hasn't synced yet. Finish once you're back online so they count.", model.errorMessage)

        api.failure = null
        model.finishWorkout()
        assertTrue(model.showingSummary)
        assertEquals(1, model.finishResult?.session?.workingSets)
        assertTrue(model.pendingSets.isEmpty())
    }

    @Test fun aQueuedSetTheServerRejectsIsDroppedWithAMessage() = runTest {
        val api = MockApi()
        val model = testModel(api)
        model.startWorkout()
        model.addExercise(bench(api))

        api.failure = IOException("offline")
        model.logSet()
        api.failure = null
        api.abandonSession(model.session!!.id)

        model.flushPendingSets()
        assertTrue(model.pendingSets.isEmpty())
        assertEquals("A set saved offline couldn't be logged: Workout not found", model.errorMessage)
    }

    @Test fun theQueueSurvivesARelaunch() = runTest {
        val file = File.createTempFile("pending", ".json").also { it.delete() }
        val set = PendingSet.create("s1", "e1", 100.0, WeightUnit.Lb, 5)
        PendingSetStore(file).save(listOf(set))
        val relaunched = testModel(store = PendingSetStore(file))
        assertEquals(listOf(set), relaunched.pendingSets)

        // An empty queue leaves no file behind.
        PendingSetStore(file).save(emptyList())
        assertFalse(file.exists())
    }

    // Leaderboard and profile

    @Test fun theLeagueAndRaidLoad() = runTest {
        val model = testModel()
        model.loadLeague()
        assertEquals("Silver", model.league?.divisionLabel)
        assertEquals(815, model.league?.me?.points)
        model.loadParties()
        assertEquals("Iron Golem", model.partyRaid?.name)
        assertEquals(model.selectedPartyId, model.partyRaid?.partyId)
    }

    @Test fun choosingAClassHighlightsItsStats() = runTest {
        val model = testModel()
        model.loadProfile()
        assertTrue(model.characterSheet!!.stats.none { it.highlighted })
        model.chooseClass("powerlifter")
        assertEquals("Powerlifter", model.characterSheet?.classLabel)
        assertEquals(listOf("strength"), model.characterSheet!!.stats.filter { it.highlighted }.map { it.key })
        model.chooseClass("powerlifter")
        assertEquals("", model.characterSheet?.characterClass)
    }

    @Test fun partiesShowTheWeeklyBoard() = runTest {
        val model = testModel()
        model.loadParties()
        assertEquals(1, model.parties.size)
        assertEquals(true, model.partyBoard?.entries?.first()?.isMe)
        model.createParty("Leg Day Club")
        assertEquals(2, model.parties.size)
        assertEquals("Leg Day Club", model.selectedParty?.name)
        model.joinParty("nope")
        assertEquals("Couldn't join the party: No party with that invite code", model.errorMessage)
    }

    @Test fun profileLoadsTheRankTrials() = runTest {
        val model = testModel()
        model.loadProfile()
        assertEquals(listOf("B", "A", "S"), model.rankTrials.map { it.rank })
    }

    @Test fun addingAnExerciseLoadsWhatToTryNext() = runTest {
        val model = testModel()
        model.searchExercises("Bench")
        val bench = model.pickerResults.first { it.id == ContractFixtures.benchID }
        model.addExercise(bench)
        assertEquals("Try 87.5 kg x 5", model.hints[bench.id]?.text)
        assertTrue(model.ghostSets[bench.id]!!.isNotEmpty())
    }

    @Test fun importingReportsWhatLandedOrTheError() = runTest {
        val model = testModel()
        model.importWorkouts("Date,Workout Name,Exercise Name,Set Order\n")
        assertTrue(model.importSummary.startsWith("Imported 42 workouts"))
        assertEquals("", model.errorMessage)
        val other = testModel()
        other.importWorkouts("name,value\n")
        assertEquals("", other.importSummary)
        assertTrue(other.errorMessage.startsWith("Couldn't import that file"))
    }

    @Test fun progressTabsComeFromTheUsersRecords() = runTest {
        val model = testModel()
        model.loadProgress()
        assertEquals(listOf("Barbell Bench Press", "Barbell Back Squat"), model.progressTabs.map { it.name })
        assertEquals(ContractFixtures.benchID, model.selectedProgressId)
        assertEquals(4, model.history.size)
        assertTrue(model.records.all { it.exerciseId == ContractFixtures.benchID })
    }

    @Test fun deletingTheAccountNeedsThePassword() = runTest {
        val model = testModel()
        assertFalse(model.deleteAccount("guess"))
        assertEquals("Couldn't delete your account: Password is incorrect", model.errorMessage)
        assertTrue(model.isSignedIn)
        assertTrue(model.deleteAccount(MockApi.PASSWORD))
        assertFalse(model.isSignedIn)
    }

    @Test fun anExpiredSessionReturnsToSignIn() = runTest {
        val api = MockApi()
        val model = testModel(api)
        model.loadHome()
        api.expireSession()
        assertFalse(model.isSignedIn)
        assertNull(model.me)
    }

    @Test fun signedOutErrorsReadAsTheSessionEnding() = runTest {
        val api = MockApi()
        val model = testModel(api)
        api.failure = ApiException.SignedOut()
        model.loadHome()
        assertEquals("Your session has ended. Please sign in again.", model.errorMessage)
    }

    // Health Connect

    private val finished: FinishResult get() = MetalArmJson.decodeFromString(ContractFixtures.finishResult)

    @Test fun aFinishedWorkoutReachesHealthOnlyWhenAskedFor() = runTest {
        val model = testModel()
        val spy = model.healthWriter as SpyHealthWriter
        model.finishResult = finished
        model.saveToHealthIfEnabled()
        assertTrue(spy.saved.isEmpty())

        model.healthSettings = HealthSettings(enabled = true)
        model.saveToHealthIfEnabled()
        val saved = spy.saved.single()
        assertTrue(saved.volumeKg > 0)
        assertTrue(saved.end.isAfter(saved.start))
        assertEquals("", model.healthStatus)

        // The same session is never written twice.
        model.saveToHealthIfEnabled()
        assertEquals(1, spy.saved.size)
    }

    @Test fun refusingHealthLeavesTheToggleOff() = runTest {
        val model = testModel()
        val spy = model.healthWriter as SpyHealthWriter
        spy.allow = false
        model.setHealthSync(true)
        assertEquals(1, spy.askedCount)
        assertFalse(model.healthSettings.enabled)
        assertTrue(model.healthStatus.contains("Health Connect"))
    }

    @Test fun revokedPermissionTurnsTheToggleOff() = runTest {
        val model = testModel()
        val spy = model.healthWriter as SpyHealthWriter
        model.healthSettings = HealthSettings(enabled = true, asked = true)
        spy.authorized = false
        model.refreshHealthAuthorization()
        assertFalse(model.healthSettings.enabled)
    }

    @Test fun aFailedWriteIsReportedButNeverInterrupts() = runTest {
        val model = testModel()
        val spy = model.healthWriter as SpyHealthWriter
        spy.authorized = true
        spy.result = HealthWriteResult.Failed("the store was busy")
        model.finishResult = finished
        model.healthSettings = HealthSettings(enabled = true, asked = true)
        model.saveToHealthIfEnabled()
        assertTrue(model.healthStatus.contains("couldn't save"))
        assertEquals("", model.errorMessage)
        assertEquals("", model.healthSettings.lastSavedSessionId)
    }

    @Test fun turningHealthOnAsksOnce() = runTest {
        val model = testModel()
        val spy = model.healthWriter as SpyHealthWriter
        model.setHealthSync(true)
        model.setHealthSync(false)
        model.setHealthSync(true)
        assertEquals(1, spy.askedCount)
        assertTrue(model.healthSettings.enabled)
    }

    // Notifications

    @Test fun theRestTimerSchedulesAndCancelsItsAlert() = runTest {
        val model = testModel()
        val spy = model.notifier as SpyNotifier
        model.startRestTimer(90)
        runCurrent()
        assertEquals(NotificationId.REST_DONE, spy.scheduled.first().id)
        assertEquals(90L, spy.scheduled.first().afterSeconds)
        model.stopRestTimer()
        runCurrent()
        assertTrue(NotificationId.REST_DONE in spy.cancelled)
    }

    @Test fun theRestTimerCountsDown() = runTest {
        val model = testModel()
        model.startRestTimer(3)
        testScheduler.advanceTimeBy(1_500)
        assertEquals(2, model.restSecondsLeft)
        testScheduler.advanceTimeBy(2_000)
        assertFalse(model.resting)
    }

    @Test fun turningRestAlertsOffCancelsWhatIsPending() = runTest {
        val model = testModel()
        val spy = model.notifier as SpyNotifier
        model.setRestAlerts(false)
        assertTrue(NotificationId.REST_DONE in spy.cancelled)
        assertFalse(model.notificationSettings.restAlerts)
    }

    @Test fun permissionIsAskedOnceAndOnlyAfterAWorkout() = runTest {
        val model = testModel()
        val spy = model.notifier as SpyNotifier
        model.askForNotificationsAfterFirstWorkout()
        model.askForNotificationsAfterFirstWorkout()
        assertEquals(1, spy.asked)
    }

    @Test fun theStreakReminderNeedsAStreakToLose() = runTest {
        val model = testModel()
        val spy = model.notifier as SpyNotifier
        val me: Me = MetalArmJson.decodeFromString(ContractFixtures.me)
        model.me = me
        val morning = LocalDateTime.of(2026, 9, 14, 10, 0).atZone(ZoneId.systemDefault()).toInstant()
        model.refreshStreakReminder(morning)
        assertTrue(spy.scheduled.any { it.id == NotificationId.STREAK_AT_RISK })

        model.me = me.copy(progress = me.progress.copy(lastCompletedOn = AppModel.isoDay(morning)))
        model.refreshStreakReminder(morning)
        assertTrue(NotificationId.STREAK_AT_RISK in spy.cancelled)
    }

    @Test fun tonightsReminderIsOnlyScheduledWhileTheEveningIsAhead() {
        val zone = ZoneId.systemDefault()
        val morning = LocalDateTime.of(2026, 9, 14, 10, 0).atZone(zone).toInstant()
        assertEquals(9L * 3600, StreakReminder.secondsUntilTonight(morning, zone))
        val night = LocalDateTime.of(2026, 9, 14, 22, 0).atZone(zone).toInstant()
        assertNull(StreakReminder.secondsUntilTonight(night, zone))
        assertNotNull(StreakReminder.secondsUntilTonight(morning))
    }
}
