package com.sreeram.metalarm

import com.sreeram.metalarm.api.ApiException
import com.sreeram.metalarm.api.ContractFixtures
import com.sreeram.metalarm.api.InMemoryTokenStore
import com.sreeram.metalarm.api.LiveApi
import com.sreeram.metalarm.api.MetalArmJson
import com.sreeram.metalarm.api.TokenPair
import com.sreeram.metalarm.api.WeightUnit
import kotlinx.coroutines.test.runTest
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import okhttp3.Interceptor
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Protocol
import okhttp3.Request
import okhttp3.Response
import okhttp3.ResponseBody.Companion.toResponseBody
import okio.Buffer
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Test
import java.util.UUID

/** The transport, against canned replies: tokens, refresh, bodies, errors. */
class LiveApiTest {
    private val signedIn = TokenPair("access-1", "bearer", 3600, "refresh-1", 2_592_000)

    private class Stub(private val replies: MutableList<Pair<Int, String>>) : Interceptor {
        val requests = mutableListOf<Request>()
        val bodies = mutableListOf<String>()
        override fun intercept(chain: Interceptor.Chain): Response {
            val request = chain.request()
            requests += request
            bodies += request.body?.let { body -> Buffer().also { body.writeTo(it) }.readUtf8() } ?: ""
            val (status, text) = replies.removeAt(0)
            return Response.Builder().request(request).protocol(Protocol.HTTP_1_1).code(status).message("stub")
                .body(text.toResponseBody("application/json".toMediaType())).build()
        }
    }

    private fun client(tokens: TokenPair? = null, vararg replies: Pair<Int, String>): Triple<LiveApi, InMemoryTokenStore, Stub> {
        val stub = Stub(replies.toMutableList())
        val store = InMemoryTokenStore(tokens)
        val api = LiveApi("http://backend.test", store, OkHttpClient.Builder().addInterceptor(stub).build())
        return Triple(api, store, stub)
    }

    private fun json(text: String): JsonObject = MetalArmJson.parseToJsonElement(text).jsonObject
    private fun JsonObject.string(key: String) = this[key]?.jsonPrimitive?.content

    @Test fun signInStoresBothTokens() = runTest {
        val (api, store, stub) = client(null, 200 to ContractFixtures.tokens)
        api.signIn("sree@metalarm.dev", "correct-horse-1")
        assertEquals("refresh-1", store.tokens?.refreshToken)
        assertEquals("/api/v1/auth/login", stub.requests.first().url.encodedPath)
        assertNull(stub.requests.first().header("Authorization"))
        assertEquals("sree@metalarm.dev", json(stub.bodies[0]).string("email"))
    }

    @Test fun requestsCarryTheAccessToken() = runTest {
        val (api, _, stub) = client(signedIn, 200 to ContractFixtures.me)
        api.me()
        assertEquals("Bearer access-1", stub.requests.first().header("Authorization"))
    }

    @Test fun anExpiredAccessTokenIsRefreshedAndTheRequestRetried() = runTest {
        val refreshed = """{"access_token": "access-2", "token_type": "bearer", "expires_in": 3600, "refresh_token": "refresh-2", "refresh_expires_in": 2592000}"""
        val (api, store, stub) = client(
            signedIn, 401 to """{"detail": "Token has expired"}""", 200 to refreshed, 200 to ContractFixtures.me,
        )
        assertEquals("Sree Ram", api.me().displayName)
        assertEquals(listOf("/api/v1/auth/me", "/api/v1/auth/refresh", "/api/v1/auth/me"), stub.requests.map { it.url.encodedPath })
        assertEquals("refresh-1", json(stub.bodies[1]).string("refresh_token"))
        assertEquals("Bearer access-2", stub.requests.last().header("Authorization"))
        assertEquals("refresh-2", store.tokens?.refreshToken)
    }

    @Test fun aRejectedRefreshSignsOut() = runTest {
        val (api, store, _) = client(
            signedIn, 401 to """{"detail": "Token has expired"}""",
            401 to """{"detail": "Refresh token is invalid or expired - sign in again"}""",
        )
        var signedOut = false
        api.onSignedOut = { signedOut = true }
        try {
            api.me()
            fail("expected SignedOut")
        } catch (expected: ApiException.SignedOut) {
        }
        assertNull(store.tokens)
        assertTrue(signedOut)
    }

    @Test fun logSetSendsClientSetIdAndUnitButNoPoints() = runTest {
        val (api, _, stub) = client(signedIn, 201 to ContractFixtures.setLogResult)
        val clientSetId = UUID.randomUUID()
        api.logSet(ContractFixtures.sessionID, ContractFixtures.benchID, 225.0, WeightUnit.Lb, 5, clientSetId)
        assertEquals("/api/v1/workouts/sessions/${ContractFixtures.sessionID}/sets", stub.requests.first().url.encodedPath)
        val sent = json(stub.bodies[0])
        assertEquals(ContractFixtures.benchID, sent.string("exercise_id"))
        assertEquals("225.0", sent.string("weight"))
        assertEquals("lb", sent.string("unit"))
        assertEquals("5", sent.string("reps"))
        assertEquals(clientSetId.toString(), sent.string("client_set_id"))
        // Points and PRs are computed by the server; the client never sends them.
        assertNull(sent["points"])
    }

    @Test fun validationErrorsAreReadable() = runTest {
        val issue = """{"detail": [{"loc": ["body", "password"], "msg": "String should have at least 8 characters", "type": "string_too_short"}]}"""
        val (api, _, _) = client(null, 422 to issue)
        try {
            api.signUp("a@metalarm.dev", "short", "A", "UTC")
            fail("expected Http")
        } catch (error: ApiException.Http) {
            assertEquals(422, error.status)
            assertEquals("String should have at least 8 characters", error.detail)
        }
    }

    @Test fun equipmentRepeatsInTheQuery() = runTest {
        val (api, _, stub) = client(signedIn, 200 to "[]")
        api.libraryWorkouts("athlete", com.sreeram.metalarm.api.LibraryFilters(equipment = listOf("barbell", "dumbbell"), maxMinutes = 30))
        val url = stub.requests.first().url
        assertEquals(listOf("barbell", "dumbbell"), url.queryParameterValues("equipment"))
        assertEquals("30", url.queryParameter("max_minutes"))
        assertEquals("athlete", url.queryParameter("category"))
    }

    @Test fun signingOutEndsThisDeviceOnTheServer() = runTest {
        val (api, store, stub) = client(signedIn, 204 to "")
        api.signOut()
        val request = stub.requests.single()
        assertEquals("POST", request.method)
        assertEquals("/api/v1/auth/logout", request.url.encodedPath)
        assertEquals("refresh-1", json(stub.bodies[0]).string("refresh_token"))
        assertNull(request.header("Authorization"))
        assertNull(store.tokens)
    }

    @Test fun signingOutWhenAlreadySignedOutSendsNothing() = runTest {
        val (api, _, stub) = client(null)
        api.signOut()
        assertTrue(stub.requests.isEmpty())
    }

    @Test fun signingOutStillForgetsTokensWhenTheServerFails() = runTest {
        val (api, store, _) = client(signedIn, 503 to """{"detail": "Service unavailable"}""")
        api.signOut()
        assertNull(store.tokens)
    }

    @Test fun deletingTheAccountSendsThePasswordAndForgetsTokens() = runTest {
        val (api, store, stub) = client(signedIn, 204 to "")
        api.deleteAccount("correct-horse-1")
        val request = stub.requests.single()
        assertEquals("DELETE", request.method)
        assertEquals("/api/v1/auth/me", request.url.encodedPath)
        assertEquals("correct-horse-1", json(stub.bodies[0]).string("password"))
        assertNull(store.tokens)
    }
}
