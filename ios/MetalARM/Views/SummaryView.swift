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

    private var lead: PREvent? { result.prEvents.celebrated }

    var body: some View {
        VStack(spacing: 0) {
            ScrollView {
                VStack(spacing: 0) {
                    ZStack {
                        RoundedRectangle(cornerRadius: 26)
                            .fill(LinearGradient(colors: [Theme.gold, Theme.goldDeep], startPoint: .topLeading, endPoint: .bottomTrailing))
                        Image(systemName: lead == nil ? "checkmark.circle.fill" : "trophy.fill")
                            .font(Theme.body(40, .semibold))
                            .foregroundStyle(Theme.bg)
                    }
                    .frame(width: 88, height: 88)
                    .shadow(color: Theme.gold.opacity(0.3), radius: 16, y: 16)

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
            Button("Done", action: onDone)
                .buttonStyle(PrimaryButtonStyle())
                .accessibilityIdentifier("doneButton")
                .padding(.horizontal, 24)
                .padding(.bottom, 24)
        }
        .background {
            ZStack {
                Theme.bg
                RadialGradient(colors: [Theme.fire.opacity(0.22), .clear], center: UnitPoint(x: 0.5, y: 0.18), startRadius: 0, endRadius: 320)
            }
            .ignoresSafeArea()
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
                    .foregroundStyle(Theme.fire)
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
                    .foregroundStyle(Theme.fire)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(.top, 12)
            }
        }
        .padding(18)
        .background {
            ZStack {
                Theme.card
                LinearGradient(colors: [Theme.fire.opacity(0.16), Theme.violet.opacity(0.16)], startPoint: .topLeading, endPoint: .bottomTrailing)
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
