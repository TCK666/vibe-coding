import os
import sys
from pathlib import Path

# 让 pytest 从项目根目录运行时能 import app / mock_auth / mock_llm
BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

# 测试使用独立 SQLite 库，避免污染开发库 baas_dev.db（必须在 app 模块导入前设置）
os.environ.setdefault("BAAS_DB_URL", "sqlite+aiosqlite:///backend/baas_test.db")
