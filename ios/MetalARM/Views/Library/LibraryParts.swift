//
//  LibraryParts.swift
//  MetalARM
//
//  What the Library screens share: their routes, the path and filter
//  vocabulary (the same as the web app's state/library.py), and the pieces -
//  program cards, workout rows, path chips, the schedule grid.
//

import SwiftUI

enum LibraryRoute: Hashable {
    case path(String)
    case program(String)
    case workout(String)
}

enum LibraryVocabulary {
    static let paths: [(category: String, label: String)] = [
        ("athlete", "Athletic"), ("bodybuilder", "Bodybuilder"), ("powerlifter", "Powerlifter"),
    ]
    static let days = [2, 3, 4, 5, 6]
    static let difficulties = ["beginner", "intermediate", "advanced"]
    static let equipment = ["bodyweight", "dumbbell", "kettlebell", "barbell", "cable", "machine", "band"]
    static let durations = [30, 45, 60]
    static let note = "These are templates, not coaching. Adjust the load to your ability."

    private static let labels = ["ez_bar": "EZ bar", "trap_bar": "Trap bar", "cardio_machine": "Cardio machine"]

    /// "ez_bar" -> "EZ bar", "dumbbell" -> "Dumbbell".
    static func label(_ code: String) -> String {
        if let known = labels[code] { return known }
        let words = code.replacingOccurrences(of: "_", with: " ")
        return words.prefix(1).uppercased() + words.dropFirst()
    }

    static func pathLabel(_ category: String) -> String {
        paths.first { $0.category == category }?.label ?? label(category)
    }
}

/// "1 program", "3 programs".
func plural(_ count: Int, _ noun: String) -> String {
    "\(count) \(noun)\(count == 1 ? "" : "s")"
}

extension LibraryWorkoutCard {
    /// "45 min · 6 exercises"
    var meta: String { "\(durationMinutes) min · \(plural(exerciseCount, "exercise"))" }
    /// The first three pieces of kit, then "+".
    var gear: String {
        equipment.prefix(3).map(LibraryVocabulary.label).joined(separator: ", ") + (equipment.count > 3 ? " +" : "")
    }
}

extension Enrollment {
    var whereLabel: String { "Week \(currentWeek) · Day \(currentDay)" }
}

/// Name, one line of description, weeks · days · level. A program for the
/// user's path carries a quiet "For your path" pill.
struct ProgramCard: View {
    let program: LibraryProgramCard
    var showPill = true

    var body: some View {
        NavigationLink(value: LibraryRoute.program(program.slug)) {
            VStack(alignment: .leading, spacing: Theme.Space.s8) {
                if (showPill && program.recommended) || program.following == true {
                    HStack(spacing: Theme.Space.s8) {
                        if showPill && program.recommended { Pill(label: "For your path") }
                        if program.following == true { Pill(label: "Following", accent: false) }
                    }
                }
                Text(program.name).font(Theme.title).foregroundStyle(Theme.text)
                    .lineLimit(2).multilineTextAlignment(.leading)
                if let description = program.description, !description.isEmpty {
                    Text(description).font(Theme.body).foregroundStyle(Theme.text2).lineLimit(1)
                }
                Text(program.meta).font(Theme.caption).foregroundStyle(Theme.text2)
            }
            .card()
        }
        .buttonStyle(.plain)
        .accessibilityIdentifier("library-program-\(program.slug)")
    }
}

/// A list row: name, then duration · exercises · equipment.
struct WorkoutRow: View {
    let workout: LibraryWorkoutCard

    var body: some View {
        NavigationLink(value: LibraryRoute.workout(workout.slug)) {
            ListRow(title: workout.name, subtitle: "\(workout.meta) · \(workout.gear)", chevron: true)
        }
        .buttonStyle(.plain)
        .accessibilityIdentifier("library-workout-\(workout.slug)")
    }
}

/// The three paths; the user's own is marked with a dot.
struct PathChips: View {
    let selected: String
    let own: String
    let onSelect: (String) -> Void

    var body: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: Theme.Space.s8) {
                ForEach(LibraryVocabulary.paths, id: \.category) { path in
                    Chip(label: path.label, selected: path.category == selected, dot: path.category == own) {
                        onSelect(path.category)
                    }
                    .accessibilityIdentifier("path-chip-\(path.category)")
                }
            }
            .padding(.horizontal, Theme.gutter)
        }
        .padding(.horizontal, -Theme.gutter)
    }
}

/// Weeks as rows, days 1-7 as cells. A workout day shows its name and opens
/// it; a rest day is a muted outline. Scrolls sideways in its own row.
struct ScheduleGrid: View {
    let weeks: [ScheduleWeek]

    private let cellWidth: CGFloat = 76
    private let weekWidth: CGFloat = 40

    var body: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            VStack(alignment: .leading, spacing: Theme.Space.s4) {
                HStack(spacing: Theme.Space.s4) {
                    Color.clear.frame(width: weekWidth, height: 1)
                    ForEach(1...7, id: \.self) { day in
                        Text("Day \(day)").font(Theme.caption).foregroundStyle(Theme.text2).frame(width: cellWidth)
                    }
                }
                ForEach(weeks) { week in
                    HStack(spacing: Theme.Space.s4) {
                        Text("W\(week.week)").font(Theme.caption).foregroundStyle(Theme.text2).frame(width: weekWidth)
                        ForEach(week.days, id: \.day) { cell($0, week: week.week) }
                    }
                }
            }
            .padding(.horizontal, Theme.gutter)
        }
        .padding(.horizontal, -Theme.gutter)
        .accessibilityElement(children: .contain)
        .accessibilityLabel("Program schedule")
    }

    @ViewBuilder
    private func cell(_ day: ScheduleDay, week: Int) -> some View {
        let shape = RoundedRectangle(cornerRadius: Theme.radius)
        if let slug = day.workoutSlug {
            NavigationLink(value: LibraryRoute.workout(slug)) {
                Text(day.workoutName ?? "Workout").font(Theme.caption).foregroundStyle(Theme.text)
                    .lineLimit(2).multilineTextAlignment(.center)
                    .padding(.horizontal, Theme.Space.s4)
                    .frame(width: cellWidth, height: Theme.touch)
                    .background(Theme.surface2, in: shape)
            }
            .buttonStyle(.plain)
            .accessibilityLabel("Week \(week), day \(day.day): \(day.workoutName ?? "workout")")
        } else {
            Text("Rest").font(Theme.caption).foregroundStyle(Theme.text3)
                .frame(width: cellWidth, height: Theme.touch)
                .overlay { shape.stroke(Theme.border) }
                .accessibilityLabel("Week \(week), day \(day.day): rest")
        }
    }
}

extension View {
    /// Pushes the Library's detail screens. Registered once, on the tab's root.
    func libraryDestinations(onStarted: @escaping () -> Void) -> some View {
        navigationDestination(for: LibraryRoute.self) { route in
            switch route {
            case .path(let category): LibraryPathView(category: category)
            case .program(let slug): LibraryProgramView(slug: slug, onStarted: onStarted)
            case .workout(let slug): LibraryWorkoutView(slug: slug, onStarted: onStarted)
            }
        }
    }
}
