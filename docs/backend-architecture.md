# Backend 架构说明

## 1. 目标模型

Backend 当前按三层模型收敛：

1. `database`
2. `state/application`
3. `agent/framework`

其中：

- `database` 存结构化事实
- `state/application` 是主层，负责实例化每一轮运行
- `agent/framework` 提供未实例化的能力框架

## 2. 核心业务主语

当前系统以 `role_id` 为业务主语。

含义：

- 一个 `role_id` 对应一张角色卡
- 一张角色卡只绑定一个对话窗口
- 一张角色卡只维护一份消息历史

但 HealthKit 数据边界已经独立出来：

- `app_user_id` 表示某个产品用户 / 某台已绑定 iOS HealthKit 来源
- `role_id` 归属于一个 `app_user_id`
- 用户级最新心率和用户级心率事件围绕 `app_user_id`
- 角色级心率历史只表示“该角色上下文里记录到的心率事件”

因此：

- 新建角色卡 = 新建 `role_id`
- 修改角色文案 = 重建角色卡 = 新 `role_id`
- 删除角色卡 = 删除该 `role_id` 的全部历史、prompt、状态

## 3. 目录职责

### 3.1 database / memory

当前持久化实现主要在：

- [app_user_store.py](/Users/rxie/Desktop/loveBEATs/backend/app/memory/app_user_store.py)
- [session_store.py](/Users/rxie/Desktop/loveBEATs/backend/app/memory/session_store.py)
- [heart_rate_store.py](/Users/rxie/Desktop/loveBEATs/backend/app/memory/heart_rate_store.py)
- [persona_templates.py](/Users/rxie/Desktop/loveBEATs/backend/app/memory/persona_templates.py)
- [agent_profiles.py](/Users/rxie/Desktop/loveBEATs/backend/app/memory/agent_profiles.py)
- [db.py](/Users/rxie/Desktop/loveBEATs/backend/app/db.py)

这是当前数据库访问层。

注意：

- 现在主持久化已经切到 `role_*` 表
- 用户级心率 source-of-truth 已回到 `heart_rate_cache`
- `app_user_healthkit_bridges` 用于记录某个 `app_user_id` 当前绑定的 iOS HealthKit 宿主
- `app_user_heart_rate_events` 用于记录用户级心率历史
- `session_*` 仍保留用于旧数据兼容和旧接口兼容
- 对外 API 仍有一部分沿用 `session_id / profile_id` 的旧字段
- 其中 `profile_id` 当前主要作为 `app_user_id` 的兼容别名

### 3.2 state / application

主层入口在：

- [runtime_state.py](/Users/rxie/Desktop/loveBEATs/backend/app/state/runtime_state.py)

职责：

- 获取当前角色对应的状态快照
- 解析 prompt、历史消息、工具策略
- 组装每轮 runtime context
- 为 agent 框架提供实例化后的输入

这层是当前后端的主编排层。

### 3.3 agent / framework

位置：

- [chat.py](/Users/rxie/Desktop/loveBEATs/backend/app/agent/chat.py)
- [runtime.py](/Users/rxie/Desktop/loveBEATs/backend/app/agent/runtime.py)
- [llm.py](/Users/rxie/Desktop/loveBEATs/backend/app/agent/llm.py)

职责：

- 提供 LLM 连接能力
- 提供工具调用执行能力
- 定义 memory policy 的运行方式
- 消费 state 层给出的 runtime context

这里不负责读取和组装完整业务状态。

## 4. system 与 tools 的位置

虽然顶层结构现在按 `database / state / agent` 理解，但以下两个子系统继续保留：

### system

位置：

- [guardrails.py](/Users/rxie/Desktop/loveBEATs/backend/app/system/guardrails.py)
- [persona.py](/Users/rxie/Desktop/loveBEATs/backend/app/system/persona.py)
- [scaffold.py](/Users/rxie/Desktop/loveBEATs/backend/app/system/scaffold.py)

职责：

- 系统级硬约束
- persona 编译
- system prompt 骨架

### tools

位置：

- [registry.py](/Users/rxie/Desktop/loveBEATs/backend/app/tools/registry.py)
- [heart_rate.py](/Users/rxie/Desktop/loveBEATs/backend/app/tools/heart_rate.py)

职责：

- 工具注册
- 工具选择
- 具体工具执行

## 5. 记忆定义

当前项目不单独拆长期记忆。

记忆就包括两部分：

- 当前角色的全部消息历史
- 当前角色创建后开始累计的角色级心率历史

同时存在一条不属于角色记忆边界的数据线：

- 当前 `app_user_id` 的最新心率和用户级心率事件

其中：

- “记忆策略”属于 agent/framework
- “记忆记录”属于 database/state

## 6. 当前迁移状态

当前已经完成的结构迁移：

- runtime 组装开始进入 `state/application`
- `agent` 不再承担完整状态解析职责
- 文档语义切换为 `role_id` 主导
- 主持久化表已切到 `roles / role_messages / role_llm_configs`
- 新增 `role_prompt_snapshots / role_heart_rate_latest / role_heart_rate_events`
- 新增用户级心率 source-of-truth：`heart_rate_cache / app_user_heart_rate_events`
- 新增 iOS 宿主注册层：`app_user_healthkit_bridges`
- agent 心率工具已改成 `role_id -> app_user_id -> latest heart rate`

当前尚未完成的迁移：

- API 参数仍大量使用 `session_id / profile_id`
- `app_user_id` 还没有完整登录/绑定链路
- Web 端人设创建还没切成真正的结构化表单

因此当前属于“边界已纠正、接口仍在兼容期”的阶段。
