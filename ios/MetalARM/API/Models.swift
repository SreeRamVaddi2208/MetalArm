//
//  Models.swift
//  MetalARM
//
//  Mirrors the response shapes in API_CONTRACT.md. Keys are decoded with
//  .convertFromSnakeCase, so `level_name` maps to `levelName`.
//

import Foundation

struct User: Codable, Equatable {
    var id: Int
    var name: String
    var level: Int
    var levelName: String
    var xpCurrent: Int
    var xpToNextLevel: Int
    // GET /profile nests the user without streak_days (it lives under `stats` there).
    var streakDays: Int?

    var xpProgress: Double {
        xpToNextLevel > 0 ? min(1, Double(xpCurrent) / Double(xpToNextLevel)) : 0
    }
}

struct Exercise: Codable, Equatable, Identifiable {
    var id: Int
    var name: String
    var category: String
    var muscleGroups: [String]
    var equipment: String
}

struct SessionStart: Codable, Equatable {
    var id: Int
    var userId: Int
    var startedAt: String
    var status: String
}

struct LoggedSet: Codable, Equatable, Identifiable {
    var id: Int
    var sessionId: Int
    var exerciseId: Int
    var setNumber: Int
    var weightKg: Double
    var reps: Int
    var isWarmup: Bool
    var isPr: Bool
}

struct SetPR: Codable, Equatable {
    var recordType: String
    var value: Double
    var previousValue: Double?
}

struct LogSetResult: Codable, Equatable {
    var loggedSet: LoggedSet
    var pr: SetPR?
    var pointsAwarded: Int

    enum CodingKeys: String, CodingKey {
        case loggedSet = "set"
        case pr
        case pointsAwarded
    }
}

struct PointsBreakdown: Codable, Equatable {
    var sets: Int
    var sessionCompleted: Int
    var prBonus: Int
    var streakBonus: Int
}

struct NewPR: Codable, Equatable {
    var exerciseName: String
    var recordType: String
    var value: Double
    var reps: Int
}

struct LevelInfo: Codable, Equatable {
    var level: Int
    var levelName: String
    var xpCurrent: Int
    var xpToNextLevel: Int
    var leveledUp: Bool

    var progress: Double {
        xpToNextLevel > 0 ? min(1, Double(xpCurrent) / Double(xpToNextLevel)) : 0
    }

    var xpRemaining: Int { max(0, xpToNextLevel - xpCurrent) }
}

struct WorkoutSummary: Codable, Equatable {
    var durationMin: Int
    var totalVolumeKg: Double
    var totalSets: Int
    var pointsBreakdown: PointsBreakdown
    var totalPoints: Int
    var newPrs: [NewPR]
    var level: LevelInfo
}

extension WorkoutSummary {
    /// The PR to celebrate, using the backend's headline priority (pr_logic.best_pr).
    /// new_prs is sorted by record type, so its first entry is not necessarily the best one.
    var headlinePR: NewPR? {
        let priority = ["max_weight", "est_1rm", "max_volume", "max_reps_at_weight"]
        func rank(_ pr: NewPR) -> Int { priority.firstIndex(of: pr.recordType) ?? priority.count }
        return newPrs.min { rank($0) < rank($1) }
    }
}

extension NewPR {
    /// max_reps_at_weight stores reps in `value`, so each record type reads differently.
    var detail: String {
        switch recordType {
        case "max_weight": "\(formatNumber(value)) kg × \(reps) reps"
        case "est_1rm": "est. 1RM \(formatNumber(value)) kg"
        case "max_volume": "\(formatNumber(value)) kg set volume"
        case "max_reps_at_weight": "\(reps) reps (most at this weight)"
        default: formatNumber(value)
        }
    }
}

struct ProgressPoint: Codable, Equatable, Identifiable {
    var date: String
    var value: Double

    var id: String { date }
}

struct ProgressData: Codable, Equatable {
    var exerciseName: String
    var metric: String
    var unit: String
    var currentValue: Double
    var changeSinceStart: Double
    var points: [ProgressPoint]
}

struct RecordItem: Codable, Equatable, Identifiable {
    var recordType: String
    var label: String
    var value: Double
    var unit: String
    var detail: String
    var achievedAt: String

    var id: String { recordType }
}

struct LeaderboardEntry: Codable, Equatable, Identifiable {
    var rank: Int
    var userId: Int
    var name: String
    var points: Int
    var isCurrentUser: Bool
    var streakDays: Int?

    var id: Int { userId }
}

struct ProfileStats: Codable, Equatable {
    var workouts: Int
    var streakDays: Int
    var prsSet: Int
}

struct Badge: Codable, Equatable, Identifiable {
    var id: String
    var name: String
    var earned: Bool
}

struct ProfileData: Codable, Equatable {
    var user: User
    var stats: ProfileStats
    var badges: [Badge]
}

struct FriendActivity: Codable, Equatable, Identifiable {
    var userName: String
    var text: String
    var hoursAgo: Int

    var id: String { "\(userName)-\(text)" }
}

/// 85.0 -> "85", 82.5 -> "82.5" — the same way the backend and web app print numbers.
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
