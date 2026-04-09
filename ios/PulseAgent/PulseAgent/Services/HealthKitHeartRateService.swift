import Foundation
import HealthKit

struct HeartRateSample {
    let bpm: Int
    let timestamp: Date
}

final class HealthKitHeartRateService {
    private let healthStore = HKHealthStore()
    private let heartRateType = HKQuantityType.quantityType(forIdentifier: .heartRate)!

    private var observerQuery: HKObserverQuery?
    private var anchoredQuery: HKAnchoredObjectQuery?
    private var anchor: HKQueryAnchor?
    private var observationStartDate: Date?

    func isAvailable() -> Bool {
        HKHealthStore.isHealthDataAvailable()
    }

    func requestAuthorization() async throws {
        try await healthStore.requestAuthorization(toShare: [], read: [heartRateType])
    }

    func fetchLatestHeartRate() async throws -> HeartRateSample? {
        let sort = NSSortDescriptor(key: HKSampleSortIdentifierEndDate, ascending: false)
        return try await withCheckedThrowingContinuation { continuation in
            let query = HKSampleQuery(
                sampleType: heartRateType,
                predicate: nil,
                limit: 1,
                sortDescriptors: [sort]
            ) { _, samples, error in
                if let error {
                    continuation.resume(throwing: error)
                    return
                }
                guard
                    let quantitySample = samples?.first as? HKQuantitySample
                else {
                    continuation.resume(returning: nil)
                    return
                }
                continuation.resume(returning: Self.toHeartRateSample(quantitySample))
            }
            self.healthStore.execute(query)
        }
    }

    func startObserving(onUpdate: @escaping @Sendable (HeartRateSample) async -> Void) {
        stopObserving()
        anchor = nil
        observationStartDate = Date()
        let predicate = HKQuery.predicateForSamples(
            withStart: observationStartDate,
            end: nil,
            options: .strictStartDate
        )

        observerQuery = HKObserverQuery(sampleType: heartRateType, predicate: predicate) { [weak self] _, completionHandler, error in
            guard error == nil, let self else {
                completionHandler()
                return
            }
            self.runAnchoredQuery(predicate: predicate, onUpdate: onUpdate)
            completionHandler()
        }

        if let observerQuery {
            healthStore.execute(observerQuery)
            healthStore.enableBackgroundDelivery(for: heartRateType, frequency: .immediate) { _, _ in }
        }

        runAnchoredQuery(predicate: predicate, onUpdate: onUpdate)
    }

    func stopObserving() {
        if let observerQuery {
            healthStore.stop(observerQuery)
        }
        if let anchoredQuery {
            healthStore.stop(anchoredQuery)
        }
        observerQuery = nil
        anchoredQuery = nil
        observationStartDate = nil
    }

    private func runAnchoredQuery(
        predicate: NSPredicate?,
        onUpdate: @escaping @Sendable (HeartRateSample) async -> Void
    ) {
        let query = HKAnchoredObjectQuery(
            type: heartRateType,
            predicate: predicate,
            anchor: anchor,
            limit: HKObjectQueryNoLimit
        ) { [weak self] _, samples, _, newAnchor, error in
            guard error == nil, let self else { return }
            self.anchor = newAnchor
            Task {
                for sample in samples?.compactMap({ $0 as? HKQuantitySample }) ?? [] {
                    let value = Self.toHeartRateSample(sample)
                    await onUpdate(value)
                }
            }
        }
        anchoredQuery = query
        healthStore.execute(query)
    }

    private nonisolated static func toHeartRateSample(_ sample: HKQuantitySample) -> HeartRateSample {
        let unit = HKUnit.count().unitDivided(by: .minute())
        let bpm = Int(sample.quantity.doubleValue(for: unit).rounded())
        return HeartRateSample(bpm: bpm, timestamp: sample.endDate)
    }
}
