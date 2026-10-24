# PRD：经营归因分析系统

| 项 | 内容 |
|---|---|
| 文档名称 | PRD_经营归因分析系统 |
| 版本 | v1.0 |
| 日期 | 2026-10-24 |
| 依据 | 《Business Attribution Analysis System 需求文档》2.1 节（2.1 至 2.1.13） |
| 状态 | 正式版（作为概要设计与开发实现的范围依据） |

**范围说明**：本 PRD 只覆盖需求文档 2.1 节"经营归因分析系统"。2.2 节"舆情分析平台"不在本期范围，严禁混入。本文档只定义"要什么"，技术栈选型与实现方案由《概要设计总纲》及后续设计文档决定。

---

## 1 项目概述与目标

### 1.1 项目目标

实现一个面向经营分析场景的多轮归因分析系统，支持围绕一个业务问题持续追问、补充证据、生成阶段性结论和最终分析报告。

系统需要支撑的核心业务过程：

1. 用户在会话中提出业务问题（如指标异常、转化下降等经营问题），并可多轮持续追问、补充资料；
2. 系统围绕该问题执行分析（数据库查询、文件读写、文本检索、命令执行等）获取证据；
3. 每轮分析输出六部分结构化结论（问题定义、关键指标、证据列表、归因结论、待补充数据、下一步建议），并生成可下载的结果文件；
4. 分析过程通过长连接实时返回中间消息和最终结果，用户可看到任务状态、当前步骤、工具执行过程。

### 1.2 交付形式

提供以下交付物：

1. 可运行前端；
2. 可运行后端；
3. 认证服务（对接认证中心，完成授权登录）；
4. 数据库初始化脚本；
5. 示例数据；
6. 接口说明；
7. 至少两组完整分析示例（本期为"客户行为分析"与"评论反馈分析"两个场景，见第 13 章）。

### 1.3 名词约定

| 名词 | 含义 |
|---|---|
| 会话（conversation） | 围绕一个业务问题展开的多轮分析载体，包含消息、附件、任务与结果 |
| 消息（message） | 会话中的一条记录，包括用户输入、模型输出、工具执行记录等 |
| 附件（attachment） | 用户上传到会话中的资料文件 |
| 分析任务（task） | 一条用户消息触发的唯一一次分析执行单元 |
| 分析结果（result） | 一轮分析结束后生成的六部分结构化结论及结果文件 |
| 上下文摘要（context summary） | 对会话中早期消息段落压缩生成的摘要记录 |
| 结果文件 | 分析结果导出生成的、可下载的文件 |

---

## 2 开发范围

本期开发范围分为三类能力：

### 2.1 基础能力

- 认证中心登录
- 会话管理
- 附件管理
- 配置热更新
- 运行日志

### 2.2 分析能力

- 实时分析
- 数据库查询
- 文件读写
- 文本检索
- 命令执行
- 结果文件生成

### 2.3 交付能力

- 聊天工作台
- 结果保存
- 结果导出
- 至少两个业务分析场景的示例数据和完整演示链路

**不在本期范围**：舆情分析平台（需求 2.2 节）的全部内容；需求 2.1.12 所列六个业务场景中除"客户行为分析""评论反馈分析"外的其余四个场景（仅保留场景定义，暂不实现，见 13.2 节）。

---

## 3 用户角色

系统包含两类用户角色，角色信息记录在 `users` 表的 `role` 字段中。

| 角色 | 职责 |
|---|---|
| `分析用户` | 创建会话、输入分析问题、上传资料、查看历史消息、查看分析结果、下载结果文件 |
| `系统管理员` | 维护认证配置、维护系统配置、查看运行日志、管理数据源连接、启停功能开关 |

---

## 4 页面需求

前端需要提供以下页面与页面区块：

| 序号 | 页面/区块 | 需求描述 |
|---|---|---|
| 1 | `授权登录入口页` | 展示登录按钮，点击后跳转认证中心完成授权登录 |
| 2 | `登录回调页` | 处理授权回调参数、换取访问令牌、保存登录态并自动跳转到聊天工作台 |
| 3 | `聊天工作台页` | 左侧展示会话列表，中间展示当前会话对话区，右侧展示本轮分析结果，底部提供问题输入框和发送按钮 |
| 4 | `附件侧栏` | 展示当前会话下的附件列表，字段至少包含文件名、文件类型、文件大小、上传时间、解析状态，支持上传、删除、下载 |
| 5 | `实时任务区` | 展示当前分析轮状态、当前步骤、错误信息、工具执行过程和结果文件生成状态 |
| 6 | `结果展示区` | 展示问题定义、关键指标、证据列表、归因结论、待补充数据、下一步建议，支持复制和导出 |

补充说明：

- `附件侧栏`、`实时任务区`、`结果展示区` 是聊天工作台页的功能区块，其展示位置（如抽屉、折叠面板等交互形式）由概要设计定义；
- `结果展示区` 展示的六部分内容与第 12 章"分析输出格式"一一对应；
- `实时任务区` 展示的信息来自第 11 章实时消息类型中的任务状态、工具执行与错误消息。

---

## 5 会话与任务规则

### 5.1 状态定义

| 对象 | 状态枚举（至少包含） |
|---|---|
| 会话 | `active`、`archived`、`deleted` |
| 分析任务 | `queued`、`running`、`success`、`failed`、`cancelled` |

### 5.2 业务规则

| 编号 | 规则 |
|---|---|
| R1 | 一条用户消息对应一次分析任务 |
| R2 | 删除会话时，同时删除该会话下的消息、附件记录、任务记录、结果记录和上下文摘要记录 |
| R3 | 同一时间一个会话只允许存在一个运行中的分析任务 |
| R4 | 分析任务通过长连接实时返回中间消息和最终结果 |

### 5.3 规则对应的落地要求

- R1：每次分析在 `analysis_tasks` 表中生成一条任务记录，`input_text` 记录该条用户消息内容；
- R2：级联删除范围覆盖 `messages`、`attachments`、`analysis_tasks`、`analysis_results`、`context_summaries` 各表中对应该会话的记录，同时按第 9 章要求删除该会话的附件目录、导出目录和临时目录；
- R3：新任务发起时若该会话已存在运行中的分析任务，必须予以拒绝并给出明确提示；
- R4：实时消息协议见第 11 章。

---

## 6 前端模块要求

前端划分为以下 7 个模块：

| 序号 | 模块 | 职责 |
|---|---|---|
| 1 | `认证回调模块` | 处理授权跳转、回调参数接收、访问令牌保存、登录态校验 |
| 2 | `会话模块` | 处理会话列表加载、新建、删除、重命名、切换 |
| 3 | `聊天模块` | 处理消息发送、消息流式渲染、取消分析、历史消息回放 |
| 4 | `附件模块` | 处理文件上传、进度展示、删除、下载 |
| 5 | `结果模块` | 处理结构化结果展示、结果复制、结果导出 |
| 6 | `配置模块` | 处理系统配置查看和配置重载 |
| 7 | `日志模块` | 处理运行状态展示和错误信息查看 |

模块与页面区块的对应关系：`认证回调模块` 支撑授权登录入口页与登录回调页；`会话模块`、`聊天模块`、`附件模块`、`结果模块` 支撑聊天工作台页及其区块；`配置模块`、`日志模块` 面向系统管理员使用（对应角色职责中的维护系统配置、查看运行日志）。

---

## 7 后端模块要求

后端划分为以下 9 个模块：

| 序号 | 模块 | 职责 |
|---|---|---|
| 1 | `认证接入模块` | 负责对接认证中心、令牌校验、当前用户识别 |
| 2 | `会话模块` | 负责会话的新增、查询、更新、删除 |
| 3 | `消息模块` | 负责消息入库、历史消息查询、消息顺序控制 |
| 4 | `附件模块` | 负责文件保存、删除、下载、路径校验 |
| 5 | `长连接模块` | 负责会话级实时连接、连接鉴权、消息推送和连接关闭 |
| 6 | `任务模块` | 负责分析任务创建、状态流转、取消执行、日志记录、临时令牌签发 |
| 7 | `分析模块` | 负责拼装上下文、执行查询和文件工具、生成结构化结论 |
| 8 | `结果模块` | 负责分析结果落库、结果导出、结果文件管理、上下文摘要压缩 |
| 9 | `配置模块` | 负责系统配置读取和热更新 |

模块与数据表、接口的对应关系：

- `会话模块` → `conversations` 表，接口 `POST /api/chat/create`、`POST /api/chat/delete`、`POST /api/chat/update`、`GET /api/chat/ls`、`GET /api/chat/ls/{conversation_id}`；
- `消息模块` → `messages` 表（含 `seq_no` 顺序控制）；
- `附件模块` → `attachments` 表，接口 `POST /api/attachment/upload`、`POST /api/attachment/delete`、`GET /api/attachment/get`；
- `长连接模块` → `websocket_tokens` 表，接口 `POST /api/chat/ws-token`、`WS /api/chat/ws/chat`；
- `任务模块` → `analysis_tasks`、`task_logs` 表，接口 `GET /api/tasks/{task_id}`；
- `分析模块` → 执行数据库查询、文件读写、文本检索、命令执行四类工具（对应第 2 章"分析能力"）；
- `结果模块` → `analysis_results`、`context_summaries` 表，接口 `GET /api/results/{task_id}`；
- `配置模块` → `system_configs` 表，接口 `POST /api/admin/reload`。

---

## 8 数据表要求

数据库需包含以下 10 张表，字段名照抄需求文档，顺序为需求文档中的字段顺序：

| 序号 | 表名 | 全部字段 | 说明 |
|---|---|---|---|
| 1 | `users` | `id`、`external_user_id`、`username`、`display_name`、`role`、`status`、`created_at`、`updated_at` | 用户表；`external_user_id` 来自认证中心的用户标识，`role` 区分分析用户与系统管理员 |
| 2 | `conversations` | `id`、`user_id`、`title`、`status`、`last_message_at`、`created_at`、`updated_at` | 会话表；`status` 取值见 5.1 节（`active`、`archived`、`deleted`） |
| 3 | `messages` | `id`、`conversation_id`、`role`、`message_type`、`content`、`tool_name`、`tool_status`、`seq_no`、`created_at` | 消息表；`role` 区分消息发出方，`message_type` 区分消息种类，`tool_name`、`tool_status` 记录工具执行消息，`seq_no` 为会话内消息顺序号 |
| 4 | `attachments` | `id`、`conversation_id`、`message_id`、`file_name`、`file_path`、`file_type`、`file_size`、`parse_status`、`created_at` | 附件表；`parse_status` 为附件侧栏展示的解析状态 |
| 5 | `analysis_tasks` | `id`、`conversation_id`、`user_id`、`input_text`、`task_status`、`current_step`、`started_at`、`finished_at`、`error_message` | 分析任务表；`task_status` 取值见 5.1 节（`queued`、`running`、`success`、`failed`、`cancelled`） |
| 6 | `analysis_results` | `id`、`task_id`、`conversation_id`、`problem_definition`、`key_metrics_json`、`evidence_list_json`、`conclusion_text`、`missing_data_text`、`next_action_text`、`result_markdown`、`result_file_path`、`created_at` | 分析结果表；六部分结果分别落库，`key_metrics_json`、`evidence_list_json` 保存数组结构，`result_markdown` 为结果全文，`result_file_path` 指向导出的结果文件 |
| 7 | `context_summaries` | `id`、`conversation_id`、`start_seq_no`、`end_seq_no`、`summary_text`、`created_at` | 上下文摘要表；以消息序号区间（`start_seq_no` 至 `end_seq_no`）记录被压缩的段落 |
| 8 | `websocket_tokens` | `id`、`user_id`、`conversation_id`、`token`、`expires_at`、`consumed_at`、`created_at` | 长连接临时令牌表；`expires_at` 为过期时间，`consumed_at` 为令牌消费时间 |
| 9 | `system_configs` | `id`、`config_key`、`config_value`、`config_group`、`updated_at` | 系统配置表；承载配置热更新，`config_group` 为配置分组 |
| 10 | `task_logs` | `id`、`task_id`、`log_level`、`log_type`、`log_content`、`created_at` | 任务运行日志表；记录任务执行过程中的日志与错误信息，支撑运行日志查看 |

约束性要求：

- 会话级联删除（规则 R2）涉及 `messages`、`attachments`、`analysis_tasks`、`analysis_results`、`context_summaries` 五张表中 `conversation_id` 对应的记录；
- 表字段的具体类型、索引与外键策略由概要设计定义。

---

## 9 文件存储要求

文件按以下目录结构存储：

| 目录 | 用途 |
|---|---|
| `uploads/{user_id}/{conversation_id}/` | 附件存储目录 |
| `exports/{user_id}/{conversation_id}/` | 导出结果存储目录 |
| `workspace/{user_id}/{conversation_id}/` | 临时中间文件存储目录 |

存储规则：

1. 附件按 `uploads/{user_id}/{conversation_id}/` 目录存储；
2. 导出结果按 `exports/{user_id}/{conversation_id}/` 目录存储；
3. 临时中间文件按 `workspace/{user_id}/{conversation_id}/` 目录存储；
4. 删除会话时，同时删除该会话对应的附件目录、导出目录和临时目录。

---

## 10 接口要求

系统需提供以下 15 个接口。方法、路径、请求字段、响应字段照抄需求文档。

| 序号 | 方法 | 路径 | 请求字段/参数 | 响应字段 | 说明 |
|---|---|---|---|---|---|
| 1 | `GET` | `/auth/login` | — | — | 跳转到认证中心发起授权登录 |
| 2 | `GET` | `/auth/callback` | 授权回调参数 | — | 处理授权回调并建立登录态 |
| 3 | `POST` | `/api/chat/create` | `title` | `conversation_id`、`title`、`status` | 新建会话 |
| 4 | `POST` | `/api/chat/delete` | `conversation_ids` | — | 删除会话（支持批量，需执行第 5 章级联删除规则） |
| 5 | `POST` | `/api/chat/update` | `conversation_id`、`title` | — | 更新会话（重命名） |
| 6 | `GET` | `/api/chat/ls` | — | `conversation_id`、`title`、`status`、`last_message_at` | 查询会话列表 |
| 7 | `GET` | `/api/chat/ls/{conversation_id}` | 路径参数 `conversation_id` | `message_id`、`role`、`content`、`attachments`、`created_at` | 查询指定会话的历史消息 |
| 8 | `POST` | `/api/attachment/upload` | `conversation_id` 和文件对象 | `attachment_id`、`file_name`、`file_path` | 上传附件 |
| 9 | `POST` | `/api/attachment/delete` | `attachment_id` | — | 删除附件 |
| 10 | `GET` | `/api/attachment/get` | `attachment_id` | 附件文件 | 下载附件 |
| 11 | `POST` | `/api/chat/ws-token` | — | `websocket_token`、`expires_in` | 签发长连接临时令牌 |
| 12 | `WS` | `/api/chat/ws/chat` | 连接参数 `websocket_token`、`conversation_id` | 实时消息（见第 11 章） | 会话级长连接，实时推送分析过程消息 |
| 13 | `POST` | `/api/admin/reload` | — | `status`、`message` | 配置重载（热更新生效） |
| 14 | `GET` | `/api/tasks/{task_id}` | 路径参数 `task_id` | `task_status`、`current_step`、`started_at`、`finished_at`、`error_message` | 查询分析任务状态 |
| 15 | `GET` | `/api/results/{task_id}` | 路径参数 `task_id` | `problem_definition`、`key_metrics`、`evidence_list`、`conclusion_text`、`missing_data_text`、`next_action_text` | 查询指定任务的分析结果（六部分结构） |

接口约定：

- `/auth/login`、`/auth/callback` 为认证相关接口，其余接口在登录态下使用，鉴权方式由概要设计定义；
- `GET /api/chat/ls/{conversation_id}` 响应中的 `attachments` 为该条消息关联的附件信息；
- 长连接消息协议见第 11 章，连接鉴权使用 `POST /api/chat/ws-token` 签发的 `websocket_token`；
- 统一响应包结构、错误码由概要设计定义。

---

## 11 实时消息类型

长连接（`WS /api/chat/ws/chat`）需支持以下 8 种实时消息类型，必备字段照抄需求文档：

| 序号 | 消息类型 | 含义 | 必备字段（至少包含） |
|---|---|---|---|
| 1 | `message_start` | 表示本轮分析开始 | `task_id`、`conversation_id` |
| 2 | `message_delta` | 表示模型增量文本 | `task_id`、`delta_text` |
| 3 | `tool_start` | 表示某个工具开始执行 | `task_id`、`tool_name` |
| 4 | `tool_finish` | 表示某个工具执行完成 | `task_id`、`tool_name`、`tool_result_summary` |
| 5 | `task_status` | 表示任务状态变化 | `task_id`、`task_status`、`current_step` |
| 6 | `result_ready` | 表示结构化结果已生成 | `task_id`、`result_id` |
| 7 | `error` | 表示本轮分析失败 | `task_id`、`error_message` |
| 8 | `done` | 表示本轮分析结束 | `task_id`、`finished_at` |

消息与页面、任务的对应要求：

- `task_status` 消息驱动实时任务区的"当前分析轮状态、当前步骤"展示，`task_status` 取值同 5.1 节分析任务状态；
- `tool_start`、`tool_finish` 消息驱动实时任务区的"工具执行过程"展示，`tool_result_summary` 为工具执行结果摘要；
- `error` 消息驱动实时任务区的"错误信息"展示；
- `result_ready` 消息触发结果展示区刷新，并可依据 `task_id` 调用 `GET /api/results/{task_id}` 获取六部分结果；
- `done` 消息表示本轮分析结束，此后本轮不再有其他消息。

---

## 12 分析输出格式

每轮分析的结构化输出必须包含以下六部分，顺序如下：

| 序号 | 部分 | 内容要求 |
|---|---|---|
| 1 | `问题定义` | 当前分析要回答的业务问题 |
| 2 | `关键指标` | 以数组保存，每项至少包含 `metric_name`、`metric_value`、`metric_unit`、`metric_period` |
| 3 | `证据列表` | 以数组保存，每项至少包含 `source_type`、`source_name`、`evidence_text`、`related_metric`、`confidence` |
| 4 | `归因结论` | 用自然语言输出主要原因和影响范围 |
| 5 | `待补充数据` | 列出当前分析仍缺失的数据项 |
| 6 | `下一步建议` | 列出后续建议动作，至少 2 条 |

输出落地要求：

1. 六部分内容在 `analysis_results` 表中分别对应 `problem_definition`、`key_metrics_json`、`evidence_list_json`、`conclusion_text`、`missing_data_text`、`next_action_text` 字段落库；
2. 结果需生成结果全文（对应 `result_markdown`）并导出为可下载的结果文件（对应 `result_file_path`，存储于第 9 章导出目录）；
3. 结果展示区按六部分结构展示，支持复制和导出；
4. `GET /api/results/{task_id}` 响应字段（`problem_definition`、`key_metrics`、`evidence_list`、`conclusion_text`、`missing_data_text`、`next_action_text`）与六部分一一对应。

---

## 13 示例业务场景与验收标准

### 13.1 本期实现场景（全链路演示）

需求 2.1.12 列出六个业务场景，本期按"至少任选两个场景完成全链路演示"的要求，选取以下两个场景交付，每个场景提供示例数据和完整演示链路：

| 场景 | 必备示例数据表 | 演示要求 |
|---|---|---|
| `客户行为分析` | 用户表、访问事件表、加购事件表、下单事件表 | 围绕用户行为类业务问题（如转化、加购未下单等）完成"提问 → 实时分析 → 六部分结果 → 结果导出"的全链路演示，并体现多轮追问与补充证据 |
| `评论反馈分析` | 评论表、评分表、商品表、退款表 | 围绕评论、评分、退款类业务问题完成"提问 → 实时分析 → 六部分结果 → 结果导出"的全链路演示，并体现多轮追问与补充证据 |

两个场景的示例数据需支撑分析模块通过数据库查询工具取数，并能在六部分结果中给出有依据的归因结论。具体演示脚本（每场景的追问轮次）由概要设计与开发文档定义。

### 13.2 暂不实现场景

以下四个场景本期暂不实现（不提供示例数据与演示链路），场景定义保留，后续版本按需补充：

| 场景 | 必备示例数据表（需求原文，供后续实现参考） |
|---|---|
| `商品目录优化` | 商品表、类目表、搜索曝光表、点击表、转化表 |
| `库存异常分析` | 库存表、入库表、出库表、销量表 |
| `市场表现分析` | 渠道表、投放表、订单表、销售汇总表 |
| `退款模式分析` | 退款申请表、退款原因表、订单表、用户表 |

### 13.3 验收标准

验收以下列八条为准（照抄需求 2.1.13）：

1. 能通过授权登录进入聊天工作台
2. 能创建会话、上传附件、发送消息并查看历史记录
3. 能通过实时连接看到分析过程中的状态变化、工具执行和最终结果
4. 能查询历史消息、切换旧会话并继续追问
5. 能在结果区看到六部分结构化输出
6. 能导出分析结果文件并重新下载
7. 能通过配置重载接口更新配置并即时生效
8. 能完成至少两个业务场景的完整演示

验收标准第 8 条按 13.1 节确定的"客户行为分析""评论反馈分析"两个场景执行。

---

## 需求覆盖对照表

| 需求章节号 | 需求章节内容 | 对应 PRD 章节 |
|---|---|---|
| 2.1 | 经营归因分析系统（项目目标、交付形式） | 第 1 章 项目概述与目标 |
| 2.1.1 | 开发范围 | 第 2 章 开发范围 |
| 2.1.2 | 用户角色 | 第 3 章 用户角色 |
| 2.1.3 | 页面需求 | 第 4 章 页面需求 |
| 2.1.4 | 会话与任务规则 | 第 5 章 会话与任务规则 |
| 2.1.5 | 前端模块要求 | 第 6 章 前端模块要求 |
| 2.1.6 | 后端模块要求 | 第 7 章 后端模块要求 |
| 2.1.7 | 数据表要求 | 第 8 章 数据表要求 |
| 2.1.8 | 文件存储要求 | 第 9 章 文件存储要求 |
| 2.1.9 | 接口要求 | 第 10 章 接口要求 |
| 2.1.10 | 实时消息类型 | 第 11 章 实时消息类型 |
| 2.1.11 | 分析输出格式 | 第 12 章 分析输出格式 |
| 2.1.12 | 示例业务场景要求 | 13.1 节（本期实现场景）、13.2 节（暂不实现场景） |
| 2.1.13 | 验收标准 | 13.3 节 验收标准 |

覆盖核对：需求 2.1.1–2.1.13 共 13 个子章节全部有对应 PRD 章节，另含 2.1 节总述（项目目标与交付形式），共 14 项，无遗漏。
