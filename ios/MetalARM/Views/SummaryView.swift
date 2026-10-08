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
        ScrollView {
            VStack(alignment: .leading, spacing: Theme.Space.s24) {
                HStack {
                    Text(lead == nil ? "Workout complete" : "New personal record")
                        .font(Theme.titleLG).foregroundStyle(Theme.text)
                    Spacer()
                    if let shareCard {
                        ShareLink(item: shareCard, preview: SharePreview("My MetalArm workout", image: shareCard)) {
                            Image(systemName: "square.and.arrow.up").foregroundStyle(Theme.text2)
                                .frame(width: Theme.iconHit, height: Theme.iconHit)
                        }
                        .accessibilityLabel("Share")
                        .accessibilityIdentifier("shareButton")
                    }
                }
                if let lead {
                    // The record: an accent-soft row, the summary's bigger moment.
                    VStack(alignment: .leading, spacing: Theme.Space.s4) {
                        HStack(spacing: Theme.Space.s8) {
                            Pill(label: "PR")
                            Text(lead.headline(in: unit)).font(Theme.body).foregroundStyle(Theme.text)
                        }
                        Text(lead.motivation).font(Theme.caption).foregroundStyle(Theme.text2)
                            .accessibilityIdentifier("prMotivation")
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(Theme.Space.s12)
                    .background(Theme.accentSoft, in: RoundedRectangle(cornerRadius: Theme.radius))
                }
                HStack(spacing: Theme.Space.s16) {
                    StatTile(value: "\(max(1, result.session.durationSeconds / 60))", label: "Duration", unit: "min")
                    StatTile(value: formatNumber(unit.fromKilograms(result.session.totalVolumeKg).rounded()),
                             label: "Volume", unit: unit.rawValue)
                    StatTile(value: "\(result.session.workingSets)", label: "Sets")
                }
                if !result.qualified {
                    Text("Short workout: under 10 minutes or fewer than 3 working sets, so no completion bonus or streak credit. Your set points still count.")
                        .font(Theme.caption).foregroundStyle(Theme.text2)
                        .accessibilityIdentifier("unqualifiedNote")
                }
                points
                Text("\(result.streak.weeks)-week streak · \(result.streak.thisWeekSessions)/\(result.streak.target) workouts this week")
                    .font(Theme.caption).foregroundStyle(Theme.text2)
            }
            .screen()
            .padding(.top, Theme.Space.s32)
        }
        .background(Theme.bg.ignoresSafeArea())
        .pinnedPrimary {
            Button("Done", action: onDone)
                .buttonStyle(.primary)
                .accessibilityIdentifier("doneButton")
        }
        .overlay {
            if showingLevelUp {
                LevelUpView(progression: result.progression, shareCard: shareCard) {
                    withAnimation(.easeOut(duration: Theme.base)) { showingLevelUp = false }
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

    /// Every point and where it came from - the server's breakdown - with the
    /// total as the screen's hero number.
    private var points: some View {
        SectionBlock(title: "Points") {
            RowGroup {
                breakdownRow("Sets logged", result.breakdown.setPoints)
                breakdownRow("Workout completed", result.breakdown.sessionBonus)
                breakdownRow("PR bonus", result.breakdown.prBonus)
                breakdownRow("Streak bonus", result.breakdown.streakBonus)
                if result.breakdown.reversals != 0 {
                    breakdownRow("Adjustments", result.breakdown.reversals)
                }
            }
            HStack(alignment: .firstTextBaseline) {
                Text("Total").font(Theme.body).foregroundStyle(Theme.text2)
                Spacer()
                Text("+\(result.breakdown.total)").font(Theme.display).foregroundStyle(Theme.accent)
                    .accessibilityIdentifier("pointsTotal")
            }
            if !result.progression.hint.isEmpty {
                Text(result.progression.hint).font(Theme.caption).foregroundStyle(Theme.text2)
            }
        }
    }

    private func breakdownRow(_ label: String, _ points: Int) -> some View {
        ListRow(title: label, trailing: points >= 0 ? "+\(points)" : "\(points)")
    }
}
