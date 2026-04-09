import Foundation
import Combine

@MainActor
final class AppConfig: ObservableObject {
    @Published var baseURL: String {
        didSet {
            UserDefaults.standard.set(baseURL.trimmingCharacters(in: .whitespacesAndNewlines), forKey: Keys.baseURL)
        }
    }

    @Published var appUserID: String {
        didSet { UserDefaults.standard.set(appUserID, forKey: Keys.appUserID) }
    }

    init() {
        self.baseURL =
            UserDefaults.standard.string(forKey: Keys.baseURL)
            ?? AppEnvironment.backendBaseURL
        self.appUserID =
            UserDefaults.standard.string(forKey: Keys.appUserID)
            ?? UserDefaults.standard.string(forKey: Keys.legacyProfileID)
            ?? Self.generateID(prefix: "app_user_ios")
    }

    private static func generateID(prefix: String) -> String {
        "\(prefix)_\(UUID().uuidString.replacingOccurrences(of: "-", with: "").prefix(12))"
    }
}

private enum AppEnvironment {
    static let backendBaseURL = "http://127.0.0.1:8000"
}

private enum Keys {
    static let baseURL = "pulseagent.base_url"
    static let appUserID = "pulseagent.app_user_id"
    static let legacyProfileID = "pulseagent.profile_id"
}
