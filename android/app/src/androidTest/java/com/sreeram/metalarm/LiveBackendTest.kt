// End to end against the real backend (the LevelForge stack, reached from the
// emulator at 10.0.2.2:8000): signs up a fresh account, picks a path, logs and
// finishes a workout, starts a Library workout, then deletes the account.
// Runs only when asked: -Pandroid.testInstrumentationRunnerArguments.live=1

package com.sreeram.metalarm

import androidx.compose.ui.test.hasContentDescription
import androidx.compose.ui.test.hasTestTagPrefix
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.hasText
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollTo
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import org.junit.Test
import org.junit.runner.RunWith
import java.util.UUID

@RunWith(AndroidJUnit4::class)
class LiveBackendTest : MetalArmUiTest() {
    /** Bookmarks, figures and saved routines against the real backend. */
    @Test fun liveBookmarksAndSavedRoutine() {
        val arguments = InstrumentationRegistry.getArguments()
        if (arguments.getString("live") != "1") return
        val password = "correct-horse-1"
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        instrumentation.uiAutomation.grantRuntimePermission(instrumentation.targetContext.packageName, android.Manifest.permission.POST_NOTIFICATIONS)
        launch(TestConfig(signedIn = false, skipOnboarding = true, liveBaseUrl = arguments.getString("backend") ?: "http://10.0.2.2:8000"))
        waitFor("authSubmitButton")
        if (!exists("displayNameField")) tap("authModeToggle")
        type("displayNameField", "Live Tester")
        type("emailField", "live-${UUID.randomUUID().toString().take(8)}@metalarm.dev")
        type("passwordField", password)
        tap("authSubmitButton")
        waitFor("path-bodybuilder", 30_000)
        tap("path-bodybuilder")
        tap("confirmPathButton")
        waitFor("tab-explore", 30_000)
        waitForText("Level 1 ·", substring = true, timeout = 30_000)

        fun firstWith(prefix: String) =
            compose.onAllNodes(hasTestTagPrefix(prefix), useUnmergedTree = true)
        fun waitForAny(prefix: String) = compose.waitUntil(30_000) { firstWith(prefix).fetchSemanticsNodes().isNotEmpty() }

        openTab("Explore")
        tap("explore-exercises")
        tap("muscle-chest")
        waitForAny("bookmark-")
        Thread.sleep(2000)
        screenshot("live-11-cards")
        firstWith("bookmark-")[0].performClick()
        compose.waitUntil(30_000) { compose.onAllNodes(hasContentDescription("Remove bookmark"), useUnmergedTree = true).fetchSemanticsNodes().isNotEmpty() }
        openTab("Library")
        compose.onNode(hasText("Saved")).performClick()
        waitForAny("saved-item-")
        firstWith("saved-item-")[0].performClick()
        waitFor("exerciseSheetFigure", 30_000)
        Thread.sleep(2000)
        screenshot("live-12-figure")
        instrumentation.sendKeyDownUpSync(android.view.KeyEvent.KEYCODE_BACK)
        waitGone("exerciseSheetFigure")

        openTab("Explore")
        tap("explore-programs")
        waitForAny("library-workout-")
        firstWith("library-workout-")[0].performScrollTo().performClick()
        tap("saveRoutineButton")
        openTab("Library")
        compose.onNode(hasText("Routines")).performClick()
        waitForAny("saved-item-")
        firstWith("saved-item-")[0].performClick()
        tap("planStartButton")
        waitFor("logSetButton", 30_000)
        screenshot("live-13-routine-session")
        val logSet = compose.onNodeWithTag("logSetButton").assertIsDisplayed().fetchSemanticsNode().boundsInRoot
        val bar = compose.onNodeWithTag("tab-home").fetchSemanticsNode().boundsInRoot
        check(logSet.bottom <= bar.top) { "Log set $logSet is behind the tab bar $bar" }

        openTab("Profile")
        tap("deleteAccountButton")
        type("deletePasswordField", password)
        tap("confirmDeleteButton")
        waitFor("authSubmitButton", 30_000)
    }

    @Test fun liveBackendTour() {
        val arguments = InstrumentationRegistry.getArguments()
        // Not an assumption: this runner reports a violated one as a failure.
        if (arguments.getString("live") != "1") return
        val base = arguments.getString("backend") ?: "http://10.0.2.2:8000"
        val password = "correct-horse-1"
        // Finishing the first workout asks for notifications; answer it up front
        // so the system dialog doesn't cover the app mid-test.
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        instrumentation.uiAutomation.grantRuntimePermission(instrumentation.targetContext.packageName, android.Manifest.permission.POST_NOTIFICATIONS)

        launch(TestConfig(signedIn = false, skipOnboarding = true, liveBaseUrl = base))
        waitFor("authSubmitButton")
        if (!exists("displayNameField")) tap("authModeToggle")
        type("displayNameField", "Live Tester")
        type("emailField", "live-${UUID.randomUUID().toString().take(8)}@metalarm.dev")
        type("passwordField", password)
        tap("authSubmitButton")

        // A new account is asked how it trains; the Library leads with that path.
        waitFor("path-bodybuilder", 30_000)
        tap("path-bodybuilder")
        tap("confirmPathButton")
        waitForText("Level 1 ·", substring = true, timeout = 30_000)
        screenshot("live-01-home")

        tap("homeStartWorkoutButton")
        tap("addFirstExerciseButton")
        type("pickerSearch", "bench press")
        compose.waitUntil(30_000) {
            compose.onAllNodes(androidx.compose.ui.test.hasTestTagPrefix("pickExercise-"), useUnmergedTree = true)
                .fetchSemanticsNodes().isNotEmpty()
        }
        compose.onAllNodes(androidx.compose.ui.test.hasTestTagPrefix("pickExercise-"), useUnmergedTree = true)[0].performScrollToAndClick()
        type("weightField", "60")
        type("repsField", "5")
        tap("logSetButton")
        compose.waitUntil(30_000) { exists(hasText("1 set ·", substring = true)) }
        tap("logSetButton")
        compose.waitUntil(30_000) { exists(hasText("2 sets ·", substring = true)) }
        screenshot("live-02-workout")
        tap("finishButton")
        waitFor("doneButton", 30_000)
        screenshot("live-03-summary")
        tap("doneButton")

        openTab("Explore")
        compose.waitUntil(30_000) {
            compose.onAllNodes(androidx.compose.ui.test.hasTestTagPrefix("library-workout-"), useUnmergedTree = true)
                .fetchSemanticsNodes().isNotEmpty()
        }
        screenshot("live-04-library")
        compose.onAllNodes(androidx.compose.ui.test.hasTestTagPrefix("library-workout-"), useUnmergedTree = true)[0].performScrollToAndClick()
        tap("libraryStartButton")
        waitFor("logSetButton", 30_000)
        screenshot("live-05-library-session")

        openTab("Profile")
        tap("deleteAccountButton")
        type("deletePasswordField", password)
        tap("confirmDeleteButton")
        waitFor("authSubmitButton", 30_000)
    }
}
