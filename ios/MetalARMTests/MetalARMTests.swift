//
//  MetalARMTests.swift
//  MetalARMTests
//
//  Created by Vaddi Sree Rama Sai Sasi Sekhar on 13/09/26.
//

import Foundation
import Testing
@testable import MetalARM

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
        #expect(try decode(PointsSummary.self, ContractFixtures.points).thisWeekPoints == 185)
        let profile = try decode(Profile.self, ContractFixtures.profile)
        #expect(profile.stats.workoutsCompleted == 142)
        #expect(profile.badgesEarned == 3)
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
        #expect(request.value(forHTTPHeaderField: "Authorization") == "Bearer access-1")
        #expect(store.tokens == nil)
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
