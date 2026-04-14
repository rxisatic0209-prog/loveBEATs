# LoveBeats

## 产品定位和价值

LoveBeats 是一个「关系型 AI 对话 + 生理状态辅助信号」的产品原型。

它不是医疗工具，也不是健康监测产品。  
它的核心目标是：在恋人陪伴、角色扮演和亲密互动场景中，把 AI 从“只读文本”升级成“文本 + 心率弱信号”的多模态对话系统。

核心价值：

- 让 AI 不只根据用户输入的文字判断语境，还能结合心率变化理解互动节奏。
- 用结构化角色卡定义角色设定、回答风格和人格边界，减少 prompt 混乱。
- 把角色系统、agent 运行时、工具系统和心率能力拆开，便于后续迭代和替换。
- 支持 Pulsoid 作为真实心率来源，也支持本地写入调试，便于开发和联调。

## 产品实现架构

当前项目是一个纯 `Web + Backend` 架构：

- Web：后端内置聊天页面，用于创建角色、发送消息和体验对话。
- Backend：FastAPI + SQLite，负责角色持久化、prompt 拼接、LLM 调用、工具执行和日志记录。
- Heart Rate Provider：当前支持：
  - `local_cache`
  - `pulsoid`

运行时主链路：

1. 用户打开网页并创建角色。
2. 用户发送消息。
3. 后端根据 `role_id` 组装本轮 runtime。
4. 模型按需调用 `get_heart_rate`。
5. 工具从当前 provider 读取最近心率。
6. 模型结合文本上下文和心率弱信号生成回复。

心率链路：

- `Pulsoid -> backend provider -> heart_rate_cache -> get_heart_rate tool`
- 或 `调试写入接口 -> backend 存储 -> get_heart_rate tool`

## 产品使用说明

### 1. 克隆项目

```bash
git clone <your-repo-url>
cd loveBEATs
```

### 2. 创建并激活虚拟环境

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

### 3. 配置环境变量

复制环境变量示例文件：

```bash
cp /Users/rxie/Desktop/loveBEATs/backend/.env.example /Users/rxie/Desktop/loveBEATs/backend/.env
```

#### 3.1 最少必填项

如需启动基础聊天链路，至少需要在 [`/Users/rxie/Desktop/loveBEATs/backend/.env`](/Users/rxie/Desktop/loveBEATs/backend/.env) 中填写：

```env
DEEPSEEK_API_KEY=your_api_key
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL_ID=deepseek-chat
HEART_RATE_TOOL_PROVIDER=local_cache
```

说明：

- `DEEPSEEK_API_KEY`
  真实模型调用所需
- `LLM_BASE_URL`
  OpenAI-compatible 接口基地址
- `LLM_MODEL_ID`
  要使用的模型名
- `HEART_RATE_TOOL_PROVIDER=local_cache`
  表示暂不接入真实心率，仅使用本地缓存或调试写入

#### 3.2 接入 Pulsoid

如需接入真实心率，请将 `.env` 配置为：

```env
DEEPSEEK_API_KEY=your_api_key
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL_ID=deepseek-chat
HEART_RATE_TOOL_PROVIDER=pulsoid
PULSOID_API_BASE=https://dev.pulsoid.net
PULSOID_ACCESS_TOKEN=your_pulsoid_access_token
PULSOID_TIMEOUT_SECONDS=6
```

说明：

- `HEART_RATE_TOOL_PROVIDER=pulsoid`
  开启 Pulsoid provider
- `PULSOID_ACCESS_TOKEN`
  你的 Pulsoid token
- `PULSOID_API_BASE`
  默认保持 `https://dev.pulsoid.net` 即可

如果上述配置缺失或无效，聊天链路仍可运行，但心率工具无法读取真实数据。

### 4. 启动后端

有两种方式。

第一种，直接启动：

```bash
cd /Users/rxie/Desktop/loveBEATs/backend
source .venv/bin/activate
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

第二种，用项目脚本：

```bash
bash /Users/rxie/Desktop/loveBEATs/backend/scripts/run_backend.sh
```

### 5. 打开网页

默认地址是：

- 健康检查：`http://127.0.0.1:8000/health`
- 聊天页面：`http://127.0.0.1:8000/chat`
- 日志接口：`http://127.0.0.1:8000/v1/debug/logs`

访问地址规则如下：

- 如果后端按默认参数启动，也就是 `--host 127.0.0.1 --port 8000`，聊天页面地址固定为 `http://127.0.0.1:8000/chat`
- 如果修改了启动参数中的 host 或 port，比如改为 `0.0.0.0:9000`，访问地址也会同步变更

结论：

- 默认启动方式下，网页地址是固定的
- 从实现上看，网页地址由后端服务的 host 和 port 决定

### 6. 使用流程

进入 `/chat` 后，用户使用链路如下：

1. 填写角色卡
2. 保存角色
3. 输入消息
4. 进入对话
5. 如果模型判定有必要，会调用 `get_heart_rate`
6. 如果已配置 Pulsoid，工具会尝试读取真实心率
7. 如果未配置 Pulsoid，可通过调试接口写入心率

### 7. 无 Pulsoid 时的心率调试方式

可先写入一条测试心率：

`POST /v1/heart-rate/latest`

Body 示例：

```json
{
  "bpm": 92
}
```

随后返回聊天页面发送消息。  
如果模型触发 `get_heart_rate`，即可读取该条最新心率。

## 项目当前状态

当前已完成：

- 角色创建与持久化
- 角色级对话历史
- 结构化角色卡拼接 prompt
- 基础 agent runtime
- `get_heart_rate` 工具
- Pulsoid provider
- 本地调试心率写入
- 日志系统
- Web 聊天入口

当前默认假设：

- 单用户使用
- 不做账号系统
- 不做 iOS 客户端依赖
- 心率作为弱信号，不作为医学判断依据

## 排错与调试

排查问题时，优先检查以下入口：

- 健康检查：`/health`
- 聊天页面：`/chat`
- 日志接口：`/v1/debug/logs`
- 日志文件：[`/Users/rxie/Desktop/loveBEATs/backend/logs/app.log`](/Users/rxie/Desktop/loveBEATs/backend/logs/app.log)

常见问题：

- `.env` 没填模型 key
- `LLM_MODEL_ID` 不可用
- `PULSOID_ACCESS_TOKEN` 无效
- 后端没真正启动成功

如果模型配置不完整，系统会回退到 `mock-local`。  
这表示基础链路可用，但不代表真实模型已接通。
