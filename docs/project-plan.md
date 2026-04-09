# PulseAgent 项目路线与执行计划

## 1. 当前共识

项目现在按“角色卡驱动”的模型继续推进。

核心规则：

- 用户通过结构化表单创建角色卡
- 每张角色卡生成一个唯一 `role_id`
- 一个 `role_id` 只绑定一个对话窗口
- 该角色的历史消息就是它的记忆
- 该角色的角色级心率历史也绑定到这个 `role_id`
- HealthKit 数据本身归属于 `app_user_id`
- 心率只从角色创建之后开始记录到该角色的记忆边界
- 如果要修改角色文案，必须重建角色卡，也就是生成新的 `role_id`
- 允许删除角色卡；删除时同时删除其 prompt、消息历史和心率历史

## 2. 产品形态

项目保留两个入口：

### 2.1 Web 前端

职责：

- 用户填写角色设定
- 创建角色卡
- 与角色聊天
- 展示角色状态

### 2.2 iOS HealthKit Sync

职责：

- 请求 HealthKit 权限
- 绑定某个 `app_user_id`
- 将该 `app_user_id` 的心率同步到 backend
- 在需要时，把当前心率事件记到某个 `role_id` 的角色记忆边界
- 仅作为心率采集端存在，不承担聊天前端

## 3. Backend 目标结构

Backend 收敛成三层：

1. `database`
2. `state/application`
3. `agent/framework`

### 3.1 database

数据库只存结构化事实，不做决策。

最终围绕两条主线存储：

- `roles`
- `role_prompt_snapshots`
- `role_messages`
- `role_heart_rate_events`
- `app_user_healthkit_bridges`
- `heart_rate_cache`
- `app_user_heart_rate_events`

### 3.2 state/application

这是主层。

职责：

- 根据结构化输入创建 `role_id`
- 读取指定 `role_id` 的完整状态
- 组装本轮 runtime context
- 实例化一次运行对象
- 调用 agent 框架
- 把新回复和新状态写回数据库

### 3.3 agent/framework

这是未实例化的能力框架。

职责：

- system prompt 骨架
- LLM adapter
- tool registry
- memory policy
- response generation pipeline

真正每轮执行时，由 `state/application` 注入 prompt、历史消息和心率历史后完成实例化。

## 4. 记忆规则

当前项目不再区分“长期记忆”和“临时记忆”。

记忆定义就是：

- 该角色的全部消息历史
- 该角色创建后开始累计的角色级心率历史

因此：

- 新建角色卡 = 新记忆边界
- 删除角色卡 = 删除整个记忆边界

但 agent 读取心率时，不再直接读 `role_id`：

- 先 `role_id -> app_user_id`
- 再 `app_user_id -> latest heart rate`

## 5. 当前执行策略

当前阶段已经完成“结构先对齐 + 第一轮数据库迁移”。

执行原则：

1. 文档先切到 `role_id + state 主层` 语义
2. backend 中把 runtime 组装逻辑迁到 `state/application`
3. `agent` 层只保留框架和执行职责
4. 旧 `session_*` API 暂时只作为兼容入口保留

## 6. 本轮执行项

本轮直接执行：

1. 重写项目路线文档
2. 重写 backend 架构文档
3. 新增 `app/state/` 作为主层入口
4. 将 turn runtime 的创建逻辑从 `agent` 迁移到 `state`
5. 将内部持久化主表切到 `role_*`

## 7. 下一阶段

下一阶段再做：

- 继续收口 API 命名，从 `session_id/profile_id` 逐步转向 `role_id/app_user_id`
- 将 iOS HealthKit 绑定链路显式化
- Web 端角色创建表单对齐结构化字段
