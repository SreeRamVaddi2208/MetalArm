// An in-memory stand-in for the backend, built on ContractFixtures - the twin
// of the iOS app's API/MockAPIClient.swift. Used by previews, unit tests and
// UI tests (the "mockApi" instrumentation argument). Workouts are stateful so
// the full start -> log -> finish loop works, and so is the Library.

package com.sreeram.metalarm.api

import java.io.IOException
import java.util.UUID
import kotlin.math.roundToLong

class MockApi(
    signedIn: Boolean = true,
    private val levelUpOnFinish: Boolean = false,
    private val rankUpOnFinish: Boolean = false,
    /** Logging a set fails as if the phone had no signal. */
    var isOffline: Boolean = false,
    /** A brand-new account that has never been asked for a training path. */
    private var pathUnanswered: Boolean = false,
) : MetalArmApi {
    /** When set, every call throws this instead of returning data. */
    var failure: Exception? = null
    /** The next set is recorded, then the reply is lost as if the network dropped. */
    var dropNextLogSetResponse = false
    /** The cosmetic class the mock remembers, like the server would. */
    var characterClass = ""

    override var onSignedOut: (() -> Unit)? = null
    override var isSignedIn: Boolean = signedIn
        private set

    private var current: WorkoutSession? = null
    private var weightUnit = WeightUnit.Kg
    private val logSetReplies = mutableMapOf<UUID, SetLogResult>()
    private val partyList: MutableList<Party> = fixture<List<Party>>(ContractFixtures.parties).toMutableList()

    // The Library: who follows what, and which workout the live session came from.
    val enrollments = linkedMapOf<String, Enrollment>()
    private var libraryStartSlug: String? = null

    /** Simulates the server rejecting the stored tokens. */
    fun expireSession() {
        isSignedIn = false
        onSignedOut?.invoke()
    }

    private inline fun <reified T> fixture(json: String): T = MetalArmJson.decodeFromString(json)

    private fun check() {
        failure?.let { throw it }
    }

    private val library: List<Exercise> by lazy { fixture(ContractFixtures.exercises) }

    // Account

    override suspend fun signIn(email: String, password: String) {
        check()
        if (password != PASSWORD) throw ApiException.Http(401, "Incorrect email or password")
        isSignedIn = true
    }

    override suspend fun signUp(email: String, password: String, displayName: String, timezone: String) {
        check()
        if (password.length < 8) throw ApiException.Http(422, "String should have at least 8 characters")
        isSignedIn = true
    }

    override suspend fun signOut() {
        isSignedIn = false
    }

    override suspend fun signOutEverywhere() {
        check()
        isSignedIn = false
    }

    override suspend fun deleteAccount(password: String) {
        check()
        if (password != PASSWORD) throw ApiException.Http(403, "Password is incorrect")
        isSignedIn = false
    }

    override suspend fun me(): Me {
        check()
        val me: Me = fixture(ContractFixtures.me)
        return me.copy(
            weightUnit = weightUnit.raw,
            characterClass = characterClass,
            characterClassSetAt = if (pathUnanswered) null else me.characterClassSetAt,
        )
    }

    override suspend fun updateWeightUnit(unit: WeightUnit): Me {
        check()
        weightUnit = unit
        return me()
    }

    override suspend fun profile(): Profile {
        check()
        val profile: Profile = fixture(ContractFixtures.profile)
        return profile.copy(user = profile.user.copy(weightUnit = weightUnit.raw))
    }

    override suspend fun rankTrials(): List<RankTrial> {
        check()
        return fixture(ContractFixtures.rankTrials)
    }

    override suspend fun character(): CharacterSheet {
        check()
        val sheet: CharacterSheet = fixture(ContractFixtures.character)
        val highlights = mapOf(
            "powerlifter" to listOf("strength"),
            "bodybuilder" to listOf("strength", "endurance"),
            "athlete" to listOf("endurance", "discipline"),
        )
        val labels = mapOf("powerlifter" to "Powerlifter", "bodybuilder" to "Bodybuilder", "athlete" to "Athletic")
        val chosen = highlights[characterClass].orEmpty()
        return sheet.copy(
            characterClass = characterClass,
            classLabel = labels[characterClass].orEmpty(),
            stats = sheet.stats.map { it.copy(highlighted = it.key in chosen) },
        )
    }

    override suspend fun updateCharacterClass(value: String): Me {
        check()
        // Answering - including declining - stops the question coming back.
        pathUnanswered = false
        characterClass = value
        return me()
    }

    override suspend fun trainingPaths(): List<TrainingPath> {
        check()
        return fixture(ContractFixtures.trainingPaths)
    }

    override suspend fun importWorkouts(csv: String, unit: WeightUnit): WorkoutImportResult {
        check()
        if (!csv.contains("Exercise Name") && !csv.contains("exercise_title")) {
            throw ApiException.Http(422, "That isn't a Strong or Hevy CSV export")
        }
        return fixture(ContractFixtures.importResult)
    }

    override suspend fun points(): PointsSummary {
        check()
        return fixture(ContractFixtures.points)
    }

    // Exercises and progress

    override suspend fun searchExercises(query: String): List<Exercise> {
        check()
        val needle = query.trim().lowercase()
        return if (needle.isEmpty()) library else library.filter { it.name.lowercase().contains(needle) }
    }

    override suspend fun lastPerformance(exerciseId: String): LastPerformance {
        check()
        if (exerciseId != ContractFixtures.benchID) return LastPerformance(exerciseId = exerciseId)
        return fixture(ContractFixtures.lastPerformance)
    }

    override suspend fun exerciseHistory(exerciseId: String): List<HistoryPoint> {
        check()
        return fixture(ContractFixtures.history)
    }

    override suspend fun records(exerciseId: String?): List<WorkoutRecord> {
        check()
        val all: List<WorkoutRecord> = fixture(ContractFixtures.records)
        return if (exerciseId == null) all else all.filter { it.exerciseId == exerciseId }
    }

    // Workouts

    override suspend fun activeSession(): WorkoutSession? {
        check()
        return current
    }

    override suspend fun session(id: String): WorkoutSession {
        check()
        return current?.takeIf { it.id == id } ?: throw ApiException.Http(404, "Workout not found")
    }

    override suspend fun presets(): List<WorkoutPreset> {
        check()
        return fixture(ContractFixtures.presets)
    }

    override suspend fun startSession(presetSlug: String?): WorkoutSession {
        check()
        current?.let { throw ApiException.Http(409, "A workout is already in progress (${it.id}) - finish or abandon it first") }
        val preset = presetSlug?.let { slug -> fixture<List<WorkoutPreset>>(ContractFixtures.presets).firstOrNull { it.slug == slug } }
        if (presetSlug != null && preset == null) throw ApiException.Http(404, "No such workout")
        val planned = preset?.exercises.orEmpty().map { slot ->
            SessionExercise(slot.exercise, SessionTarget(slot.targetSets, slot.targetReps, null, slot.restSeconds))
        }
        val session = WorkoutSession(
            id = ContractFixtures.sessionID,
            name = preset?.let { "${it.categoryLabel ?: it.category} · ${it.name}" },
            status = "in_progress",
            startedAt = "2026-09-13T18:00:00Z",
            exercises = planned,
        )
        current = session
        return session
    }

    // The first set of each exercise beats the last session's best, so it pays the PR bonus.
    override suspend fun logSet(
        sessionId: String, exerciseId: String, weight: Double, unit: WeightUnit, reps: Int, clientSetId: UUID,
    ): SetLogResult {
        check()
        if (isOffline) throw IOException("The Internet connection appears to be offline.")
        // Like the server: a repeated client_set_id gets the original reply.
        logSetReplies[clientSetId]?.let { return it.copy(isDuplicate = true) }
        var session = current?.takeIf { it.id == sessionId } ?: throw ApiException.Http(404, "Workout not found")
        val exercise = library.firstOrNull { it.id == exerciseId } ?: throw ApiException.Http(404, "Exercise not found")
        val kilograms = (unit.toKilograms(weight) * 100).roundToLong() / 100.0

        if (session.exercises.none { it.exercise.id == exerciseId }) {
            val last = lastPerformance(exerciseId)
            session = session.copy(
                exercises = session.exercises + SessionExercise(exercise, previousSets = last.sets, hint = last.hint),
            )
        }
        val index = session.exercises.indexOfFirst { it.exercise.id == exerciseId }
        val card = session.exercises[index]
        val isFirst = card.sets.isEmpty()
        val loggedSet = WorkoutSet(
            id = UUID.randomUUID().toString(), sessionId = sessionId, exerciseId = exerciseId,
            setNumber = card.sets.size + 1, weightKg = kilograms, reps = reps, isPr = isFirst,
            completedAt = "2026-09-13T18:05:00Z",
        )
        val points = 2 + if (isFirst) 50 else 0
        session = session.copy(
            exercises = session.exercises.toMutableList().also { it[index] = card.copy(sets = card.sets + loggedSet) },
            workingSets = session.workingSets + 1,
            totalVolumeKg = session.totalVolumeKg + kilograms * reps,
            pointsTotal = session.pointsTotal + points,
        )
        current = session

        val prEvents = if (isFirst) listOf(
            PREvent(
                exerciseId = exerciseId, exerciseName = exercise.name, recordType = "max_weight", value = kilograms,
                weightKg = kilograms, previousValue = kilograms - 2.5, isBaseline = false, bonusAwarded = true,
                setId = loggedSet.id,
            ),
        ) else emptyList()
        val awards = buildList {
            add(Award("set_logged", 2, "Set logged"))
            if (isFirst) add(Award("pr_achieved", 50, "New PR: max_weight"))
        }
        val reply = SetLogResult(
            loggedSet = loggedSet, prEvents = prEvents, awards = awards, pointsAwarded = points,
            sessionPoints = session.pointsTotal, setCapReached = false, progression = steadyProgression(points),
        )
        logSetReplies[clientSetId] = reply
        if (dropNextLogSetResponse) {
            dropNextLogSetResponse = false
            throw IOException("The network connection was lost.")
        }
        return reply
    }

    override suspend fun finishSession(sessionId: String): FinishResult {
        check()
        val session = current?.takeIf { it.id == sessionId } ?: throw ApiException.Http(404, "Workout not found")
        advanceEnrollment(libraryStartSlug)
        libraryStartSlug = null
        val qualified = session.workingSets >= 3
        val prSets = session.exercises.flatMap { it.sets }.filter { it.isPr }
        val prEvents = session.exercises.mapNotNull { entry ->
            val best = entry.sets.firstOrNull { it.isPr } ?: return@mapNotNull null
            PREvent(
                exerciseId = entry.exercise.id, exerciseName = entry.exercise.name, recordType = "max_weight",
                value = best.weightKg, weightKg = best.weightKg, previousValue = best.weightKg - 2.5,
                isBaseline = false, bonusAwarded = true, setId = best.id,
            )
        }
        val prBonus = 50 * minOf(prSets.size, 3)
        val breakdown = PointsBreakdown(
            setPoints = 2 * session.workingSets, prBonus = prBonus,
            sessionBonus = if (qualified) 25 else 0, streakBonus = if (qualified) 20 else 0, reversals = 0,
            total = 2 * session.workingSets + prBonus + if (qualified) 45 else 0,
        )
        current = null
        return FinishResult(
            session = SessionSummary(
                id = session.id, status = "completed", startedAt = session.startedAt,
                endedAt = "2026-09-13T18:25:00Z", durationSeconds = 1500, workingSets = session.workingSets,
                exerciseCount = session.exercises.size, totalVolumeKg = session.totalVolumeKg,
                pointsTotal = breakdown.total, prCount = prSets.size,
            ),
            qualified = qualified, breakdown = breakdown, pointsCredited = breakdown.total,
            prEvents = prEvents, streak = fixture(ContractFixtures.streak),
            progression = finishProgression(breakdown.total),
        )
    }

    override suspend fun abandonSession(sessionId: String) {
        check()
        current = null
    }

    private fun finishProgression(points: Int): ProgressionDelta = when {
        rankUpOnFinish -> ProgressionDelta(points, points, 38_000 + points, 19, 20, "C", "B", 6, 12, leveledUp = true, rankedUp = true)
        levelUpOnFinish -> ProgressionDelta(points, points, 18_450 + points, 14, 15, "C", "C", 6, 12, leveledUp = true, rankedUp = false)
        else -> steadyProgression(points)
    }

    private fun steadyProgression(points: Int) =
        ProgressionDelta(points, points, 18_450 + points, 14, 14, "C", "C", 6, 12, leveledUp = false, rankedUp = false)

    // Parties

    override suspend fun parties(): List<Party> {
        check()
        return partyList.toList()
    }

    override suspend fun createParty(name: String): Party {
        check()
        val party = Party(
            id = UUID.randomUUID().toString(), name = name, ownerId = ContractFixtures.userID, maxMembers = 10,
            memberCount = 1, isActive = true, createdAt = "2026-09-13T18:00:00Z", myRole = "owner",
            inviteCode = "NEWC2345", totalPartyXp = 0,
        )
        partyList += party
        return party
    }

    override suspend fun joinParty(inviteCode: String): Party {
        check()
        if (inviteCode.uppercase() != "IRON2345") throw ApiException.Http(404, "No party with that invite code")
        return partyList[0]
    }

    override suspend fun partyLeaderboard(partyId: String): PartyBoard {
        check()
        val board: PartyBoard = fixture(ContractFixtures.partyBoard)
        if (partyId == ContractFixtures.partyID) return board.copy(partyId = partyId)
        return board.copy(
            partyId = partyId,
            entries = board.entries.filter { it.isMe }.map { it.copy(points = 0, workouts = 0) },
        )
    }

    override suspend fun partyRaid(partyId: String): PartyRaid {
        check()
        return fixture<PartyRaid>(ContractFixtures.partyRaid).copy(partyId = partyId)
    }

    override suspend fun league(): League {
        check()
        return fixture(ContractFixtures.league)
    }

    // The Library (in memory): a small catalog built from the fixture
    // exercises - two workouts and one program per path - recommended and
    // ordered the way the server does it: the user's path first, easiest first.

    private data class MockSlot(val exerciseId: String, val sets: Int, val low: Int, val high: Int, val rest: Int, val superset: Int = 0)
    private data class MockWorkout(
        val slug: String, val name: String, val category: String, val difficulty: String, val minutes: Int,
        val standalone: Boolean, val slots: List<MockSlot>,
    )
    private data class MockProgram(
        val slug: String, val name: String, val category: String, val difficulty: String, val weeks: Int,
        val workouts: List<String>, val days: List<Int>,
    )
    private data class TrainingDay(val week: Int, val day: Int, val slug: String)

    private fun label(category: String) = LibraryVocabulary.pathLabel(category)

    /** The server's order: the user's path, then the others; easiest first. */
    private fun rank(category: String, difficulty: String, size: Int): List<Int> = listOf(
        if (category == characterClass) 0 else 1,
        PATH_ORDER.indexOf(category).let { if (it < 0) 9 else it },
        DIFFICULTY_ORDER[difficulty] ?: 9,
        size,
    )

    private val rankComparator = Comparator<List<Int>> { a, b ->
        a.zip(b).firstOrNull { it.first != it.second }?.let { it.first.compareTo(it.second) } ?: 0
    }

    private fun workoutCard(w: MockWorkout, sort: Int): LibraryWorkoutCard {
        val equipment = w.slots.mapNotNull { slot -> library.firstOrNull { it.id == slot.exerciseId }?.equipment }.distinct()
        return LibraryWorkoutCard(
            slug = w.slug, name = w.name, description = "${w.name}, for the ${label(w.category)} path.",
            category = w.category, categoryLabel = label(w.category), difficulty = w.difficulty,
            durationMinutes = w.minutes, exerciseCount = w.slots.size, equipment = equipment, focusTags = emptyList(),
            recommended = characterClass.isNotEmpty() && w.category == characterClass, sort = sort,
        )
    }

    private fun programCard(p: MockProgram, sort: Int) = LibraryProgramCard(
        slug = p.slug, name = p.name, description = "${p.name}: ${p.days.size} days a week.",
        category = p.category, categoryLabel = label(p.category), difficulty = p.difficulty, weeks = p.weeks,
        daysPerWeek = p.days.size, equipment = listOf("barbell"),
        recommended = characterClass.isNotEmpty() && p.category == characterClass, sort = sort,
        following = enrollments[p.slug]?.status == "active",
    )

    private fun workoutCards(items: List<MockWorkout>) = items
        .sortedWith(compareBy(rankComparator) { rank(it.category, it.difficulty, it.minutes) })
        .mapIndexed { index, w -> workoutCard(w, index) }

    private fun programCards(items: List<MockProgram>) = items
        .sortedWith(compareBy(rankComparator) { rank(it.category, it.difficulty, it.days.size) })
        .mapIndexed { index, p -> programCard(p, index) }

    /** Every training day, in order. */
    private fun trainingDays(p: MockProgram): List<TrainingDay> {
        var n = 0
        return (1..p.weeks).flatMap { week -> p.days.map { day -> TrainingDay(week, day, p.workouts[n++ % p.workouts.size]) } }
    }

    private fun atOrAfter(day: TrainingDay, e: Enrollment) =
        day.week > e.currentWeek || (day.week == e.currentWeek && day.day >= e.currentDay)

    private fun enrollmentOut(e: Enrollment, p: MockProgram): Enrollment {
        val next = trainingDays(p).firstOrNull { atOrAfter(it, e) }
        val card = if (e.status == "completed") null
        else next?.let { day -> WORKOUTS.firstOrNull { it.slug == day.slug }?.let { workoutCard(it, 0) } }
        return e.copy(nextWorkout = card)
    }

    private fun advanceEnrollment(slug: String?) {
        if (slug == null) return
        val (key, e) = enrollments.entries.firstOrNull { it.value.status == "active" }?.toPair() ?: return
        val p = PROGRAMS.firstOrNull { it.slug == key } ?: return
        val days = trainingDays(p)
        val index = days.indexOfFirst { atOrAfter(it, e) }
        if (index < 0 || days[index].slug != slug) return
        enrollments[key] = if (index + 1 < days.size) {
            e.copy(currentWeek = days[index + 1].week, currentDay = days[index + 1].day)
        } else {
            e.copy(status = "completed")
        }
    }

    override suspend fun libraryHome(): LibraryHome {
        check()
        val path = characterClass
        val standalone = WORKOUTS.filter { it.standalone }
        val yours = enrollments.entries.firstOrNull { it.value.status == "active" }?.let { found ->
            PROGRAMS.firstOrNull { it.slug == found.key }?.let { YourProgram(programCard(it, 0), enrollmentOut(found.value, it)) }
        }
        return LibraryHome(
            path = path, needsPath = path.isEmpty(), yourProgram = yours,
            recommendedPrograms = if (path.isEmpty()) emptyList() else programCards(PROGRAMS.filter { it.category == path }),
            recommendedWorkouts = if (path.isEmpty()) emptyList() else workoutCards(standalone.filter { it.category == path }),
            otherPaths = PATH_ORDER.filter { it != path }.map { c ->
                PathCount(c, label(c), PROGRAMS.count { it.category == c }, standalone.count { it.category == c })
            },
        )
    }

    override suspend fun libraryPrograms(category: String?, filters: LibraryFilters): List<LibraryProgramCard> {
        check()
        return programCards(PROGRAMS.filter { p ->
            (category == null || p.category == category) &&
                (filters.difficulty == null || p.difficulty == filters.difficulty) &&
                (filters.daysPerWeek == null || p.days.size == filters.daysPerWeek)
        })
    }

    override suspend fun libraryProgram(slug: String): LibraryProgram {
        check()
        val p = PROGRAMS.firstOrNull { it.slug == slug } ?: throw ApiException.Http(404, "No such program")
        val card = programCard(p, 0)
        val days = trainingDays(p)
        val names = WORKOUTS.associate { it.slug to it.name }
        val schedule = (1..p.weeks).map { week ->
            ScheduleWeek(week, (1..7).map { day ->
                val workout = days.firstOrNull { it.week == week && it.day == day }?.slug
                ScheduleDay(day, workout, workout?.let { names[it] })
            })
        }
        return LibraryProgram(
            slug = p.slug, name = p.name, description = card.description, category = p.category,
            categoryLabel = card.categoryLabel, difficulty = p.difficulty, weeks = p.weeks, daysPerWeek = p.days.size,
            equipment = card.equipment, recommended = card.recommended, following = card.following, schedule = schedule,
            workouts = p.workouts.mapNotNull { s -> WORKOUTS.firstOrNull { it.slug == s }?.let { workoutCard(it, 0) } },
            enrollment = enrollments[p.slug]?.let { enrollmentOut(it, p) },
        )
    }

    override suspend fun libraryWorkouts(category: String?, filters: LibraryFilters): List<LibraryWorkoutCard> {
        check()
        return workoutCards(WORKOUTS.filter { w ->
            w.standalone && (category == null || w.category == category) &&
                (filters.difficulty == null || w.difficulty == filters.difficulty) &&
                (filters.maxMinutes == null || w.minutes <= filters.maxMinutes)
        })
    }

    override suspend fun libraryWorkout(slug: String): LibraryWorkout {
        check()
        val w = WORKOUTS.firstOrNull { it.slug == slug } ?: throw ApiException.Http(404, "No such workout")
        val card = workoutCard(w, 0)
        return LibraryWorkout(
            slug = w.slug, name = w.name, description = card.description, category = w.category,
            categoryLabel = card.categoryLabel, difficulty = w.difficulty, durationMinutes = w.minutes,
            exerciseCount = w.slots.size, equipment = card.equipment, recommended = card.recommended,
            exercises = w.slots.mapIndexedNotNull { index, slot ->
                library.firstOrNull { it.id == slot.exerciseId }?.let {
                    LibraryWorkoutExercise(index, it, slot.sets, slot.low, slot.high, slot.rest, null, slot.superset)
                }
            },
        )
    }

    override suspend fun startLibraryWorkout(slug: String): WorkoutSession {
        check()
        current?.let { throw ApiException.Http(409, "A workout is already in progress (${it.id}) - finish or abandon it first") }
        val workout = libraryWorkout(slug)
        val planned = workout.exercises.map { slot ->
            SessionExercise(
                exercise = slot.exercise,
                target = SessionTarget(slot.targetSets, slot.repHigh, null, slot.restSeconds, slot.repLow, slot.repHigh),
                supersetGroup = slot.supersetGroup.takeIf { it > 0 },
            )
        }
        val session = WorkoutSession(
            id = ContractFixtures.sessionID, name = workout.name, status = "in_progress",
            startedAt = "2026-09-13T18:00:00Z", exercises = planned,
        )
        current = session
        libraryStartSlug = slug
        return session
    }

    override suspend fun saveLibraryWorkout(slug: String): SavedRoutine {
        check()
        return SavedRoutine("routine-$slug", libraryWorkout(slug).name)
    }

    override suspend fun followProgram(slug: String): Enrollment {
        check()
        val p = PROGRAMS.firstOrNull { it.slug == slug } ?: throw ApiException.Http(404, "No such program")
        enrollments.entries.filter { it.key != slug && it.value.status == "active" }.forEach {
            enrollments[it.key] = it.value.copy(status = "paused")
        }
        val first = trainingDays(p).first()
        var e = enrollments[slug] ?: Enrollment(
            id = "enrollment-$slug", programSlug = slug, status = "active", startedAt = "2026-09-13T18:00:00Z",
            currentWeek = first.week, currentDay = first.day,
        )
        if (e.status == "completed") e = e.copy(currentWeek = first.week, currentDay = first.day)
        e = e.copy(status = "active")
        enrollments[slug] = e
        return enrollmentOut(e, p)
    }

    override suspend fun unfollowProgram(slug: String): Enrollment {
        check()
        val e = enrollments[slug] ?: throw ApiException.Http(404, "Not following this program")
        val p = PROGRAMS.first { it.slug == slug }
        val paused = e.copy(status = "paused")
        enrollments[slug] = paused
        return enrollmentOut(paused, p)
    }

    companion object {
        const val PASSWORD = "correct-horse-1"

        private val PATH_ORDER = listOf("athlete", "bodybuilder", "powerlifter")
        private val DIFFICULTY_ORDER = mapOf("beginner" to 0, "intermediate" to 1, "advanced" to 2)

        private val WORKOUTS: List<MockWorkout> = ContractFixtures.run {
            listOf(
                MockWorkout("athletic-circuit", "Athletic circuit", "athlete", "beginner", 30, true, listOf(
                    MockSlot(squatID, 3, 15, 15, 45, superset = 1), MockSlot(pullUpID, 3, 12, 15, 45, superset = 1))),
                MockWorkout("athletic-press", "Press and pull", "athlete", "intermediate", 35, true, listOf(
                    MockSlot(pressID, 3, 12, 15, 45), MockSlot(rowID, 3, 12, 15, 45))),
                MockWorkout("chest-and-triceps", "Chest and triceps", "bodybuilder", "intermediate", 55, true, listOf(
                    MockSlot(benchID, 4, 8, 10, 90), MockSlot(pressID, 3, 10, 12, 75))),
                MockWorkout("back-and-biceps", "Back and biceps", "bodybuilder", "beginner", 50, true, listOf(
                    MockSlot(rowID, 4, 8, 12, 90), MockSlot(pullUpID, 3, 8, 12, 90))),
                MockWorkout("squat-day", "Squat day", "powerlifter", "intermediate", 70, true, listOf(
                    MockSlot(squatID, 5, 3, 5, 240), MockSlot(deadliftID, 3, 3, 5, 240))),
                MockWorkout("bench-day", "Bench day", "powerlifter", "intermediate", 60, true, listOf(
                    MockSlot(benchID, 5, 3, 5, 240), MockSlot(rowID, 3, 6, 8, 120))),
            )
        }

        private val PROGRAMS = listOf(
            MockProgram("foundations-of-movement", "Foundations of Movement", "athlete", "beginner", 4,
                listOf("athletic-circuit", "athletic-press"), listOf(1, 3, 5)),
            MockProgram("upper-lower-8wk", "Upper / Lower", "bodybuilder", "beginner", 8,
                listOf("chest-and-triceps", "back-and-biceps"), listOf(1, 2, 4, 5)),
            MockProgram("linear-strength-base", "Linear Strength Base", "powerlifter", "beginner", 8,
                listOf("squat-day", "bench-day"), listOf(1, 3, 5)),
        )
    }
}
