//
//  ContentView.swift
//  LoveBeats
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

                Section {
                    Button("清空日志") {
                        viewModel.clearLogs()
                    }
                } header: {
                    Text("运行日志")
                } footer: {
                    Text("这里会显示授权、读取、上传和监听过程中的关键事件，方便排查问题。")
                }

                if viewModel.logs.isEmpty {
                    Section("日志内容") {
                        Text("还没有日志。操作一次授权、上传或开始同步后，这里会出现记录。")
                            .foregroundStyle(.secondary)
                    }
                } else {
                    Section("日志内容") {
                        ForEach(viewModel.logs) { entry in
                            VStack(alignment: .leading, spacing: 4) {
                                HStack {
                                    Text(entry.level.rawValue)
                                        .font(.caption.monospaced())
                                        .foregroundStyle(entry.level == .error ? .red : .secondary)
                                    Spacer()
                                    Text(entry.timestamp.formatted(date: .omitted, time: .standard))
                                        .font(.caption)
                                        .foregroundStyle(.secondary)
                                }
                                Text(entry.message)
                                    .font(.footnote)
                                    .textSelection(.enabled)
                            }
                            .padding(.vertical, 2)
                        }
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
