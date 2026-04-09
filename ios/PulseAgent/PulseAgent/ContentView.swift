//
//  ContentView.swift
//  PulseAgent
//
//  Created by 谢染 on 2026/4/8.
//

import SwiftUI

struct ContentView: View {
    @ObservedObject var viewModel: HeartRateSyncViewModel

    var body: some View {
        HealthSyncView(viewModel: viewModel)
    }
}

private struct HealthSyncView: View {
    @ObservedObject var viewModel: HeartRateSyncViewModel
    @FocusState private var isBaseURLFocused: Bool

    var body: some View {
        NavigationStack {
            Form {
                Section("定位") {
                    Text("这个 App 只负责 HealthKit 心率同步。聊天前端独立运行在 Web 端，不再内嵌在 iOS 内。")
                        .foregroundStyle(.secondary)
                }

                Section("服务端地址") {
                    TextField("http://192.168.1.23:8000", text: $viewModel.config.baseURL)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                        .keyboardType(.URL)
                        .submitLabel(.done)
                        .focused($isBaseURLFocused)

                    Text("真机要填运行 backend 的那台电脑的局域网地址，不是手机自己的地址。")
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                }

                Section("同步状态") {
                    LabeledContent("Permission", value: viewModel.permissionStatus)
                    LabeledContent("Latest BPM", value: viewModel.latestBPM.map(String.init) ?? "--")
                    LabeledContent("Timestamp", value: formatted(date: viewModel.latestTimestamp))
                    LabeledContent("Backend Status", value: viewModel.backendStatus)
                }

                Section("HealthKit") {
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
            .navigationTitle("心率同步")
            .toolbar {
                ToolbarItemGroup(placement: .keyboard) {
                    Spacer()
                    Button("完成") {
                        isBaseURLFocused = false
                    }
                }
            }
        }
    }

    private func formatted(date: Date?) -> String {
        guard let date else { return "--" }
        return date.formatted(date: .omitted, time: .standard)
    }
}
