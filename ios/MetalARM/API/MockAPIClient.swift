//
//  MockAPIClient.swift
//  MetalARM
//
//  An in-memory stand-in for the backend, built on ContractFixtures. Used by
//  SwiftUI previews, unit tests, and UI tests (launch argument -UITestMockAPI).
//  Workouts are stateful so the full start -> log -> finish loop works.
//

import Foundation

final class MockAPIClient: MetalArmAPI {
    static let password = "correct-horse-1"

    /// When set, every call throws this instead of returning data.
    var failure: Error?
    /// Simulates a reply lost on the way back: the next set is recorded, then
    /// the call fails as if the network dropped.
    var dropNextLogSetResponse = false
    // Replies already given, by client_set_id - the server's dedupe.
    private var logSetReplies: [UUID: SetLogResult] = [:]
    var onSignedOut: (() -> Void)?
    private(set) var isSignedIn: Bool

    private var current: WorkoutSession?
    private var partyList: [Party]
    private var weightUnit = WeightUnit.kg
    /// The cosmetic class the mock remembers, like the server would.
    var characterClass = ""
    private let decoder = LiveAPIClient.makeDecoder()

    // -UITestLevelUp: finishing a workout levels the user up (14 -> 15).
    private let levelUpOnFinish: Bool
    // -UITestRankUp: finishing a workout reaches a new rank (level 20, C -> B).
    private let rankUpOnFinish: Bool

    // -UITestOffline: logging a set fails as if the phone had no signal.
    var isOffline: Bool

    init(signedIn: Bool = true, levelUpOnFinish: Bool = false, rankUpOnFinish: Bool = false, offline: Bool = false) {
        isSignedIn = signedIn
        isOffline = offline
        self.levelUpOnFinish = levelUpOnFinish
        self.rankUpOnFinish = rankUpOnFinish
        partyList = []
        partyList = fixture(ContractFixtures.parties)
    }

    /// Simulates the server rejecting the stored tokens.
    func expireSession() {
        isSignedIn = false
        onSignedOut?()
    }

    private func fixture<T: Decodable>(_ json: String) -> T {
        try! decoder.decode(T.self, from: Data(json.utf8))
    }

    private func check() throws {
        if let failure { throw failure }
    }

    // MARK: - Account

    func signIn(email: String, password: String) async throws {
        try check()
        guard password == Self.password else { throw APIError.http(status: 401, detail: "Incorrect email or password") }
        isSignedIn = true
    }

    func signUp(email: String, password: String, displayName: String, timezone: String) async throws {
        try check()
        guard password.count >= 8 else { throw APIError.http(status: 422, detail: "String should have at least 8 characters") }
        isSignedIn = true
    }

    func signOut() async {
        isSignedIn = false
    }

    func signOutEverywhere() async throws {
        try check()
        isSignedIn = false
    }

    func deleteAccount(password: String) async throws {
        try check()
        guard password == Self.password else { throw APIError.http(status: 403, detail: "Password is incorrect") }
        isSignedIn = false
    }

    func me() async throws -> Me {
        try check()
        var me: Me = fixture(ContractFixtures.me)
        me.weightUnit = weightUnit.rawValue
        return me
    }

    func updateWeightUnit(_ unit: WeightUnit) async throws -> Me {
        try check()
        weightUnit = unit
        return try await me()
    }

    func profile() async throws -> Profile {
        try check()
        var profile: Profile = fixture(ContractFixtures.profile)
        profile.user.weightUnit = weightUnit.rawValue
        return profile
    }

    func points() async throws -> PointsSummary {
        try check()
        return fixture(ContractFixtures.points)
    }

    // MARK: - Exercises and progress

    func searchExercises(query: String) async throws -> [Exercise] {
        try check()
        let all: [Exercise] = fixture(ContractFixtures.exercises)
        let needle = query.trimmed.lowercased()
        return needle.isEmpty ? all : all.filter { $0.name.lowercased().contains(needle) }
    }

    func lastPerformance(exerciseID: String) async throws -> LastPerformance {
        try check()
        guard exerciseID == ContractFixtures.benchID else {
            return LastPerformance(exerciseId: exerciseID, sessionId: nil, performedAt: nil, sets: [], hint: nil)
        }
        return fixture(ContractFixtures.lastPerformance)
    }

    func exerciseHistory(exerciseID: String) async throws -> [HistoryPoint] {
        try check()
        return fixture(ContractFixtures.history)
    }

    func records(exerciseID: String?) async throws -> [WorkoutRecord] {
        try check()
        let all: [WorkoutRecord] = fixture(ContractFixtures.records)
        guard let exerciseID else { return all }
        return all.filter { $0.exerciseId == exerciseID }
    }

    // MARK: - Workouts

    func activeSession() async throws -> WorkoutSession? {
        try check()
        return current
    }

    func session(id: String) async throws -> WorkoutSession {
        try check()
        guard let current, current.id == id else { throw APIError.http(status: 404, detail: "Workout not found") }
        return current
    }

    func startSession() async throws -> WorkoutSession {
        try check()
        if let current {
            throw APIError.http(status: 409, detail: "A workout is already in progress (\(current.id)) - finish or abandon it first")
        }
        let session = WorkoutSession(
            id: ContractFixtures.sessionID, name: nil, status: "in_progress", routineId: nil,
            startedAt: "2026-09-13T18:00:00Z", endedAt: nil, durationSeconds: 0, workingSets: 0,
            totalVolumeKg: 0, pointsTotal: 0, pointsCredited: 0, qualified: nil, exercises: [])
        current = session
        return session
    }

    // The first set of each exercise beats the last session's best, so it pays the PR bonus.
    func logSet(sessionID: String, exerciseID: String, weight: Double, unit: WeightUnit, reps: Int, clientSetID: UUID) async throws -> SetLogResult {
        try check()
        if isOffline { throw URLError(.notConnectedToInternet) }
        // Like the server: a repeated client_set_id gets the original reply.
        if var earlier = logSetReplies[clientSetID] {
            earlier.isDuplicate = true
            return earlier
        }
        guard var session = current, session.id == sessionID else { throw APIError.http(status: 404, detail: "Workout not found") }
        let library: [Exercise] = fixture(ContractFixtures.exercises)
        guard let exercise = library.first(where: { $0.id == exerciseID }) else {
            throw APIError.http(status: 404, detail: "Exercise not found")
        }
        let kilograms = ((unit == .kg ? weight : weight * WeightUnit.kilogramsPerPound) * 100).rounded() / 100

        if !session.exercises.contains(where: { $0.exercise.id == exerciseID }) {
            let last = try await lastPerformance(exerciseID: exerciseID)
            session.exercises.append(
                SessionExercise(exercise: exercise, target: nil, sets: [], previousSets: last.sets, hint: last.hint)
            )
        }
        let index = session.exercises.firstIndex { $0.exercise.id == exerciseID }!
        let isFirst = session.exercises[index].sets.isEmpty
        let loggedSet = WorkoutSet(
            id: UUID().uuidString, sessionId: sessionID, exerciseId: exerciseID,
            setNumber: session.exercises[index].sets.count + 1, weightKg: kilograms, reps: reps, rpe: nil,
            isWarmup: false, isPr: isFirst, durationSeconds: nil, distanceM: nil,
            completedAt: "2026-09-13T18:05:00Z")
        session.exercises[index].sets.append(loggedSet)

        let points = 2 + (isFirst ? 50 : 0)
        session.workingSets += 1
        session.totalVolumeKg += kilograms * Double(reps)
        session.pointsTotal += points
        current = session

        let prEvents = isFirst ? [PREvent(
            exerciseId: exerciseID, exerciseName: exercise.name, recordType: "max_weight", value: kilograms,
            weightKg: kilograms, previousValue: kilograms - 2.5, isBaseline: false, bonusAwarded: true,
            setId: loggedSet.id)] : []
        var awards = [Award(sourceType: "set_logged", points: 2, reason: "Set logged")]
        if isFirst { awards.append(Award(sourceType: "pr_achieved", points: 50, reason: "New PR: max_weight")) }
        let reply = SetLogResult(
            loggedSet: loggedSet, prEvents: prEvents, awards: awards, pointsAwarded: points,
            sessionPoints: session.pointsTotal, setCapReached: false,
            progression: steadyProgression(points), isDuplicate: false)
        logSetReplies[clientSetID] = reply
        if dropNextLogSetResponse {
            dropNextLogSetResponse = false
            throw URLError(.networkConnectionLost)
        }
        return reply
    }

    func finishSession(sessionID: String) async throws -> FinishResult {
        try check()
        guard let session = current, session.id == sessionID else { throw APIError.http(status: 404, detail: "Workout not found") }
        let qualified = session.workingSets >= 3
        let prSets = session.exercises.flatMap(\.sets).filter(\.isPr)
        let prEvents = session.exercises.compactMap { entry -> PREvent? in
            guard let best = entry.sets.first(where: \.isPr) else { return nil }
            return PREvent(
                exerciseId: entry.exercise.id, exerciseName: entry.exercise.name, recordType: "max_weight",
                value: best.weightKg, weightKg: best.weightKg, previousValue: best.weightKg - 2.5,
                isBaseline: false, bonusAwarded: true, setId: best.id)
        }
        let breakdown = PointsBreakdown(
            setPoints: 2 * session.workingSets, prBonus: 50 * min(prSets.count, 3),
            sessionBonus: qualified ? 25 : 0, streakBonus: qualified ? 20 : 0, reversals: 0,
            total: 2 * session.workingSets + 50 * min(prSets.count, 3) + (qualified ? 45 : 0))
        current = nil
        return FinishResult(
            session: SessionSummary(
                id: session.id, name: nil, status: "completed", startedAt: session.startedAt,
                endedAt: "2026-09-13T18:25:00Z", durationSeconds: 1500, workingSets: session.workingSets,
                exerciseCount: session.exercises.count, totalVolumeKg: session.totalVolumeKg,
                pointsTotal: breakdown.total, prCount: prSets.count),
            qualified: qualified, awards: [], breakdown: breakdown, pointsCredited: breakdown.total,
            prEvents: prEvents, streak: fixture(ContractFixtures.streak),
            progression: finishProgression(breakdown.total))
    }

    func abandonSession(sessionID: String) async throws {
        try check()
        current = nil
    }

    private func finishProgression(_ points: Int) -> ProgressionDelta {
        if rankUpOnFinish { return rankUpProgression(points) }
        return levelUpOnFinish ? levelUpProgression(points) : steadyProgression(points)
    }

    private func rankUpProgression(_ points: Int) -> ProgressionDelta {
        ProgressionDelta(
            xpAwarded: points, pointsAwarded: points, totalXp: 38_000 + points, levelBefore: 19, levelAfter: 20,
            rankBefore: "C", rankAfter: "B", currentStreak: 6, longestStreak: 12, leveledUp: true, rankedUp: true)
    }

    private func levelUpProgression(_ points: Int) -> ProgressionDelta {
        ProgressionDelta(
            xpAwarded: points, pointsAwarded: points, totalXp: 18450 + points, levelBefore: 14, levelAfter: 15,
            rankBefore: "C", rankAfter: "C", currentStreak: 6, longestStreak: 12, leveledUp: true, rankedUp: false)
    }

    private func steadyProgression(_ points: Int) -> ProgressionDelta {
        ProgressionDelta(
            xpAwarded: points, pointsAwarded: points, totalXp: 18450 + points, levelBefore: 14, levelAfter: 14,
            rankBefore: "C", rankAfter: "C", currentStreak: 6, longestStreak: 12, leveledUp: false, rankedUp: false)
    }

    // MARK: - Parties

    func parties() async throws -> [Party] {
        try check()
        return partyList
    }

    func createParty(name: String) async throws -> Party {
        try check()
        let party = Party(
            id: UUID().uuidString, name: name, ownerId: ContractFixtures.userID, maxMembers: 10, memberCount: 1,
            isActive: true, createdAt: "2026-09-13T18:00:00Z", myRole: "owner", inviteCode: "NEWC2345", totalPartyXp: 0)
        partyList.append(party)
        return party
    }

    func joinParty(inviteCode: String) async throws -> Party {
        try check()
        guard inviteCode.uppercased() == "IRON2345" else { throw APIError.http(status: 404, detail: "No party with that invite code") }
        return partyList[0]
    }

    func partyRaid(partyID: String) async throws -> PartyRaid {
        try check()
        var raid: PartyRaid = fixture(ContractFixtures.partyRaid)
        raid.partyId = partyID
        return raid
    }

    func rankTrials() async throws -> [RankTrial] {
        try check()
        return fixture(ContractFixtures.rankTrials)
    }

    func character() async throws -> CharacterSheet {
        try check()
        var sheet: CharacterSheet = fixture(ContractFixtures.character)
        let highlights: [String: [String]] = [
            "powerlifter": ["strength"],
            "bodybuilder": ["strength", "endurance"],
            "athlete": ["endurance", "discipline"],
        ]
        let labels = ["powerlifter": "Powerlifter", "bodybuilder": "Bodybuilder", "athlete": "Athlete"]
        let chosen = highlights[characterClass] ?? []
        sheet.characterClass = characterClass
        sheet.classLabel = labels[characterClass] ?? ""
        sheet.stats = sheet.stats.map { stat in
            var marked = stat
            marked.highlighted = chosen.contains(stat.key)
            return marked
        }
        return sheet
    }

    func updateCharacterClass(_ value: String) async throws -> Me {
        try check()
        characterClass = value
        return try await me()
    }

    func importWorkouts(csv: String, unit: WeightUnit) async throws -> WorkoutImportResult {
        try check()
        guard csv.contains("Exercise Name") || csv.contains("exercise_title") else {
            throw APIError.http(status: 422, detail: "That isn't a Strong or Hevy CSV export")
        }
        return fixture(ContractFixtures.importResult)
    }

    func partyLeaderboard(partyID: String) async throws -> PartyBoard {
        try check()
        var board: PartyBoard = fixture(ContractFixtures.partyBoard)
        board.partyId = partyID
        if partyID != ContractFixtures.partyID {
            board.entries = board.entries.filter(\.isMe).map { entry in
                var mine = entry
                mine.points = 0
                mine.workouts = 0
                return mine
            }
        }
        return board
    }
}
