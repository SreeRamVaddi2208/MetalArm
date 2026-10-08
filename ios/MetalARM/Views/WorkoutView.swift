//
//  WorkoutView.swift
//  MetalARM
//
//  The Train tab. With nothing live: Start empty workout, and the way into
//  the Library. With a workout live: one exercise in focus - its logged sets
//  as calm rows, then weight and reps as steppers and Log set, the screen's
//  one accent action. Chips switch exercise; focus also moves on by itself
//  once an exercise has done its plan (AppModel.advanceFocus).
//
//  The session lives on the server, so leaving the tab (or the app) loses
//  nothing: it is rehydrated from /workouts/sessions/active.
//

import SwiftUI

struct WorkoutView: View {
    private enum InputField {
        case weight, reps
    }

    @Environment(AppModel.self) private var model
    var onOpenLibrary: () -> Void = {}
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
            Button("Discard workout", role: .destructive) {
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

    // MARK: Nothing live

    private var emptyState: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: Theme.Space.s24) {
                ScreenTitle("Train")
                Text("Start a workout to log sets, earn points and chase records. Your last numbers fill in for you.")
                    .font(Theme.body).foregroundStyle(Theme.text2)
                RowGroup {
                    Button(action: onOpenLibrary) {
                        ListRow(title: "Browse the Library", subtitle: "Programs and ready-made workouts for your path",
                                chevron: true) {
                            Image(systemName: "books.vertical").foregroundStyle(Theme.text2)
                        }
                    }
                    .buttonStyle(.plain)
                    .accessibilityIdentifier("trainToLibrary")
                }
                ErrorText(message: model.errorMessage)
            }
            .screen()
        }
        .pinnedPrimary {
            Button {
                Task { await model.startWorkout() }
            } label: {
                Label("Start empty workout", systemImage: "play.fill")
            }
            .buttonStyle(.primary)
            .accessibilityIdentifier("workoutStartButton")
        }
    }

    // MARK: A workout

    private func activeSession(_ session: WorkoutSession) -> some View {
        ScrollView {
            VStack(alignment: .leading, spacing: Theme.Space.s16) {
                header(session)
                if model.resting {
                    banner(icon: "timer", text: "Rest - \(model.restDisplay) until the next set", accent: true)
                        .accessibilityIdentifier("restBanner")
                }
                if !model.pendingSets.isEmpty {
                    banner(icon: "icloud.slash", text: model.syncStatusText)
                        .accessibilityIdentifier("offlineBanner")
                }
                if !model.progressionHint.isEmpty {
                    banner(icon: "arrow.up.circle", text: model.progressionHint)
                        .accessibilityIdentifier("progressionBanner")
                }
                if !model.prHint.isEmpty {
                    banner(icon: "medal", text: model.prHint, accent: true)
                        .accessibilityIdentifier("prBanner")
                }
                exerciseChips
                if let exercise = model.selectedExercise {
                    exerciseCard(exercise)
                } else {
                    EmptyState(systemImage: "list.bullet.rectangle",
                               line: "Add the first exercise - your last session's numbers fill in for you.") {
                        Button("Add exercise") { showingPicker = true }
                            .buttonStyle(MAButtonStyle(kind: .secondary, full: false))
                            .accessibilityIdentifier("addFirstExerciseButton")
                    }
                }
                ErrorText(message: model.errorMessage)
            }
            .screen()
        }
        .scrollDismissesKeyboard(.interactively)
        // Log set is the screen's one primary, always within thumb reach.
        .pinnedPrimary {
            if model.selectedExercise != nil {
                Button {
                    focusedField = nil
                    Task { await model.logSet() }
                } label: {
                    Label("Log set", systemImage: "checkmark")
                }
                .buttonStyle(.primary)
                .disabled(model.isBusy)
                .accessibilityIdentifier("logSetButton")
            }
        }
    }

    private func header(_ session: WorkoutSession) -> some View {
        HStack(spacing: Theme.Space.s8) {
            VStack(alignment: .leading, spacing: 0) {
                Text(session.name ?? "Workout").font(Theme.label).foregroundStyle(Theme.text).lineLimit(1)
                Text("\(model.setsLoggedCount) \(model.setsLoggedCount == 1 ? "set" : "sets") · \(session.pointsTotal) pts")
                    .font(Theme.caption).foregroundStyle(Theme.text2)
                    .accessibilityIdentifier("setsLoggedText")
            }
            Spacer()
            Menu {
                Button("Discard workout", systemImage: "trash", role: .destructive) { confirmingDiscard = true }
            } label: {
                Image(systemName: "ellipsis").foregroundStyle(Theme.text2)
                    .frame(width: Theme.iconHit, height: Theme.iconHit)
            }
            .accessibilityLabel("Workout options")
            Button("Finish") {
                focusedField = nil
                Task { await model.finishWorkout() }
            }
            .buttonStyle(.ghost)
            .disabled(model.isBusy)
            .accessibilityIdentifier("finishButton")
        }
    }

    private var exerciseChips: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: Theme.Space.s8) {
                ForEach(model.workoutExercises) { exercise in
                    Chip(label: exercise.name, selected: exercise.id == model.selectedExerciseID) {
                        model.select(exercise.id)
                    }
                }
                Chip(label: "+ Add") { showingPicker = true }
                    .accessibilityIdentifier("addExerciseButton")
            }
            .padding(.horizontal, Theme.gutter)
        }
        .padding(.horizontal, -Theme.gutter)
    }

    private func exerciseCard(_ exercise: Exercise) -> some View {
        @Bindable var model = model
        let unit = model.weightUnit
        let card = model.selectedSessionExercise
        let sets = card?.sets ?? []
        let previous = model.selectedPreviousSets
        let queued = model.queuedSets(for: exercise.id)
        return VStack(alignment: .leading, spacing: Theme.Space.s12) {
            HStack(alignment: .top, spacing: Theme.Space.s12) {
                VStack(alignment: .leading, spacing: Theme.Space.s4) {
                    Text(exercise.name).font(Theme.title).foregroundStyle(Theme.text)
                    Text(card?.supersetGroup.map { "Superset \($0) · \(exercise.muscleLabel)" } ?? exercise.muscleLabel)
                        .font(Theme.caption).foregroundStyle(Theme.text2)
                }
                Spacer(minLength: 0)
                ExerciseDemo(exercise: exercise, size: Theme.touch, cornerRadius: Theme.radius, context: "cardExerciseDemo")
            }
            if let hint = model.selectedHint {
                Text(hint.text).font(Theme.caption).foregroundStyle(Theme.text2)
                    .accessibilityIdentifier("progressionHint")
            }
            if !sets.isEmpty || !queued.isEmpty {
                VStack(spacing: 0) {
                    ForEach(sets) { logged in
                        doneRow(number: logged.isWarmup ? "W" : "\(logged.setNumber)",
                                line: "\(formatNumber(unit.fromKilograms(logged.weightKg))) \(unit.rawValue) × \(logged.reps ?? 0)",
                                pr: logged.isPr)
                    }
                    // Saved offline: shown in place, with a clock until they sync.
                    ForEach(Array(queued.enumerated()), id: \.element.id) { offset, queuedSet in
                        doneRow(number: "\(sets.count + offset + 1)",
                                line: "\(formatNumber(unit.fromKilograms(queuedSet.weightKg))) \(unit.rawValue) × \(queuedSet.reps)",
                                pending: true)
                            .accessibilityIdentifier("queuedSet")
                    }
                }
            }
            if !previous.isEmpty {
                Text("Last time · " + previous.prefix(4).map {
                    "\(formatNumber(unit.fromKilograms($0.weightKg))) × \($0.reps ?? 0)"
                }.joined(separator: ", "))
                .font(Theme.caption).foregroundStyle(Theme.text3)
                .accessibilityIdentifier("ghostValues")
            }
            Text("Set \(sets.count + queued.count + 1)").font(Theme.label).foregroundStyle(Theme.text2)
            stepper("Weight", unit: unit.rawValue, text: $model.weightInput, keyboard: .decimalPad, field: .weight,
                    minus: { model.bumpWeight(-1) }, plus: { model.bumpWeight(1) })
                .accessibilityElement(children: .contain)
                .accessibilityIdentifier("weightStepper")
            stepper("Reps", unit: "reps", text: $model.repsInput, keyboard: .numberPad, field: .reps,
                    minus: { model.bumpReps(-1) }, plus: { model.bumpReps(1) })
                .accessibilityElement(children: .contain)
                .accessibilityIdentifier("repsStepper")
        }
        .card()
    }

    private func doneRow(number: String, line: String, pr: Bool = false, pending: Bool = false) -> some View {
        HStack(spacing: Theme.Space.s12) {
            Text(number).font(Theme.label).foregroundStyle(Theme.text2).frame(width: Theme.Space.s24)
            Text(line).font(Theme.body).foregroundStyle(Theme.text2)
            Spacer()
            if pr { Pill(label: "PR") }
            Image(systemName: pending ? "clock.arrow.circlepath" : "checkmark")
                .foregroundStyle(pending ? Theme.text3 : Theme.accent)
                .accessibilityLabel(pending ? "Waiting to sync" : "Logged")
        }
        .frame(minHeight: Theme.touch)
    }

    private func stepper(_ label: String, unit: String, text: Binding<String>, keyboard: UIKeyboardType,
                         field: InputField, minus: @escaping () -> Void, plus: @escaping () -> Void) -> some View {
        VStack(alignment: .leading, spacing: Theme.Space.s4) {
            Text(label).font(Theme.caption).foregroundStyle(Theme.text2)
            HStack(spacing: Theme.Space.s8) {
                stepButton("minus", "Less \(label.lowercased())", minus)
                HStack(alignment: .firstTextBaseline, spacing: Theme.Space.s4) {
                    // Sized by the value, not the placeholder, so the unit
                    // sits right beside the number.
                    Text(text.wrappedValue.isEmpty ? "0" : text.wrappedValue)
                        .font(Theme.display)
                        .hidden()
                        .overlay {
                            TextField(label, text: text, prompt: Text("0").foregroundStyle(Theme.text3))
                                .keyboardType(keyboard)
                                .focused($focusedField, equals: field)
                                .font(Theme.display)
                                .foregroundStyle(Theme.text)
                                .multilineTextAlignment(.center)
                                .accessibilityIdentifier(field == .weight ? "weightField" : "repsField")
                        }
                    Text(unit).font(Theme.caption).foregroundStyle(Theme.text2)
                }
                .frame(maxWidth: .infinity)
                stepButton("plus", "More \(label.lowercased())", plus)
            }
        }
    }

    private func stepButton(_ systemName: String, _ label: String, _ action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Image(systemName: systemName).font(.system(.title3)).foregroundStyle(Theme.text)
                .frame(width: Theme.touch, height: Theme.touch)
                .background(Theme.surface2, in: Circle())
        }
        .buttonStyle(.plain)
        .accessibilityLabel(label)
    }

    private func banner(icon: String, text: String, accent: Bool = false) -> some View {
        HStack(spacing: Theme.Space.s12) {
            Image(systemName: icon).foregroundStyle(accent ? Theme.accent : Theme.text2)
            Text(text).font(Theme.label).foregroundStyle(Theme.text)
            Spacer()
        }
        .card(padding: Theme.Space.s12)
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
