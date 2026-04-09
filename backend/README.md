# Backend

后端当前是单进程 FastAPI + SQLite，目标不是做大而全的平台，而是先把这几条链路跑稳：

- persona / agent / role 持久化
- 聊天 runtime
- 心率缓存与按需读取
- 独立 Web 聊天入口

## 当前定位

当前路线已经收敛为：

- Web 是聊天与人设输入入口
- Backend 是统一运行时
- iOS 只是 HealthKit 心率同步器

项目总路线和阶段计划见：

- [docs/project-plan.md](/Users/rxie/Desktop/loveBEATs/docs/project-plan.md)
- [docs/backend-architecture.md](/Users/rxie/Desktop/loveBEATs/docs/backend-architecture.md)

## 当前内部结构

Backend 现在按三层理解：

- `app/memory/` + `app/db.py`
  持久化层，当前仍保留部分 `session_*` 历史命名
- `app/state/`
  主编排层，负责每轮 runtime 实例化
- `app/agent/`
  agent 框架与执行层

`app/system/` 和 `app/tools/` 作为 agent 的子系统继续保留。

## 直接体验

- 启动服务：`make run`
- 打开页面：`http://127.0.0.1:8000/chat`
- 跑接口冒烟：`make smoke`
- 跑 persona/agent 冒烟：`make smoke-persona-agent`
- 跑测试：`make test`

## 前端接法

当前推荐的新语义是：

- 一张角色卡对应一个 `role_id`
- 一个 `role_id` 只绑定一个对话窗口
- 角色消息历史围绕 `role_id`
- HealthKit 数据归属于 `app_user_id`
- 一个 `role_id` 会绑定到一个 `app_user_id`

兼容阶段仍然保留旧字段：

- `session_id`
- `profile_id`

但新接口已经支持直接使用：

- `role_id`
- `app_user_id`

兼容规则：

- 如果传了 `role_id`，系统会默认把它当作当前的 `session_id`
- `profile_id` 现在主要作为 `app_user_id` 的兼容别名保留

正常发消息时，前端优先只传：

- `role_id`
- `user_message`
- `idle_seconds`

创建角色时，推荐优先传：

- `role_card`

其中 `role_id` 由后端自动生成，前端不需要也不应该让用户填写。

当前 `role_card` 结构包括：

- `name`
- `user_nickname`
- `relationship_setting`
- `story_background`
- `trait_profile`
- `attachment_style`
- `processing_style`
- `key_experiences`
- `core_motivations`
- `response_style`
- `response_boundaries`
- `keywords`

## 关键接口

- `GET /chat`
- `POST /v1/roles`
- `GET /v1/roles/{role_id}`
- `GET /v1/roles/{role_id}/history`
- `POST /v1/roles/{role_id}/heart-rate`
- `GET /v1/roles/{role_id}/heart-rate/latest`
- `GET /v1/roles/{role_id}/heart-rate/history`
- `POST /v1/app-users/{app_user_id}/heart-rate/latest`
- `GET /v1/app-users/{app_user_id}/heart-rate/latest`
- `GET /v1/app-users/{app_user_id}/heart-rate/history`
- `GET /v1/tools/heart-rate/provider`
- `POST /v1/sessions`
- `GET /v1/sessions/{session_id}`
- `GET /v1/sessions/{session_id}/history`
- `POST /v1/chat/send`
- `POST /v1/personas`
- `GET /v1/personas`
- `POST /v1/agents`
- `GET /v1/agents`
- `POST /v1/heart-rate/latest`
- `POST /v1/turns/preview`
- `POST /v1/turns/debug`

## persona / agent

当前 persona 结构支持：

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

当前也支持直接传结构化 `role_card`，由后端自动编译成 `persona_text + persona_profile`。

当前 agent profile 支持：

- `system_preamble`
- `tool_call_limit`
- `heart_rate_enabled`
- `heart_rate_max_call_per_turn`
- `allow_stale_heart_rate`

## 主要持久化表

- `roles`
- `role_llm_configs`
- `role_messages`
- `heart_rate_cache`
- `app_user_heart_rate_events`
- `role_heart_rate_latest`
- `role_heart_rate_events`
- `role_prompt_snapshots`
- `persona_templates`
- `agent_profiles`

## 主要模块

- `app/state/runtime_state.py`
  runtime 组装、角色快照解析、调试视图
- `app/agent/runtime.py`
  运行执行层
- `app/agent/llm.py`
  OpenAI 兼容模型调用层
- `app/memory/session_store.py`
  当前兼容阶段的角色会话持久化，同时维护 `role -> app_user` 归属
- `app/memory/role_store.py`
  新的 `role_id` 语义包装层
- `app/memory/heart_rate_store.py`
  用户级心率缓存和角色级心率历史

## 调试说明

- `POST /v1/turns/preview`
  只生成 runtime，不落库
- `POST /v1/turns/debug`
  额外返回 prompt、llm 摘要和 warnings
- `GET /v1/tools/heart-rate/provider`
  查看当前心率工具 provider，默认应为 `local_cache`

如果没提供完整模型配置，聊天会退回 `mock-local` 占位回复。这说明链路通了，不代表真实模型已经接入。

## 心率能力的边界

当前推荐方式不是让 Web 直接接 HealthKit，而是：

1. iOS 读取并同步某个 `app_user_id` 的心率到 backend
2. backend 维护用户级心率缓存和历史
3. agent runtime 在某个 `role_id` 下先解析所属 `app_user_id`
4. 再读取该 `app_user_id` 的最近心率

当前 `get_heart_rate` 保持为 backend 内部 tool，默认 provider 为：

- `local_cache`
  默认 provider，从 `heart_rate_cache` 读用户级最近值

当前不再把 MCP 作为主路线。项目主线是：

- iOS：最小 HealthKit 同步器
- backend：心率存储与查询
- agent：直接调用 backend 内部 tool

## 记忆规则

- 角色记忆以 `role_id` 为边界
- 一个 `role_id` 只对应一个对话窗口
- 角色消息历史就是角色记忆
- 用户级心率属于 `app_user_id`
- 角色级心率历史是“该角色创建后，在该角色上下文里累计的心率事件”
- 修改角色文案应重建角色卡，而不是原地覆盖
