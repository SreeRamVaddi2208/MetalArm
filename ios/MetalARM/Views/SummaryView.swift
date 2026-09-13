//
//  SummaryView.swift
//  MetalARM
//
//  Port of frontend/frontend/pages/summary.py.
//

import SwiftUI

struct SummaryView: View {
    let summary: WorkoutSummary
    var onDone: () -> Void

    private var hasPR: Bool { !summary.newPrs.isEmpty }

    var body: some View {
        VStack(spacing: 0) {
            ScrollView {
                VStack(spacing: 0) {
                    ZStack {
                        RoundedRectangle(cornerRadius: 26)
                            .fill(LinearGradient(colors: [Theme.gold, Theme.goldDeep], startPoint: .topLeading, endPoint: .bottomTrailing))
                        Image(systemName: hasPR ? "trophy.fill" : "checkmark.circle.fill")
                            .font(.system(size: 40, weight: .semibold))
                            .foregroundStyle(Theme.bg)
                    }
                    .frame(width: 88, height: 88)
                    .shadow(color: Theme.gold.opacity(0.3), radius: 16, y: 16)

                    Text(hasPR ? "New Personal Record!" : "Workout Complete")
                        .font(Theme.display(26, .heavy))
                        .foregroundStyle(Theme.text)
                        .padding(.top, 18)

                    if let pr = summary.headlinePR {
                        Text("\(pr.exerciseName) · \(pr.detail)")
                            .font(.system(size: 14))
                            .foregroundStyle(Theme.dim)
                            .padding(.top, 6)
                    }

                    HStack(spacing: 12) {
                        StatTile(value: "\(summary.durationMin)", label: "Duration", unit: "min")
                        StatTile(value: formatNumber(summary.totalVolumeKg), label: "Volume", unit: "kg")
                        StatTile(value: "\(summary.totalSets)", label: "Sets")
                    }
                    .padding(.top, 26)

                    pointsCard
                        .padding(.top, 14)
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
                    .font(.system(size: 13, weight: .semibold))
                    .foregroundStyle(Theme.dim)
                Spacer()
                Text("+\(summary.totalPoints)")
                    .font(Theme.display(26, .heavy))
                    .foregroundStyle(Theme.fire)
            }
            VStack(spacing: 4) {
                breakdownRow("Sets logged", summary.pointsBreakdown.sets)
                breakdownRow("Session completed", summary.pointsBreakdown.sessionCompleted)
                breakdownRow("PR bonus", summary.pointsBreakdown.prBonus)
                breakdownRow("Streak bonus", summary.pointsBreakdown.streakBonus)
            }
            .padding(.top, 12)
            XPBar(progress: summary.level.progress)
                .padding(.top, 14)
            Text("Level \(summary.level.level) — \(summary.level.xpRemaining) XP to next level")
                .font(.system(size: 11))
                .foregroundStyle(Theme.dim)
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(.top, 6)
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
            Text("+\(points)")
        }
        .font(.system(size: 12))
        .foregroundStyle(Theme.faint)
    }
}
