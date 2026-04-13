//
//  LoveBeatsApp.swift
//  LoveBeats
//
//  Created by 谢染 on 2026/4/8.
//

import SwiftUI

@main
struct LoveBeatsApp: App {
    @StateObject private var viewModel = HeartRateSyncViewModel()

    var body: some Scene {
        WindowGroup {
            ContentView(viewModel: viewModel)
        }
    }
}
