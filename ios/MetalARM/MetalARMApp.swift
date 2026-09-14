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
                signedIn: arguments.contains("-UITestSignedIn"), levelUpOnFinish: arguments.contains("-UITestLevelUp"))
        } else {
            let tokens = KeychainTokenStore()
            if resetOnboarding { tokens.tokens = nil }
            api = LiveAPIClient(baseURL: AppConfig.apiBaseURL, tokenStore: tokens)
        }
        _model = State(initialValue: AppModel(api: api))
    }

    var body: some Scene {
        WindowGroup {
            RootView()
                .environment(model)
                .preferredColorScheme(.dark)
        }
    }
}
