package com.sreeram.metalarm

import com.sreeram.metalarm.api.ActiveSession
import com.sreeram.metalarm.api.CharacterSheet
import com.sreeram.metalarm.api.ContractFixtures
import com.sreeram.metalarm.api.Enrollment
import com.sreeram.metalarm.api.FinishResult
import com.sreeram.metalarm.api.HistoryPoint
import com.sreeram.metalarm.api.LastPerformance
import com.sreeram.metalarm.api.League
import com.sreeram.metalarm.api.LibraryFixtures
import com.sreeram.metalarm.api.LibraryHome
import com.sreeram.metalarm.api.LibraryProgram
import com.sreeram.metalarm.api.LibraryProgramCard
import com.sreeram.metalarm.api.LibraryVocabulary
import com.sreeram.metalarm.api.LibraryWorkout
import com.sreeram.metalarm.api.LibraryWorkoutCard
import com.sreeram.metalarm.api.LiveApi
import com.sreeram.metalarm.api.Me
import com.sreeram.metalarm.api.MetalArmJson
import com.sreeram.metalarm.api.Party
import com.sreeram.metalarm.api.PartyBoard
import com.sreeram.metalarm.api.PartyRaid
import com.sreeram.metalarm.api.PointsSummary
import com.sreeram.metalarm.api.Profile
import com.sreeram.metalarm.api.RankTrial
import com.sreeram.metalarm.api.SetLogResult
import com.sreeram.metalarm.api.TokenPair
import com.sreeram.metalarm.api.TrainingPath
import com.sreeram.metalarm.api.WorkoutImportResult
import com.sreeram.metalarm.api.WorkoutPreset
import com.sreeram.metalarm.api.WorkoutRecord
import com.sreeram.metalarm.api.WorkoutSession
import com.sreeram.metalarm.api.celebrated
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/** Every payload the app reads decodes - the server's real shapes. */
class DecodingTest {
    private inline fun <reified T> decode(json: String): T = MetalArmJson.decodeFromString(json)

    @Test fun tokenPair() {
        val tokens = decode<TokenPair>(ContractFixtures.tokens)
        assertEquals("access-1", tokens.accessToken)
        assertEquals("refresh-1", tokens.refreshToken)
    }

    @Test fun meCarriesProgression() {
        val me = decode<Me>(ContractFixtures.me)
        assertEquals("Sree Ram", me.displayName)
        assertEquals(14, me.progress.currentLevel)
        assertEquals("C", me.progress.rank)
        assertEquals(2140.0 / 3000.0, me.progress.xpProgress, 1e-9)
    }

    @Test fun activeSessionIncludesGhostSets() {
        val active = decode<ActiveSession>(ContractFixtures.activeSession)
        val card = active.session!!.exercises.single()
        assertEquals(1, card.sets.size)
        assertEquals(2, card.previousSets.size)
        assertEquals(3, card.target?.targetSets)
        assertNull(decode<ActiveSession>(ContractFixtures.noActiveSession).session)
    }

    @Test fun setLogResultLeadsWithTheBonusRecord() {
        val result = decode<SetLogResult>(ContractFixtures.setLogResult)
        assertEquals(110.0, result.loggedSet.weightKg, 0.0)
        assertEquals("max_weight", result.prEvents.celebrated?.recordType)
        assertTrue(result.progression.leveledUp)
    }

    @Test fun finishResult() {
        val result = decode<FinishResult>(ContractFixtures.finishResult)
        assertTrue(result.qualified)
        assertEquals(140, result.breakdown.total)
        assertEquals(1, result.streak.sessionsToGo)
    }

    @Test fun progressPartiesPointsAndProfile() {
        assertEquals(4, decode<List<HistoryPoint>>(ContractFixtures.history).size)
        assertEquals(4, decode<List<WorkoutRecord>>(ContractFixtures.records).size)
        assertEquals(3, decode<List<TrainingPath>>(ContractFixtures.trainingPaths).size)
        assertEquals(3, decode<List<WorkoutPreset>>(ContractFixtures.presets).size)
        assertEquals("Iron Crew", decode<List<Party>>(ContractFixtures.parties).single().name)
        assertEquals(4, decode<PartyBoard>(ContractFixtures.partyBoard).entries.size)
        assertEquals("Iron Golem", decode<PartyRaid>(ContractFixtures.partyRaid).name)
        assertEquals(3120, decode<PointsSummary>(ContractFixtures.points).totalPoints)
        assertEquals(4, decode<Profile>(ContractFixtures.profile).badges.size)
        assertEquals(3, decode<List<RankTrial>>(ContractFixtures.rankTrials).size)
        assertEquals("Sree Ram", decode<League>(ContractFixtures.league).me?.displayName)
        assertEquals(3, decode<CharacterSheet>(ContractFixtures.character).stats.size)
        assertEquals(42, decode<WorkoutImportResult>(ContractFixtures.importResult).workoutsImported)
        assertEquals(2, decode<LastPerformance>(ContractFixtures.lastPerformance).sets.size)
    }

    @Test fun fastApiErrorsReadAsSentences() {
        assertEquals("Workout not found", LiveApi.detail("""{"detail": "Workout not found"}""", 404))
        assertEquals("Bad email", LiveApi.detail("""{"detail": [{"msg": "Value error, Bad email"}]}""", 422))
        assertEquals("Internal Server Error", LiveApi.detail("<html>", 500))
    }

    // The Library, from payloads captured off the backend.

    @Test fun theLibraryHomeLeadsWithYourProgram() {
        val home = decode<LibraryHome>(LibraryFixtures.libraryHome)
        assertEquals("bodybuilder", home.path)
        assertFalse(home.needsPath)
        val yours = home.yourProgram!!
        assertEquals("upper-lower-8wk", yours.program.slug)
        assertEquals("active", yours.enrollment.status)
        assertNotNull(yours.enrollment.nextWorkout)
        assertTrue(home.recommendedPrograms.all { it.category == "bodybuilder" && it.recommended })
        assertEquals(setOf("athlete", "powerlifter"), home.otherPaths.map { it.category }.toSet())
    }

    @Test fun withNoPathTheHomeAsksForOne() {
        val home = decode<LibraryHome>(LibraryFixtures.libraryHomeNoPath)
        assertTrue(home.needsPath)
        assertNull(home.yourProgram)
        assertEquals(3, home.otherPaths.size)
    }

    @Test fun listsComeInTheServersOrder() {
        val programs = decode<List<LibraryProgramCard>>(LibraryFixtures.libraryPrograms)
        val workouts = decode<List<LibraryWorkoutCard>>(LibraryFixtures.libraryWorkouts)
        assertEquals(programs.indices.toList(), programs.map { it.sort })
        assertEquals(workouts.indices.toList(), workouts.map { it.sort })
    }

    @Test fun aProgramHasAWeekByWeekSchedule() {
        val program = decode<LibraryProgram>(LibraryFixtures.libraryProgram)
        assertEquals(program.weeks, program.schedule.size)
        assertTrue(program.schedule.all { it.days.size == 7 })
        assertEquals(program.daysPerWeek, program.schedule[0].days.count { it.workoutSlug != null })
        assertEquals("active", program.enrollment?.status)
    }

    @Test fun aWorkoutListsTargetsNotWeights() {
        val workout = decode<LibraryWorkout>(LibraryFixtures.libraryWorkout)
        assertEquals(workout.exerciseCount, workout.exercises.size)
        val first = workout.exercises.first()
        assertTrue(first.target.contains(" × "))
        assertTrue(first.target.endsWith("s rest"))
        val slot = first.copy(targetSets = 4, repLow = 8, repHigh = 12, restSeconds = 90)
        assertEquals("4 × 8–12 · 90s rest", slot.target)
        assertEquals("4 × 5 · 90s rest", slot.copy(repLow = 5, repHigh = 5).target)
    }

    @Test fun aStartedWorkoutCarriesItsPlan() {
        val session = decode<WorkoutSession>(LibraryFixtures.libraryStartedSession)
        val workout = decode<LibraryWorkout>(LibraryFixtures.libraryWorkout)
        assertEquals(workout.exercises.map { it.exercise.id }, session.exercises.map { it.exercise.id })
        val target = session.exercises.first().target!!
        assertEquals(workout.exercises[0].targetSets, target.targetSets)
        assertEquals(workout.exercises[0].repLow, target.targetRepsLow)
        assertEquals(workout.exercises[0].repHigh, target.targetRepsHigh)
        decode<Enrollment>(LibraryFixtures.enrollment)
    }

    @Test fun kitReadsLikeTheWeb() {
        assertEquals("EZ bar", LibraryVocabulary.label("ez_bar"))
        assertEquals("Dumbbell", LibraryVocabulary.label("dumbbell"))
        assertEquals("Cardio machine", LibraryVocabulary.label("cardio_machine"))
    }
}
