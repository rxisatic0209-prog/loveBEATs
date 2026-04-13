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
            ?? AppEnvironment.defaultAppUserID
    }
}

private enum AppEnvironment {
    static let backendBaseURL = "http://127.0.0.1:8000"
    static let defaultAppUserID = "local_app_user"
}

private enum Keys {
    static let baseURL = "LoveBeats.base_url"
    static let appUserID = "LoveBeats.app_user_id"
    static let legacyProfileID = "LoveBeats.profile_id"
}
