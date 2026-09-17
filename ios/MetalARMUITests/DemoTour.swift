//
//  DemoTour.swift
//  MetalARMUITests
//
//  Drives the app through every feature at a readable pace, for a screen
//  recording. NOT a test: it asserts almost nothing, it just walks the app.
//
//  Skipped unless METALARM_DEMO=1, so CI never runs it (a three-minute tour
//  has no business in a pull request check).
//
//      xcrun simctl io <udid> recordVideo --codec h264 --mask ignored out.mp4 &
//      xcodebuild test -only-testing:MetalARMUITests/DemoTour \
//        -destination "id=<udid>" METALARM_DEMO=1
//
//  Runs against MockAPIClient, so the account is populated (Level 14, Rank C,
//  records, a party, a raid boss, a league place) and the tour is repeatable.
//

import XCTest

final class DemoTour: XCTestCase {
    /// Long enough to read a screen, short enough to keep the tour moving.
    private let beat: TimeInterval = 2.2

    override func setUpWithError() throws {
        continueAfterFailure = true
        // No environment gate. Two recordings were lost to one: xcodebuild's
        // TEST_RUNNER_-prefixed variables did not reach this runner, so the
        // tour skipped in half a second and the recorder captured an idle
        // simulator - while still reporting TEST SUCCEEDED.
        //
        // This file is deliberately NOT committed, so CI never sees it. If it
        // is ever kept, keep it out of CI with an explicit
        // `-skip-testing:MetalARMUITests/DemoTour` in the workflow, which
        // cannot silently stop working.
    }

    @MainActor
    private func pause(_ multiplier: Double = 1) {
        Thread.sleep(forTimeInterval: beat * multiplier)
    }

    /// Stamps where a segment begins, in absolute time. build.py subtracts the
    /// moment recording started to get an offset into the capture, so the cuts
    /// land on the right frames instead of on guessed pacing.
    @MainActor
    private func mark(_ name: String) {
        print("DEMO_MARK \(name) \(Date().timeIntervalSince1970)")
    }

    @MainActor
    private func element(_ app: XCUIApplication, _ identifier: String) -> XCUIElement {
        app.descendants(matching: .any)[identifier]
    }

    @MainActor
    private func openTab(_ app: XCUIApplication, _ name: String) {
        let tab = app.tabBars.buttons[name]
        if tab.exists { tab.tap() } else { app.buttons[name].firstMatch.tap() }
        pause()
    }

    /// Scrolls until the element is on screen, then holds so it can be read.
    @MainActor
    private func reveal(_ element: XCUIElement, in app: XCUIApplication, maxSwipes: Int = 8) {
        var swipes = 0
        while !element.isHittable && swipes < maxSwipes {
            app.swipeUp()
            swipes += 1
            Thread.sleep(forTimeInterval: 0.4)
        }
        pause()
    }

    @MainActor
    func testDemoTour() throws {
        let app = XCUIApplication()
        // `-key value` launch arguments are UserDefaults overrides, so this
        // tells NotificationSettings the permission prompt has already been
        // shown. Without it iOS puts its own alert over the summary a few
        // seconds after the first finished workout - real behaviour, but it
        // sits on top of the screen the recording is trying to show.
        app.launchArguments = [
            "-UITestMockAPI", "-UITestSignedIn", "-UITestSkipOnboarding",
            "-notifications.asked", "YES",
        ]
        app.launch()

        // --- Home: level, rank, XP, streak, the next rank trial -----------
        XCTAssertTrue(app.staticTexts["Level 14 · Rank C"].waitForExistence(timeout: 15), "Home never loaded")
        mark("home")
        pause(2)
        app.swipeUp()
        pause()
        app.swipeDown()
        pause()

        // --- Start a workout and add an exercise --------------------------
        mark("workout")
        app.buttons["homeStartWorkoutButton"].tap()
        let addFirst = app.buttons["addFirstExerciseButton"]
        XCTAssertTrue(addFirst.waitForExistence(timeout: 10), "Workout never started")
        pause()
        addFirst.tap()

        let bench = app.buttons["pickExercise-Barbell Bench Press"]
        XCTAssertTrue(bench.waitForExistence(timeout: 10), "Picker did not load")
        pause(1.5)
        bench.tap()

        // Ghost values from last session, and what to try next.
        let logSet = app.buttons["logSetButton"]
        XCTAssertTrue(logSet.waitForExistence(timeout: 10), "Exercise card missing")
        mark("hint")
        pause(2)

        // --- Log a set: PR moment, then the level-up ----------------------
        mark("logset")
        logSet.tap()
        pause(2)
        if app.staticTexts["KEEP LIFTING"].waitForExistence(timeout: 6) {
            pause()
            app.staticTexts["KEEP LIFTING"].tap()
        } else if app.buttons["KEEP LIFTING"].exists {
            pause()
            app.buttons["KEEP LIFTING"].tap()
        }
        pause(1.5)
        // The level-up sequence, when the mock's XP crosses a level.
        mark("levelup")
        if app.staticTexts["CONTINUE"].waitForExistence(timeout: 5) {
            pause(1.5)
            app.staticTexts["CONTINUE"].tap()
        } else if app.buttons["CONTINUE"].exists {
            pause(1.5)
            app.buttons["CONTINUE"].tap()
        }
        pause()

        // --- Finish, summary, share card ----------------------------------
        mark("finish")
        if app.buttons["finishButton"].exists {
            app.buttons["finishButton"].tap()
            pause(2.5)
            let share = app.buttons["shareButton"]
            if share.waitForExistence(timeout: 8) {
                mark("share")
                share.tap()
                pause(2.5)
                // Dismiss the share sheet.
                if app.buttons["Close"].exists {
                    app.buttons["Close"].tap()
                } else {
                    app.swipeDown()
                }
                pause()
            }
            if app.buttons["doneButton"].exists {
                app.buttons["doneButton"].tap()
                pause()
            }
        }

        // --- Progress: history and records --------------------------------
        mark("progress")
        openTab(app, "Progress")
        pause(2)
        app.swipeUp()
        pause(1.5)

        // --- Ranks: this week's league, then the party raid ---------------
        mark("ranks")
        openTab(app, "Ranks")
        let league = element(app, "leagueCard")
        if league.waitForExistence(timeout: 10) { pause(2.5) }
        let raid = element(app, "raidCard")
        if raid.exists { reveal(raid, in: app) }
        pause(1.5)

        // --- Profile: character sheet, class, trials, the rest ------------
        mark("character")
        openTab(app, "Profile")
        let character = element(app, "characterCard")
        if character.waitForExistence(timeout: 10) {
            reveal(character, in: app)
            // Pick a class and let the highlight land.
            let powerlifter = app.buttons["class-powerlifter"]
            if powerlifter.isHittable {
                powerlifter.tap()
                pause(2)
            }
        }
        mark("trials")
        let trials = element(app, "rankTrialsCard")
        if trials.exists { reveal(trials, in: app) }
        pause(1.5)

        // Settings: import, reminders, Apple Health.
        mark("extras")
        let importRow = app.buttons["importWorkoutsButton"]
        if importRow.exists { reveal(importRow, in: app) }
        pause(2)
        app.swipeUp()
        pause(2)
    }
}
