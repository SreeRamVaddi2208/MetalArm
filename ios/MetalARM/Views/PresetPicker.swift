//
//  PresetPicker.swift
//  MetalARM
//
//  Three ready-made workouts - athletic, powerlifting, bodybuilding - offered
//  where a workout begins. Picking one opens its plan with a demo beside it, so
//  the movements are seen before anything is committed to; Start loads the
//  whole plan (GET /workouts/presets, POST /workouts/sessions {preset_slug}).
//

import SwiftUI

/// The three cards on the Workout tab's empty state.
struct PresetCards: View {
    @Environment(AppModel.self) private var model
    @Binding var chosen: WorkoutPreset?

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("OR START A READY-MADE WORKOUT")
                .font(Theme.body(11))
                .kerning(0.5)
                .foregroundStyle(Theme.dim)
            ForEach(model.presets) { preset in
                Button {
                    chosen = preset
                } label: {
                    HStack(spacing: 12) {
                        ExerciseDemo(exercise: preset.exercises[0].exercise, size: 56, cornerRadius: 10, context: "cardDemo")
                        VStack(alignment: .leading, spacing: 3) {
                            Text(preset.label.uppercased())
                                .font(Theme.body(10, .semibold))
                                .kerning(0.6)
                                .foregroundStyle(Theme.accent)
                            Text(preset.name)
                                .font(Theme.display(16))
                                .foregroundStyle(Theme.text)
                            Text(preset.lengthLabel)
                                .font(Theme.body(11))
                                .foregroundStyle(Theme.dim)
                        }
                        Spacer()
                        Image(systemName: "chevron.right")
                            .font(Theme.body(12, .semibold))
                            .foregroundStyle(Theme.faint)
                    }
                    .padding(12)
                    .frame(maxWidth: .infinity)
                    .cardStyle(cornerRadius: 14)
                    .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
                .accessibilityIdentifier("preset-\(preset.slug)")
            }
        }
        .task { await model.loadPresets() }
    }
}

/// The chosen workout: what it is, and what each movement looks like.
struct PresetSheet: View {
    @Environment(AppModel.self) private var model
    @Environment(\.dismiss) private var dismiss
    let preset: WorkoutPreset
    /// The movement the demo is showing; the first one until another is tapped.
    @State private var showing: PresetSlot?

    private var demoSlot: PresetSlot? { showing ?? preset.exercises.first }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    Text(preset.summary)
                        .font(Theme.body(13.5))
                        .foregroundStyle(Theme.dim)

                    if let demoSlot {
                        HStack(alignment: .top, spacing: 14) {
                            ExerciseDemo(exercise: demoSlot.exercise, size: 132, cornerRadius: 14, context: "presetDemo")
                            VStack(alignment: .leading, spacing: 4) {
                                Text(demoSlot.exercise.name)
                                    .font(Theme.display(17))
                                    .foregroundStyle(Theme.text)
                                Text(demoSlot.exercise.muscleLabel)
                                    .font(Theme.body(11))
                                    .foregroundStyle(Theme.dim)
                                Text(demoSlot.plan)
                                    .font(Theme.body(12, .semibold))
                                    .foregroundStyle(Theme.accent)
                                    .padding(.top, 2)
                                Text("Tap a movement below to see it.")
                                    .font(Theme.body(10.5))
                                    .foregroundStyle(Theme.faint)
                                    .padding(.top, 4)
                            }
                            Spacer(minLength: 0)
                        }
                        .padding(12)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        // No identifier on the card: it would override the
                        // demo's own, which is what says whether a clip is
                        // playing or the placeholder stands in.
                        .cardStyle(cornerRadius: 16)
                    }

                    VStack(spacing: 0) {
                        ForEach(Array(preset.exercises.enumerated()), id: \.element.id) { index, slot in
                            Button {
                                showing = slot
                            } label: {
                                HStack(spacing: 12) {
                                    Text("\(index + 1)")
                                        .font(Theme.display(13))
                                        .foregroundStyle(Theme.faint)
                                        .frame(width: 18, alignment: .leading)
                                    VStack(alignment: .leading, spacing: 2) {
                                        Text(slot.exercise.name)
                                            .font(Theme.body(14, .semibold))
                                            .foregroundStyle(demoSlot?.id == slot.id ? Theme.accent : Theme.text)
                                        Text(slot.plan)
                                            .font(Theme.body(11))
                                            .foregroundStyle(Theme.dim)
                                    }
                                    Spacer()
                                    if slot.exercise.mediaUrl != nil {
                                        Image(systemName: "play.circle")
                                            .font(Theme.body(15))
                                            .foregroundStyle(Theme.silver)
                                    }
                                }
                                .padding(.vertical, 11)
                                .padding(.horizontal, 14)
                                .contentShape(Rectangle())
                            }
                            .buttonStyle(.plain)
                            .accessibilityIdentifier("presetSlot-\(slot.exercise.name)")
                            if index < preset.exercises.count - 1 {
                                Rectangle()
                                    .fill(Theme.cardBorder)
                                    .frame(height: 1)
                                    .padding(.leading, 44)
                            }
                        }
                    }
                    .cardStyle(cornerRadius: 16)

                    Button {
                        Task {
                            await model.startWorkout(presetSlug: preset.slug)
                            dismiss()
                        }
                    } label: {
                        Text("Start this workout")
                    }
                    .buttonStyle(PrimaryButtonStyle())
                    .disabled(model.isBusy)
                    .accessibilityIdentifier("startPresetButton")

                    ErrorText(message: model.errorMessage)
                }
                .padding(20)
            }
            .background(Theme.bg)
            .navigationTitle("\(preset.label) · \(preset.name)")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
            }
        }
        .preferredColorScheme(.dark)
    }
}
