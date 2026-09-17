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

@MainActor
struct HealthStatusProbeTests {
    @Test func turningHealthOnRecordsWhatHappened() async {
        let model = AppModel(api: MockAPIClient())
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
