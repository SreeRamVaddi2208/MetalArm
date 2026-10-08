// Talks to the MetalArm backend - the twin of the iOS LiveAPIClient. Sends the
// access token on every request; when it has expired (401), swaps the refresh
// token for a new pair once and retries. If that fails too, the tokens are
// dropped and onSignedOut fires. A network failure during the refresh keeps
// the tokens: a blip must not sign the user out.

package com.sreeram.metalarm.api

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.serializer
import okhttp3.HttpUrl
import okhttp3.HttpUrl.Companion.toHttpUrl
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import java.util.UUID
import java.util.concurrent.TimeUnit

class LiveApi(
    baseUrl: String,
    private val tokenStore: TokenStore,
    private val client: OkHttpClient = defaultClient(),
) : MetalArmApi {
    private val base: HttpUrl = baseUrl.trimEnd('/').toHttpUrl()
    private val refreshLock = Mutex()

    override var onSignedOut: (() -> Unit)? = null
    override val isSignedIn: Boolean get() = tokenStore.tokens != null

    // Account

    override suspend fun signIn(email: String, password: String) {
        tokenStore.tokens = send(post("auth/login", LoginBody(email, password)), authenticated = false)
    }

    override suspend fun signUp(email: String, password: String, displayName: String, timezone: String) {
        send<Me>(post("auth/signup", SignupBody(email, password, displayName, timezone)), authenticated = false)
        signIn(email, password)
    }

    override suspend fun signOut() {
        // Forget the tokens first, so the sign-out holds even if the app dies
        // mid-request; then, best effort, revoke this device's session.
        val tokens = tokenStore.tokens ?: return
        tokenStore.tokens = null
        runCatching { perform(post("auth/logout", RefreshBody(tokens.refreshToken)), authenticated = false) }
    }

    override suspend fun signOutEverywhere() {
        perform(post("auth/logout-all", EmptyBody()), authenticated = true)
        tokenStore.tokens = null
    }

    override suspend fun deleteAccount(password: String) {
        perform(delete("auth/me", PasswordBody(password)), authenticated = true)
        tokenStore.tokens = null
    }

    override suspend fun me(): Me = send(get("auth/me"))
    override suspend fun updateWeightUnit(unit: WeightUnit): Me = send(patch("auth/me", WeightUnitBody(unit.raw)))
    override suspend fun profile(): Profile = send(get("profile"))
    override suspend fun rankTrials(): List<RankTrial> = send(get("profile/trials"))
    override suspend fun character(): CharacterSheet = send(get("profile/character"))
    override suspend fun updateCharacterClass(value: String): Me = send(patch("auth/me", CharacterClassBody(value)))
    override suspend fun trainingPaths(): List<TrainingPath> = send(get("training-categories"))
    override suspend fun importWorkouts(csv: String, unit: WeightUnit): WorkoutImportResult =
        send(post("workouts/import", ImportBody(csv, unit.raw)))
    override suspend fun points(): PointsSummary = send(get("workouts/points"))

    // Exercises and progress

    override suspend fun searchExercises(query: String): List<Exercise> {
        val parameters = mutableMapOf("limit" to "50")
        if (query.isNotBlank()) parameters["q"] = query.trim()
        return send(get("exercises", parameters))
    }

    override suspend fun lastPerformance(exerciseId: String): LastPerformance =
        send(get("exercises/$exerciseId/last-performance"))
    override suspend fun exerciseHistory(exerciseId: String): List<HistoryPoint> =
        send(get("exercises/$exerciseId/history"))
    override suspend fun records(exerciseId: String?): List<WorkoutRecord> =
        send(get("workouts/records", exerciseId?.let { mapOf("exercise_id" to it) } ?: emptyMap()))

    // Workouts

    override suspend fun activeSession(): WorkoutSession? = send<ActiveSession>(get("workouts/sessions/active")).session
    override suspend fun session(id: String): WorkoutSession = send(get("workouts/sessions/$id"))
    override suspend fun presets(): List<WorkoutPreset> = send(get("workouts/presets"))

    override suspend fun startSession(presetSlug: String?): WorkoutSession =
        if (presetSlug == null) send(post("workouts/sessions", EmptyBody()))
        else send(post("workouts/sessions", PresetStart(presetSlug)))

    override suspend fun logSet(
        sessionId: String, exerciseId: String, weight: Double, unit: WeightUnit, reps: Int, clientSetId: UUID,
    ): SetLogResult = send(post("workouts/sessions/$sessionId/sets", SetBody(exerciseId, weight, unit.raw, reps, clientSetId.toString())))

    override suspend fun finishSession(sessionId: String): FinishResult =
        send(post("workouts/sessions/$sessionId/finish", EmptyBody()))

    override suspend fun abandonSession(sessionId: String) {
        perform(post("workouts/sessions/$sessionId/abandon", EmptyBody()), authenticated = true)
    }

    // Library

    override suspend fun libraryHome(): LibraryHome = send(get("library/home"))

    override suspend fun libraryPrograms(category: String?, filters: LibraryFilters): List<LibraryProgramCard> {
        val query = mutableMapOf<String, String>()
        category?.let { query["category"] = it }
        filters.difficulty?.let { query["difficulty"] = it }
        filters.daysPerWeek?.let { query["days_per_week"] = it.toString() }
        return send(get("library/programs", query, equipmentItems(filters)))
    }

    override suspend fun libraryProgram(slug: String): LibraryProgram = send(get("library/programs/$slug"))

    override suspend fun libraryWorkouts(category: String?, filters: LibraryFilters): List<LibraryWorkoutCard> {
        val query = mutableMapOf<String, String>()
        category?.let { query["category"] = it }
        filters.difficulty?.let { query["difficulty"] = it }
        filters.maxMinutes?.let { query["max_minutes"] = it.toString() }
        return send(get("library/workouts", query, equipmentItems(filters)))
    }

    override suspend fun libraryWorkout(slug: String): LibraryWorkout = send(get("library/workouts/$slug"))
    override suspend fun startLibraryWorkout(slug: String): WorkoutSession = send(post("library/workouts/$slug/start", EmptyBody()))
    override suspend fun saveLibraryWorkout(slug: String): SavedRoutine =
        send(post("library/workouts/$slug/save-to-routines", EmptyBody()))
    override suspend fun followProgram(slug: String): Enrollment = send(post("library/programs/$slug/follow", EmptyBody()))
    override suspend fun unfollowProgram(slug: String): Enrollment = send(delete("library/programs/$slug/follow", EmptyBody()))

    /** `equipment` repeats: "what can I do with these". */
    private fun equipmentItems(filters: LibraryFilters) = filters.equipment.map { "equipment" to it }

    // Parties

    override suspend fun parties(): List<Party> = send(get("parties"))
    override suspend fun createParty(name: String): Party = send(post("parties", PartyBody(name)))
    override suspend fun joinParty(inviteCode: String): Party = send(post("parties/join", JoinBody(inviteCode)))
    override suspend fun partyLeaderboard(partyId: String): PartyBoard =
        send(get("parties/$partyId/workout-leaderboard", mapOf("period" to "week")))
    override suspend fun partyRaid(partyId: String): PartyRaid = send(get("parties/$partyId/raid"))
    override suspend fun league(): League = send(get("leagues/current"))

    // Transport

    private class Spec(
        val method: String,
        val path: String,
        val query: Map<String, String> = emptyMap(),
        val repeated: List<Pair<String, String>> = emptyList(),
        val body: String? = null,
    )

    private fun get(path: String, query: Map<String, String> = emptyMap(), repeated: List<Pair<String, String>> = emptyList()) =
        Spec("GET", path, query, repeated)

    private inline fun <reified B> post(path: String, body: B) = Spec("POST", path, body = MetalArmJson.encodeToString(serializer<B>(), body))
    private inline fun <reified B> patch(path: String, body: B) = Spec("PATCH", path, body = MetalArmJson.encodeToString(serializer<B>(), body))
    private inline fun <reified B> delete(path: String, body: B) = Spec("DELETE", path, body = MetalArmJson.encodeToString(serializer<B>(), body))

    private suspend inline fun <reified T> send(spec: Spec, authenticated: Boolean = true): T {
        val text = perform(spec, authenticated)
        return try {
            MetalArmJson.decodeFromString(serializer<T>(), text)
        } catch (error: kotlinx.serialization.SerializationException) {
            throw ApiException.InvalidResponse()
        }
    }

    private suspend fun perform(spec: Spec, authenticated: Boolean, isRetry: Boolean = false): String {
        val builder = request(spec)
        if (authenticated) {
            val tokens = tokenStore.tokens ?: throw ApiException.SignedOut()
            builder.header("Authorization", "Bearer ${tokens.accessToken}")
        }
        val (status, text) = withContext(Dispatchers.IO) {
            client.newCall(builder.build()).execute().use { it.code to it.body.string() }
        }
        if (status == 401 && authenticated) {
            if (isRetry) {
                endSession()
                throw ApiException.SignedOut()
            }
            try {
                refreshTokens()
            } catch (error: ApiException) {
                if (error is ApiException.SignedOut || error.httpStatus == 401) {
                    endSession()
                    throw ApiException.SignedOut()
                }
                throw error
            }
            return perform(spec, authenticated = true, isRetry = true)
        }
        if (status !in 200..299) throw ApiException.Http(status, detail(text, status))
        return text
    }

    /** Concurrent 401s share one refresh instead of racing each other. */
    private suspend fun refreshTokens() {
        val stale = tokenStore.tokens
        refreshLock.withLock {
            // Someone else refreshed while this caller waited.
            if (tokenStore.tokens != stale && tokenStore.tokens != null) return
            val refreshToken = tokenStore.tokens?.refreshToken ?: throw ApiException.SignedOut()
            val text = perform(post("auth/refresh", RefreshBody(refreshToken)), authenticated = false)
            tokenStore.tokens = MetalArmJson.decodeFromString(TokenPair.serializer(), text)
        }
    }

    private fun endSession() {
        tokenStore.tokens = null
        onSignedOut?.invoke()
    }

    private fun request(spec: Spec): Request.Builder {
        val url = base.newBuilder().addPathSegments("api/v1/" + spec.path).apply {
            spec.query.toSortedMap().forEach { (key, value) -> addQueryParameter(key, value) }
            spec.repeated.forEach { (key, value) -> addQueryParameter(key, value) }
        }.build()
        val body = spec.body?.toRequestBody(JSON)
        return Request.Builder().url(url).header("Accept", "application/json").method(spec.method, body)
    }

    companion object {
        private val JSON = "application/json".toMediaType()

        fun defaultClient(): OkHttpClient = OkHttpClient.Builder()
            .callTimeout(15, TimeUnit.SECONDS)
            .build()

        /** FastAPI errors are {"detail": "..."} or {"detail": [{"msg": ...}]}. */
        fun detail(text: String, status: Int): String {
            val detail = runCatching { MetalArmJson.parseToJsonElement(text).jsonObject["detail"] }.getOrNull()
            return when (detail) {
                is JsonPrimitive -> detail.contentOrNull ?: fallback(status)
                is JsonArray -> detail.mapNotNull { issue ->
                    (issue as? JsonObject)?.get("msg")?.jsonPrimitive?.contentOrNull?.replace("Value error, ", "")
                }.joinToString("\n").ifEmpty { fallback(status) }
                else -> fallback(status)
            }
        }

        private fun fallback(status: Int) = when (status) {
            400 -> "Bad Request"
            403 -> "Forbidden"
            404 -> "Not Found"
            409 -> "Conflict"
            422 -> "Unprocessable Content"
            429 -> "Too Many Requests"
            in 500..599 -> "Internal Server Error"
            else -> "Request failed ($status)"
        }
    }
}

@Serializable private class EmptyBody
@Serializable private class LoginBody(val email: String, val password: String)
@Serializable private class SignupBody(val email: String, val password: String, val displayName: String, val timezone: String)
@Serializable private class RefreshBody(val refreshToken: String)
@Serializable private class PasswordBody(val password: String)
@Serializable private class WeightUnitBody(val weightUnit: String)
// No points or PR fields: the server computes those and ignores any sent.
@Serializable private class SetBody(val exerciseId: String, val weight: Double, val unit: String, val reps: Int, val clientSetId: String)
@Serializable private class PresetStart(val presetSlug: String)
@Serializable private class PartyBody(val name: String)
@Serializable private class JoinBody(val inviteCode: String)
@Serializable private class ImportBody(val csv: String, val unit: String)
@Serializable private class CharacterClassBody(val characterClass: String)

