//
//  TokenStore.swift
//  MetalARM
//
//  Where the sign-in tokens live between launches.
//

import Foundation
import os
import Security

protocol TokenStore: AnyObject {
    var tokens: TokenPair? { get set }
}

final class InMemoryTokenStore: TokenStore {
    var tokens: TokenPair?

    init(tokens: TokenPair? = nil) {
        self.tokens = tokens
    }
}

/// The Keychain: encrypted at rest, readable after the first unlock (so a
/// refresh works in the background), and never restored to another device.
final class KeychainTokenStore: TokenStore {
    private static let log = Logger(subsystem: "com.SreeRam.MetalARM", category: "auth")
    private let service = "com.SreeRam.MetalARM.auth"
    private let account = "tokens"

    private var baseQuery: [String: Any] {
        [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
        ]
    }

    var tokens: TokenPair? {
        get {
            var query = baseQuery
            query[kSecReturnData as String] = true
            query[kSecMatchLimit as String] = kSecMatchLimitOne
            var result: CFTypeRef?
            guard SecItemCopyMatching(query as CFDictionary, &result) == errSecSuccess,
                  let data = result as? Data else { return nil }
            return try? JSONDecoder().decode(TokenPair.self, from: data)
        }
        set {
            SecItemDelete(baseQuery as CFDictionary)
            guard let newValue, let data = try? JSONEncoder().encode(newValue) else { return }
            var item = baseQuery
            item[kSecValueData as String] = data
            item[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly
            let status = SecItemAdd(item as CFDictionary, nil)
            // A refused write used to pass silently, and the next request then
            // found no token and reported "your session has ended" with nothing
            // in the log to explain it. That is exactly what an unsigned build
            // does (errSecMissingEntitlement, -34018), and it cost an hour.
            if status != errSecSuccess {
                Self.log.error("Keychain refused the tokens (OSStatus \(status)); the session will not survive a relaunch")
            }
        }
    }
}
