import Foundation

enum BackendClientError: Error, LocalizedError {
    case invalidBaseURL
    case invalidResponse

    var errorDescription: String? {
        switch self {
        case .invalidBaseURL:
            return "Backend Base URL 无效。"
        case .invalidResponse:
            return "服务端响应无效。"
        }
    }
}

struct BackendClient {
    func uploadHeartRate(baseURL: String, payload: HeartRatePayload) async throws -> HeartRateResponse {
        guard let url = URL(string: baseURL + "/v1/heart-rate/latest") else {
            throw BackendClientError.invalidBaseURL
        }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONEncoder().encode(payload)

        let (data, response) = try await URLSession.shared.data(for: request)
        guard let httpResponse = response as? HTTPURLResponse, 200 ..< 300 ~= httpResponse.statusCode else {
            throw BackendClientError.invalidResponse
        }
        return try JSONDecoder().decode(HeartRateResponse.self, from: data)
    }
}
