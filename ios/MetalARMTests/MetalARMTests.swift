//
//  MetalARMTests.swift
//  MetalARMTests
//
//  Created by Vaddi Sree Rama Sai Sasi Sekhar on 13/09/26.
//

import Foundation
import Testing
@testable import MetalARM

// MARK: - Decoding the API_CONTRACT.md examples

@MainActor
struct ContractDecodingTests {
    private let decoder = LiveAPIClient.makeDecoder()

    private func decode<T: Decodable>(_ type: T.Type, _ json: String) throws -> T {
        try decoder.decode(type, from: Data(json.utf8))
    }

    @Test func user() throws {
        let user = try decode(User.self, ContractFixtures.user)
        #expect(user.levelName == "Forged")
        #expect(user.xpToNextLevel == 3000)
        #expect(user.streakDays == 6)
    }

    @Test func logSetWithPR() throws {
        let result = try decode(LogSetResult.self, ContractFixtures.logSetWithPR)
        #expect(result.loggedSet.setNumber == 3)
        #expect(result.loggedSet.isPr)
        #expect(result.pr?.recordType == "max_weight")
        #expect(result.pr?.previousValue == 82.5)
        #expect(result.pointsAwarded == 2)
    }

    @Test func logSetWithoutPR() throws {
        let json = """
        {"set": {"id": 9002, "session_id": 501, "exercise_id": 1, "set_number": 4, "weight_kg": 80, "reps": 5, "is_warmup": false, "is_pr": false}, "pr": null, "points_awarded": 2}
        """
        let result = try decode(LogSetResult.self, json)
        #expect(result.pr == nil)
        #expect(!result.loggedSet.isPr)
    }

    @Test func workoutSummary() throws {
        let summary = try decode(WorkoutSummary.self, ContractFixtures.workoutSummary)
        #expect(summary.totalPoints == 185)
        #expect(summary.pointsBreakdown.streakBonus == 74)
        #expect(summary.newPrs.first?.exerciseName == "Barbell Bench Press")
        #expect(summary.level.xpRemaining == 860)
    }

    @Test func contractHeadlinePRReadsAsWeightTimesReps() throws {
        let summary = try decode(WorkoutSummary.self, ContractFixtures.workoutSummary)
        #expect(summary.headlinePR?.detail == "85 kg × 7 reps")
    }

    // Regression: the summary showed new_prs[0] (sorted by type), so a reps record read "8 kg × 8 reps".
    @Test func headlinePRUsesBackendPriorityNotListOrder() throws {
        var summary = try decode(WorkoutSummary.self, ContractFixtures.workoutSummary)
        summary.newPrs = [
            NewPR(exerciseName: "Barbell Bench Press", recordType: "max_reps_at_weight", value: 8, reps: 8),
            NewPR(exerciseName: "Barbell Bench Press", recordType: "max_volume", value: 640, reps: 8),
        ]
        #expect(summary.headlinePR?.recordType == "max_volume")
        #expect(summary.headlinePR?.detail == "640 kg set volume")
        #expect(summary.newPrs[0].detail == "8 reps (most at this weight)")
    }

    @Test func progressAndRecords() throws {
        let progress = try decode(ProgressData.self, ContractFixtures.progress)
        #expect(progress.changeSinceStart == 12.5)
        #expect(progress.points.last?.value == 85)
        let records = try decode([RecordItem].self, ContractFixtures.records)
        #expect(records.map(\.label) == ["Heaviest", "Best est. 1RM"])
    }

    @Test func leaderboardStreakIsOptional() throws {
        let entries = try decode([LeaderboardEntry].self, ContractFixtures.leaderboard)
        #expect(entries.first?.isCurrentUser == true)
        #expect(entries.first?.streakDays == nil)
        #expect(entries.last?.streakDays == 5)
    }

    @Test func profileUserHasNoStreak() throws {
        let profile = try decode(ProfileData.self, ContractFixtures.profile)
        #expect(profile.user.streakDays == nil)
        #expect(profile.stats.prsSet == 23)
        #expect(profile.badges.count == 2)
    }

    @Test func friendActivity() throws {
        let feed = try decode([FriendActivity].self, ContractFixtures.friendActivity)
        #expect(feed.map(\.userName) == ["Arjun", "Meera"])
        #expect(feed.first?.hoursAgo == 2)
    }
}

// MARK: - LiveAPIClient against a stubbed network

nonisolated final class StubURLProtocol: URLProtocol {
    nonisolated(unsafe) static var response: (status: Int, body: String) = (200, "{}")
    nonisolated(unsafe) static var lastRequest: URLRequest?
    nonisolated(unsafe) static var lastBody: Data?

    override class func canInit(with request: URLRequest) -> Bool { true }

    override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }

    override func startLoading() {
        Self.lastRequest = request
        // URLSession moves httpBody into a stream before it reaches a URLProtocol.
        Self.lastBody = request.httpBody ?? request.httpBodyStream.map(Self.readAll)
        let httpResponse = HTTPURLResponse(
            url: request.url!, statusCode: Self.response.status, httpVersion: "HTTP/1.1",
            headerFields: ["Content-Type": "application/json"])!
        client?.urlProtocol(self, didReceive: httpResponse, cacheStoragePolicy: .notAllowed)
        client?.urlProtocol(self, didLoad: Data(Self.response.body.utf8))
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
    private func makeClient(status: Int = 200, body: String) -> LiveAPIClient {
        StubURLProtocol.response = (status, body)
        StubURLProtocol.lastRequest = nil
        StubURLProtocol.lastBody = nil
        let configuration = URLSessionConfiguration.ephemeral
        configuration.protocolClasses = [StubURLProtocol.self]
        return LiveAPIClient(baseURL: URL(string: "http://backend.test")!, session: URLSession(configuration: configuration))
    }

    @Test func meRequestsUsersMe() async throws {
        let user = try await makeClient(body: ContractFixtures.user).me()
        #expect(StubURLProtocol.lastRequest?.httpMethod == "GET")
        #expect(StubURLProtocol.lastRequest?.url?.path == "/users/me")
        #expect(user.name == "Sree Ram")
    }

    @Test func logSetPostsOnlyContractFields() async throws {
        let result = try await makeClient(status: 201, body: ContractFixtures.logSetWithPR)
            .logSet(sessionID: 501, exerciseID: 1, weightKg: 85, reps: 6)
        let request = try #require(StubURLProtocol.lastRequest)
        #expect(request.httpMethod == "POST")
        #expect(request.url?.path == "/sessions/501/sets")
        let body = try #require(StubURLProtocol.lastBody)
        let json = try #require(try JSONSerialization.jsonObject(with: body) as? [String: Any])
        #expect(json["exercise_id"] as? Int == 1)
        #expect(json["weight_kg"] as? Double == 85)
        #expect(json["reps"] as? Int == 6)
        #expect(json["is_warmup"] as? Bool == false)
        // Points and PRs are server-computed; the client must never send them.
        #expect(json["points"] == nil)
        #expect(json["is_pr"] == nil)
        #expect(result.pr?.value == 85)
    }

    @Test func leaderboardAsksForThisWeek() async throws {
        _ = try await makeClient(body: ContractFixtures.leaderboard).leaderboard()
        #expect(StubURLProtocol.lastRequest?.url?.query == "period=week")
    }

    @Test func progressAsksForMaxWeightOverOneYear() async throws {
        _ = try await makeClient(body: ContractFixtures.progress).progress(exerciseID: 2)
        #expect(StubURLProtocol.lastRequest?.url?.path == "/progress/2")
        #expect(StubURLProtocol.lastRequest?.url?.query == "metric=max_weight&range=1y")
    }

    @Test func errorStatusSurfacesServerDetail() async {
        let client = makeClient(status: 400, body: #"{"detail": "Session already finished"}"#)
        await #expect(throws: APIError.http(status: 400, detail: "Session already finished")) {
            _ = try await client.finishSession(sessionID: 501)
        }
    }
}

// MARK: - AppModel (ported AppState) with the mock backend

@MainActor
struct AppModelTests {
    @Test func loadHomeFillsUserAndFeed() async {
        let model = AppModel(api: MockAPIClient())
        await model.loadHome()
        #expect(model.user?.name == "Sree Ram")
        #expect(model.friendActivity.count == 2)
        #expect(abs(model.xpProgress - 2140.0 / 3000.0) < 0.0001)
    }

    @Test func startWorkoutPicksBenchAndOpensSession() async {
        let model = AppModel(api: MockAPIClient())
        await model.startWorkout()
        #expect(model.sessionActive)
        #expect(model.activeExercise?.name == "Barbell Bench Press")
        #expect(model.activeExerciseMuscleLabel == "Chest, Triceps")
        #expect(model.setsLogged.isEmpty)
    }

    @Test func loggingASetAddsRowShowsPRAndStartsRest() async {
        let model = AppModel(api: MockAPIClient())
        await model.startWorkout()
        await model.logCurrentSet()
        #expect(model.setsLogged.count == 1)
        #expect(model.setsLogged.first?.weightKg == 80)
        #expect(model.prHint == "New max weight: 80")
        #expect(model.resting)
        #expect(model.restDisplay == "1:30")
        model.stopRestTimer()
        #expect(!model.resting)
    }

    @Test func secondSetClearsPRHint() async {
        let model = AppModel(api: MockAPIClient())
        await model.startWorkout()
        await model.logCurrentSet()
        await model.logCurrentSet()
        #expect(model.setsLogged.count == 2)
        #expect(model.prHint.isEmpty)
        model.stopRestTimer()
    }

    @Test func nonNumericInputShowsErrorWithoutLogging() async {
        let model = AppModel(api: MockAPIClient())
        await model.startWorkout()
        model.weightInput = "heavy"
        await model.logCurrentSet()
        #expect(model.errorMessage == "Weight and reps need to be numbers.")
        #expect(model.setsLogged.isEmpty)
        #expect(!model.resting)
    }

    @Test func finishingShowsSummaryAndEndsSession() async {
        let model = AppModel(api: MockAPIClient())
        await model.startWorkout()
        await model.logCurrentSet()
        await model.finishWorkout()
        #expect(model.showingSummary)
        #expect(!model.sessionActive)
        #expect(!model.resting)
        #expect(model.summary?.totalPoints == 185)
        #expect(model.summaryXPRemaining == 860)
    }

    // Regression: tabs used to hardcode ids 1/2/3, so "Squat" loaded Incline Dumbbell Press.
    @Test func progressTabsResolveSeededExerciseIDsByName() async {
        let model = AppModel(api: MockAPIClient())
        await model.loadProgress()
        #expect(model.progressTabs.map(\.name) == ["Bench Press", "Squat", "Deadlift"])
        #expect(model.progressTabs.map(\.id) == [1, 3, 5])
        #expect(model.selectedExerciseID == 1)
    }

    @Test func switchingProgressTabLoadsThatExercise() async {
        let model = AppModel(api: MockAPIClient())
        await model.loadProgress()
        await model.selectExercise(3)
        #expect(model.selectedExerciseID == 3)
        #expect(model.progress?.unit == "kg")
        #expect(model.records.count == 2)
    }

    @Test func profileCountsEarnedBadgesAndKeepsStreak() async {
        let model = AppModel(api: MockAPIClient())
        await model.loadProfile()
        #expect(model.badgesEarnedCount == 1)
        #expect(model.user?.streakDays == 6)
        #expect(model.profileStats?.workouts == 142)
    }

    @Test func backendFailureShowsErrorMessage() async {
        let api = MockAPIClient()
        api.failure = APIError.http(status: 500, detail: "boom")
        let model = AppModel(api: api)
        await model.loadHome()
        #expect(model.errorMessage == "Couldn't reach the backend: boom (HTTP 500)")
        #expect(model.user == nil)
    }
}

// MARK: - Formatting helpers

@MainActor
struct FormattingTests {
    @Test(arguments: zip([85.0, 82.5, 142.25, 0], ["85", "82.5", "142.25", "0"]))
    func formatsNumbersLikeTheBackend(value: Double, expected: String) {
        #expect(formatNumber(value) == expected)
    }

    @Test func initialsUseFirstTwoWords() {
        #expect(initials(of: "Sree Ram") == "SR")
        #expect(initials(of: "meera") == "M")
    }
}
