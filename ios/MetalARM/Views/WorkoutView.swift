//
//  WorkoutView.swift
//  MetalARM
//
//  The live workout. The session lives on the server, so leaving the tab (or
//  the app) loses nothing: it is rehydrated from /workouts/sessions/active.
//

import SwiftUI

struct WorkoutView: View {
    private enum InputField {
        case weight, reps
    }

    @Environment(AppModel.self) private var model
    @State private var showingPicker = false
    @State private var confirmingDiscard = false
    @FocusState private var focusedField: InputField?

    var body: some View {
        Group {
            if let session = model.session {
                activeSession(session)
            } else {
                emptyState
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Theme.bg)
        .task { await model.loadWorkout() }
        .sheet(isPresented: $showingPicker) { ExercisePickerView() }
        .confirmationDialog("Discard this workout?", isPresented: $confirmingDiscard, titleVisibility: .visible) {
            Button("Discard Workout", role: .destructive) {
                Task { await model.abandonWorkout() }
            }
        } message: {
            Text("Points from its sets are taken back.")
        }
        .toolbar {
            // Number pads have no return key.
            ToolbarItemGroup(placement: .keyboard) {
                Spacer()
                Button("Done") { focusedField = nil }
                    .accessibilityIdentifier("keyboardDoneButton")
            }
        }
    }

    private var emptyState: some View {
        VStack(spacing: 16) {
            Image(systemName: "dumbbell.fill")
                .font(Theme.body(44))
                .foregroundStyle(Theme.accent)
            Text("No active workout")
                .font(Theme.display(22))
                .foregroundStyle(Theme.text)
            Text("Start a session to log sets, earn points and chase PRs.")
                .font(Theme.body(14))
                .foregroundStyle(Theme.dim)
                .multilineTextAlignment(.center)
            Button {
                Task { await model.startWorkout() }
            } label: {
                Label("Start Workout", systemImage: "plus")
            }
            .buttonStyle(PrimaryButtonStyle())
            .accessibilityIdentifier("workoutStartButton")
            ErrorText(message: model.errorMessage)
        }
        .padding(24)
    }

    private func activeSession(_ session: WorkoutSession) -> some View {
        ScrollView {
            VStack(spacing: 16) {
                header(session)
                if model.resting {
                    banner(icon: "timer", text: "Rest — \(model.restDisplay) until next set", tint: Theme.accent, textColor: Theme.text)
                        .accessibilityIdentifier("restBanner")
                }
                if !model.pendingSets.isEmpty {
                    banner(icon: "icloud.slash", text: model.syncStatusText, tint: Theme.silver, textColor: Theme.text)
                        .accessibilityIdentifier("offlineBanner")
                }
                if !model.progressionHint.isEmpty {
                    banner(icon: "arrow.up.circle.fill", text: model.progressionHint, tint: Theme.silver, textColor: Theme.text)
                        .accessibilityIdentifier("progressionBanner")
                }
                if !model.prHint.isEmpty {
                    banner(icon: "sparkles", text: model.prHint, tint: Theme.success, textColor: Theme.success)
                        .accessibilityIdentifier("prBanner")
                }
                exerciseChips
                if let exercise = model.selectedExercise {
                    exerciseCard(exercise)
                } else {
                    addFirstPrompt
                }
                ErrorText(message: model.errorMessage)
            }
            .padding(20)
        }
        .scrollDismissesKeyboard(.interactively)
    }

    private func header(_ session: WorkoutSession) -> some View {
        HStack {
            Menu {
                Button("Discard Workout", systemImage: "trash", role: .destructive) { confirmingDiscard = true }
            } label: {
                Image(systemName: "ellipsis.circle")
                    .font(Theme.body(20))
                    .foregroundStyle(Theme.dim)
            }
            .frame(width: 60, alignment: .leading)
            .accessibilityLabel("Workout options")
            Spacer()
            VStack(spacing: 0) {
                Text("SESSION")
                    .font(Theme.body(11))
                    .kerning(0.5)
                    .foregroundStyle(Theme.dim)
                Text("\(model.setsLoggedCount) \(model.setsLoggedCount == 1 ? "set" : "sets") logged")
                    .font(Theme.display(15))
                    .foregroundStyle(Theme.text)
                Text("\(session.pointsTotal) pts")
                    .font(Theme.body(12, .semibold))
                    .foregroundStyle(Theme.accent)
            }
            Spacer()
            Button("Finish") {
                focusedField = nil
                Task { await model.finishWorkout() }
            }
            .font(Theme.display(14))
            .foregroundStyle(Theme.accent)
            .frame(width: 60, alignment: .trailing)
            .disabled(model.isBusy)
            .accessibilityIdentifier("finishButton")
        }
    }

    private var exerciseChips: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 8) {
                ForEach(model.workoutExercises) { exercise in
                    let active = exercise.id == model.selectedExerciseID
                    Button {
                        model.select(exercise.id)
                    } label: {
                        Text(exercise.name)
                            .font(Theme.display(12.5, active ? .bold : .semibold))
                            .foregroundStyle(active ? Theme.bg : Theme.dim)
                            .padding(.horizontal, 14)
                            .padding(.vertical, 8)
                            .background(active ? Theme.accent : Theme.card, in: Capsule())
                            .overlay(Capsule().stroke(active ? Color.clear : Theme.cardBorder))
                    }
                    .buttonStyle(.plain)
                }
                Button {
                    showingPicker = true
                } label: {
                    Label("Add", systemImage: "plus")
                        .font(Theme.body(12.5, .semibold))
                        .foregroundStyle(Theme.accent)
                        .padding(.horizontal, 14)
                        .padding(.vertical, 8)
                        .overlay(Capsule().strokeBorder(Theme.accent.opacity(0.5), style: StrokeStyle(lineWidth: 1, dash: [4])))
                }
                .buttonStyle(.plain)
                .accessibilityIdentifier("addExerciseButton")
            }
        }
    }

    private var addFirstPrompt: some View {
        VStack(spacing: 12) {
            Image(systemName: "list.bullet.rectangle")
                .font(Theme.body(30))
                .foregroundStyle(Theme.dim)
            Text("Add your first exercise")
                .font(Theme.display(17))
                .foregroundStyle(Theme.text)
            Text("Pick from the library - your last session's numbers fill in for you.")
                .font(Theme.body(13))
                .foregroundStyle(Theme.dim)
                .multilineTextAlignment(.center)
            Button {
                showingPicker = true
            } label: {
                Label("Add Exercise", systemImage: "plus")
            }
            .buttonStyle(PrimaryButtonStyle())
            .accessibilityIdentifier("addFirstExerciseButton")
        }
        .padding(20)
        .frame(maxWidth: .infinity)
        .cardStyle(cornerRadius: 18)
    }

    private func exerciseCard(_ exercise: Exercise) -> some View {
        @Bindable var model = model
        let unit = model.weightUnit
        let sets = model.selectedSessionExercise?.sets ?? []
        let previous = model.selectedPreviousSets
        return VStack(alignment: .leading, spacing: 8) {
            Text(exercise.name)
                .font(Theme.display(18))
                .foregroundStyle(Theme.text)
            Text(exercise.muscleLabel)
                .font(Theme.body(11))
                .foregroundStyle(Theme.dim)
                .padding(.horizontal, 9)
                .padding(.vertical, 4)
                .background(Theme.bg2, in: RoundedRectangle(cornerRadius: 8))
            if !previous.isEmpty {
                Text("Last time: " + previous.prefix(4).map { "\(formatNumber(unit.fromKilograms($0.weightKg))) × \($0.reps ?? 0)" }.joined(separator: ", "))
                    .font(Theme.body(12))
                    .foregroundStyle(Theme.dim)
                    .accessibilityIdentifier("ghostValues")
            }
            if let hint = model.selectedHint {
                Label(hint.text, systemImage: hint.kind == "progress" ? "arrow.up.right" : "arrow.triangle.2.circlepath")
                    .font(Theme.body(12, .semibold))
                    .foregroundStyle(hint.kind == "progress" ? Theme.accent : Theme.silver)
                    .accessibilityIdentifier("progressionHint")
            }
            setColumns(
                columnLabel("SET"),
                columnLabel("WEIGHT (\(unit.rawValue))"),
                columnLabel("REPS"),
                Color.clear.frame(height: 1)
            )
            .padding(.top, 6)
            ForEach(sets) { loggedSet in
                setColumns(
                    Text("\(loggedSet.setNumber)")
                        .font(Theme.display(13))
                        .foregroundStyle(Theme.dim),
                    valueBox(formatNumber(unit.fromKilograms(loggedSet.weightKg))),
                    valueBox(loggedSet.reps.map(String.init) ?? "–"),
                    Image(systemName: loggedSet.isPr ? "checkmark.seal.fill" : "checkmark")
                        .foregroundStyle(loggedSet.isPr ? Theme.success : Theme.dim)
                )
            }
            // Saved offline: shown in place, with a clock until they sync.
            let queued = model.queuedSets(for: exercise.id)
            ForEach(Array(queued.enumerated()), id: \.element.id) { offset, queuedSet in
                setColumns(
                    Text("\(sets.count + offset + 1)")
                        .font(Theme.display(13))
                        .foregroundStyle(Theme.dim),
                    valueBox(formatNumber(unit.fromKilograms(queuedSet.weightKg))),
                    valueBox(String(queuedSet.reps)),
                    Image(systemName: "clock.arrow.circlepath")
                        .foregroundStyle(Theme.faint)
                        .accessibilityLabel("Waiting to sync")
                )
                .accessibilityIdentifier("queuedSet")
            }
            setColumns(
                Text("\(sets.count + queued.count + 1)")
                    .font(Theme.display(13))
                    .foregroundStyle(Theme.accent),
                inputField("Weight", text: $model.weightInput, keyboard: .decimalPad, field: .weight)
                    .accessibilityIdentifier("weightField"),
                inputField("Reps", text: $model.repsInput, keyboard: .numberPad, field: .reps)
                    .accessibilityIdentifier("repsField"),
                Color.clear.frame(height: 1)
            )
            .padding(.vertical, 4)
            .background(Theme.accent.opacity(0.16), in: RoundedRectangle(cornerRadius: 10))
            Button {
                focusedField = nil
                Task { await model.logSet() }
            } label: {
                Label("Log Set", systemImage: "plus")
                    .font(Theme.body(13, .semibold))
                    .frame(maxWidth: .infinity)
                    .padding(11)
                    .contentShape(Rectangle())
            }
            .buttonStyle(.plain)
            .foregroundStyle(Theme.dim)
            .overlay(
                RoundedRectangle(cornerRadius: 12)
                    .strokeBorder(Theme.cardBorder, style: StrokeStyle(lineWidth: 1, dash: [4]))
            )
            .disabled(model.isBusy)
            .accessibilityIdentifier("logSetButton")
            .padding(.top, 6)
        }
        .padding(.horizontal, 18)
        .padding(.vertical, 16)
        .cardStyle(cornerRadius: 18)
    }

    private func setColumns(_ number: some View, _ weight: some View, _ reps: some View, _ status: some View) -> some View {
        HStack(spacing: 10) {
            number.frame(width: 32)
            weight.frame(maxWidth: .infinity, alignment: .leading)
            reps.frame(maxWidth: .infinity, alignment: .leading)
            status.frame(width: 32)
        }
    }

    private func columnLabel(_ text: String) -> some View {
        Text(text)
            .font(Theme.body(11))
            .foregroundStyle(Theme.faint)
    }

    private func valueBox(_ text: String) -> some View {
        Text(text)
            .font(Theme.display(15, .semibold))
            .foregroundStyle(Theme.text)
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(.horizontal, 12)
            .padding(.vertical, 10)
            .background(Theme.bg2, in: RoundedRectangle(cornerRadius: 10))
    }

    private func inputField(_ placeholder: String, text: Binding<String>, keyboard: UIKeyboardType, field: InputField) -> some View {
        TextField(placeholder, text: text)
            .keyboardType(keyboard)
            .focused($focusedField, equals: field)
            .font(Theme.display(15, .semibold))
            .foregroundStyle(Theme.text)
            .padding(.horizontal, 12)
            .padding(.vertical, 10)
            .background(Theme.bg2, in: RoundedRectangle(cornerRadius: 10))
            .overlay(RoundedRectangle(cornerRadius: 10).stroke(Theme.accent))
    }

    private func banner(icon: String, text: String, tint: Color, textColor: Color) -> some View {
        HStack(spacing: 12) {
            Image(systemName: icon)
                .foregroundStyle(tint)
            Text(text)
                .font(Theme.body(13, .semibold))
                .foregroundStyle(textColor)
            Spacer()
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 12)
        .background(tint.opacity(0.16), in: RoundedRectangle(cornerRadius: 14))
        .overlay(RoundedRectangle(cornerRadius: 14).stroke(tint.opacity(0.3)))
        .accessibilityElement(children: .combine)
    }
}

#Preview {
    let model = AppModel(api: MockAPIClient())
    WorkoutView()
        .environment(model)
        .preferredColorScheme(.dark)
        .task { await model.startWorkout() }
}
