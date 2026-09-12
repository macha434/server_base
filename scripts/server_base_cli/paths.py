"""server_base_cli パッケージ全体で使うパス解決。"""
from __future__ import annotations

from pathlib import Path

# このファイルは scripts/server_base_cli/paths.py に置かれる想定。
# parents[0]=server_base_cli, [1]=scripts, [2]=リポジトリルート
REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
STACKS_DIR = REPO_ROOT / "stacks"
CORE_DIR = REPO_ROOT / "core"
SSL_DIR = REPO_ROOT / "ssl"
COMPOSE_GENERATED = REPO_ROOT / "compose.generated.yaml"


def stack_dir(app_name: str) -> Path:
    return STACKS_DIR / app_name


def stack_compose_path(app_name: str) -> Path:
    return stack_dir(app_name) / "docker-compose.yml"


def script_path(name: str) -> Path:
    return SCRIPTS_DIR / name
