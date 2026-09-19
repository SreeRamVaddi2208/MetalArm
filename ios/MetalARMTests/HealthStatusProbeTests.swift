//
//  HealthStatusProbeTests.swift
//  MetalARMTests
//
//  A diagnostic, not a guard: it exercises setHealthSync against the REAL
//  AppleHealthWriter on whatever destination the suite is running on, and
//  reports what the app concluded.
//
//  The UI test failed with "the toggle refused to switch on without telling
//  the user why", and the log could not say whether the status line was never
//  set (an app bug) or was set but not reachable by the accessibility query (a
//  test bug). This answers that directly.
//

import HealthKit
import Testing

@testable import MetalARM

//  Runs only once the simulator has ANSWERED the Health permission sheet. On a
//  fresh device (every CI runner) setHealthSync would put that sheet up, a
//  unit-test host cannot answer it, and the suite would sit there until the
//  job timed out - which GitHub reports as "cancelled". Answered once, the
//  request returns at once with no sheet, so locally it still runs.
@MainActor
@Suite(
    .enabled(if: permissionAlreadyAnswered(), "no Health permission answer on this device; the sheet would hang the suite"),
    .timeLimit(.minutes(1))
)
struct HealthStatusProbeTests {
    @Test func turningHealthOnRecordsWhatHappened() async {
        let model = AppModel.forTesting()
        model.healthWriter = AppleHealthWriter()
        model.healthSettings = HealthSettings()

        await model.setHealthSync(true)

        // The invariant the UI test was really checking: the app must never be
        // switched on AND complaining, and never off AND silent.
        if model.healthSettings.enabled {
            #expect(model.healthStatus.isEmpty)
        } else {
            #expect(!model.healthStatus.isEmpty, "Health is off with no reason recorded")
        }
    }
}

private func permissionAlreadyAnswered() -> Bool {
    HKHealthStore.isHealthDataAvailable()
        && HKHealthStore().authorizationStatus(for: HKObjectType.workoutType()) != .notDetermined
}
