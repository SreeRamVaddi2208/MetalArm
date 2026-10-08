// The LevelForge /api/v1 endpoints the app uses (docs/api-contract.md) - one
// to one with the iOS app's API/MetalArmAPI.swift, so the two clients stay
// easy to compare.

package com.sreeram.metalarm.api

import java.io.IOException
import java.util.UUID

/** A failure the server explained, or the session ending. */
sealed class ApiException(message: String) : Exception(message) {
    class Http(val status: Int, val detail: String) : ApiException(detail)
    class InvalidResponse : ApiException("The server sent an unexpected response.")
    class SignedOut : ApiException("Your session has ended. Please sign in again.")
}

val Throwable.httpStatus: Int? get() = (this as? ApiException.Http)?.status

/** No signal, server unreachable, timed out: worth queueing and retrying. */
val Throwable.isConnectivityFailure: Boolean get() = this is IOException

interface MetalArmApi {
    val isSignedIn: Boolean
    /** Called when the server rejects the stored tokens and refreshing fails. */
    var onSignedOut: (() -> Unit)?

    // Account
    suspend fun signIn(email: String, password: String)
    suspend fun signUp(email: String, password: String, displayName: String, timezone: String)
    /** Forgets this device's tokens and, best effort, ends its server session. */
    suspend fun signOut()
    /** Revokes every token the account holds, on every device. */
    suspend fun signOutEverywhere()
    suspend fun deleteAccount(password: String)
    suspend fun me(): Me
    suspend fun updateWeightUnit(unit: WeightUnit): Me
    suspend fun profile(): Profile
    suspend fun rankTrials(): List<RankTrial>
    suspend fun character(): CharacterSheet
    suspend fun updateCharacterClass(value: String): Me
    suspend fun trainingPaths(): List<TrainingPath>
    suspend fun importWorkouts(csv: String, unit: WeightUnit): WorkoutImportResult
    suspend fun points(): PointsSummary

    // Exercises and progress
    suspend fun searchExercises(query: String): List<Exercise>
    suspend fun lastPerformance(exerciseId: String): LastPerformance
    suspend fun exerciseHistory(exerciseId: String): List<HistoryPoint>
    suspend fun records(exerciseId: String?): List<WorkoutRecord>

    // Workouts
    suspend fun activeSession(): WorkoutSession?
    suspend fun session(id: String): WorkoutSession
    suspend fun presets(): List<WorkoutPreset>
    suspend fun startSession(presetSlug: String? = null): WorkoutSession
    suspend fun logSet(sessionId: String, exerciseId: String, weight: Double, unit: WeightUnit, reps: Int, clientSetId: UUID): SetLogResult
    suspend fun finishSession(sessionId: String): FinishResult
    suspend fun abandonSession(sessionId: String)

    // The Library: ready-made programs and workouts for each training path
    suspend fun libraryHome(): LibraryHome
    suspend fun libraryPrograms(category: String?, filters: LibraryFilters): List<LibraryProgramCard>
    suspend fun libraryProgram(slug: String): LibraryProgram
    suspend fun libraryWorkouts(category: String?, filters: LibraryFilters): List<LibraryWorkoutCard>
    suspend fun libraryWorkout(slug: String): LibraryWorkout
    /** A live session pre-loaded with the workout's exercises. 409 if one is live. */
    suspend fun startLibraryWorkout(slug: String): WorkoutSession
    suspend fun saveLibraryWorkout(slug: String): SavedRoutine
    suspend fun followProgram(slug: String): Enrollment
    suspend fun unfollowProgram(slug: String): Enrollment

    // Parties
    suspend fun parties(): List<Party>
    suspend fun createParty(name: String): Party
    suspend fun joinParty(inviteCode: String): Party
    suspend fun partyLeaderboard(partyId: String): PartyBoard
    suspend fun partyRaid(partyId: String): PartyRaid
    suspend fun league(): League
}

/** Where the signed-in tokens live (platform/KeystoreTokenStore in the app). */
interface TokenStore {
    var tokens: TokenPair?
}

class InMemoryTokenStore(override var tokens: TokenPair? = null) : TokenStore
