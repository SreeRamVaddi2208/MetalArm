//
//  HealthStore.swift
//  MetalARM
//
//  Finished workouts written to Apple Health.
//
//  WRITE ONLY. MetalArm asks to ADD workouts and never to read anything, which
//  is the smallest ask that still puts a session in the Fitness app - and the
//  one that is easy to justify in App Review. Nothing is written until the user
//  turns it on in Profile.
//
//  Behind a protocol for the same reason as the notifier: a unit-test host has
//  no HealthKit store, so tests inject a spy and assert what WOULD be saved.
//

import Foundation
import HealthKit

/// What a finished session looks like to Health.
struct FinishedWorkout: Equatable, Sendable {
    var start: Date
    var end: Date
    var volumeKg: Double
    var workingSets: Int
}

protocol HealthWriting: Sendable {
    var isAvailable: Bool { get }
    func requestAuthorization() async -> Bool
    func save(_ workout: FinishedWorkout) async -> Bool
}

struct AppleHealthWriter: HealthWriting {
    private var store: HKHealthStore { HKHealthStore() }

    var isAvailable: Bool { HKHealthStore.isHealthDataAvailable() }

    func requestAuthorization() async -> Bool {
        guard isAvailable else { return false }
        // `read: []` is deliberate - see the file comment.
        do {
            try await store.requestAuthorization(toShare: [HKObjectType.workoutType()], read: [])
            return true
        } catch {
            return false
        }
    }

    func save(_ workout: FinishedWorkout) async -> Bool {
        guard isAvailable, workout.end > workout.start else { return false }
        let configuration = HKWorkoutConfiguration()
        configuration.activityType = .traditionalStrengthTraining
        let builder = HKWorkoutBuilder(
            healthStore: store, configuration: configuration, device: .local()
        )
        do {
            try await builder.beginCollection(at: workout.start)
            // Volume and sets are MetalArm's own numbers; Health has no field
            // for them, so they ride along as metadata rather than being lost.
            try await builder.addMetadata([
                "MetalArmVolumeKg": workout.volumeKg,
                "MetalArmWorkingSets": workout.workingSets,
            ])
            try await builder.endCollection(at: workout.end)
            _ = try await builder.finishWorkout()
            return true
        } catch {
            return false
        }
    }
}

/// Whether the user asked for their workouts to land in Health. Off until
/// asked for: an integration that starts writing on its own is a surprise.
struct HealthSettings: Equatable, Sendable {
    var enabled = false
    /// Whether the HealthKit permission sheet has already been shown. iOS only
    /// shows it once per type, so re-asking achieves nothing.
    var asked = false

    private enum Key {
        static let enabled = "health.enabled"
        static let asked = "health.asked"
    }

    static func load(from defaults: UserDefaults = .standard) -> Self {
        Self(
            enabled: defaults.bool(forKey: Key.enabled),
            asked: defaults.bool(forKey: Key.asked)
        )
    }

    func save(to defaults: UserDefaults = .standard) {
        defaults.set(enabled, forKey: Key.enabled)
        defaults.set(asked, forKey: Key.asked)
    }
}
