// The main flows on the mock backend - ports of the iOS MetalARMUITests. The
// screenshots double as the Play Store set.

package com.sreeram.metalarm

import androidx.compose.ui.test.SemanticsNodeInteraction
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollTo
import androidx.compose.ui.test.assertIsNotEnabled
import androidx.compose.ui.test.hasText
import androidx.test.ext.junit.runners.AndroidJUnit4
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class MetalArmFlowTest : MetalArmUiTest() {
    private val password = "correct-horse-1"

    @Test fun onboardingAndSignUp() {
        launch(TestConfig(signedIn = false, skipOnboarding = false))
        waitFor("onboardingTitle")
        screenshot("01-onboarding")
        tap("getStartedButton")
        type("displayNameField", "Sree Ram")
        type("emailField", "sree@metalarm.dev")
        type("passwordField", password)
        screenshot("02-create-account")
        tap("authSubmitButton")
        waitForText("Level 14 · Intermediate")
    }

    @Test fun signInControls() {
        launch(TestConfig(signedIn = false, skipOnboarding = false))
        tap("haveAccountButton")
        waitForText("Welcome back")
        assertFalse(exists("displayNameField"))
        tap("authModeToggle")
        waitForText("Create your account")
        tap("authModeToggle")
        waitForText("Welcome back")
        tag("authSubmitButton").assertIsNotEnabled()
        type("emailField", "sree@metalarm.dev")
        type("passwordField", "wrong-password")
        tap("authSubmitButton")
        waitForText("Couldn't sign in: Incorrect email or password")
        type("passwordField", password)
        tap("authSubmitButton")
        waitForText("Level 14 · Intermediate")
    }

    @Test fun workoutLoopFromStartToSummary() {
        launchSignedIn()
        screenshot("03-home")
        tap("homeStartWorkoutButton")
        tap("addFirstExerciseButton")
        waitFor("pickExercise-Barbell Bench Press")
        screenshot("04-exercise-picker")
        tap("pickExercise-Barbell Bench Press")
        waitFor("logSetButton")
        assertTrue(exists("ghostValues"))
        assertTrue(exists("progressionHint"))
        screenshot("05-workout")

        tap("logSetButton")
        compose.waitUntil(REACTS) { exists(hasText("1 set ·", substring = true)) }
        assertTrue(exists("prBanner"))
        assertTrue(exists("restBanner"))
        screenshot("06-set-logged")

        tap("finishButton")
        waitFor("doneButton")
        assertTrue(exists(hasText("New personal record")))
        assertTrue(exists("unqualifiedNote"))
        screenshot("07-summary")
        tap("doneButton")
        waitFor("workoutStartButton")
    }

    @Test fun workoutControls() {
        launchSignedIn()
        tap("homeStartWorkoutButton")
        tap("addFirstExerciseButton")
        waitFor("pickerCancel")
        tap("pickerCancel")
        waitGone("exercisePicker")
        assertTrue(exists("addFirstExerciseButton"))

        // Search, then pick.
        tap("addFirstExerciseButton")
        type("pickerSearch", "bench")
        waitGone("pickExercise-Barbell Back Squat")
        tap("pickExercise-Barbell Bench Press")
        waitFor("logSetButton")

        // The steppers move by a plate and a rep.
        tap("weightPlus")
        compose.waitUntil(REACTS) { textOf("weightField") == "82.5" }
        tap("repsMinus")
        compose.waitUntil(REACTS) { textOf("repsField") == "7" }

        // "+ Add" opens the picker again for a second exercise.
        tap("addExerciseButton")
        tap("pickExercise-Barbell Back Squat")
        waitFor("chip-Barbell Back Squat")
        tap("chip-Barbell Bench Press")
        waitFor("ghostValues")

        tap("logSetButton")
        compose.waitUntil(REACTS) { exists(hasText("1 set ·", substring = true)) }

        // Discard, through the options menu and its confirmation.
        tap("workoutOptions")
        tap("discardWorkoutItem")
        waitForText("Discard this workout?")
        tap("confirmDiscardButton")
        waitFor("workoutStartButton")
        tap("workoutStartButton")
        waitFor("addFirstExerciseButton")
    }

    @Test fun loggingOfflineQueuesTheSet() {
        launchSignedIn(TestConfig(offline = true))
        tap("homeStartWorkoutButton")
        tap("addFirstExerciseButton")
        tap("pickExercise-Barbell Bench Press")
        tap("logSetButton")
        waitFor("offlineBanner")
        assertTrue(exists("queuedSet"))
        screenshot("offline-set")
    }

    @Test fun levelUpCelebration() {
        finishOneSetWorkout(TestConfig(levelUpOnFinish = true))
        waitFor("levelUpOverlay")
        assertTrue(exists(hasText("Level up")))
        assertTrue(exists(hasText("You reached level 15. Keep going.")))
        Thread.sleep(1_200)
        screenshot("12-level-up")
        assertTrue(exists("levelUpShareButton"))
        tap("levelUpContinueButton")
        waitGone("levelUpOverlay")
        assertTrue(exists("doneButton"))
        assertTrue(exists("shareButton"))
    }

    @Test fun rankUpCelebration() {
        finishOneSetWorkout(TestConfig(rankUpOnFinish = true))
        waitFor("levelUpOverlay")
        assertTrue(exists(hasText("Rank up")))
        assertTrue(exists(hasText("You're now Advanced at level 20.")))
        Thread.sleep(1_200)
        screenshot("rank-up")
        tag("levelUpOverlay").assertIsDisplayed()
        tap("levelUpContinueButton")
        waitGone("levelUpOverlay")
    }

    private fun finishOneSetWorkout(config: TestConfig) {
        launchSignedIn(config)
        tap("homeStartWorkoutButton")
        tap("addFirstExerciseButton")
        tap("pickExercise-Barbell Bench Press")
        tap("logSetButton")
        compose.waitUntil(REACTS) { exists(hasText("1 set ·", substring = true)) }
        tap("finishButton")
    }

    @Test fun progressLeaderboardAndProfile() {
        launchSignedIn()
        openTab("Progress")
        waitForText("Records")
        waitFor("record-Heaviest — Barbell Bench Press")
        screenshot("08-progress")
        tap("progressTab-Barbell Back Squat")
        waitFor("record-Heaviest — Barbell Back Squat")
        assertFalse(exists("record-Heaviest — Barbell Bench Press"))

        openTab("Home")
        waitFor("homeBoardRow-Meera")
        compose.onNode(hasText("See all"), useUnmergedTree = true).performScrollToAndClick()
        waitFor("partyRow-Meera")
        assertTrue(exists("leagueCard"))
        assertTrue(exists("raidCard"))
        screenshot("09-leaderboard")

        openTab("Profile")
        waitForText("Badges")
        waitFor("characterCard")
        assertTrue(exists("rankTrialsCard"))
        assertTrue(exists("importWorkoutsButton"))
        screenshot("10-profile")
    }

    @Test fun leaderboardControls() {
        launchSignedIn()
        compose.onNode(hasText("See all"), useUnmergedTree = true).performScrollToAndClick()
        waitFor("partyRow-Meera")
        tap("addPartyButton")
        waitForText("Create a party")
        text("Create a party").performScrollToAndClick()
        type("promptField", "Sweep Crew")
        tap("promptConfirm")
        waitFor("partyRow-Sree Ram")
        compose.waitUntil(REACTS) { exists(hasText("Sweep Crew")) }
        assertFalse(exists("partyRow-Arjun"))

        tap("addPartyButton")
        text("Join with a code").performScrollToAndClick()
        type("promptField", "WRONG999")
        tap("promptConfirm")
        waitForText("No party with that invite code", substring = true)

        tap("addPartyButton")
        text("Join with a code").performScrollToAndClick()
        type("promptField", "IRON2345")
        tap("promptConfirm")
        waitFor("partyRow-Arjun")
    }

    @Test fun profileSettings() {
        launchSignedIn()
        openTab("Profile")
        waitFor("characterCard")
        tap("trainingPathButton")
        tap("path-athlete")
        tap("confirmPathButton")
        waitFor("characterCard")
        waitForText("Athletic")

        // kg -> lb shows up on Progress.
        text("lb").performScrollToAndClick()
        openTab("Progress")
        compose.waitUntil(REACTS) { textOf("topSetUnit") == "lb" }
        openTab("Profile")
        text("kg").performScrollToAndClick()
        openTab("Progress")
        compose.waitUntil(REACTS) { textOf("topSetUnit") == "kg" }

        openTab("Profile")
        tap("restAlertsToggle")
        tap("streakRemindersToggle")
        screenshot("profile-settings")

        // Delete, then cancel: still signed in.
        tap("deleteAccountButton")
        waitFor("deleteAccountSheet")
        screenshot("11-delete-account")
        tap("cancelDeleteButton")
        waitGone("deleteAccountSheet")

        // Sign out of all devices, confirmed: back to sign-in.
        tap("signOutEverywhereButton")
        tap("confirmSignOutEverywhere")
        waitFor("authSubmitButton")
    }

    @Test fun deletingTheAccountReturnsToSignIn() {
        launchSignedIn()
        openTab("Profile")
        tap("deleteAccountButton")
        type("deletePasswordField", password)
        tap("confirmDeleteButton")
        waitFor("authSubmitButton")
    }

    @Test fun choosingATrainingPathDuringOnboarding() {
        launch(TestConfig(noTrainingPath = true))
        waitFor("path-athlete")
        assertTrue(exists(hasText("Pick how you train")))
        tag("confirmPathButton").assertIsNotEnabled()
        screenshot("14-training-path")
        tap("path-athlete")
        tap("confirmPathButton")
        waitForText("Level 14 · Intermediate")
        assertFalse(exists("path-athlete"))
    }

    @Test fun theTrainingPathQuestionCanBeDeclined() {
        launch(TestConfig(noTrainingPath = true))
        tap("skipPathButton")
        waitForText("Level 14 · Intermediate")
    }

    @Test fun everyTabLoads() {
        launchSignedIn()
        val checks = listOf("Train" to "workoutStartButton", "Library" to "choosePathButton", "Progress" to "topSetUnit", "Profile" to "characterCard")
        for ((tab, tag) in checks) {
            openTab(tab)
            waitFor(tag)
        }
        assertEquals(true, exists("tab-home"))
    }
}

/** Scroll a matched node into view, then tap it. */
fun SemanticsNodeInteraction.performScrollToAndClick() {
    runCatching { performScrollTo() }
    performClick()
}
