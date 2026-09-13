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
        // UI tests start from onboarding and run against the contract examples, not a live server.
        if arguments.contains("-UITestResetOnboarding") {
            UserDefaults.standard.removeObject(forKey: "hasOnboarded")
        }
        let api: MetalArmAPI = arguments.contains("-UITestMockAPI") ? MockAPIClient() : LiveAPIClient()
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
