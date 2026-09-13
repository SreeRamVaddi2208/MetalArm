//
//  AppModel.swift
//  MetalARM
//
//  App-wide state, ported from AppState in frontend/frontend/state.py.
//

import Foundation
import Observation

@Observable
final class AppModel {
    struct ProgressTab: Identifiable, Hashable {
        let id: Int
        let name: String
    }

    static let restDuration = 90

    let api: MetalArmAPI

    // Home / user
    var user: User?
    var friendActivity: [FriendActivity] = []

    // Exercise library
    var exercises: [Exercise] = []

    // Active workout session
    var sessionID: Int?
    var activeExercise: Exercise?
    var setsLogged: [LoggedSet] = []
    var weightInput = "80"
    var repsInput = "8"
    var prHint = ""
    var restSecondsLeft = 0

    // Last finished session
    var summary: WorkoutSummary?
    var showingSummary = false

    // Progress tabs are resolved from /exercises by name: the seeded ids are not 1/2/3
    // (Squat is 3 and Deadlift is 5), so hardcoding ids shows the wrong exercise.
    static let progressExercises = [
        (tab: "Bench Press", exercise: "Barbell Bench Press"),
        (tab: "Squat", exercise: "Barbell Back Squat"),
        (tab: "Deadlift", exercise: "Conventional Deadlift"),
    ]
    var progressTabs: [ProgressTab] = []
    var selectedExerciseID = 1
    var progress: ProgressData?
    var records: [RecordItem] = []

    // Leaderboard / profile
    var leaderboard: [LeaderboardEntry] = []
    var profileStats: ProfileStats?
    var badges: [Badge] = []

    var errorMessage = ""

    @ObservationIgnored private var restTask: Task<Void, Never>?

    init(api: MetalArmAPI) {
        self.api = api
    }

    // MARK: - Derived values

    var sessionActive: Bool { sessionID != nil }

    var resting: Bool { restSecondsLeft > 0 }

    var activeExerciseMuscleLabel: String {
        activeExercise?.muscleGroups.joined(separator: ", ").capitalized ?? ""
    }

    var xpProgress: Double { user?.xpProgress ?? 0 }

    var summaryXPRemaining: Int { summary?.level.xpRemaining ?? 0 }

    var summaryXPProgress: Double { summary?.level.progress ?? 0 }

    var badgesEarnedCount: Int { badges.filter(\.earned).count }

    var restDisplay: String {
        let seconds = max(0, restSecondsLeft)
        return String(format: "%d:%02d", seconds / 60, seconds % 60)
    }

    // MARK: - Home

    func loadHome() async {
        do {
            user = try await api.me()
            friendActivity = try await api.friendActivity()
            errorMessage = ""
        } catch {
            errorMessage = "Couldn't reach the backend: \(error.localizedDescription)"
        }
    }

    // MARK: - Workout

    func startWorkout() async {
        do {
            if exercises.isEmpty {
                exercises = try await api.exercises()
            }
            // Single-exercise sessions for now, defaulting to bench — same as the web app.
            guard let bench = exercises.first(where: { $0.name.lowercased().contains("bench") }) ?? exercises.first else {
                errorMessage = "No exercises are available."
                return
            }
            let session = try await api.startSession()
            activeExercise = bench
            sessionID = session.id
            setsLogged = []
            prHint = ""
            weightInput = "80"
            repsInput = "8"
            stopRestTimer()
            errorMessage = ""
        } catch {
            errorMessage = "Couldn't start a session: \(error.localizedDescription)"
        }
    }

    func logCurrentSet() async {
        guard let weight = Double(weightInput.trimmingCharacters(in: .whitespaces)),
              let reps = Int(repsInput.trimmingCharacters(in: .whitespaces)) else {
            errorMessage = "Weight and reps need to be numbers."
            return
        }
        guard let sessionID, let exercise = activeExercise else {
            errorMessage = "Start a workout first."
            return
        }
        do {
            let result = try await api.logSet(sessionID: sessionID, exerciseID: exercise.id, weightKg: weight, reps: reps)
            setsLogged.append(result.loggedSet)
            if let pr = result.pr {
                let record = pr.recordType.replacingOccurrences(of: "_", with: " ")
                let previous = pr.previousValue.map { " (was \(formatNumber($0)))" } ?? ""
                prHint = "New \(record): \(formatNumber(pr.value))\(previous)"
            } else {
                prHint = ""
            }
            errorMessage = ""
            startRestTimer()
        } catch {
            errorMessage = "Couldn't log that set: \(error.localizedDescription)"
        }
    }

    func startRestTimer() {
        restTask?.cancel()
        restSecondsLeft = Self.restDuration
        restTask = Task { [weak self] in
            while !Task.isCancelled {
                try? await Task.sleep(for: .seconds(1))
                guard let self, !Task.isCancelled else { return }
                self.restSecondsLeft = max(0, self.restSecondsLeft - 1)
                if self.restSecondsLeft == 0 { return }
            }
        }
    }

    func stopRestTimer() {
        restTask?.cancel()
        restTask = nil
        restSecondsLeft = 0
    }

    func finishWorkout() async {
        guard let sessionID else { return }
        do {
            summary = try await api.finishSession(sessionID: sessionID)
            self.sessionID = nil
            activeExercise = nil
            stopRestTimer()
            errorMessage = ""
            showingSummary = true
            // Home's level/XP card should reflect the points just earned.
            if let refreshed = try? await api.me() {
                user = refreshed
            }
        } catch {
            errorMessage = "Couldn't finish the session: \(error.localizedDescription)"
        }
    }

    // MARK: - Progress

    func loadProgress() async {
        do {
            if exercises.isEmpty {
                exercises = try await api.exercises()
            }
        } catch {
            errorMessage = "Couldn't load progress: \(error.localizedDescription)"
            return
        }
        progressTabs = Self.progressExercises.compactMap { entry in
            exercises.first { $0.name == entry.exercise }.map { ProgressTab(id: $0.id, name: entry.tab) }
        }
        if !progressTabs.contains(where: { $0.id == selectedExerciseID }), let first = progressTabs.first {
            selectedExerciseID = first.id
        }
        await selectExercise(selectedExerciseID)
    }

    func selectExercise(_ exerciseID: Int) async {
        selectedExerciseID = exerciseID
        do {
            progress = try await api.progress(exerciseID: exerciseID)
            records = try await api.records(exerciseID: exerciseID)
            errorMessage = ""
        } catch {
            errorMessage = "Couldn't load progress: \(error.localizedDescription)"
        }
    }

    // MARK: - Leaderboard

    func loadLeaderboard() async {
        do {
            leaderboard = try await api.leaderboard()
            errorMessage = ""
        } catch {
            errorMessage = "Couldn't load the leaderboard: \(error.localizedDescription)"
        }
    }

    // MARK: - Profile

    func loadProfile() async {
        do {
            let data = try await api.profile()
            var profileUser = data.user
            profileUser.streakDays = data.stats.streakDays
            user = profileUser
            profileStats = data.stats
            badges = data.badges
            errorMessage = ""
        } catch {
            errorMessage = "Couldn't load your profile: \(error.localizedDescription)"
        }
    }
}
