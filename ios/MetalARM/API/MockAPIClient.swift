//
//  MockAPIClient.swift
//  MetalARM
//
//  Serves the API_CONTRACT.md examples without a backend. Used by SwiftUI
//  previews, unit tests, and UI tests (launch argument -UITestMockAPI).
//

import Foundation

final class MockAPIClient: MetalArmAPI {
    /// When set, every call throws this instead of returning data.
    var failure: Error?

    private var setsInSession = 0
    private let decoder = LiveAPIClient.makeDecoder()

    private func fixture<T: Decodable>(_ json: String) throws -> T {
        if let failure { throw failure }
        return try decoder.decode(T.self, from: Data(json.utf8))
    }

    func me() async throws -> User { try fixture(ContractFixtures.user) }

    func exercises() async throws -> [Exercise] { try fixture(ContractFixtures.exercises) }

    func startSession() async throws -> SessionStart {
        let session: SessionStart = try fixture(ContractFixtures.sessionStart)
        setsInSession = 0
        return session
    }

    // The first set of a session counts as a max-weight PR, like a fresh exercise on the backend.
    func logSet(sessionID: Int, exerciseID: Int, weightKg: Double, reps: Int) async throws -> LogSetResult {
        if let failure { throw failure }
        setsInSession += 1
        let isFirst = setsInSession == 1
        let loggedSet = LoggedSet(
            id: 9000 + setsInSession, sessionId: sessionID, exerciseId: exerciseID,
            setNumber: setsInSession, weightKg: weightKg, reps: reps, isWarmup: false, isPr: isFirst)
        return LogSetResult(
            loggedSet: loggedSet,
            pr: isFirst ? SetPR(recordType: "max_weight", value: weightKg, previousValue: nil) : nil,
            pointsAwarded: 2)
    }

    func finishSession(sessionID: Int) async throws -> WorkoutSummary { try fixture(ContractFixtures.workoutSummary) }

    func progress(exerciseID: Int) async throws -> ProgressData { try fixture(ContractFixtures.progress) }

    func records(exerciseID: Int) async throws -> [RecordItem] { try fixture(ContractFixtures.records) }

    func leaderboard() async throws -> [LeaderboardEntry] { try fixture(ContractFixtures.leaderboard) }

    func profile() async throws -> ProfileData { try fixture(ContractFixtures.profile) }

    func friendActivity() async throws -> [FriendActivity] { try fixture(ContractFixtures.friendActivity) }
}
