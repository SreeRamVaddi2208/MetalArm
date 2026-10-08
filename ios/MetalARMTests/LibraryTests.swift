//
//  LibraryTests.swift
//  MetalARMTests
//
//  The Library tab: the server's payloads decode, starting a workout makes it
//  the live session, a program can be followed and paused, and focus moves
//  through a planned workout the way it does on the web.
//

import Foundation
import SwiftUI
import Testing
@testable import MetalARM

/// Logs a set at whatever the inputs hold, filling a weight when the plan
/// left it blank (a Library workout never prescribes one).
@MainActor
private func logOne(_ model: AppModel) async {
    if model.weightInput.isEmpty { model.weightInput = "60" }
    if model.repsInput.isEmpty { model.repsInput = "8" }
    await model.logSet()
}

@MainActor
struct LibraryDecodingTests {
    private let decoder = LiveAPIClient.makeDecoder()

    private func decode<T: Decodable>(_ type: T.Type, _ json: String) throws -> T {
        try decoder.decode(type, from: Data(json.utf8))
    }

    @Test func theHomeLeadsWithYourProgram() throws {
        let home = try decode(LibraryHome.self, ContractFixtures.libraryHome)
        #expect(home.path == "bodybuilder")
        #expect(!home.needsPath)
        let yours = try #require(home.yourProgram)
        #expect(yours.program.slug == "upper-lower-8wk")
        #expect(yours.enrollment.status == "active")
        #expect(yours.enrollment.nextWorkout != nil)
        #expect(!home.recommendedPrograms.isEmpty)
        #expect(home.recommendedPrograms.allSatisfy { $0.category == "bodybuilder" && $0.recommended })
        #expect(Set(home.otherPaths.map(\.category)) == ["athlete", "powerlifter"])
    }

    @Test func withNoPathTheHomeAsksForOne() throws {
        let home = try decode(LibraryHome.self, ContractFixtures.libraryHomeNoPath)
        #expect(home.needsPath)
        #expect(home.yourProgram == nil)
        #expect(home.recommendedPrograms.isEmpty)
        #expect(home.otherPaths.count == 3)
    }

    @Test func listsComeInTheServersOrder() throws {
        let programs = try decode([LibraryProgramCard].self, ContractFixtures.libraryPrograms)
        let workouts = try decode([LibraryWorkoutCard].self, ContractFixtures.libraryWorkouts)
        #expect(programs.map(\.sort) == Array(0..<programs.count))
        #expect(workouts.map(\.sort) == Array(0..<workouts.count))
    }

    @Test func aProgramHasAWeekByWeekSchedule() throws {
        let program = try decode(LibraryProgram.self, ContractFixtures.libraryProgram)
        #expect(program.schedule.count == program.weeks)
        #expect(program.schedule.allSatisfy { $0.days.count == 7 })
        let trainingDays = program.schedule[0].days.filter { $0.workoutSlug != nil }
        #expect(trainingDays.count == program.daysPerWeek)
        #expect(program.enrollment?.status == "active")
        #expect(program.meta.hasPrefix("\(program.weeks) weeks · \(program.daysPerWeek) days a week"))
    }

    @Test func aWorkoutListsTargetsNotWeights() throws {
        let workout = try decode(LibraryWorkout.self, ContractFixtures.libraryWorkout)
        #expect(workout.exercises.count == workout.exerciseCount)
        let first = try #require(workout.exercises.first)
        #expect(first.target.contains(" × "))
        #expect(first.target.hasSuffix("s rest"))
    }

    @Test func aStartedWorkoutCarriesItsPlan() throws {
        let session = try decode(WorkoutSession.self, ContractFixtures.libraryStartedSession)
        let workout = try decode(LibraryWorkout.self, ContractFixtures.libraryWorkout)
        #expect(session.exercises.map(\.exercise.id) == workout.exercises.map(\.exercise.id))
        let target = try #require(session.exercises.first?.target)
        #expect(target.targetSets == workout.exercises[0].targetSets)
        #expect(target.targetRepsLow == workout.exercises[0].repLow)
        #expect(target.targetRepsHigh == workout.exercises[0].repHigh)
        _ = try decode(Enrollment.self, ContractFixtures.enrollment)
    }

    @Test func aTargetReadsAsAPlan() throws {
        var slot = try decode(LibraryWorkout.self, ContractFixtures.libraryWorkout).exercises[0]
        (slot.targetSets, slot.repLow, slot.repHigh, slot.restSeconds) = (4, 8, 12, 90)
        #expect(slot.target == "4 × 8–12 · 90s rest")
        (slot.repLow, slot.repHigh) = (5, 5)
        #expect(slot.target == "4 × 5 · 90s rest")
    }

    @Test func kitReadsLikeTheWeb() {
        #expect(LibraryVocabulary.label("ez_bar") == "EZ bar")
        #expect(LibraryVocabulary.label("dumbbell") == "Dumbbell")
        #expect(LibraryVocabulary.label("cardio_machine") == "Cardio machine")
    }
}

@MainActor
struct LibraryFlowTests {
    private func bodybuilder() -> (AppModel, MockAPIClient) {
        let api = MockAPIClient()
        api.characterClass = "bodybuilder"
        return (AppModel.forTesting(api: api), api)
    }

    @Test func yourPathIsRecommendedFirst() async {
        let (model, _) = bodybuilder()
        await model.loadLibraryHome()
        let home = try! #require(model.libraryHome)
        #expect(home.recommendedWorkouts.first?.category == "bodybuilder")
        #expect(home.recommendedWorkouts.map(\.sort) == Array(0..<home.recommendedWorkouts.count))
        #expect(home.recommendedPrograms.map(\.slug) == ["upper-lower-8wk"])

        await model.loadLibraryPath("powerlifter")
        #expect(model.libraryWorkouts.allSatisfy { $0.category == "powerlifter" && !$0.recommended })
    }

    @Test func withNoPathEverythingIsListed() async {
        let model = AppModel.forTesting()
        await model.loadLibraryHome()
        #expect(model.libraryHome?.needsPath == true)
        #expect(model.libraryHome?.otherPaths.count == 3)
    }

    @Test func startingAWorkoutMakesItTheLiveSession() async {
        let (model, _) = bodybuilder()
        let started = await model.startLibraryWorkout("chest-and-triceps")
        #expect(started)
        #expect(model.session?.name == "Chest and triceps")
        #expect(model.workoutExercises.map(\.name) == ["Barbell Bench Press", "Overhead Press"])
        #expect(model.selectedExercise?.name == "Barbell Bench Press")
        #expect(model.session?.exercises.first?.target?.targetRepsLow == 8)
        // The inputs start from the plan: the bottom of the rep range.
        #expect(model.repsInput == "8")
    }

    @Test func oneWorkoutAtATime() async {
        let (model, _) = bodybuilder()
        await model.startWorkout()
        let started = await model.startLibraryWorkout("chest-and-triceps")
        #expect(!started)
        #expect(model.errorMessage == "Finish or discard the workout you have going first.")
        #expect(model.session?.name == nil)
    }

    @Test func followingAProgramPutsItFirst() async {
        let (model, _) = bodybuilder()
        await model.loadLibraryProgram("upper-lower-8wk")
        #expect(model.libraryProgram?.enrollment == nil)

        await model.followProgram("upper-lower-8wk")
        #expect(model.libraryProgram?.enrollment?.status == "active")
        #expect(model.libraryHome?.yourProgram?.program.slug == "upper-lower-8wk")
        #expect(model.libraryHome?.yourProgram?.enrollment.nextWorkout?.slug == "chest-and-triceps")

        await model.unfollowProgram("upper-lower-8wk")
        #expect(model.libraryProgram?.enrollment?.status == "paused")
        #expect(model.libraryHome?.yourProgram == nil)
    }

    @Test func finishingTheNextWorkoutMovesTheProgramOn() async {
        let (model, _) = bodybuilder()
        await model.followProgram("upper-lower-8wk")
        _ = await model.startLibraryWorkout("chest-and-triceps")
        await logOne(model)
        await model.finishWorkout()
        await model.loadLibraryHome()
        let enrollment = try! #require(model.libraryHome?.yourProgram?.enrollment)
        #expect((enrollment.currentWeek, enrollment.currentDay) == (1, 2))
        #expect(enrollment.nextWorkout?.slug == "back-and-biceps")
    }

    @Test func savingSaysWhereItWent() async {
        let (model, _) = bodybuilder()
        await model.saveLibraryWorkout("squat-day")
        #expect(model.libraryNotice == "Saved \"Squat day\" to your routines.")
    }

    @Test func signingOutForgetsTheLibrary() async {
        let (model, _) = bodybuilder()
        await model.loadLibraryHome()
        await model.signOut()
        #expect(model.libraryHome == nil)
    }
}

@MainActor
struct FocusTests {
    @Test func focusMovesOnOnceThePlanIsDone() async {
        let api = MockAPIClient()
        let model = AppModel.forTesting(api: api)
        _ = await model.startLibraryWorkout("bench-day")   // Bench 5 sets, then Row
        for _ in 0..<4 { await logOne(model) }
        #expect(model.selectedExercise?.name == "Barbell Bench Press")
        await logOne(model)
        #expect(model.selectedExercise?.name == "Barbell Row")
    }

    @Test func aSupersetAlternates() async {
        let model = AppModel.forTesting()
        _ = await model.startLibraryWorkout("athletic-circuit")   // Squat + Pull-Up, superset 1
        #expect(model.selectedExercise?.name == "Barbell Back Squat")
        await logOne(model)
        #expect(model.selectedExercise?.name == "Pull-Up")
        await logOne(model)
        #expect(model.selectedExercise?.name == "Barbell Back Squat")
    }
}

@MainActor
struct TokenTests {
    private func hex(_ color: Color) -> String {
        let resolved = color.resolve(in: EnvironmentValues())
        let channels = [resolved.red, resolved.green, resolved.blue].map { Int(($0 * 255).rounded()) }
        return channels.map { String(format: "%02X", $0) }.joined()
    }

    // The same values as frontend/metalarm/theme.py.
    @Test func coloursMatchTheWeb() {
        #expect(hex(Theme.bg) == "0E0E10")
        #expect(hex(Theme.surface) == "17171A")
        #expect(hex(Theme.surface2) == "202024")
        #expect(hex(Theme.border) == "2A2A2F")
        #expect(hex(Theme.text) == "F4F4F2")
        #expect(hex(Theme.text2) == "A1A1A8")
        #expect(hex(Theme.text3) == "6E6E76")
        #expect(hex(Theme.accent) == "FF6B2C")
        #expect(hex(Theme.danger) == "E5484D")
    }

    @Test func tapTargetsAreBigEnough() {
        #expect(Theme.touch >= 48)
        #expect(Theme.iconHit >= 44)
        #expect(Theme.buttonHeight >= Theme.touch)
    }
}
