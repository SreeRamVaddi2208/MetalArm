//
//  Notifications.swift
//  MetalARM
//
//  LOCAL notifications only: the rest timer finishing, and a reminder on a day
//  the streak would otherwise end. Server push (party events) needs an APNs key
//  from the Apple account - see docs/launch-checklist.md - so nothing here
//  talks to a server.
//
//  Two rules this follows:
//
//  - **Permission is asked after the first finished workout**, never at launch.
//    A prompt before the app has done anything for you is the fastest way to a
//    permanent "Don't Allow", and iOS only asks once.
//  - **Nothing is scheduled the user didn't ask for.** Both kinds have a toggle
//    in Profile, and a toggle turned off cancels what is already pending.
//

import Foundation
import UserNotifications

/// One pending local notification.
struct LocalNotification: Equatable, Sendable {
    var id: String
    var title: String
    var body: String
    /// Seconds from now. iOS requires this to be > 0.
    var after: TimeInterval
}

enum NotificationID {
    static let restDone = "rest-done"
    static let streakAtRisk = "streak-at-risk"
}

/// The seam. A unit-test host has no notification centre worth talking to, so
/// tests inject a spy and assert what WOULD be scheduled.
protocol NotificationScheduling: Sendable {
    /// True once the user has allowed notifications.
    func isAuthorized() async -> Bool
    /// Asks, and reports what the user chose. iOS only ever prompts once.
    func requestAuthorization() async -> Bool
    func schedule(_ notification: LocalNotification) async
    func cancel(_ ids: [String]) async
}

/// The real thing, over UNUserNotificationCenter.
struct SystemNotificationScheduler: NotificationScheduling {
    private var center: UNUserNotificationCenter { .current() }

    func isAuthorized() async -> Bool {
        let settings = await center.notificationSettings()
        return settings.authorizationStatus == .authorized
            || settings.authorizationStatus == .provisional
    }

    func requestAuthorization() async -> Bool {
        (try? await center.requestAuthorization(options: [.alert, .sound])) ?? false
    }

    func schedule(_ notification: LocalNotification) async {
        guard notification.after > 0 else { return }
        let content = UNMutableNotificationContent()
        content.title = notification.title
        content.body = notification.body
        content.sound = .default
        let request = UNNotificationRequest(
            identifier: notification.id,
            content: content,
            trigger: UNTimeIntervalNotificationTrigger(timeInterval: notification.after, repeats: false)
        )
        // Re-adding the same identifier replaces the pending one, which is
        // exactly what a restarted rest timer should do.
        try? await center.add(request)
    }

    func cancel(_ ids: [String]) async {
        center.removePendingNotificationRequests(withIdentifiers: ids)
    }
}

/// What the user asked for, remembered across launches.
struct NotificationSettings: Equatable, Sendable {
    var restAlerts: Bool = true
    var streakReminders: Bool = true
    /// Whether the permission prompt has already been shown, so a decline is
    /// not re-asked on every finished workout (iOS would ignore it anyway).
    var asked: Bool = false

    private enum Key {
        static let rest = "notifications.restAlerts"
        static let streak = "notifications.streakReminders"
        static let asked = "notifications.asked"
    }

    static func load(from defaults: UserDefaults = .standard) -> Self {
        Self(
            // Absent means "not chosen yet", and the default is on - the
            // toggles only matter once permission has been granted.
            restAlerts: defaults.object(forKey: Key.rest) as? Bool ?? true,
            streakReminders: defaults.object(forKey: Key.streak) as? Bool ?? true,
            asked: defaults.bool(forKey: Key.asked)
        )
    }

    func save(to defaults: UserDefaults = .standard) {
        defaults.set(restAlerts, forKey: Key.rest)
        defaults.set(streakReminders, forKey: Key.streak)
        defaults.set(asked, forKey: Key.asked)
    }
}

enum StreakReminder {
    /// When tonight's reminder should fire, in seconds from `now`, or nil when
    /// the hour has already passed today.
    static let hour = 19

    static func secondsUntilTonight(from now: Date, calendar: Calendar = .current) -> TimeInterval? {
        var components = calendar.dateComponents([.year, .month, .day], from: now)
        components.hour = hour
        components.minute = 0
        guard let fireAt = calendar.date(from: components), fireAt > now else { return nil }
        return fireAt.timeIntervalSince(now)
    }
}
