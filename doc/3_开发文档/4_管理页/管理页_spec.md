# 管理页 spec（里程碑7）

依据：PRD 第 3/6/7 章（管理员职责/配置模块/日志模块）；概要设计 §6.7。

## 1. 配置服务（config_service）

- 运行期配置唯一来源 = `system_configs` 表；进程内 `_cache` 字典加速同步读取。
- `reload_cache()`：全量重读 DB → 重建缓存（`POST /api/admin/reload` 触发，应用启动时也执行）。
- `set_value(key, value, group)`：upsert DB + 同步更新缓存。
- `get_sync(key, default)`：运行期同步读缓存（LLM 客户端工厂/工具白名单/上下文阈值/ws token TTL 等）。
- 启动时 seed 默认配置项（不存在才插入）：llm.provider/base_url/model/api_key、analysis.max_tool_calls、analysis.context_threshold、ws.token_ttl_seconds、tool.cmd.whitelist、tool.db_query.readonly_dsn。

## 2. 生效点（改配置 → reload/直接写入 → 即时生效）

| 配置 | 消费点 |
|---|---|
| llm.provider/base_url/model/api_key | 每个任务启动时构建 LLM 客户端（get_llm_client 读缓存），下轮任务即用新值 |
| analysis.context_threshold | 每次拼上下文 |
| tool.cmd.whitelist | 每次 cmd_exec |
| ws.token_ttl_seconds | 每次 ws-token 签发 |
| tool.db_query.readonly_dsn | 数据源连接（里程碑8 接演示库时消费） |

## 3. 管理端接口（全部要求 role=admin，否则 AUTH_FORBIDDEN 403）

| 接口 | 行为 |
|---|---|
| GET /api/admin/configs | 全部配置（key/value/group/updated_at） |
| POST /api/admin/configs | body `{config_key, config_value}`，upsert 并同步缓存 |
| POST /api/admin/reload | 重建缓存，响应 `{status, message}`（需求 2.1.9） |
| GET /api/admin/logs?task_id=&limit= | task_logs 倒序（默认 200 条），运行状态与错误查看 |

## 4. 前端

- /admin/config：配置表格 + 行内"修改"对话框 + 重载按钮（重载后刷新并提示条数）。
- /admin/logs：日志表格（时间/级别/类型/task_id/内容）+ task_id 过滤 + 刷新。
- Workbench 头部：role=admin 才显示"配置管理/运行日志"入口；非 admin 访问 /admin/* 页面自动跳回工作台。

## 5. 验收清单

- [ ] 非 admin 访问管理接口 403
- [ ] admin 改 llm.model → 不重启 → 下一轮任务使用新值（缓存生效）
- [ ] 直接改 DB 后 reload → 缓存同步
- [ ] 日志页能看到任务 state_change/tool_exec/error 记录
