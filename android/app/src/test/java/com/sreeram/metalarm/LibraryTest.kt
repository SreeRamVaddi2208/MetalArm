package com.sreeram.metalarm

import com.sreeram.metalarm.api.MockApi
import com.sreeram.metalarm.state.AppModel
import kotlinx.coroutines.test.TestScope
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/** The Library against the mock, and focus moving through a planned workout -
 *  the same rules as the web and the iOS app. */
class LibraryTest {
    private fun TestScope.bodybuilder(): AppModel = testModel(MockApi().apply { characterClass = "bodybuilder" })

    /** Logs a set at whatever the inputs hold, filling a weight when the plan
     *  left it blank (a Library workout never prescribes one). */
    private suspend fun logOne(model: AppModel) {
        if (model.weightInput.isEmpty()) model.weightInput = "60"
        if (model.repsInput.isEmpty()) model.repsInput = "8"
        model.logSet()
    }

    @Test fun yourPathIsRecommendedFirst() = runTest {
        val model = bodybuilder()
        model.loadLibraryHome()
        val home = model.libraryHome!!
        assertEquals("bodybuilder", home.recommendedWorkouts.first().category)
        assertEquals(home.recommendedWorkouts.indices.toList(), home.recommendedWorkouts.map { it.sort })
        assertEquals(listOf("upper-lower-8wk"), home.recommendedPrograms.map { it.slug })

        model.loadLibraryPath("powerlifter")
        assertTrue(model.libraryWorkouts.all { it.category == "powerlifter" && !it.recommended })
    }

    @Test fun withNoPathEverythingIsListed() = runTest {
        val model = testModel()
        model.loadLibraryHome()
        assertEquals(true, model.libraryHome?.needsPath)
        assertEquals(3, model.libraryHome?.otherPaths?.size)
    }

    @Test fun startingAWorkoutMakesItTheLiveSession() = runTest {
        val model = bodybuilder()
        assertTrue(model.startLibraryWorkout("chest-and-triceps"))
        assertEquals("Chest and triceps", model.session?.name)
        assertEquals(listOf("Barbell Bench Press", "Overhead Press"), model.workoutExercises.map { it.name })
        assertEquals("Barbell Bench Press", model.selectedExercise?.name)
        assertEquals(8, model.session?.exercises?.first()?.target?.targetRepsLow)
        // The inputs start from the plan: the bottom of the rep range.
        assertEquals("8", model.repsInput)
    }

    @Test fun oneWorkoutAtATime() = runTest {
        val model = bodybuilder()
        model.startWorkout()
        assertFalse(model.startLibraryWorkout("chest-and-triceps"))
        assertEquals("Finish or discard the workout you have going first.", model.errorMessage)
        assertNull(model.session?.name)
    }

    @Test fun followingAProgramPutsItFirst() = runTest {
        val model = bodybuilder()
        model.loadLibraryProgram("upper-lower-8wk")
        assertNull(model.libraryProgram?.enrollment)

        model.followProgram("upper-lower-8wk")
        assertEquals("active", model.libraryProgram?.enrollment?.status)
        assertEquals("upper-lower-8wk", model.libraryHome?.yourProgram?.program?.slug)
        assertEquals("chest-and-triceps", model.libraryHome?.yourProgram?.enrollment?.nextWorkout?.slug)

        model.unfollowProgram("upper-lower-8wk")
        assertEquals("paused", model.libraryProgram?.enrollment?.status)
        assertNull(model.libraryHome?.yourProgram)
    }

    @Test fun finishingTheNextWorkoutMovesTheProgramOn() = runTest {
        val model = bodybuilder()
        model.followProgram("upper-lower-8wk")
        model.startLibraryWorkout("chest-and-triceps")
        logOne(model)
        model.finishWorkout()
        model.loadLibraryHome()
        val enrollment = model.libraryHome!!.yourProgram!!.enrollment
        assertEquals(1 to 2, enrollment.currentWeek to enrollment.currentDay)
        assertEquals("back-and-biceps", enrollment.nextWorkout?.slug)
    }

    @Test fun savingSaysWhereItWent() = runTest {
        val model = bodybuilder()
        model.saveLibraryWorkout("squat-day")
        assertEquals("Saved \"Squat day\" to your routines.", model.libraryNotice)
    }

    @Test fun signingOutForgetsTheLibrary() = runTest {
        val model = bodybuilder()
        model.loadLibraryHome()
        model.signOut()
        assertNull(model.libraryHome)
    }

    @Test fun focusMovesOnOnceThePlanIsDone() = runTest {
        val model = testModel()
        model.startLibraryWorkout("bench-day") // Bench 5 sets, then Row
        repeat(4) { logOne(model) }
        assertEquals("Barbell Bench Press", model.selectedExercise?.name)
        logOne(model)
        assertEquals("Barbell Row", model.selectedExercise?.name)
    }

    @Test fun aSupersetAlternates() = runTest {
        val model = testModel()
        model.startLibraryWorkout("athletic-circuit") // Squat + Pull-Up, superset 1
        assertEquals("Barbell Back Squat", model.selectedExercise?.name)
        logOne(model)
        assertEquals("Pull-Up", model.selectedExercise?.name)
        logOne(model)
        assertEquals("Barbell Back Squat", model.selectedExercise?.name)
    }

    @Test fun theSteppersMoveByAPlateAndARep() = runTest {
        val model = testModel()
        model.weightInput = "80"
        model.bumpWeight(1)
        assertEquals("82.5", model.weightInput)
        model.repsInput = "1"
        model.bumpReps(-1)
        assertEquals("1", model.repsInput)
    }
}
