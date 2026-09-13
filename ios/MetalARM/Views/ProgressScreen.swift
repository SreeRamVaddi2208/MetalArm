//
//  ProgressScreen.swift
//  MetalARM
//
//  Port of frontend/frontend/pages/progress.py. Named ProgressScreen to avoid
//  clashing with SwiftUI's ProgressView.
//

import Charts
import SwiftUI

struct ProgressScreen: View {
    @Environment(AppModel.self) private var model

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                Text("Progress")
                    .font(Theme.display(28))
                    .foregroundStyle(Theme.text)
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 8) {
                        ForEach(model.progressTabs) { tab in
                            tabButton(tab)
                        }
                    }
                }
                if let progress = model.progress {
                    chartCard(progress)
                }
                Text("Personal records")
                    .font(Theme.display(16))
                    .foregroundStyle(Theme.text)
                    .padding(.top, 2)
                ForEach(model.records) { record in
                    recordRow(record, exerciseName: model.progress?.exerciseName ?? "")
                }
                if model.records.isEmpty && model.progress != nil {
                    Text("No records yet — log a set to set your first.")
                        .font(.system(size: 13))
                        .foregroundStyle(Theme.dim)
                }
                ErrorText(message: model.errorMessage)
            }
            .padding(20)
        }
        .background(Theme.bg)
        .task { await model.loadProgress() }
    }

    private func tabButton(_ tab: AppModel.ProgressTab) -> some View {
        let active = tab.id == model.selectedExerciseID
        return Button {
            Task { await model.selectExercise(tab.id) }
        } label: {
            Text(tab.name)
                .font(Theme.display(12.5, active ? .bold : .semibold))
                .foregroundStyle(active ? Theme.bg : Theme.dim)
                .padding(.horizontal, 14)
                .padding(.vertical, 7)
                .background(active ? Theme.fire : Theme.card, in: RoundedRectangle(cornerRadius: 10))
                .overlay(RoundedRectangle(cornerRadius: 10).stroke(active ? Color.clear : Theme.cardBorder))
        }
        .buttonStyle(.plain)
    }

    private func chartCard(_ progress: ProgressData) -> some View {
        let improving = progress.changeSinceStart >= 0
        return VStack(alignment: .leading, spacing: 4) {
            HStack(alignment: .firstTextBaseline, spacing: 4) {
                Text(formatNumber(progress.currentValue))
                    .font(Theme.display(26, .heavy))
                    .foregroundStyle(Theme.text)
                Text(progress.unit)
                    .font(.system(size: 13))
                    .foregroundStyle(Theme.dim)
            }
            Text("\(improving ? "▲" : "▼") \(formatNumber(abs(progress.changeSinceStart))) since start")
                .font(.system(size: 12, weight: .semibold))
                .foregroundStyle(improving ? Theme.green : Theme.fire)
            Chart(progress.points) { point in
                AreaMark(x: .value("Date", point.date), y: .value(progress.unit, point.value))
                    .foregroundStyle(LinearGradient(colors: [Theme.fire.opacity(0.35), Theme.fire.opacity(0.02)], startPoint: .top, endPoint: .bottom))
                    .interpolationMethod(.monotone)
                LineMark(x: .value("Date", point.date), y: .value(progress.unit, point.value))
                    .foregroundStyle(Theme.fire)
                    .interpolationMethod(.monotone)
            }
            .chartXAxis(.hidden)
            .chartYAxis(.hidden)
            .chartYScale(domain: .automatic(includesZero: false))
            .frame(height: 140)
            .padding(.top, 10)
        }
        .padding(18)
        .cardStyle()
    }

    private func recordRow(_ record: RecordItem, exerciseName: String) -> some View {
        HStack(spacing: 12) {
            Image(systemName: "medal.fill")
                .font(.system(size: 18))
                .foregroundStyle(Theme.gold)
            VStack(alignment: .leading, spacing: 2) {
                Text("\(record.label) — \(exerciseName)")
                    .font(.system(size: 13.5, weight: .bold))
                    .foregroundStyle(Theme.text)
                Text("\(record.detail) · \(record.achievedAt)")
                    .font(.system(size: 11.5))
                    .foregroundStyle(Theme.dim)
            }
            Spacer()
            Text("\(formatNumber(record.value)) \(record.unit)")
                .font(Theme.display(13))
                .foregroundStyle(Theme.fire)
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 12)
        .cardStyle(cornerRadius: 14)
    }
}

#Preview {
    ProgressScreen()
        .environment(AppModel(api: MockAPIClient()))
        .preferredColorScheme(.dark)
}
