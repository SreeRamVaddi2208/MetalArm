//
//  LibraryUITests.swift
//  MetalARMUITests
//
//  The Library tab against the mock backend: your path leads, a workout is
//  two taps from a live session, a program can be followed, the list can be
//  filtered, and an account with no path is asked for one.
//

import XCTest

final class LibraryUITests: MetalARMUITestCase {
    @MainActor
    func testAWorkoutFromTheLibraryRunsToTheSummary() throws {
        let app = launchSignedIn(["-UITestPath", "bodybuilder"])
        openTab(app, "Library")

        // The server's order: the user's path, easiest first.
        let back = app.buttons["library-workout-back-and-biceps"]
        let chest = app.buttons["library-workout-chest-and-triceps"]
        XCTAssertTrue(back.waitForExistence(timeout: reacts), "The recommended workouts never appeared")
        XCTAssertTrue(chest.exists)
        XCTAssertLessThan(back.frame.minY, chest.frame.minY, "The beginner workout should lead")
        XCTAssertFalse(app.buttons["library-workout-squat-day"].exists, "Another path's workout is recommended")
        attachScreenshot(app, named: "15 Library")

        scrollUntilHittable(chest, in: app)
        chest.tap()
        XCTAssertTrue(element(app, "library-exercise-0").waitForExistence(timeout: reacts), "The workout did not open")
        XCTAssertTrue(element(app, "library-exercise-0").label.contains("4 × 8–10 · 90s rest"))
        attachScreenshot(app, named: "16 Library workout")

        app.buttons["libraryStartButton"].tap()
        XCTAssertTrue(app.buttons["logSetButton"].waitForExistence(timeout: reacts), "Start did not land on Train")
        XCTAssertTrue(app.buttons["Barbell Bench Press"].firstMatch.exists)
        XCTAssertTrue(app.buttons["Overhead Press"].firstMatch.exists)
        // The plan fills the reps: the bottom of the range.
        XCTAssertEqual(app.textFields["repsField"].value as? String, "8")

        type("60", into: app.textFields["weightField"])
        app.buttons["keyboardDoneButton"].tap()
        app.buttons["logSetButton"].tap()
        XCTAssertTrue(setsLogged(app, 1).waitForExistence(timeout: reacts), "The set was not logged")
        app.buttons["finishButton"].tap()
        XCTAssertTrue(app.buttons["doneButton"].waitForExistence(timeout: reacts), "Summary never appeared")
    }

    @MainActor
    func testOneWorkoutAtATime() throws {
        let app = launchSignedIn(["-UITestPath", "bodybuilder"])
        app.buttons["homeStartWorkoutButton"].tap()
        XCTAssertTrue(app.buttons["addFirstExerciseButton"].waitForExistence(timeout: reacts))

        openTab(app, "Library")
        let chest = app.buttons["library-workout-chest-and-triceps"]
        XCTAssertTrue(chest.waitForExistence(timeout: reacts))
        scrollUntilHittable(chest, in: app)
        chest.tap()
        let start = app.buttons["libraryStartButton"]
        XCTAssertTrue(start.waitForExistence(timeout: reacts))
        start.tap()
        XCTAssertTrue(app.staticTexts["Finish or discard the workout you have going first."].waitForExistence(timeout: reacts),
                      "Starting over a live workout was not explained")
    }

    @MainActor
    func testFollowingAProgram() throws {
        let app = launchSignedIn(["-UITestPath", "bodybuilder"])
        openTab(app, "Library")
        let program = app.buttons["library-program-upper-lower-8wk"]
        XCTAssertTrue(program.waitForExistence(timeout: reacts), "The recommended programs never appeared")
        program.tap()

        let follow = app.buttons["followProgramButton"]
        XCTAssertTrue(follow.waitForExistence(timeout: reacts), "The program did not open")
        XCTAssertTrue(element(app, "Program schedule").exists || app.otherElements["Program schedule"].exists,
                      "The schedule is missing")
        attachScreenshot(app, named: "17 Library program")
        follow.tap()

        let startNext = app.buttons["startNextButton"]
        XCTAssertTrue(startNext.waitForExistence(timeout: reacts), "Following did not offer the next workout")
        XCTAssertTrue(startNext.label.contains("Chest and triceps"))
        XCTAssertTrue(app.buttons["pauseProgramButton"].exists)

        // Back on the Library's home, it leads.
        app.navigationBars.buttons.element(boundBy: 0).tap()
        XCTAssertTrue(element(app, "yourProgramCard").waitForExistence(timeout: reacts), "Your program is not shown")
        app.buttons["yourProgramStartButton"].tap()
        XCTAssertTrue(app.buttons["logSetButton"].waitForExistence(timeout: reacts), "Start did not land on Train")
    }

    @MainActor
    func testFilteringAPath() throws {
        let app = launchSignedIn(["-UITestPath", "athlete"])
        openTab(app, "Library")
        let search = app.buttons["librarySearchButton"]
        XCTAssertTrue(search.waitForExistence(timeout: reacts))
        search.tap()

        let press = app.buttons["library-workout-athletic-press"]
        XCTAssertTrue(press.waitForExistence(timeout: reacts), "The path did not list its workouts")
        app.buttons["libraryFilterButton"].tap()
        let thirty = app.buttons["Up to 30 min"]
        XCTAssertTrue(thirty.waitForExistence(timeout: reacts), "The filter sheet did not open")
        thirty.tap()
        app.buttons["showResultsButton"].tap()
        XCTAssertTrue(press.waitForNonExistence(timeout: reacts), "A 35-minute workout survived a 30-minute filter")
        XCTAssertTrue(app.buttons["library-workout-athletic-circuit"].exists)
        XCTAssertTrue(app.staticTexts["1 filter on"].exists)

        // Another path, same filters.
        app.buttons["path-chip-powerlifter"].tap()
        XCTAssertTrue(app.staticTexts["No workouts match these filters."].waitForExistence(timeout: reacts))
        app.buttons["Clear"].tap()
        XCTAssertTrue(app.buttons["library-workout-squat-day"].waitForExistence(timeout: reacts), "Clear did not clear")
    }

    @MainActor
    func testWithNoPathTheLibraryAsksForOne() throws {
        let app = launchSignedIn()
        openTab(app, "Library")
        let choose = app.buttons["choosePathButton"]
        XCTAssertTrue(choose.waitForExistence(timeout: reacts), "No prompt to choose a path")
        XCTAssertTrue(app.buttons["library-path-athlete"].exists, "Every path should be listed")
        choose.tap()

        let athlete = app.buttons["path-athlete"]
        XCTAssertTrue(athlete.waitForExistence(timeout: reacts), "The path cards did not open")
        let confirm = app.buttons["confirmPathButton"]
        scrollUntilHittable(athlete, in: app, clearOf: confirm)
        athlete.tap()
        XCTAssertTrue(waitUntilEnabled(confirm))
        confirm.tap()
        XCTAssertTrue(app.buttons["library-workout-athletic-circuit"].waitForExistence(timeout: reacts),
                      "Choosing a path did not bring its recommendations")
        XCTAssertFalse(choose.exists)
    }
}
