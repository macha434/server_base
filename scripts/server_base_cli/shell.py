"""server_base_cli 全体で使う subprocess 共通ヘルパー。"""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Sequence

from . import paths


def run_script(script_name: str, args: Sequence[str] = (), cwd: Path | None = None) -> int:
    """scripts/<script_name> を実行し、標準出力・標準エラーをそのまま流す。exit codeを返す。"""
    cmd = [str(paths.script_path(script_name)), *args]
    result = subprocess.run(cmd, cwd=str(cwd or paths.REPO_ROOT))
    return result.returncode


def run(cmd: Sequence[str], cwd: Path | None = None) -> int:
    """任意のコマンドを実行し、標準出力・標準エラーをそのまま流す。exit codeを返す。"""
    result = subprocess.run(list(cmd), cwd=str(cwd or paths.REPO_ROOT))
    return result.returncode


def capture(cmd: Sequence[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
    """任意のコマンドを実行し、標準出力・標準エラーをテキストとして取得する。exit codeが非0でも例外を投げない。"""
    return subprocess.run(
        list(cmd),
        cwd=str(cwd or paths.REPO_ROOT),
        capture_output=True,
        text=True,
    )
