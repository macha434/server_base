"""pytestが server_base_cli パッケージを見つけられるよう scripts/ をパスに追加する。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
