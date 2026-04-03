# Shortcuts 心率桥接方案

目标：不开发 iOS App，也能把 iPhone/Apple Watch 的心率同步到当前后端。

## 适用场景

- 不想做原生 iOS 客户端
- Mac 上没有可用的 Xcode 环境
- 先验证“聊天 + 心率上下文”这条链路

## 核心思路

用 iPhone 上的 `快捷指令 Shortcuts` 做桥：

1. 从健康数据里读取最近一次心率
2. 取出 BPM 和时间
3. 调用后端 `POST /v1/heart-rate/latest`

聊天前端依然可以是网页。

## 你需要的后端地址

如果手机和电脑在同一个 Wi‑Fi 下，不要填 `127.0.0.1`，要填电脑局域网 IP，例如：

```text
http://192.168.1.23:8000
```

## 快捷指令动作顺序

建议新建一个快捷指令，名字例如：

`Sync Heart Rate to PulseAgent`

动作顺序：

1. `Find Health Samples`
   - 类型选 `Heart Rate`
   - 排序选 `Latest First`
   - Limit 设为 `1`

2. `Get Details of Health Samples`
   - 取 `Value`

3. 再加一个 `Get Details of Health Samples`
   - 取 `End Date`

4. `Text`
   - 手动拼 JSON：

```json
{
  "profile_id": "your_profile_id",
  "bpm": VALUE_HERE,
  "timestamp": "DATE_HERE"
}
```

5. `Get Contents of URL`
   - URL:

```text
http://YOUR_LAN_IP:8000/v1/heart-rate/latest
```

   - Method: `POST`
   - Request Body: `JSON`
   - Headers:
     - `Content-Type: application/json`

如果你不想手写 JSON，也可以用 `Dictionary` 动作构造：

- `profile_id`
- `bpm`
- `timestamp`

然后把这个 Dictionary 传给 `Get Contents of URL`。

## 推荐两个版本

### 1. 手动同步版

手动点击快捷指令执行。

优点：

- 最稳定
- 最容易先跑通

### 2. Apple Watch 触发版

把快捷指令打开 `Show on Apple Watch`，然后在手表 Shortcuts 里点。

优点：

- 操作更接近“设备感知”

限制：

- 不是严格后台实时推送
- 需要你主动触发

## 最小联调检查

先启动后端：

```bash
cd /Users/rxie/Desktop/loveBEATs/backend
make run
```

然后在手机执行快捷指令，再检查：

```bash
curl http://127.0.0.1:8000/v1/heart-rate/latest/your_profile_id
```

如果你是在手机上调，记得把 `127.0.0.1` 换成电脑局域网 IP。

返回里看到这种结构就通了：

```json
{
  "profile_id": "your_profile_id",
  "bpm": 92,
  "timestamp": "...",
  "age_sec": 3,
  "status": "fresh"
}
```

## 当前限制

- Shortcuts 不是持续后台实时流
- 自动化触发能力有限，不是“心率变化即触发”
- 适合 MVP 验证，不适合当最终正式方案
