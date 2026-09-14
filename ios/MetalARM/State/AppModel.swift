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
    // Logged with no connection; sent in order once the network is back.
    private(set) var pendingSets: [PendingSet] = []

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
    @ObservationIgnored private let pendingStore: PendingSetStore
    @ObservationIgnored private let connectivity = ConnectivityMonitor()
    @ObservationIgnored private var isFlushing = false

    init(api: MetalArmAPI, pendingStore: PendingSetStore = .inMemory) {
        self.api = api
        self.pendingStore = pendingStore
        isSignedIn = api.isSignedIn
        pendingSets = pendingStore.load()
        api.onSignedOut = { [weak self] in self?.resetAfterSignOut() }
    }

    /// Sends queued sets whenever the network comes back.
    func startSyncingWhenOnline() {
        connectivity.start { [weak self] in
            Task { await self?.flushPendingSets() }
        }
    }

    // MARK: - Derived values

    /// The party to invite friends into from a share card: the one on the
    /// Ranks tab, else the first.
    var shareInviteCode: String? {
        parties.first { $0.id == selectedPartyID }?.inviteCode ?? parties.first?.inviteCode
    }

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

    /// Signs out at once; telling the server (which may be slow or offline)
    /// happens afterwards and never holds the user on a signed-in screen.
    func signOut() async {
        resetAfterSignOut()
        await api.signOut()
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
        pendingSets = []
        pendingStore.save([])
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
        await flushPendingSets()
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
        // One id per tap: a retry of this same set - now, or after the phone was
        // offline - can never log it twice.
        let set = PendingSet(
            clientSetID: UUID(), sessionID: current.id, exerciseID: exercise.id, weight: weight, unit: weightUnit,
            reps: reps)
        let rest = selectedSessionExercise?.target?.restSeconds ?? Self.defaultRestSeconds

        // Sets already waiting go first, so the server gets them in the order they were done.
        guard pendingSets.isEmpty else {
            queue(set)
            startRestTimer(seconds: rest)
            await flushPendingSets()
            return
        }

        isBusy = true
        defer { isBusy = false }
        do {
            let result = try await send(set)
            prHint = result.prEvents.celebrated?.headline(in: weightUnit) ?? ""
            progressionHint = result.progression.hint
            session = try await api.session(id: current.id)
            pendingExercises.removeAll { $0.id == exercise.id }
            errorMessage = ""
            startRestTimer(seconds: selectedSessionExercise?.target?.restSeconds ?? rest)
        } catch let error where error.isConnectivityFailure {
            // No answer from the server: keep the set and send it when the network is back.
            // If it did arrive and only the answer was lost, the resend is ignored.
            queue(set)
            errorMessage = ""
            startRestTimer(seconds: rest)
        } catch APIError.signedOut {
            errorMessage = APIError.signedOut.localizedDescription
        } catch {
            errorMessage = "Couldn't log that set: \(error.localizedDescription)"
        }
    }

    /// Sets saved offline for this exercise in the current workout.
    func queuedSets(for exerciseID: String) -> [PendingSet] {
        pendingSets.filter { $0.sessionID == session?.id && $0.exerciseID == exerciseID }
    }

    var syncStatusText: String {
        let count = pendingSets.count
        return count == 1
            ? "1 set saved offline. It'll sync when you're back online."
            : "\(count) sets saved offline. They'll sync when you're back online."
    }

    /// Sends queued sets in order. Stops at the first one that still can't
    /// reach the server; drops (and reports) any the server rejects - say,
    /// because that workout was finished on another device.
    func flushPendingSets() async {
        guard !isFlushing, !pendingSets.isEmpty else { return }
        isFlushing = true
        defer { isFlushing = false }

        var sentAny = false
        var rejections: [String] = []
        while let next = pendingSets.first {
            do {
                let result = try await send(next)
                sentAny = true
                if let headline = result.prEvents.celebrated?.headline(in: weightUnit) { prHint = headline }
                progressionHint = result.progression.hint
            } catch let error where error.isConnectivityFailure {
                break
            } catch APIError.signedOut {
                break
            } catch {
                rejections.append(error.localizedDescription)
            }
            pendingSets.removeFirst()
            pendingStore.save(pendingSets)
        }

        if let first = rejections.first {
            errorMessage = rejections.count == 1
                ? "A set saved offline couldn't be logged: \(first)"
                : "\(rejections.count) sets saved offline couldn't be logged: \(first)"
        }
        if sentAny, let current = session {
            if let latest = try? await api.session(id: current.id) { session = latest }
            let logged = Set(session?.exercises.map(\.exercise.id) ?? [])
            pendingExercises.removeAll { logged.contains($0.id) }
        }
    }

    private func send(_ set: PendingSet) async throws -> SetLogResult {
        try await api.logSet(
            sessionID: set.sessionID, exerciseID: set.exerciseID, weight: set.weight, unit: set.unit,
            reps: set.reps, clientSetID: set.clientSetID)
    }

    private func queue(_ set: PendingSet) {
        pendingSets.append(set)
        pendingStore.save(pendingSets)
    }

    func finishWorkout() async {
        guard let current = session else { return }
        // Queued sets have to reach the server first, or they wouldn't count.
        await flushPendingSets()
        let unsynced = pendingSets.filter { $0.sessionID == current.id }.count
        guard unsynced == 0 else {
            errorMessage = "\(unsynced) \(unsynced == 1 ? "set hasn't" : "sets haven't") synced yet. "
                + "Finish once you're back online so they count."
            return
        }
        await run("Couldn't finish the workout") {
            finishResult = try await api.finishSession(sessionID: current.id)
            clearWorkout()
            // The share card carries the party invite code; parties load on the
            // Ranks tab, which the user may not have opened yet.
            if parties.isEmpty, let loaded = try? await api.parties() {
                parties = loaded.filter(\.isActive)
            }
            showingSummary = true
        }
        await refreshStats()
    }

    func abandonWorkout() async {
        guard let current = session else { return }
        await run("Couldn't discard the workout") {
            try await api.abandonSession(sessionID: current.id)
            // A discarded workout's queued sets have nowhere to go.
            pendingSets.removeAll { $0.sessionID == current.id }
            pendingStore.save(pendingSets)
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
