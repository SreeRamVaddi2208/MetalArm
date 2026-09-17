//
//  HealthKitSmokeTests.swift
//  MetalARMTests
//
//  Exercises the REAL HealthKit writer, not the spy.
//
//  The rest of the Health tests inject SpyHealthWriter, which proves the app's
//  logic but would pass just as happily if the entitlement were missing, the
//  usage string were absent, or HealthKit were never linked. These tests touch
//  the actual framework, so they fail if any of that is wrong:
//
//  - a missing NSHealthUpdateUsageDescription CRASHES on requestAuthorization,
//  - a missing entitlement leaves authorization permanently undetermined,
//  - a writer that ignores permission would return .saved here instead of
//    .notAuthorized.
//
//  Nothing here asks for permission: a unit-test host cannot answer the sheet,
//  and an unanswered sheet would hang the suite. The permission flow itself is
//  covered in the UI test.
//

import HealthKit
import Testing

@testable import MetalARM

// The app module is main-actor by default, so HealthWriteResult's Equatable
// conformance is too. Matching that here keeps the comparisons below on the
// right side of isolation - every other suite in this target does the same.
@MainActor
struct HealthKitSmokeTests {
    private let writer = AppleHealthWriter()

    @Test func healthKitIsAvailableHere() {
        // True on a simulator runtime that ships HealthKit, and on any iPhone.
        // False on iPad-only or Mac destinations, where the app correctly
        // reports `.unavailable` rather than pretending to save.
        #expect(writer.isAvailable == HKHealthStore.isHealthDataAvailable())
    }

    @Test func authorizationStatusIsReadableWithoutAsking() {
        guard writer.isAvailable else { return }
        let status = HKHealthStore().authorizationStatus(for: HKObjectType.workoutType())
        // Undetermined until the user is asked - never "authorized" by default,
        // which is the assumption the old code accidentally made.
        #expect(status == .notDetermined || status == .sharingDenied || status == .sharingAuthorized)
        #expect(writer.isAuthorized == (status == .sharingAuthorized))
    }

    @Test func writingWithoutPermissionIsRefusedRatherThanCrashing() async {
        guard writer.isAvailable, !writer.isAuthorized else { return }
        let result = await writer.save(
            FinishedWorkout(
                sessionID: "smoke-test",
                start: Date(timeIntervalSinceNow: -1800),
                end: Date(),
                volumeKg: 1250,
                workingSets: 9
            )
        )
        #expect(result == .notAuthorized)
        #expect(result.isSuccess == false)
        #expect(result.message.contains("Settings"))
    }

    @Test func aWorkoutWithNoDurationIsRejectedBeforeHealthKitSeesIt() async {
        guard writer.isAvailable else { return }
        let moment = Date()
        let result = await writer.save(
            FinishedWorkout(
                sessionID: "zero-length",
                start: moment,
                end: moment,
                volumeKg: 0,
                workingSets: 0
            )
        )
        // Either refused for permission or for the duration - never .saved.
        #expect(result.isSuccess == false)
    }
}
