//
//  HealthPermissionUITests.swift
//  MetalARMUITests
//
//  Drives the REAL Health permission sheet, which belongs to another process.
//
//  What this asserts is an invariant rather than a particular answer: whatever
//  happens on that sheet, the toggle must tell the truth. The bug this guards
//  against switched the toggle ON after a refusal - HealthKit does not throw
//  when the user taps "Don't Allow" - and then failed silently for ever.
//
//  So: allowed means on with nothing to report; anything else means off WITH a
//  reason on screen. A test written this way cannot pass by accident and does
//  not depend on the sheet's exact wording or layout.
//

import XCTest

final class HealthPermissionUITests: XCTestCase {
    override func setUpWithError() throws {
        continueAfterFailure = false
    }

    @MainActor
    private func openProfile(_ app: XCUIApplication) {
        let tab = app.tabBars.buttons["Profile"]
        if tab.exists { tab.tap() } else { app.buttons["Profile"].firstMatch.tap() }
    }

    @MainActor
    private func scrollIntoView(_ element: XCUIElement, in app: XCUIApplication) {
        var swipes = 0
        while !element.isHittable && swipes < 8 {
            app.swipeUp()
            swipes += 1
            Thread.sleep(forTimeInterval: 0.3)
        }
    }

    /// Answers the Health permission sheet.
    ///
    /// The sheet is presented by HealthPrivacyService but appears in the APP's
    /// element tree - a navigation bar called "Health Access" - not in
    /// springboard. An earlier version of this test waited on springboard,
    /// found nothing, and failed while the sheet sat open in front of it, with
    /// the app correctly suspended awaiting the answer.
    @MainActor
    private func answerHealthSheet(in app: XCUIApplication) -> Bool {
        let sheet = app.navigationBars["Health Access"]
        guard sheet.waitForExistence(timeout: 12) else { return false }

        // The sheet's own identifiers, read from its element tree. "Allow" is
        // DISABLED until something is switched on, and "Turn On All" is a cell,
        // not a button - guessing at labels tapped nothing and left Allow grey.
        let allCategories = app.cells["UIA.Health.AuthSheet.AllCategoryButton"]
        let workouts = app.switches["UIA.Health.Workouts.SwitchCell.Switch"]
        if allCategories.waitForExistence(timeout: 5), allCategories.isHittable {
            allCategories.tap()
        } else if workouts.waitForExistence(timeout: 5), workouts.isHittable {
            workouts.tap()
        }

        let allow = app.buttons["UIA.Health.Allow.Button"]
        guard allow.waitForExistence(timeout: 5) else { return false }
        // Only tappable once a category is on; that is the whole point of the
        // step above.
        guard allow.isEnabled else { return false }
        allow.tap()
        return sheet.waitForNonExistence(timeout: 12)
    }

    @MainActor
    func testHealthToggleNeverClaimsAConnectionItDoesNotHave() throws {
        let app = XCUIApplication()
        app.launchArguments = [
            "-UITestMockAPI", "-UITestSignedIn", "-UITestSkipOnboarding",
            // Keeps the notification prompt out of the way of this one.
            "-notifications.asked", "YES",
        ]
        app.launch()

        openProfile(app)
        let toggle = app.switches["healthSyncToggle"]
        XCTAssertTrue(toggle.waitForExistence(timeout: 20), "Health toggle missing from Profile")
        scrollIntoView(toggle, in: app)
        XCTAssertTrue(toggle.isHittable, "Health toggle never scrolled into view")

        // Start from off, so the tap under test is the one that asks.
        if (toggle.value as? String) == "1" {
            toggle.tap()
            Thread.sleep(forTimeInterval: 1)
        }
        XCTAssertEqual(toggle.value as? String, "0", "Health should start switched off")

        toggle.tap()
        _ = answerHealthSheet(in: app)
        // The app records the answer and re-renders.
        Thread.sleep(forTimeInterval: 2.5)

        let isOn = (toggle.value as? String) == "1"
        let status = app.descendants(matching: .any)["healthStatusText"]

        if isOn {
            XCTAssertFalse(
                status.exists,
                "The toggle says Health is connected while the app is reporting a problem"
            )
        } else {
            XCTAssertTrue(
                status.exists,
                "The toggle refused to switch on without telling the user why"
            )
        }
    }
}
