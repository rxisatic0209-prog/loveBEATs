import Foundation

enum BackendClientError: Error, LocalizedError {
    case invalidBaseURL
    case invalidResponse
    case localServerUnreachableFromDevice
    case network(URLError)

    var errorDescription: String? {
        switch self {
        case .invalidBaseURL:
            return "当前填写的 backend 地址无效。"
        case .invalidResponse:
            return "服务端响应无效。"
        case .localServerUnreachableFromDevice:
            return "真机无法访问当前本地地址。请改成运行 backend 的那台电脑的局域网地址。"
        case .network(let error):
            return "连接服务端失败：\(error.localizedDescription)"
        }
    }
}

struct BackendClient {
    func uploadHeartRate(baseURL: String, appUserID: String, payload: HeartRateUploadRequest) async throws -> HeartRateResponse {
        let url = try appUserURL(baseURL: baseURL, appUserID: appUserID, path: "/heart-rate/latest")
        return try await send(url: url, method: "POST", body: payload, responseType: HeartRateResponse.self)
    }

    private func appUserURL(baseURL: String, appUserID: String, path: String) throws -> URL {
        guard let encodedUserID = appUserID.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed),
              let url = URL(string: baseURL + "/v1/app-users/\(encodedUserID)\(path)") else {
            throw BackendClientError.invalidBaseURL
        }
        try ensureReachableHost(url)
        return url
    }

    private func ensureReachableHost(_ url: URL) throws {
#if !targetEnvironment(simulator)
        if let host = url.host?.lowercased(), host == "127.0.0.1" || host == "localhost" {
            throw BackendClientError.localServerUnreachableFromDevice
        }
#endif
    }

    private func send<Body: Encodable, Response: Decodable>(
        url: URL,
        method: String,
        body: Body,
        responseType: Response.Type
    ) async throws -> Response {
        var request = URLRequest(url: url)
        request.httpMethod = method
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONEncoder().encode(body)
        return try await perform(request: request, responseType: responseType)
    }

    private func perform<Response: Decodable>(
        request: URLRequest,
        responseType: Response.Type
    ) async throws -> Response {
        let data: Data
        let response: URLResponse
        do {
            (data, response) = try await URLSession.shared.data(for: request)
        } catch let error as URLError {
            throw BackendClientError.network(error)
        }
        guard let httpResponse = response as? HTTPURLResponse, 200 ..< 300 ~= httpResponse.statusCode else {
            throw BackendClientError.invalidResponse
        }
        return try JSONDecoder().decode(responseType, from: data)
    }
}
