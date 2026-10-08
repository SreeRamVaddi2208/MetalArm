// App-wide state - the Android twin of the iOS app's State/AppModel.swift and
// AppModel+Library.swift. Mirrors the behaviour rules in docs/workouts-api.md:
// rehydrate the live workout on load, send a fresh client_set_id per tap,
// celebrate from the response, and never compute points on the device.
//
// Plain Compose snapshot state (`mutableStateOf`), like an @Observable class:
// screens read the properties and recompose when they change.

package com.sreeram.metalarm.state

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import com.sreeram.metalarm.api.ApiException
import com.sreeram.metalarm.api.CharacterSheet
import com.sreeram.metalarm.api.Exercise
import com.sreeram.metalarm.api.FinishResult
import com.sreeram.metalarm.api.HistoryPoint
import com.sreeram.metalarm.api.League
import com.sreeram.metalarm.api.LibraryFilters
import com.sreeram.metalarm.api.LibraryHome
import com.sreeram.metalarm.api.LibraryProgram
import com.sreeram.metalarm.api.LibraryProgramCard
import com.sreeram.metalarm.api.LibraryWorkout
import com.sreeram.metalarm.api.LibraryWorkoutCard
import com.sreeram.metalarm.api.Me
import com.sreeram.metalarm.api.MetalArmApi
import com.sreeram.metalarm.api.Party
import com.sreeram.metalarm.api.PartyBoard
import com.sreeram.metalarm.api.PartyRaid
import com.sreeram.metalarm.api.PointsSummary
import com.sreeram.metalarm.api.Profile
import com.sreeram.metalarm.api.ProgressionHint
import com.sreeram.metalarm.api.RankTrial
import com.sreeram.metalarm.api.SessionExercise
import com.sreeram.metalarm.api.SetLogResult
import com.sreeram.metalarm.api.TrainingPath
import com.sreeram.metalarm.api.WeightUnit
import com.sreeram.metalarm.api.WorkoutRecord
import com.sreeram.metalarm.api.WorkoutSession
import com.sreeram.metalarm.api.WorkoutSet
import com.sreeram.metalarm.api.celebrated
import com.sreeram.metalarm.api.formatNumber
import com.sreeram.metalarm.api.httpStatus
import com.sreeram.metalarm.api.isConnectivityFailure
import com.sreeram.metalarm.api.parseServerDate
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import java.time.Instant
import java.time.ZoneId
import java.util.TimeZone
import kotlin.coroutines.cancellation.CancellationException

class AppModel(
    val api: MetalArmApi,
    /** Runs the rest timer and fire-and-forget work. The app's main scope;
     *  a test's backgroundScope. */
    private val scope: CoroutineScope,
    private val pendingStore: PendingSetStore = PendingSetStore.inMemory,
    private val prefs: Prefs = MemoryPrefs(),
    var notifier: Notifier = NoopNotifier,
    var healthWriter: HealthWriter = UnavailableHealth,
) {
    data class ProgressTab(val id: String, val name: String)

    var isSignedIn by mutableStateOf(api.isSignedIn)
        private set
    var notificationSettings by mutableStateOf(NotificationSettings.load(prefs))
    var healthSettings by mutableStateOf(HealthSettings.load(prefs))
    /** Why the last Health write didn't land, shown under the toggle. */
    var healthStatus by mutableStateOf("")

    // Home
    var me by mutableStateOf<Me?>(null)
    var points by mutableStateOf<PointsSummary?>(null)

    // Workout
    var session by mutableStateOf<WorkoutSession?>(null)
    /** Chosen in the picker but with no set logged yet, so not on the server. */
    var pendingExercises by mutableStateOf<List<Exercise>>(emptyList())
    var ghostSets by mutableStateOf<Map<String, List<WorkoutSet>>>(emptyMap())
    var hints by mutableStateOf<Map<String, ProgressionHint?>>(emptyMap())
    var selectedExerciseId by mutableStateOf<String?>(null)
    var weightInput by mutableStateOf("")
    var repsInput by mutableStateOf("")
    var prHint by mutableStateOf("")
    var trainingPaths by mutableStateOf<List<TrainingPath>>(emptyList())
    var progressionHint by mutableStateOf("")
    var restSecondsLeft by mutableStateOf(0)
    var pickerResults by mutableStateOf<List<Exercise>>(emptyList())
    var finishResult by mutableStateOf<FinishResult?>(null)
    var showingSummary by mutableStateOf(false)
    /** Logged with no connection; sent in order once the network is back. */
    var pendingSets by mutableStateOf(pendingStore.load())
        private set

    // Progress
    var progressTabs by mutableStateOf<List<ProgressTab>>(emptyList())
    var selectedProgressId by mutableStateOf<String?>(null)
    var history by mutableStateOf<List<HistoryPoint>>(emptyList())
    var records by mutableStateOf<List<WorkoutRecord>>(emptyList())

    // Leaderboard
    var parties by mutableStateOf<List<Party>>(emptyList())
    var selectedPartyId by mutableStateOf<String?>(null)
    var partyBoard by mutableStateOf<PartyBoard?>(null)
    var partyRaid by mutableStateOf<PartyRaid?>(null)
    var league by mutableStateOf<League?>(null)

    // Profile
    var profile by mutableStateOf<Profile?>(null)
    var rankTrials by mutableStateOf<List<RankTrial>>(emptyList())
    var characterSheet by mutableStateOf<CharacterSheet?>(null)
    /** The last Strong or Hevy import's result, shown once then cleared. */
    var importSummary by mutableStateOf("")

    // Library: the tab's home, the open path's lists, and the open detail.
    // Recommendations and order are always the server's.
    var libraryHome by mutableStateOf<LibraryHome?>(null)
    var libraryPrograms by mutableStateOf<List<LibraryProgramCard>>(emptyList())
    var libraryWorkouts by mutableStateOf<List<LibraryWorkoutCard>>(emptyList())
    var libraryFilters by mutableStateOf(LibraryFilters())
    var libraryProgram by mutableStateOf<LibraryProgram?>(null)
    var libraryWorkout by mutableStateOf<LibraryWorkout?>(null)
    var libraryNotice by mutableStateOf("")

    var errorMessage by mutableStateOf("")
    var isBusy by mutableStateOf(false)

    private var restJob: Job? = null
    private var isFlushing = false

    init {
        api.onSignedOut = { resetAfterSignOut() }
    }

    // MARK: Derived values

    /** The party to invite friends into from a share card. */
    val shareInviteCode: String?
        get() = parties.firstOrNull { it.id == selectedPartyId }?.inviteCode ?: parties.firstOrNull()?.inviteCode

    val weightUnit: WeightUnit get() = WeightUnit.of(me?.weightUnit ?: profile?.user?.weightUnit)
    val sessionActive: Boolean get() = session != null
    val resting: Boolean get() = restSecondsLeft > 0

    val restDisplay: String
        get() {
            val seconds = maxOf(0, restSecondsLeft)
            return "%d:%02d".format(seconds / 60, seconds % 60)
        }

    /** Exercises on the workout board: those on the session, then ones just added. */
    val workoutExercises: List<Exercise>
        get() {
            val logged = session?.exercises?.map { it.exercise }.orEmpty()
            return logged + pendingExercises.filter { pending -> logged.none { it.id == pending.id } }
        }

    val selectedExercise: Exercise? get() = workoutExercises.firstOrNull { it.id == selectedExerciseId }

    val selectedSessionExercise: SessionExercise?
        get() = session?.exercises?.firstOrNull { it.exercise.id == selectedExerciseId }

    /** Last session's sets for the selected exercise - the ghost values. */
    val selectedPreviousSets: List<WorkoutSet>
        get() {
            val id = selectedExerciseId ?: return emptyList()
            val fromSession = selectedSessionExercise?.previousSets.orEmpty()
            return fromSession.ifEmpty { ghostSets[id].orEmpty() }
        }

    val selectedHint: ProgressionHint?
        get() {
            val id = selectedExerciseId ?: return null
            return selectedSessionExercise?.hint ?: hints[id]
        }

    val setsLoggedCount: Int get() = session?.exercises?.sumOf { it.sets.size } ?: 0
    val selectedParty: Party? get() = parties.firstOrNull { it.id == selectedPartyId }

    // MARK: Account

    suspend fun signIn(email: String, password: String) {
        run("Couldn't sign in") {
            api.signIn(email.trim(), password)
            isSignedIn = true
        }
    }

    suspend fun signUp(email: String, password: String, displayName: String) {
        run("Couldn't create your account") {
            api.signUp(email.trim(), password, displayName.trim(), TimeZone.getDefault().id)
            isSignedIn = true
        }
    }

    /** Signs out at once; telling the server happens afterwards. */
    suspend fun signOut() {
        resetAfterSignOut()
        api.signOut()
    }

    suspend fun signOutEverywhere() {
        var succeeded = false
        run("Couldn't sign out of other devices") {
            api.signOutEverywhere()
            succeeded = true
        }
        if (succeeded) resetAfterSignOut()
    }

    /** Returns whether the account was deleted. */
    suspend fun deleteAccount(password: String): Boolean {
        var deleted = false
        run("Couldn't delete your account") {
            api.deleteAccount(password)
            deleted = true
        }
        if (deleted) resetAfterSignOut()
        return deleted
    }

    private fun resetAfterSignOut() {
        isSignedIn = false
        me = null
        points = null
        profile = null
        rankTrials = emptyList()
        characterSheet = null
        clearWorkout()
        pendingSets = emptyList()
        pendingStore.save(emptyList())
        ghostSets = emptyMap()
        hints = emptyMap()
        finishResult = null
        showingSummary = false
        progressTabs = emptyList()
        selectedProgressId = null
        history = emptyList()
        records = emptyList()
        parties = emptyList()
        selectedPartyId = null
        partyBoard = null
        partyRaid = null
        league = null
        libraryHome = null
        libraryPrograms = emptyList()
        libraryWorkouts = emptyList()
        libraryFilters = LibraryFilters()
        libraryProgram = null
        libraryWorkout = null
        libraryNotice = ""
        scope.launch { notifier.cancel(listOf(NotificationId.REST_DONE, NotificationId.STREAK_AT_RISK)) }
    }

    // MARK: Home

    suspend fun loadHome() {
        run("Couldn't load your stats") {
            me = api.me()
            points = api.points()
            session = api.activeSession()
        }
        if (selectedExercise == null) selectDefaultExercise()
    }

    // MARK: Workout

    suspend fun loadWorkout() {
        run("Couldn't load your workout") {
            session = api.activeSession()
        }
        if (selectedExercise == null) selectDefaultExercise()
        flushPendingSets()
    }

    suspend fun startWorkout() {
        run("Couldn't start a workout") {
            session = try {
                api.startSession(null)
            } catch (error: ApiException) {
                // One is already live (started on another device): resume it.
                if (error.httpStatus == 409) api.activeSession() else throw error
            }
            pendingExercises = emptyList()
            prHint = ""
            progressionHint = ""
            stopRestTimer()
        }
        selectDefaultExercise()
    }

    suspend fun searchExercises(query: String) {
        run("Couldn't search exercises") {
            pickerResults = api.searchExercises(query)
        }
    }

    suspend fun addExercise(exercise: Exercise) {
        if (workoutExercises.none { it.id == exercise.id }) pendingExercises = pendingExercises + exercise
        if (exercise.id !in ghostSets) {
            runCatching { api.lastPerformance(exercise.id) }.getOrNull()?.let { last ->
                ghostSets = ghostSets + (exercise.id to last.sets)
                hints = hints + (exercise.id to last.hint)
            }
        }
        select(exercise.id)
    }

    fun select(exerciseId: String) {
        selectedExerciseId = exerciseId
        prefillInputs()
    }

    /** The first exercise still owed sets, so a Library workout opens on its
     *  first movement; else the latest one added. */
    fun selectDefaultExercise() {
        val owed = session?.exercises?.firstOrNull(::owesSets)
        val id = owed?.exercise?.id ?: session?.exercises?.lastOrNull()?.exercise?.id ?: pendingExercises.lastOrNull()?.id
        if (id != null) select(id) else selectedExerciseId = null
    }

    private fun workingSets(card: SessionExercise) = card.sets.count { !it.isWarmup }

    /** Under its plan, or untouched when it has none. */
    private fun owesSets(card: SessionExercise): Boolean {
        val planned = card.target?.targetSets
        return if (planned != null && planned > 0) workingSets(card) < planned else card.sets.isEmpty()
    }

    /** After a set: within a superset, on to the partner that is behind; once
     *  an exercise has done its plan, on to the next one still owed sets. The
     *  same rule as the web (state/workout.py `_advance`) and iOS. */
    private fun advanceFocus(exerciseId: String) {
        val cards = session?.exercises ?: return
        val index = cards.indexOfFirst { it.exercise.id == exerciseId }
        if (index < 0) return
        val card = cards[index]
        val group = card.supersetGroup
        if (group != null && group > 0) {
            val members = cards.indices.filter { cards[it].supersetGroup == group }
            val at = members.indexOf(index)
            if (at >= 0) {
                val rotated = members.drop(at + 1) + members.take(at + 1)
                val next = rotated.firstOrNull { owesSets(cards[it]) && workingSets(cards[it]) <= workingSets(card) }
                if (next != null) {
                    select(cards[next].exercise.id)
                    return
                }
            }
        }
        val planned = card.target?.targetSets
        if (planned != null && planned > 0 && workingSets(card) < planned) return
        cards.drop(index + 1).firstOrNull(::owesSets)?.let { select(it.exercise.id) }
    }

    /** This session's last set, else last time's, else the plan's reps with no
     *  weight (a Library workout carries no weights). */
    private fun prefillInputs() {
        val reference = selectedSessionExercise?.sets?.lastOrNull() ?: selectedPreviousSets.firstOrNull()
        if (reference == null) {
            weightInput = ""
            val target = selectedSessionExercise?.target
            repsInput = (target?.targetRepsLow ?: target?.targetReps)?.toString() ?: ""
            return
        }
        weightInput = formatNumber(weightUnit.fromKilograms(reference.weightKg))
        repsInput = reference.reps?.toString() ?: ""
    }

    /** The steppers: weight by the unit's plate step, reps by one. */
    fun bumpWeight(direction: Int) {
        val step = if (weightUnit == WeightUnit.Kg) 2.5 else 5.0
        val current = weightInput.trim().replace(',', '.').toDoubleOrNull() ?: 0.0
        weightInput = formatNumber(maxOf(0.0, current + step * direction))
    }

    fun bumpReps(direction: Int) {
        repsInput = maxOf(1, (repsInput.trim().toIntOrNull() ?: 0) + direction).toString()
    }

    suspend fun logSet() {
        val current = session
        val exercise = selectedExercise
        if (current == null || exercise == null) {
            errorMessage = "Add an exercise first."
            return
        }
        val weight = weightInput.trim().replace(',', '.').toDoubleOrNull()
        val reps = repsInput.trim().toIntOrNull()
        if (weight == null || weight < 0 || reps == null || reps <= 0) {
            errorMessage = "Enter a weight and a number of reps."
            return
        }
        // One id per tap: a retry of this same set can never log it twice.
        val set = PendingSet.create(current.id, exercise.id, weight, weightUnit, reps)
        val rest = selectedSessionExercise?.target?.restSeconds ?: DEFAULT_REST_SECONDS

        // Sets already waiting go first, so the server gets them in order.
        if (pendingSets.isNotEmpty()) {
            queue(set)
            startRestTimer(rest)
            flushPendingSets()
            return
        }

        isBusy = true
        try {
            val result = send(set)
            prHint = result.prEvents.celebrated?.let { "${it.headline(weightUnit)}\n${it.motivation}" } ?: ""
            progressionHint = result.progression.hint
            session = api.session(current.id)
            pendingExercises = pendingExercises.filter { it.id != exercise.id }
            errorMessage = ""
            startRestTimer(selectedSessionExercise?.target?.restSeconds ?: rest)
            advanceFocus(exercise.id)
        } catch (error: CancellationException) {
            throw error
        } catch (error: Exception) {
            when {
                // No answer: keep the set and send it when the network is back.
                error.isConnectivityFailure -> {
                    queue(set)
                    errorMessage = ""
                    startRestTimer(rest)
                }
                error is ApiException.SignedOut -> errorMessage = error.message ?: ""
                else -> errorMessage = "Couldn't log that set: ${error.message}"
            }
        } finally {
            isBusy = false
        }
    }

    /** Sets saved offline for this exercise in the current workout. */
    fun queuedSets(exerciseId: String): List<PendingSet> =
        pendingSets.filter { it.sessionId == session?.id && it.exerciseId == exerciseId }

    val syncStatusText: String
        get() = if (pendingSets.size == 1) "1 set saved offline. It'll sync when you're back online."
        else "${pendingSets.size} sets saved offline. They'll sync when you're back online."

    /** Sends queued sets in order. Stops at the first that still can't reach
     *  the server; drops (and reports) any the server rejects. */
    suspend fun flushPendingSets() {
        if (isFlushing || pendingSets.isEmpty()) return
        isFlushing = true
        try {
            var sentAny = false
            val rejections = mutableListOf<String>()
            while (pendingSets.isNotEmpty()) {
                val next = pendingSets.first()
                try {
                    val result = send(next)
                    sentAny = true
                    result.prEvents.celebrated?.let { prHint = "${it.headline(weightUnit)}\n${it.motivation}" }
                    progressionHint = result.progression.hint
                } catch (error: CancellationException) {
                    throw error
                } catch (error: Exception) {
                    if (error.isConnectivityFailure || error is ApiException.SignedOut) break
                    rejections += error.message ?: "Unknown error"
                }
                pendingSets = pendingSets.drop(1)
                pendingStore.save(pendingSets)
            }
            rejections.firstOrNull()?.let { first ->
                errorMessage = if (rejections.size == 1) "A set saved offline couldn't be logged: $first"
                else "${rejections.size} sets saved offline couldn't be logged: $first"
            }
            val current = session
            if (sentAny && current != null) {
                runCatching { api.session(current.id) }.getOrNull()?.let { session = it }
                val logged = session?.exercises?.map { it.exercise.id }.orEmpty().toSet()
                pendingExercises = pendingExercises.filter { it.id !in logged }
            }
        } finally {
            isFlushing = false
        }
    }

    private suspend fun send(set: PendingSet): SetLogResult = api.logSet(
        set.sessionId, set.exerciseId, set.weight, set.weightUnit, set.reps, java.util.UUID.fromString(set.clientSetId),
    )

    private fun queue(set: PendingSet) {
        pendingSets = pendingSets + set
        pendingStore.save(pendingSets)
    }

    suspend fun finishWorkout() {
        val current = session ?: return
        // Queued sets have to reach the server first, or they wouldn't count.
        flushPendingSets()
        val unsynced = pendingSets.count { it.sessionId == current.id }
        if (unsynced > 0) {
            errorMessage = "$unsynced ${if (unsynced == 1) "set hasn't" else "sets haven't"} synced yet. " +
                "Finish once you're back online so they count."
            return
        }
        run("Couldn't finish the workout") {
            finishResult = api.finishSession(current.id)
            clearWorkout()
            // The share card carries the party invite code.
            if (parties.isEmpty()) runCatching { api.parties() }.getOrNull()?.let { loaded -> parties = loaded.filter { it.isActive } }
            showingSummary = true
        }
        refreshStats()
        askForNotificationsAfterFirstWorkout()
        refreshStreakReminder()
        saveToHealthIfEnabled()
    }

    /** Adds the finished workout to Health Connect, if the user asked for it.
     *  Never interrupts: a problem goes to `healthStatus`, shown in Profile. */
    suspend fun saveToHealthIfEnabled() {
        if (!healthSettings.enabled) return
        val summary = finishResult?.session ?: return
        val start = parseServerDate(summary.startedAt) ?: return
        val end = summary.endedAt?.let(::parseServerDate) ?: return
        // A repeated finish must not put the same workout in twice.
        if (healthSettings.lastSavedSessionId == summary.id) return
        val result = healthWriter.save(FinishedWorkout(summary.id, start, end, summary.totalVolumeKg, summary.workingSets))
        healthStatus = result.message
        if (result.isSuccess) {
            updateHealth(healthSettings.copy(lastSavedSessionId = summary.id))
        } else if (result == HealthWriteResult.NotAuthorized) {
            // Permission was revoked; stop claiming it is on.
            updateHealth(healthSettings.copy(enabled = false))
        }
    }

    /** Turning it on asks for permission the first time - never at launch -
     *  and only switches on if the user ACTUALLY allowed it. */
    suspend fun setHealthSync(on: Boolean) {
        if (!on) {
            updateHealth(healthSettings.copy(enabled = false))
            healthStatus = ""
            return
        }
        if (!healthWriter.isAvailable) {
            healthStatus = HealthWriteResult.Unavailable.message
            return
        }
        var granted = healthWriter.isAuthorized()
        if (!granted && !healthSettings.asked) {
            updateHealth(healthSettings.copy(asked = true))
            granted = healthWriter.requestAuthorization()
        }
        if (!granted) {
            updateHealth(healthSettings.copy(enabled = false))
            healthStatus = HealthWriteResult.NotAuthorized.message
            return
        }
        updateHealth(healthSettings.copy(enabled = true))
        healthStatus = ""
    }

    /** Keeps the toggle honest when permission is revoked elsewhere. */
    suspend fun refreshHealthAuthorization() {
        if (!healthSettings.enabled || !healthWriter.isAvailable) return
        if (!healthWriter.isAuthorized()) {
            updateHealth(healthSettings.copy(enabled = false))
            healthStatus = HealthWriteResult.NotAuthorized.message
        }
    }

    private fun updateHealth(settings: HealthSettings) {
        healthSettings = settings
        settings.save(prefs)
    }

    suspend fun abandonWorkout() {
        val current = session ?: return
        run("Couldn't discard the workout") {
            api.abandonSession(current.id)
            // A discarded workout's queued sets have nowhere to go.
            pendingSets = pendingSets.filter { it.sessionId != current.id }
            pendingStore.save(pendingSets)
            clearWorkout()
        }
        refreshStats()
    }

    private suspend fun refreshStats() {
        runCatching { api.me() }.getOrNull()?.let { me = it }
        runCatching { api.points() }.getOrNull()?.let { points = it }
    }

    private fun clearWorkout() {
        session = null
        pendingExercises = emptyList()
        selectedExerciseId = null
        weightInput = ""
        repsInput = ""
        prHint = ""
        progressionHint = ""
        stopRestTimer()
    }

    fun startRestTimer(seconds: Int = DEFAULT_REST_SECONDS) {
        restJob?.cancel()
        restSecondsLeft = seconds
        // The in-app timer is the real one; the alert matters once the app is
        // in the background, and re-using the id replaces any pending one.
        if (notificationSettings.restAlerts) {
            scope.launch {
                if (notifier.isAuthorized()) {
                    notifier.schedule(LocalNotification(NotificationId.REST_DONE, "Rest done", "Time for your next set.", seconds.toLong()))
                }
            }
        }
        restJob = scope.launch {
            while (isActive && restSecondsLeft > 0) {
                delay(1_000)
                restSecondsLeft = maxOf(0, restSecondsLeft - 1)
            }
        }
    }

    fun stopRestTimer() {
        restJob?.cancel()
        restJob = null
        restSecondsLeft = 0
        scope.launch { notifier.cancel(listOf(NotificationId.REST_DONE)) }
    }

    /** Asked AFTER the first finished workout, never at launch. */
    suspend fun askForNotificationsAfterFirstWorkout() {
        if (notificationSettings.asked) return
        updateNotifications(notificationSettings.copy(asked = true))
        notifier.requestAuthorization()
    }

    /** "Your streak ends tonight" - only with a streak to lose and today not
     *  trained yet. Anything else cancels what is pending. */
    suspend fun refreshStreakReminder(now: Instant = Instant.now()) {
        val streak = me?.progress?.currentStreak ?: 0
        val trainedToday = me?.progress?.lastCompletedOn == isoDay(now)
        val after = StreakReminder.secondsUntilTonight(now)
        if (!notificationSettings.streakReminders || streak <= 0 || trainedToday || after == null || !notifier.isAuthorized()) {
            notifier.cancel(listOf(NotificationId.STREAK_AT_RISK))
            return
        }
        notifier.schedule(
            LocalNotification(
                NotificationId.STREAK_AT_RISK, "Your streak ends tonight",
                "A workout today keeps your $streak-day streak alive.", after,
            ),
        )
    }

    suspend fun setRestAlerts(on: Boolean) {
        updateNotifications(notificationSettings.copy(restAlerts = on))
        if (!on) notifier.cancel(listOf(NotificationId.REST_DONE))
    }

    suspend fun setStreakReminders(on: Boolean) {
        updateNotifications(notificationSettings.copy(streakReminders = on))
        refreshStreakReminder()
    }

    private fun updateNotifications(settings: NotificationSettings) {
        notificationSettings = settings
        settings.save(prefs)
    }

    // MARK: Progress

    suspend fun loadProgress() {
        run("Couldn't load progress") {
            val tabs = mutableListOf<ProgressTab>()
            for (record in api.records(null)) {
                if (tabs.none { it.id == record.exerciseId }) tabs += ProgressTab(record.exerciseId, record.exerciseName)
            }
            if (tabs.isEmpty()) {
                for (name in STARTER_EXERCISES) {
                    api.searchExercises(name).firstOrNull { it.name == name }?.let { tabs += ProgressTab(it.id, it.name) }
                }
            }
            progressTabs = tabs
        }
        val keep = progressTabs.any { it.id == selectedProgressId }
        val id = if (keep) selectedProgressId else progressTabs.firstOrNull()?.id
        if (id != null) selectProgress(id)
    }

    suspend fun selectProgress(exerciseId: String) {
        selectedProgressId = exerciseId
        run("Couldn't load progress") {
            history = api.exerciseHistory(exerciseId)
            records = api.records(exerciseId)
        }
    }

    // MARK: Leaderboard

    suspend fun loadParties() {
        run("Couldn't load your parties") {
            parties = api.parties().filter { it.isActive }
            if (parties.none { it.id == selectedPartyId }) selectedPartyId = parties.firstOrNull()?.id
            partyBoard = selectedPartyId?.let { api.partyLeaderboard(it) }
        }
        loadRaid()
    }

    /** This week's party boss. A raid that fails to load hides its card. */
    suspend fun loadRaid() {
        val partyId = selectedPartyId
        partyRaid = if (partyId == null) null else runCatching { api.partyRaid(partyId) }.getOrNull()
    }

    suspend fun selectParty(partyId: String) {
        selectedPartyId = partyId
        run("Couldn't load the leaderboard") { partyBoard = api.partyLeaderboard(partyId) }
        loadRaid()
    }

    suspend fun createParty(name: String) {
        if (name.isBlank()) {
            errorMessage = "Give the party a name."
            return
        }
        var created: Party? = null
        run("Couldn't create the party") { created = api.createParty(name.trim()) }
        created?.let {
            selectedPartyId = it.id
            loadParties()
        }
    }

    suspend fun joinParty(inviteCode: String) {
        if (inviteCode.isBlank()) {
            errorMessage = "Enter an invite code."
            return
        }
        var joined: Party? = null
        run("Couldn't join the party") { joined = api.joinParty(inviteCode.trim().uppercase()) }
        joined?.let {
            selectedPartyId = it.id
            loadParties()
        }
    }

    /** This week's league. Asking is what enters the user into the week. */
    suspend fun loadLeague() {
        league = runCatching { api.league() }.getOrNull()
    }

    // MARK: Profile

    suspend fun loadProfile() {
        run("Couldn't load your profile") { profile = api.profile() }
        refreshHealthAuthorization()
        // Secondary to the profile itself: a failure leaves the last ones shown.
        runCatching { api.rankTrials() }.getOrNull()?.let { rankTrials = it }
        runCatching { api.character() }.getOrNull()?.let { characterSheet = it }
    }

    /** Imports a Strong or Hevy CSV export, then reloads what it moved. */
    suspend fun importWorkouts(csv: String) {
        run("Couldn't import that file") {
            importSummary = api.importWorkouts(csv, weightUnit).summary
            me = api.me()
            profile = api.profile()
        }
        runCatching { api.rankTrials() }.getOrNull()?.let { rankTrials = it }
    }

    /** Pick a class, or tap the current one again to clear it. Cosmetic: it
     *  changes which stats are highlighted and nothing else. */
    suspend fun chooseClass(value: String) {
        val next = if (characterSheet?.characterClass == value) "" else value
        run("Couldn't change your class") {
            me = api.updateCharacterClass(next)
            characterSheet = api.character()
        }
    }

    // MARK: Training path

    /** Asked once, right after signing up. Null `characterClassSetAt` means
     *  never asked; a user who skipped has a timestamp and an empty path. */
    val needsTrainingPath: Boolean get() = isSignedIn && me != null && me?.characterClassSetAt == null

    suspend fun loadTrainingPaths() {
        if (trainingPaths.isNotEmpty()) return
        // The cards fall back to their built-in copy rather than showing nothing.
        trainingPaths = runCatching { api.trainingPaths() }.getOrDefault(emptyList())
    }

    /** Commits the choice. An empty value means "skip". */
    suspend fun chooseTrainingPath(category: String): Boolean {
        var saved = false
        run("Couldn't save your training path") {
            me = api.updateCharacterClass(category)
            characterSheet = runCatching { api.character() }.getOrNull()
            saved = true
        }
        return saved
    }

    suspend fun setWeightUnit(unit: WeightUnit) {
        if (unit == weightUnit) return
        run("Couldn't change the weight unit") {
            me = api.updateWeightUnit(unit)
            profile = api.profile()
        }
        prefillInputs()
    }

    // MARK: Library

    suspend fun loadLibraryHome() {
        run("Couldn't load the Library") { libraryHome = api.libraryHome() }
    }

    /** One path's programs and workouts, with the current filters. */
    suspend fun loadLibraryPath(category: String) {
        run("Couldn't load this path") {
            libraryPrograms = api.libraryPrograms(category, libraryFilters)
            libraryWorkouts = api.libraryWorkouts(category, libraryFilters)
        }
    }

    suspend fun loadLibraryProgram(slug: String) {
        if (libraryProgram?.slug != slug) libraryProgram = null
        run("Couldn't load this program") { libraryProgram = api.libraryProgram(slug) }
    }

    suspend fun loadLibraryWorkout(slug: String) {
        if (libraryWorkout?.slug != slug) libraryWorkout = null
        run("Couldn't load this workout") { libraryWorkout = api.libraryWorkout(slug) }
    }

    /** Starts a Library workout as the live session. Returns true when it did,
     *  so the caller can switch to Train. One workout at a time. */
    suspend fun startLibraryWorkout(slug: String): Boolean {
        isBusy = true
        try {
            session = api.startLibraryWorkout(slug)
            pendingExercises = emptyList()
            prHint = ""
            progressionHint = ""
            stopRestTimer()
            selectDefaultExercise()
            errorMessage = ""
            return true
        } catch (error: CancellationException) {
            throw error
        } catch (error: Exception) {
            errorMessage = when {
                error.httpStatus == 409 -> "Finish or discard the workout you have going first."
                error is ApiException.SignedOut -> error.message ?: ""
                else -> "Couldn't start this workout: ${error.message}"
            }
            return false
        } finally {
            isBusy = false
        }
    }

    suspend fun saveLibraryWorkout(slug: String) {
        run("Couldn't save this workout") {
            val saved = api.saveLibraryWorkout(slug)
            libraryNotice = "Saved \"${saved.name}\" to your routines."
        }
    }

    suspend fun followProgram(slug: String) {
        run("Couldn't follow this program") {
            api.followProgram(slug)
            libraryProgram = api.libraryProgram(slug)
            libraryHome = api.libraryHome()
        }
    }

    suspend fun unfollowProgram(slug: String) {
        run("Couldn't stop following this program") {
            api.unfollowProgram(slug)
            libraryProgram = api.libraryProgram(slug)
            libraryHome = api.libraryHome()
        }
    }

    // MARK: Errors

    suspend fun run(context: String, work: suspend () -> Unit) {
        isBusy = true
        try {
            work()
            errorMessage = ""
        } catch (error: CancellationException) {
            throw error
        } catch (error: ApiException.SignedOut) {
            errorMessage = error.message ?: ""
        } catch (error: Exception) {
            errorMessage = "$context: ${error.message}"
        } finally {
            isBusy = false
        }
    }

    companion object {
        const val DEFAULT_REST_SECONDS = 90
        /** Shown on Progress until the user has records of their own. */
        val STARTER_EXERCISES = listOf("Barbell Bench Press", "Barbell Back Squat", "Conventional Deadlift")

        fun isoDay(instant: Instant, zone: ZoneId = ZoneId.systemDefault()): String =
            instant.atZone(zone).toLocalDate().toString()
    }
}
