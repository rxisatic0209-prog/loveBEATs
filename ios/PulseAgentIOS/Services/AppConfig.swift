import Foundation

@MainActor
final class AppConfig: ObservableObject {
    @Published var baseURL: String {
        didSet { UserDefaults.standard.set(baseURL, forKey: Keys.baseURL) }
    }

    @Published var profileID: String {
        didSet { UserDefaults.standard.set(profileID, forKey: Keys.profileID) }
    }

    init() {
        self.baseURL = UserDefaults.standard.string(forKey: Keys.baseURL) ?? "http://127.0.0.1:8000"
        self.profileID = UserDefaults.standard.string(forKey: Keys.profileID) ?? "ios_demo_profile"
    }
}

private enum Keys {
    static let baseURL = "pulseagent.base_url"
    static let profileID = "pulseagent.profile_id"
}
