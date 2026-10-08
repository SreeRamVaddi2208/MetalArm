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

    // The Library: who follows what, and which workout the live session came from.
    var enrollments: [String: Enrollment] = [:]
    var libraryStartSlug: String?

    /// A brand-new account that has never been asked for a training path, so
    /// the onboarding question appears. Established accounts have answered.
    private var pathUnanswered: Bool

    init(
        signedIn: Bool = true, levelUpOnFinish: Bool = false, rankUpOnFinish: Bool = false,
        offline: Bool = false, pathUnanswered: Bool = false
    ) {
        isSignedIn = signedIn
        isOffline = offline
        self.pathUnanswered = pathUnanswered
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
        me.characterClass = characterClass
        if pathUnanswered { me.characterClassSetAt = nil }
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

    func presets() async throws -> [WorkoutPreset] {
        try check()
        return fixture(ContractFixtures.presets)
    }

    func startSession(presetSlug: String? = nil) async throws -> WorkoutSession {
        try check()
        if let current {
            throw APIError.http(status: 409, detail: "A workout is already in progress (\(current.id)) - finish or abandon it first")
        }
        // A preset starts loaded: its exercises, in order, with their targets.
        let preset: WorkoutPreset? = presetSlug.flatMap { slug in
            (fixture(ContractFixtures.presets) as [WorkoutPreset]).first { $0.slug == slug }
        }
        if presetSlug != nil && preset == nil {
            throw APIError.http(status: 404, detail: "No such workout")
        }
        let planned: [SessionExercise] = (preset?.exercises ?? []).map { slot in
            SessionExercise(
                exercise: slot.exercise,
                target: SessionTarget(
                    targetSets: slot.targetSets, targetReps: slot.targetReps,
                    targetWeightKg: nil, restSeconds: slot.restSeconds),
                sets: [], previousSets: [], hint: nil)
        }
        let session = WorkoutSession(
            id: ContractFixtures.sessionID,
            name: preset.map { "\($0.label) · \($0.name)" },
            status: "in_progress", routineId: nil,
            startedAt: "2026-09-13T18:00:00Z", endedAt: nil, durationSeconds: 0, workingSets: 0,
            totalVolumeKg: 0, pointsTotal: 0, pointsCredited: 0, qualified: nil, exercises: planned)
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
        advanceEnrollment(after: libraryStartSlug)
        libraryStartSlug = nil
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

    func league() async throws -> League {
        try check()
        return fixture(ContractFixtures.league)
    }

    func character() async throws -> CharacterSheet {
        try check()
        var sheet: CharacterSheet = fixture(ContractFixtures.character)
        let highlights: [String: [String]] = [
            "powerlifter": ["strength"],
            "bodybuilder": ["strength", "endurance"],
            "athlete": ["endurance", "discipline"],
        ]
        // The same names the training paths use, as the server sends.
        let labels = ["powerlifter": "Powerlifter", "bodybuilder": "Bodybuilder", "athlete": "Athletic"]
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

    func trainingPaths() async throws -> [TrainingPath] {
        try check()
        return fixture(ContractFixtures.trainingPaths)
    }

    func updateCharacterClass(_ value: String) async throws -> Me {
        try check()
        // Answering - including declining - is what stops the question coming
        // back, exactly as the server records it.
        pathUnanswered = false
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

// MARK: - The Library (in memory)
//
// A small catalog built from the fixture exercises - two workouts and one
// program per path - recommended and ordered the way the server does it: the
// user's path first, easiest first.

extension MockAPIClient {
    struct MockSlot { let exerciseID: String; let sets: Int; let low: Int; let high: Int; let rest: Int; var superset = 0 }
    struct MockWorkout { let slug: String; let name: String; let category: String; let difficulty: String; let minutes: Int; let standalone: Bool; let slots: [MockSlot] }
    struct MockProgram { let slug: String; let name: String; let category: String; let difficulty: String; let weeks: Int; let workouts: [String]; let days: [Int] }

    static let pathLabels = ["athlete": "Athletic", "bodybuilder": "Bodybuilder", "powerlifter": "Powerlifter"]
    static let pathOrder = ["athlete", "bodybuilder", "powerlifter"]
    static let difficultyOrder = ["beginner": 0, "intermediate": 1, "advanced": 2]

    static let libraryWorkouts: [MockWorkout] = {
        let F = ContractFixtures.self
        return [
            MockWorkout(slug: "athletic-circuit", name: "Athletic circuit", category: "athlete", difficulty: "beginner",
                        minutes: 30, standalone: true, slots: [
                            MockSlot(exerciseID: F.squatID, sets: 3, low: 15, high: 15, rest: 45, superset: 1),
                            MockSlot(exerciseID: F.pullUpID, sets: 3, low: 12, high: 15, rest: 45, superset: 1)]),
            MockWorkout(slug: "athletic-press", name: "Press and pull", category: "athlete", difficulty: "intermediate",
                        minutes: 35, standalone: true, slots: [
                            MockSlot(exerciseID: F.pressID, sets: 3, low: 12, high: 15, rest: 45),
                            MockSlot(exerciseID: F.rowID, sets: 3, low: 12, high: 15, rest: 45)]),
            MockWorkout(slug: "chest-and-triceps", name: "Chest and triceps", category: "bodybuilder", difficulty: "intermediate",
                        minutes: 55, standalone: true, slots: [
                            MockSlot(exerciseID: F.benchID, sets: 4, low: 8, high: 10, rest: 90),
                            MockSlot(exerciseID: F.pressID, sets: 3, low: 10, high: 12, rest: 75)]),
            MockWorkout(slug: "back-and-biceps", name: "Back and biceps", category: "bodybuilder", difficulty: "beginner",
                        minutes: 50, standalone: true, slots: [
                            MockSlot(exerciseID: F.rowID, sets: 4, low: 8, high: 12, rest: 90),
                            MockSlot(exerciseID: F.pullUpID, sets: 3, low: 8, high: 12, rest: 90)]),
            MockWorkout(slug: "squat-day", name: "Squat day", category: "powerlifter", difficulty: "intermediate",
                        minutes: 70, standalone: true, slots: [
                            MockSlot(exerciseID: F.squatID, sets: 5, low: 3, high: 5, rest: 240),
                            MockSlot(exerciseID: F.deadliftID, sets: 3, low: 3, high: 5, rest: 240)]),
            MockWorkout(slug: "bench-day", name: "Bench day", category: "powerlifter", difficulty: "intermediate",
                        minutes: 60, standalone: true, slots: [
                            MockSlot(exerciseID: F.benchID, sets: 5, low: 3, high: 5, rest: 240),
                            MockSlot(exerciseID: F.rowID, sets: 3, low: 6, high: 8, rest: 120)]),
        ]
    }()

    static let libraryPrograms: [MockProgram] = [
        MockProgram(slug: "foundations-of-movement", name: "Foundations of Movement", category: "athlete",
                    difficulty: "beginner", weeks: 4, workouts: ["athletic-circuit", "athletic-press"], days: [1, 3, 5]),
        MockProgram(slug: "upper-lower-8wk", name: "Upper / Lower", category: "bodybuilder",
                    difficulty: "beginner", weeks: 8, workouts: ["chest-and-triceps", "back-and-biceps"], days: [1, 2, 4, 5]),
        MockProgram(slug: "linear-strength-base", name: "Linear Strength Base", category: "powerlifter",
                    difficulty: "beginner", weeks: 8, workouts: ["squat-day", "bench-day"], days: [1, 3, 5]),
    ]

    private var exercisesByID: [String: Exercise] {
        Dictionary(uniqueKeysWithValues: (fixture(ContractFixtures.exercises) as [Exercise]).map { ($0.id, $0) })
    }

    private func label(_ category: String) -> String { Self.pathLabels[category] ?? category.capitalized }

    /// The server's order: the user's path, then the others; easiest first.
    private func rank(_ category: String, _ difficulty: String, _ size: Int) -> [Int] {
        [category == characterClass ? 0 : 1, Self.pathOrder.firstIndex(of: category) ?? 9,
         Self.difficultyOrder[difficulty] ?? 9, size]
    }

    private func workoutCard(_ w: MockWorkout, sort: Int) -> LibraryWorkoutCard {
        var equipment: [String] = []
        for slot in w.slots {
            if let kit = exercisesByID[slot.exerciseID]?.equipment, !equipment.contains(kit) { equipment.append(kit) }
        }
        return LibraryWorkoutCard(
            slug: w.slug, name: w.name, description: "\(w.name), for the \(label(w.category)) path.",
            category: w.category, categoryLabel: label(w.category), difficulty: w.difficulty,
            durationMinutes: w.minutes, exerciseCount: w.slots.count, equipment: equipment, focusTags: [],
            recommended: !characterClass.isEmpty && w.category == characterClass, sort: sort)
    }

    private func programCard(_ p: MockProgram, sort: Int) -> LibraryProgramCard {
        LibraryProgramCard(
            slug: p.slug, name: p.name, description: "\(p.name): \(p.days.count) days a week.",
            category: p.category, categoryLabel: label(p.category), difficulty: p.difficulty, weeks: p.weeks,
            daysPerWeek: p.days.count, equipment: ["barbell"],
            recommended: !characterClass.isEmpty && p.category == characterClass, sort: sort,
            following: enrollments[p.slug]?.status == "active")
    }

    private func workoutCards(_ items: [MockWorkout]) -> [LibraryWorkoutCard] {
        items.sorted { rank($0.category, $0.difficulty, $0.minutes).lexicographicallyPrecedes(rank($1.category, $1.difficulty, $1.minutes)) }
            .enumerated().map { workoutCard($1, sort: $0) }
    }

    private func programCards(_ items: [MockProgram]) -> [LibraryProgramCard] {
        items.sorted { rank($0.category, $0.difficulty, $0.days.count).lexicographicallyPrecedes(rank($1.category, $1.difficulty, $1.days.count)) }
            .enumerated().map { programCard($1, sort: $0) }
    }

    /// (week, day, workout slug) for every training day, in order.
    private func trainingDays(_ p: MockProgram) -> [(week: Int, day: Int, slug: String)] {
        var out: [(Int, Int, String)] = []
        var n = 0
        for week in 1...p.weeks {
            for day in p.days {
                out.append((week, day, p.workouts[n % p.workouts.count]))
                n += 1
            }
        }
        return out
    }

    private func enrollmentOut(_ e: Enrollment, _ p: MockProgram) -> Enrollment {
        var e = e
        let next = trainingDays(p).first { ($0.week, $0.day) >= (e.currentWeek, e.currentDay) }
        e.nextWorkout = e.status == "completed" ? nil : next.flatMap { day in
            Self.libraryWorkouts.first { $0.slug == day.slug }.map { workoutCard($0, sort: 0) }
        }
        return e
    }

    fileprivate func advanceEnrollment(after slug: String?) {
        guard let slug, let active = enrollments.first(where: { $0.value.status == "active" }),
              case let (key, e) = (active.key, active.value),
              let p = Self.libraryPrograms.first(where: { $0.slug == key }) else { return }
        let days = trainingDays(p)
        guard let index = days.firstIndex(where: { ($0.week, $0.day) >= (e.currentWeek, e.currentDay) }),
              days[index].slug == slug else { return }
        var updated = e
        if index + 1 < days.count {
            updated.currentWeek = days[index + 1].week
            updated.currentDay = days[index + 1].day
        } else {
            updated.status = "completed"
        }
        enrollments[key] = updated
    }

    func libraryHome() async throws -> LibraryHome {
        try check()
        let path = characterClass
        let standalone = Self.libraryWorkouts.filter(\.standalone)
        let active = enrollments.first { $0.value.status == "active" }
        let yours = active.flatMap { found in
            Self.libraryPrograms.first { $0.slug == found.key }.map {
                YourProgram(program: programCard($0, sort: 0), enrollment: enrollmentOut(found.value, $0))
            }
        }
        return LibraryHome(
            path: path, needsPath: path.isEmpty, yourProgram: yours,
            recommendedPrograms: path.isEmpty ? [] : programCards(Self.libraryPrograms.filter { $0.category == path }),
            recommendedWorkouts: path.isEmpty ? [] : workoutCards(standalone.filter { $0.category == path }),
            otherPaths: Self.pathOrder.filter { $0 != path }.map { c in
                PathCount(category: c, label: label(c), programs: Self.libraryPrograms.filter { $0.category == c }.count,
                          workouts: standalone.filter { $0.category == c }.count)
            })
    }

    func libraryPrograms(category: String?, filters: LibraryFilters) async throws -> [LibraryProgramCard] {
        try check()
        return programCards(Self.libraryPrograms.filter { p in
            (category == nil || p.category == category) && (filters.difficulty == nil || p.difficulty == filters.difficulty)
                && (filters.daysPerWeek == nil || p.days.count == filters.daysPerWeek)
        })
    }

    func libraryProgram(slug: String) async throws -> LibraryProgram {
        try check()
        guard let p = Self.libraryPrograms.first(where: { $0.slug == slug }) else {
            throw APIError.http(status: 404, detail: "No such program")
        }
        let card = programCard(p, sort: 0)
        let days = trainingDays(p)
        let names = Dictionary(uniqueKeysWithValues: Self.libraryWorkouts.map { ($0.slug, $0.name) })
        let schedule = (1...p.weeks).map { week in
            ScheduleWeek(week: week, days: (1...7).map { day in
                let slug = days.first { $0.week == week && $0.day == day }?.slug
                return ScheduleDay(day: day, workoutSlug: slug, workoutName: slug.flatMap { names[$0] })
            })
        }
        return LibraryProgram(
            slug: p.slug, name: p.name, description: card.description, category: p.category,
            categoryLabel: card.categoryLabel, difficulty: p.difficulty, weeks: p.weeks, daysPerWeek: p.days.count,
            equipment: card.equipment, recommended: card.recommended, following: card.following, schedule: schedule,
            workouts: p.workouts.compactMap { slug in Self.libraryWorkouts.first { $0.slug == slug }.map { workoutCard($0, sort: 0) } },
            enrollment: enrollments[p.slug].map { enrollmentOut($0, p) })
    }

    func libraryWorkouts(category: String?, filters: LibraryFilters) async throws -> [LibraryWorkoutCard] {
        try check()
        return workoutCards(Self.libraryWorkouts.filter { w in
            w.standalone && (category == nil || w.category == category)
                && (filters.difficulty == nil || w.difficulty == filters.difficulty)
                && (filters.maxMinutes == nil || w.minutes <= filters.maxMinutes!)
        })
    }

    func libraryWorkout(slug: String) async throws -> LibraryWorkout {
        try check()
        guard let w = Self.libraryWorkouts.first(where: { $0.slug == slug }) else {
            throw APIError.http(status: 404, detail: "No such workout")
        }
        let card = workoutCard(w, sort: 0)
        let byID = exercisesByID
        return LibraryWorkout(
            slug: w.slug, name: w.name, description: card.description, category: w.category,
            categoryLabel: card.categoryLabel, difficulty: w.difficulty, durationMinutes: w.minutes,
            exerciseCount: w.slots.count, equipment: card.equipment, recommended: card.recommended,
            exercises: w.slots.enumerated().compactMap { index, slot in
                byID[slot.exerciseID].map {
                    LibraryWorkoutExercise(position: index, exercise: $0, targetSets: slot.sets, repLow: slot.low,
                                           repHigh: slot.high, restSeconds: slot.rest, note: nil, supersetGroup: slot.superset)
                }
            },
            routineId: nil)
    }

    func startLibraryWorkout(slug: String) async throws -> WorkoutSession {
        try check()
        if let current {
            throw APIError.http(status: 409, detail: "A workout is already in progress (\(current.id)) - finish or abandon it first")
        }
        let workout = try await libraryWorkout(slug: slug)
        let planned = workout.exercises.map { slot in
            SessionExercise(
                exercise: slot.exercise,
                target: SessionTarget(targetSets: slot.targetSets, targetReps: slot.repHigh, targetWeightKg: nil,
                                      restSeconds: slot.restSeconds, targetRepsLow: slot.repLow, targetRepsHigh: slot.repHigh),
                supersetGroup: slot.supersetGroup > 0 ? slot.supersetGroup : nil,
                sets: [], previousSets: [], hint: nil)
        }
        let session = WorkoutSession(
            id: ContractFixtures.sessionID, name: workout.name, status: "in_progress", routineId: nil,
            startedAt: "2026-09-13T18:00:00Z", endedAt: nil, durationSeconds: 0, workingSets: 0,
            totalVolumeKg: 0, pointsTotal: 0, pointsCredited: 0, qualified: nil, exercises: planned)
        current = session
        libraryStartSlug = slug
        return session
    }

    func saveLibraryWorkout(slug: String) async throws -> SavedRoutine {
        try check()
        let workout = try await libraryWorkout(slug: slug)
        return SavedRoutine(id: "routine-\(slug)", name: workout.name)
    }

    func followProgram(slug: String) async throws -> Enrollment {
        try check()
        guard let p = Self.libraryPrograms.first(where: { $0.slug == slug }) else {
            throw APIError.http(status: 404, detail: "No such program")
        }
        for (key, var other) in enrollments where key != slug && other.status == "active" {
            other.status = "paused"
            enrollments[key] = other
        }
        let first = trainingDays(p).first!
        var e = enrollments[slug] ?? Enrollment(
            id: "enrollment-\(slug)", programSlug: slug, status: "active", startedAt: "2026-09-13T18:00:00Z",
            currentWeek: first.week, currentDay: first.day, nextWorkout: nil)
        if e.status == "completed" { (e.currentWeek, e.currentDay) = (first.week, first.day) }
        e.status = "active"
        enrollments[slug] = e
        return enrollmentOut(e, p)
    }

    func unfollowProgram(slug: String) async throws -> Enrollment {
        try check()
        guard var e = enrollments[slug], let p = Self.libraryPrograms.first(where: { $0.slug == slug }) else {
            throw APIError.http(status: 404, detail: "Not following this program")
        }
        e.status = "paused"
        enrollments[slug] = e
        return enrollmentOut(e, p)
    }
}

