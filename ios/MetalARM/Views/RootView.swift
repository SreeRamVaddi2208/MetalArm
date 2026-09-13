//
//  RootView.swift
//  MetalARM
//

import SwiftUI

struct RootView: View {
    enum AppTab: Hashable {
        case home, workout, progress, ranks, profile
    }

    @Environment(AppModel.self) private var model
    @AppStorage("hasOnboarded") private var hasOnboarded = false
    @State private var selectedTab: AppTab = .home
    @State private var authMode: AuthView.Mode = .signUp

    var body: some View {
        if !hasOnboarded {
            OnboardingView { mode in
                authMode = mode
                hasOnboarded = true
            }
        } else if !model.isSignedIn {
            AuthView(mode: $authMode)
        } else {
            tabs
        }
    }

    private var tabs: some View {
        @Bindable var model = model
        return TabView(selection: $selectedTab) {
            Tab("Home", systemImage: "house", value: AppTab.home) {
                HomeView { selectedTab = .workout }
            }
            Tab("Workout", systemImage: "dumbbell", value: AppTab.workout) {
                WorkoutView()
            }
            Tab("Progress", systemImage: "chart.line.uptrend.xyaxis", value: AppTab.progress) {
                ProgressScreen()
            }
            Tab("Ranks", systemImage: "trophy", value: AppTab.ranks) {
                LeaderboardView()
            }
            Tab("Profile", systemImage: "person.crop.circle", value: AppTab.profile) {
                ProfileView()
            }
        }
        .tint(Theme.fire)
        .fullScreenCover(isPresented: $model.showingSummary) {
            if let result = model.finishResult {
                SummaryView(result: result, unit: model.weightUnit) { model.showingSummary = false }
            }
        }
    }
}

#Preview {
    RootView()
        .environment(AppModel(api: MockAPIClient()))
        .preferredColorScheme(.dark)
}
