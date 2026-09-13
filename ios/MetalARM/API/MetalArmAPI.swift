//
//  MetalArmAPI.swift
//  MetalARM
//
//  One method per endpoint in API_CONTRACT.md — the same set as frontend/frontend/api.py.
//

protocol MetalArmAPI: AnyObject {
    func me() async throws -> User
    func exercises() async throws -> [Exercise]
    func startSession() async throws -> SessionStart
    func logSet(sessionID: Int, exerciseID: Int, weightKg: Double, reps: Int) async throws -> LogSetResult
    func finishSession(sessionID: Int) async throws -> WorkoutSummary
    func progress(exerciseID: Int) async throws -> ProgressData
    func records(exerciseID: Int) async throws -> [RecordItem]
    func leaderboard() async throws -> [LeaderboardEntry]
    func profile() async throws -> ProfileData
    func friendActivity() async throws -> [FriendActivity]
}
