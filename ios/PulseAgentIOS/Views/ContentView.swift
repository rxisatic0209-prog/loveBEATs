import SwiftUI

struct ContentView: View {
    @ObservedObject var viewModel: HeartRateSyncViewModel

    var body: some View {
        NavigationStack {
            Form {
                Section("Backend") {
                    TextField("Backend Base URL", text: $viewModel.config.baseURL)
                        .textInputAutocapitalization(.never)
                        .keyboardType(.URL)
                        .autocorrectionDisabled()

                    TextField("Profile ID", text: $viewModel.config.profileID)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                }

                Section("HealthKit") {
                    LabeledContent("Permission", value: viewModel.permissionStatus)
                    LabeledContent("Latest BPM", value: viewModel.latestBPM.map(String.init) ?? "--")
                    LabeledContent("Timestamp", value: formatted(date: viewModel.latestTimestamp))
                    LabeledContent("Backend Status", value: viewModel.backendStatus)

                    Button("Authorize HealthKit") {
                        viewModel.requestAuthorization()
                    }

                    Button("Upload Latest Once") {
                        viewModel.uploadLatestOnce()
                    }

                    Button(viewModel.isSyncing ? "Stop Sync" : "Start Sync") {
                        if viewModel.isSyncing {
                            viewModel.stopSync()
                        } else {
                            viewModel.startSync()
                        }
                    }
                }

                if let errorMessage = viewModel.errorMessage {
                    Section("Error") {
                        Text(errorMessage)
                            .foregroundStyle(.red)
                    }
                }
            }
            .navigationTitle("PulseAgent")
        }
    }

    private func formatted(date: Date?) -> String {
        guard let date else { return "--" }
        return date.formatted(date: .omitted, time: .standard)
    }
}
