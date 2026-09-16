//
//  Models.swift
//  MetalARM
//
//  Mirrors backend/app/schemas/{auth,user,profile,workout,party}.py. Keys are
//  decoded with .convertFromSnakeCase; ids and timestamps stay strings.
//  Points, XP and records always come from the server - never computed here.
//

import Foundation

// MARK: - Auth

struct TokenPair: Codable, Equatable {
    var accessToken: String
    var tokenType: String
    var expiresIn: Int
    var refreshToken: String
    var refreshExpiresIn: Int
}

// MARK: - Account and progression

struct ProgressInfo: Codable, Equatable {
    var totalXp: Int
    var currentLevel: Int
    var pointsBalance: Int
    var longestStreak: Int
    var lastCompletedOn: String?
    var xpIntoLevel: Int
    var xpForNextLevel: Int
    var currentStreak: Int
    var streakIsActive: Bool
    var rank: String
    var rankByLevel: String
    var nextRank: String?
    var nextRankLevel: Int?
    var nextRankStreak: Int?
    /// The strength trial between the user and the next rank, e.g.
    /// "Barbell Bench Press at 1x bodyweight".
    var nextRankTrial: String?
    /// Rank trials passed so far, e.g. "BA".
    var trialsPassed: String?

    var xpProgress: Double {
        xpForNextLevel > 0 ? min(1, Double(xpIntoLevel) / Double(xpForNextLevel)) : 0
    }
}

struct UserInfo: Codable, Equatable {
    var id: String
    var email: String
    var displayName: String
    var timezone: String
    var createdAt: String
    var weightUnit: String
}

struct Me: Codable, Equatable {
    var id: String
    var email: String
    var displayName: String
    var timezone: String
    var createdAt: String
    var weightUnit: String
    var progress: ProgressInfo
    var characterClass: String?
}

struct Badge: Codable, Equatable, Identifiable {
    var id: String
    var name: String
    var description: String
    var icon: String
    var earned: Bool
    var progress: Int
    var target: Int
    var percent: Int
}

struct LifetimeStats: Codable, Equatable {
    var questsCompleted: Int
    var partyQuestsCompleted: Int
    var rewardsRedeemed: Int
    var pointsEarned: Int
    var pointsSpent: Int
    var partiesJoined: Int
    var partyXpContributed: Int
    var memberSince: String
    var workoutsCompleted: Int
    var workoutPrs: Int
    var totalVolumeKg: Double
    var longestWorkoutStreak: Int
}

struct Profile: Codable, Equatable {
    var user: UserInfo
    var progress: ProgressInfo
    var stats: LifetimeStats
    var badges: [Badge]
    var badgesEarned: Int
    var badgesTotal: Int
}

// MARK: - Exercises

struct Exercise: Codable, Equatable, Hashable, Identifiable {
    var id: String
    var name: String
    var slug: String?
    var category: String
    var primaryMuscleGroups: [String]
    var equipment: String
    var instructions: String?
    var mediaUrl: String?
    var isCustom: Bool
    var isArchived: Bool

    var muscleLabel: String {
        primaryMuscleGroups.map { $0.replacingOccurrences(of: "_", with: " ") }.joined(separator: ", ").capitalized
    }
}

struct HistoryPoint: Codable, Equatable, Identifiable {
    var sessionId: String
    var performedAt: String
    var topWeightKg: Double?
    var topWeightReps: Int?
    var bestEst1rm: Double?
    var volumeKg: Double
    var workingSets: Int
    var totalReps: Int

    var id: String { sessionId }
}

/// What to try next on an exercise (backend app/core/progression_hints.py).
/// `kind` is progress, plateau or deload.
struct ProgressionHint: Codable, Equatable {
    var kind: String
    var text: String
    var targetWeightKg: Double?
    var targetReps: Int?
}

struct LastPerformance: Codable, Equatable {
    var exerciseId: String
    var sessionId: String?
    var performedAt: String?
    var sets: [WorkoutSet]
    var hint: ProgressionHint?
}

// MARK: - Sessions and sets

struct WorkoutSet: Codable, Equatable, Identifiable {
    var id: String
    var sessionId: String
    var exerciseId: String
    var setNumber: Int
    var weightKg: Double
    var reps: Int?
    var rpe: Double?
    var isWarmup: Bool
    var isPr: Bool
    var durationSeconds: Int?
    var distanceM: Double?
    var completedAt: String
}

struct SessionTarget: Codable, Equatable {
    var targetSets: Int?
    var targetReps: Int?
    var targetWeightKg: Double?
    var restSeconds: Int?
}

struct SessionExercise: Codable, Equatable, Identifiable {
    var exercise: Exercise
    var target: SessionTarget?
    var sets: [WorkoutSet]
    // The last completed session's sets on this exercise: the ghost values.
    var previousSets: [WorkoutSet]
    var hint: ProgressionHint?

    var id: String { exercise.id }
}

struct WorkoutSession: Codable, Equatable, Identifiable {
    var id: String
    var name: String?
    var status: String
    var routineId: String?
    var startedAt: String
    var endedAt: String?
    var durationSeconds: Int
    var workingSets: Int
    var totalVolumeKg: Double
    var pointsTotal: Int
    var pointsCredited: Int
    var qualified: Bool?
    var exercises: [SessionExercise]
}

struct ActiveSession: Codable, Equatable {
    var session: WorkoutSession?
}

struct Award: Codable, Equatable {
    var sourceType: String
    var points: Int
    var reason: String
}

struct PREvent: Codable, Equatable {
    var exerciseId: String
    var exerciseName: String
    var recordType: String
    var value: Double
    var weightKg: Double?
    var previousValue: Double?
    var isBaseline: Bool
    var bonusAwarded: Bool
    var setId: String?
}

struct ProgressionDelta: Codable, Equatable {
    var xpAwarded: Int
    var pointsAwarded: Int
    var totalXp: Int
    var levelBefore: Int
    var levelAfter: Int
    var rankBefore: String
    var rankAfter: String
    var currentStreak: Int
    var longestStreak: Int
    var leveledUp: Bool
    var rankedUp: Bool
}

struct SetLogResult: Codable, Equatable {
    var loggedSet: WorkoutSet
    var prEvents: [PREvent]
    var awards: [Award]
    var pointsAwarded: Int
    var sessionPoints: Int
    var setCapReached: Bool
    var progression: ProgressionDelta
    var isDuplicate: Bool

    enum CodingKeys: String, CodingKey {
        case loggedSet = "set"
        case prEvents, awards, pointsAwarded, sessionPoints, setCapReached, progression, isDuplicate
    }
}

struct SessionSummary: Codable, Equatable {
    var id: String
    var name: String?
    var status: String
    var startedAt: String
    var endedAt: String?
    var durationSeconds: Int
    var workingSets: Int
    var exerciseCount: Int
    var totalVolumeKg: Double
    var pointsTotal: Int
    var prCount: Int
}

struct Streak: Codable, Equatable {
    var weeks: Int
    var thisWeekSessions: Int
    var target: Int
    var thisWeekDone: Bool
    var sessionsToGo: Int
}

struct PointsBreakdown: Codable, Equatable {
    var setPoints: Int
    var prBonus: Int
    var sessionBonus: Int
    var streakBonus: Int
    var reversals: Int
    var total: Int
}

struct FinishResult: Codable, Equatable {
    var session: SessionSummary
    // False: under 10 minutes or fewer than 3 working sets - no completion
    // bonus and no streak credit, but set points still count.
    var qualified: Bool
    var awards: [Award]
    var breakdown: PointsBreakdown
    var pointsCredited: Int
    var prEvents: [PREvent]
    var streak: Streak
    var progression: ProgressionDelta
}

struct PointsSummary: Codable, Equatable {
    var totalPoints: Int
    var thisWeekPoints: Int
    var sessionsCompleted: Int
    var streak: Streak
}

struct WorkoutRecord: Codable, Equatable, Identifiable {
    var exerciseId: String
    var exerciseName: String
    var recordType: String
    var value: Double
    var weightKg: Double?
    var achievedAt: String
    var sessionId: String
    var setId: String?

    var id: String { "\(exerciseId)-\(recordType)-\(weightKg ?? 0)" }
}

// MARK: - Parties

struct Party: Codable, Equatable, Identifiable {
    var id: String
    var name: String
    var ownerId: String
    var maxMembers: Int
    var memberCount: Int
    var isActive: Bool
    var createdAt: String
    var myRole: String
    var inviteCode: String?
    var totalPartyXp: Int
}

struct PartyBoardEntry: Codable, Equatable, Identifiable {
    var position: Int
    var userId: String
    var displayName: String
    var points: Int
    var workouts: Int
    var level: Int
    var rank: String
    var isMe: Bool

    var id: String { userId }
}

struct PartyBoard: Codable, Equatable {
    var partyId: String
    var period: String
    var periodStart: String?
    var entries: [PartyBoardEntry]
}

struct RaidHitter: Codable, Equatable, Identifiable {
    var userId: String
    var displayName: String
    var damage: Int
    var hits: Int
    var isMe: Bool

    var id: String { userId }
}

/// This week's party boss (GET /parties/{id}/raid; the rules are in the
/// backend's app/core/raids.py). Every finished workout hits it for the
/// weight lifted; on days nobody trains it heals.
/// GET /profile/character: one character stat, 0-100 with the number behind it.
struct CharacterStat: Codable, Equatable, Identifiable {
    var key: String
    var label: String
    var value: Int
    var detail: String
    var highlighted: Bool

    var id: String { key }
    var fraction: Double { min(1, max(0, Double(value) / 100)) }
}

/// The character sheet. The class only highlights stats - it changes no score.
struct CharacterSheet: Codable, Equatable {
    var characterClass: String
    var classLabel: String
    var stats: [CharacterStat]
}

/// POST /workouts/import: what a Strong or Hevy export added to the history.
struct WorkoutImportResult: Codable, Equatable {
    var source: String
    var workoutsImported: Int
    var setsImported: Int
    var workoutsSkipped: Int
    var rowsSkipped: Int
    var exercisesCreated: [String]
    var xpAwarded: Int
    var duplicate: Bool
    var progression: ProgressionDelta?

    var summary: String {
        if duplicate { return "That file was already imported - nothing changed." }
        let app = source == "strong" ? "Strong" : "Hevy"
        var parts = ["Imported \(workoutsImported) workout\(workoutsImported == 1 ? "" : "s") (\(setsImported) sets) from \(app)."]
        if workoutsSkipped > 0 { parts.append("\(workoutsSkipped) already in your history.") }
        if !exercisesCreated.isEmpty {
            parts.append("\(exercisesCreated.count) new exercise\(exercisesCreated.count == 1 ? "" : "s") added.")
        }
        if xpAwarded > 0 { parts.append("+\(xpAwarded) XP.") }
        return parts.joined(separator: " ")
    }
}

/// GET /profile/trials: a strength standard that gates rank B, A or S.
struct RankTrial: Codable, Equatable, Identifiable {
    var rank: String
    var lift: String
    var description: String
    var multiplier: Double
    /// Nil until a bodyweight is logged.
    var targetKg: Double?
    var bestKg: Double?
    var passed: Bool

    var id: String { rank }

    /// How close the best lift is to the target, 0...1.
    var fraction: Double {
        guard let targetKg, targetKg > 0 else { return 0 }
        return min(1, (bestKg ?? 0) / targetKg)
    }
}

struct PartyRaid: Codable, Equatable {
    var partyId: String
    var weekKey: String
    var name: String
    var maxHp: Int
    var hpRemaining: Int
    var damageDealt: Int
    var healed: Int
    var idleDays: Int
    var defeated: Bool
    var defeatedAt: String?
    var endsAt: String
    var hitters: [RaidHitter]

    var hpFraction: Double { maxHp > 0 ? Double(hpRemaining) / Double(maxHp) : 0 }

    func daysLeft(from now: Date = .now) -> Int {
        guard let end = parseServerDate(endsAt) else { return 0 }
        return max(0, Int((end.timeIntervalSince(now) / 86_400).rounded(.up)))
    }
}

// MARK: - Units and wording

enum WeightUnit: String, Codable, CaseIterable, Identifiable {
    case kg, lb

    /// Exactly the backend's workout_rules.LB_TO_KG. Weights are stored in kg.
    static let kilogramsPerPound = 0.45359237

    var id: String { rawValue }

    func fromKilograms(_ kilograms: Double) -> Double {
        switch self {
        case .kg: kilograms
        // Pounds to one decimal: 80 kg reads 176.4 lb, not 176.36981...
        case .lb: ((kilograms / Self.kilogramsPerPound) * 10).rounded() / 10
        }
    }

    func format(kilograms: Double) -> String {
        "\(formatNumber(fromKilograms(kilograms))) \(rawValue)"
    }
}

extension PREvent {
    /// max_reps_at_weight carries reps in `value`; the other record types are kilograms.
    func headline(in unit: WeightUnit) -> String {
        switch recordType {
        case "max_weight": "New heaviest \(exerciseName): \(unit.format(kilograms: value))"
        case "est_1rm": "New est. 1RM on \(exerciseName): \(unit.format(kilograms: value))"
        case "max_volume": "New volume record on \(exerciseName): \(unit.format(kilograms: value))"
        case "max_reps_at_weight":
            "New rep record on \(exerciseName): \(Int(value)) reps at \(unit.format(kilograms: weightKg ?? 0))"
        default: "New record on \(exerciseName)"
        }
    }
}

extension Array where Element == PREvent {
    /// What to celebrate: the record that paid the PR bonus, else any genuine
    /// record. First-ever logs (baselines) are not celebrated.
    var celebrated: PREvent? {
        first(where: \.bonusAwarded) ?? first(where: { !$0.isBaseline })
    }
}

extension ProgressionDelta {
    var hint: String {
        if rankedUp { return "Rank up! You're now rank \(rankAfter)." }
        if leveledUp { return "Level up! You reached level \(levelAfter)." }
        return ""
    }
}

extension WorkoutRecord {
    static let displayOrder = ["max_weight", "est_1rm", "max_volume", "max_reps_at_weight"]

    var label: String {
        switch recordType {
        case "max_weight": "Heaviest"
        case "est_1rm": "Best est. 1RM"
        case "max_volume": "Best session volume"
        case "max_reps_at_weight": "Most reps"
        default: recordType
        }
    }

    func valueText(in unit: WeightUnit) -> String {
        recordType == "max_reps_at_weight"
            ? "\(Int(value)) reps @ \(unit.format(kilograms: weightKg ?? 0))"
            : unit.format(kilograms: value)
    }
}

/// 85.0 -> "85", 82.5 -> "82.5" - the same way the backend prints numbers.
func formatNumber(_ value: Double) -> String {
    if value == value.rounded() { return String(Int(value)) }
    var text = String(format: "%.2f", value)
    while text.hasSuffix("0") { text.removeLast() }
    return text
}

/// "Sree Ram" -> "SR"
func initials(of name: String) -> String {
    String(name.split(separator: " ").prefix(2).compactMap(\.first)).uppercased()
}

/// Pydantic timestamps carry microseconds ("…05.123456Z"), which
/// ISO8601DateFormatter does not reliably parse, so they are dropped first.
func parseServerDate(_ text: String) -> Date? {
    let trimmed = text.replacingOccurrences(of: #"\.\d+"#, with: "", options: .regularExpression)
    return ISO8601DateFormatter().date(from: trimmed)
}

extension String {
    var trimmed: String { trimmingCharacters(in: .whitespacesAndNewlines) }
}
