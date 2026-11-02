//
//  ExercisePickerView.swift
//  MetalARM
//
//  Searches the shared exercise library plus the user's own exercises. From
//  Workout a tap adds the exercise.
//

import SwiftUI

struct ExercisePickerView: View {
    @Environment(AppModel.self) private var model
    @Environment(\.dismiss) private var dismiss
    @State private var query = ""

    var body: some View {
        NavigationStack {
            List(model.pickerResults) { exercise in
                Button {
                    Task {
                        await model.addExercise(exercise)
                        dismiss()
                    }
                } label: {
                    HStack(spacing: Theme.Space.s12) {
                        ExerciseDemo(exercise: exercise, size: Theme.iconHit, context: "pickerDemo")
                        VStack(alignment: .leading, spacing: 0) {
                            Text(exercise.name)
                                .font(Theme.body)
                                .foregroundStyle(Theme.text)
                            Text("\(exercise.muscleLabel) · \(exercise.equipment.capitalized)")
                                .font(Theme.caption)
                                .foregroundStyle(Theme.text2)
                        }
                    }
                }
                .accessibilityIdentifier("pickExercise-\(exercise.name)")
                .listRowBackground(Theme.surface)
            }
            .overlay {
                if model.pickerResults.isEmpty && !query.trimmed.isEmpty && !model.isBusy {
                    ContentUnavailableView.search(text: query)
                }
            }
            .scrollContentBackground(.hidden)
            .background(Theme.bg)
            .searchable(text: $query, placement: .navigationBarDrawer(displayMode: .always), prompt: "Search exercises")
            .navigationTitle("Add exercise")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
            }
            .task(id: query) {
                // Debounce typing: a newer query cancels this one.
                try? await Task.sleep(for: .milliseconds(250))
                guard !Task.isCancelled else { return }
                await model.searchExercises(query)
            }
        }
        .preferredColorScheme(.dark)
    }
}

#Preview {
    ExercisePickerView()
        .environment(AppModel(api: MockAPIClient()))
}
