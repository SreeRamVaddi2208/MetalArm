//
//  TrainingPathView.swift
//  MetalARM
//
//  "Which one's you?" - asked once, right after signing up, and reachable
//  again from Profile because training goals move.
//
//  The path is `users.character_class`: it decides which character stats are
//  highlighted AND which ready-made workout the app leads with. It never
//  touches points, XP or a leaderboard, so it is safe to change at any time.
//
//  The copy and the numbers come from GET /training-categories, so the three
//  cards are not hardcoded here; if that call fails the cards still render
//  from the paths the app knows by name.
//

import SwiftUI

struct TrainingPathView: View {
    @Environment(AppModel.self) private var model

    /// Onboarding shows Skip and a "you can change this later" line; Profile
    /// does not need either.
    var isOnboarding: Bool = true
    var onDone: () -> Void

    @State private var chosen: String?

    private var paths: [TrainingPath] {
        model.trainingPaths.isEmpty ? TrainingPath.fallbacks : model.trainingPaths
    }

    var body: some View {
        VStack(spacing: 0) {
            ScrollView {
                VStack(alignment: .leading, spacing: 18) {
                    VStack(alignment: .leading, spacing: 6) {
                        Text(isOnboarding ? "WHICH ONE'S YOU?" : "TRAINING PATH")
                            .font(Theme.body(11, .semibold))
                            .kerning(1)
                            .foregroundStyle(Theme.accent)
                        Text(isOnboarding ? "Pick how you train" : "How you train")
                            .font(Theme.display(28))
                            .foregroundStyle(Theme.text)
                        Text("It sets the weights, reps and workouts MetalArm suggests. It never changes your points or your rank.")
                            .font(Theme.body(13))
                            .foregroundStyle(Theme.dim)
                    }
                    .padding(.top, isOnboarding ? 28 : 8)

                    ForEach(paths) { path in
                        card(path)
                    }

                    ErrorText(message: model.errorMessage)
                }
                .padding(20)
            }

            VStack(spacing: 10) {
                Button {
                    Task {
                        guard let chosen else { return }
                        if await model.chooseTrainingPath(chosen) { onDone() }
                    }
                } label: {
                    Text(isOnboarding ? "Start training" : "Save")
                }
                .buttonStyle(PrimaryButtonStyle())
                .disabled(chosen == nil || model.isBusy)
                .opacity(chosen == nil ? 0.5 : 1)
                .accessibilityIdentifier("confirmPathButton")

                if isOnboarding {
                    Button("Not sure yet") {
                        // Recorded as asked-and-declined, so the question does
                        // not come back every launch.
                        Task {
                            await model.chooseTrainingPath("")
                            onDone()
                        }
                    }
                    .font(Theme.body(13, .semibold))
                    .foregroundStyle(Theme.dim)
                    .accessibilityIdentifier("skipPathButton")
                }
            }
            .padding(.horizontal, 24)
            .padding(.bottom, 24)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Theme.bg)
        .task {
            await model.loadTrainingPaths()
            chosen = model.me?.characterClass.flatMap { $0.isEmpty ? nil : $0 }
        }
    }

    private func card(_ path: TrainingPath) -> some View {
        let selected = chosen == path.category
        return Button {
            chosen = path.category
        } label: {
            HStack(alignment: .top, spacing: 14) {
                TrainingPathCharacter(category: path.category, height: 132)
                    .frame(width: 104)
                VStack(alignment: .leading, spacing: 5) {
                    Text(path.displayName)
                        .font(Theme.display(19))
                        .foregroundStyle(selected ? Theme.accent : Theme.text)
                    Text(path.tagline)
                        .font(Theme.body(12.5))
                        .foregroundStyle(Theme.dim)
                        .fixedSize(horizontal: false, vertical: true)
                    Text(path.summary)
                        .font(Theme.body(11, .semibold))
                        .foregroundStyle(Theme.silver)
                        .padding(.top, 2)
                }
                Spacer(minLength: 0)
            }
            .padding(14)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(selected ? Theme.accent.opacity(0.12) : Theme.card, in: RoundedRectangle(cornerRadius: 18))
            .overlay(
                RoundedRectangle(cornerRadius: 18)
                    .stroke(selected ? Theme.accent : Theme.cardBorder, lineWidth: selected ? 2 : 1))
            .shadow(color: Theme.accent.opacity(selected ? 0.22 : 0), radius: 18)
            .scaleEffect(selected ? 1.015 : 1)
            .animation(.spring(response: 0.3, dampingFraction: 0.75), value: selected)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .accessibilityIdentifier("path-\(path.category)")
        .accessibilityAddTraits(selected ? [.isSelected] : [])
    }
}

extension TrainingPath {
    /// Used only if /training-categories cannot be reached: the question must
    /// still be answerable offline, and the server is the source of truth the
    /// moment it replies.
    static let fallbacks: [TrainingPath] = [
        TrainingPath(
            category: "athlete", displayName: "Athletic",
            tagline: "Conditioning first. Lean and capable, not bulked.",
            description: "", repRangeLow: 12, repRangeHigh: 20, relativeLoad: "low",
            relativeVolume: "high", restSecondsGuidance: 60, emphasisTags: []),
        TrainingPath(
            category: "bodybuilder", displayName: "Bodybuilder",
            tagline: "Size and symmetry. Working sets close to failure.",
            description: "", repRangeLow: 8, repRangeHigh: 15, relativeLoad: "moderate_high",
            relativeVolume: "moderate_high", restSecondsGuidance: 90, emphasisTags: []),
        TrainingPath(
            category: "powerlifter", displayName: "Powerlifter",
            tagline: "Maximal strength. Heavy, low reps, long rests.",
            description: "", repRangeLow: 1, repRangeHigh: 6, relativeLoad: "heavy",
            relativeVolume: "low", restSecondsGuidance: 240, emphasisTags: []),
    ]
}
