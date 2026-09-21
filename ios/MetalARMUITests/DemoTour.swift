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
//  Runs against MockAPIClient, so the account is populated (Level 14, Intermediate,
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
        // The file IS committed, so CI keeps it out with an explicit
        // `-skip-testing:MetalARMUITests/DemoTour` in .github/workflows/ios.yml,
        // which cannot silently stop working the way an env gate did.
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

    /// Types at a readable speed, and clears iOS's "Use Strong Password?"
    /// sheet, which otherwise covers the form the recording is showing.
    @MainActor
    private func type(_ text: String, into field: XCUIElement, in app: XCUIApplication) {
        field.tap()
        if app.staticTexts["Use Strong Password?"].waitForExistence(timeout: 2) {
            app.buttons["Close"].firstMatch.tap()
            _ = app.staticTexts["Use Strong Password?"].waitForNonExistence(timeout: 3)
            field.tap()
        }
        field.typeText(text)
        Thread.sleep(forTimeInterval: 0.4)
    }

    /// After signing up iOS offers to save the password, over the app.
    @MainActor
    private func dismissSavePassword(_ app: XCUIApplication) {
        let notNow = app.buttons["Not Now"]
        guard notNow.waitForExistence(timeout: 4) else { return }
        for _ in 1...3 {
            if notNow.isHittable { notNow.tap() }
            if notNow.waitForNonExistence(timeout: 2) { return }
        }
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
        // Starts where a new user does: onboarding, not mid-app. The account
        // has never been asked for a training path, so that question appears.
        app.launchArguments = [
            "-UITestMockAPI", "-UITestResetOnboarding", "-UITestNoTrainingPath",
            "-notifications.asked", "YES",
        ]
        app.launch()

        // --- Onboarding ---------------------------------------------------
        XCTAssertTrue(app.staticTexts["onboardingTitle"].waitForExistence(timeout: 15), "Onboarding never appeared")
        mark("onboarding")
        pause(2)
        app.buttons["getStartedButton"].tap()

        // --- Creating an account ------------------------------------------
        mark("signup")
        pause()
        type("Sree Ram", into: app.textFields["displayNameField"], in: app)
        type("sree@metalarm.dev", into: app.textFields["emailField"], in: app)
        type("correct-horse-1", into: app.secureTextFields["passwordField"], in: app)
        pause()
        app.buttons["authSubmitButton"].tap()
        dismissSavePassword(app)

        // --- Training path: three builds, one choice ----------------------
        let athletic = app.buttons["path-athlete"]
        XCTAssertTrue(athletic.waitForExistence(timeout: 15), "The training path question never appeared")
        mark("trainingpath")
        pause(2)
        // Turn one of the figures, so it reads as something you can rotate
        // rather than a still. It spins on its own too, but a drag shows why.
        let figure = element(app, "pathCharacter-athlete")
        if figure.exists {
            figure.coordinate(withNormalizedOffset: CGVector(dx: 0.3, dy: 0.5))
                .press(
                    forDuration: 0.1,
                    thenDragTo: figure.coordinate(withNormalizedOffset: CGVector(dx: 0.85, dy: 0.5)))
        }
        pause()
        app.swipeUp()
        pause(1.5)
        app.swipeDown()
        athletic.tap()
        pause(1.5)
        app.buttons["confirmPathButton"].tap()

        // --- Home: level, rank, XP, streak, the next rank trial -----------
        XCTAssertTrue(app.staticTexts["Level 14 · Intermediate"].waitForExistence(timeout: 15), "Home never loaded")
        mark("home")
        pause(2)
        app.swipeUp()
        pause()
        app.swipeDown()
        pause()

        // --- Ready-made workouts, and a demo of each movement -------------
        mark("presets")
        openTab(app, "Workout")
        let heavyDay = app.buttons["preset-powerlifting-heavy-day"]
        XCTAssertTrue(heavyDay.waitForExistence(timeout: 10), "The ready-made workouts never appeared")
        pause(2)
        heavyDay.tap()
        pause(2.5)

        // The demo sits beside the plan; tapping a movement moves it.
        mark("demo")
        app.buttons["presetSlot-Barbell Bench Press"].tap()
        pause(2)
        // The mock library's name for it; the live library says "Deadlift".
        app.buttons["presetSlot-Conventional Deadlift"].tap()
        pause(2)
        app.buttons["startPresetButton"].tap()
        XCTAssertTrue(app.buttons["logSetButton"].waitForExistence(timeout: 15), "The ready-made workout never started")
        pause(2.5)

        // Put it back, so the hand-built workout below starts from nothing.
        app.buttons["Workout options"].tap()
        pause(0.5)
        app.buttons["Discard Workout"].tap()
        pause(0.5)
        app.buttons["Discard Workout"].firstMatch.tap()
        _ = app.buttons["workoutStartButton"].waitForExistence(timeout: 10)
        openTab(app, "Home")

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
            // The path is changeable here, with the same cards onboarding used.
            let openPath = app.buttons["trainingPathButton"]
            if openPath.isHittable {
                openPath.tap()
                pause(2)
                let powerlifter = app.buttons["path-powerlifter"]
                if powerlifter.waitForExistence(timeout: 5) {
                    powerlifter.tap()
                    pause(1.5)
                    app.buttons["confirmPathButton"].tap()
                    pause(2)
                }
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

        // --- The rank-up: the rarest moment in the app --------------------
        // A fresh launch, because it takes a finished workout to earn one.
        app.terminate()
        app.launchArguments = [
            "-UITestMockAPI", "-UITestSignedIn", "-UITestSkipOnboarding", "-UITestRankUp",
            "-notifications.asked", "YES",
        ]
        app.launch()
        mark("rankup")
        XCTAssertTrue(app.buttons["homeStartWorkoutButton"].waitForExistence(timeout: 15), "Home never loaded")
        app.buttons["homeStartWorkoutButton"].tap()
        let addAgain = app.buttons["addFirstExerciseButton"]
        XCTAssertTrue(addAgain.waitForExistence(timeout: 10), "Workout never started")
        addAgain.tap()
        let benchAgain = app.buttons["pickExercise-Barbell Bench Press"]
        XCTAssertTrue(benchAgain.waitForExistence(timeout: 10), "Picker did not load")
        benchAgain.tap()
        XCTAssertTrue(app.buttons["logSetButton"].waitForExistence(timeout: 10), "Exercise card missing")
        app.buttons["logSetButton"].tap()
        pause()
        app.buttons["finishButton"].tap()

        // The tier lands, the ladder reads Intermediate -> Advanced, plates fly.
        let overlay = element(app, "levelUpOverlay")
        if overlay.waitForExistence(timeout: 15) {
            pause(3)
            app.buttons["levelUpContinueButton"].tap()
            pause(1.5)
        }
        mark("end")
        pause()
    }
}
