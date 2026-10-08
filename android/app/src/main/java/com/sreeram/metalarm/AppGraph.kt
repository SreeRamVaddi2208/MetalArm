// Builds the one AppModel the app runs on, from the live backend or - for UI
// tests - the in-memory mock. Tests set `testConfig` before launching
// MainActivity, the way the iOS UI tests pass launch arguments.

package com.sreeram.metalarm

import android.content.Context
import com.sreeram.metalarm.api.LiveApi
import com.sreeram.metalarm.api.MockApi
import com.sreeram.metalarm.platform.AndroidNotifier
import com.sreeram.metalarm.platform.Connectivity
import com.sreeram.metalarm.platform.HealthConnectWriter
import com.sreeram.metalarm.platform.KeystoreTokenStore
import com.sreeram.metalarm.platform.SharedPrefs
import com.sreeram.metalarm.state.AppModel
import com.sreeram.metalarm.state.MemoryPrefs
import com.sreeram.metalarm.state.NoopNotifier
import com.sreeram.metalarm.state.UnavailableHealth
import com.sreeram.metalarm.state.PendingSetStore
import kotlinx.coroutines.MainScope
import kotlinx.coroutines.launch
import java.io.File

/** What a UI test asks for - the iOS -UITest* launch arguments. */
data class TestConfig(
    val signedIn: Boolean = true,
    val skipOnboarding: Boolean = true,
    val levelUpOnFinish: Boolean = false,
    val rankUpOnFinish: Boolean = false,
    val offline: Boolean = false,
    val noTrainingPath: Boolean = false,
    /** An account that already trains on this path. */
    val path: String = "",
    /** Run against a real backend instead of the mock (the live test). */
    val liveBaseUrl: String? = null,
)

object AppGraph {
    @Volatile var testConfig: TestConfig? = null

    private var model: AppModel? = null
    // Both hold the APPLICATION context, which lives as long as this object.
    @android.annotation.SuppressLint("StaticFieldLeak")
    lateinit var notifier: AndroidNotifier
        private set
    @android.annotation.SuppressLint("StaticFieldLeak")
    lateinit var health: HealthConnectWriter
        private set
    private val scope = MainScope()

    /** Onboarding is shown once per install. */
    fun hasOnboarded(context: Context): Boolean {
        testConfig?.let { if (it.skipOnboarding) return true }
        return settings(context).getBoolean(ONBOARDED) ?: false
    }

    fun setOnboarded(context: Context) = settings(context).putBoolean(ONBOARDED, true)

    private fun settings(context: Context) =
        if (testConfig != null && testConfig?.liveBaseUrl == null) testPrefs else SharedPrefs(context.applicationContext)

    private val testPrefs = MemoryPrefs()

    @Synchronized
    fun model(context: Context): AppModel {
        model?.let { return it }
        val app = context.applicationContext
        notifier = AndroidNotifier(app)
        health = HealthConnectWriter(app)
        val config = testConfig
        val built = if (config != null && config.liveBaseUrl == null) {
            val mock = MockApi(
                signedIn = config.signedIn, levelUpOnFinish = config.levelUpOnFinish,
                rankUpOnFinish = config.rankUpOnFinish, isOffline = config.offline,
                pathUnanswered = config.noTrainingPath,
            ).apply { characterClass = config.path }
            // The mock backend starts fresh every launch, so its queue does too.
            // No real notifier or Health Connect: their permission prompts
            // would cover the app mid-test (unit tests cover that logic).
            AppModel(mock, scope, PendingSetStore.inMemory, MemoryPrefs(), NoopNotifier, UnavailableHealth)
        } else {
            val tokens = KeystoreTokenStore(app)
            val api = LiveApi(config?.liveBaseUrl ?: BuildConfig.API_BASE_URL, tokens)
            AppModel(api, scope, PendingSetStore(File(app.filesDir, "pending-sets.json")), SharedPrefs(app), notifier, health)
        }
        // Sets saved offline go out as soon as the network is back.
        Connectivity(app).start { scope.launch { built.flushPendingSets() } }
        model = built
        return built
    }

    /** Forget the model, so the next launch builds a fresh one (UI tests). */
    fun reset() {
        model = null
        testPrefs.putBoolean(ONBOARDED, false)
    }

    private const val ONBOARDED = "hasOnboarded"
}
