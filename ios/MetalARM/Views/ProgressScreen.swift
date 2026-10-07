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
            VStack(alignment: .leading, spacing: Theme.Space.s24) {
                ScreenTitle("Progress")
                if model.progressTabs.isEmpty {
                    if !model.isBusy {
                        EmptyState(systemImage: "chart.line.uptrend.xyaxis",
                                   line: "Finish a workout to start tracking your progress.")
                    }
                } else {
                    tabs
                    chart
                    SectionBlock(title: "Records") {
                        if model.records.isEmpty && !model.isBusy {
                            Text("Records appear as you beat your best on this exercise.")
                                .font(Theme.body).foregroundStyle(Theme.text2)
                        } else {
                            RowGroup {
                                ForEach(sortedRecords) { record in
                                    ListRow(title: "\(record.label) — \(record.exerciseName)",
                                            subtitle: parseServerDate(record.achievedAt)?.formatted(date: .abbreviated, time: .omitted)
                                                ?? String(record.achievedAt.prefix(10)),
                                            trailing: record.valueText(in: model.weightUnit))
                                }
                            }
                        }
                    }
                }
                ErrorText(message: model.errorMessage)
            }
            .screen()
        }
        .background(Theme.bg)
        .task { await model.loadProgress() }
        .refreshable { await model.loadProgress() }
    }

    private var tabs: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: Theme.Space.s8) {
                ForEach(model.progressTabs) { tab in
                    Chip(label: tab.name, selected: tab.id == model.selectedProgressID) {
                        Task { await model.selectProgress(tab.id) }
                    }
                }
            }
            .padding(.horizontal, Theme.gutter)
        }
        .padding(.horizontal, -Theme.gutter)
    }

    /// One accent line, no fill; a dot only on the latest point.
    private var chart: some View {
        let points = chartPoints
        let unit = model.weightUnit.rawValue
        return VStack(alignment: .leading, spacing: Theme.Space.s8) {
            if let last = points.last, let first = points.first {
                VStack(alignment: .leading, spacing: Theme.Space.s4) {
                    Text("Top set").font(Theme.caption).foregroundStyle(Theme.text2)
                    HStack(alignment: .firstTextBaseline, spacing: Theme.Space.s4) {
                        Text(formatNumber(last.value)).font(Theme.display).foregroundStyle(Theme.text)
                        Text(unit).font(Theme.caption).foregroundStyle(Theme.text2)
                            .accessibilityIdentifier("topSetUnit")
                    }
                }
                if points.count > 1 {
                    let change = last.value - first.value
                    Text("\(change >= 0 ? "+" : "−")\(formatNumber(abs(change))) \(unit) since \(first.date.formatted(.dateTime.month().day()))")
                        .font(Theme.caption).foregroundStyle(Theme.text2)
                }
                Chart(points) { point in
                    LineMark(x: .value("Date", point.date), y: .value(unit, point.value))
                        .foregroundStyle(Theme.accent)
                        .interpolationMethod(.monotone)
                    if point.id == last.id {
                        PointMark(x: .value("Date", point.date), y: .value(unit, point.value))
                            .foregroundStyle(Theme.accent)
                    }
                }
                .chartXAxis {
                    AxisMarks(values: .automatic(desiredCount: 4)) { _ in
                        AxisValueLabel().foregroundStyle(Theme.text2)
                    }
                }
                .chartYAxis {
                    AxisMarks(position: .trailing, values: .automatic(desiredCount: 4)) { _ in
                        AxisGridLine().foregroundStyle(Theme.border)
                        AxisValueLabel().foregroundStyle(Theme.text2)
                    }
                }
                .chartYScale(domain: .automatic(includesZero: false))
                .frame(height: 200)
            } else {
                EmptyState(systemImage: "chart.line.uptrend.xyaxis", line: "No finished workouts with this exercise yet.")
            }
        }
    }
}

#Preview {
    NavigationStack { ProgressScreen() }
        .environment(AppModel(api: MockAPIClient()))
        .preferredColorScheme(.dark)
}
