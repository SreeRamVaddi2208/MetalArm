//
//  LibraryPathView.swift
//  MetalARM
//
//  Every program and workout of one training path, in the server's order,
//  narrowed by the filter sheet (days, difficulty, equipment, length).
//

import SwiftUI

struct LibraryPathView: View {
    @Environment(AppModel.self) private var model
    @State var category: String
    @State private var filtering = false
    @State private var loaded = false

    private var own: String { model.libraryHome?.path ?? model.me?.characterClass ?? "" }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: Theme.Space.s24) {
                PathChips(selected: category, own: own) { category = $0 }
                if !model.libraryFilters.isEmpty {
                    HStack {
                        Text("\(model.libraryFilters.count) filter\(model.libraryFilters.count == 1 ? "" : "s") on")
                            .font(Theme.caption).foregroundStyle(Theme.text2)
                        Spacer()
                        Button("Clear") { clearFilters() }.buttonStyle(.ghost)
                    }
                }
                if !loaded {
                    VStack(spacing: Theme.Space.s12) {
                        Skeleton(height: 120)
                        Skeleton(height: 120)
                        Skeleton()
                    }
                } else {
                    ErrorState(message: model.errorMessage) { Task { await load() } }
                    SectionBlock(title: "Programs") {
                        if model.libraryPrograms.isEmpty {
                            EmptyState(systemImage: "calendar", line: "No programs match these filters.") { clearButton }
                        } else {
                            ForEach(model.libraryPrograms) { ProgramCard(program: $0, showPill: false) }
                        }
                    }
                    SectionBlock(title: "Workouts") {
                        if model.libraryWorkouts.isEmpty {
                            EmptyState(systemImage: "dumbbell", line: "No workouts match these filters.") { clearButton }
                        } else {
                            RowGroup {
                                ForEach(model.libraryWorkouts) { WorkoutRow(workout: $0) }
                            }
                        }
                    }
                }
            }
            .screen()
        }
        .background(Theme.bg)
        .navigationTitle(LibraryVocabulary.pathLabel(category))
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .topBarTrailing) {
                IconButton(systemName: "slider.horizontal.3", label: "Filter", badge: !model.libraryFilters.isEmpty) {
                    filtering = true
                }
                .accessibilityIdentifier("libraryFilterButton")
            }
        }
        .task(id: category) { await load() }
        .sheet(isPresented: $filtering) {
            FilterSheet(filters: model.libraryFilters) { filters in
                model.libraryFilters = filters
                filtering = false
                Task { await load() }
            }
        }
    }

    private var clearButton: some View {
        Button("Clear filters") { clearFilters() }
            .buttonStyle(MAButtonStyle(kind: .secondary, full: false))
            .disabled(model.libraryFilters.isEmpty)
    }

    private func clearFilters() {
        model.libraryFilters = LibraryFilters()
        Task { await load() }
    }

    private func load() async {
        await model.loadLibraryPath(category)
        loaded = true
    }
}

/// Chips in four groups; nothing changes until Show results.
private struct FilterSheet: View {
    @State var filters: LibraryFilters
    let onApply: (LibraryFilters) -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Space.s16) {
            Text("Filter").font(Theme.title).foregroundStyle(Theme.text)
                .padding(.top, Theme.Space.s24)
            ScrollView {
                VStack(alignment: .leading, spacing: Theme.Space.s24) {
                    group("Days a week") {
                        ForEach(LibraryVocabulary.days, id: \.self) { days in
                            Chip(label: "\(days)", selected: filters.daysPerWeek == days) {
                                filters.daysPerWeek = filters.daysPerWeek == days ? nil : days
                            }
                        }
                    }
                    group("Difficulty") {
                        ForEach(LibraryVocabulary.difficulties, id: \.self) { level in
                            Chip(label: LibraryVocabulary.label(level), selected: filters.difficulty == level) {
                                filters.difficulty = filters.difficulty == level ? nil : level
                            }
                        }
                    }
                    group("Equipment you have") {
                        ForEach(LibraryVocabulary.equipment, id: \.self) { kit in
                            Chip(label: LibraryVocabulary.label(kit), selected: filters.equipment.contains(kit)) {
                                if let index = filters.equipment.firstIndex(of: kit) {
                                    filters.equipment.remove(at: index)
                                } else {
                                    filters.equipment.append(kit)
                                }
                            }
                        }
                    }
                    group("Workout length") {
                        ForEach(LibraryVocabulary.durations, id: \.self) { minutes in
                            Chip(label: "Up to \(minutes) min", selected: filters.maxMinutes == minutes) {
                                filters.maxMinutes = filters.maxMinutes == minutes ? nil : minutes
                            }
                        }
                    }
                    Button("Clear filters") { filters = LibraryFilters() }
                        .buttonStyle(MAButtonStyle(kind: .ghost))
                }
            }
            Button("Show results") { onApply(filters) }
                .buttonStyle(.primary)
                .accessibilityIdentifier("showResultsButton")
        }
        .padding(.horizontal, Theme.gutter)
        .padding(.bottom, Theme.Space.s8)
        .presentationDetents([.large])
        .presentationBackground(Theme.surface)
        .presentationCornerRadius(Theme.radiusSheet)
        .presentationDragIndicator(.visible)
    }

    private func group<Content: View>(_ title: String, @ViewBuilder _ content: () -> Content) -> some View {
        VStack(alignment: .leading, spacing: Theme.Space.s8) {
            Text(title).font(Theme.caption).foregroundStyle(Theme.text2)
            FlowLayout(spacing: Theme.Space.s8) { content() }
        }
    }
}

/// Lays children out left to right, wrapping onto new lines.
struct FlowLayout: Layout {
    var spacing: CGFloat

    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        let rows = arrange(width: proposal.width ?? .infinity, subviews: subviews)
        return CGSize(width: proposal.width ?? rows.width, height: rows.height)
    }

    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        let rows = arrange(width: bounds.width, subviews: subviews)
        for (index, origin) in rows.origins.enumerated() {
            subviews[index].place(at: CGPoint(x: bounds.minX + origin.x, y: bounds.minY + origin.y),
                                  proposal: .unspecified)
        }
    }

    private func arrange(width: CGFloat, subviews: Subviews) -> (origins: [CGPoint], width: CGFloat, height: CGFloat) {
        var origins: [CGPoint] = []
        var x: CGFloat = 0, y: CGFloat = 0, lineHeight: CGFloat = 0, widest: CGFloat = 0
        for subview in subviews {
            let size = subview.sizeThatFits(.unspecified)
            if x > 0 && x + size.width > width {
                x = 0
                y += lineHeight + spacing
                lineHeight = 0
            }
            origins.append(CGPoint(x: x, y: y))
            x += size.width + spacing
            lineHeight = max(lineHeight, size.height)
            widest = max(widest, x - spacing)
        }
        return (origins, widest, y + lineHeight)
    }
}
