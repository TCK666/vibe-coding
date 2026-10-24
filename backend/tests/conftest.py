import sys
from pathlib import Path

# 让 pytest 从项目根目录运行时能 import app / mock_auth / mock_llm
BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))
