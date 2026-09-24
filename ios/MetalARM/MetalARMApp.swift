//
//  MetalARMApp.swift
//  MetalARM
//
//  Created by Vaddi Sree Rama Sai Sasi Sekhar on 13/09/26.
//

import SwiftUI

@main
struct MetalARMApp: App {
    @State private var model: AppModel

    init() {
        let arguments = ProcessInfo.processInfo.arguments
        // UI-test hooks: start from onboarding, skip it, and/or use the in-memory backend.
        let resetOnboarding = arguments.contains("-UITestResetOnboarding")
        if resetOnboarding {
            UserDefaults.standard.removeObject(forKey: "hasOnboarded")
        }
        if arguments.contains("-UITestSkipOnboarding") {
            UserDefaults.standard.set(true, forKey: "hasOnboarded")
        }

        let api: MetalArmAPI
        if arguments.contains("-UITestMockAPI") {
            api = MockAPIClient(
                signedIn: arguments.contains("-UITestSignedIn"), levelUpOnFinish: arguments.contains("-UITestLevelUp"),
                rankUpOnFinish: arguments.contains("-UITestRankUp"), offline: arguments.contains("-UITestOffline"),
                pathUnanswered: arguments.contains("-UITestNoTrainingPath"))
        } else {
            let tokens = KeychainTokenStore()
            if resetOnboarding { tokens.tokens = nil }
            api = LiveAPIClient(baseURL: AppConfig.apiBaseURL, tokenStore: tokens)
        }
        // The mock backend starts fresh every launch, so its offline queue does too.
        let pendingStore: PendingSetStore = arguments.contains("-UITestMockAPI") ? .inMemory : .onDisk
        _model = State(initialValue: AppModel(api: api, pendingStore: pendingStore))
    }

    var body: some Scene {
        WindowGroup {
            RootView()
                .environment(model)
                .preferredColorScheme(.dark)
        }
    }
}
