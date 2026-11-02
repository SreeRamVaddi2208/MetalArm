//
//  ExploreExercises.swift
//  MetalARM
//
//  Explore's Exercises tab: the muscle and equipment grids, the figure cards
//  they lead to, and one exercise's figure, muscles and steps.
//

import SwiftUI

private let threeColumns = Array(repeating: GridItem(.flexible(), spacing: Theme.Space.s12), count: 3)
private let twoColumns = Array(repeating: GridItem(.flexible(), spacing: Theme.Space.s12), count: 2)

/// The browsable rows of backend/app/data/taxonomy.json.
private let muscleTiles: [(code: String, label: String)] = [
    ("chest", "Chest"), ("biceps", "Biceps"), ("triceps", "Triceps"), ("back", "Back"), ("shoulders", "Shoulders"),
    ("abs", "Abs"), ("quads", "Quadriceps"), ("hamstrings", "Hamstrings"), ("glutes", "Glutes"), ("calves", "Calves"),
    ("forearms", "Forearms"), ("cardio", "Cardio"),
]
private let equipmentTiles: [(code: String, label: String)] = [
    ("barbell", "Barbell"), ("dumbbell", "Dumbbell"), ("bodyweight", "Body weight"), ("cable", "Cable"),
    ("machine", "Machine"), ("smith_machine", "Smith machine"), ("kettlebell", "Kettlebell"), ("band", "Band"),
    ("ez_bar", "EZ bar"), ("trap_bar", "Trap bar"), ("cardio_machine", "Cardio machine"), ("other", "Other"),
]

struct ExploreExercises: View {
    @Environment(AppModel.self) private var model
    let query: String

    @State private var muscle: (code: String, label: String)?
    @State private var gear: (code: String, label: String)?
    @State private var cards: [ExerciseCard] = []
    @State private var total = 0
    @State private var cursor: String?
    @State private var favorites: Set<String> = []
    @State private var open: ExerciseCard?
    @State private var error = ""

    private var listing: Bool { muscle != nil || gear != nil || !query.trimmed.isEmpty }
    private var searchKey: String { "\(query.trimmed)|\(muscle?.code ?? "")|\(gear?.code ?? "")" }

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Space.s24) {
            if !error.isEmpty {
                ErrorState(message: error) { Task { await search() } }
            } else if listing {
                results
            } else {
                grids
            }
        }
        .task(id: searchKey) {
            // Debounce typing: a newer query cancels this one.
            try? await Task.sleep(for: .milliseconds(250))
            guard !Task.isCancelled else { return }
            await search()
        }
        .sheet(item: $open) { card in
            ExerciseSheet(id: card.id, name: card.name)
        }
    }

    private var grids: some View {
        VStack(alignment: .leading, spacing: Theme.Space.s24) {
            SectionBlock(title: "Muscle Groups") {
                LazyVGrid(columns: threeColumns, spacing: Theme.Space.s16) {
                    ForEach(muscleTiles, id: \.code) { tile in
                        Button { muscle = tile } label: {
                            VStack(spacing: Theme.Space.s8) {
                                FigureImage(path: "/figures/muscles/\(tile.code).png").aspectRatio(1, contentMode: .fit)
                                Text(tile.label).font(Theme.label).foregroundStyle(Theme.text)
                            }
                        }
                        .buttonStyle(.plain)
                        .accessibilityIdentifier("muscle-\(tile.code)")
                    }
                }
            }
            SectionBlock(title: "Equipment") {
                LazyVGrid(columns: threeColumns, spacing: Theme.Space.s16) {
                    ForEach(equipmentTiles, id: \.code) { tile in
                        Button { gear = tile } label: {
                            VStack(spacing: Theme.Space.s8) {
                                FigureImage(path: "/figures/equipment/\(tile.code).png")
                                    .padding(Theme.Space.s16)
                                    .aspectRatio(1, contentMode: .fit)
                                    .background(Theme.surface, in: Circle())
                                Text(tile.label).font(Theme.label).foregroundStyle(Theme.text)
                                    .lineLimit(1).minimumScaleFactor(0.8)
                            }
                        }
                        .buttonStyle(.plain)
                        .accessibilityIdentifier("equipment-\(tile.code)")
                    }
                }
            }
        }
    }

    private var results: some View {
        VStack(alignment: .leading, spacing: Theme.Space.s12) {
            HStack {
                Text(muscle?.label ?? gear?.label ?? "Results").font(Theme.title).foregroundStyle(Theme.text)
                Spacer()
                if muscle != nil || gear != nil {
                    Button("Clear") { muscle = nil; gear = nil }
                        .font(Theme.label).foregroundStyle(Theme.text2)
                        .accessibilityIdentifier("exploreClear")
                }
            }
            Text(plural(total, "exercise")).font(Theme.caption).foregroundStyle(Theme.text2)
            LazyVGrid(columns: twoColumns, spacing: Theme.Space.s12) {
                ForEach(cards) { card($0) }
            }
            if cursor != nil {
                Button("Show more") { Task { await search(more: true) } }
                    .font(Theme.label).foregroundStyle(Theme.text2)
                    .frame(maxWidth: .infinity, minHeight: Theme.touch)
            }
        }
    }

    private func card(_ card: ExerciseCard) -> some View {
        Button { open = card } label: {
            VStack(alignment: .leading, spacing: 0) {
                FigureImage(path: card.thumbnailUrl)
                    .aspectRatio(1, contentMode: .fit)
                    .frame(maxWidth: .infinity)
                    .background(Theme.surface)
                VStack(alignment: .leading, spacing: Theme.Space.s4) {
                    Text(card.name).font(Theme.label).foregroundStyle(Theme.text)
                        .lineLimit(2, reservesSpace: true).multilineTextAlignment(.leading)
                    Text(card.muscleLabel).font(Theme.caption).foregroundStyle(Theme.text2).lineLimit(1)
                }
                .padding(Theme.Space.s12)
            }
            .background(Theme.surface2, in: RoundedRectangle(cornerRadius: Theme.radius))
            .clipShape(RoundedRectangle(cornerRadius: Theme.radius))
        }
        .buttonStyle(.plain)
        .accessibilityIdentifier("exerciseCard-\(card.name)")
        .overlay(alignment: .topLeading) {
            let on = favorites.contains(card.id)
            Button {
                Task { await toggle(card.id) }
            } label: {
                Image(systemName: on ? "bookmark.fill" : "bookmark")
                    .foregroundStyle(on ? Theme.accent : Theme.text2)
                    .frame(width: Theme.iconHit, height: Theme.iconHit)
            }
            .accessibilityLabel(on ? "Remove bookmark" : "Bookmark")
            .accessibilityIdentifier("bookmark-\(card.name)")
        }
    }

    private func search(more: Bool = false) async {
        error = ""
        do {
            if favorites.isEmpty {
                let kept = try await model.api.savedItems(filter: "favorites")
                favorites = Set(kept.filter { $0.type == "exercise" }.map(\.id))
            }
            guard listing else { return }
            let page = try await model.api.browseExercises(
                query: query, muscle: muscle?.code, equipment: gear?.code, cursor: more ? cursor : nil)
            cards = more ? cards + page.items : page.items
            total = page.total
            cursor = page.nextCursor
        } catch is CancellationError {
            return
        } catch {
            self.error = error.localizedDescription
        }
    }

    private func toggle(_ id: String) async {
        let on = !favorites.contains(id)
        do {
            try await model.api.setFavorite(type: "exercise", id: id, on: on)
            if on { favorites.insert(id) } else { favorites.remove(id) }
        } catch {
            self.error = error.localizedDescription
        }
    }
}

/// One exercise: the large figure, what it works, and how to do it.
struct ExerciseSheet: View {
    @Environment(AppModel.self) private var model
    @Environment(\.dismiss) private var dismiss
    let id: String
    let name: String
    @State private var exercise: Exercise?
    @State private var error = ""

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: Theme.Space.s16) {
                    if let exercise {
                        // Square whether or not the picture has arrived.
                        Theme.surface
                            .aspectRatio(1, contentMode: .fit)
                            .overlay { FigureImage(path: exercise.illustrationUrl ?? exercise.thumbnailUrl) }
                            .clipShape(RoundedRectangle(cornerRadius: Theme.radius))
                            .accessibilityElement(children: .ignore)
                            .accessibilityLabel("\(exercise.name): muscles worked")
                            .accessibilityIdentifier("exerciseSheetFigure")
                        Text(exercise.muscleLabel).font(Theme.title).foregroundStyle(Theme.text)
                        if !(exercise.secondaryMuscleGroups ?? []).isEmpty {
                            Text("Also: \(exercise.secondaryLabel)").font(Theme.caption).foregroundStyle(Theme.text2)
                        }
                        ForEach(Array(exercise.howTo.enumerated()), id: \.offset) { index, step in
                            Text("\(index + 1). \(step)").font(Theme.body).foregroundStyle(Theme.text)
                        }
                        if let credit = exercise.figureCredit {
                            Text(credit).font(Theme.caption).foregroundStyle(Theme.text3)
                        }
                    } else if error.isEmpty {
                        Skeleton(height: 280)
                    } else {
                        ErrorState(message: error) { Task { await load() } }
                    }
                }
                .screen()
            }
            .background(Theme.bg)
            .navigationTitle(name)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Done") { dismiss() } }
            }
            .task { await load() }
        }
        .preferredColorScheme(.dark)
    }

    private func load() async {
        error = ""
        do {
            exercise = try await model.api.exercise(id: id)
        } catch {
            self.error = error.localizedDescription
        }
    }
}
