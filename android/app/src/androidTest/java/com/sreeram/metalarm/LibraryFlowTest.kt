// The Library on the mock backend - a port of the iOS LibraryUITests: your
// path leads, a workout is two taps from a live session, a program can be
// followed, the list can be filtered, and an account with no path is asked.

package com.sreeram.metalarm

import androidx.compose.ui.test.hasText
import androidx.test.ext.junit.runners.AndroidJUnit4
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class LibraryFlowTest : MetalArmUiTest() {
    @Test fun aWorkoutFromTheLibraryRunsToTheSummary() {
        launchSignedIn(TestConfig(path = "bodybuilder"))
        openTab("Library")
        waitFor("library-workout-back-and-biceps")
        assertTrue(exists("library-workout-chest-and-triceps"))
        // The server's order: the beginner workout leads.
        val back = tag("library-workout-back-and-biceps").fetchSemanticsNode().positionInRoot.y
        val chest = tag("library-workout-chest-and-triceps").fetchSemanticsNode().positionInRoot.y
        assertTrue("The beginner workout should lead", back < chest)
        assertFalse(exists("library-workout-squat-day"))
        screenshot("15-library")

        tap("library-workout-chest-and-triceps")
        waitFor("library-exercise-0")
        assertTrue(exists(hasText("4 × 8–10 · 90s rest", substring = true)))
        screenshot("16-library-workout")

        tap("libraryStartButton")
        waitFor("logSetButton")
        assertTrue(exists("chip-Barbell Bench Press"))
        assertTrue(exists("chip-Overhead Press"))
        // The plan fills the reps: the bottom of the range.
        assertEquals("8", textOf("repsField"))
        type("weightField", "60")
        tap("logSetButton")
        compose.waitUntil(REACTS) { exists(hasText("1 set ·", substring = true)) }
        tap("finishButton")
        waitFor("doneButton")
    }

    @Test fun oneWorkoutAtATime() {
        launchSignedIn(TestConfig(path = "bodybuilder"))
        tap("homeStartWorkoutButton")
        waitFor("addFirstExerciseButton")
        openTab("Library")
        tap("library-workout-chest-and-triceps")
        tap("libraryStartButton")
        waitForText("Finish or discard the workout you have going first.")
    }

    @Test fun followingAProgram() {
        launchSignedIn(TestConfig(path = "bodybuilder"))
        openTab("Library")
        tap("library-program-upper-lower-8wk")
        waitFor("followProgramButton")
        assertTrue(exists("programSchedule"))
        screenshot("17-library-program")
        tap("followProgramButton")
        waitFor("startNextButton")
        assertTrue(exists(hasText("Start next: Chest and triceps")))
        assertTrue(exists("pauseProgramButton"))

        tap("backButton")
        waitFor("yourProgramCard")
        tap("yourProgramStartButton")
        waitFor("logSetButton")
    }

    @Test fun filteringAPath() {
        launchSignedIn(TestConfig(path = "athlete"))
        openTab("Library")
        tap("librarySearchButton")
        waitFor("library-workout-athletic-press")
        tap("libraryFilterButton")
        tap("duration-30")
        tap("showResultsButton")
        waitGone("library-workout-athletic-press")
        assertTrue(exists("library-workout-athletic-circuit"))
        waitForText("1 filter on")

        // Another path, same filters.
        tap("path-chip-powerlifter")
        waitForText("No workouts match these filters.")
        tap("clearFiltersButton")
        waitFor("library-workout-squat-day")
    }

    @Test fun withNoPathTheLibraryAsksForOne() {
        launchSignedIn()
        openTab("Library")
        waitFor("choosePathButton")
        assertTrue(exists("library-path-athlete"))
        tap("choosePathButton")
        tap("path-athlete")
        tap("confirmPathButton")
        waitFor("library-workout-athletic-circuit")
        assertFalse(exists("choosePathButton"))
    }

    @Test fun trainLeadsToTheLibrary() {
        launchSignedIn(TestConfig(path = "powerlifter"))
        openTab("Train")
        tap("trainToLibrary")
        tap("library-workout-squat-day")
        waitFor("library-exercise-0")
        assertTrue(exists(hasText("5 × 3–5 · 240s rest", substring = true)))
        screenshot("13-library-workout")
        tap("libraryStartButton")
        waitFor("logSetButton")
        assertTrue(exists("chip-Barbell Back Squat"))
        assertTrue(exists("chip-Conventional Deadlift"))
        assertFalse(exists("addFirstExerciseButton"))
    }
}
