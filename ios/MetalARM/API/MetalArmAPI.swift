//
//  MetalArmAPI.swift
//  MetalARM
//
//  The LevelForge /api/v1 endpoints the app uses (see docs/api-contract.md
//  and docs/workouts-api.md).
//

import Foundation

protocol MetalArmAPI: AnyObject {
    var isSignedIn: Bool { get }
    /// Called when the server rejects the stored tokens and refreshing fails.
    var onSignedOut: (() -> Void)? { get set }

    // Account
    func signIn(email: String, password: String) async throws
    func signUp(email: String, password: String, displayName: String, timezone: String) async throws
    /// Ends this device's session on the server (best effort) and forgets its
    /// tokens, even when the server can't be reached.
    func signOut() async
    /// Revokes every token the account holds, on every device.
    func signOutEverywhere() async throws
    func deleteAccount(password: String) async throws
    func me() async throws -> Me
    func updateWeightUnit(_ unit: WeightUnit) async throws -> Me
    func profile() async throws -> Profile
    func rankTrials() async throws -> [RankTrial]
    func character() async throws -> CharacterSheet
    func updateCharacterClass(_ value: String) async throws -> Me
    func importWorkouts(csv: String, unit: WeightUnit) async throws -> WorkoutImportResult
    func points() async throws -> PointsSummary

    // Exercises and progress
    func searchExercises(query: String) async throws -> [Exercise]
    func lastPerformance(exerciseID: String) async throws -> LastPerformance
    func exerciseHistory(exerciseID: String) async throws -> [HistoryPoint]
    func records(exerciseID: String?) async throws -> [WorkoutRecord]

    // Workouts
    func activeSession() async throws -> WorkoutSession?
    func session(id: String) async throws -> WorkoutSession
    /// The ready-made workouts, one per training style.
    func presets() async throws -> [WorkoutPreset]
    /// Blank, or loaded with a preset's exercises and targets.
    func startSession(presetSlug: String?) async throws -> WorkoutSession
    func logSet(sessionID: String, exerciseID: String, weight: Double, unit: WeightUnit, reps: Int, clientSetID: UUID) async throws -> SetLogResult
    func finishSession(sessionID: String) async throws -> FinishResult
    func abandonSession(sessionID: String) async throws

    // Parties
    func parties() async throws -> [Party]
    func createParty(name: String) async throws -> Party
    func joinParty(inviteCode: String) async throws -> Party
    func partyLeaderboard(partyID: String) async throws -> PartyBoard
    func partyRaid(partyID: String) async throws -> PartyRaid
    func league() async throws -> League
}
