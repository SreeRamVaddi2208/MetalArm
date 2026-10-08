// Mirrors backend/app/schemas (and the iOS app's API/Models.swift). Keys are
// snake_case on the wire (MetalArmJson's naming strategy); ids and timestamps
// stay strings. Points, XP and records always come from the server - never
// computed here.

package com.sreeram.metalarm.api

import kotlinx.serialization.ExperimentalSerializationApi
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonNamingStrategy
import java.time.Instant
import java.time.OffsetDateTime
import java.util.Locale
import kotlin.math.ceil
import kotlin.math.roundToLong

@OptIn(ExperimentalSerializationApi::class)
val MetalArmJson = Json {
    namingStrategy = JsonNamingStrategy.SnakeCase
    ignoreUnknownKeys = true
    explicitNulls = false
    coerceInputValues = true
    encodeDefaults = true
}

// MARK: Auth

@Serializable
data class TokenPair(
    val accessToken: String,
    val tokenType: String,
    val expiresIn: Int,
    val refreshToken: String,
    val refreshExpiresIn: Int,
)

// MARK: Account and progression

@Serializable
data class ProgressInfo(
    val totalXp: Int,
    val currentLevel: Int,
    val pointsBalance: Int,
    val longestStreak: Int,
    val lastCompletedOn: String? = null,
    val xpIntoLevel: Int,
    val xpForNextLevel: Int,
    val currentStreak: Int,
    val streakIsActive: Boolean,
    val rank: String,
    val rankByLevel: String,
    val nextRank: String? = null,
    val nextRankLevel: Int? = null,
    val nextRankStreak: Int? = null,
    /** The strength trial between the user and the next rank. */
    val nextRankTrial: String? = null,
    /** Rank trials passed so far, e.g. "BA". */
    val trialsPassed: String? = null,
) {
    val xpProgress: Double
        get() = if (xpForNextLevel > 0) minOf(1.0, xpIntoLevel.toDouble() / xpForNextLevel) else 0.0
}

@Serializable
data class UserInfo(
    val id: String,
    val email: String,
    val displayName: String,
    val timezone: String,
    val createdAt: String,
    val weightUnit: String,
)

@Serializable
data class Me(
    val id: String,
    val email: String,
    val displayName: String,
    val timezone: String,
    val createdAt: String,
    val weightUnit: String,
    val progress: ProgressInfo,
    val characterClass: String? = null,
    /** Null means never asked, which is what onboarding checks. */
    val characterClassSetAt: String? = null,
)

/** A training path, as the server describes it (GET /training-categories). */
@Serializable
data class TrainingPath(
    val category: String,
    val displayName: String,
    val tagline: String,
    val description: String,
    val repRangeLow: Int,
    val repRangeHigh: Int,
    val relativeLoad: String,
    val relativeVolume: String,
    val restSecondsGuidance: Int,
    val emphasisTags: List<String> = emptyList(),
) {
    /** "12-20 reps · light · short rests" */
    val summary: String
        get() {
            val rest = when {
                restSecondsGuidance >= 120 -> "long rests"
                restSecondsGuidance >= 75 -> "moderate rests"
                else -> "short rests"
            }
            val load = mapOf("low" to "light", "moderate" to "moderate", "moderate_high" to "moderate-heavy", "heavy" to "heavy")
            return "$repRangeLow-$repRangeHigh reps · ${load[relativeLoad] ?: relativeLoad} · $rest"
        }

    companion object {
        /** The cards still render without the server. */
        val fallbacks = listOf(
            TrainingPath("athlete", "Athletic", "Conditioning first. Lean and capable, not bulked.", "", 12, 20, "low", "high", 60),
            TrainingPath("bodybuilder", "Bodybuilder", "Size and symmetry. Working sets close to failure.", "", 8, 15, "moderate_high", "moderate_high", 90),
            TrainingPath("powerlifter", "Powerlifter", "Maximal strength. Heavy, low reps, long rests.", "", 1, 6, "heavy", "low", 240),
        )
    }
}

@Serializable
data class Badge(
    val id: String,
    val name: String,
    val description: String,
    val icon: String,
    val earned: Boolean,
    val progress: Int,
    val target: Int,
    val percent: Int,
)

@Serializable
data class LifetimeStats(
    val questsCompleted: Int,
    val partyQuestsCompleted: Int,
    val rewardsRedeemed: Int,
    val pointsEarned: Int,
    val pointsSpent: Int,
    val partiesJoined: Int,
    val partyXpContributed: Int,
    val memberSince: String,
    val workoutsCompleted: Int,
    val workoutPrs: Int,
    val totalVolumeKg: Double,
    val longestWorkoutStreak: Int,
)

@Serializable
data class Profile(
    val user: UserInfo,
    val progress: ProgressInfo,
    val stats: LifetimeStats,
    val badges: List<Badge>,
    val badgesEarned: Int,
    val badgesTotal: Int,
)

// MARK: Exercises

@Serializable
data class Exercise(
    val id: String,
    val name: String,
    val slug: String? = null,
    val category: String,
    val primaryMuscleGroups: List<String> = emptyList(),
    val equipment: String,
    val instructions: String? = null,
    val mediaUrl: String? = null,
    val isCustom: Boolean = false,
    val isArchived: Boolean = false,
) {
    val muscleLabel: String
        get() = primaryMuscleGroups.joinToString(", ") { it.replace('_', ' ') }.capitalizedWords()
}

@Serializable
data class HistoryPoint(
    val sessionId: String,
    val performedAt: String,
    val topWeightKg: Double? = null,
    val topWeightReps: Int? = null,
    val bestEst1rm: Double? = null,
    val volumeKg: Double,
    val workingSets: Int,
    val totalReps: Int,
)

/** What to try next on an exercise. `kind` is progress, plateau or deload. */
@Serializable
data class ProgressionHint(
    val kind: String,
    val text: String,
    val targetWeightKg: Double? = null,
    val targetReps: Int? = null,
)

@Serializable
data class LastPerformance(
    val exerciseId: String,
    val sessionId: String? = null,
    val performedAt: String? = null,
    val sets: List<WorkoutSet> = emptyList(),
    val hint: ProgressionHint? = null,
)

// MARK: Sessions and sets

@Serializable
data class WorkoutSet(
    val id: String,
    val sessionId: String,
    val exerciseId: String,
    val setNumber: Int,
    val weightKg: Double,
    val reps: Int? = null,
    val rpe: Double? = null,
    val isWarmup: Boolean = false,
    val isPr: Boolean = false,
    val durationSeconds: Int? = null,
    val distanceM: Double? = null,
    val completedAt: String,
)

@Serializable
data class SessionTarget(
    val targetSets: Int? = null,
    val targetReps: Int? = null,
    val targetWeightKg: Double? = null,
    val restSeconds: Int? = null,
    // The rep range when the plan gives one ("8-12"); targetReps is its top.
    val targetRepsLow: Int? = null,
    val targetRepsHigh: Int? = null,
)

/** One slot of a legacy ready-made workout (GET /workouts/presets). */
@Serializable
data class PresetSlot(
    val exercise: Exercise,
    val targetSets: Int,
    val targetReps: Int,
    val restSeconds: Int,
)

@Serializable
data class WorkoutPreset(
    val slug: String,
    val category: String,
    val categoryLabel: String? = null,
    val name: String,
    val summary: String,
    val exercises: List<PresetSlot>,
    val matchesYourPath: Boolean? = null,
)

@Serializable
data class SessionExercise(
    val exercise: Exercise,
    val target: SessionTarget? = null,
    /** Cards sharing a number are a superset; null is none. */
    val supersetGroup: Int? = null,
    val sets: List<WorkoutSet> = emptyList(),
    /** The last completed session's sets on this exercise: the ghost values. */
    val previousSets: List<WorkoutSet> = emptyList(),
    val hint: ProgressionHint? = null,
)

@Serializable
data class WorkoutSession(
    val id: String,
    val name: String? = null,
    val status: String,
    val routineId: String? = null,
    val startedAt: String,
    val endedAt: String? = null,
    val durationSeconds: Int = 0,
    val workingSets: Int = 0,
    val totalVolumeKg: Double = 0.0,
    val pointsTotal: Int = 0,
    val pointsCredited: Int = 0,
    val qualified: Boolean? = null,
    val exercises: List<SessionExercise> = emptyList(),
)

@Serializable
data class ActiveSession(val session: WorkoutSession? = null)

@Serializable
data class Award(val sourceType: String, val points: Int, val reason: String)

@Serializable
data class PREvent(
    val exerciseId: String,
    val exerciseName: String,
    val recordType: String,
    val value: Double,
    val weightKg: Double? = null,
    val previousValue: Double? = null,
    val isBaseline: Boolean = false,
    val bonusAwarded: Boolean = false,
    val setId: String? = null,
) {
    /** max_reps_at_weight carries reps in `value`; the others are kilograms. */
    fun headline(unit: WeightUnit): String = when (recordType) {
        "max_weight" -> "New heaviest $exerciseName: ${unit.format(value)}"
        "est_1rm" -> "New est. 1RM on $exerciseName: ${unit.format(value)}"
        "max_volume" -> "New volume record on $exerciseName: ${unit.format(value)}"
        "max_reps_at_weight" -> "New rep record on $exerciseName: ${value.toInt()} reps at ${unit.format(weightKg ?: 0.0)}"
        else -> "New record on $exerciseName"
    }

    /** The line that follows the record, keyed on the set that set it. */
    val motivation: String get() = Motivation.line(setId ?: exerciseId)
}

/** What to celebrate: the record that paid the PR bonus, else any genuine
 *  record. First-ever logs (baselines) are not celebrated. */
val List<PREvent>.celebrated: PREvent?
    get() = firstOrNull { it.bonusAwarded } ?: firstOrNull { !it.isBaseline }

@Serializable
data class ProgressionDelta(
    val xpAwarded: Int,
    val pointsAwarded: Int,
    val totalXp: Int,
    val levelBefore: Int,
    val levelAfter: Int,
    val rankBefore: String,
    val rankAfter: String,
    val currentStreak: Int,
    val longestStreak: Int,
    val leveledUp: Boolean,
    val rankedUp: Boolean,
) {
    val hint: String
        get() = when {
            rankedUp -> "Rank up! You're now ${RankTitle.of(rankAfter)}."
            leveledUp -> "Level up! You reached level $levelAfter."
            else -> ""
        }
}

@Serializable
data class SetLogResult(
    @SerialName("set") val loggedSet: WorkoutSet,
    val prEvents: List<PREvent> = emptyList(),
    val awards: List<Award> = emptyList(),
    val pointsAwarded: Int,
    val sessionPoints: Int,
    val setCapReached: Boolean = false,
    val progression: ProgressionDelta,
    val isDuplicate: Boolean = false,
)

@Serializable
data class SessionSummary(
    val id: String,
    val name: String? = null,
    val status: String,
    val startedAt: String,
    val endedAt: String? = null,
    val durationSeconds: Int,
    val workingSets: Int,
    val exerciseCount: Int,
    val totalVolumeKg: Double,
    val pointsTotal: Int,
    val prCount: Int,
)

@Serializable
data class Streak(
    val weeks: Int,
    val thisWeekSessions: Int,
    val target: Int,
    val thisWeekDone: Boolean,
    val sessionsToGo: Int,
)

@Serializable
data class PointsBreakdown(
    val setPoints: Int,
    val prBonus: Int,
    val sessionBonus: Int,
    val streakBonus: Int,
    val reversals: Int,
    val total: Int,
)

@Serializable
data class FinishResult(
    val session: SessionSummary,
    /** False: under 10 minutes or fewer than 3 working sets. */
    val qualified: Boolean,
    val awards: List<Award> = emptyList(),
    val breakdown: PointsBreakdown,
    val pointsCredited: Int,
    val prEvents: List<PREvent> = emptyList(),
    val streak: Streak,
    val progression: ProgressionDelta,
)

@Serializable
data class PointsSummary(
    val totalPoints: Int,
    val thisWeekPoints: Int,
    val sessionsCompleted: Int,
    val streak: Streak,
)

@Serializable
data class WorkoutRecord(
    val exerciseId: String,
    val exerciseName: String,
    val recordType: String,
    val value: Double,
    val weightKg: Double? = null,
    val achievedAt: String,
    val sessionId: String,
    val setId: String? = null,
) {
    val id: String get() = "$exerciseId-$recordType-${weightKg ?: 0.0}"

    val label: String
        get() = when (recordType) {
            "max_weight" -> "Heaviest"
            "est_1rm" -> "Best est. 1RM"
            "max_volume" -> "Best session volume"
            "max_reps_at_weight" -> "Most reps"
            else -> recordType
        }

    fun valueText(unit: WeightUnit): String =
        if (recordType == "max_reps_at_weight") "${value.toInt()} reps @ ${unit.format(weightKg ?: 0.0)}"
        else unit.format(value)

    companion object {
        val displayOrder = listOf("max_weight", "est_1rm", "max_volume", "max_reps_at_weight")
    }
}

// MARK: Parties, leagues, raids

@Serializable
data class Party(
    val id: String,
    val name: String,
    val ownerId: String,
    val maxMembers: Int,
    val memberCount: Int,
    val isActive: Boolean,
    val createdAt: String,
    val myRole: String,
    val inviteCode: String? = null,
    val totalPartyXp: Int = 0,
)

@Serializable
data class PartyBoardEntry(
    val position: Int,
    val userId: String,
    val displayName: String,
    val points: Int,
    val workouts: Int,
    val level: Int,
    val rank: String,
    val isMe: Boolean,
)

@Serializable
data class PartyBoard(
    val partyId: String,
    val period: String,
    val periodStart: String? = null,
    val entries: List<PartyBoardEntry> = emptyList(),
)

@Serializable
data class RaidHitter(
    val userId: String,
    val displayName: String,
    val damage: Int,
    val hits: Int,
    val isMe: Boolean,
)

@Serializable
data class PartyRaid(
    val partyId: String,
    val weekKey: String,
    val name: String,
    val maxHp: Int,
    val hpRemaining: Int,
    val damageDealt: Int,
    val healed: Int,
    val idleDays: Int,
    val defeated: Boolean,
    val defeatedAt: String? = null,
    val endsAt: String,
    val hitters: List<RaidHitter> = emptyList(),
) {
    val hpFraction: Double get() = if (maxHp > 0) hpRemaining.toDouble() / maxHp else 0.0
    fun daysLeft(now: Instant = Instant.now()): Int = daysUntil(endsAt, now)
}

@Serializable
data class LeagueEntry(
    val position: Int,
    val userId: String,
    val displayName: String,
    val points: Int,
    val level: Int,
    val rank: String,
    val isMe: Boolean,
)

@Serializable
data class League(
    val weekKey: String,
    val division: Int,
    val divisionLabel: String,
    val groupNo: Int,
    val endsAt: String,
    val promotedFrom: Int? = null,
    val promoteCutoff: Int,
    val demoteCutoff: Int,
    val entries: List<LeagueEntry> = emptyList(),
) {
    fun daysLeft(now: Instant = Instant.now()): Int = daysUntil(endsAt, now)
    val me: LeagueEntry? get() = entries.firstOrNull { it.isMe }
}

@Serializable
data class CharacterStat(
    val key: String,
    val label: String,
    val value: Int,
    val detail: String,
    val highlighted: Boolean,
) {
    val fraction: Double get() = (value / 100.0).coerceIn(0.0, 1.0)
}

/** The character sheet. The class only highlights stats - it changes no score. */
@Serializable
data class CharacterSheet(
    val characterClass: String,
    val classLabel: String,
    val stats: List<CharacterStat> = emptyList(),
)

/** POST /workouts/import: what a Strong or Hevy export added to the history. */
@Serializable
data class WorkoutImportResult(
    val source: String,
    val workoutsImported: Int,
    val setsImported: Int,
    val workoutsSkipped: Int,
    val rowsSkipped: Int,
    val exercisesCreated: List<String> = emptyList(),
    val xpAwarded: Int,
    val duplicate: Boolean,
    val progression: ProgressionDelta? = null,
) {
    val summary: String
        get() {
            if (duplicate) return "That file was already imported - nothing changed."
            val app = if (source == "strong") "Strong" else "Hevy"
            val parts = mutableListOf("Imported ${plural(workoutsImported, "workout")} ($setsImported sets) from $app.")
            if (workoutsSkipped > 0) parts += "$workoutsSkipped already in your history."
            if (exercisesCreated.isNotEmpty()) parts += "${plural(exercisesCreated.size, "new exercise")} added."
            if (xpAwarded > 0) parts += "+$xpAwarded XP."
            return parts.joinToString(" ")
        }
}

/** GET /profile/trials: a strength standard that gates rank B, A or S. */
@Serializable
data class RankTrial(
    val rank: String,
    val lift: String,
    val description: String,
    val multiplier: Double,
    /** Null until a bodyweight is logged. */
    val targetKg: Double? = null,
    val bestKg: Double? = null,
    val passed: Boolean,
) {
    val fraction: Double
        get() = targetKg?.takeIf { it > 0 }?.let { minOf(1.0, (bestKg ?: 0.0) / it) } ?: 0.0
}

// MARK: The Library (GET /library/...)

@Serializable
data class LibraryWorkoutCard(
    val slug: String,
    val name: String,
    val description: String? = null,
    val category: String,
    val categoryLabel: String,
    val difficulty: String,
    val durationMinutes: Int,
    val exerciseCount: Int,
    val equipment: List<String> = emptyList(),
    val focusTags: List<String>? = null,
    val recommended: Boolean,
    val sort: Int,
) {
    /** "45 min · 6 exercises" */
    val meta: String get() = "$durationMinutes min · ${plural(exerciseCount, "exercise")}"
    /** The first three pieces of kit, then "+". */
    val gear: String
        get() = equipment.take(3).joinToString(", ") { LibraryVocabulary.label(it) } + if (equipment.size > 3) " +" else ""
}

@Serializable
data class LibraryProgramCard(
    val slug: String,
    val name: String,
    val description: String? = null,
    val category: String,
    val categoryLabel: String,
    val difficulty: String,
    val weeks: Int,
    val daysPerWeek: Int,
    val equipment: List<String> = emptyList(),
    val recommended: Boolean,
    val sort: Int,
    val following: Boolean? = null,
) {
    val meta: String get() = "$weeks weeks · $daysPerWeek days a week · ${difficulty.capitalizedFirst()}"
}

@Serializable
data class LibraryWorkoutExercise(
    val position: Int,
    val exercise: Exercise,
    val targetSets: Int,
    val repLow: Int,
    val repHigh: Int,
    val restSeconds: Int,
    val note: String? = null,
    val supersetGroup: Int = 0,
) {
    /** "4 × 8–12 · 90s rest" - targets, never a weight. */
    val target: String
        get() = "$targetSets × ${if (repLow == repHigh) "$repLow" else "$repLow–$repHigh"} · ${restSeconds}s rest"
}

@Serializable
data class LibraryWorkout(
    val slug: String,
    val name: String,
    val description: String? = null,
    val category: String,
    val categoryLabel: String,
    val difficulty: String,
    val durationMinutes: Int,
    val exerciseCount: Int,
    val equipment: List<String> = emptyList(),
    val recommended: Boolean,
    val exercises: List<LibraryWorkoutExercise> = emptyList(),
    val routineId: String? = null,
)

@Serializable
data class ScheduleDay(val day: Int, val workoutSlug: String? = null, val workoutName: String? = null)

@Serializable
data class ScheduleWeek(val week: Int, val days: List<ScheduleDay>)

@Serializable
data class Enrollment(
    val id: String,
    val programSlug: String,
    val status: String,
    val startedAt: String,
    val currentWeek: Int,
    val currentDay: Int,
    val nextWorkout: LibraryWorkoutCard? = null,
) {
    val whereLabel: String get() = "Week $currentWeek · Day $currentDay"
}

@Serializable
data class LibraryProgram(
    val slug: String,
    val name: String,
    val description: String? = null,
    val category: String,
    val categoryLabel: String,
    val difficulty: String,
    val weeks: Int,
    val daysPerWeek: Int,
    val equipment: List<String> = emptyList(),
    val recommended: Boolean,
    val following: Boolean? = null,
    val schedule: List<ScheduleWeek> = emptyList(),
    val workouts: List<LibraryWorkoutCard> = emptyList(),
    val enrollment: Enrollment? = null,
) {
    val meta: String get() = "$weeks weeks · $daysPerWeek days a week · ${difficulty.capitalizedFirst()}"
}

@Serializable
data class YourProgram(val program: LibraryProgramCard, val enrollment: Enrollment)

@Serializable
data class PathCount(val category: String, val label: String, val programs: Int, val workouts: Int)

@Serializable
data class LibraryHome(
    val path: String,
    val needsPath: Boolean,
    val yourProgram: YourProgram? = null,
    val recommendedPrograms: List<LibraryProgramCard> = emptyList(),
    val recommendedWorkouts: List<LibraryWorkoutCard> = emptyList(),
    val otherPaths: List<PathCount> = emptyList(),
)

/** Optional filters for the program and workout lists. */
data class LibraryFilters(
    val daysPerWeek: Int? = null,
    val difficulty: String? = null,
    val equipment: List<String> = emptyList(),
    val maxMinutes: Int? = null,
) {
    val isEmpty: Boolean get() = daysPerWeek == null && difficulty == null && equipment.isEmpty() && maxMinutes == null
    val count: Int
        get() = (if (daysPerWeek == null) 0 else 1) + (if (difficulty == null) 0 else 1) + equipment.size +
            (if (maxMinutes == null) 0 else 1)
}

/** What save-to-routines returns: enough to say where it went. */
@Serializable
data class SavedRoutine(val id: String, val name: String)

/** The path and filter vocabulary - the same as the web's state/library.py. */
object LibraryVocabulary {
    val paths = listOf("athlete" to "Athletic", "bodybuilder" to "Bodybuilder", "powerlifter" to "Powerlifter")
    val days = listOf(2, 3, 4, 5, 6)
    val difficulties = listOf("beginner", "intermediate", "advanced")
    val equipment = listOf("bodyweight", "dumbbell", "kettlebell", "barbell", "cable", "machine", "band")
    val durations = listOf(30, 45, 60)
    const val NOTE = "These are templates, not coaching. Adjust the load to your ability."

    private val labels = mapOf("ez_bar" to "EZ bar", "trap_bar" to "Trap bar", "cardio_machine" to "Cardio machine")

    /** "ez_bar" -> "EZ bar", "dumbbell" -> "Dumbbell". */
    fun label(code: String): String = labels[code] ?: code.replace('_', ' ').capitalizedFirst()

    fun pathLabel(category: String): String = paths.firstOrNull { it.first == category }?.second ?: label(category)
}

// MARK: Units, ranks and wording

enum class WeightUnit(val raw: String) {
    Kg("kg"), Lb("lb");

    fun fromKilograms(kilograms: Double): Double = when (this) {
        Kg -> kilograms
        // Pounds to one decimal: 80 kg reads 176.4 lb.
        Lb -> ((kilograms / KILOGRAMS_PER_POUND) * 10).roundToLong() / 10.0
    }

    fun toKilograms(value: Double): Double = if (this == Kg) value else value * KILOGRAMS_PER_POUND

    fun format(kilograms: Double): String = "${formatNumber(fromKilograms(kilograms))} $raw"

    companion object {
        /** Exactly the backend's workout_rules.LB_TO_KG. */
        const val KILOGRAMS_PER_POUND = 0.45359237

        fun of(raw: String?): WeightUnit = entries.firstOrNull { it.raw == raw } ?: Kg
    }
}

object RankTitle {
    val ladder = listOf(
        "E" to "Untrained", "D" to "Novice", "C" to "Intermediate",
        "B" to "Advanced", "A" to "Elite", "S" to "World Class",
    )
    private val titles = ladder.toMap()

    /** An unknown letter is shown as it came. */
    fun of(letter: String): String = titles[letter.uppercase()] ?: letter

    /** "Advanced, Elite and World Class" */
    fun list(letters: List<String>): String {
        val names = letters.map(::of)
        if (names.size <= 1) return names.firstOrNull() ?: ""
        return names.dropLast(1).joinToString(", ") + " and " + names.last()
    }
}

object Motivation {
    val lines = listOf(
        "That lift was as solid as a lion.",
        "That bar moved like it owed you money.",
        "Steady as a rack bolted to bedrock.",
        "Smooth as chalk on a cold bar.",
        "Those plates went up like they were foam.",
        "Braced like a bridge in a storm.",
        "That pull came off the floor like it was late for work.",
        "Locked out like a vault door.",
        "That set moved like gravity took the day off.",
        "Tight as a belt on the third notch.",
        "You drove through the floor like it owed you a push.",
        "Bar path straight as a plumb line.",
        "Quiet bar. Loud result.",
        "That rep looked easy. It wasn't.",
    )

    /** Sum of the key's code points modulo the list - the same as the web and
     *  iOS, so all three apps say the same line. */
    fun line(key: String): String {
        val total = key.codePoints().toArray().sum()
        return lines[total % lines.size]
    }
}

/** 85.0 -> "85", 82.5 -> "82.5" - the same way the backend prints numbers. */
fun formatNumber(value: Double): String {
    if (value == Math.rint(value)) return value.toLong().toString()
    return String.format(Locale.US, "%.2f", value).trimEnd('0').trimEnd('.')
}

/** "Sree Ram" -> "SR" */
fun initials(name: String): String =
    name.split(' ').filter { it.isNotEmpty() }.take(2).mapNotNull { it.firstOrNull() }.joinToString("").uppercase()

/** "1 program", "3 programs". */
fun plural(count: Int, noun: String): String = "$count $noun${if (count == 1) "" else "s"}"

fun parseServerDate(text: String): Instant? = runCatching { OffsetDateTime.parse(text).toInstant() }
    .recoverCatching { Instant.parse(text) }
    .getOrNull()

private fun daysUntil(endsAt: String, now: Instant): Int {
    val end = parseServerDate(endsAt) ?: return 0
    return maxOf(0, ceil((end.epochSecond - now.epochSecond) / 86_400.0).toInt())
}

fun String.capitalizedFirst(): String = replaceFirstChar { it.titlecase(Locale.US) }

/** Swift's .capitalized: every word starts upper case, the rest lower. */
fun String.capitalizedWords(): String =
    split(' ').joinToString(" ") { word -> word.lowercase(Locale.US).replaceFirstChar { it.titlecase(Locale.US) } }
