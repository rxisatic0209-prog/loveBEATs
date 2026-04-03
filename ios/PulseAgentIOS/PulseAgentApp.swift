import SwiftUI

@main
struct PulseAgentApp: App {
    @StateObject private var viewModel = HeartRateSyncViewModel()

    var body: some Scene {
        WindowGroup {
            ContentView(viewModel: viewModel)
        }
    }
}
