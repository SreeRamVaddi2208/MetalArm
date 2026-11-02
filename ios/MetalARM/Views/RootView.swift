//
//  RootView.swift
//  MetalARM
//

import SwiftUI

struct RootView: View {
    @Environment(AppModel.self) private var model
    @Environment(\.scenePhase) private var scenePhase
    @AppStorage("hasOnboarded") private var hasOnboarded = false
    @State private var selectedTab: AppTab = .home
    /// A tab is built on its first visit, then kept: each holds its own stack.
    @State private var visited: Set<AppTab> = [.home]
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

    @ViewBuilder
    private func tabContent(_ tab: AppTab) -> some View {
        // Each tab keeps its own stack: a list pushes its detail.
        switch tab {
        case .home: NavigationStack { HomeView { selectedTab = .workout }.statusBarBackdrop() }
        case .explore: LibraryHomeView { selectedTab = .workout }
        case .workout: NavigationStack { WorkoutView { selectedTab = .explore }.statusBarBackdrop() }
        case .library: SavedLibraryView { selectedTab = .workout }
        case .you: NavigationStack { YouView().statusBarBackdrop() }
        }
    }

    private var tabs: some View {
        @Bindable var model = model
        return ZStack {
            ForEach(AppTab.allCases) { tab in
                if visited.contains(tab) {
                    tabContent(tab)
                        // The inset below does not reach scroll views inside a
                        // stack: without this, a list's last row stays under the bar.
                        .contentMargins(.bottom, 84, for: .scrollContent)
                        .environment(\.tabBarInset, 76)
                        .opacity(selectedTab == tab ? 1 : 0)
                        .allowsHitTesting(selectedTab == tab)
                        .accessibilityHidden(selectedTab != tab)
                }
            }
        }
        .background(Theme.bg)
        .safeAreaInset(edge: .bottom, spacing: 0) {
            FloatingTabBar(selected: $selectedTab)
                .ignoresSafeArea(.keyboard, edges: .bottom)
        }
        .onChange(of: selectedTab) { _, tab in visited.insert(tab) }
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
