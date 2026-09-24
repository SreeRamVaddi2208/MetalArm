//
//  ButtonSweepUITests.swift
//  MetalARMUITests
//
//  Presses every control the other UI tests never touch, and checks that each
//  one did its job - not merely that it exists. Runs against the mock backend.
//
//  Left to other suites: the Health toggle (HealthPermissionUITests drives the
//  real permission sheet) and the empty-Ranks buttons, which the mock cannot
//  reach because its signed-in user already has a party (testLiveBackendTour
//  presses them on a fresh account).
//

import XCTest

final class ButtonSweepUITests: MetalARMUITestCase {
    override func setUpWithError() throws {
        try super.setUpWithError()
        // Finishing a workout asks for notification permission; answer it
        // whenever it gets in the way, so it can never block a tap.
        addUIInterruptionMonitor(withDescription: "Notification permission") { alert in
            for label in ["Allow", "Don’t Allow", "Don't Allow"] where alert.buttons[label].exists {
                alert.buttons[label].tap()
                return true
            }
            return false
        }
    }

    // MARK: - Helpers

    private let safari = XCUIApplication(bundleIdentifier: "com.apple.mobilesafari")

    /// A Link must hand off to Safari; then come back to the app.
    @MainActor
    private func assertOpensSafari(_ link: XCUIElement, in app: XCUIApplication, _ name: String) {
        link.tap()
        // Safari's FIRST launch on a cold CI runner takes longer than 15 s,
        // which failed this test there while it passed locally every time.
        // Wait properly, and tap once more before giving up: a tap that lands
        // while the page is still opening is indistinguishable from a slow one.
        if !safari.wait(for: .runningForeground, timeout: 30) {
            if link.isHittable { link.tap() }
            XCTAssertTrue(
                safari.wait(for: .runningForeground, timeout: 30),
                "\(name) did not open Safari")
        }
        app.activate()
        XCTAssertTrue(app.wait(for: .runningForeground, timeout: 10), "Could not return to the app after \(name)")
        // "Running foreground" arrives before the scene is taking touches: a
        // tap straight after it was dropped on 1 run in 3 (it never was after
        // a 2 s settle). No person taps that fast after switching back.
        Thread.sleep(forTimeInterval: 2)
    }

    /// A SwiftUI Link: exposed as a Button by some iOS versions, a Link by others.
    @MainActor
    private func linkNamed(_ label: String, in app: XCUIApplication) -> XCUIElement {
        app.descendants(matching: .any).matching(
            NSPredicate(format: "label == %@ AND (elementType == %d OR elementType == %d)",
                        label, XCUIElement.ElementType.button.rawValue, XCUIElement.ElementType.link.rawValue)
        ).firstMatch
    }

    /// A ShareLink must put up the system share sheet; then close it.
    @MainActor
    private func assertOpensShareSheet(_ button: XCUIElement, in app: XCUIApplication, _ name: String) {
        XCTAssertTrue(button.waitForExistence(timeout: 5), "\(name) missing")
        button.tap()
        let sheet = app.otherElements["ActivityListView"]
        let copy = app.buttons["Copy"]
        let appeared = sheet.waitForExistence(timeout: 10) || copy.waitForExistence(timeout: 2)
        XCTAssertTrue(appeared, "\(name) did not open the share sheet")
        attachScreenshot(app, named: "Share sheet - \(name)")

        // Closing it is the flaky half, and it failed on CI: the sheet is still
        // animating in when the Close button is first looked for, so the old
        // code fell through to a swipe that landed on nothing. Wait for Close,
        // and keep trying rather than assuming one attempt worked.
        let close = app.buttons["Close"].firstMatch
        for attempt in 1...3 {
            if close.waitForExistence(timeout: attempt == 1 ? 5 : 2), close.isHittable {
                close.tap()
            } else {
                app.swipeDown(velocity: .fast)
            }
            if sheet.waitForNonExistence(timeout: 5) { return }
        }
        XCTFail("\(name)'s share sheet would not close")
    }

    /// Taps the switch inside a full-width SwiftUI Toggle row, then waits for
    /// its value to change: SwiftUI re-renders a beat after the tap, so reading
    /// it straight away can still see the old value.
    @MainActor
    private func flip(_ toggle: XCUIElement, _ name: String) {
        let before = isOn(toggle)
        let want = before ? "0" : "1"
        // The switch itself when it is addressable, else the right-hand end of
        // the row. A coordinate tap alone missed on CI: the row is full width,
        // and 93% across is beside the switch on a narrower device.
        let target = toggle.switches.firstMatch.exists ? toggle.switches.firstMatch : toggle
        for attempt in 1...3 {
            if attempt == 1, target.isHittable {
                target.tap()
            } else {
                toggle.coordinate(withNormalizedOffset: CGVector(dx: 0.93, dy: 0.5)).tap()
            }
            let changed = expectation(for: NSPredicate(format: "value == %@", want), evaluatedWith: toggle)
            if XCTWaiter.wait(for: [changed], timeout: 3) == .completed { return }
        }
        XCTFail("\(name) did not flip")
    }

    @MainActor
    private func isOn(_ toggle: XCUIElement) -> Bool {
        (toggle.value as? String) == "1"
    }

    @MainActor
    private func startWorkoutWithBench(_ app: XCUIApplication) {
        app.buttons["homeStartWorkoutButton"].tap()
        let addFirst = app.buttons["addFirstExerciseButton"]
        XCTAssertTrue(addFirst.waitForExistence(timeout: 5), "Workout never started")
        addFirst.tap()
        let bench = app.buttons["pickExercise-Barbell Bench Press"]
        XCTAssertTrue(bench.waitForExistence(timeout: 10), "Exercise picker did not load")
        bench.tap()
        XCTAssertTrue(app.buttons["logSetButton"].waitForExistence(timeout: 5), "Exercise card missing")
    }

    // MARK: - Onboarding and sign-in

    @MainActor
    func testOnboardingAndAuthControls() throws {
        let app = launch(["-UITestResetOnboarding"])
        let haveAccount = app.buttons["haveAccountButton"]
        XCTAssertTrue(haveAccount.waitForExistence(timeout: 10), "Onboarding never appeared")
        haveAccount.tap()
        XCTAssertTrue(app.staticTexts["Welcome back"].waitForExistence(timeout: 5), "'I already have an account' did not open sign-in")
        XCTAssertFalse(app.textFields["displayNameField"].exists, "Sign-in should not ask for a name")

        let toggle = app.buttons["authModeToggle"]
        toggle.tap()
        XCTAssertTrue(app.staticTexts["Create your account"].waitForExistence(timeout: 5), "Toggle did not switch to sign-up")
        XCTAssertTrue(app.textFields["displayNameField"].exists)
        toggle.tap()
        XCTAssertTrue(app.staticTexts["Welcome back"].waitForExistence(timeout: 5), "Toggle did not switch back to sign-in")

        let submit = app.buttons["authSubmitButton"]
        XCTAssertFalse(submit.isEnabled, "Sign In should be disabled until the form is filled")

        assertOpensSafari(linkNamed("Privacy Policy", in: app), in: app, "Privacy Policy (sign-in)")

        type("sree@metalarm.dev", into: app.textFields["emailField"])
        type(password, into: app.secureTextFields["passwordField"])
        XCTAssertTrue(submit.isEnabled, "Sign In stayed disabled with a filled form")
        submit.tap()
        XCTAssertTrue(app.staticTexts["Level 14 · Intermediate"].waitForExistence(timeout: 10), "Sign In did not reach Home")
    }

    // MARK: - Workout

    @MainActor
    func testWorkoutControls() throws {
        let app = launchSignedIn()
        app.buttons["homeStartWorkoutButton"].tap()

        // The picker's Cancel closes it without adding anything.
        let addFirst = app.buttons["addFirstExerciseButton"]
        XCTAssertTrue(addFirst.waitForExistence(timeout: 5), "Workout never started")
        addFirst.tap()
        XCTAssertTrue(app.navigationBars["Add Exercise"].waitForExistence(timeout: 5), "Picker did not open")
        app.navigationBars["Add Exercise"].buttons["Cancel"].tap()
        XCTAssertTrue(app.navigationBars["Add Exercise"].waitForNonExistence(timeout: 5), "Picker Cancel did not close it")
        XCTAssertTrue(addFirst.exists, "Cancel should leave the workout empty")

        // Search, then pick.
        addFirst.tap()
        let search = app.searchFields.firstMatch
        XCTAssertTrue(search.waitForExistence(timeout: 5))
        type("bench", into: search)
        // The search is debounced, so wait for the list to narrow.
        XCTAssertTrue(app.buttons["pickExercise-Barbell Back Squat"].waitForNonExistence(timeout: 5), "Search did not filter")
        XCTAssertTrue(app.buttons["pickExercise-Barbell Bench Press"].exists, "Search lost the bench press")
        app.buttons["pickExercise-Barbell Bench Press"].tap()
        XCTAssertTrue(app.buttons["logSetButton"].waitForExistence(timeout: 5))

        // "Add" chip opens the picker again for a second exercise.
        app.buttons["addExerciseButton"].tap()
        let squat = app.buttons["pickExercise-Barbell Back Squat"]
        XCTAssertTrue(squat.waitForExistence(timeout: 10), "Add did not open the picker")
        squat.tap()
        XCTAssertTrue(app.staticTexts["Barbell Back Squat"].waitForExistence(timeout: 5), "Second exercise not added")

        // The chips switch between exercises.
        app.buttons["Barbell Bench Press"].firstMatch.tap()
        XCTAssertTrue(element(app, "ghostValues").waitForExistence(timeout: 5), "Chip did not switch back to the bench press")

        // Keyboard Done closes the number pad.
        let weight = app.textFields["weightField"]
        weight.tap()
        XCTAssertTrue(app.keyboards.firstMatch.waitForExistence(timeout: 5), "Number pad did not open")
        app.buttons["keyboardDoneButton"].tap()
        XCTAssertTrue(app.keyboards.firstMatch.waitForNonExistence(timeout: 5), "Keyboard Done did not close the keyboard")

        app.buttons["logSetButton"].tap()
        XCTAssertTrue(app.staticTexts["1 set logged"].waitForExistence(timeout: 5), "Log Set did nothing")

        // Discard, through the options menu and its confirmation.
        app.buttons["Workout options"].tap()
        let discard = app.buttons["Discard Workout"]
        XCTAssertTrue(discard.waitForExistence(timeout: 5), "Options menu did not open")
        discard.tap()
        // Wait for the CONFIRMATION, not just for a button of that name: the
        // menu item and the dialog's button share it, and a tap during the
        // dialog's animation lands on nothing (which is what failed here).
        XCTAssertTrue(
            app.staticTexts["Discard this workout?"].waitForExistence(timeout: 5),
            "The confirmation never appeared")
        let confirm = app.buttons["Discard Workout"].firstMatch
        XCTAssertTrue(confirm.waitForExistence(timeout: 5), "Discard was not confirmed")
        for _ in 1...3 where !confirm.isHittable { Thread.sleep(forTimeInterval: 0.4) }
        confirm.tap()
        XCTAssertTrue(app.buttons["workoutStartButton"].waitForExistence(timeout: 10), "Discard did not end the workout")

        // The Workout tab's own Start button.
        app.buttons["workoutStartButton"].tap()
        XCTAssertTrue(addFirst.waitForExistence(timeout: 5), "Start Workout (Workout tab) did nothing")
    }

    // MARK: - Summary, celebration and sharing

    @MainActor
    func testCelebrationAndSummaryControls() throws {
        let app = launchSignedIn(["-UITestLevelUp"])
        startWorkoutWithBench(app)
        app.buttons["logSetButton"].tap()
        app.buttons["finishButton"].tap()

        let overlay = element(app, "levelUpOverlay")
        XCTAssertTrue(overlay.waitForExistence(timeout: 5), "Level-up never appeared")
        Thread.sleep(forTimeInterval: 1.0) // its buttons fade in
        assertOpensShareSheet(app.buttons["levelUpShareButton"], in: app, "Level-up share")
        app.buttons["levelUpContinueButton"].tap()
        XCTAssertTrue(overlay.waitForNonExistence(timeout: 5), "Continue did not close the celebration")

        assertOpensShareSheet(app.buttons["shareButton"], in: app, "Summary share")
        app.buttons["doneButton"].tap()
        XCTAssertTrue(app.buttons["workoutStartButton"].waitForExistence(timeout: 5), "Done did not close the summary")
    }

    // MARK: - Ranks

    @MainActor
    func testRanksControls() throws {
        let app = launchSignedIn()
        openTab(app, "Ranks")
        XCTAssertTrue(app.staticTexts["Meera"].waitForExistence(timeout: 5), "Party board did not load")

        let add = app.buttons["Add a party"]

        // Create: Cancel does nothing, Create adds the party.
        add.tap()
        app.buttons["Create a Party"].tap()
        XCTAssertTrue(app.alerts["Create a party"].waitForExistence(timeout: 5), "Create a Party did not open")
        app.alerts["Create a party"].buttons["Cancel"].tap()
        XCTAssertTrue(app.alerts["Create a party"].waitForNonExistence(timeout: 5), "Cancel did not close Create")

        add.tap()
        app.buttons["Create a Party"].tap()
        let createAlert = app.alerts["Create a party"]
        XCTAssertTrue(createAlert.waitForExistence(timeout: 5))
        type("Sweep Crew", into: createAlert.textFields.firstMatch)
        createAlert.buttons["Create"].tap()
        // Two parties now, so the header becomes a party switcher.
        let switcher = app.buttons.containing(NSPredicate(format: "label CONTAINS 'Sweep Crew'")).firstMatch
        XCTAssertTrue(switcher.waitForExistence(timeout: 5), "Created party not shown")

        // Join: Cancel does nothing, a wrong code is explained, the right one works.
        add.tap()
        app.buttons["Join with Code"].tap()
        XCTAssertTrue(app.alerts["Join a party"].waitForExistence(timeout: 5), "Join with Code did not open")
        app.alerts["Join a party"].buttons["Cancel"].tap()
        XCTAssertTrue(app.alerts["Join a party"].waitForNonExistence(timeout: 5), "Cancel did not close Join")

        add.tap()
        app.buttons["Join with Code"].tap()
        type("WRONG999", into: app.alerts["Join a party"].textFields.firstMatch)
        app.alerts["Join a party"].buttons["Join"].tap()
        XCTAssertTrue(app.staticTexts.containing(NSPredicate(format: "label CONTAINS 'No party with that invite code'")).firstMatch
            .waitForExistence(timeout: 5), "A wrong invite code was not explained")

        add.tap()
        app.buttons["Join with Code"].tap()
        type("IRON2345", into: app.alerts["Join a party"].textFields.firstMatch)
        app.alerts["Join a party"].buttons["Join"].tap()
        XCTAssertTrue(app.staticTexts.containing(NSPredicate(format: "label CONTAINS 'No party with that invite code'")).firstMatch
            .waitForNonExistence(timeout: 5), "Joining with a valid code still shows an error")
        // Joining selects the party joined. Meera also appears in the league and
        // raid cards, so look for a row that only Iron Crew's own board has.
        let ironCrewRow = app.staticTexts["3 workouts · Novice"]
        XCTAssertTrue(ironCrewRow.waitForExistence(timeout: 5), "Joining Iron Crew did not switch to its board")

        // The switcher moves between parties. It is labelled with the selected
        // party, so while its menu is open the other party's name is the only match.
        app.buttons["Iron Crew"].firstMatch.tap()
        app.buttons["Sweep Crew"].tap()
        XCTAssertTrue(ironCrewRow.waitForNonExistence(timeout: 5), "Switching to Sweep Crew kept Iron Crew's board")
        app.buttons["Sweep Crew"].firstMatch.tap()
        app.buttons["Iron Crew"].tap()
        XCTAssertTrue(ironCrewRow.waitForExistence(timeout: 5), "Switching back to Iron Crew did not load its board")

        let share = app.buttons["Share"].firstMatch
        scrollUntilHittable(share, in: app)
        assertOpensShareSheet(share, in: app, "Invite code share")
    }

    // MARK: - Progress

    @MainActor
    func testProgressControls() throws {
        let app = launchSignedIn()
        openTab(app, "Progress")
        XCTAssertTrue(app.staticTexts["Heaviest — Barbell Bench Press"].waitForExistence(timeout: 5), "Progress did not load")

        app.buttons["Barbell Back Squat"].tap()
        XCTAssertTrue(app.staticTexts.containing(NSPredicate(format: "label ENDSWITH '— Barbell Back Squat'")).firstMatch
            .waitForExistence(timeout: 5), "Squat tab did not show squat records")
        XCTAssertFalse(app.staticTexts["Heaviest — Barbell Bench Press"].exists, "Bench records still shown on the squat tab")

        app.buttons["Barbell Bench Press"].tap()
        XCTAssertTrue(app.staticTexts["Heaviest — Barbell Bench Press"].waitForExistence(timeout: 5), "Bench tab did not come back")
    }

    // MARK: - Profile

    @MainActor
    func testProfileSettingsControls() throws {
        var app = launchSignedIn()
        openTab(app, "Profile")
        XCTAssertTrue(element(app, "characterCard").waitForExistence(timeout: 5), "Profile did not load")

        // The training path opens the same cards onboarding uses.
        let openPath = app.buttons["trainingPathButton"]
        scrollUntilHittable(openPath, in: app)
        openPath.tap()
        let athlete = app.buttons["path-athlete"]
        XCTAssertTrue(athlete.waitForExistence(timeout: 5), "The training path cards did not open")
        let confirmPath = app.buttons["confirmPathButton"]
        scrollUntilHittable(athlete, in: app, clearOf: confirmPath)
        athlete.tap()
        XCTAssertTrue(waitUntilEnabled(confirmPath), "Choosing a path did not enable Save")
        confirmPath.tap()
        // The sheet must close, or everything below is looking at the wrong screen.
        XCTAssertTrue(athlete.waitForNonExistence(timeout: 10), "The path sheet did not close")
        XCTAssertTrue(app.staticTexts["Athletic"].waitForExistence(timeout: 10), "The chosen path is not shown on Profile")

        // kg -> lb shows up elsewhere in the app, then back.
        let picker = app.segmentedControls["weightUnitPicker"]
        scrollUntilHittable(picker, in: app)
        app.swipeUp()
        attachScreenshot(app, named: "Profile settings")
        picker.buttons["lb"].tap()
        XCTAssertTrue(picker.buttons["lb"].isSelected, "lb not selected")
        openTab(app, "Progress")
        XCTAssertTrue(app.staticTexts["lb top set"].waitForExistence(timeout: 5), "Switching to lb did not change Progress")
        openTab(app, "Profile")
        scrollUntilHittable(picker, in: app)
        picker.buttons["kg"].tap()
        openTab(app, "Progress")
        XCTAssertTrue(app.staticTexts["kg top set"].waitForExistence(timeout: 5), "Switching back to kg did not change Progress")
        openTab(app, "Profile")

        // Both notification toggles flip, and stay flipped across a relaunch.
        for id in ["restAlertsToggle", "streakRemindersToggle"] {
            let toggle = app.switches[id]
            scrollUntilHittable(toggle, in: app)
            let before = isOn(toggle)
            flip(toggle, id)

            app.terminate()
            app = launchSignedIn()
            openTab(app, "Profile")
            let again = app.switches[id]
            scrollUntilHittable(again, in: app)
            XCTAssertNotEqual(isOn(again), before, "\(id) did not survive a relaunch")
            flip(again, "\(id) (back)") // put it back for the next run
        }

        // Import opens the file picker; Cancel closes it.
        let importButton = app.buttons["importWorkoutsButton"]
        scrollUntilHittable(importButton, in: app)
        importButton.tap()
        let cancel = app.buttons["Cancel"].firstMatch
        XCTAssertTrue(cancel.waitForExistence(timeout: 10), "Import did not open the file picker")
        attachScreenshot(app, named: "Import file picker")
        cancel.tap()
        XCTAssertTrue(importButton.waitForExistence(timeout: 5), "Could not get back from the file picker")

        // Privacy and Support hand off to Safari.
        let privacy = linkNamed("Privacy Policy", in: app)
        scrollUntilHittable(privacy, in: app)
        assertOpensSafari(privacy, in: app, "Privacy Policy (profile)")
        let support = linkNamed("Support", in: app)
        scrollUntilHittable(support, in: app)
        assertOpensSafari(support, in: app, "Support")

        // Delete Account, then Cancel: still signed in.
        let delete = app.buttons["deleteAccountButton"]
        scrollUntilHittable(delete, in: app)
        delete.tap()
        XCTAssertTrue(app.navigationBars["Delete Account"].waitForExistence(timeout: 5), "Delete Account did not open")
        app.navigationBars["Delete Account"].buttons["Cancel"].tap()
        XCTAssertTrue(app.navigationBars["Delete Account"].waitForNonExistence(timeout: 5), "Cancel did not close Delete Account")
        XCTAssertTrue(delete.exists, "Cancelling a delete should leave you signed in")

        // Sign Out of All Devices, confirmed: back to sign-in.
        let everywhere = app.buttons["Sign Out of All Devices"]
        scrollUntilHittable(everywhere, in: app)
        everywhere.tap()
        let confirm = app.buttons["Sign Out Everywhere"]
        XCTAssertTrue(confirm.waitForExistence(timeout: 5), "Sign Out Everywhere was not confirmed")
        confirm.tap()
        XCTAssertTrue(app.buttons["authSubmitButton"].waitForExistence(timeout: 10), "Sign Out Everywhere did not sign out")
    }

    @MainActor
    func testSignOut() throws {
        let app = launchSignedIn()
        openTab(app, "Profile")
        let signOut = app.buttons["signOutButton"]
        XCTAssertTrue(signOut.waitForExistence(timeout: 10))
        scrollUntilHittable(signOut, in: app)
        signOut.tap()
        XCTAssertTrue(app.buttons["authSubmitButton"].waitForExistence(timeout: 10), "Sign Out did not sign out")
    }

    // MARK: - Pull to refresh

    @MainActor
    func testPullToRefreshKeepsEveryTabLoaded() throws {
        let app = launchSignedIn()
        let checks: [(tab: String, content: XCUIElement)] = [
            ("Home", app.staticTexts["Level 14 · Intermediate"]),
            ("Progress", app.staticTexts["Heaviest — Barbell Bench Press"]),
            ("Ranks", app.staticTexts["Meera"]),
            ("Profile", app.staticTexts["Badges"]),
        ]
        for (tab, content) in checks {
            openTab(app, tab)
            XCTAssertTrue(content.waitForExistence(timeout: 10), "\(tab) did not load")
            let top = app.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.25))
            top.press(forDuration: 0.1, thenDragTo: app.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.85)))
            XCTAssertTrue(content.waitForExistence(timeout: 10), "\(tab) lost its content after a refresh")
        }
    }
}
