//
//  ExercisePickerView.swift
//  MetalARM
//
//  Searches the shared exercise library plus the user's own exercises.
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
                    HStack(spacing: 12) {
                        ExerciseDemo(exercise: exercise, size: 44, cornerRadius: 9, context: "pickerDemo")
                        VStack(alignment: .leading, spacing: 3) {
                            Text(exercise.name)
                                .font(Theme.body(15, .semibold))
                                .foregroundStyle(Theme.text)
                            Text("\(exercise.muscleLabel) · \(exercise.equipment.capitalized)")
                                .font(Theme.body(12))
                                .foregroundStyle(Theme.dim)
                        }
                    }
                }
                .accessibilityIdentifier("pickExercise-\(exercise.name)")
                .listRowBackground(Theme.card)
            }
            .overlay {
                if model.pickerResults.isEmpty && !query.trimmed.isEmpty && !model.isBusy {
                    ContentUnavailableView.search(text: query)
                }
            }
            .scrollContentBackground(.hidden)
            .background(Theme.bg)
            .searchable(text: $query, placement: .navigationBarDrawer(displayMode: .always), prompt: "Search exercises")
            .navigationTitle("Add Exercise")
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
