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
                VStack(alignment: .leading, spacing: Theme.Space.s16) {
                    VStack(alignment: .leading, spacing: Theme.Space.s8) {
                        Text(isOnboarding ? "Pick how you train" : "How you train")
                            .font(Theme.titleLG)
                            .foregroundStyle(Theme.text)
                        Text("It shapes the workouts and programs MetalArm leads with. It never changes your points or your rank.")
                            .font(Theme.body)
                            .foregroundStyle(Theme.text2)
                    }
                    .padding(.top, isOnboarding ? Theme.Space.s32 : Theme.Space.s8)

                    ForEach(paths) { path in
                        card(path)
                    }

                    ErrorText(message: model.errorMessage)
                }
                .screen()
            }

            VStack(spacing: Theme.Space.s8) {
                Button {
                    Task {
                        guard let chosen else { return }
                        if await model.chooseTrainingPath(chosen) { onDone() }
                    }
                } label: {
                    Text(isOnboarding ? "Start training" : "Save")
                }
                .buttonStyle(.primary)
                .disabled(chosen == nil || model.isBusy)
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
                    .buttonStyle(MAButtonStyle(kind: .ghost))
                    .accessibilityIdentifier("skipPathButton")
                }
            }
            .padding(.horizontal, Theme.gutter)
            .padding(.bottom, Theme.Space.s16)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Theme.bg)
        .task {
            // Seed from the saved path FIRST, and never over a tap: the cards
            // render from the fallbacks straight away, so a path can be chosen
            // while /training-categories is still in flight - assigning after
            // the await would throw that choice away and re-disable Save.
            if chosen == nil {
                chosen = model.me?.characterClass.flatMap { $0.isEmpty ? nil : $0 }
            }
            await model.loadTrainingPaths()
        }
    }

    private func card(_ path: TrainingPath) -> some View {
        let selected = chosen == path.category
        return Button {
            chosen = path.category
        } label: {
            // Selected: a 2 pt accent outline on accent-soft, and a check.
            // No glow - the same card the web app uses.
            HStack(alignment: .top, spacing: Theme.Space.s12) {
                TrainingPathCharacter(category: path.category, height: 132)
                    .frame(width: 104)
                VStack(alignment: .leading, spacing: Theme.Space.s4) {
                    Text(path.displayName).font(Theme.title).foregroundStyle(Theme.text)
                    Text(path.tagline).font(Theme.body).foregroundStyle(Theme.text2)
                        .fixedSize(horizontal: false, vertical: true)
                    Text(path.summary).font(Theme.caption).foregroundStyle(Theme.text2)
                }
                Spacer(minLength: 0)
                Image(systemName: selected ? "checkmark.circle.fill" : "circle")
                    .font(.system(.title3))
                    .foregroundStyle(selected ? Theme.accent : Theme.border)
            }
            .padding(Theme.cardPadding)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(selected ? Theme.accentSoft : Theme.surface, in: RoundedRectangle(cornerRadius: Theme.radius))
            .overlay(RoundedRectangle(cornerRadius: Theme.radius).stroke(selected ? Theme.accent : Theme.border,
                                                                         lineWidth: selected ? 2 : 1))
            .animation(.easeOut(duration: Theme.fast), value: selected)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .accessibilityIdentifier("path-\(path.category)")
        // A Button owns its subtree's accessibility, so the character inside it
        // has no identifier of its own to find: say what is pictured here.
        .accessibilityLabel("\(path.displayName) build. \(path.tagline) \(path.summary)")
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
