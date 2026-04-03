# Backend

当前是单进程 + SQLite 单文件实现，目标是在保持简单的前提下把核心链路跑稳。

后续可替换：

- `app/db.py` -> Postgres/Redis/ORM
- `app/services/llm.py` -> 更完整的供应商适配层
- `app/services/chat_runtime.py` -> 更完整的 tool runtime 和埋点

当前建议前端接法：

- 进入某个恋人窗口时先创建 session
- persona 和 llm_config 默认绑定在 session 上
- 每次发送消息只传 `session_id`、`profile_id`、`user_message`、`idle_seconds`

当前 persona 字段已支持：

- `display_name`
- `user_nickname`
- `relation_mode`
- `tone_hint`
- `initiative_hint`
- `affection_style`
- `expression_level`
- `comfort_hint`
- `taboo_list`
- `lexicon_list`

当前持久化内容：

- `sessions`
- `session_llm_configs`
- `chat_messages`
- `heart_rate_cache`

当前模块分层：

- `app/services/agent_scaffold.py`
  平台级 scaffold，定义固定 prompt、tool registry、pipeline、安全规则
- `app/services/turn_runtime.py`
  每轮对话的 turn runtime factory + executor
- `app/services/chat_runtime.py`
  薄入口，负责把 API 请求转给 runtime
- `app/services/llm.py`
  OpenAI 兼容模型调用层

调试接口：

- `POST /v1/turns/preview`
  只返回 turn runtime，不落库
- `POST /v1/turns/debug`
  返回 turn runtime + prompt messages + llm 摘要 + warnings，不落库

本地联调命令：

- `make run`
  启动 FastAPI 服务
- `make test`
  跑单测
- `make smoke`
  用真实 HTTP 请求跑一遍后端闭环
