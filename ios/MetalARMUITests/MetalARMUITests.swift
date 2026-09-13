//
//  MetalARMUITests.swift
//  MetalARMUITests
//
//  Created by Vaddi Sree Rama Sai Sasi Sekhar on 13/09/26.
//

import XCTest

final class MetalARMUITests: XCTestCase {

    override func setUpWithError() throws {
        continueAfterFailure = false
    }

    // Runs against the API_CONTRACT.md examples (MockAPIClient), starting from onboarding.
    @MainActor
    private func launchApp() -> XCUIApplication {
        let app = XCUIApplication()
        app.launchArguments += ["-UITestMockAPI", "-UITestResetOnboarding"]
        app.launch()
        return app
    }

    @MainActor
    private func launchPastOnboarding() -> XCUIApplication {
        let app = launchApp()
        let getStarted = app.buttons["getStartedButton"]
        XCTAssertTrue(getStarted.waitForExistence(timeout: 10), "Onboarding never appeared")
        getStarted.tap()
        XCTAssertTrue(app.staticTexts["Level 14 — Forged"].waitForExistence(timeout: 5), "Home never showed the level card")
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
    private func attachScreenshot(_ app: XCUIApplication, named name: String) {
        let attachment = XCTAttachment(screenshot: app.screenshot())
        attachment.name = name
        attachment.lifetime = .keepAlways
        add(attachment)
    }

    @MainActor
    func testOnboardingLeadsToHome() throws {
        let app = launchApp()
        XCTAssertTrue(app.staticTexts["onboardingTitle"].waitForExistence(timeout: 10), "Onboarding never appeared")
        attachScreenshot(app, named: "01 Onboarding")

        app.buttons["getStartedButton"].tap()
        XCTAssertTrue(app.staticTexts["Level 14 — Forged"].waitForExistence(timeout: 5), "Home never showed the level card")
        XCTAssertTrue(app.staticTexts["Sree Ram"].exists)
        attachScreenshot(app, named: "02 Home")
    }

    @MainActor
    func testWorkoutLoopFromStartToSummary() throws {
        let app = launchPastOnboarding()

        app.buttons["homeStartWorkoutButton"].tap()
        let logSet = app.buttons["logSetButton"]
        XCTAssertTrue(logSet.waitForExistence(timeout: 5), "Workout screen never opened")
        XCTAssertTrue(app.staticTexts["Barbell Bench Press"].exists)
        attachScreenshot(app, named: "03 Workout")

        logSet.tap()
        XCTAssertTrue(app.staticTexts["1 sets logged"].waitForExistence(timeout: 5), "Logged set did not appear")
        XCTAssertTrue(app.descendants(matching: .any)["restBanner"].exists, "Rest timer banner missing")
        XCTAssertTrue(app.descendants(matching: .any)["prBanner"].exists, "PR banner missing")
        attachScreenshot(app, named: "04 Set logged")

        app.buttons["finishButton"].tap()
        XCTAssertTrue(app.staticTexts["+185"].waitForExistence(timeout: 5), "Summary never showed the points")
        XCTAssertTrue(app.staticTexts["New Personal Record!"].exists)
        attachScreenshot(app, named: "05 Summary")

        app.buttons["doneButton"].tap()
        XCTAssertTrue(app.buttons["workoutStartButton"].waitForExistence(timeout: 5), "Summary did not close back to the workout tab")
    }

    @MainActor
    func testTabsShowProgressRanksAndProfile() throws {
        let app = launchPastOnboarding()

        openTab(app, "Progress")
        XCTAssertTrue(app.staticTexts["Personal records"].waitForExistence(timeout: 5), "Progress tab did not load")
        XCTAssertTrue(app.staticTexts["Heaviest — Barbell Bench Press"].waitForExistence(timeout: 5))
        attachScreenshot(app, named: "06 Progress")

        openTab(app, "Ranks")
        XCTAssertTrue(app.staticTexts["Meera"].waitForExistence(timeout: 5), "Leaderboard did not load")
        XCTAssertTrue(app.staticTexts["(you)"].exists)
        attachScreenshot(app, named: "07 Leaderboard")

        openTab(app, "Profile")
        XCTAssertTrue(app.staticTexts["Badges"].waitForExistence(timeout: 5), "Profile tab did not load")
        XCTAssertTrue(app.staticTexts["1 / 2"].waitForExistence(timeout: 5))
        attachScreenshot(app, named: "08 Profile")
    }

    // End-to-end against the real backend (uvicorn on localhost:8000). Logs a real session,
    // so it only runs when xcodebuild is given TEST_RUNNER_METALARM_LIVE_UI=1.
    @MainActor
    func testLiveBackendTour() throws {
        try XCTSkipUnless(ProcessInfo.processInfo.environment["METALARM_LIVE_UI"] == "1",
                          "Start the backend and set TEST_RUNNER_METALARM_LIVE_UI=1 to run")
        let app = XCUIApplication()
        app.launchArguments += ["-UITestResetOnboarding"]
        // IPv4 on purpose: "localhost" can resolve to ::1, where another service may hold port 8000.
        app.launchEnvironment["METALARM_BACKEND_URL"] =
            ProcessInfo.processInfo.environment["METALARM_BACKEND_URL"] ?? "http://127.0.0.1:8000"
        app.launch()

        let getStarted = app.buttons["getStartedButton"]
        XCTAssertTrue(getStarted.waitForExistence(timeout: 10), "Onboarding never appeared")
        getStarted.tap()
        let levelCard = app.staticTexts.matching(NSPredicate(format: "label BEGINSWITH 'Level '")).firstMatch
        XCTAssertTrue(levelCard.waitForExistence(timeout: 10), "Home never loaded from the backend")
        attachScreenshot(app, named: "Live 01 Home")

        app.buttons["homeStartWorkoutButton"].tap()
        let logSet = app.buttons["logSetButton"]
        XCTAssertTrue(logSet.waitForExistence(timeout: 10), "Backend session never started")
        logSet.tap()
        XCTAssertTrue(app.staticTexts["1 sets logged"].waitForExistence(timeout: 10))
        logSet.tap()
        XCTAssertTrue(app.staticTexts["2 sets logged"].waitForExistence(timeout: 10))
        attachScreenshot(app, named: "Live 02 Workout")

        app.buttons["finishButton"].tap()
        XCTAssertTrue(app.buttons["doneButton"].waitForExistence(timeout: 10), "Summary never appeared")
        attachScreenshot(app, named: "Live 03 Summary")
        app.buttons["doneButton"].tap()

        openTab(app, "Progress")
        XCTAssertTrue(app.staticTexts["Personal records"].waitForExistence(timeout: 10))
        attachScreenshot(app, named: "Live 04 Progress Bench")
        app.buttons["Squat"].tap()
        let squatRecord = app.staticTexts.matching(NSPredicate(format: "label CONTAINS 'Barbell Back Squat'")).firstMatch
        XCTAssertTrue(squatRecord.waitForExistence(timeout: 10), "Squat tab did not load Barbell Back Squat")
        attachScreenshot(app, named: "Live 05 Progress Squat")

        openTab(app, "Ranks")
        XCTAssertTrue(app.staticTexts["(you)"].waitForExistence(timeout: 10))
        attachScreenshot(app, named: "Live 06 Leaderboard")

        openTab(app, "Profile")
        XCTAssertTrue(app.staticTexts["Badges"].waitForExistence(timeout: 10))
        attachScreenshot(app, named: "Live 07 Profile")
    }

    @MainActor
    func testLaunchPerformance() throws {
        // This measures how long it takes to launch your application.
        measure(metrics: [XCTApplicationLaunchMetric()]) {
            XCUIApplication().launch()
        }
    }
}
