//
//  AppConfig.swift
//  MetalARM
//
//  Server addresses for this build. Debug points at the local Docker stack,
//  Release at production; both come from the METALARM_*_BASE_URL build
//  settings through Info.plist. See docs/deployment.md.
//

import Foundation

enum AppConfig {
    /// The MetalArm API. METALARM_BACKEND_URL in the environment wins, for tests.
    static var apiBaseURL: URL {
        url(environmentKey: "METALARM_BACKEND_URL", plistKey: "METALARMAPIBaseURL", fallback: "http://127.0.0.1:8000")
    }

    /// The web app, which also serves /privacy and /support.
    static var webBaseURL: URL {
        url(environmentKey: "METALARM_WEB_URL", plistKey: "METALARMWebBaseURL", fallback: "http://localhost:3000")
    }

    static var privacyPolicyURL: URL { webBaseURL.appending(path: "privacy") }

    static var supportURL: URL { webBaseURL.appending(path: "support") }

    private static func url(environmentKey: String, plistKey: String, fallback: String) -> URL {
        if let value = ProcessInfo.processInfo.environment[environmentKey], let url = URL(string: value) {
            return url
        }
        if let value = Bundle.main.object(forInfoDictionaryKey: plistKey) as? String,
           !value.isEmpty, let url = URL(string: value) {
            return url
        }
        return URL(string: fallback)!
    }
}
