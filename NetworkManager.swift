// ============================================================
// NetworkManager.swift — добавьте в Xcode проект BabyTrack
// Замените SampleData.nannies на вызовы API
// ============================================================

import Foundation

// MARK: - Конфигурация
struct API {
    // ⚠️ Замените на ваш Railway URL после деплоя
    static let baseURL = "https://your-app.railway.app"
    
    // Для локальной разработки:
    // static let baseURL = "http://localhost:8000"
}

// MARK: - Errors
enum APIError: Error, LocalizedError {
    case invalidURL
    case noData
    case decodingError(Error)
    case serverError(Int, String)
    case unauthorized
    
    var errorDescription: String? {
        switch self {
        case .unauthorized: return "Необходима авторизация"
        case .serverError(_, let msg): return msg
        case .decodingError(let e): return "Ошибка данных: \(e)"
        default: return "Ошибка соединения"
        }
    }
}

// MARK: - Token Storage
class TokenStorage {
    static let shared = TokenStorage()
    private let key = "babytrack_token"
    
    var token: String? {
        get { UserDefaults.standard.string(forKey: key) }
        set { UserDefaults.standard.set(newValue, forKey: key) }
    }
    
    func clear() { token = nil }
}

// MARK: - Network Manager
class NetworkManager {
    static let shared = NetworkManager()
    private let decoder: JSONDecoder
    
    init() {
        decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        let fmt = ISO8601DateFormatter()
        fmt.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        decoder.dateDecodingStrategy = .custom { decoder in
            let str = try decoder.singleValueContainer().decode(String.self)
            return fmt.date(from: str) ?? Date()
        }
    }
    
    // MARK: - Generic Request
    private func request<T: Decodable>(
        _ endpoint: String,
        method: String = "GET",
        body: Encodable? = nil,
        requiresAuth: Bool = true
    ) async throws -> T {
        guard let url = URL(string: API.baseURL + endpoint) else {
            throw APIError.invalidURL
        }
        
        var req = URLRequest(url: url)
        req.httpMethod = method
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        if requiresAuth {
            guard let token = TokenStorage.shared.token else {
                throw APIError.unauthorized
            }
            req.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        
        if let body = body {
            req.httpBody = try JSONEncoder().encode(body)
        }
        
        let (data, response) = try await URLSession.shared.data(for: req)
        
        if let http = response as? HTTPURLResponse {
            if http.statusCode == 401 { throw APIError.unauthorized }
            if http.statusCode >= 400 {
                let msg = (try? JSONDecoder().decode([String: String].self, from: data))?["detail"] ?? "Ошибка сервера"
                throw APIError.serverError(http.statusCode, msg)
            }
        }
        
        do {
            return try decoder.decode(T.self, from: data)
        } catch {
            throw APIError.decodingError(error)
        }
    }
}

// MARK: - Auth API
extension NetworkManager {
    struct OTPRequest: Encodable { let phone: String }
    struct VerifyRequest: Encodable { let phone: String; let code: String; let name: String? }
    struct TokenResponse: Decodable {
        let accessToken: String
        let userId: String
        let isNewUser: Bool
    }
    
    func sendOTP(phone: String) async throws {
        struct Empty: Decodable {}
        let _: Empty = try await request("/auth/send-otp", method: "POST",
                                         body: OTPRequest(phone: phone), requiresAuth: false)
    }
    
    func verifyOTP(phone: String, code: String, name: String? = nil) async throws -> TokenResponse {
        let resp: TokenResponse = try await request("/auth/verify-otp", method: "POST",
                                                     body: VerifyRequest(phone: phone, code: code, name: name),
                                                     requiresAuth: false)
        TokenStorage.shared.token = resp.accessToken
        return resp
    }
}

// MARK: - Nannies API
extension NetworkManager {
    struct NannyDTO: Decodable, Identifiable {
        let id: String
        let name: String
        let age: Int?
        let bio: String?
        let avatarUrl: String?
        let hourlyRate: Int
        let experienceYears: Int
        let city: String
        let district: String?
        let specialties: [String]
        let languages: [String]
        let workDays: [String]
        let rating: Double
        let reviewCount: Int
        let isVerified: Bool
        let isAvailable: Bool
        let distanceKm: Double?
    }
    
    struct NannyListDTO: Decodable {
        let nannies: [NannyDTO]
        let total: Int
        let page: Int
    }
    
    func getNannies(
        sortBy: String = "rating",
        minRating: Double? = nil,
        maxRate: Int? = nil,
        isVerified: Bool? = nil,
        isAvailable: Bool? = nil,
        page: Int = 1
    ) async throws -> NannyListDTO {
        var params = "?sort_by=\(sortBy)&page=\(page)"
        if let r = minRating { params += "&min_rating=\(r)" }
        if let r = maxRate { params += "&max_rate=\(r)" }
        if let v = isVerified { params += "&is_verified=\(v)" }
        if let a = isAvailable { params += "&is_available=\(a)" }
        
        return try await request("/nannies\(params)", requiresAuth: false)
    }
    
    func getNanny(id: String) async throws -> NannyDTO {
        return try await request("/nannies/\(id)", requiresAuth: false)
    }
    
    func toggleFavorite(nannyId: String) async throws -> Bool {
        struct Resp: Decodable { let isFavorite: Bool }
        let r: Resp = try await request("/nannies/\(nannyId)/favorite", method: "POST")
        return r.isFavorite
    }
    
    func getFavorites() async throws -> [NannyDTO] {
        return try await request("/nannies/me/favorites")
    }
}

// MARK: - Bookings API
extension NetworkManager {
    struct BookingCreateDTO: Encodable {
        let nannyId: String
        let date: String          // ISO8601
        let startTime: String
        let endTime: String
        let childrenCount: Int
        let notes: String?
    }
    
    struct BookingDTO: Decodable, Identifiable {
        let id: String
        let nanny: NannyDTO
        let date: Date
        let startTime: String
        let endTime: String
        let childrenCount: Int
        let status: String
        let totalCost: Int?
        let notes: String?
    }
    
    func createBooking(
        nannyId: String,
        date: Date,
        startTime: String,
        endTime: String,
        childrenCount: Int,
        notes: String? = nil
    ) async throws -> BookingDTO {
        let fmt = ISO8601DateFormatter()
        let body = BookingCreateDTO(
            nannyId: nannyId,
            date: fmt.string(from: date),
            startTime: startTime,
            endTime: endTime,
            childrenCount: childrenCount,
            notes: notes
        )
        return try await request("/bookings", method: "POST", body: body)
    }
    
    func getMyBookings(status: String? = nil) async throws -> [BookingDTO] {
        var path = "/bookings"
        if let s = status { path += "?status_filter=\(s)" }
        return try await request(path)
    }
    
    func cancelBooking(id: String) async throws -> BookingDTO {
        struct Body: Encodable { let status: String }
        return try await request("/bookings/\(id)/status", method: "PATCH",
                                  body: Body(status: "cancelled"))
    }
}

// MARK: - Chat API
extension NetworkManager {
    struct MessageDTO: Decodable, Identifiable {
        let id: String
        let chatId: String
        let senderId: String
        let type: String
        let text: String?
        let isRead: Bool
        let createdAt: Date
    }
    
    func getMessages(chatId: String) async throws -> [MessageDTO] {
        return try await request("/chats/\(chatId)/messages")
    }
    
    func sendMessage(chatId: String, text: String) async throws -> MessageDTO {
        struct Body: Encodable { let text: String }
        return try await request("/chats/\(chatId)/messages", method: "POST", body: Body(text: text))
    }
}

// MARK: - WebSocket Chat
class ChatWebSocket: NSObject, URLSessionWebSocketDelegate {
    var onMessage: ((MessageDTO) -> Void)?
    private var task: URLSessionWebSocketTask?
    
    func connect(chatId: String) {
        guard let token = TokenStorage.shared.token,
              let url = URL(string: "\(API.baseURL.replacingOccurrences(of: "https", with: "wss"))/chats/\(chatId)/ws?token=\(token)")
        else { return }
        
        let session = URLSession(configuration: .default, delegate: self, delegateQueue: nil)
        task = session.webSocketTask(with: url)
        task?.resume()
        receiveLoop()
    }
    
    func send(text: String) {
        task?.send(.string(#"{"text":"\#(text)","type":"text"}"#)) { _ in }
    }
    
    func disconnect() {
        task?.cancel(with: .goingAway, reason: nil)
    }
    
    private func receiveLoop() {
        task?.receive { [weak self] result in
            switch result {
            case .success(let msg):
                if case .string(let str) = msg,
                   let data = str.data(using: .utf8),
                   let dto = try? JSONDecoder().decode(MessageDTO.self, from: data) {
                    DispatchQueue.main.async { self?.onMessage?(dto) }
                }
                self?.receiveLoop()
            case .failure:
                break
            }
        }
    }
}

// MARK: - Usage Example
/*
 // В вашем ViewModel:

 @MainActor
 class NannyListViewModel: ObservableObject {
     @Published var nannies: [NetworkManager.NannyDTO] = []
     @Published var isLoading = false
     @Published var error: String?

     func load() async {
         isLoading = true
         do {
             let result = try await NetworkManager.shared.getNannies()
             nannies = result.nannies
         } catch {
             self.error = error.localizedDescription
         }
         isLoading = false
     }
 }

 // В SwiftUI View:
 .task { await viewModel.load() }
*/
