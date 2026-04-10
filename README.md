# LoveBeats MVP

当前仓库已经能跑通三条主链路：

- Web 聊天前端
- persona / agent / session 后端平台
- iOS HealthKit 心率同步器

## 当前范围

- 中文聊天
- 当前会话窗口记忆
- 结构化 persona 编译
- persona 模板与 agent 配置持久化
- 最新心率缓存与新鲜度判断
- 单次 tool calling runtime
- OpenAI 兼容模型接入
- 独立 Web 聊天页
- 独立 iOS 心率同步工具

## 当前路线

项目已经从“iOS 内嵌 Web 聊天”回收为更解耦的结构：

- Web 负责用户的人设输入和聊天交互
- Backend 负责 persona 编译、session、LLM、心率工具
- iOS 只负责 HealthKit 权限和心率同步

## 目录

- `backend/` FastAPI 服务，包含 `chat` 内置体验页
- `ios/PulseAgent/` 可编译的 SwiftUI + HealthKit 心率同步工程

## 快速启动

```bash
cd /Users/rxie/Desktop/loveBEATs/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
uvicorn app.main:app --reload
```

服务默认启动在 `http://127.0.0.1:8000`。

启动后可直接打开：

```text
自己的网址
```

## 主要接口

- `GET /health`
- `GET /chat`
- `GET /v1/agent/scaffold`
- `POST /v1/turns/preview`
- `POST /v1/turns/debug`
- `POST /v1/sessions`
- `GET /v1/sessions/{session_id}`
- `GET /v1/sessions/{session_id}/history`
- `POST /v1/persona/compile`
- `POST /v1/heart-rate/latest`
- `POST /v1/chat/send`

## 当前分层

- `Scaffold Layer`
  平台固定规则、base system prompt、tool registry、安全规则
- `Compiler Layer`
  persona 和模型配置转成运行时可用内容
- `Agent Runtime Layer`
  每轮请求实例化 `turn runtime = session + persona + tools + recent messages + policy`
- `Execution Layer`
  真正调用 LLM、处理 tool call、写回消息

`/v1/turns/preview` 返回本轮 runtime 结构，`/v1/turns/debug` 会额外返回 prompt messages、LLM 配置摘要和警告信息，方便调试。

## 推荐调用顺序

1. `POST /v1/sessions`
2. `POST /v1/heart-rate/latest`
3. `POST /v1/chat/send`
4. `GET /v1/sessions/{session_id}/history`

`/v1/chat/send` 在 session 已创建后，可以不重复传 `persona_text`。

## 环境变量

```bash
cd backend
cp .env.example .env
# 然后在 .env 里填写：
# LLM_API_KEY=
# LLM_BASE_URL=
# LLM_MODEL_ID=
# SQLITE_PATH=
```

前端也可以在创建 session 时直接传：

```json
{
  "persona_profile": {
    "display_name": "阿昼",
    "user_nickname": "宝宝",
    "relation_mode": "你是用户的年上恋人，稳定、克制、有照顾感。",
    "tone_hint": "轻柔、亲密，不要过火。",
    "affection_style": "直接表达喜欢，但不要油腻。",
    "expression_level": "偏高",
    "comfort_hint": "先接住情绪，再慢慢哄。",
    "taboo_list": ["不说教", "不冷暴力"],
    "lexicon_list": ["笨蛋", "乖一点"]
  },
  "llm_config": {
    "api_key": "sk-...",
    "base_url": "https://your-openai-compatible-endpoint/v1",
    "model_id": "your-model-id"
  }
}
```

如果环境变量和请求都没提供完整模型配置，聊天接口会返回本地占位回复，方便先联调前后端。

## 本地测试

```bash
cd /Users/rxie/Desktop/loveBEATs/backend
python3 -m unittest discover -s tests
```

## 体验入口

```bash
cd /Users/rxie/Desktop/loveBEATs/backend
make run
```

- 浏览器体验：

```text
自己的网址
```

- 接口联调：

```bash
cd /Users/rxie/Desktop/loveBEATs/backend
make smoke
```

`make smoke` 会走一遍：

- `GET /health`
- `POST /v1/sessions`
- `POST /v1/heart-rate/latest`
- `POST /v1/turns/debug`
- `POST /v1/chat/send`
- `GET /v1/sessions/{session_id}/history`

## 当前限制

- 当前使用 SQLite 单文件持久化，默认文件名为 `pulseagent.db`
- 真实模型调用依赖有效的 `LLM_API_KEY / LLM_BASE_URL / LLM_MODEL_ID`
- 心率主链路是“iOS HealthKit 同步器 -> backend 存储 -> agent 内部 tool”，不直接开放给网页读取
- Web 前端当前仍然是后端静态页形态，适合 MVP 验证
- iOS 端需要用户手动填写运行 backend 的那台电脑的局域网地址
