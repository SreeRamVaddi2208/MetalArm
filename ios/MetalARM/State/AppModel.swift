//
//  AppModel.swift
//  MetalARM
//
//  App-wide state. Mirrors the behaviour rules in docs/workouts-api.md:
//  rehydrate the live workout on load, send a fresh client_set_id per tap,
//  celebrate from the response, and never compute points on the device.
//

import Foundation
import Observation

@Observable
final class AppModel {
    struct ProgressTab: Identifiable, Hashable {
        let id: String
        let name: String
    }

    static let defaultRestSeconds = 90
    // Shown on the Progress screen until the user has records of their own.
    static let starterExercises = ["Barbell Bench Press", "Barbell Back Squat", "Conventional Deadlift"]

    let api: MetalArmAPI
    private(set) var isSignedIn: Bool

    // Home
    var me: Me?
    var points: PointsSummary?

    // Workout
    var session: WorkoutSession?
    // Chosen in the picker but with no set logged yet, so not on the server.
    var pendingExercises: [Exercise] = []
    var ghostSets: [String: [WorkoutSet]] = [:]
    var selectedExerciseID: String?
    var weightInput = ""
    var repsInput = ""
    var prHint = ""
    var progressionHint = ""
    var restSecondsLeft = 0
    var pickerResults: [Exercise] = []
    var finishResult: FinishResult?
    var showingSummary = false

    // Progress
    var progressTabs: [ProgressTab] = []
    var selectedProgressID: String?
    var history: [HistoryPoint] = []
    var records: [WorkoutRecord] = []

    // Ranks
    var parties: [Party] = []
    var selectedPartyID: String?
    var partyBoard: PartyBoard?

    // Profile
    var profile: Profile?

    var errorMessage = ""
    var isBusy = false

    @ObservationIgnored private var restTask: Task<Void, Never>?

    init(api: MetalArmAPI) {
        self.api = api
        isSignedIn = api.isSignedIn
        api.onSignedOut = { [weak self] in self?.resetAfterSignOut() }
    }

    // MARK: - Derived values

    var weightUnit: WeightUnit {
        WeightUnit(rawValue: me?.weightUnit ?? profile?.user.weightUnit ?? "kg") ?? .kg
    }

    var sessionActive: Bool { session != nil }

    var resting: Bool { restSecondsLeft > 0 }

    var restDisplay: String {
        let seconds = max(0, restSecondsLeft)
        return String(format: "%d:%02d", seconds / 60, seconds % 60)
    }

    var xpProgress: Double { me?.progress.xpProgress ?? profile?.progress.xpProgress ?? 0 }

    /// Exercises on the workout board: those with sets (server order), then ones just added.
    var workoutExercises: [Exercise] {
        let logged = session?.exercises.map(\.exercise) ?? []
        return logged + pendingExercises.filter { pending in !logged.contains { $0.id == pending.id } }
    }

    var selectedExercise: Exercise? { workoutExercises.first { $0.id == selectedExerciseID } }

    var selectedSessionExercise: SessionExercise? {
        session?.exercises.first { $0.exercise.id == selectedExerciseID }
    }

    /// Last session's sets for the selected exercise - the ghost values.
    var selectedPreviousSets: [WorkoutSet] {
        guard let selectedExerciseID else { return [] }
        let fromSession = selectedSessionExercise?.previousSets ?? []
        return fromSession.isEmpty ? ghostSets[selectedExerciseID] ?? [] : fromSession
    }

    var setsLoggedCount: Int { session?.exercises.reduce(0) { $0 + $1.sets.count } ?? 0 }

    var selectedParty: Party? { parties.first { $0.id == selectedPartyID } }

    // MARK: - Account

    func signIn(email: String, password: String) async {
        await run("Couldn't sign in") {
            try await api.signIn(email: email.trimmed, password: password)
            isSignedIn = true
        }
    }

    func signUp(email: String, password: String, displayName: String) async {
        await run("Couldn't create your account") {
            try await api.signUp(
                email: email.trimmed, password: password, displayName: displayName.trimmed,
                timezone: TimeZone.current.identifier)
            isSignedIn = true
        }
    }

    func signOut() {
        api.signOut()
        resetAfterSignOut()
    }

    func signOutEverywhere() async {
        var succeeded = false
        await run("Couldn't sign out of other devices") {
            try await api.signOutEverywhere()
            succeeded = true
        }
        if succeeded { resetAfterSignOut() }
    }

    /// Returns whether the account was deleted.
    func deleteAccount(password: String) async -> Bool {
        var deleted = false
        await run("Couldn't delete your account") {
            try await api.deleteAccount(password: password)
            deleted = true
        }
        if deleted { resetAfterSignOut() }
        return deleted
    }

    private func resetAfterSignOut() {
        isSignedIn = false
        me = nil
        points = nil
        profile = nil
        clearWorkout()
        ghostSets = [:]
        finishResult = nil
        showingSummary = false
        progressTabs = []
        selectedProgressID = nil
        history = []
        records = []
        parties = []
        selectedPartyID = nil
        partyBoard = nil
    }

    // MARK: - Home

    func loadHome() async {
        await run("Couldn't load your stats") {
            me = try await api.me()
            points = try await api.points()
            session = try await api.activeSession()
        }
        if selectedExercise == nil { selectDefaultExercise() }
    }

    // MARK: - Workout

    func loadWorkout() async {
        await run("Couldn't load your workout") {
            session = try await api.activeSession()
        }
        if selectedExercise == nil { selectDefaultExercise() }
    }

    func startWorkout() async {
        await run("Couldn't start a workout") {
            do {
                session = try await api.startSession()
            } catch let error as APIError where error.status == 409 {
                // One is already live (started on another device): resume it.
                session = try await api.activeSession()
            }
            pendingExercises = []
            prHint = ""
            progressionHint = ""
            stopRestTimer()
        }
        selectDefaultExercise()
    }

    func searchExercises(_ query: String) async {
        await run("Couldn't search exercises") {
            pickerResults = try await api.searchExercises(query: query)
        }
    }

    func addExercise(_ exercise: Exercise) async {
        if !workoutExercises.contains(where: { $0.id == exercise.id }) {
            pendingExercises.append(exercise)
        }
        if ghostSets[exercise.id] == nil, let sets = try? await api.lastPerformance(exerciseID: exercise.id) {
            ghostSets[exercise.id] = sets
        }
        select(exercise.id)
    }

    func select(_ exerciseID: String) {
        selectedExerciseID = exerciseID
        prefillInputs()
    }

    private func selectDefaultExercise() {
        if let id = session?.exercises.last?.exercise.id ?? pendingExercises.last?.id {
            select(id)
        } else {
            selectedExerciseID = nil
        }
    }

    /// This session's last set on the exercise, else last time's, else blank.
    private func prefillInputs() {
        guard let reference = selectedSessionExercise?.sets.last ?? selectedPreviousSets.first else {
            weightInput = ""
            repsInput = ""
            return
        }
        weightInput = formatNumber(weightUnit.fromKilograms(reference.weightKg))
        repsInput = reference.reps.map(String.init) ?? ""
    }

    func logSet() async {
        guard let current = session, let exercise = selectedExercise else {
            errorMessage = "Add an exercise first."
            return
        }
        guard let weight = Double(weightInput.trimmed.replacingOccurrences(of: ",", with: ".")), weight >= 0,
              let reps = Int(repsInput.trimmed), reps > 0 else {
            errorMessage = "Enter a weight and a number of reps."
            return
        }
        // One id per tap: a retry of this same request can never log twice.
        let clientSetID = UUID()
        await run("Couldn't log that set") {
            let result = try await api.logSet(
                sessionID: current.id, exerciseID: exercise.id, weight: weight, unit: weightUnit,
                reps: reps, clientSetID: clientSetID)
            prHint = result.prEvents.celebrated?.headline(in: weightUnit) ?? ""
            progressionHint = result.progression.hint
            session = try await api.session(id: current.id)
            pendingExercises.removeAll { $0.id == exercise.id }
            let rest = selectedSessionExercise?.target?.restSeconds ?? Self.defaultRestSeconds
            startRestTimer(seconds: rest)
        }
    }

    func finishWorkout() async {
        guard let current = session else { return }
        await run("Couldn't finish the workout") {
            finishResult = try await api.finishSession(sessionID: current.id)
            clearWorkout()
            showingSummary = true
        }
        await refreshStats()
    }

    func abandonWorkout() async {
        guard let current = session else { return }
        await run("Couldn't discard the workout") {
            try await api.abandonSession(sessionID: current.id)
            clearWorkout()
        }
        await refreshStats()
    }

    private func refreshStats() async {
        if let latest = try? await api.me() { me = latest }
        if let latest = try? await api.points() { points = latest }
    }

    private func clearWorkout() {
        session = nil
        pendingExercises = []
        selectedExerciseID = nil
        weightInput = ""
        repsInput = ""
        prHint = ""
        progressionHint = ""
        stopRestTimer()
    }

    func startRestTimer(seconds: Int = defaultRestSeconds) {
        restTask?.cancel()
        restSecondsLeft = seconds
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

    // MARK: - Progress

    func loadProgress() async {
        await run("Couldn't load progress") {
            var tabs: [ProgressTab] = []
            for record in try await api.records(exerciseID: nil) where !tabs.contains(where: { $0.id == record.exerciseId }) {
                tabs.append(ProgressTab(id: record.exerciseId, name: record.exerciseName))
            }
            if tabs.isEmpty {
                for name in Self.starterExercises {
                    if let match = try await api.searchExercises(query: name).first(where: { $0.name == name }) {
                        tabs.append(ProgressTab(id: match.id, name: match.name))
                    }
                }
            }
            progressTabs = tabs
        }
        let keep = progressTabs.contains { $0.id == selectedProgressID }
        if let id = keep ? selectedProgressID : progressTabs.first?.id {
            await selectProgress(id)
        }
    }

    func selectProgress(_ exerciseID: String) async {
        selectedProgressID = exerciseID
        await run("Couldn't load progress") {
            history = try await api.exerciseHistory(exerciseID: exerciseID)
            records = try await api.records(exerciseID: exerciseID)
        }
    }

    // MARK: - Ranks

    func loadParties() async {
        await run("Couldn't load your parties") {
            parties = try await api.parties().filter(\.isActive)
            if !parties.contains(where: { $0.id == selectedPartyID }) {
                selectedPartyID = parties.first?.id
            }
            partyBoard = try await selectedPartyID.asyncMap { try await api.partyLeaderboard(partyID: $0) }
        }
    }

    func selectParty(_ partyID: String) async {
        selectedPartyID = partyID
        await run("Couldn't load the leaderboard") {
            partyBoard = try await api.partyLeaderboard(partyID: partyID)
        }
    }

    func createParty(name: String) async {
        guard !name.trimmed.isEmpty else { return }
        var created: Party?
        await run("Couldn't create the party") {
            created = try await api.createParty(name: name.trimmed)
        }
        if let created {
            selectedPartyID = created.id
            await loadParties()
        }
    }

    func joinParty(inviteCode: String) async {
        guard !inviteCode.trimmed.isEmpty else { return }
        var joined: Party?
        await run("Couldn't join the party") {
            joined = try await api.joinParty(inviteCode: inviteCode.trimmed.uppercased())
        }
        if let joined {
            selectedPartyID = joined.id
            await loadParties()
        }
    }

    // MARK: - Profile

    func loadProfile() async {
        await run("Couldn't load your profile") {
            profile = try await api.profile()
        }
    }

    func setWeightUnit(_ unit: WeightUnit) async {
        guard unit != weightUnit else { return }
        await run("Couldn't change the weight unit") {
            me = try await api.updateWeightUnit(unit)
            profile = try await api.profile()
        }
        prefillInputs()
    }

    // MARK: - Errors

    private func run(_ context: String, _ work: () async throws -> Void) async {
        isBusy = true
        defer { isBusy = false }
        do {
            try await work()
            errorMessage = ""
        } catch APIError.signedOut {
            errorMessage = APIError.signedOut.localizedDescription
        } catch {
            errorMessage = "\(context): \(error.localizedDescription)"
        }
    }
}

private extension Optional {
    func asyncMap<T>(_ transform: (Wrapped) async throws -> T) async rethrows -> T? {
        guard let self else { return nil }
        return try await transform(self)
    }
}
