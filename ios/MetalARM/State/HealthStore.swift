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
//  The important lesson in this file: `requestAuthorization` does NOT throw
//  when the user taps "Don't Allow". An earlier version returned true whenever
//  the call completed, so the toggle switched on after a refusal and every
//  write failed silently for ever. Authorization is judged by
//  `authorizationStatus(for:)` and nothing else.
//
//  Behind a protocol for the same reason as the notifier: a unit-test host has
//  no HealthKit store, so tests inject a spy and assert what WOULD be saved.
//

import Foundation
import HealthKit
import os

/// What a finished session looks like to Health.
struct FinishedWorkout: Equatable, Sendable {
    /// The MetalArm session id. Written as HKMetadataKeyExternalUUID so the
    /// same workout cannot land in Health twice.
    var sessionID: String
    var start: Date
    var end: Date
    var volumeKg: Double
    var workingSets: Int
}

/// Why a write didn't happen. Carried so the caller can log something useful
/// instead of staring at `false`.
enum HealthWriteResult: Equatable, Sendable {
    case saved
    case alreadySaved
    case unavailable
    case notAuthorized
    case failed(String)

    var isSuccess: Bool { self == .saved || self == .alreadySaved }

    /// Short, shown under the toggle in Profile. Empty when nothing is wrong.
    var message: String {
        switch self {
        case .saved, .alreadySaved: ""
        case .unavailable: "Health isn't available on this device."
        case .notAuthorized: "Health hasn't allowed workouts. Change it in Settings › Health › Data Access."
        case .failed(let reason): "Health couldn't save that workout: \(reason)"
        }
    }
}

protocol HealthWriting: Sendable {
    var isAvailable: Bool { get }
    /// The live permission state, so the toggle can follow what iOS actually
    /// thinks rather than what the app once recorded.
    var isAuthorized: Bool { get }
    /// Asks, then reports what the user ACTUALLY chose.
    func requestAuthorization() async -> Bool
    func save(_ workout: FinishedWorkout) async -> HealthWriteResult
}

struct AppleHealthWriter: HealthWriting {
    /// One store for the life of the app: HKHealthStore owns authorization
    /// state, and a fresh instance per call throws that away.
    private static let shared = HKHealthStore()
    private static let log = Logger(subsystem: "com.SreeRam.MetalARM", category: "health")

    private var store: HKHealthStore { Self.shared }
    private var workoutType: HKSampleType { HKObjectType.workoutType() }

    var isAvailable: Bool { HKHealthStore.isHealthDataAvailable() }

    var isAuthorized: Bool {
        guard isAvailable else { return false }
        return store.authorizationStatus(for: workoutType) == .sharingAuthorized
    }

    func requestAuthorization() async -> Bool {
        guard isAvailable else { return false }
        do {
            // `read: []` is deliberate - see the file comment.
            try await store.requestAuthorization(toShare: [workoutType], read: [])
        } catch {
            Self.log.error("Health authorization request failed: \(error.localizedDescription)")
            return false
        }
        // The request completing says nothing about the answer. This does.
        let granted = isAuthorized
        Self.log.info("Health authorization \(granted ? "granted" : "refused")")
        return granted
    }

    func save(_ workout: FinishedWorkout) async -> HealthWriteResult {
        guard isAvailable else { return .unavailable }
        guard isAuthorized else { return .notAuthorized }
        guard workout.end > workout.start else {
            return .failed("the session has no duration")
        }

        let configuration = HKWorkoutConfiguration()
        configuration.activityType = .traditionalStrengthTraining
        let builder = HKWorkoutBuilder(
            healthStore: store, configuration: configuration, device: .local()
        )
        do {
            try await builder.beginCollection(at: workout.start)
            try await builder.addMetadata([
                // What this key exists for: the writer's own id for the sample,
                // so a retry cannot create a duplicate workout.
                HKMetadataKeyExternalUUID: workout.sessionID,
                // Volume and sets are MetalArm's numbers; Health has no field
                // for them, so they ride along rather than being lost.
                "MetalArmVolumeKg": workout.volumeKg,
                "MetalArmWorkingSets": workout.workingSets,
            ])
            try await builder.endCollection(at: workout.end)
            _ = try await builder.finishWorkout()
            Self.log.info("Saved workout \(workout.sessionID, privacy: .public) to Health")
            return .saved
        } catch {
            Self.log.error("Health write failed: \(error.localizedDescription)")
            return .failed(error.localizedDescription)
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
    /// The last session written, so a repeated save is a no-op even before
    /// HealthKit's own de-duplication gets involved.
    var lastSavedSessionID = ""

    private enum Key {
        static let enabled = "health.enabled"
        static let asked = "health.asked"
        static let lastSaved = "health.lastSavedSessionID"
    }

    static func load(from defaults: UserDefaults = .standard) -> Self {
        Self(
            enabled: defaults.bool(forKey: Key.enabled),
            asked: defaults.bool(forKey: Key.asked),
            lastSavedSessionID: defaults.string(forKey: Key.lastSaved) ?? ""
        )
    }

    func save(to defaults: UserDefaults = .standard) {
        defaults.set(enabled, forKey: Key.enabled)
        defaults.set(asked, forKey: Key.asked)
        defaults.set(lastSavedSessionID, forKey: Key.lastSaved)
    }
}
