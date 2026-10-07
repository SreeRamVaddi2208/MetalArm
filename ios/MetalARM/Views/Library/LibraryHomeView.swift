//
//  LibraryHomeView.swift
//  MetalARM
//
//  The Library tab: the program you follow (its Start is the screen's one
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
    @State private var browsingExercises = false

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
                ScreenTitle(title: "Library") {
                    NavigationLink(value: LibraryRoute.path(own.isEmpty ? "athlete" : own)) {
                        Image(systemName: "magnifyingglass").font(.system(.title3)).foregroundStyle(Theme.text2)
                            .frame(width: Theme.iconHit, height: Theme.iconHit)
                    }
                    .accessibilityLabel("Search and filter")
                    .accessibilityIdentifier("librarySearchButton")
                }
                PathChips(selected: own, own: own) { category in
                    path.append(LibraryRoute.path(category))
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
            .screen()
        }
        .background(Theme.bg)
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
        .sheet(isPresented: $browsingExercises) { ExercisePickerView(browsing: true) }
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
        RowGroup {
            Button { browsingExercises = true } label: {
                ListRow(title: "Exercises", subtitle: "Every exercise, by muscle and equipment", chevron: true) {
                    Image(systemName: "magnifyingglass").foregroundStyle(Theme.text2)
                }
            }
            .buttonStyle(.plain)
            .accessibilityIdentifier("libraryExercisesRow")
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
