//
//  SummaryView.swift
//  MetalARM
//
//  The finish screen, built entirely from the server's FinishResponse.
//

import SwiftUI

struct SummaryView: View {
    let result: FinishResult
    let unit: WeightUnit
    var onDone: () -> Void

    /// Every level-up (and rank-up) opens with the celebration.
    @State private var showingLevelUp: Bool

    /// Printed on the share card, so a share can bring a friend into the party.
    let inviteCode: String?
    @State private var shareCard: Image?

    init(result: FinishResult, unit: WeightUnit, inviteCode: String? = nil, onDone: @escaping () -> Void) {
        self.result = result
        self.unit = unit
        self.inviteCode = inviteCode
        self.onDone = onDone
        _showingLevelUp = State(initialValue: result.progression.leveledUp || result.progression.rankedUp)
    }

    private var lead: PREvent? { result.prEvents.celebrated }

    var body: some View {
        VStack(spacing: 0) {
            ScrollView {
                VStack(spacing: 0) {
                    ZStack {
                        RoundedRectangle(cornerRadius: 26)
                            .fill(LinearGradient(colors: [Theme.silver, Theme.silverDeep], startPoint: .topLeading, endPoint: .bottomTrailing))
                        Image(systemName: lead == nil ? "checkmark.circle.fill" : "trophy.fill")
                            .font(Theme.body(40, .semibold))
                            .foregroundStyle(Theme.bg)
                    }
                    .frame(width: 88, height: 88)
                    .shadow(color: Theme.silver.opacity(0.3), radius: 16, y: 16)

                    Text(lead == nil ? "Workout Complete" : "New Personal Record!")
                        .font(Theme.display(26, .heavy))
                        .foregroundStyle(Theme.text)
                        .padding(.top, 18)

                    if let lead {
                        Text(lead.headline(in: unit))
                            .font(Theme.body(14))
                            .foregroundStyle(Theme.dim)
                            .multilineTextAlignment(.center)
                            .padding(.top, 6)
                    }

                    HStack(spacing: 12) {
                        StatTile(value: "\(max(1, result.session.durationSeconds / 60))", label: "Duration", unit: "min")
                        StatTile(value: formatNumber(unit.fromKilograms(result.session.totalVolumeKg).rounded()), label: "Volume", unit: unit.rawValue)
                        StatTile(value: "\(result.session.workingSets)", label: "Sets")
                    }
                    .padding(.top, 26)

                    if !result.qualified {
                        HStack(alignment: .top, spacing: 10) {
                            Image(systemName: "info.circle")
                            Text("Short workout: under 10 minutes or fewer than 3 working sets, so no completion bonus or streak credit. Your set points still count.")
                        }
                        .font(Theme.body(12))
                        .foregroundStyle(Theme.dim)
                        .padding(12)
                        .cardStyle(cornerRadius: 14)
                        .padding(.top, 14)
                        .accessibilityElement(children: .combine)
                        .accessibilityIdentifier("unqualifiedNote")
                    }

                    pointsCard
                        .padding(.top, 14)

                    Text("\(result.streak.weeks)-week streak · \(result.streak.thisWeekSessions)/\(result.streak.target) workouts this week")
                        .font(Theme.body(12))
                        .foregroundStyle(Theme.dim)
                        .padding(.top, 12)
                }
                .padding(.horizontal, 28)
                .padding(.top, 56)
            }
            VStack(spacing: 10) {
                if let shareCard {
                    ShareLink(item: shareCard, preview: SharePreview("My MetalArm workout", image: shareCard)) {
                        Label("Share", systemImage: "square.and.arrow.up")
                    }
                    .buttonStyle(SecondaryButtonStyle())
                    .accessibilityIdentifier("shareButton")
                }
                Button("Done", action: onDone)
                    .buttonStyle(PrimaryButtonStyle())
                    .accessibilityIdentifier("doneButton")
            }
            .padding(.horizontal, 24)
            .padding(.bottom, 24)
        }
        .background {
            ZStack {
                Theme.bg
                RadialGradient(colors: [Theme.accent.opacity(0.22), .clear], center: UnitPoint(x: 0.5, y: 0.18), startRadius: 0, endRadius: 320)
            }
            .ignoresSafeArea()
        }
        .overlay {
            if showingLevelUp {
                LevelUpView(progression: result.progression, shareCard: shareCard) {
                    withAnimation(.easeOut(duration: 0.25)) { showingLevelUp = false }
                }
                .transition(.opacity)
            }
        }
        .task { renderShareCard() }
    }

    private func renderShareCard() {
        guard shareCard == nil else { return }
        let content = ShareCardContent.make(result: result, unit: unit, inviteCode: inviteCode)
        if let image = ShareCardRenderer.render(content) {
            shareCard = Image(uiImage: image)
        }
    }

    private var pointsCard: some View {
        VStack(spacing: 0) {
            HStack {
                Text("Points earned")
                    .font(Theme.body(13, .semibold))
                    .foregroundStyle(Theme.dim)
                Spacer()
                Text("+\(result.breakdown.total)")
                    .font(Theme.display(26, .heavy))
                    .foregroundStyle(Theme.accent)
            }
            VStack(spacing: 4) {
                breakdownRow("Sets logged", result.breakdown.setPoints)
                breakdownRow("Workout completed", result.breakdown.sessionBonus)
                breakdownRow("PR bonus", result.breakdown.prBonus)
                breakdownRow("Streak bonus", result.breakdown.streakBonus)
                if result.breakdown.reversals != 0 {
                    breakdownRow("Adjustments", result.breakdown.reversals)
                }
            }
            .padding(.top, 12)
            if !result.progression.hint.isEmpty {
                Text(result.progression.hint)
                    .font(Theme.body(13, .bold))
                    .foregroundStyle(Theme.accent)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(.top, 12)
            }
        }
        .padding(18)
        .background {
            ZStack {
                Theme.card
                LinearGradient(colors: [Theme.accent.opacity(0.16), Theme.silver.opacity(0.16)], startPoint: .topLeading, endPoint: .bottomTrailing)
            }
            .clipShape(RoundedRectangle(cornerRadius: 18))
        }
        .overlay(RoundedRectangle(cornerRadius: 18).stroke(Theme.cardBorder))
    }

    private func breakdownRow(_ label: String, _ points: Int) -> some View {
        HStack {
            Text(label)
            Spacer()
            Text(points >= 0 ? "+\(points)" : "\(points)")
        }
        .font(Theme.body(12))
        .foregroundStyle(Theme.faint)
    }
}
