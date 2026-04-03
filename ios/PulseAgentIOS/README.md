# PulseAgent iOS Skeleton

这是一套最小 iOS 侧代码骨架，目标是打通：

- HealthKit 权限申请
- 读取最新心率
- 监听心率更新
- 上传到现有后端 `POST /v1/heart-rate/latest`

当前目录不是完整 `.xcodeproj`，因为本机没有可用的 Xcode 环境可生成和编译工程。
但这些文件可以直接放进一个新的 SwiftUI iOS App 工程里使用。

当前已经覆盖的心率链路：

- 请求 HealthKit 读取权限
- 拉取最新心率
- 监听后续心率样本
- 上传到 `POST /v1/heart-rate/latest`

当前还没覆盖的部分：

- 完整聊天 UI
- 后台任务和掉线重试
- 真机编译验证

## 需要的能力

- iOS App target
- HealthKit capability
- `NSHealthShareUsageDescription`

## 最小接入步骤

1. 在 Xcode 创建一个新的 iOS App 工程
2. 将本目录下的 Swift 文件拖入工程
3. 打开 Signing & Capabilities，添加 `HealthKit`
4. 在 `Info.plist` 中加入：
   - `NSHealthShareUsageDescription`
5. 将示例 entitlements 内容合并到 target 的 entitlements
6. 启动后在界面里填写：
   - `Backend Base URL`
   - `Profile ID`
7. 点击 `Authorize HealthKit`
8. 点击 `Start Sync`

## 当前限制

- 仅处理心率读取和上传，不包含聊天前端
- 默认按最新样本上传，没有复杂重试队列
- 后台持续同步能力还需要结合真机和 target 能力继续调
