# LoveBeats

## 1. 产品定位和价值
LoveBeats 是一个「关系型 AI 对话 + 生理状态辅助信号」的产品原型。  
它的定位不是医疗工具，而是通过心率等弱信号，帮助 AI 在亲密对话里更好地把握节奏、语气和回应分寸。

核心价值：

- 把对话系统从“只看文本”升级为“文本 + 实时状态”的多信号交互。
- 统一角色卡（persona / role / agent）与运行时策略，支持长期可迭代。
- 心率链路采用 provider 抽象，便于在 `local_cache / Pulsoid / 未来数据源` 间切换。

## 2. 产品实现架构
LoveBeats 当前是三层结构：

- Web：聊天入口与角色配置入口（后端内置页面）。
- Backend（FastAPI）：负责角色编排、LLM 调用、工具执行、心率数据存储与读取。
- 数据源 Provider：当前支持本地缓存与 Pulsoid latest HTTP。

运行时链路：

1. 用户在 Web 发起一轮对话。
2. Backend 组装 turn runtime（role + persona + policy + recent messages + tools）。
3. 当模型请求 `get_heart_rate` 时，工具从当前 provider 读取最近心率。
4. 模型结合文本语境和心率状态生成回复。

心率数据链路：

- `Pulsoid -> backend provider -> heart_rate_cache / app_user_heart_rate_events -> get_heart_rate tool`
- 或 `外部写入接口 -> backend 存储 -> get_heart_rate tool`

## 3. 产品使用方法
### 3.1 启动后端
```bash
cd /Users/rxie/Desktop/loveBEATs/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

### 3.2 配置环境变量
```bash
cd /Users/rxie/Desktop/loveBEATs/backend
cp .env.example .env
```

`.env` 至少配置：

- `LLM_API_KEY` 或 `DEEPSEEK_API_KEY`
- `LLM_BASE_URL`
- `LLM_MODEL_ID`
- `HEART_RATE_TOOL_PROVIDER`（`local_cache` 或 `pulsoid`）

如果使用 Pulsoid，再补：

- `PULSOID_API_BASE=https://dev.pulsoid.net`
- `PULSOID_ACCESS_TOKEN=...`
- `PULSOID_TIMEOUT_SECONDS=6`

### 3.3 访问入口

- 健康检查：`http://127.0.0.1:8000/health`
- 聊天页面：`http://127.0.0.1:8000/chat`
- Provider 信息：`http://127.0.0.1:8000/v1/tools/heart-rate/provider`

## 4. 产品进度
已完成：

- 角色系统（persona / role / agent）和运行时组装。
- `get_heart_rate` 工具接入与心率状态（fresh/recent/stale/unavailable）判定。
- 心率数据持久化（最新值缓存 + 历史事件）。
- Pulsoid provider 基础链路与本地缓存回退能力。
- Web 内置聊天页与基础调试接口（`turns/preview`、`turns/debug`）。

进行中：

- Provider 观测与错误诊断（更细粒度日志/告警）。
- 工具调用策略优化（何时调用心率工具的动态判断）。

下一步：

- 完善部署与运维（云端一键部署、配置模板、安全收敛）。
- 增强会话复盘能力（结合心率与对话历史的结构化摘要）。
