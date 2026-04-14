# Backend

## 产品定位和价值

后端是 LoveBeats 的核心运行时。

它负责：

- 持久化角色和对话历史
- 组装 system prompt 和 persona prompt
- 调用真实 LLM
- 注册和执行工具
- 维护全局心率缓存和角色上下文心率记录

该后端并非通用聊天平台，而是服务于「亲密关系角色扮演 + 心率弱信号辅助」这一明确产品场景。

## 产品实现架构

当前后端由四块组成：

- FastAPI API 层
- SQLite 持久化层
- Agent runtime 层
- Tool/provider 层

心率能力现在是单用户、全局最近值模型：

- 不做账号系统
- 不暴露 `user_id`
- `get_heart_rate` 直接读取当前 provider 对应的最近心率

## 产品使用说明

### 1. 安装

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

### 2. 环境变量

```bash
cp .env.example .env
```

#### 基础聊天链路

```env
DEEPSEEK_API_KEY=your_api_key
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL_ID=deepseek-chat
HEART_RATE_TOOL_PROVIDER=local_cache
```

#### Pulsoid 接入

```env
DEEPSEEK_API_KEY=your_api_key
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL_ID=deepseek-chat
HEART_RATE_TOOL_PROVIDER=pulsoid
PULSOID_API_BASE=https://dev.pulsoid.net
PULSOID_ACCESS_TOKEN=your_pulsoid_access_token
PULSOID_TIMEOUT_SECONDS=6
```

### 3. 启动

```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

或使用项目脚本：

```bash
bash scripts/run_backend.sh
```

### 4. 访问地址

默认地址：

- `http://127.0.0.1:8000/health`
- `http://127.0.0.1:8000/chat`
- `http://127.0.0.1:8000/v1/debug/logs`

如果启动命令中的 host 或 port 发生变化，访问地址也会同步变化。

## 关键接口

- `GET /health`
- `GET /chat`
- `POST /v1/roles`
- `GET /v1/roles`
- `GET /v1/roles/{role_id}`
- `GET /v1/roles/{role_id}/history`
- `POST /v1/chat/send`
- `POST /v1/turns/preview`
- `POST /v1/turns/debug`
- `POST /v1/heart-rate/latest`
- `GET /v1/heart-rate/latest`
- `GET /v1/heart-rate/history`
- `POST /v1/roles/{role_id}/heart-rate`
- `GET /v1/roles/{role_id}/heart-rate/latest`
- `GET /v1/roles/{role_id}/heart-rate/history`
- `GET /v1/tools/heart-rate/provider`

## 排错与调试

- 日志接口：`GET /v1/debug/logs`
- 日志文件：`logs/app.log`

如果模型配置不完整，系统会使用 `mock-local`。这表示后端基础链路正常，但真实模型尚未接通。
