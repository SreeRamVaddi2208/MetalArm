//
//  ProgressScreen.swift
//  MetalARM
//
//  Per-exercise history (top weight per finished workout) and records.
//  Named ProgressScreen to avoid clashing with SwiftUI's ProgressView.
//

import Charts
import SwiftUI

struct ProgressScreen: View {
    private struct ChartPoint: Identifiable {
        let id: String
        let date: Date
        let value: Double
    }

    @Environment(AppModel.self) private var model

    private var chartPoints: [ChartPoint] {
        model.history.compactMap { point in
            guard let top = point.topWeightKg, let date = parseServerDate(point.performedAt) else { return nil }
            return ChartPoint(id: point.id, date: date, value: model.weightUnit.fromKilograms(top))
        }
    }

    // One row per record type; "most reps" has a row per weight, so show the heaviest three.
    private var sortedRecords: [WorkoutRecord] {
        let order = WorkoutRecord.displayOrder
        let others = model.records
            .filter { $0.recordType != "max_reps_at_weight" }
            .sorted { (order.firstIndex(of: $0.recordType) ?? order.count) < (order.firstIndex(of: $1.recordType) ?? order.count) }
        let reps = model.records
            .filter { $0.recordType == "max_reps_at_weight" }
            .sorted { ($0.weightKg ?? 0) > ($1.weightKg ?? 0) }
            .prefix(3)
        return others + reps
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                Text("Progress")
                    .font(Theme.display(28))
                    .foregroundStyle(Theme.text)
                if model.progressTabs.isEmpty {
                    if !model.isBusy {
                        Text("Finish a workout to start tracking your progress.")
                            .font(Theme.body(14))
                            .foregroundStyle(Theme.dim)
                    }
                } else {
                    tabs
                    chartCard
                    Text("Personal records")
                        .font(Theme.display(16))
                        .foregroundStyle(Theme.text)
                        .padding(.top, 2)
                    ForEach(sortedRecords) { record in
                        recordRow(record)
                    }
                    if model.records.isEmpty && !model.isBusy {
                        Text("No records yet - finish a workout with this exercise.")
                            .font(Theme.body(13))
                            .foregroundStyle(Theme.dim)
                    }
                }
                ErrorText(message: model.errorMessage)
            }
            .padding(20)
        }
        .background(Theme.bg)
        .task { await model.loadProgress() }
        .refreshable { await model.loadProgress() }
    }

    private var tabs: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 8) {
                ForEach(model.progressTabs) { tab in
                    let active = tab.id == model.selectedProgressID
                    Button {
                        Task { await model.selectProgress(tab.id) }
                    } label: {
                        Text(tab.name)
                            .font(Theme.display(12.5, active ? .bold : .semibold))
                            .foregroundStyle(active ? Theme.bg : Theme.dim)
                            .padding(.horizontal, 14)
                            .padding(.vertical, 7)
                            .background(active ? Theme.accent : Theme.card, in: RoundedRectangle(cornerRadius: 10))
                            .overlay(RoundedRectangle(cornerRadius: 10).stroke(active ? Color.clear : Theme.cardBorder))
                    }
                    .buttonStyle(.plain)
                }
            }
        }
    }

    private var chartCard: some View {
        let points = chartPoints
        let unit = model.weightUnit.rawValue
        return VStack(alignment: .leading, spacing: 4) {
            if let last = points.last, let first = points.first {
                HStack(alignment: .firstTextBaseline, spacing: 4) {
                    Text(formatNumber(last.value))
                        .font(Theme.display(26, .heavy))
                        .foregroundStyle(Theme.text)
                    Text("\(unit) top set")
                        .font(Theme.body(13))
                        .foregroundStyle(Theme.dim)
                }
                if points.count > 1 {
                    let change = last.value - first.value
                    Text("\(change >= 0 ? "▲" : "▼") \(formatNumber(abs(change))) \(unit) since \(first.date.formatted(.dateTime.month().day()))")
                        .font(Theme.body(12, .semibold))
                        .foregroundStyle(change >= 0 ? Theme.success : Theme.dim)
                }
                Chart(points) { point in
                    AreaMark(x: .value("Date", point.date), y: .value(unit, point.value))
                        .foregroundStyle(LinearGradient(colors: [Theme.accent.opacity(0.35), Theme.accent.opacity(0.02)], startPoint: .top, endPoint: .bottom))
                        .interpolationMethod(.monotone)
                    LineMark(x: .value("Date", point.date), y: .value(unit, point.value))
                        .foregroundStyle(Theme.accent)
                        .interpolationMethod(.monotone)
                }
                .chartXAxis(.hidden)
                .chartYAxis(.hidden)
                .chartYScale(domain: .automatic(includesZero: false))
                .frame(height: 140)
                .padding(.top, 10)
            } else {
                Text("No finished workouts with this exercise yet.")
                    .font(Theme.body(13))
                    .foregroundStyle(Theme.dim)
                    .frame(maxWidth: .infinity, minHeight: 80)
            }
        }
        .padding(18)
        .cardStyle()
    }

    private func recordRow(_ record: WorkoutRecord) -> some View {
        HStack(spacing: 12) {
            Image(systemName: "medal.fill")
                .font(Theme.body(18))
                .foregroundStyle(Theme.silver)
            VStack(alignment: .leading, spacing: 2) {
                Text("\(record.label) — \(record.exerciseName)")
                    .font(Theme.body(13.5, .bold))
                    .foregroundStyle(Theme.text)
                Text(parseServerDate(record.achievedAt)?.formatted(date: .abbreviated, time: .omitted) ?? String(record.achievedAt.prefix(10)))
                    .font(Theme.body(11.5))
                    .foregroundStyle(Theme.dim)
            }
            Spacer()
            Text(record.valueText(in: model.weightUnit))
                .font(Theme.display(13))
                .foregroundStyle(Theme.accent)
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
