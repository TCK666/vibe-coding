# 任务引擎与长连接 spec（里程碑5）

依据：PRD 第 5/10/11 章（任务规则/WS接口/消息类型）；概要设计 §6.2/6.3/6.8。

## 1. WS 通道

- `POST /api/chat/ws-token`：body `{conversation_id}`；校验会话归属后签发一次性令牌（websocket_tokens 表，默认 30s 过期，连接成功即写 consumed_at），返回 `{websocket_token, expires_in}`。
- `WS /api/chat/ws/chat?websocket_token=&conversation_id=`：
  - 鉴权：token 存在、未消费、未过期、conversation_id 匹配、会话属于 token 属主，任一不满足 → accept 后立即 `close(4401)`。
  - 连接注册：`ws_manager` 按 conversation_id 维护连接集合（每连接一把发送锁，避免并发写帧）。
  - 客户端消息：`{type:"chat", content}` 发起分析；`{type:"cancel", task_id}` 取消；`{type:"ping"}` → 回 `{type:"pong"}`。
  - 断线不取消任务：分析继续在服务端执行，结果落库，重连后经 `GET /api/tasks/{id}` 与历史消息补偿。

## 2. 任务状态机与并发约束

```
queued ─▶ running ─▶ success │ failed │ cancelled
```

- 一条用户消息 = 一个 analysis_task；事务内 FOR UPDATE 会话行后检查：存在 queued/running 任务 → 拒绝（`TASK_RUNNING`,409）。
- 取消：任务句柄注册于内存 `_running_tasks`；cancel 后在下一个 await 点抛 CancelledError → 状态置 cancelled → 推送 done；非运行中任务取消报 `TASK_NOT_RUNNING`。
- 失败：任何异常 → task_status=failed + error_message + error 事件 + done。
- task_logs 记录：state_change / tool_exec / error / cancel。

## 3. 消息协议（信封 `{type, data, ts}`，8 类，字段对齐需求 2.1.10）

| type | data 字段 | 时机 |
|---|---|---|
| message_start | task_id, conversation_id | 任务开始（queued→running 前） |
| message_delta | task_id, delta_text | LLM 增量文本 |
| tool_start / tool_finish | task_id, tool_name(, tool_result_summary) | 每次工具执行前后 |
| task_status | task_id, task_status, current_step | 状态/步骤变化 |
| result_ready | task_id, result_id | 结果落库后 |
| error | task_id(可空), error_message | 任务失败或请求被拒（如 TASK_RUNNING） |
| done | task_id, finished_at | 本轮结束（success/failed/cancelled 都发，最后一条） |

## 4. 分析编排（run_task）

1. message_start → 状态 running → 用户消息入库（seq_no 自增）。
2. 拼上下文（里程碑5简版）：system 提示词（角色+六部分输出要求+工具说明）+ 最近 20 条历史。
3. LLM 轮次循环（≤ max_tool_calls=8）：流式收 DeltaText→message_delta；Finish=tool_calls → 逐个 tool_start → 执行 → tool_finish（摘要≤500字，完整输出进上下文与 task_logs）→ 带工具结果进入下一轮；Finish=stop → 结束。
4. 结果落库：从最终文本提取 ```json 六部分```（容错），写 analysis_results（result_file_path 留待里程碑6导出）→ assistant 结果消息入库 → result_ready。
5. done 收尾。工具结果消息以 role=tool / message_type=tool_event 入库，供历史回放。

## 5. 工具（里程碑5先做 db_query）

- db_query：仅单条 SELECT（禁分号/危险关键字），无 LIMIT 自动加 LIMIT 100，执行于应用库连接，完整结果 JSON（截断 4000 字）回传 LLM，摘要回前端。
- file_ops / text_search / cmd_exec：里程碑6 实现，未接入时返回 `TOOL_NOT_IMPLEMENTED` 摘要。

## 6. LLM Adapter 调整

- ToolCall 事件补 `index` 字段（OpenAI tool_calls 分片按 index 累积，id/name 取首个非空）。

## 7. 验收清单

- [ ] ws-token 一次性：复用/过期/伪造 → 4401
- [ ] 一轮分析 8 类消息全部出现且 done 收尾
- [ ] 运行中再发第二条 → error(TASK_RUNNING)，原任务不受影响
- [ ] 取消 → task_status=cancelled + done，任务行落库
- [ ] GET /api/tasks/{id} 归属校验 + 状态字段齐全
- [ ] 断线重连后历史消息可回放（含工具事件）
