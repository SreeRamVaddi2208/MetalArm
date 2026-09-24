//
//  MetalARMUITestCase.swift
//  MetalARMUITests
//
//  What every mock-backend UI test shares: launching, finding things, typing
//  past iOS's password sheets, and screenshots. A base class rather than an
//  XCTestCase extension, because DemoTour keeps its own private helpers of the
//  same names.
//

import XCTest

class MetalARMUITestCase: XCTestCase {
    let password = "correct-horse-1"

    override func setUpWithError() throws {
        continueAfterFailure = false
    }

    @MainActor
    func launch(_ arguments: [String]) -> XCUIApplication {
        let app = XCUIApplication()
        app.launchArguments = ["-UITestMockAPI"] + arguments
        app.launch()
        return app
    }

    @MainActor
    func launchSignedIn(_ extra: [String] = []) -> XCUIApplication {
        let app = launch(["-UITestSignedIn", "-UITestSkipOnboarding"] + extra)
        XCTAssertTrue(app.staticTexts["Level 14 · Intermediate"].waitForExistence(timeout: 10), "Home never loaded")
        return app
    }

    @MainActor
    func openTab(_ app: XCUIApplication, _ name: String) {
        let tab = app.tabBars.buttons[name]
        if tab.exists {
            tab.tap()
        } else {
            app.buttons[name].firstMatch.tap()
        }
    }

    @MainActor
    func element(_ app: XCUIApplication, _ identifier: String) -> XCUIElement {
        app.descendants(matching: .any)[identifier]
    }

    @MainActor
    func type(_ text: String, into field: XCUIElement) {
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
    func typeNewPassword(_ text: String, into field: XCUIElement, in app: XCUIApplication) {
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
    func dismissSavePasswordPrompt(_ app: XCUIApplication) {
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

    /// Waits for a control to become enabled. A button disabled at the moment
    /// it is tapped swallows the tap silently, and the failure then shows up
    /// somewhere else entirely - a sheet still open two steps later.
    @MainActor
    @discardableResult
    func waitUntilEnabled(_ element: XCUIElement, timeout: TimeInterval = 5) -> Bool {
        let enabled = expectation(for: NSPredicate(format: "isEnabled == true"), evaluatedWith: element)
        return XCTWaiter.wait(for: [enabled], timeout: timeout) == .completed
    }

    @MainActor
    func attachScreenshot(_ app: XCUIApplication, named name: String) {
        let attachment = XCTAttachment(screenshot: app.screenshot())
        attachment.name = name
        attachment.lifetime = .keepAlways
        add(attachment)
    }

    /// Scrolls until `element` can really be tapped. "Hittable" alone is not
    /// enough: the floating tab bar sits over the content, and XCUITest calls an
    /// element under it hittable - the tap then lands on the tab bar. On a small
    /// phone (CI's iPhone 17e) that tapped the current tab, which scrolls it to
    /// the top, instead of the Streak reminders switch. So nudge the content up
    /// until the element is clear of the bar.
    ///
    /// `clearOf` names whatever is in the way when it is not the tab bar. A
    /// sheet has its own footer, and a card only half-scrolled into the sheet
    /// reports a frame whose CENTRE is behind that footer - XCUITest taps the
    /// centre, so the tap lands on the footer's disabled button and is
    /// swallowed silently. The workflow picks whichever simulator the runner
    /// happens to have (ios.yml), so which cards this hits changes run to run.
    @MainActor
    func scrollUntilHittable(
        _ element: XCUIElement,
        in app: XCUIApplication,
        maxSwipes: Int = 12,
        clearOf obstruction: XCUIElement? = nil
    ) {
        var swipes = 0
        while !element.isHittable && swipes < maxSwipes {
            app.swipeUp()
            swipes += 1
        }
        XCTAssertTrue(element.isHittable, "\(element) never scrolled into view")

        let bar = obstruction ?? app.tabBars.firstMatch
        guard bar.exists else { return }
        var nudges = 0
        while element.frame.maxY > bar.frame.minY - 8 && nudges < 6 {
            let from = app.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.6))
            from.press(forDuration: 0.05, thenDragTo: from.withOffset(CGVector(dx: 0, dy: -120)))
            nudges += 1
        }
        XCTAssertLessThanOrEqual(element.frame.maxY, bar.frame.minY - 8, "\(element) is still under the tab bar")
    }

    @MainActor
    func deleteAccount(_ app: XCUIApplication, screenshot: String? = nil) {
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
}
