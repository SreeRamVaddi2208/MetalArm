//
//  WorkoutView.swift
//  MetalARM
//
//  Port of frontend/frontend/pages/workout.py.
//

import SwiftUI

struct WorkoutView: View {
    @Environment(AppModel.self) private var model

    var body: some View {
        Group {
            if model.sessionActive {
                activeSession
            } else {
                emptyState
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Theme.bg)
    }

    private var emptyState: some View {
        VStack(spacing: 16) {
            Image(systemName: "dumbbell.fill")
                .font(.system(size: 44))
                .foregroundStyle(Theme.fire)
            Text("No active workout")
                .font(Theme.display(22))
                .foregroundStyle(Theme.text)
            Text("Start a session to log sets, earn points and chase PRs.")
                .font(.system(size: 14))
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

    private var activeSession: some View {
        ScrollView {
            VStack(spacing: 16) {
                header
                if model.resting {
                    banner(icon: "timer", text: "Rest — \(model.restDisplay) until next set", tint: Theme.fire, textColor: Theme.text)
                        .accessibilityIdentifier("restBanner")
                }
                exerciseCard
                if !model.prHint.isEmpty {
                    banner(icon: "sparkles", text: model.prHint, tint: Theme.green, textColor: Theme.green)
                        .accessibilityIdentifier("prBanner")
                }
                ErrorText(message: model.errorMessage)
                Text("+ Add Exercise (coming soon)")
                    .font(Theme.display(13, .semibold))
                    .foregroundStyle(Theme.dim)
                    .frame(maxWidth: .infinity)
                    .padding(13)
                    .cardStyle(cornerRadius: 14)
                    .padding(.top, 8)
            }
            .padding(20)
        }
        .scrollDismissesKeyboard(.interactively)
    }

    private var header: some View {
        HStack {
            Color.clear.frame(width: 50, height: 1)
            Spacer()
            VStack(spacing: 0) {
                Text("SESSION")
                    .font(.system(size: 11))
                    .kerning(0.5)
                    .foregroundStyle(Theme.dim)
                Text("\(model.setsLogged.count) sets logged")
                    .font(Theme.display(15))
                    .foregroundStyle(Theme.text)
            }
            Spacer()
            Button("Finish") {
                Task { await model.finishWorkout() }
            }
            .font(Theme.display(13))
            .foregroundStyle(Theme.fire)
            .frame(width: 50, alignment: .trailing)
            .accessibilityIdentifier("finishButton")
        }
    }

    private var exerciseCard: some View {
        @Bindable var model = model
        return VStack(spacing: 8) {
            // Stacked so long muscle lists don't squeeze the exercise name onto two lines.
            VStack(alignment: .leading, spacing: 6) {
                Text(model.activeExercise?.name ?? "")
                    .font(Theme.display(18))
                    .foregroundStyle(Theme.text)
                Text(model.activeExerciseMuscleLabel)
                    .font(.system(size: 11))
                    .foregroundStyle(Theme.dim)
                    .padding(.horizontal, 9)
                    .padding(.vertical, 4)
                    .background(Theme.bg2, in: RoundedRectangle(cornerRadius: 8))
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            setColumns(
                columnLabel("SET"),
                columnLabel("WEIGHT (kg)"),
                columnLabel("REPS"),
                Color.clear.frame(height: 1)
            )
            .padding(.top, 8)
            ForEach(Array(model.setsLogged.enumerated()), id: \.element.id) { index, loggedSet in
                setColumns(
                    Text("\(index + 1)")
                        .font(Theme.display(13))
                        .foregroundStyle(Theme.dim),
                    valueBox(formatNumber(loggedSet.weightKg)),
                    valueBox("\(loggedSet.reps)"),
                    Image(systemName: loggedSet.isPr ? "checkmark.seal.fill" : "checkmark")
                        .foregroundStyle(loggedSet.isPr ? Theme.green : Theme.dim)
                )
            }
            setColumns(
                Text("\(model.setsLogged.count + 1)")
                    .font(Theme.display(13))
                    .foregroundStyle(Theme.fire),
                inputField("Weight", text: $model.weightInput, keyboard: .decimalPad)
                    .accessibilityIdentifier("weightField"),
                inputField("Reps", text: $model.repsInput, keyboard: .numberPad)
                    .accessibilityIdentifier("repsField"),
                Color.clear.frame(height: 1)
            )
            .padding(.vertical, 4)
            .background(Theme.fire.opacity(0.16), in: RoundedRectangle(cornerRadius: 10))
            Button {
                Task { await model.logCurrentSet() }
            } label: {
                Label("Log Set", systemImage: "plus")
                    .font(.system(size: 13, weight: .semibold))
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
            .font(.system(size: 11))
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

    private func inputField(_ placeholder: String, text: Binding<String>, keyboard: UIKeyboardType) -> some View {
        TextField(placeholder, text: text)
            .keyboardType(keyboard)
            .font(Theme.display(15, .semibold))
            .foregroundStyle(Theme.text)
            .padding(.horizontal, 12)
            .padding(.vertical, 10)
            .background(Theme.bg2, in: RoundedRectangle(cornerRadius: 10))
            .overlay(RoundedRectangle(cornerRadius: 10).stroke(Theme.fire))
    }

    private func banner(icon: String, text: String, tint: Color, textColor: Color) -> some View {
        HStack(spacing: 12) {
            Image(systemName: icon)
                .foregroundStyle(tint)
            Text(text)
                .font(.system(size: 13, weight: .semibold))
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
