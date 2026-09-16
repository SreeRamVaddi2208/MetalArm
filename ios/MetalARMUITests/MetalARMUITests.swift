//
//  MetalARMUITests.swift
//  MetalARMUITests
//
//  Created by Vaddi Sree Rama Sai Sasi Sekhar on 13/09/26.
//
//  Runs against MockAPIClient (launch argument -UITestMockAPI) unless noted.
//  The screenshots double as the App Store set when run on iPhone 17 Pro Max.
//

import XCTest

final class MetalARMUITests: XCTestCase {
    private let password = "correct-horse-1"

    override func setUpWithError() throws {
        continueAfterFailure = false
    }

    @MainActor
    private func launch(_ arguments: [String]) -> XCUIApplication {
        let app = XCUIApplication()
        app.launchArguments = ["-UITestMockAPI"] + arguments
        app.launch()
        return app
    }

    @MainActor
    private func launchSignedIn() -> XCUIApplication {
        let app = launch(["-UITestSignedIn", "-UITestSkipOnboarding"])
        XCTAssertTrue(app.staticTexts["Level 14 · Rank C"].waitForExistence(timeout: 10), "Home never loaded")
        return app
    }

    @MainActor
    private func openTab(_ app: XCUIApplication, _ name: String) {
        let tab = app.tabBars.buttons[name]
        if tab.exists {
            tab.tap()
        } else {
            app.buttons[name].firstMatch.tap()
        }
    }

    @MainActor
    private func element(_ app: XCUIApplication, _ identifier: String) -> XCUIElement {
        app.descendants(matching: .any)[identifier]
    }

    @MainActor
    private func type(_ text: String, into field: XCUIElement) {
        XCTAssertTrue(field.waitForExistence(timeout: 5), "\(field) missing")
        // A tap during a transition can land without handing over the keyboard
        // ("Neither element nor any descendant has keyboard focus"); re-tap until it has it.
        for _ in 1...3 {
            field.tap()
            if (field.value(forKey: "hasKeyboardFocus") as? Bool) == true { break }
            Thread.sleep(forTimeInterval: 0.5)
        }
        field.typeText(text)
    }

    /// The sign-up password field is a new-password field, so iOS may cover it
    /// with its own "Use Strong Password?" sheet, which would swallow the typing.
    /// The sheet can arrive late (or not at all), so verify what landed - a secure
    /// field reports one bullet per character - and retry if it swallowed the typing.
    @MainActor
    private func typeNewPassword(_ text: String, into field: XCUIElement, in app: XCUIApplication) {
        XCTAssertTrue(field.waitForExistence(timeout: 5), "\(field) missing")
        for attempt in 1...3 {
            field.tap()
            if app.staticTexts["Use Strong Password?"].waitForExistence(timeout: attempt == 1 ? 2 : 5) {
                app.buttons["Close"].firstMatch.tap()
                _ = app.staticTexts["Use Strong Password?"].waitForNonExistence(timeout: 3)
                field.tap()
            }
            let typed = (field.value as? String) ?? ""
            if !typed.isEmpty && typed != field.placeholderValue {
                field.typeText(String(repeating: XCUIKeyboardKey.delete.rawValue, count: typed.count))
            }
            field.typeText(text)
            if ((field.value as? String) ?? "").count == text.count { return }
        }
        XCTFail("Could not type the password - the AutoFill sheet kept taking the keyboard")
    }

    /// After a sign-up with a new password iOS may offer "Save Password?", which
    /// covers the app until dismissed.
    @MainActor
    private func dismissSavePasswordPrompt(_ app: XCUIApplication) {
        let notNow = app.buttons["Not Now"]
        guard notNow.waitForExistence(timeout: 5) else { return }
        // A tap while the sheet is still sliding in can be swallowed, leaving
        // it over Home - keep tapping until it has actually gone.
        for _ in 1...4 {
            if notNow.isHittable { notNow.tap() }
            if notNow.waitForNonExistence(timeout: 3) { return }
        }
        XCTFail("The Save Password sheet would not close")
    }

    @MainActor
    private func attachScreenshot(_ app: XCUIApplication, named name: String) {
        let attachment = XCTAttachment(screenshot: app.screenshot())
        attachment.name = name
        attachment.lifetime = .keepAlways
        add(attachment)
    }

    @MainActor
    private func scrollUntilHittable(_ element: XCUIElement, in app: XCUIApplication, maxSwipes: Int = 8) {
        var swipes = 0
        while !element.isHittable && swipes < maxSwipes {
            app.swipeUp()
            swipes += 1
        }
        XCTAssertTrue(element.isHittable, "\(element) never scrolled into view")
    }

    @MainActor
    private func deleteAccount(_ app: XCUIApplication, screenshot: String? = nil) {
        openTab(app, "Profile")
        let delete = app.buttons["deleteAccountButton"]
        XCTAssertTrue(delete.waitForExistence(timeout: 10), "Delete Account missing")
        // Profile grows with its cards (badges, rank trials); scroll until the
        // button is actually on screen rather than a fixed number of swipes.
        scrollUntilHittable(delete, in: app)
        delete.tap()
        type(password, into: app.secureTextFields["deletePasswordField"])
        if let screenshot { attachScreenshot(app, named: screenshot) }
        app.buttons["confirmDeleteButton"].tap()
        XCTAssertTrue(app.buttons["authSubmitButton"].waitForExistence(timeout: 10), "Deleting the account did not sign out")
    }

    @MainActor
    func testOnboardingAndSignUp() throws {
        let app = launch(["-UITestResetOnboarding"])
        XCTAssertTrue(app.staticTexts["onboardingTitle"].waitForExistence(timeout: 10), "Onboarding never appeared")
        attachScreenshot(app, named: "01 Onboarding")

        app.buttons["getStartedButton"].tap()
        type("Sree Ram", into: app.textFields["displayNameField"])
        type("sree@metalarm.dev", into: app.textFields["emailField"])
        typeNewPassword(password, into: app.secureTextFields["passwordField"], in: app)
        attachScreenshot(app, named: "02 Create account")

        app.buttons["authSubmitButton"].tap()
        XCTAssertTrue(app.staticTexts["Level 14 · Rank C"].waitForExistence(timeout: 10), "Sign-up did not reach Home")
        dismissSavePasswordPrompt(app)
        attachScreenshot(app, named: "Home after sign-up")
    }

    @MainActor
    func testWorkoutLoopFromStartToSummary() throws {
        let app = launchSignedIn()

        app.buttons["homeStartWorkoutButton"].tap()
        let addFirst = app.buttons["addFirstExerciseButton"]
        XCTAssertTrue(addFirst.waitForExistence(timeout: 5), "Workout never started")
        addFirst.tap()

        let bench = app.buttons["pickExercise-Barbell Bench Press"]
        XCTAssertTrue(bench.waitForExistence(timeout: 10), "Exercise picker did not load")
        attachScreenshot(app, named: "04 Exercise picker")
        bench.tap()

        let logSet = app.buttons["logSetButton"]
        XCTAssertTrue(logSet.waitForExistence(timeout: 5), "Exercise card missing")
        XCTAssertTrue(element(app, "ghostValues").exists, "Last session's numbers missing")
        attachScreenshot(app, named: "05 Workout")

        logSet.tap()
        XCTAssertTrue(app.staticTexts["1 set logged"].waitForExistence(timeout: 5), "Set was not logged")
        XCTAssertTrue(element(app, "prBanner").exists, "PR banner missing")
        XCTAssertTrue(element(app, "restBanner").exists, "Rest timer missing")
        attachScreenshot(app, named: "06 Set logged")

        app.buttons["finishButton"].tap()
        XCTAssertTrue(app.buttons["doneButton"].waitForExistence(timeout: 5), "Summary never appeared")
        XCTAssertTrue(app.staticTexts["New Personal Record!"].exists)
        XCTAssertTrue(element(app, "unqualifiedNote").exists, "Short workout was not explained")
        attachScreenshot(app, named: "07 Summary")

        app.buttons["doneButton"].tap()
        XCTAssertTrue(app.buttons["workoutStartButton"].waitForExistence(timeout: 5), "Summary did not close")
    }

    @MainActor
    func testProgressRanksAndProfile() throws {
        let app = launchSignedIn()
        attachScreenshot(app, named: "03 Home")

        openTab(app, "Progress")
        XCTAssertTrue(app.staticTexts["Personal records"].waitForExistence(timeout: 5), "Progress did not load")
        XCTAssertTrue(app.staticTexts["Heaviest — Barbell Bench Press"].waitForExistence(timeout: 5))
        attachScreenshot(app, named: "08 Progress")

        openTab(app, "Ranks")
        XCTAssertTrue(app.staticTexts["Meera"].waitForExistence(timeout: 5), "Party board did not load")
        XCTAssertTrue(app.staticTexts["(you)"].exists)
        XCTAssertTrue(element(app, "raidCard").exists, "Party raid missing")
        attachScreenshot(app, named: "09 Ranks")

        openTab(app, "Profile")
        XCTAssertTrue(app.staticTexts["Badges"].waitForExistence(timeout: 5), "Profile did not load")
        XCTAssertTrue(element(app, "rankTrialsCard").waitForExistence(timeout: 5), "Rank trials missing")
        XCTAssertTrue(app.buttons["importWorkoutsButton"].exists, "Import from Strong or Hevy missing")
        attachScreenshot(app, named: "10 Profile")
    }

    @MainActor
    func testDeletingTheAccountReturnsToSignIn() throws {
        let app = launchSignedIn()
        deleteAccount(app, screenshot: "11 Delete account")
    }

    /// Signs in to the mock backend with `flag`, logs one set, and finishes.
    @MainActor
    private func finishOneSetWorkout(flag: String) -> XCUIApplication {
        let app = launch(["-UITestSignedIn", "-UITestSkipOnboarding", flag])
        XCTAssertTrue(app.staticTexts["Level 14 · Rank C"].waitForExistence(timeout: 10), "Home never loaded")

        app.buttons["homeStartWorkoutButton"].tap()
        let addFirst = app.buttons["addFirstExerciseButton"]
        XCTAssertTrue(addFirst.waitForExistence(timeout: 5), "Workout never started")
        addFirst.tap()
        let bench = app.buttons["pickExercise-Barbell Bench Press"]
        XCTAssertTrue(bench.waitForExistence(timeout: 10), "Exercise picker did not load")
        bench.tap()
        let logSet = app.buttons["logSetButton"]
        XCTAssertTrue(logSet.waitForExistence(timeout: 5), "Exercise card missing")
        logSet.tap()
        app.buttons["finishButton"].tap()
        return app
    }

    @MainActor
    func testRankUpCelebration() throws {
        // The mock backend reports a new rank (level 20, C -> B) when the workout finishes.
        let app = finishOneSetWorkout(flag: "-UITestRankUp")
        let overlay = element(app, "levelUpOverlay")
        XCTAssertTrue(overlay.waitForExistence(timeout: 5), "Rank-up celebration never appeared")
        XCTAssertTrue(app.staticTexts["RANK UP"].exists)
        XCTAssertTrue(app.staticTexts["You're now rank B at level 20."].exists)
        Thread.sleep(forTimeInterval: 1.2)
        attachScreenshot(app, named: "Rank up")

        // Tapping anywhere dismisses it too.
        overlay.tap()
        XCTAssertTrue(overlay.waitForNonExistence(timeout: 3), "Celebration did not close")
        XCTAssertTrue(app.buttons["doneButton"].exists, "Summary missing behind the celebration")
    }

    @MainActor
    func testLoggingOfflineQueuesTheSet() throws {
        // The mock backend is out of reach, like a gym with no signal.
        let app = launch(["-UITestSignedIn", "-UITestSkipOnboarding", "-UITestOffline"])
        XCTAssertTrue(app.staticTexts["Level 14 · Rank C"].waitForExistence(timeout: 10), "Home never loaded")

        app.buttons["homeStartWorkoutButton"].tap()
        let addFirst = app.buttons["addFirstExerciseButton"]
        XCTAssertTrue(addFirst.waitForExistence(timeout: 5), "Workout never started")
        addFirst.tap()
        let bench = app.buttons["pickExercise-Barbell Bench Press"]
        XCTAssertTrue(bench.waitForExistence(timeout: 5), "Exercise picker did not load")
        bench.tap()
        let logSet = app.buttons["logSetButton"]
        XCTAssertTrue(logSet.waitForExistence(timeout: 5), "Exercise card missing")
        logSet.tap()

        // Kept on the phone instead of an error.
        XCTAssertTrue(element(app, "offlineBanner").waitForExistence(timeout: 5), "Offline banner missing")
        XCTAssertTrue(element(app, "queuedSet").exists, "Queued set not shown")
        attachScreenshot(app, named: "Offline set")
    }

    @MainActor
    func testLevelUpCelebration() throws {
        // The mock backend reports a level-up (14 -> 15) when the workout finishes.
        let app = finishOneSetWorkout(flag: "-UITestLevelUp")

        let overlay = element(app, "levelUpOverlay")
        XCTAssertTrue(overlay.waitForExistence(timeout: 5), "Level-up celebration never appeared")
        XCTAssertTrue(app.staticTexts["LEVEL UP"].exists)
        XCTAssertTrue(app.staticTexts["You reached level 15. Keep going."].exists)
        // Let the rings and sparks settle before the screenshot.
        Thread.sleep(forTimeInterval: 1.2)
        attachScreenshot(app, named: "12 Level up")

        // The story card is offered on the celebration and on the summary.
        XCTAssertTrue(app.buttons["levelUpShareButton"].exists, "Share missing on the celebration")
        app.buttons["levelUpContinueButton"].tap()
        XCTAssertTrue(app.buttons["shareButton"].waitForExistence(timeout: 3), "Share missing on the summary")
        XCTAssertTrue(overlay.waitForNonExistence(timeout: 3), "Celebration did not close")
        XCTAssertTrue(app.buttons["doneButton"].exists, "Summary missing behind the celebration")
    }

    // End-to-end against the real backend (the LevelForge stack on 127.0.0.1:8000):
    // signs up a fresh account, logs a workout, then deletes the account again.
    // Runs only when xcodebuild is given TEST_RUNNER_METALARM_LIVE_UI=1.
    @MainActor
    func testLiveBackendTour() throws {
        try XCTSkipUnless(ProcessInfo.processInfo.environment["METALARM_LIVE_UI"] == "1",
                          "Start the backend and set TEST_RUNNER_METALARM_LIVE_UI=1 to run")
        let app = XCUIApplication()
        app.launchArguments = ["-UITestResetOnboarding"]
        app.launchEnvironment["METALARM_BACKEND_URL"] =
            ProcessInfo.processInfo.environment["METALARM_BACKEND_URL"] ?? "http://127.0.0.1:8000"
        app.launch()

        XCTAssertTrue(app.buttons["getStartedButton"].waitForExistence(timeout: 10))
        app.buttons["getStartedButton"].tap()
        type("Live Tester", into: app.textFields["displayNameField"])
        type("live-\(UUID().uuidString.prefix(8).lowercased())@metalarm.dev", into: app.textFields["emailField"])
        typeNewPassword(password, into: app.secureTextFields["passwordField"], in: app)
        app.buttons["authSubmitButton"].tap()
        let level = app.staticTexts.matching(NSPredicate(format: "label BEGINSWITH 'Level 1 '")).firstMatch
        XCTAssertTrue(level.waitForExistence(timeout: 15), "Sign-up against the backend failed")
        dismissSavePasswordPrompt(app)
        attachScreenshot(app, named: "Live 01 Home")

        app.buttons["homeStartWorkoutButton"].tap()
        let addFirst = app.buttons["addFirstExerciseButton"]
        XCTAssertTrue(addFirst.waitForExistence(timeout: 10), "Backend workout never started")
        addFirst.tap()
        type("bench press", into: app.searchFields.firstMatch)
        let pick = app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH 'pickExercise-'")).firstMatch
        XCTAssertTrue(pick.waitForExistence(timeout: 10), "Exercise search returned nothing")
        attachScreenshot(app, named: "Live 02 Exercise search")
        pick.tap()

        type("60", into: app.textFields["weightField"])
        type("5", into: app.textFields["repsField"])
        app.buttons["keyboardDoneButton"].tap()
        app.buttons["logSetButton"].tap()
        XCTAssertTrue(app.staticTexts["1 set logged"].waitForExistence(timeout: 10), "First set was not logged")
        app.buttons["logSetButton"].tap()
        XCTAssertTrue(app.staticTexts["2 sets logged"].waitForExistence(timeout: 10), "Second set was not logged")
        attachScreenshot(app, named: "Live 03 Workout")

        app.buttons["finishButton"].tap()
        XCTAssertTrue(app.buttons["doneButton"].waitForExistence(timeout: 10), "Summary never appeared")
        attachScreenshot(app, named: "Live 04 Summary")
        app.buttons["doneButton"].tap()

        openTab(app, "Progress")
        XCTAssertTrue(app.staticTexts["Personal records"].waitForExistence(timeout: 10))
        attachScreenshot(app, named: "Live 05 Progress")

        openTab(app, "Ranks")
        XCTAssertTrue(app.buttons["createPartyButton"].waitForExistence(timeout: 10))
        attachScreenshot(app, named: "Live 06 Ranks")

        openTab(app, "Profile")
        XCTAssertTrue(app.staticTexts["Badges"].waitForExistence(timeout: 10))
        attachScreenshot(app, named: "Live 07 Profile")

        deleteAccount(app)
    }

    @MainActor
    func testLaunchPerformance() throws {
        measure(metrics: [XCTApplicationLaunchMetric()]) {
            let app = XCUIApplication()
            app.launchArguments = ["-UITestMockAPI"]
            app.launch()
        }
    }
}
