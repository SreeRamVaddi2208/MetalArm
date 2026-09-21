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
    private var badge: String { isRankUp ? RankTitle.shout(progression.rankAfter) : "\(progression.levelAfter)" }
    private var title: String { isRankUp ? "RANK UP" : "LEVEL UP" }

    private var subtitle: String {
        if isRankUp { return "You're now \(RankTitle.of(progression.rankAfter)) at level \(progression.levelAfter)." }
        if levelsGained > 1 { return "+\(levelsGained) levels. You reached level \(progression.levelAfter)." }
        return "You reached level \(progression.levelAfter). Keep going."
    }

    private var announcement: String {
        isRankUp ? "Rank up. You are now \(RankTitle.of(progression.rankAfter))." : "Level up. You reached level \(progression.levelAfter)."
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
                        ForEach(0..<(isRankUp ? 5 : 3), id: \.self) { ring in
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
                            Spark(index: index, burst: burst, asPlate: isRankUp)
                        }
                    }
                    // A rank is a word, not a digit: it starts wide and slightly
                    // large, then settles as the rings go out - a heavier landing
                    // than the level number's quick spring.
                    Text(badge)
                        .font(Theme.display(isRankUp ? 54 : 120, .bold))
                        .tracking(isRankUp ? (appeared || reduceMotion ? 4 : 18) : 0)
                        .minimumScaleFactor(0.5)
                        .lineLimit(1)
                        .foregroundStyle(
                            LinearGradient(colors: [Theme.accent, Theme.silver, Theme.silverDeep], startPoint: .top, endPoint: .bottom))
                        .shadow(color: Theme.accent.opacity(0.45), radius: 24)
                        .scaleEffect(appeared || reduceMotion ? 1 : (isRankUp ? 1.25 : 0.4))
                        .opacity(appeared ? 1 : 0)
                        .padding(.horizontal, 20)
                        .animation(
                            reduceMotion
                                ? .easeOut(duration: 0.25)
                                : (isRankUp
                                    ? .spring(response: 0.75, dampingFraction: 0.72)
                                    : .spring(response: 0.45, dampingFraction: 0.55)),
                            value: appeared)
                        .accessibilityHidden(true)
                }
                .frame(height: 230)

                if isRankUp {
                    HStack(spacing: 10) {
                        Text(RankTitle.of(progression.rankBefore))
                            .foregroundStyle(Theme.faint)
                            .opacity(appeared ? 0.55 : 1)
                            .scaleEffect(appeared || reduceMotion ? 0.94 : 1)
                        Image(systemName: "arrow.right")
                            .foregroundStyle(Theme.dim)
                            .offset(x: appeared || reduceMotion ? 0 : -10)
                            .opacity(appeared ? 1 : 0)
                        Text(RankTitle.of(progression.rankAfter))
                            .foregroundStyle(Theme.text)
                            .scaleEffect(appeared || reduceMotion ? 1 : 0.9)
                            .opacity(appeared ? 1 : 0)
                    }
                    .font(Theme.display(14, .semibold))
                    .animation(reduceMotion ? .easeOut(duration: 0.2) : .easeOut(duration: 0.5).delay(0.35), value: appeared)
                    .accessibilityHidden(true)
                }

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
                // A third as the rings reach their widest.
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.55) { hapticBeat += 1 }
            }
            AccessibilityNotification.Announcement(announcement).post()
        }
    }
}

/// One piece flying out from the badge: a metal shard on a level-up, and on a
/// rank-up a short bar that spins as it goes, like a plate leaving the bar.
private struct Spark: View {
    let index: Int
    let burst: Bool
    var asPlate = false

    var body: some View {
        let angle = Double(index) / 24 * 2 * .pi + (index.isMultiple(of: 2) ? 0.12 : -0.1)
        let distance = CGFloat((asPlate ? 185 : 150) + (index * 37) % 70)
        let spin = Double((index % 3) + 1) * (index.isMultiple(of: 2) ? 1 : -1) * .pi / 2
        RoundedRectangle(cornerRadius: asPlate ? 2 : 1.5)
            .fill(index.isMultiple(of: 3) ? Theme.accent : Theme.silver)
            .frame(
                width: asPlate ? CGFloat(8 + (index % 3) * 3) : 3,
                height: asPlate ? CGFloat(3 + (index % 2) * 2) : CGFloat(14 + (index % 4) * 4))
            .rotationEffect(.radians(asPlate ? (burst ? angle + spin : angle) : angle + .pi / 2))
            .offset(x: burst ? cos(angle) * distance : 0, y: burst ? sin(angle) * distance : 0)
            .opacity(burst ? 0 : 1)
            .animation(
                .easeOut(duration: asPlate ? 1.15 : 0.9).delay(0.12 + Double(index % 5) * 0.03),
                value: burst)
    }
}
