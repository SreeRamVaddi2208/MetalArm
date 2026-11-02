//
//  SavedLibraryView.swift
//  MetalARM
//
//  The Library tab: what you have kept - your routines, your programs, and
//  the exercises you bookmarked.
//

import SwiftUI

struct SavedLibraryView: View {
    @Environment(AppModel.self) private var model
    /// Called once a saved routine has started, to switch to Workout.
    var onStarted: () -> Void = {}
    private static let parts = [("Routines", "routines"), ("Programs", "programs"), ("Saved", "favorites")]

    @State private var filter = "routines"
    @State private var items: [SavedItem]?
    @State private var open: SavedItem?
    @State private var plan: SavedItem?
    @State private var error = ""

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: Theme.Space.s16) {
                    ScreenTitle("Library")
                    HStack(spacing: Theme.Space.s8) {
                        ForEach(Self.parts, id: \.1) { part in
                            Button { filter = part.1 } label: {
                                Text(part.0).font(Theme.label)
                                    .foregroundStyle(filter == part.1 ? Theme.text : Theme.text2)
                                    .frame(maxWidth: .infinity, minHeight: Theme.touch)
                                    .background(filter == part.1 ? Theme.surface2 : .clear,
                                                in: RoundedRectangle(cornerRadius: Theme.radius))
                            }
                            .buttonStyle(.plain)
                            .accessibilityIdentifier("saved-\(part.1)")
                        }
                    }
                    if !error.isEmpty {
                        ErrorState(message: error) { Task { await load() } }
                    } else if let items {
                        if items.isEmpty {
                            EmptyState(systemImage: "bookmark", line: "Nothing here yet. Explore has plenty to keep.")
                        } else {
                            RowGroup {
                                ForEach(items) { row($0) }
                            }
                        }
                    } else {
                        Skeleton()
                    }
                }
                .screen()
            }
            .background(Theme.bg)
            .statusBarBackdrop()
            .task(id: filter) { await load() }
            .refreshable { await load() }
            .sheet(item: $open) { ExerciseSheet(id: $0.id, name: $0.title) }
            .sheet(item: $plan) { item in
                PlanSheet(item: item) {
                    plan = nil
                    onStarted()
                }
            }
        }
    }

    @ViewBuilder
    private func row(_ item: SavedItem) -> some View {
        if item.type == "exercise" {
            Button { open = item } label: {
                ListRow(title: item.title, subtitle: item.subtitle ?? "", chevron: true) {
                    FigureImage(path: item.image).frame(width: Theme.iconHit, height: Theme.iconHit)
                }
            }
            .buttonStyle(.plain)
            .accessibilityIdentifier("saved-item-\(item.title)")
        } else {
            Button { plan = item } label: {
                ListRow(title: item.title, subtitle: item.subtitle ?? "", chevron: true)
            }
            .buttonStyle(.plain)
            .accessibilityIdentifier("saved-item-\(item.title)")
        }
    }

    private func load() async {
        error = ""
        do {
            items = try await model.api.savedItems(filter: filter)
        } catch is CancellationError {
            return
        } catch {
            self.error = error.localizedDescription
        }
    }
}

/// A saved routine, with its exercises and Start; or a saved program, whose
/// routines each lead to the same.
private struct PlanSheet: View {
    @Environment(AppModel.self) private var model
    @Environment(\.dismiss) private var dismiss
    let item: SavedItem
    var onStarted: () -> Void

    @State private var program: ProgramDetail?
    @State private var routine: RoutineDetail?
    @State private var error = ""
    @State private var starting = false

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: Theme.Space.s16) {
                    if !error.isEmpty {
                        ErrorState(message: error) { Task { await load() } }
                    } else if let routine {
                        RowGroup {
                            ForEach(Array(routine.exercises.enumerated()), id: \.offset) { _, slot in
                                ListRow(title: slot.exercise.name, subtitle: slot.targetLabel) {
                                    ExerciseDemo(exercise: slot.exercise, size: Theme.iconHit, context: "planDemo")
                                }
                            }
                        }
                        Button("Start") { Task { await start(routine.id) } }
                            .buttonStyle(.plain)
                            .font(Theme.label).foregroundStyle(Theme.onAccent)
                            .frame(maxWidth: .infinity, minHeight: Theme.touch)
                            .background(Theme.accent, in: Capsule())
                            .disabled(starting)
                            .accessibilityIdentifier("planStartButton")
                    } else if let program {
                        RowGroup {
                            ForEach(program.routines) { entry in
                                Button { Task { await openRoutine(entry.id) } } label: {
                                    ListRow(title: entry.name, subtitle: plural(entry.exerciseCount, "exercise"), chevron: true)
                                }
                                .buttonStyle(.plain)
                                .accessibilityIdentifier("plan-routine-\(entry.name)")
                            }
                        }
                    } else {
                        Skeleton()
                    }
                }
                .screen()
            }
            .background(Theme.bg)
            .navigationTitle(routine?.name ?? item.title)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Done") { dismiss() } }
            }
            .task { await load() }
        }
        .preferredColorScheme(.dark)
    }

    private func load() async {
        error = ""
        do {
            if item.type == "routine" {
                routine = try await model.api.routine(id: item.id)
            } else {
                program = try await model.api.program(id: item.id)
            }
        } catch {
            self.error = error.localizedDescription
        }
    }

    private func openRoutine(_ id: String) async {
        do {
            routine = try await model.api.routine(id: id)
        } catch {
            self.error = error.localizedDescription
        }
    }

    private func start(_ id: String) async {
        starting = true
        defer { starting = false }
        if await model.startRoutine(id) {
            onStarted()
        } else {
            error = model.errorMessage
        }
    }
}
