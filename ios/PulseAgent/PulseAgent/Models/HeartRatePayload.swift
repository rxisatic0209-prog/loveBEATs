import Foundation

struct HeartRateUploadRequest: Codable {
    let bpm: Int
    let timestamp: String
}

struct HeartRateResponse: Codable {
    let appUserId: String?
    let profileId: String
    let bpm: Int?
    let timestamp: String?
    let ageSec: Int?
    let status: String

    enum CodingKeys: String, CodingKey {
        case appUserId = "app_user_id"
        case profileId = "profile_id"
        case bpm
        case timestamp
        case ageSec = "age_sec"
        case status
    }
}
