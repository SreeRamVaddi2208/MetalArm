//
//  LiveAPIClient.swift
//  MetalARM
//
//  Talks to the FastAPI backend in backend/. Points, PRs and XP are computed
//  server-side; this client only sends what the contract's request bodies allow.
//

import Foundation

enum APIError: LocalizedError, Equatable {
    case http(status: Int, detail: String)
    case invalidResponse

    var errorDescription: String? {
        switch self {
        case let .http(status, detail): "\(detail) (HTTP \(status))"
        case .invalidResponse: "The server sent an unexpected response."
        }
    }
}

final class LiveAPIClient: MetalArmAPI {
    /// Same default and override variable as frontend/frontend/api.py.
    static var defaultBaseURL: URL {
        if let override = ProcessInfo.processInfo.environment["METALARM_BACKEND_URL"],
           let url = URL(string: override) {
            return url
        }
        return URL(string: "http://localhost:8000")!
    }

    static func makeDecoder() -> JSONDecoder {
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        return decoder
    }

    private let baseURL: URL
    private let session: URLSession
    private let decoder = LiveAPIClient.makeDecoder()
    private let encoder: JSONEncoder = {
        let encoder = JSONEncoder()
        encoder.keyEncodingStrategy = .convertToSnakeCase
        return encoder
    }()

    init(baseURL: URL = LiveAPIClient.defaultBaseURL, session: URLSession = .shared) {
        self.baseURL = baseURL
        self.session = session
    }

    func me() async throws -> User { try await get("users/me") }

    func exercises() async throws -> [Exercise] { try await get("exercises") }

    func startSession() async throws -> SessionStart { try await post("sessions", body: EmptyBody()) }

    func logSet(sessionID: Int, exerciseID: Int, weightKg: Double, reps: Int) async throws -> LogSetResult {
        try await post(
            "sessions/\(sessionID)/sets",
            body: LogSetBody(exerciseId: exerciseID, weightKg: weightKg, reps: reps, rpe: nil, isWarmup: false))
    }

    func finishSession(sessionID: Int) async throws -> WorkoutSummary {
        try await post("sessions/\(sessionID)/finish", body: EmptyBody())
    }

    func progress(exerciseID: Int) async throws -> ProgressData {
        try await get("progress/\(exerciseID)", query: ["metric": "max_weight", "range": "1y"])
    }

    func records(exerciseID: Int) async throws -> [RecordItem] { try await get("progress/\(exerciseID)/records") }

    func leaderboard() async throws -> [LeaderboardEntry] { try await get("leaderboard", query: ["period": "week"]) }

    func profile() async throws -> ProfileData { try await get("profile") }

    func friendActivity() async throws -> [FriendActivity] { try await get("friends/activity") }

    // MARK: - Transport

    private struct EmptyBody: Encodable {}

    private struct LogSetBody: Encodable {
        let exerciseId: Int
        let weightKg: Double
        let reps: Int
        let rpe: Double?
        let isWarmup: Bool
    }

    private struct ErrorBody: Decodable {
        let detail: String
    }

    private func get<T: Decodable>(_ path: String, query: [String: String] = [:]) async throws -> T {
        var components = URLComponents(url: baseURL.appending(path: path), resolvingAgainstBaseURL: false)!
        if !query.isEmpty {
            components.queryItems = query.sorted { $0.key < $1.key }.map { URLQueryItem(name: $0.key, value: $0.value) }
        }
        var request = URLRequest(url: components.url!, timeoutInterval: 10)
        request.httpMethod = "GET"
        return try await send(request)
    }

    private func post<T: Decodable, Body: Encodable>(_ path: String, body: Body) async throws -> T {
        var request = URLRequest(url: baseURL.appending(path: path), timeoutInterval: 10)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try encoder.encode(body)
        return try await send(request)
    }

    private func send<T: Decodable>(_ request: URLRequest) async throws -> T {
        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse else { throw APIError.invalidResponse }
        guard (200..<300).contains(http.statusCode) else {
            // FastAPI errors look like {"detail": "Session already finished"}.
            let detail = (try? JSONDecoder().decode(ErrorBody.self, from: data))?.detail
                ?? HTTPURLResponse.localizedString(forStatusCode: http.statusCode)
            throw APIError.http(status: http.statusCode, detail: detail)
        }
        return try decoder.decode(T.self, from: data)
    }
}
