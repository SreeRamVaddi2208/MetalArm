//
//  LibraryWorkoutView.swift
//  MetalARM
//
//  A workout: its exercises with targets ("4 × 8–12 · 90s rest" - never a
//  weight), Save to routines, and Start workout pinned low.
//

import SwiftUI

struct LibraryWorkoutView: View {
    @Environment(AppModel.self) private var model
    let slug: String
    var onStarted: () -> Void = {}

    @State private var saved = false

    private var workout: LibraryWorkout? { model.libraryWorkout?.slug == slug ? model.libraryWorkout : nil }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: Theme.Space.s24) {
                if let workout {
                    content(workout)
                } else if model.errorMessage.isEmpty {
                    VStack(spacing: Theme.Space.s12) {
                        Skeleton(height: 96)
                        Skeleton()
                        Skeleton()
                        Skeleton()
                    }
                }
                ErrorText(message: model.errorMessage)
            }
            .screen()
        }
        .background(Theme.bg)
        .navigationBarTitleDisplayMode(.inline)
        .task {
            model.libraryNotice = ""
            await model.loadLibraryWorkout(slug)
            saved = workout?.routineId != nil
        }
        .pinnedPrimary {
            if workout != nil {
                Button {
                    Task { if await model.startLibraryWorkout(slug) { onStarted() } }
                } label: {
                    Label(model.isBusy ? "Starting…" : "Start workout", systemImage: "play.fill")
                }
                .buttonStyle(.primary)
                .disabled(model.isBusy)
                .accessibilityIdentifier("libraryStartButton")
            }
        }
    }

    @ViewBuilder
    private func content(_ workout: LibraryWorkout) -> some View {
        VStack(alignment: .leading, spacing: Theme.Space.s8) {
            Text(workout.name).font(Theme.titleLG).foregroundStyle(Theme.text)
                .accessibilityAddTraits(.isHeader)
            Pill(label: workout.categoryLabel, accent: false)
        }
        HStack(spacing: Theme.Space.s16) {
            StatTile(value: "\(workout.durationMinutes)", label: "Minutes")
            StatTile(value: "\(workout.exerciseCount)", label: "Exercises")
        }
        Text(workout.equipment.map(LibraryVocabulary.label).joined(separator: ", "))
            .font(Theme.caption).foregroundStyle(Theme.text2)
        if let description = workout.description, !description.isEmpty {
            Text(description).font(Theme.body).foregroundStyle(Theme.text2)
        }
        RowGroup {
            ForEach(workout.exercises) { row($0) }
        }
        if !model.libraryNotice.isEmpty {
            Text(model.libraryNotice).font(Theme.caption).foregroundStyle(Theme.text2)
                .accessibilityIdentifier("libraryNotice")
        }
        Button {
            Task {
                await model.saveLibraryWorkout(slug)
                if !model.libraryNotice.isEmpty { saved = true }
            }
        } label: {
            Label(saved ? "In your routines" : "Save to routines", systemImage: "bookmark")
        }
        .buttonStyle(.secondary)
        .disabled(saved || model.isBusy)
        .accessibilityIdentifier("saveRoutineButton")
    }

    private func row(_ slot: LibraryWorkoutExercise) -> some View {
        let muscle = slot.exercise.primaryMuscleGroups.first.map(LibraryVocabulary.label) ?? ""
        let superset = slot.supersetGroup > 0 ? "Superset \(slot.supersetGroup) · " : ""
        return VStack(alignment: .leading, spacing: 0) {
            ListRow(title: slot.exercise.name,
                    subtitle: [muscle, superset + slot.target].filter { !$0.isEmpty }.joined(separator: " · ")) {
                ExerciseDemo(exercise: slot.exercise, size: Theme.iconHit, cornerRadius: Theme.radius,
                             context: "libraryExerciseDemo")
            }
            if let note = slot.note, !note.isEmpty {
                Text(note).font(Theme.caption).foregroundStyle(Theme.text3).padding(.bottom, Theme.Space.s8)
            }
        }
        .accessibilityElement(children: .combine)
        .accessibilityIdentifier("library-exercise-\(slot.position)")
    }
}
