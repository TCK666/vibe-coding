-- Business_Attribution_Analysis_System 初始化脚本（MySQL 8，utf8mb4）
-- 与 backend/app/models/tables.py 同构：两处必须同步修改
-- 开发期应用默认 SQLite（BAAS_DB_URL）；MySQL 部署：mysql -u root -p < 01_init.sql
CREATE DATABASE IF NOT EXISTS baas DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE baas;

CREATE TABLE IF NOT EXISTS users (
  id INT AUTO_INCREMENT PRIMARY KEY,
  external_user_id VARCHAR(64) NOT NULL,
  username VARCHAR(64) NOT NULL,
  display_name VARCHAR(128) NOT NULL DEFAULT '',
  role VARCHAR(16) NOT NULL DEFAULT 'user' COMMENT 'user=分析用户 admin=系统管理员',
  status VARCHAR(16) NOT NULL DEFAULT 'active',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_users_external (external_user_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS conversations (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL,
  title VARCHAR(256) NOT NULL DEFAULT '未命名会话',
  status VARCHAR(16) NOT NULL DEFAULT 'active' COMMENT 'active archived deleted',
  last_message_at DATETIME NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  KEY idx_conversations_user (user_id, status),
  CONSTRAINT fk_conversations_user FOREIGN KEY (user_id) REFERENCES users (id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS messages (
  id INT AUTO_INCREMENT PRIMARY KEY,
  conversation_id INT NOT NULL,
  role VARCHAR(16) NOT NULL COMMENT 'user assistant tool system',
  message_type VARCHAR(32) NOT NULL DEFAULT 'text' COMMENT 'text notice tool_event result',
  content MEDIUMTEXT NULL,
  tool_name VARCHAR(64) NULL,
  tool_status VARCHAR(16) NULL,
  seq_no INT NOT NULL COMMENT '会话内自增，顺序控制',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_messages_conv_seq (conversation_id, seq_no),
  CONSTRAINT fk_messages_conv FOREIGN KEY (conversation_id) REFERENCES conversations (id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS attachments (
  id INT AUTO_INCREMENT PRIMARY KEY,
  conversation_id INT NOT NULL,
  message_id INT NULL,
  file_name VARCHAR(256) NOT NULL,
  file_path VARCHAR(512) NOT NULL,
  file_type VARCHAR(64) NOT NULL DEFAULT '',
  file_size BIGINT NOT NULL DEFAULT 0,
  parse_status VARCHAR(16) NOT NULL DEFAULT 'pending' COMMENT 'pending parsing success failed',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_attachments_conv (conversation_id),
  CONSTRAINT fk_attachments_conv FOREIGN KEY (conversation_id) REFERENCES conversations (id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS analysis_tasks (
  id INT AUTO_INCREMENT PRIMARY KEY,
  conversation_id INT NOT NULL,
  user_id INT NOT NULL,
  input_text MEDIUMTEXT NULL,
  task_status VARCHAR(16) NOT NULL DEFAULT 'queued' COMMENT 'queued running success failed cancelled',
  current_step VARCHAR(128) NOT NULL DEFAULT '',
  started_at DATETIME NULL,
  finished_at DATETIME NULL,
  error_message MEDIUMTEXT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_tasks_conv_status (conversation_id, task_status),
  KEY idx_tasks_user (user_id),
  CONSTRAINT fk_tasks_conv FOREIGN KEY (conversation_id) REFERENCES conversations (id),
  CONSTRAINT fk_tasks_user FOREIGN KEY (user_id) REFERENCES users (id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS analysis_results (
  id INT AUTO_INCREMENT PRIMARY KEY,
  task_id INT NOT NULL,
  conversation_id INT NOT NULL,
  problem_definition MEDIUMTEXT NULL,
  key_metrics_json JSON NULL,
  evidence_list_json JSON NULL,
  conclusion_text MEDIUMTEXT NULL,
  missing_data_text MEDIUMTEXT NULL,
  next_action_text MEDIUMTEXT NULL,
  result_markdown MEDIUMTEXT NULL,
  result_file_path VARCHAR(512) NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uk_results_task (task_id),
  KEY idx_results_conv (conversation_id),
  CONSTRAINT fk_results_task FOREIGN KEY (task_id) REFERENCES analysis_tasks (id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS context_summaries (
  id INT AUTO_INCREMENT PRIMARY KEY,
  conversation_id INT NOT NULL,
  start_seq_no INT NOT NULL,
  end_seq_no INT NOT NULL,
  summary_text MEDIUMTEXT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_summaries_conv (conversation_id, end_seq_no),
  CONSTRAINT fk_summaries_conv FOREIGN KEY (conversation_id) REFERENCES conversations (id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS websocket_tokens (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL,
  conversation_id INT NOT NULL,
  token VARCHAR(128) NOT NULL,
  expires_at DATETIME NOT NULL,
  consumed_at DATETIME NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uk_ws_tokens_token (token),
  KEY idx_ws_tokens_user (user_id),
  CONSTRAINT fk_ws_tokens_user FOREIGN KEY (user_id) REFERENCES users (id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS system_configs (
  id INT AUTO_INCREMENT PRIMARY KEY,
  config_key VARCHAR(128) NOT NULL,
  config_value MEDIUMTEXT NULL,
  config_group VARCHAR(64) NOT NULL DEFAULT 'default',
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_configs_key (config_key)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS task_logs (
  id INT AUTO_INCREMENT PRIMARY KEY,
  task_id INT NOT NULL,
  log_level VARCHAR(8) NOT NULL DEFAULT 'INFO',
  log_type VARCHAR(32) NOT NULL DEFAULT '' COMMENT 'tool_exec state_change error',
  log_content MEDIUMTEXT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_task_logs_task (task_id, created_at),
  CONSTRAINT fk_task_logs_task FOREIGN KEY (task_id) REFERENCES analysis_tasks (id)
) ENGINE=InnoDB;

-- 默认运行配置（热更新生效）
INSERT IGNORE INTO system_configs (config_key, config_value, config_group) VALUES
  ('llm.provider', 'mock', 'llm'),
  ('llm.base_url', 'http://127.0.0.1:9002', 'llm'),
  ('llm.model', 'mock-attribution', 'llm'),
  ('llm.api_key', 'mock-key', 'llm'),
  ('analysis.max_tool_calls', '8', 'analysis'),
  ('analysis.context_threshold', '8000', 'analysis'),
  ('ws.token_ttl_seconds', '30', 'ws'),
  ('tool.cmd.whitelist', 'python,ping,dir', 'tool'),
  ('tool.db_query.readonly_dsn', '', 'tool');
