import Foundation

struct HeartRatePayload: Codable {
    let profileId: String
    let bpm: Int
    let timestamp: String

    enum CodingKeys: String, CodingKey {
        case profileId = "profile_id"
        case bpm
        case timestamp
    }
}

struct HeartRateResponse: Codable {
    let profileId: String
    let bpm: Int?
    let timestamp: String?
    let ageSec: Int?
    let status: String

    enum CodingKeys: String, CodingKey {
        case profileId = "profile_id"
        case bpm
        case timestamp
        case ageSec = "age_sec"
        case status
    }
}
