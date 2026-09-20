//
//  LiveAPIClient.swift
//  MetalARM
//
//  Talks to the MetalArm backend. Sends the access token on every request;
//  when it has expired (401), swaps the refresh token for a new pair once and
//  retries. If that fails too, the tokens are dropped and onSignedOut fires.
//

import Foundation

enum APIError: LocalizedError, Equatable {
    case http(status: Int, detail: String)
    case invalidResponse
    case signedOut

    var status: Int? {
        if case let .http(status, _) = self { status } else { nil }
    }

    var errorDescription: String? {
        switch self {
        case let .http(_, detail): detail
        case .invalidResponse: "The server sent an unexpected response."
        case .signedOut: "Your session has ended. Please sign in again."
        }
    }
}

final class LiveAPIClient: MetalArmAPI {
    static func makeDecoder() -> JSONDecoder {
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        return decoder
    }

    var onSignedOut: (() -> Void)?

    private let baseURL: URL
    private let session: URLSession
    private let tokenStore: TokenStore
    private let decoder = LiveAPIClient.makeDecoder()
    private let encoder: JSONEncoder = {
        let encoder = JSONEncoder()
        encoder.keyEncodingStrategy = .convertToSnakeCase
        return encoder
    }()
    // Concurrent 401s share one refresh instead of racing each other.
    private var refreshTask: Task<TokenPair, Error>?

    init(baseURL: URL = AppConfig.apiBaseURL, session: URLSession = .shared, tokenStore: TokenStore) {
        self.baseURL = baseURL
        self.session = session
        self.tokenStore = tokenStore
    }

    var isSignedIn: Bool { tokenStore.tokens != nil }

    // MARK: - Account

    func signIn(email: String, password: String) async throws {
        tokenStore.tokens = try await send(.post("auth/login", LoginBody(email: email, password: password), encoder), authenticated: false)
    }

    func signUp(email: String, password: String, displayName: String, timezone: String) async throws {
        let body = SignupBody(email: email, password: password, displayName: displayName, timezone: timezone)
        let _: Me = try await send(.post("auth/signup", body, encoder), authenticated: false)
        try await signIn(email: email, password: password)
    }

    func signOut() async {
        // Forget the tokens first, so the sign-out holds even if the app is
        // quit mid-request. Then, best effort, revoke this device's session
        // with the refresh token - still valid after the access token expired.
        guard let tokens = tokenStore.tokens else { return }
        tokenStore.tokens = nil
        _ = try? await perform(
            try .post("auth/logout", RefreshBody(refreshToken: tokens.refreshToken), encoder), authenticated: false)
    }

    func signOutEverywhere() async throws {
        _ = try await perform(.post("auth/logout-all", EmptyBody(), encoder), authenticated: true)
        tokenStore.tokens = nil
    }

    func deleteAccount(password: String) async throws {
        _ = try await perform(.delete("auth/me", PasswordBody(password: password), encoder), authenticated: true)
        tokenStore.tokens = nil
    }

    func me() async throws -> Me { try await send(.get("auth/me")) }

    func updateWeightUnit(_ unit: WeightUnit) async throws -> Me {
        try await send(.patch("auth/me", WeightUnitBody(weightUnit: unit), encoder))
    }

    func profile() async throws -> Profile { try await send(.get("profile")) }
    func rankTrials() async throws -> [RankTrial] { try await send(.get("profile/trials")) }
    func character() async throws -> CharacterSheet { try await send(.get("profile/character")) }

    func updateCharacterClass(_ value: String) async throws -> Me {
        try await send(.patch("auth/me", CharacterClassBody(characterClass: value), encoder))
    }

    func importWorkouts(csv: String, unit: WeightUnit) async throws -> WorkoutImportResult {
        try await send(.post("workouts/import", ImportBody(csv: csv, unit: unit.rawValue), encoder))
    }

    func points() async throws -> PointsSummary { try await send(.get("workouts/points")) }

    // MARK: - Exercises and progress

    func searchExercises(query: String) async throws -> [Exercise] {
        var parameters = ["limit": "50"]
        if !query.trimmed.isEmpty { parameters["q"] = query.trimmed }
        return try await send(.get("exercises", query: parameters))
    }

    func lastPerformance(exerciseID: String) async throws -> LastPerformance {
        try await send(.get("exercises/\(exerciseID)/last-performance"))
    }

    func exerciseHistory(exerciseID: String) async throws -> [HistoryPoint] {
        try await send(.get("exercises/\(exerciseID)/history"))
    }

    func records(exerciseID: String?) async throws -> [WorkoutRecord] {
        try await send(.get("workouts/records", query: exerciseID.map { ["exercise_id": $0] } ?? [:]))
    }

    // MARK: - Workouts

    func activeSession() async throws -> WorkoutSession? {
        let result: ActiveSession = try await send(.get("workouts/sessions/active"))
        return result.session
    }

    func session(id: String) async throws -> WorkoutSession { try await send(.get("workouts/sessions/\(id)")) }

    func presets() async throws -> [WorkoutPreset] { try await send(.get("workouts/presets")) }

    func startSession(presetSlug: String? = nil) async throws -> WorkoutSession {
        guard let presetSlug else {
            return try await send(.post("workouts/sessions", EmptyBody(), encoder))
        }
        return try await send(.post("workouts/sessions", PresetStart(presetSlug: presetSlug), encoder))
    }

    func logSet(sessionID: String, exerciseID: String, weight: Double, unit: WeightUnit, reps: Int, clientSetID: UUID) async throws -> SetLogResult {
        let body = SetBody(exerciseId: exerciseID, weight: weight, unit: unit, reps: reps, clientSetId: clientSetID.uuidString)
        return try await send(.post("workouts/sessions/\(sessionID)/sets", body, encoder))
    }

    func finishSession(sessionID: String) async throws -> FinishResult {
        try await send(.post("workouts/sessions/\(sessionID)/finish", EmptyBody(), encoder))
    }

    func abandonSession(sessionID: String) async throws {
        _ = try await perform(.post("workouts/sessions/\(sessionID)/abandon", EmptyBody(), encoder), authenticated: true)
    }

    // MARK: - Parties

    func parties() async throws -> [Party] { try await send(.get("parties")) }

    func createParty(name: String) async throws -> Party {
        try await send(.post("parties", PartyBody(name: name), encoder))
    }

    func joinParty(inviteCode: String) async throws -> Party {
        try await send(.post("parties/join", JoinBody(inviteCode: inviteCode), encoder))
    }

    func partyLeaderboard(partyID: String) async throws -> PartyBoard {
        try await send(.get("parties/\(partyID)/workout-leaderboard", query: ["period": "week"]))
    }

    func partyRaid(partyID: String) async throws -> PartyRaid {
        try await send(.get("parties/\(partyID)/raid"))
    }

    func league() async throws -> League { try await send(.get("leagues/current")) }

    // MARK: - Transport

    private struct RequestSpec {
        var method: String
        var path: String
        var query: [String: String] = [:]
        var body: Data?

        static func get(_ path: String, query: [String: String] = [:]) -> RequestSpec {
            RequestSpec(method: "GET", path: path, query: query)
        }

        static func post(_ path: String, _ body: some Encodable, _ encoder: JSONEncoder) throws -> RequestSpec {
            RequestSpec(method: "POST", path: path, body: try encoder.encode(body))
        }

        static func patch(_ path: String, _ body: some Encodable, _ encoder: JSONEncoder) throws -> RequestSpec {
            RequestSpec(method: "PATCH", path: path, body: try encoder.encode(body))
        }

        static func delete(_ path: String, _ body: some Encodable, _ encoder: JSONEncoder) throws -> RequestSpec {
            RequestSpec(method: "DELETE", path: path, body: try encoder.encode(body))
        }
    }

    private struct EmptyBody: Encodable {}
    private struct LoginBody: Encodable { let email: String; let password: String }
    private struct SignupBody: Encodable { let email: String; let password: String; let displayName: String; let timezone: String }
    private struct RefreshBody: Encodable { let refreshToken: String }
    private struct PasswordBody: Encodable { let password: String }
    private struct WeightUnitBody: Encodable { let weightUnit: WeightUnit }
    // No points or PR fields: the server computes those and ignores any sent.
    private struct SetBody: Encodable {
        let exerciseId: String
        let weight: Double
        let unit: WeightUnit
        let reps: Int
        let clientSetId: String
    }
    private struct PresetStart: Encodable { let presetSlug: String }
    private struct PartyBody: Encodable { let name: String }
    private struct JoinBody: Encodable { let inviteCode: String }

    private func send<T: Decodable>(_ spec: @autoclosure () throws -> RequestSpec, authenticated: Bool = true) async throws -> T {
        let data = try await perform(try spec(), authenticated: authenticated)
        return try decoder.decode(T.self, from: data)
    }

    private func perform(_ spec: RequestSpec, authenticated: Bool, isRetry: Bool = false) async throws -> Data {
        var request = makeURLRequest(spec)
        if authenticated {
            guard let tokens = tokenStore.tokens else { throw APIError.signedOut }
            request.setValue("Bearer \(tokens.accessToken)", forHTTPHeaderField: "Authorization")
        }

        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse else { throw APIError.invalidResponse }

        if http.statusCode == 401 && authenticated {
            if isRetry {
                endSession()
                throw APIError.signedOut
            }
            do {
                try await refreshTokens()
            } catch let error as APIError where error == .signedOut || error.status == 401 {
                endSession()
                throw APIError.signedOut
            }
            // Any other refresh failure (offline, server down) propagates and
            // keeps the tokens: a network blip must not sign the user out.
            return try await perform(spec, authenticated: true, isRetry: true)
        }

        guard (200..<300).contains(http.statusCode) else {
            throw APIError.http(status: http.statusCode, detail: Self.detail(from: data, status: http.statusCode))
        }
        return data
    }

    private func refreshTokens() async throws {
        if let refreshTask {
            _ = try await refreshTask.value
            return
        }
        guard let refreshToken = tokenStore.tokens?.refreshToken else { throw APIError.signedOut }
        let spec = try RequestSpec.post("auth/refresh", RefreshBody(refreshToken: refreshToken), encoder)
        let task = Task { () throws -> TokenPair in
            let data = try await self.perform(spec, authenticated: false)
            return try self.decoder.decode(TokenPair.self, from: data)
        }
        refreshTask = task
        defer { refreshTask = nil }
        tokenStore.tokens = try await task.value
    }

    private func endSession() {
        tokenStore.tokens = nil
        onSignedOut?()
    }

    private func makeURLRequest(_ spec: RequestSpec) -> URLRequest {
        var components = URLComponents(url: baseURL.appending(path: "api/v1/" + spec.path), resolvingAgainstBaseURL: false)!
        if !spec.query.isEmpty {
            components.queryItems = spec.query.sorted { $0.key < $1.key }.map { URLQueryItem(name: $0.key, value: $0.value) }
        }
        var request = URLRequest(url: components.url!, timeoutInterval: 15)
        request.httpMethod = spec.method
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        if let body = spec.body {
            request.httpBody = body
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        }
        return request
    }

    /// FastAPI errors are {"detail": "..."} or, for validation, {"detail": [{"msg": ...}]}.
    private struct ErrorBody: Decodable {
        struct Issue: Decodable { let msg: String }

        enum Detail: Decodable {
            case message(String)
            case issues([Issue])

            init(from decoder: Decoder) throws {
                let container = try decoder.singleValueContainer()
                if let message = try? container.decode(String.self) {
                    self = .message(message)
                } else {
                    self = .issues(try container.decode([Issue].self))
                }
            }
        }

        let detail: Detail
    }

    static func detail(from data: Data, status: Int) -> String {
        guard let body = try? JSONDecoder().decode(ErrorBody.self, from: data) else {
            return HTTPURLResponse.localizedString(forStatusCode: status).capitalized
        }
        switch body.detail {
        case let .message(message): return message
        case let .issues(issues): return issues.map { $0.msg.replacingOccurrences(of: "Value error, ", with: "") }.joined(separator: "\n")
        }
    }
}

/// A Strong or Hevy CSV export, sent as text.
private struct ImportBody: Encodable {
    var csv: String
    var unit: String
}

/// PATCH auth/me: the cosmetic class, "" to clear it.
private struct CharacterClassBody: Encodable {
    var characterClass: String
}
