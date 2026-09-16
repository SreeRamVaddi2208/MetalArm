//
//  MetalARMTests.swift
//  MetalARMTests
//
//  Created by Vaddi Sree Rama Sai Sasi Sekhar on 13/09/26.
//

import Foundation
import Testing
import UIKit
@testable import MetalARM

// MARK: - Bundled fonts

@MainActor
struct FontTests {
    // A font missing from the bundle or UIAppFonts would silently fall back to
    // the system font, so check every face loads by its PostScript name.
    @Test(arguments: Theme.fontNames)
    func bundledFontLoads(name: String) {
        #expect(UIFont(name: name, size: 12) != nil, "\(name) is not in the app bundle")
    }
}

// MARK: - Decoding the backend's response shapes

@MainActor
struct DecodingTests {
    private let decoder = LiveAPIClient.makeDecoder()

    private func decode<T: Decodable>(_ type: T.Type, _ json: String) throws -> T {
        try decoder.decode(type, from: Data(json.utf8))
    }

    @Test func tokenPair() throws {
        let tokens = try decode(TokenPair.self, ContractFixtures.tokens)
        #expect(tokens.accessToken == "access-1")
        #expect(tokens.refreshToken == "refresh-1")
        #expect(tokens.refreshExpiresIn == 2_592_000)
    }

    @Test func meCarriesProgression() throws {
        let me = try decode(Me.self, ContractFixtures.me)
        #expect(me.displayName == "Sree Ram")
        #expect(me.progress.currentLevel == 14)
        #expect(me.progress.rank == "C")
        #expect(me.progress.nextRankStreak == nil)
        #expect(abs(me.progress.xpProgress - 2140.0 / 3000.0) < 0.0001)
    }

    @Test func activeSessionIncludesGhostSets() throws {
        let active = try decode(ActiveSession.self, ContractFixtures.activeSession)
        let bench = try #require(active.session?.exercises.first)
        #expect(bench.exercise.name == "Barbell Bench Press")
        #expect(bench.target?.restSeconds == 120)
        #expect(bench.previousSets.map(\.reps) == [8, 7])
        #expect(try decode(ActiveSession.self, ContractFixtures.noActiveSession).session == nil)
    }

    @Test func setLogResultLeadsWithTheBonusRecord() throws {
        let result = try decode(SetLogResult.self, ContractFixtures.setLogResult)
        #expect(result.loggedSet.setNumber == 2)
        #expect(result.prEvents.celebrated?.recordType == "max_weight")
        #expect(result.progression.hint == "Level up! You reached level 10.")
        #expect(result.sessionPoints == 66)
    }

    @Test func finishResult() throws {
        let result = try decode(FinishResult.self, ContractFixtures.finishResult)
        #expect(result.qualified)
        #expect(result.breakdown.total == 140)
        #expect(result.breakdown.reversals == -2)
        #expect(result.streak.sessionsToGo == 1)
    }

    @Test func progressPartiesPointsAndProfile() throws {
        #expect(try decode([HistoryPoint].self, ContractFixtures.history).count == 4)
        #expect(try decode([WorkoutRecord].self, ContractFixtures.records).first?.label == "Heaviest")
        #expect(try decode([Party].self, ContractFixtures.parties).first?.inviteCode == "IRON2345")
        #expect(try decode(PartyBoard.self, ContractFixtures.partyBoard).entries.first?.isMe == true)
        let raid = try decode(PartyRaid.self, ContractFixtures.partyRaid)
        #expect(raid.name == "Iron Golem")
        #expect(raid.hpRemaining == 41_250)
        #expect(abs(raid.hpFraction - 41_250.0 / 60_000.0) < 0.0001)
        #expect(raid.hitters.first?.isMe == true)
        #expect(raid.daysLeft(from: parseServerDate("2026-09-17T12:00:00Z")!) == 4)
        #expect(try decode(PointsSummary.self, ContractFixtures.points).thisWeekPoints == 185)
        let profile = try decode(Profile.self, ContractFixtures.profile)
        #expect(profile.stats.workoutsCompleted == 142)
        #expect(profile.badgesEarned == 3)
        #expect(profile.progress.nextRankTrial == "Barbell Bench Press at 1x bodyweight")
        let sheet = try decode(CharacterSheet.self, ContractFixtures.character)
        #expect(sheet.stats.map(\.key) == ["strength", "endurance", "discipline"])
        #expect(sheet.stats[1].fraction == 0.61)
        let trials = try decode([RankTrial].self, ContractFixtures.rankTrials)
        #expect(trials.map(\.rank) == ["B", "A", "S"])
        #expect(abs(trials[0].fraction - 72.5 / 80.0) < 0.0001)
        #expect(trials[2].bestKg == nil && trials[2].fraction == 0)
        let imported = try decode(WorkoutImportResult.self, ContractFixtures.importResult)
        let last = try decode(LastPerformance.self, ContractFixtures.lastPerformance)
        #expect(last.hint?.kind == "progress")
        #expect(last.hint?.targetReps == 5)
        #expect(imported.summary == "Imported 42 workouts (610 sets) from Strong. 3 already in your history. 1 new exercise added. +420 XP.")
    }
}

// MARK: - Units and wording

@MainActor
struct FormattingTests {
    @Test func poundsShowOneDecimal() {
        #expect(WeightUnit.lb.format(kilograms: 80) == "176.4 lb")
        #expect(WeightUnit.kg.format(kilograms: 82.5) == "82.5 kg")
    }

    @Test func firstEverLogsAreNotCelebrated() {
        let baseline = PREvent(
            exerciseId: "e", exerciseName: "Squat", recordType: "max_weight", value: 100, weightKg: 100,
            previousValue: nil, isBaseline: true, bonusAwarded: false, setId: nil)
        #expect([baseline].celebrated == nil)
    }

    @Test func repRecordsReadAsReps() {
        let event = PREvent(
            exerciseId: "e", exerciseName: "Bench", recordType: "max_reps_at_weight", value: 8, weightKg: 80,
            previousValue: 7, isBaseline: false, bonusAwarded: false, setId: nil)
        #expect(event.headline(in: .kg) == "New rep record on Bench: 8 reps at 80 kg")
    }

    @Test func serverTimestampsParse() {
        #expect(parseServerDate("2026-09-13T21:14:05.123456Z") != nil)
        #expect(parseServerDate("2026-09-07T00:00:00+05:30") != nil)
    }

    @Test(arguments: zip([85.0, 82.5, 142.25, 0], ["85", "82.5", "142.25", "0"]))
    func formatsNumbersLikeTheBackend(value: Double, expected: String) {
        #expect(formatNumber(value) == expected)
    }

    @Test func initialsUseFirstTwoWords() {
        #expect(initials(of: "Sree Ram") == "SR")
        #expect(initials(of: "meera") == "M")
    }
}

// MARK: - LiveAPIClient against a stubbed network

nonisolated final class StubURLProtocol: URLProtocol {
    nonisolated(unsafe) static var responses: [(status: Int, body: String)] = []
    nonisolated(unsafe) static var requests: [URLRequest] = []
    nonisolated(unsafe) static var bodies: [Data] = []

    override class func canInit(with request: URLRequest) -> Bool { true }

    override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }

    override func startLoading() {
        Self.requests.append(request)
        // URLSession moves httpBody into a stream before it reaches a URLProtocol.
        Self.bodies.append(request.httpBody ?? request.httpBodyStream.map(Self.readAll) ?? Data())
        let next = Self.responses.isEmpty ? (status: 500, body: "{}") : Self.responses.removeFirst()
        let response = HTTPURLResponse(
            url: request.url!, statusCode: next.status, httpVersion: "HTTP/1.1",
            headerFields: ["Content-Type": "application/json"])!
        client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
        client?.urlProtocol(self, didLoad: Data(next.body.utf8))
        client?.urlProtocolDidFinishLoading(self)
    }

    override func stopLoading() {}

    private static func readAll(_ stream: InputStream) -> Data {
        stream.open()
        defer { stream.close() }
        var data = Data()
        var buffer = [UInt8](repeating: 0, count: 1024)
        while stream.hasBytesAvailable {
            let count = stream.read(&buffer, maxLength: buffer.count)
            if count <= 0 { break }
            data.append(buffer, count: count)
        }
        return data
    }
}

@MainActor
@Suite(.serialized)
struct LiveAPIClientTests {
    private let signedIn = TokenPair(
        accessToken: "access-1", tokenType: "bearer", expiresIn: 3600,
        refreshToken: "refresh-1", refreshExpiresIn: 2_592_000)

    private func makeClient(tokens: TokenPair? = nil, responses: [(Int, String)]) -> (LiveAPIClient, InMemoryTokenStore) {
        StubURLProtocol.responses = responses.map { (status: $0.0, body: $0.1) }
        StubURLProtocol.requests = []
        StubURLProtocol.bodies = []
        let configuration = URLSessionConfiguration.ephemeral
        configuration.protocolClasses = [StubURLProtocol.self]
        let store = InMemoryTokenStore(tokens: tokens)
        let client = LiveAPIClient(
            baseURL: URL(string: "http://backend.test")!, session: URLSession(configuration: configuration), tokenStore: store)
        return (client, store)
    }

    private func body(_ index: Int) throws -> [String: Any] {
        try #require(try JSONSerialization.jsonObject(with: StubURLProtocol.bodies[index]) as? [String: Any])
    }

    @Test func signInStoresBothTokens() async throws {
        let (client, store) = makeClient(responses: [(200, ContractFixtures.tokens)])
        try await client.signIn(email: "sree@metalarm.dev", password: "correct-horse-1")
        #expect(store.tokens?.refreshToken == "refresh-1")
        let request = try #require(StubURLProtocol.requests.first)
        #expect(request.url?.path == "/api/v1/auth/login")
        #expect(request.value(forHTTPHeaderField: "Authorization") == nil)
        #expect(try body(0)["email"] as? String == "sree@metalarm.dev")
    }

    @Test func requestsCarryTheAccessToken() async throws {
        let (client, _) = makeClient(tokens: signedIn, responses: [(200, ContractFixtures.me)])
        _ = try await client.me()
        #expect(StubURLProtocol.requests.first?.value(forHTTPHeaderField: "Authorization") == "Bearer access-1")
    }

    @Test func expiredAccessTokenIsRefreshedAndTheRequestRetried() async throws {
        let refreshed = #"{"access_token": "access-2", "token_type": "bearer", "expires_in": 3600, "refresh_token": "refresh-2", "refresh_expires_in": 2592000}"#
        let (client, store) = makeClient(tokens: signedIn, responses: [
            (401, #"{"detail": "Token has expired"}"#), (200, refreshed), (200, ContractFixtures.me),
        ])
        let me = try await client.me()
        #expect(me.displayName == "Sree Ram")
        #expect(StubURLProtocol.requests.map { $0.url?.path ?? "" } == ["/api/v1/auth/me", "/api/v1/auth/refresh", "/api/v1/auth/me"])
        #expect(try body(1)["refresh_token"] as? String == "refresh-1")
        #expect(StubURLProtocol.requests.last?.value(forHTTPHeaderField: "Authorization") == "Bearer access-2")
        #expect(store.tokens?.refreshToken == "refresh-2")
    }

    @Test func rejectedRefreshSignsOut() async throws {
        let (client, store) = makeClient(tokens: signedIn, responses: [
            (401, #"{"detail": "Token has expired"}"#),
            (401, #"{"detail": "Refresh token is invalid or expired - sign in again"}"#),
        ])
        var signedOut = false
        client.onSignedOut = { signedOut = true }
        await #expect(throws: APIError.signedOut) {
            _ = try await client.me()
        }
        #expect(store.tokens == nil)
        #expect(signedOut)
    }

    @Test func logSetSendsClientSetIDAndUnitButNoPoints() async throws {
        let (client, _) = makeClient(tokens: signedIn, responses: [(201, ContractFixtures.setLogResult)])
        let clientSetID = UUID()
        _ = try await client.logSet(
            sessionID: ContractFixtures.sessionID, exerciseID: ContractFixtures.benchID, weight: 225, unit: .lb,
            reps: 5, clientSetID: clientSetID)
        #expect(StubURLProtocol.requests.first?.url?.path == "/api/v1/workouts/sessions/\(ContractFixtures.sessionID)/sets")
        let sent = try body(0)
        #expect(sent["exercise_id"] as? String == ContractFixtures.benchID)
        #expect(sent["weight"] as? Double == 225)
        #expect(sent["unit"] as? String == "lb")
        #expect(sent["reps"] as? Int == 5)
        #expect(sent["client_set_id"] as? String == clientSetID.uuidString)
        // Points and PRs are computed by the server; the client never sends them.
        #expect(sent["points"] == nil)
    }

    @Test func validationErrorsAreReadable() async {
        let issue = #"{"detail": [{"loc": ["body", "password"], "msg": "String should have at least 8 characters", "type": "string_too_short"}]}"#
        let (client, _) = makeClient(responses: [(422, issue)])
        await #expect(throws: APIError.http(status: 422, detail: "String should have at least 8 characters")) {
            try await client.signUp(email: "a@metalarm.dev", password: "short", displayName: "A", timezone: "UTC")
        }
    }

    @Test func signingOutEndsThisDeviceOnTheServer() async throws {
        let (client, store) = makeClient(tokens: signedIn, responses: [(204, "")])
        await client.signOut()
        let request = try #require(StubURLProtocol.requests.first)
        #expect(request.httpMethod == "POST")
        #expect(request.url?.path == "/api/v1/auth/logout")
        // The refresh token, not the access token: it still works after the
        // access token has expired, so the session is always revoked.
        #expect(try body(0)["refresh_token"] as? String == "refresh-1")
        #expect(request.value(forHTTPHeaderField: "Authorization") == nil)
        #expect(store.tokens == nil)
    }

    @Test func signingOutWhenAlreadySignedOutSendsNothing() async {
        let (client, _) = makeClient(responses: [])
        await client.signOut()
        #expect(StubURLProtocol.requests.isEmpty)
    }

    @Test func signingOutStillForgetsTokensWhenTheServerFails() async {
        let (client, store) = makeClient(tokens: signedIn, responses: [(503, #"{"detail": "Service unavailable"}"#)])
        await client.signOut()
        #expect(store.tokens == nil)
    }

    @Test func signingOutEverywhereUsesLogoutAll() async throws {
        let (client, store) = makeClient(tokens: signedIn, responses: [(204, "")])
        try await client.signOutEverywhere()
        #expect(StubURLProtocol.requests.first?.url?.path == "/api/v1/auth/logout-all")
        #expect(store.tokens == nil)
    }

    @Test func deletingTheAccountSendsThePasswordAndForgetsTokens() async throws {
        let (client, store) = makeClient(tokens: signedIn, responses: [(204, "")])
        try await client.deleteAccount(password: "correct-horse-1")
        let request = try #require(StubURLProtocol.requests.first)
        #expect(request.httpMethod == "DELETE")
        #expect(request.url?.path == "/api/v1/auth/me")
        #expect(try body(0)["password"] as? String == "correct-horse-1")
        #expect(store.tokens == nil)
    }
}

// MARK: - AppModel with the in-memory backend

@MainActor
struct ShareCardTests {
    private func finishResult() throws -> FinishResult {
        try LiveAPIClient.makeDecoder().decode(FinishResult.self, from: Data(ContractFixtures.finishResult.utf8))
    }

    @Test func aRankUpLeadsTheCard() throws {
        var result = try finishResult()
        result.progression.rankedUp = true
        result.progression.leveledUp = true
        result.progression.rankAfter = "B"
        result.progression.levelAfter = 20
        let card = ShareCardContent.make(result: result, unit: .kg, inviteCode: "IRON2345")
        #expect(card.kind == .rankUp)
        #expect(card.headline == "B")
        #expect(card.caption == "Rank B at level 20")
        #expect(card.inviteCode == "IRON2345")
    }

    @Test func aLevelUpComesNext() throws {
        var result = try finishResult()
        result.progression.rankedUp = false
        result.progression.leveledUp = true
        result.progression.levelAfter = 15
        let card = ShareCardContent.make(result: result, unit: .kg, inviteCode: nil)
        #expect(card.kind == .levelUp)
        #expect(card.headline == "15")
        #expect(card.inviteCode == nil)
    }

    @Test func thenARecordThenThePoints() throws {
        var result = try finishResult()
        result.progression.rankedUp = false
        result.progression.leveledUp = false
        let record = PREvent(
            exerciseId: ContractFixtures.benchID, exerciseName: "Barbell Bench Press", recordType: "max_weight",
            value: 100, weightKg: 100, previousValue: 95, isBaseline: false, bonusAwarded: true, setId: "s1")
        result.prEvents = [record]
        let withRecord = ShareCardContent.make(result: result, unit: .kg, inviteCode: "")
        #expect(withRecord.kind == .record)
        #expect(withRecord.caption == record.headline(in: .kg))
        // An empty invite code is never printed.
        #expect(withRecord.inviteCode == nil)

        result.prEvents = []
        let plain = ShareCardContent.make(result: result, unit: .kg, inviteCode: nil)
        #expect(plain.kind == .workout)
        #expect(plain.headline == "+\(result.breakdown.total)")
    }

    @Test func theCardRendersAtStorySize() throws {
        let card = ShareCardContent.make(result: try finishResult(), unit: .kg, inviteCode: "IRON2345")
        let image = try #require(ShareCardRenderer.render(card))
        #expect(image.size.width * image.scale == 1080)
        #expect(image.size.height * image.scale == 1920)
        // Kept with the test results, so the card itself can be looked at.
        Attachment.record(try #require(image.pngData()), named: "share-card.png")
    }

    @Test func finishingLoadsPartiesForTheInviteCode() async throws {
        let api = MockAPIClient()
        let model = AppModel(api: api)
        #expect(model.parties.isEmpty)
        await model.startWorkout()
        await model.addExercise(try #require(try await api.searchExercises(query: "bench").first))
        await model.logSet()
        await model.finishWorkout()
        #expect(!model.parties.isEmpty)
        #expect(model.shareInviteCode == model.parties.first?.inviteCode)
    }
}

@MainActor
struct AppModelTests {
    private func signedInModel() -> (AppModel, MockAPIClient) {
        let api = MockAPIClient()
        return (AppModel(api: api), api)
    }

    private func bench(_ api: MockAPIClient) async throws -> Exercise {
        try #require(try await api.searchExercises(query: "bench").first)
    }

    @Test func signingInThenLoadingHome() async {
        let model = AppModel(api: MockAPIClient(signedIn: false))
        #expect(!model.isSignedIn)
        await model.signIn(email: " sree@metalarm.dev ", password: MockAPIClient.password)
        #expect(model.isSignedIn)
        await model.loadHome()
        #expect(model.me?.progress.currentLevel == 14)
        #expect(model.points?.thisWeekPoints == 185)
        #expect(!model.sessionActive)
    }

    @Test func wrongPasswordStaysSignedOut() async {
        let model = AppModel(api: MockAPIClient(signedIn: false))
        await model.signIn(email: "sree@metalarm.dev", password: "wrong-password")
        #expect(!model.isSignedIn)
        #expect(model.errorMessage == "Couldn't sign in: Incorrect email or password")
    }

    @Test func workoutLoopFromStartToSummary() async throws {
        let (model, api) = signedInModel()
        await model.startWorkout()
        #expect(model.sessionActive)
        #expect(model.selectedExercise == nil)

        await model.addExercise(try await bench(api))
        // Prefilled from last session's first set (the ghost values).
        #expect(model.weightInput == "80")
        #expect(model.repsInput == "8")

        await model.logSet()
        #expect(model.setsLoggedCount == 1)
        #expect(model.pendingExercises.isEmpty)
        #expect(model.prHint == "New heaviest Barbell Bench Press: 80 kg")
        #expect(model.resting)
        #expect(model.restDisplay == "1:30")

        await model.finishWorkout()
        #expect(model.showingSummary)
        #expect(!model.sessionActive)
        #expect(!model.resting)
        // A single set is not a qualifying workout: no completion bonus.
        #expect(model.finishResult?.qualified == false)
        #expect(model.finishResult?.breakdown.sessionBonus == 0)
        #expect(model.finishResult?.breakdown.prBonus == 50)
    }

    @Test func invalidInputIsRejectedWithoutLogging() async throws {
        let (model, api) = signedInModel()
        await model.startWorkout()
        await model.addExercise(try await bench(api))
        model.weightInput = "heavy"
        await model.logSet()
        #expect(model.errorMessage == "Enter a weight and a number of reps.")
        #expect(model.setsLoggedCount == 0)
    }

    @Test func poundsAreShownAndSentAsPounds() async throws {
        let (model, api) = signedInModel()
        await model.loadHome()
        await model.setWeightUnit(.lb)
        #expect(model.weightUnit == .lb)
        await model.startWorkout()
        await model.addExercise(try await bench(api))
        #expect(model.weightInput == "176.4")
        await model.logSet()
        let kilograms = try #require(model.session?.exercises.first?.sets.first?.weightKg)
        #expect(abs(kilograms - 80) < 0.05)
    }

    @Test func startingWhileOneIsLiveResumesIt() async {
        let (model, api) = signedInModel()
        await model.startWorkout()
        // A second device sees the 409 and picks up the same workout.
        let otherDevice = AppModel(api: api)
        await otherDevice.startWorkout()
        #expect(otherDevice.session?.id == model.session?.id)
        #expect(otherDevice.errorMessage.isEmpty)
    }

    @Test func discardingEndsTheWorkout() async {
        let (model, _) = signedInModel()
        await model.startWorkout()
        await model.abandonWorkout()
        #expect(!model.sessionActive)
    }

    // MARK: Offline logging

    @Test func aSetLoggedOfflineIsQueuedAndSyncsLater() async throws {
        let (model, api) = signedInModel()
        await model.startWorkout()
        await model.addExercise(try await bench(api))

        api.failure = URLError(.notConnectedToInternet)
        await model.logSet()
        #expect(model.pendingSets.count == 1)
        #expect(model.errorMessage.isEmpty)
        #expect(model.setsLoggedCount == 0)
        #expect(model.resting)

        api.failure = nil
        await model.flushPendingSets()
        #expect(model.pendingSets.isEmpty)
        #expect(model.setsLoggedCount == 1)
    }

    @Test func queuedSetsSyncInTheOrderTheyWereDone() async throws {
        let (model, api) = signedInModel()
        await model.startWorkout()
        await model.addExercise(try await bench(api))

        api.failure = URLError(.notConnectedToInternet)
        for weight in ["80", "82.5", "85"] {
            model.weightInput = weight
            model.repsInput = "5"
            await model.logSet()
        }
        #expect(model.pendingSets.map(\.weight) == [80, 82.5, 85])

        api.failure = nil
        await model.flushPendingSets()
        let logged = try #require(model.session?.exercises.first?.sets)
        #expect(logged.map(\.weightKg) == [80, 82.5, 85])
    }

    @Test func aLostReplyIsResentWithoutLoggingTwice() async throws {
        let (model, api) = signedInModel()
        await model.startWorkout()
        await model.addExercise(try await bench(api))

        // The set reaches the server; the reply never comes back.
        api.dropNextLogSetResponse = true
        await model.logSet()
        #expect(model.pendingSets.count == 1)

        await model.flushPendingSets()
        #expect(model.pendingSets.isEmpty)
        #expect(model.setsLoggedCount == 1)
    }

    @Test func finishingWaitsForQueuedSets() async throws {
        let (model, api) = signedInModel()
        await model.startWorkout()
        await model.addExercise(try await bench(api))

        api.failure = URLError(.notConnectedToInternet)
        await model.logSet()
        await model.finishWorkout()
        #expect(model.sessionActive)
        #expect(!model.showingSummary)
        #expect(model.errorMessage == "1 set hasn't synced yet. Finish once you're back online so they count.")

        api.failure = nil
        await model.finishWorkout()
        #expect(model.showingSummary)
        #expect(model.finishResult?.session.workingSets == 1)
        #expect(model.pendingSets.isEmpty)
    }

    @Test func aQueuedSetTheServerRejectsIsDroppedWithAMessage() async throws {
        let (model, api) = signedInModel()
        await model.startWorkout()
        await model.addExercise(try await bench(api))

        api.failure = URLError(.notConnectedToInternet)
        await model.logSet()
        // Meanwhile the workout was ended on another device.
        api.failure = nil
        try await api.abandonSession(sessionID: try #require(model.session?.id))

        await model.flushPendingSets()
        #expect(model.pendingSets.isEmpty)
        #expect(model.errorMessage == "A set saved offline couldn't be logged: Workout not found")
    }

    @Test func theQueueSurvivesARelaunch() throws {
        let file = FileManager.default.temporaryDirectory.appending(path: "pending-\(UUID().uuidString).json")
        defer { try? FileManager.default.removeItem(at: file) }
        let set = PendingSet(clientSetID: UUID(), sessionID: "s1", exerciseID: "e1", weight: 100, unit: .lb, reps: 5)

        PendingSetStore(fileURL: file).save([set])
        let relaunched = AppModel(api: MockAPIClient(), pendingStore: PendingSetStore(fileURL: file))
        #expect(relaunched.pendingSets == [set])

        // An empty queue leaves no file behind.
        PendingSetStore(fileURL: file).save([])
        #expect(!FileManager.default.fileExists(atPath: file.path()))
    }

    @Test func partiesLoadThisWeeksRaid() async {
        let (model, _) = signedInModel()
        await model.loadParties()
        #expect(model.partyRaid?.name == "Iron Golem")
        #expect(model.partyRaid?.partyId == model.selectedPartyID)
    }

    @Test func choosingAClassHighlightsItsStats() async {
        let (model, _) = signedInModel()
        await model.loadProfile()
        #expect(model.characterSheet?.stats.allSatisfy { !$0.highlighted } == true)

        await model.chooseClass("powerlifter")
        #expect(model.characterSheet?.classLabel == "Powerlifter")
        #expect(model.characterSheet?.stats.filter(\.highlighted).map(\.key) == ["strength"])

        // Tapping the same class again clears it.
        await model.chooseClass("powerlifter")
        #expect(model.characterSheet?.characterClass == "")
        #expect(model.characterSheet?.stats.contains { $0.highlighted } == false)
    }

    @Test func profileLoadsTheRankTrials() async {
        let (model, _) = signedInModel()
        await model.loadProfile()
        #expect(model.rankTrials.map(\.rank) == ["B", "A", "S"])
        #expect(model.rankTrials.first?.description == "Barbell Bench Press at 1x bodyweight")
    }

    @Test func addingAnExerciseLoadsWhatToTryNext() async throws {
        let (model, _) = signedInModel()
        await model.searchExercises("Bench")
        let bench = try #require(model.pickerResults.first { $0.id == ContractFixtures.benchID })
        await model.addExercise(bench)
        #expect(model.hints[bench.id]?.text == "Try 87.5 kg x 5")
        #expect(model.ghostSets[bench.id]?.isEmpty == false)
    }

    @Test func importingAnExportReportsWhatLanded() async {
        let (model, _) = signedInModel()
        await model.importWorkouts(csv: "Date,Workout Name,Exercise Name,Set Order\n")
        #expect(model.importSummary.hasPrefix("Imported 42 workouts"))
        #expect(model.errorMessage.isEmpty)
        #expect(model.rankTrials.count == 3)
    }

    @Test func importingSomethingElseShowsTheError() async {
        let (model, _) = signedInModel()
        await model.importWorkouts(csv: "name,value\n")
        #expect(model.importSummary.isEmpty)
        #expect(model.errorMessage.hasPrefix("Couldn't import that file"))
    }

    @Test func progressTabsComeFromTheUsersRecords() async {
        let (model, _) = signedInModel()
        await model.loadProgress()
        #expect(model.progressTabs.map(\.name) == ["Barbell Bench Press", "Barbell Back Squat"])
        #expect(model.selectedProgressID == ContractFixtures.benchID)
        #expect(model.history.count == 4)
        #expect(model.records.allSatisfy { $0.exerciseId == ContractFixtures.benchID })
    }

    @Test func partiesShowTheWeeklyBoard() async {
        let (model, _) = signedInModel()
        await model.loadParties()
        #expect(model.parties.count == 1)
        #expect(model.partyBoard?.entries.first?.isMe == true)

        await model.createParty(name: "Leg Day Club")
        #expect(model.parties.count == 2)
        #expect(model.selectedParty?.name == "Leg Day Club")

        await model.joinParty(inviteCode: "nope")
        #expect(model.errorMessage == "Couldn't join the party: No party with that invite code")
    }

    @Test func deletingTheAccountNeedsThePassword() async {
        let (model, _) = signedInModel()
        #expect(await model.deleteAccount(password: "guess") == false)
        #expect(model.errorMessage == "Couldn't delete your account: Password is incorrect")
        #expect(model.isSignedIn)
        #expect(await model.deleteAccount(password: MockAPIClient.password))
        #expect(!model.isSignedIn)
    }

    @Test func anExpiredSessionReturnsToSignIn() async {
        let (model, api) = signedInModel()
        await model.loadHome()
        api.expireSession()
        #expect(!model.isSignedIn)
        #expect(model.me == nil)
    }
}
