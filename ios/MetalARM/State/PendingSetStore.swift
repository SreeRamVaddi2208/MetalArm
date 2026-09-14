//
//  PendingSetStore.swift
//  MetalARM
//
//  Sets logged while the phone had no connection (gyms often have none). Each
//  keeps the client_set_id from the tap, so sending it again - even after a
//  response that was lost on the way back - can never log it twice: the server
//  answers a repeated id with the set it already has.
//

import Foundation
import Network

struct PendingSet: Codable, Equatable, Identifiable {
    let clientSetID: UUID
    let sessionID: String
    let exerciseID: String
    let weight: Double
    let unit: WeightUnit
    let reps: Int

    var id: UUID { clientSetID }

    /// For showing the queued set beside the logged ones, which are in kg.
    var weightKg: Double { unit == .kg ? weight : weight * WeightUnit.kilogramsPerPound }
}

/// Keeps the queue in a file so it survives the app being closed. With no
/// file (tests, UI tests on the mock backend) it lives only in memory.
final class PendingSetStore {
    private let fileURL: URL?

    init(fileURL: URL?) {
        self.fileURL = fileURL
    }

    static var onDisk: PendingSetStore {
        let directory = try? FileManager.default.url(
            for: .applicationSupportDirectory, in: .userDomainMask, appropriateFor: nil, create: true)
        return PendingSetStore(fileURL: directory?.appending(path: "pending-sets.json"))
    }

    static var inMemory: PendingSetStore { PendingSetStore(fileURL: nil) }

    func load() -> [PendingSet] {
        guard let fileURL, let data = try? Data(contentsOf: fileURL) else { return [] }
        return (try? JSONDecoder().decode([PendingSet].self, from: data)) ?? []
    }

    func save(_ sets: [PendingSet]) {
        guard let fileURL else { return }
        if sets.isEmpty {
            try? FileManager.default.removeItem(at: fileURL)
        } else {
            try? JSONEncoder().encode(sets).write(to: fileURL, options: .atomic)
        }
    }
}

extension Error {
    /// True when the request never got an answer - no network, or the server
    /// out of reach. Those sets are kept and retried; a set the server actually
    /// answered (rejected, say) is not.
    var isConnectivityFailure: Bool {
        guard let error = self as? URLError else { return false }
        switch error.code {
        case .notConnectedToInternet, .networkConnectionLost, .timedOut, .cannotConnectToHost,
             .cannotFindHost, .dnsLookupFailed, .internationalRoamingOff, .dataNotAllowed:
            return true
        default:
            return false
        }
    }
}

/// Calls back whenever the network comes back after being down.
final class ConnectivityMonitor {
    private let monitor = NWPathMonitor()
    private var started = false
    private var wasSatisfied = true

    func start(onReconnect: @escaping @MainActor @Sendable () -> Void) {
        guard !started else { return }
        started = true
        monitor.pathUpdateHandler = { [weak self] path in
            let satisfied = path.status == .satisfied
            Task { @MainActor in
                guard let self else { return }
                if satisfied && !self.wasSatisfied { onReconnect() }
                self.wasSatisfied = satisfied
            }
        }
        monitor.start(queue: DispatchQueue(label: "com.metalarm.connectivity"))
    }
}
