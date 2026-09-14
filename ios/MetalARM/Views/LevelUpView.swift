//
//  LevelUpView.swift
//  MetalARM
//
//  The level-up celebration, shown over the summary whenever the server's
//  FinishResponse says the workout levelled the user up. A rank-up gets the
//  bigger version. Reduce Motion turns it into a plain fade.
//

import SwiftUI

struct LevelUpView: View {
    let progression: ProgressionDelta
    /// The summary's story card, offered right when the moment is biggest.
    var shareCard: Image? = nil
    var onContinue: () -> Void

    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var appeared = false
    @State private var burst = false
    @State private var hapticBeat = 0

    private var isRankUp: Bool { progression.rankedUp }
    private var levelsGained: Int { max(1, progression.levelAfter - progression.levelBefore) }
    private var badge: String { isRankUp ? progression.rankAfter : "\(progression.levelAfter)" }
    private var title: String { isRankUp ? "RANK UP" : "LEVEL UP" }

    private var subtitle: String {
        if isRankUp { return "You're now rank \(progression.rankAfter) at level \(progression.levelAfter)." }
        if levelsGained > 1 { return "+\(levelsGained) levels. You reached level \(progression.levelAfter)." }
        return "You reached level \(progression.levelAfter). Keep going."
    }

    private var announcement: String {
        isRankUp ? "Rank up. You reached rank \(progression.rankAfter)." : "Level up. You reached level \(progression.levelAfter)."
    }

    var body: some View {
        ZStack {
            // Nearly opaque: the summary behind must not compete with the number.
            Color.black.opacity(0.94)
                .ignoresSafeArea()
            RadialGradient(colors: [Theme.silver.opacity(isRankUp ? 0.34 : 0.24), .clear], center: .center, startRadius: 0, endRadius: 380)
                .ignoresSafeArea()
                .opacity(appeared ? 1 : 0)
                .animation(.easeOut(duration: 0.4), value: appeared)

            VStack(spacing: 18) {
                ZStack {
                    if !reduceMotion {
                        ForEach(0..<(isRankUp ? 4 : 3), id: \.self) { ring in
                            Circle()
                                .stroke(
                                    LinearGradient(colors: [Theme.accent, Theme.silverDeep], startPoint: .top, endPoint: .bottom),
                                    lineWidth: 3)
                                .frame(width: 150, height: 150)
                                .scaleEffect(burst ? 2.1 + Double(ring) * 0.35 : 0.6)
                                .opacity(burst ? 0 : 0.9)
                                .animation(.easeOut(duration: 1.1).delay(0.15 + Double(ring) * 0.18), value: burst)
                        }
                        ForEach(0..<24, id: \.self) { index in
                            Spark(index: index, burst: burst)
                        }
                    }
                    Text(badge)
                        .font(Theme.display(isRankUp ? 132 : 120, .bold))
                        .foregroundStyle(
                            LinearGradient(colors: [Theme.accent, Theme.silver, Theme.silverDeep], startPoint: .top, endPoint: .bottom))
                        .shadow(color: Theme.accent.opacity(0.45), radius: 24)
                        .scaleEffect(appeared || reduceMotion ? 1 : 0.4)
                        .opacity(appeared ? 1 : 0)
                        .animation(
                            reduceMotion ? .easeOut(duration: 0.25) : .spring(response: 0.45, dampingFraction: 0.55),
                            value: appeared)
                        .accessibilityHidden(true)
                }
                .frame(height: 230)

                VStack(spacing: 8) {
                    Text(title)
                        .font(Theme.display(30, .bold))
                        .tracking(6)
                        .foregroundStyle(Theme.accent)
                    Text(subtitle)
                        .font(Theme.body(15))
                        .foregroundStyle(Theme.dim)
                        .multilineTextAlignment(.center)
                }
                .offset(y: appeared || reduceMotion ? 0 : 24)
                .opacity(appeared ? 1 : 0)
                .animation(.easeOut(duration: 0.45).delay(reduceMotion ? 0 : 0.25), value: appeared)

                Button("Continue", action: onContinue)
                    .buttonStyle(PrimaryButtonStyle())
                    .accessibilityIdentifier("levelUpContinueButton")
                    .padding(.horizontal, 56)
                    .padding(.top, 18)
                    .opacity(appeared ? 1 : 0)
                    .animation(.easeOut(duration: 0.3).delay(reduceMotion ? 0 : 0.5), value: appeared)

                if let shareCard {
                    ShareLink(item: shareCard, preview: SharePreview("MetalArm", image: shareCard)) {
                        Label("Share", systemImage: "square.and.arrow.up")
                            .font(Theme.body(14, .semibold))
                            .foregroundStyle(Theme.dim)
                            .padding(8)
                    }
                    .accessibilityIdentifier("levelUpShareButton")
                    .opacity(appeared ? 1 : 0)
                    .animation(.easeOut(duration: 0.3).delay(reduceMotion ? 0 : 0.6), value: appeared)
                }
            }
            .padding(.horizontal, 24)
        }
        .contentShape(Rectangle())
        .onTapGesture(perform: onContinue)
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier("levelUpOverlay")
        .sensoryFeedback(trigger: hapticBeat) { _, _ in
            isRankUp ? .impact(weight: .heavy, intensity: 1) : .success
        }
        .onAppear {
            appeared = true
            burst = true
            hapticBeat += 1
            if isRankUp {
                // Rank-up: a second, heavier beat right after the first.
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.2) { hapticBeat += 1 }
            }
            AccessibilityNotification.Announcement(announcement).post()
        }
    }
}

/// One metal shard flying out from the badge.
private struct Spark: View {
    let index: Int
    let burst: Bool

    var body: some View {
        let angle = Double(index) / 24 * 2 * .pi + (index.isMultiple(of: 2) ? 0.12 : -0.1)
        let distance = CGFloat(150 + (index * 37) % 70)
        Capsule()
            .fill(index.isMultiple(of: 3) ? Theme.accent : Theme.silver)
            .frame(width: 3, height: CGFloat(14 + (index % 4) * 4))
            .rotationEffect(.radians(angle + .pi / 2))
            .offset(x: burst ? cos(angle) * distance : 0, y: burst ? sin(angle) * distance : 0)
            .opacity(burst ? 0 : 1)
            .animation(.easeOut(duration: 0.9).delay(0.12 + Double(index % 5) * 0.03), value: burst)
    }
}
