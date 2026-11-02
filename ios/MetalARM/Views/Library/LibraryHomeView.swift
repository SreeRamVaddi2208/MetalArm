//
//  LibraryHomeView.swift
//  MetalARM
//
//  The Explore tab: search, and two tabs. Exercises is ExploreExercises;
//  Programs is the program you follow (its Start is the screen's one
//  accent fill), what is recommended for your path, then the other paths and
//  the exercise list. Two taps to a workout. With no path yet, one card asks
//  for it and everything is listed by path.
//

import SwiftUI

struct LibraryHomeView: View {
    @Environment(AppModel.self) private var model
    /// Called once a workout has started, to switch to Train.
    var onStarted: () -> Void = {}

    @State private var path = NavigationPath()
    @State private var choosingPath = false
    @State private var part = "Programs"
    @State private var query = ""
    @State private var allPrograms: [LibraryProgramCard] = []
    @State private var allWorkouts: [LibraryWorkoutCard] = []

    private var own: String { model.libraryHome?.path ?? model.me?.characterClass ?? "" }

    var body: some View {
        // The tab owns its stack, so the path chips and "See all" can push.
        NavigationStack(path: $path) {
            home.statusBarBackdrop().libraryDestinations(onStarted: onStarted)
        }
    }

    private var home: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: Theme.Space.s24) {
                HStack(spacing: Theme.Space.s8) {
                    Image(systemName: "magnifyingglass").foregroundStyle(Theme.text2)
                    TextField(part == "Exercises" ? "Search for exercises" : "Search for programs", text: $query)
                        .font(Theme.body).foregroundStyle(Theme.text)
                        .autocorrectionDisabled()
                        .accessibilityIdentifier("exploreSearch")
                }
                .padding(.horizontal, Theme.Space.s16)
                .frame(minHeight: Theme.touch)
                .background(Theme.surface2, in: RoundedRectangle(cornerRadius: Theme.radius))
                HStack(spacing: 0) {
                    ForEach(["Programs", "Exercises"], id: \.self) { option in
                        Button { part = option } label: {
                            VStack(spacing: Theme.Space.s8) {
                                Text(option).font(Theme.label)
                                    .foregroundStyle(part == option ? Theme.text : Theme.text2)
                                Rectangle().fill(part == option ? Theme.text : .clear).frame(height: 2)
                            }
                            .frame(maxWidth: .infinity)
                            .contentShape(Rectangle())
                        }
                        .buttonStyle(.plain)
                        .accessibilityIdentifier("explore-\(option)")
                    }
                }
                if part == "Exercises" {
                    ExploreExercises(query: query)
                } else {
                    if query.trimmed.isEmpty { programs } else { programHits }
                }
            }
            .screen()
        }
        .background(Theme.bg)
        .task(id: query.trimmed.isEmpty) {
            // Every program and workout, once, for the search below.
            guard !query.trimmed.isEmpty, allPrograms.isEmpty else { return }
            allPrograms = (try? await model.api.libraryPrograms(category: nil, filters: LibraryFilters())) ?? []
            allWorkouts = (try? await model.api.libraryWorkouts(category: nil, filters: LibraryFilters())) ?? []
        }
        .task { await model.loadLibraryHome() }
        .refreshable { await model.loadLibraryHome() }
        .sheet(isPresented: $choosingPath) {
            TrainingPathView(isOnboarding: false) {
                choosingPath = false
                Task { await model.loadLibraryHome() }
            }
            .task { await model.loadTrainingPaths() }
            .presentationBackground(Theme.bg)
        }
    }

    @ViewBuilder
    private var programHits: some View {
        let needle = query.trimmed.lowercased()
        let foundPrograms = allPrograms.filter { $0.name.lowercased().contains(needle) }
        let foundWorkouts = allWorkouts.filter { $0.name.lowercased().contains(needle) }
        if foundPrograms.isEmpty && foundWorkouts.isEmpty {
            EmptyState(systemImage: "magnifyingglass", line: "No programs or workouts match.")
        }
        if !foundPrograms.isEmpty {
            SectionBlock(title: "Programs") {
                VStack(spacing: Theme.Space.s12) { ForEach(foundPrograms) { ProgramCard(program: $0) } }
            }
        }
        if !foundWorkouts.isEmpty {
            SectionBlock(title: "Workouts") {
                RowGroup { ForEach(foundWorkouts) { WorkoutRow(workout: $0) } }
            }
        }
    }

    @ViewBuilder
    private var programs: some View {
        HStack(spacing: Theme.Space.s8) {
            PathChips(selected: own, own: own) { category in
                path.append(LibraryRoute.path(category))
            }
            NavigationLink(value: LibraryRoute.path(own.isEmpty ? "athlete" : own)) {
                Image(systemName: "slider.horizontal.3").font(Theme.title).foregroundStyle(Theme.text2)
                    .frame(width: Theme.iconHit, height: Theme.iconHit)
            }
            .accessibilityLabel("Search and filter")
            .accessibilityIdentifier("librarySearchButton")
        }
        if let home = model.libraryHome {
            content(home)
        } else if model.errorMessage.isEmpty {
            VStack(spacing: Theme.Space.s16) {
                Skeleton(height: 120)
                Skeleton(height: 160)
                Skeleton()
            }
        } else {
            ErrorState(message: model.errorMessage) { Task { await model.loadLibraryHome() } }
        }
    }

    @ViewBuilder
    private func content(_ home: LibraryHome) -> some View {
        if let yours = home.yourProgram {
            yourProgram(yours)
        }
        if home.needsPath {
            choosePath
        } else {
            SectionBlock(title: "Recommended for you", action: "See all",
                         onAction: { path.append(LibraryRoute.path(home.path)) }) {
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(alignment: .top, spacing: Theme.Space.s12) {
                        ForEach(home.recommendedPrograms) { program in
                            ProgramCard(program: program).frame(width: 280)
                        }
                    }
                    .padding(.horizontal, Theme.gutter)
                }
                .padding(.horizontal, -Theme.gutter)
                if !home.recommendedWorkouts.isEmpty {
                    Text("Workouts").font(Theme.caption).foregroundStyle(Theme.text2)
                    RowGroup {
                        ForEach(home.recommendedWorkouts) { WorkoutRow(workout: $0) }
                    }
                }
            }
        }
        SectionBlock(title: home.needsPath ? "Browse by path" : "Explore other paths") {
            RowGroup {
                ForEach(home.otherPaths) { other in
                    NavigationLink(value: LibraryRoute.path(other.category)) {
                        ListRow(title: other.label, subtitle: "\(plural(other.programs, "program")) · \(plural(other.workouts, "workout"))",
                                chevron: true)
                    }
                    .buttonStyle(.plain)
                    .accessibilityIdentifier("library-path-\(other.category)")
                }
            }
        }
    }

    private func yourProgram(_ yours: YourProgram) -> some View {
        VStack(alignment: .leading, spacing: Theme.Space.s8) {
            Text("Your program").font(Theme.caption).foregroundStyle(Theme.text2)
            NavigationLink(value: LibraryRoute.program(yours.program.slug)) {
                Text(yours.program.name).font(Theme.title).foregroundStyle(Theme.text)
            }
            .buttonStyle(.plain)
            Text(yours.enrollment.whereLabel).font(Theme.caption).foregroundStyle(Theme.text2)
            if let next = yours.enrollment.nextWorkout {
                NavigationLink(value: LibraryRoute.workout(next.slug)) {
                    ListRow(title: "Next: \(next.name)", subtitle: next.meta, chevron: true)
                }
                .buttonStyle(.plain)
                Button {
                    Task { if await model.startLibraryWorkout(next.slug) { onStarted() } }
                } label: {
                    Label("Start", systemImage: "play.fill")
                }
                .buttonStyle(.primary)
                .disabled(model.isBusy)
                .accessibilityIdentifier("yourProgramStartButton")
            }
        }
        .card()
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier("yourProgramCard")
    }

    private var choosePath: some View {
        VStack(alignment: .leading, spacing: Theme.Space.s12) {
            Text("Pick your training path").font(Theme.title).foregroundStyle(Theme.text)
            Text("The Library leads with programs and workouts made for how you train. Until then, here is everything.")
                .font(Theme.body).foregroundStyle(Theme.text2)
            Button("Choose your path") { choosingPath = true }
                .buttonStyle(.primary)
                .accessibilityIdentifier("choosePathButton")
        }
        .card()
    }
}

#Preview {
    LibraryHomeView()
        .environment(AppModel(api: MockAPIClient()))
        .preferredColorScheme(.dark)
}
