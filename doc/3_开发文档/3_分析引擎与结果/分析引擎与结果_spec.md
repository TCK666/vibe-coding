# 分析引擎与结果 spec（里程碑6）

依据：PRD 第 2/7/11/12 章；概要设计 §6.4/6.5/6.6。里程碑5已落地任务引擎与 WS 编排，本 spec 只写增量。

## 1. 上下文拼装（context_builder）

每轮分析上下文 = system 提示词 + 摘要段 + 未摘要历史消息 + 附件解析文本：

- system：角色/六部分输出 schema/工具说明 + 会话数据源说明（附件清单、工作目录提示）。
- 摘要段：context_summaries 全部行（按 end_seq_no 顺序），格式 `【历史摘要 seq a-b】...`。
- 未摘要消息：seq_no > 最大 end_seq_no 的 user/assistant(text,result) 全文，tool_event 截断 200 字。
- 附件解析文本：parse_status=success 的附件，每个截断 3000 字，标注来源文件名。

**摘要压缩触发**：未摘要消息总字符 > `analysis.context_threshold`（默认 8000，system_configs 可调）且消息数 > 4 → 取较旧一半交 LLM 非流式摘要 → 写 context_summaries(start_seq_no, end_seq_no, summary_text) → 本轮只用较新一半。

## 2. 附件解析（上传时同步执行）

- 文本类后缀（txt/md/csv/json/log/py/sql/html）：utf-8 读取（errors=replace），≤200KB，写入 `workspace/{user}/{conv}/parsed_{attachment_id}.txt` → parse_status=success。
- 其他后缀（二进制/表格）→ parse_status=failed（本版本不解析，验收仅要求展示状态）。

## 3. 工具补全（execute_tool 增加 ToolContext(user_id, conversation_id)）

| 工具 | 行为 | 安全 |
|---|---|---|
| db_query | 里程碑5已实现 | 仅 SELECT/单语句/强制 LIMIT |
| file_read / file_write | 读写 `workspace/{user}/{conv}/` 内文件 | resolve 后必须位于 workspace 会话目录内；write ≤100KB |
| text_search | 在 workspace 全部文本文件（含 parsed_*.txt）按关键词逐行检索 | 最多 20 条命中，每行截断 200 字 |
| cmd_exec | 在 workspace 会话目录内执行命令，捕获 stdout/stderr | 首词白名单（`tool.cmd.whitelist`，默认 python,ping,dir）+ 30s 超时 + 输出截断 4000 字 |

## 4. 六部分结果强校验与渲染

- Pydantic Schema：KeyMetric(metric_name/metric_value/metric_unit/metric_period)、Evidence(source_type/source_name/evidence_text/related_metric/confidence∈0-1)、SixPartResult(problem_definition/key_metrics/evidence_list/conclusion_text/missing_data_text/next_action_text≥2条)。
- 校验成功 → analysis_results 六列 + `result_markdown`=模板渲染（表格化指标/证据 + 建议编号列表）；校验失败 → result_markdown=原始文本、problem_definition 兜底标注，task_logs 记 WARNING。
- 导出：校验成功即写 `exports/{user}/{conv}/{task_id}.md` → result_file_path。

## 5. 结果接口

| 接口 | 行为 |
|---|---|
| GET /api/results/{task_id} | 六部分 + result_markdown + result_file_path（归属校验） |
| GET /api/results/{task_id}/download | FileResponse 下载导出文件（exports 越界校验） |
| GET /api/results/latest/{conversation_id} | 会话内最新结果（需求外补充，供前端切会话回放） |

## 6. 验收清单

- [ ] 上传 txt 附件 → parse_status=success，text_search 能命中
- [ ] file_write→file_read 往返一致；`../` 越界拒绝；cmd_exec 白名单外拒绝
- [ ] 一轮分析：result_ready → GET /api/results/{id} 六部分齐全（建议≥2条校验生效）
- [ ] 导出文件存在于 exports/{user}/{conv}/，下载内容与 result_markdown 一致
- [ ] 历史消息超阈值 → context_summaries 落一行，下一轮上下文含摘要段
