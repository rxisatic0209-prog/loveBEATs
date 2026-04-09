import Foundation
import Combine

@MainActor
final class HeartRateSyncViewModel: ObservableObject {
    @Published var config = AppConfig()
    @Published var latestBPM: Int?
    @Published var latestTimestamp: Date?
    @Published var backendStatus: String = "Idle"
    @Published var permissionStatus: String = "Not Requested"
    @Published var errorMessage: String?
    @Published var isSyncing = false

    private let healthKitService = HealthKitHeartRateService()
    private let backendClient = BackendClient()

    func requestAuthorization() {
        Task {
            do {
                guard healthKitService.isAvailable() else {
                    permissionStatus = "HealthKit Unavailable"
                    return
                }
                try await healthKitService.requestAuthorization()
                permissionStatus = "Authorized"
                if let sample = try await healthKitService.fetchLatestHeartRate() {
                    latestBPM = sample.bpm
                    latestTimestamp = sample.timestamp
                }
            } catch {
                permissionStatus = "Authorization Failed"
                errorMessage = error.localizedDescription
            }
        }
    }

    func startSync() {
        guard !isSyncing else { return }
        isSyncing = true
        backendStatus = "Listening"
        errorMessage = nil

        healthKitService.startObserving { [weak self] sample in
            guard let self else { return }
            let baseURL = await MainActor.run { self.config.baseURL }
            let appUserID = await MainActor.run { self.config.appUserID }
            let payload = HeartRateUploadRequest(
                bpm: sample.bpm,
                timestamp: ISO8601DateFormatter().string(from: sample.timestamp)
            )
            await MainActor.run {
                self.latestBPM = sample.bpm
                self.latestTimestamp = sample.timestamp
                self.backendStatus = "Uploading"
            }
            do {
                let response = try await self.backendClient.uploadHeartRate(
                    baseURL: baseURL,
                    appUserID: appUserID,
                    payload: payload
                )
                await MainActor.run {
                    self.backendStatus = "Uploaded (\(response.status))"
                }
            } catch {
                await MainActor.run {
                    self.backendStatus = "Upload Failed"
                    self.errorMessage = error.localizedDescription
                }
            }
        }
    }

    func stopSync() {
        healthKitService.stopObserving()
        isSyncing = false
        backendStatus = "Stopped"
    }

    func uploadLatestOnce() {
        Task {
            do {
                guard let sample = try await healthKitService.fetchLatestHeartRate() else {
                    backendStatus = "No Heart Rate Sample"
                    return
                }
                latestBPM = sample.bpm
                latestTimestamp = sample.timestamp
                let payload = HeartRateUploadRequest(
                    bpm: sample.bpm,
                    timestamp: ISO8601DateFormatter().string(from: sample.timestamp)
                )
                let response = try await backendClient.uploadHeartRate(
                    baseURL: config.baseURL,
                    appUserID: config.appUserID,
                    payload: payload
                )
                backendStatus = "Uploaded (\(response.status))"
            } catch {
                backendStatus = "Upload Failed"
                errorMessage = error.localizedDescription
            }
        }
    }
}
