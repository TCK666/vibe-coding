# 会话/消息/附件模块 spec（里程碑4）

依据：PRD 第 5/7/8/9/10 章；概要设计 §6.1/§7.1/§7.3。数据对象（10 表模型）已在里程碑2落地，本 spec 只写本模块的行为契约。

## 1. 会话模块

| 接口 | 行为 |
|---|---|
| POST /api/chat/create | body `{title?}`（缺省"未命名会话"），创建 status=active 会话，返回 `{conversation_id,title,status}` |
| POST /api/chat/update | body `{conversation_id,title}`，仅本人会话可改，改 `updated_at` |
| POST /api/chat/delete | body `{conversation_ids:[...]}`，批量；仅删除本人会话；执行级联清理（见 §4），返回 `{deleted:[已删id]}` |
| GET /api/chat/ls | 返回本人 status≠deleted 的会话：`conversation_id,title,status,last_message_at`，按 last_message_at 降序（空值排后） |
| GET /api/chat/ls/{id} | 返回 `{conversation, messages[], conversation_attachments[]}`；messages 按 seq_no 升序，每条含 `message_id,role,content,attachments[],created_at` |

- 归属校验：所有接口先查 `conversations.user_id == 当前用户`，否则 `CONV_NOT_FOUND`(404)。
- 会话列表不返回已删除会话（删除是物理删除，见 §4）。

## 2. 消息模块

- `seq_no` 会话内从 1 自增：事务内锁定会话行 → `MAX(seq_no)+1`；`uq_messages_conv_seq` 唯一约束兜底并发。
- 写入消息同时更新 `conversations.last_message_at`。
- role ∈ user/assistant/tool/system；本里程碑只有 user 文本消息（分析回写在里程碑5/6 追加）。
- 消息暂无独立 REST 接口：用户消息随 WS 通道提交（里程碑5），历史经 `ls/{id}` 回放。

## 3. 附件模块

| 接口 | 行为 |
|---|---|
| POST /api/attachment/upload | multipart：`conversation_id` + 文件；保存到 `uploads/{user_id}/{conversation_id}/{8位uuid}_{原名}`；返回 `{attachment_id,file_name,file_path}`；parse_status=pending（解析在里程碑6） |
| POST /api/attachment/delete | body `{attachment_id}`，删记录+物理文件 |
| GET /api/attachment/get?attachment_id= | FileResponse 下载（鉴权后流式返回） |
| GET /api/attachment/ls?conversation_id= | 会话附件列表（需求外补充接口，供侧栏刷新） |

约束：
- 单文件 ≤ 50MB（`FILE_TOO_LARGE`）。
- `safe_name = Path(filename).name` 去目录成分；`file_path` 一律正斜杠相对路径（概要设计 §12 Windows 约定）。
- **路径校验**：读取/删除前 `resolve()` 后必须仍在 `uploads/` 根内，越界即 `FILE_PATH_INVALID`（防 `../` 穿越）。
- 归属校验：附件所属会话必须是当前用户的，否则 `ATTACHMENT_NOT_FOUND`(404)。

## 4. 删除级联（顺序执行，单事务）

1. 删 `websocket_tokens`（conversation_id）
2. 取 task_ids → 删 `task_logs`
3. 删 `analysis_results` → `analysis_tasks` → `context_summaries` → `messages` → `attachments`（记录）
4. 删会话行
5. 事务提交后删三个物理目录：`uploads|exports|workspace/{user_id}/{conversation_id}/`（不存在则忽略）

## 5. 补充接口

- GET /api/auth/me：返回当前登录用户（`user_id,external_user_id,username,display_name,role`），供前端头部与角色判断。

## 6. 验收清单（本模块）

- [ ] 建会话 → 列表可见 → 重命名生效
- [ ] 上传附件 → 侧栏可见（名称/类型/大小/时间/parse_status）→ 下载内容一致 → 删除后文件与记录消失
- [ ] 跨用户访问会话/附件一律 404
- [ ] 连发 3 条消息 seq_no = 1,2,3 且顺序稳定
- [ ] 删除会话：所有级联记录清零 + 三个目录消失
- [ ] `../` 越界路径被拒绝
