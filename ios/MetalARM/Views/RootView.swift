//
//  RootView.swift
//  MetalARM
//

import SwiftUI

struct RootView: View {
    enum AppTab: Hashable {
        case home, train, library, progress, profile
    }

    @Environment(AppModel.self) private var model
    @Environment(\.scenePhase) private var scenePhase
    @AppStorage("hasOnboarded") private var hasOnboarded = false
    @State private var selectedTab: AppTab = .home
    @State private var authMode: AuthView.Mode = .signUp
    /// Answered (or skipped) in this launch. `me` refreshes a beat later, so
    /// without this the question can flash back before the server replies.
    @State private var pathAsked = false

    var body: some View {
        if !hasOnboarded {
            OnboardingView { mode in
                authMode = mode
                hasOnboarded = true
            }
        } else if !model.isSignedIn {
            AuthView(mode: $authMode)
        } else if model.needsTrainingPath && !pathAsked {
            // Asked once, between signing in and the app proper: the answer
            // decides what gets suggested from the first workout on.
            TrainingPathView(isOnboarding: true) { pathAsked = true }
        } else {
            tabs
        }
    }

    private var tabs: some View {
        @Bindable var model = model
        return TabView(selection: $selectedTab) {
            // Each tab keeps its own stack: a list pushes its detail.
            Tab("Home", systemImage: "house", value: AppTab.home) {
                NavigationStack { HomeView { selectedTab = .train }.statusBarBackdrop() }
            }
            Tab("Train", systemImage: "dumbbell", value: AppTab.train) {
                NavigationStack { WorkoutView { selectedTab = .library }.statusBarBackdrop() }
            }
            Tab("Library", systemImage: "books.vertical", value: AppTab.library) {
                LibraryHomeView { selectedTab = .train }
            }
            Tab("Progress", systemImage: "chart.line.uptrend.xyaxis", value: AppTab.progress) {
                NavigationStack { ProgressScreen().statusBarBackdrop() }
            }
            Tab("Profile", systemImage: "person.crop.circle", value: AppTab.profile) {
                NavigationStack { ProfileView().statusBarBackdrop() }
            }
        }
        .tint(Theme.accent)
        // Sets saved offline go out as soon as the network is back, or when
        // the app returns to the foreground.
        .task { model.startSyncingWhenOnline() }
        .onChange(of: scenePhase) { _, phase in
            if phase == .active { Task { await model.flushPendingSets() } }
        }
        .fullScreenCover(isPresented: $model.showingSummary) {
            if let result = model.finishResult {
                SummaryView(result: result, unit: model.weightUnit, inviteCode: model.shareInviteCode) {
                    model.showingSummary = false
                }
            }
        }
    }
}

#Preview {
    RootView()
        .environment(AppModel(api: MockAPIClient()))
        .preferredColorScheme(.dark)
}
