# Server Base CLI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `server-base <サブコマンド>` という統一CLIで、server_baseの日常操作(初回セットアップ・systemdサービス登録解除・アプリ追加削除・稼働確認・ログ・再起動・証明書更新)を行えるようにする。

**Architecture:** Python3製のCLI(`scripts/server-base`エントリポイント + `scripts/server_base_cli/`パッケージ)。既存の`scripts/*.sh`は一切変更せず、`subprocess`経由で薄くラップする。`argparse`でサブコマンドを構成し、各サブコマンドは`commands/`配下の対応するモジュールに実装する。

**Tech Stack:** Python 3 (標準ライブラリのみ: argparse, subprocess, pathlib, socket, datetime)。テストはpytest。

## Global Constraints

- 実装言語はPython3。標準ライブラリのみを使う(サードパーティ依存を増やさない)
- 既存の `scripts/*.sh`(`up.sh` / `down.sh` / `new-app.sh` / `install-service.sh` /
  `uninstall-service.sh` / `setup-dns.sh` / `generate-cert.sh` / `render-compose.sh`)と
  `gen-nginx-conf.py` は変更・削除しない。CLIは`subprocess`経由でラップするのみ
- コマンド名は `server-base`
- CLIは `scripts/` の中に完結させる。リポジトリ直下に新規ディレクトリは作らない
  (`scripts/server-base` エントリポイント + `scripts/server_base_cli/` パッケージ)
- `install-cli.sh` / `uninstall-cli.sh` は `~/.local/bin` にシンボリックリンクする。
  sudoは不要(`/usr/local/bin`は使わない)
- 破壊的操作(`app remove`)は確認プロンプト必須。`-y`/`--yes`でスキップ可能
- 全コマンド共通: ラップ先スクリプト・`docker`コマンドの exit code をそのまま
  CLIの exit code として返す。stdout/stderrはリアルタイムに素通しする(バッファリングして握りつぶさない)
- テストはpytest。`docker`/`systemctl`等の外部コマンド呼び出しは`shell.py`に薄く
  集約し、呼び出しコマンドの組み立てをモックで検証する。実機結合テスト(docker/systemd/
  実DNSが絡む実際の動作)はこのセッションでは実施できないため対象外とし、ユーザー側で行う
- 型ヒントを使うモジュールは冒頭で `from __future__ import annotations` を使い、
  Python 3.8以降でも動作するようにする(ユーザーの実サーバーのPythonバージョンが不明なため)

---

## 事前準備: pytestのインストール

- [ ] **pytestをインストールする**

Run: `python3 -m pip install --user pytest`

- [ ] **インストールを確認する**

Run: `python3 -m pytest --version`
Expected: `pytest x.y.z` のようなバージョン表示

---

### Task 1: テスト基盤と `paths.py`

**Files:**
- Create: `scripts/server_base_cli/__init__.py`
- Create: `scripts/server_base_cli/paths.py`
- Create: `scripts/conftest.py`
- Test: `scripts/tests/test_paths.py`

**Interfaces:**
- Consumes: なし(最初のタスク)
- Produces:
  - `paths.REPO_ROOT: Path` — リポジトリルート
  - `paths.SCRIPTS_DIR: Path` — `scripts/`
  - `paths.STACKS_DIR: Path` — `stacks/`
  - `paths.CORE_DIR: Path` — `core/`
  - `paths.SSL_DIR: Path` — `ssl/`
  - `paths.COMPOSE_GENERATED: Path` — `compose.generated.yaml`
  - `paths.stack_dir(app_name: str) -> Path`
  - `paths.stack_compose_path(app_name: str) -> Path`
  - `paths.script_path(name: str) -> Path`

- [ ] **Step 1: `scripts/conftest.py` を作成し、`scripts/`をimportパスに追加する**

```python
"""pytestが server_base_cli パッケージを見つけられるよう scripts/ をパスに追加する。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
```

- [ ] **Step 2: `scripts/server_base_cli/__init__.py` を空ファイルとして作成する**

```python
```

- [ ] **Step 3: 失敗するテストを書く**

`scripts/tests/test_paths.py`:
```python
from server_base_cli import paths


def test_repo_root_contains_scripts_and_stacks_dirs():
    assert (paths.REPO_ROOT / "scripts").is_dir()
    assert (paths.REPO_ROOT / "stacks").is_dir()
    assert (paths.REPO_ROOT / "core").is_dir()


def test_stack_dir():
    assert paths.stack_dir("myapp") == paths.STACKS_DIR / "myapp"


def test_stack_compose_path():
    assert paths.stack_compose_path("myapp") == paths.STACKS_DIR / "myapp" / "docker-compose.yml"


def test_script_path():
    assert paths.script_path("up.sh") == paths.SCRIPTS_DIR / "up.sh"


def test_compose_generated_path():
    assert paths.COMPOSE_GENERATED == paths.REPO_ROOT / "compose.generated.yaml"
```

- [ ] **Step 4: テストを実行し失敗を確認する**

Run: `python3 -m pytest scripts/tests/test_paths.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'server_base_cli.paths'` または `paths` が空)

- [ ] **Step 5: `paths.py` を実装する**

`scripts/server_base_cli/paths.py`:
```python
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
```

- [ ] **Step 6: テストを実行し成功を確認する**

Run: `python3 -m pytest scripts/tests/test_paths.py -v`
Expected: 5 passed

- [ ] **Step 7: コミット**

```bash
git add scripts/conftest.py scripts/server_base_cli/__init__.py scripts/server_base_cli/paths.py scripts/tests/test_paths.py
git commit -m "feat(cli): add path resolution module"
```

---

### Task 2: `shell.py` — subprocessヘルパー

**Files:**
- Create: `scripts/server_base_cli/shell.py`
- Test: `scripts/tests/test_shell.py`

**Interfaces:**
- Consumes: `paths.script_path`, `paths.REPO_ROOT` (Task 1)
- Produces:
  - `shell.run_script(script_name: str, args: Sequence[str] = (), cwd: Path | None = None) -> int`
  - `shell.run(cmd: Sequence[str], cwd: Path | None = None) -> int`
  - `shell.capture(cmd: Sequence[str], cwd: Path | None = None) -> subprocess.CompletedProcess`

- [ ] **Step 1: 失敗するテストを書く**

`scripts/tests/test_shell.py`:
```python
from unittest.mock import MagicMock, patch

from server_base_cli import paths, shell


def test_run_script_builds_correct_command_and_returns_exit_code():
    with patch("server_base_cli.shell.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        code = shell.run_script("up.sh", ["--profile", "time"])

    called_cmd = mock_run.call_args.args[0]
    assert called_cmd == [str(paths.script_path("up.sh")), "--profile", "time"]
    assert code == 0


def test_run_script_defaults_to_no_extra_args():
    with patch("server_base_cli.shell.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        shell.run_script("install-service.sh")

    called_cmd = mock_run.call_args.args[0]
    assert called_cmd == [str(paths.script_path("install-service.sh"))]


def test_run_streams_output_and_returns_exit_code():
    with patch("server_base_cli.shell.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=3)
        code = shell.run(["docker", "compose", "ps"])

    called_cmd = mock_run.call_args.args[0]
    assert called_cmd == ["docker", "compose", "ps"]
    assert mock_run.call_args.kwargs.get("capture_output") in (None, False)
    assert code == 3


def test_capture_sets_capture_output_and_text_and_does_not_raise():
    with patch("server_base_cli.shell.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stdout="web\n", stderr="boom")
        result = shell.capture(["docker", "compose", "config", "--services"])

    assert mock_run.call_args.kwargs["capture_output"] is True
    assert mock_run.call_args.kwargs["text"] is True
    assert result.returncode == 1
    assert result.stdout == "web\n"
```

- [ ] **Step 2: テストを実行し失敗を確認する**

Run: `python3 -m pytest scripts/tests/test_shell.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'server_base_cli.shell'`)

- [ ] **Step 3: `shell.py` を実装する**

`scripts/server_base_cli/shell.py`:
```python
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
```

- [ ] **Step 4: テストを実行し成功を確認する**

Run: `python3 -m pytest scripts/tests/test_shell.py -v`
Expected: 4 passed

- [ ] **Step 5: コミット**

```bash
git add scripts/server_base_cli/shell.py scripts/tests/test_shell.py
git commit -m "feat(cli): add subprocess helper module"
```

---

### Task 3: `stacks.py` — アプリ一覧・サービス名解決

**Files:**
- Create: `scripts/server_base_cli/stacks.py`
- Test: `scripts/tests/test_stacks.py`

**Interfaces:**
- Consumes: `paths.STACKS_DIR`, `paths.stack_compose_path` (Task 1), `shell.capture` (Task 2)
- Produces:
  - `stacks.list_apps() -> list[str]` — `stacks/*/docker-compose.yml` が存在するアプリ名の昇順リスト
  - `stacks.app_exists(app_name: str) -> bool`
  - `stacks.app_services(app_name: str) -> list[str]` — 失敗時は `RuntimeError` を投げる

- [ ] **Step 1: 失敗するテストを書く**

`scripts/tests/test_stacks.py`:
```python
from unittest.mock import MagicMock, patch

import pytest

from server_base_cli import paths, stacks


def test_list_apps_returns_sorted_names_with_compose_file(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "STACKS_DIR", tmp_path)
    (tmp_path / "zeta").mkdir()
    (tmp_path / "zeta" / "docker-compose.yml").write_text("services: {}\n")
    (tmp_path / "alpha").mkdir()
    (tmp_path / "alpha" / "docker-compose.yml").write_text("services: {}\n")
    (tmp_path / "no-compose-yet").mkdir()

    assert stacks.list_apps() == ["alpha", "zeta"]


def test_list_apps_returns_empty_list_when_stacks_dir_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "STACKS_DIR", tmp_path / "does-not-exist")

    assert stacks.list_apps() == []


def test_app_exists_true_and_false(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "STACKS_DIR", tmp_path)
    (tmp_path / "myapp").mkdir()
    (tmp_path / "myapp" / "docker-compose.yml").write_text("services: {}\n")

    assert stacks.app_exists("myapp") is True
    assert stacks.app_exists("missing") is False


def test_app_services_parses_stdout_lines():
    with patch("server_base_cli.stacks.shell.capture") as mock_capture:
        mock_capture.return_value = MagicMock(returncode=0, stdout="web\nworker\n", stderr="")
        services = stacks.app_services("myapp")

    assert services == ["web", "worker"]


def test_app_services_raises_runtime_error_on_failure():
    with patch("server_base_cli.stacks.shell.capture") as mock_capture:
        mock_capture.return_value = MagicMock(returncode=1, stdout="", stderr="boom")
        with pytest.raises(RuntimeError):
            stacks.app_services("myapp")
```

- [ ] **Step 2: テストを実行し失敗を確認する**

Run: `python3 -m pytest scripts/tests/test_stacks.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'server_base_cli.stacks'`)

- [ ] **Step 3: `stacks.py` を実装する**

`scripts/server_base_cli/stacks.py`:
```python
"""stacks/*/docker-compose.yml のアプリ一覧・サービス名解決。"""
from __future__ import annotations

from . import paths, shell


def list_apps() -> list[str]:
    """docker-compose.ymlを持つアプリ名を昇順で返す。"""
    if not paths.STACKS_DIR.is_dir():
        return []
    return sorted(p.parent.name for p in paths.STACKS_DIR.glob("*/docker-compose.yml"))


def app_exists(app_name: str) -> bool:
    return paths.stack_compose_path(app_name).is_file()


def app_services(app_name: str) -> list[str]:
    """stacks/<app_name>/docker-compose.yml が定義するサービス名一覧を返す。"""
    compose_file = paths.stack_compose_path(app_name)
    result = shell.capture(["docker", "compose", "-f", str(compose_file), "config", "--services"])
    if result.returncode != 0:
        raise RuntimeError(
            f"docker compose config --services が失敗しました({app_name}): {result.stderr}"
        )
    return [line for line in result.stdout.splitlines() if line.strip()]
```

- [ ] **Step 4: テストを実行し成功を確認する**

Run: `python3 -m pytest scripts/tests/test_stacks.py -v`
Expected: 5 passed

- [ ] **Step 5: コミット**

```bash
git add scripts/server_base_cli/stacks.py scripts/tests/test_stacks.py
git commit -m "feat(cli): add stacks helper module for app discovery"
```

---

### Task 4: CLIエントリポイントと `service add`/`service remove`

**Files:**
- Create: `scripts/server_base_cli/commands/__init__.py`
- Create: `scripts/server_base_cli/commands/service.py`
- Create: `scripts/server_base_cli/main.py`
- Create: `scripts/server-base`
- Test: `scripts/tests/test_command_service.py`

**Interfaces:**
- Consumes: `shell.run_script` (Task 2)
- Produces:
  - `main.build_parser() -> argparse.ArgumentParser`
  - `main.main(argv: list[str] | None = None) -> int`
  - `commands.service.register(subparsers: argparse._SubParsersAction) -> None`
  - 以降のすべてのサブコマンドタスクは `commands/*.py` に `register(subparsers)` を実装し、
    `main.build_parser()` から呼び出す、という同じパターンに従う

- [ ] **Step 1: `commands/__init__.py` を空ファイルとして作成する**

```python
```

- [ ] **Step 2: 失敗するテストを書く**

`scripts/tests/test_command_service.py`:
```python
from unittest.mock import patch

from server_base_cli.main import build_parser


def test_service_add_invokes_install_service_sh():
    with patch("server_base_cli.commands.service.shell.run_script") as mock_run:
        mock_run.return_value = 0
        parser = build_parser()
        args = parser.parse_args(["service", "add"])
        code = args.func(args)

    mock_run.assert_called_once_with("install-service.sh")
    assert code == 0


def test_service_remove_invokes_uninstall_service_sh():
    with patch("server_base_cli.commands.service.shell.run_script") as mock_run:
        mock_run.return_value = 0
        parser = build_parser()
        args = parser.parse_args(["service", "remove"])
        code = args.func(args)

    mock_run.assert_called_once_with("uninstall-service.sh")
    assert code == 0


def test_service_add_propagates_nonzero_exit_code():
    with patch("server_base_cli.commands.service.shell.run_script") as mock_run:
        mock_run.return_value = 1
        parser = build_parser()
        args = parser.parse_args(["service", "add"])
        code = args.func(args)

    assert code == 1


def test_top_level_help_does_not_raise():
    parser = build_parser()
    with_help = parser.format_help()
    assert "service" in with_help
```

- [ ] **Step 3: テストを実行し失敗を確認する**

Run: `python3 -m pytest scripts/tests/test_command_service.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'server_base_cli.main'`)

- [ ] **Step 4: `commands/service.py` を実装する**

`scripts/server_base_cli/commands/service.py`:
```python
"""`server-base service add|remove` — systemdユーザーサービス(core-stack.service)の登録・解除。"""
from __future__ import annotations

import argparse

from .. import shell


def _add(args: argparse.Namespace) -> int:
    return shell.run_script("install-service.sh")


def _remove(args: argparse.Namespace) -> int:
    return shell.run_script("uninstall-service.sh")


def register(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("service", help="systemdユーザーサービス(core-stack.service)の登録・解除")
    service_sub = parser.add_subparsers(dest="service_command", required=True)

    add_parser = service_sub.add_parser("add", help="systemdユーザーサービスとして登録する")
    add_parser.set_defaults(func=_add)

    remove_parser = service_sub.add_parser("remove", help="systemdユーザーサービスの登録を解除する")
    remove_parser.set_defaults(func=_remove)
```

- [ ] **Step 5: `main.py` を実装する**

`scripts/server_base_cli/main.py`:
```python
"""server-base CLI の argparse エントリポイント。"""
from __future__ import annotations

import argparse

from .commands import service


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="server-base",
        description="server_base の運用操作(初回セットアップ・アプリ追加削除・稼働確認等)をまとめて行うCLI",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    service.register(subparsers)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)
```

- [ ] **Step 6: `scripts/server-base` エントリポイントを作成し実行権限を付与する**

`scripts/server-base`:
```python
#!/usr/bin/env python3
"""server-base CLI 実行エントリポイント。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from server_base_cli.main import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
```

Run: `chmod +x scripts/server-base`

- [ ] **Step 7: テストを実行し成功を確認する**

Run: `python3 -m pytest scripts/tests/test_command_service.py -v`
Expected: 4 passed

- [ ] **Step 8: エントリポイントが実際に動くことを確認する(docker不要)**

Run: `./scripts/server-base --help`
Expected: usageメッセージが表示され、`service` サブコマンドが一覧に出る

Run: `./scripts/server-base service --help`
Expected: `add`/`remove` が一覧に出る

- [ ] **Step 9: コミット**

```bash
git add scripts/server_base_cli/commands/__init__.py scripts/server_base_cli/commands/service.py scripts/server_base_cli/main.py scripts/server-base scripts/tests/test_command_service.py
git commit -m "feat(cli): add server-base entrypoint and service add/remove"
```

---

### Task 5: `init` サブコマンド

**Files:**
- Create: `scripts/server_base_cli/commands/init.py`
- Modify: `scripts/server_base_cli/main.py`
- Test: `scripts/tests/test_command_init.py`

**Interfaces:**
- Consumes: `shell.run_script` (Task 2)
- Produces: `commands.init.register(subparsers)`

- [ ] **Step 1: 失敗するテストを書く**

`scripts/tests/test_command_init.py`:
```python
from unittest.mock import patch

from server_base_cli.main import build_parser


def test_init_runs_setup_dns_then_cert_then_up_in_order():
    calls = []

    def fake_run_script(name, args=()):
        calls.append((name, tuple(args)))
        return 0

    with patch("server_base_cli.commands.init.shell.run_script", side_effect=fake_run_script):
        parser = build_parser()
        args = parser.parse_args(["init"])
        code = args.func(args)

    assert calls == [
        ("setup-dns.sh", ()),
        ("generate-cert.sh", ("ubuntu.local",)),
        ("up.sh", ()),
    ]
    assert code == 0


def test_init_stops_after_first_failure():
    calls = []

    def fake_run_script(name, args=()):
        calls.append(name)
        return 0 if name != "generate-cert.sh" else 1

    with patch("server_base_cli.commands.init.shell.run_script", side_effect=fake_run_script):
        parser = build_parser()
        args = parser.parse_args(["init"])
        code = args.func(args)

    assert calls == ["setup-dns.sh", "generate-cert.sh"]
    assert code == 1
```

- [ ] **Step 2: テストを実行し失敗を確認する**

Run: `python3 -m pytest scripts/tests/test_command_init.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'server_base_cli.commands.init'`)

- [ ] **Step 3: `commands/init.py` を実装する**

`scripts/server_base_cli/commands/init.py`:
```python
"""`server-base init` — DNS・TLS証明書の発行とcoreの起動を一括で行う初回セットアップ。"""
from __future__ import annotations

import argparse
import sys

from .. import shell

_STEPS = [
    ("setup-dns.sh", []),
    ("generate-cert.sh", ["ubuntu.local"]),
    ("up.sh", []),
]


def _init(args: argparse.Namespace) -> int:
    for script_name, script_args in _STEPS:
        display = script_name if not script_args else f"{script_name} {' '.join(script_args)}"
        print(f"==> {display}")
        code = shell.run_script(script_name, script_args)
        if code != 0:
            print(f"!!! {script_name} が失敗しました(exit code {code})。ここで停止します。", file=sys.stderr)
            return code
    return 0


def register(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("init", help="DNS・TLS証明書の発行とcoreの起動を一括で行う")
    parser.set_defaults(func=_init)
```

- [ ] **Step 4: `main.py` に `init` を登録する**

`scripts/server_base_cli/main.py` を編集し、importと登録を追加する:
```python
from .commands import init, service
```
（`from .commands import service` の行を置き換える）
```python
    subparsers = parser.add_subparsers(dest="command", required=True)

    init.register(subparsers)
    service.register(subparsers)
```

- [ ] **Step 5: テストを実行し成功を確認する**

Run: `python3 -m pytest scripts/tests/test_command_init.py -v`
Expected: 2 passed

- [ ] **Step 6: `--help` が壊れていないことを確認する**

Run: `./scripts/server-base init --help`
Expected: エラー無くusageが表示される

- [ ] **Step 7: コミット**

```bash
git add scripts/server_base_cli/commands/init.py scripts/server_base_cli/main.py scripts/tests/test_command_init.py
git commit -m "feat(cli): add init subcommand"
```

---

### Task 6: `app add` サブコマンド

**Files:**
- Create: `scripts/server_base_cli/commands/app.py`
- Modify: `scripts/server_base_cli/main.py`
- Test: `scripts/tests/test_command_app.py`

**Interfaces:**
- Consumes: `shell.run_script` (Task 2)
- Produces: `commands.app.register(subparsers)` (このタスクでは `app add` のみ実装。`app remove` はTask 7で同じファイルに追加する)

- [ ] **Step 1: 失敗するテストを書く**

`scripts/tests/test_command_app.py`:
```python
from unittest.mock import patch

from server_base_cli.main import build_parser


def test_app_add_passes_through_args_without_service_name():
    with patch("server_base_cli.commands.app.shell.run_script") as mock_run:
        mock_run.return_value = 0
        parser = build_parser()
        args = parser.parse_args(
            ["app", "add", "time-announcement", "../time-announcement-frontend", "deploy/docker-compose.yaml", "time", "3000"]
        )
        code = args.func(args)

    mock_run.assert_called_once_with(
        "new-app.sh",
        ["time-announcement", "../time-announcement-frontend", "deploy/docker-compose.yaml", "time", "3000"],
    )
    assert code == 0


def test_app_add_inserts_service_name_when_given():
    with patch("server_base_cli.commands.app.shell.run_script") as mock_run:
        mock_run.return_value = 0
        parser = build_parser()
        args = parser.parse_args(
            [
                "app", "add", "myapp", "../myapp", "deploy/docker-compose.yaml",
                "--service", "web", "myapp", "3000",
            ]
        )
        code = args.func(args)

    mock_run.assert_called_once_with(
        "new-app.sh",
        ["myapp", "../myapp", "deploy/docker-compose.yaml", "web", "myapp", "3000"],
    )
    assert code == 0


def test_app_add_propagates_failure_exit_code():
    with patch("server_base_cli.commands.app.shell.run_script") as mock_run:
        mock_run.return_value = 1
        parser = build_parser()
        args = parser.parse_args(
            ["app", "add", "myapp", "../myapp", "deploy/docker-compose.yaml", "myapp", "3000"]
        )
        code = args.func(args)

    assert code == 1
```

- [ ] **Step 2: テストを実行し失敗を確認する**

Run: `python3 -m pytest scripts/tests/test_command_app.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'server_base_cli.commands.app'`)

- [ ] **Step 3: `commands/app.py` に `add` を実装する**

`scripts/server_base_cli/commands/app.py`:
```python
"""`server-base app add|remove` — stacks/<app名>/docker-compose.yml の追加・削除。"""
from __future__ import annotations

import argparse

from .. import shell


def _add(args: argparse.Namespace) -> int:
    cmd_args = [args.app_name, args.repo_path, args.compose_file]
    if args.service_name:
        cmd_args.append(args.service_name)
    cmd_args += [args.subdomain, args.port]
    return shell.run_script("new-app.sh", cmd_args)


def register(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("app", help="アプリの追加・削除")
    app_sub = parser.add_subparsers(dest="app_command", required=True)

    add_parser = app_sub.add_parser("add", help="新しいアプリを stacks/ に追加する")
    add_parser.add_argument("app_name", help="stacks/<app名>/ のディレクトリ名")
    add_parser.add_argument("repo_path", help="アプリ側リポジトリへの相対/絶対パス")
    add_parser.add_argument("compose_file", help="アプリ側リポジトリから見たcomposeファイルのパス")
    add_parser.add_argument(
        "--service",
        dest="service_name",
        default=None,
        help="アプリ側composeのサービス名(サービスが1個だけなら省略可・自動検出)",
    )
    add_parser.add_argument("subdomain", help="<subdomain>.ubuntu.local で公開する")
    add_parser.add_argument("port", help="アプリがリッスンするポート番号")
    add_parser.set_defaults(func=_add)
```

- [ ] **Step 4: `main.py` に `app` を登録する**

`scripts/server_base_cli/main.py` を編集する:
```python
from .commands import app, init, service
```
```python
    app.register(subparsers)
    init.register(subparsers)
    service.register(subparsers)
```

- [ ] **Step 5: テストを実行し成功を確認する**

Run: `python3 -m pytest scripts/tests/test_command_app.py -v`
Expected: 3 passed

- [ ] **Step 6: `--help` が壊れていないことを確認する**

Run: `./scripts/server-base app add --help`
Expected: エラー無くusageが表示される

- [ ] **Step 7: コミット**

```bash
git add scripts/server_base_cli/commands/app.py scripts/server_base_cli/main.py scripts/tests/test_command_app.py
git commit -m "feat(cli): add app add subcommand"
```

---

### Task 7: `app remove` サブコマンド

**Files:**
- Modify: `scripts/server_base_cli/commands/app.py`
- Test: `scripts/tests/test_command_app.py`(追記)

**Interfaces:**
- Consumes: `shell.run_script`, `shell.run` (Task 2), `stacks.app_exists`, `stacks.app_services` (Task 3), `paths.stack_dir`, `paths.COMPOSE_GENERATED` (Task 1)
- Produces: `app remove` サブコマンド(`commands.app.register` に追加登録)

- [ ] **Step 1: 失敗するテストを追記する**

`scripts/tests/test_command_app.py` の末尾に追記:
```python
from server_base_cli import paths


def test_app_remove_fails_fast_when_app_not_found():
    with patch("server_base_cli.commands.app.stacks.app_exists", return_value=False):
        parser = build_parser()
        args = parser.parse_args(["app", "remove", "missing-app"])
        code = args.func(args)

    assert code == 1


def test_app_remove_aborts_when_user_declines_confirmation():
    with patch("server_base_cli.commands.app.stacks.app_exists", return_value=True), \
         patch("builtins.input", return_value="n"), \
         patch("server_base_cli.commands.app.shell.run_script") as mock_run_script:
        parser = build_parser()
        args = parser.parse_args(["app", "remove", "myapp"])
        code = args.func(args)

    mock_run_script.assert_not_called()
    assert code == 1


def test_app_remove_skips_confirmation_with_yes_flag(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "STACKS_DIR", tmp_path)
    app_dir = tmp_path / "myapp"
    app_dir.mkdir()
    (app_dir / "docker-compose.yml").write_text("services:\n  web: {}\n")

    calls = []

    def fake_run_script(name, args=()):
        calls.append(("run_script", name, tuple(args)))
        return 0

    def fake_run(cmd):
        calls.append(("run", tuple(cmd)))
        return 0

    with patch("server_base_cli.commands.app.shell.run_script", side_effect=fake_run_script), \
         patch("server_base_cli.commands.app.shell.run", side_effect=fake_run), \
         patch("server_base_cli.commands.app.stacks.app_services", return_value=["web"]):
        parser = build_parser()
        args = parser.parse_args(["app", "remove", "myapp", "-y"])
        code = args.func(args)

    assert code == 0
    assert not app_dir.exists()
    assert ("run_script", "render-compose.sh", ()) in calls
    assert (
        "run",
        ("docker", "compose", "-f", str(paths.COMPOSE_GENERATED), "rm", "-f", "-s", "-v", "web"),
    ) in calls
    assert ("run", ("docker", "network", "rm", "net-myapp")) in calls
    assert ("run_script", "up.sh", ()) in calls
    # render-compose.sh -> rm -> network rm -> up.sh の順で呼ばれること
    run_script_order = [c[1] for c in calls if c[0] == "run_script"]
    assert run_script_order == ["render-compose.sh", "up.sh"]


def test_app_remove_stops_when_render_compose_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "STACKS_DIR", tmp_path)
    app_dir = tmp_path / "myapp"
    app_dir.mkdir()
    (app_dir / "docker-compose.yml").write_text("services:\n  web: {}\n")

    with patch("server_base_cli.commands.app.shell.run_script", return_value=1) as mock_run_script, \
         patch("server_base_cli.commands.app.shell.run") as mock_run:
        parser = build_parser()
        args = parser.parse_args(["app", "remove", "myapp", "-y"])
        code = args.func(args)

    assert code == 1
    mock_run.assert_not_called()
    assert app_dir.exists()  # render-compose.sh失敗時はまだ削除しない
```

- [ ] **Step 2: テストを実行し失敗を確認する**

Run: `python3 -m pytest scripts/tests/test_command_app.py -v`
Expected: 新規4件がFAIL (`app remove` コマンドが未登録のため `argparse` エラー)

- [ ] **Step 3: `commands/app.py` に `remove` を実装する**

`scripts/server_base_cli/commands/app.py` を編集し、以下を追加する:
```python
from __future__ import annotations

import argparse
import shutil
import sys

from .. import paths, shell, stacks


def _add(args: argparse.Namespace) -> int:
    cmd_args = [args.app_name, args.repo_path, args.compose_file]
    if args.service_name:
        cmd_args.append(args.service_name)
    cmd_args += [args.subdomain, args.port]
    return shell.run_script("new-app.sh", cmd_args)


def _remove(args: argparse.Namespace) -> int:
    app_name = args.app_name

    if not stacks.app_exists(app_name):
        print(f"エラー: stacks/{app_name}/docker-compose.yml が見つかりません。", file=sys.stderr)
        return 1

    if not args.yes:
        answer = input(
            f"以下を削除します: stacks/{app_name}/ ・コンテナ ・net-{app_name} ネットワーク\n"
            "続行しますか? [y/N] "
        )
        if answer.strip().lower() not in ("y", "yes"):
            print("中止しました。")
            return 1

    code = shell.run_script("render-compose.sh")
    if code != 0:
        print("エラー: render-compose.sh の実行に失敗しました。", file=sys.stderr)
        return code

    services = stacks.app_services(app_name)
    if services:
        code = shell.run(
            ["docker", "compose", "-f", str(paths.COMPOSE_GENERATED), "rm", "-f", "-s", "-v", *services]
        )
        if code != 0:
            print(f"エラー: コンテナの削除に失敗しました(exit code {code})。", file=sys.stderr)
            return code

    shell.run(["docker", "network", "rm", f"net-{app_name}"])

    shutil.rmtree(paths.stack_dir(app_name))

    return shell.run_script("up.sh")


def register(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("app", help="アプリの追加・削除")
    app_sub = parser.add_subparsers(dest="app_command", required=True)

    add_parser = app_sub.add_parser("add", help="新しいアプリを stacks/ に追加する")
    add_parser.add_argument("app_name", help="stacks/<app名>/ のディレクトリ名")
    add_parser.add_argument("repo_path", help="アプリ側リポジトリへの相対/絶対パス")
    add_parser.add_argument("compose_file", help="アプリ側リポジトリから見たcomposeファイルのパス")
    add_parser.add_argument(
        "--service",
        dest="service_name",
        default=None,
        help="アプリ側composeのサービス名(サービスが1個だけなら省略可・自動検出)",
    )
    add_parser.add_argument("subdomain", help="<subdomain>.ubuntu.local で公開する")
    add_parser.add_argument("port", help="アプリがリッスンするポート番号")
    add_parser.set_defaults(func=_add)

    remove_parser = app_sub.add_parser("remove", help="アプリを stacks/ から削除する")
    remove_parser.add_argument("app_name", help="stacks/<app名>/ のディレクトリ名")
    remove_parser.add_argument("-y", "--yes", action="store_true", help="確認プロンプトを省略する")
    remove_parser.set_defaults(func=_remove)
```

- [ ] **Step 4: テストを実行し成功を確認する**

Run: `python3 -m pytest scripts/tests/test_command_app.py -v`
Expected: 7 passed

- [ ] **Step 5: `--help` が壊れていないことを確認する**

Run: `./scripts/server-base app remove --help`
Expected: エラー無くusageが表示される

- [ ] **Step 6: コミット**

```bash
git add scripts/server_base_cli/commands/app.py scripts/tests/test_command_app.py
git commit -m "feat(cli): add app remove subcommand"
```

---

### Task 8: `logs` サブコマンド

**Files:**
- Create: `scripts/server_base_cli/commands/logs.py`
- Modify: `scripts/server_base_cli/main.py`
- Test: `scripts/tests/test_command_logs.py`

**Interfaces:**
- Consumes: `shell.run` (Task 2), `stacks.app_exists`, `stacks.app_services` (Task 3), `paths.COMPOSE_GENERATED` (Task 1)
- Produces: `commands.logs.register(subparsers)`

- [ ] **Step 1: 失敗するテストを書く**

`scripts/tests/test_command_logs.py`:
```python
from unittest.mock import patch

from server_base_cli import paths
from server_base_cli.main import build_parser


def test_logs_without_app_targets_core_services():
    with patch("server_base_cli.commands.logs.shell.run") as mock_run:
        mock_run.return_value = 0
        parser = build_parser()
        args = parser.parse_args(["logs"])
        code = args.func(args)

    mock_run.assert_called_once_with(
        ["docker", "compose", "-f", str(paths.COMPOSE_GENERATED), "logs", "-f", "nginx", "dnsmasq"]
    )
    assert code == 0


def test_logs_with_app_targets_that_apps_services():
    with patch("server_base_cli.commands.logs.stacks.app_exists", return_value=True), \
         patch("server_base_cli.commands.logs.stacks.app_services", return_value=["web"]), \
         patch("server_base_cli.commands.logs.shell.run") as mock_run:
        mock_run.return_value = 0
        parser = build_parser()
        args = parser.parse_args(["logs", "myapp"])
        code = args.func(args)

    mock_run.assert_called_once_with(
        ["docker", "compose", "-f", str(paths.COMPOSE_GENERATED), "logs", "-f", "web"]
    )
    assert code == 0


def test_logs_with_unknown_app_fails_fast():
    with patch("server_base_cli.commands.logs.stacks.app_exists", return_value=False), \
         patch("server_base_cli.commands.logs.shell.run") as mock_run:
        parser = build_parser()
        args = parser.parse_args(["logs", "missing-app"])
        code = args.func(args)

    mock_run.assert_not_called()
    assert code == 1
```

- [ ] **Step 2: テストを実行し失敗を確認する**

Run: `python3 -m pytest scripts/tests/test_command_logs.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'server_base_cli.commands.logs'`)

- [ ] **Step 3: `commands/logs.py` を実装する**

`scripts/server_base_cli/commands/logs.py`:
```python
"""`server-base logs [app名]` — coreまたは指定アプリのログを追跡表示する。"""
from __future__ import annotations

import argparse
import sys

from .. import paths, shell, stacks

_CORE_SERVICES = ["nginx", "dnsmasq"]


def _logs(args: argparse.Namespace) -> int:
    if args.app_name:
        if not stacks.app_exists(args.app_name):
            print(f"エラー: stacks/{args.app_name}/docker-compose.yml が見つかりません。", file=sys.stderr)
            return 1
        services = stacks.app_services(args.app_name)
    else:
        services = _CORE_SERVICES

    return shell.run(["docker", "compose", "-f", str(paths.COMPOSE_GENERATED), "logs", "-f", *services])


def register(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("logs", help="coreまたは指定アプリのログを表示する(docker compose logs -f)")
    parser.add_argument("app_name", nargs="?", default=None, help="省略時はcore(nginx/dnsmasq)")
    parser.set_defaults(func=_logs)
```

- [ ] **Step 4: `main.py` に `logs` を登録する**

`scripts/server_base_cli/main.py` を編集する:
```python
from .commands import app, init, logs, service
```
```python
    app.register(subparsers)
    init.register(subparsers)
    logs.register(subparsers)
    service.register(subparsers)
```

- [ ] **Step 5: テストを実行し成功を確認する**

Run: `python3 -m pytest scripts/tests/test_command_logs.py -v`
Expected: 3 passed

- [ ] **Step 6: コミット**

```bash
git add scripts/server_base_cli/commands/logs.py scripts/server_base_cli/main.py scripts/tests/test_command_logs.py
git commit -m "feat(cli): add logs subcommand"
```

---

### Task 9: `restart` サブコマンド

**Files:**
- Create: `scripts/server_base_cli/commands/restart.py`
- Modify: `scripts/server_base_cli/main.py`
- Test: `scripts/tests/test_command_restart.py`

**Interfaces:**
- Consumes: `shell.run`, `shell.run_script` (Task 2), `stacks.app_exists`, `stacks.app_services` (Task 3), `paths.COMPOSE_GENERATED` (Task 1)
- Produces: `commands.restart.register(subparsers)`

- [ ] **Step 1: 失敗するテストを書く**

`scripts/tests/test_command_restart.py`:
```python
from unittest.mock import patch

from server_base_cli import paths
from server_base_cli.main import build_parser


def test_restart_without_app_runs_down_then_up():
    calls = []

    def fake_run_script(name, args=()):
        calls.append(name)
        return 0

    with patch("server_base_cli.commands.restart.shell.run_script", side_effect=fake_run_script):
        parser = build_parser()
        args = parser.parse_args(["restart"])
        code = args.func(args)

    assert calls == ["down.sh", "up.sh"]
    assert code == 0


def test_restart_without_app_stops_if_down_fails():
    with patch("server_base_cli.commands.restart.shell.run_script", return_value=1) as mock_run_script:
        parser = build_parser()
        args = parser.parse_args(["restart"])
        code = args.func(args)

    mock_run_script.assert_called_once_with("down.sh")
    assert code == 1


def test_restart_with_app_restarts_only_that_apps_services():
    with patch("server_base_cli.commands.restart.stacks.app_exists", return_value=True), \
         patch("server_base_cli.commands.restart.stacks.app_services", return_value=["web"]), \
         patch("server_base_cli.commands.restart.shell.run") as mock_run:
        mock_run.return_value = 0
        parser = build_parser()
        args = parser.parse_args(["restart", "myapp"])
        code = args.func(args)

    mock_run.assert_called_once_with(
        ["docker", "compose", "-f", str(paths.COMPOSE_GENERATED), "restart", "web"]
    )
    assert code == 0


def test_restart_with_unknown_app_fails_fast():
    with patch("server_base_cli.commands.restart.stacks.app_exists", return_value=False), \
         patch("server_base_cli.commands.restart.shell.run") as mock_run:
        parser = build_parser()
        args = parser.parse_args(["restart", "missing-app"])
        code = args.func(args)

    mock_run.assert_not_called()
    assert code == 1
```

- [ ] **Step 2: テストを実行し失敗を確認する**

Run: `python3 -m pytest scripts/tests/test_command_restart.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'server_base_cli.commands.restart'`)

- [ ] **Step 3: `commands/restart.py` を実装する**

`scripts/server_base_cli/commands/restart.py`:
```python
"""`server-base restart [app名]` — coreを含む全体、または指定アプリのみ再起動する。"""
from __future__ import annotations

import argparse
import sys

from .. import paths, shell, stacks


def _restart(args: argparse.Namespace) -> int:
    if args.app_name:
        if not stacks.app_exists(args.app_name):
            print(f"エラー: stacks/{args.app_name}/docker-compose.yml が見つかりません。", file=sys.stderr)
            return 1
        services = stacks.app_services(args.app_name)
        return shell.run(["docker", "compose", "-f", str(paths.COMPOSE_GENERATED), "restart", *services])

    code = shell.run_script("down.sh")
    if code != 0:
        return code
    return shell.run_script("up.sh")


def register(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("restart", help="coreまたは指定アプリを再起動する")
    parser.add_argument("app_name", nargs="?", default=None, help="省略時はcore+全アプリ(down→up)")
    parser.set_defaults(func=_restart)
```

- [ ] **Step 4: `main.py` に `restart` を登録する**

`scripts/server_base_cli/main.py` を編集する:
```python
from .commands import app, init, logs, restart, service
```
```python
    app.register(subparsers)
    init.register(subparsers)
    logs.register(subparsers)
    restart.register(subparsers)
    service.register(subparsers)
```

- [ ] **Step 5: テストを実行し成功を確認する**

Run: `python3 -m pytest scripts/tests/test_command_restart.py -v`
Expected: 4 passed

- [ ] **Step 6: コミット**

```bash
git add scripts/server_base_cli/commands/restart.py scripts/server_base_cli/main.py scripts/tests/test_command_restart.py
git commit -m "feat(cli): add restart subcommand"
```

---

### Task 10: `cert renew` サブコマンド

**Files:**
- Create: `scripts/server_base_cli/commands/cert.py`
- Modify: `scripts/server_base_cli/main.py`
- Test: `scripts/tests/test_command_cert.py`

**Interfaces:**
- Consumes: `shell.run_script` (Task 2)
- Produces: `commands.cert.register(subparsers)`

- [ ] **Step 1: 失敗するテストを書く**

`scripts/tests/test_command_cert.py`:
```python
from unittest.mock import patch

from server_base_cli.main import build_parser


def test_cert_renew_defaults_to_ubuntu_local():
    with patch("server_base_cli.commands.cert.shell.run_script") as mock_run:
        mock_run.return_value = 0
        parser = build_parser()
        args = parser.parse_args(["cert", "renew"])
        code = args.func(args)

    mock_run.assert_called_once_with("generate-cert.sh", ["ubuntu.local"])
    assert code == 0


def test_cert_renew_accepts_custom_domain():
    with patch("server_base_cli.commands.cert.shell.run_script") as mock_run:
        mock_run.return_value = 0
        parser = build_parser()
        args = parser.parse_args(["cert", "renew", "example.local"])
        code = args.func(args)

    mock_run.assert_called_once_with("generate-cert.sh", ["example.local"])
    assert code == 0
```

- [ ] **Step 2: テストを実行し失敗を確認する**

Run: `python3 -m pytest scripts/tests/test_command_cert.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'server_base_cli.commands.cert'`)

- [ ] **Step 3: `commands/cert.py` を実装する**

`scripts/server_base_cli/commands/cert.py`:
```python
"""`server-base cert renew [domain]` — TLS証明書を再発行する。"""
from __future__ import annotations

import argparse

from .. import shell


def _renew(args: argparse.Namespace) -> int:
    return shell.run_script("generate-cert.sh", [args.domain])


def register(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("cert", help="TLS証明書の操作")
    cert_sub = parser.add_subparsers(dest="cert_command", required=True)

    renew_parser = cert_sub.add_parser("renew", help="TLS証明書を再発行する")
    renew_parser.add_argument("domain", nargs="?", default="ubuntu.local", help="省略時はubuntu.local")
    renew_parser.set_defaults(func=_renew)
```

- [ ] **Step 4: `main.py` に `cert` を登録する**

`scripts/server_base_cli/main.py` を編集する:
```python
from .commands import app, cert, init, logs, restart, service
```
```python
    app.register(subparsers)
    cert.register(subparsers)
    init.register(subparsers)
    logs.register(subparsers)
    restart.register(subparsers)
    service.register(subparsers)
```

- [ ] **Step 5: テストを実行し成功を確認する**

Run: `python3 -m pytest scripts/tests/test_command_cert.py -v`
Expected: 2 passed

- [ ] **Step 6: コミット**

```bash
git add scripts/server_base_cli/commands/cert.py scripts/server_base_cli/main.py scripts/tests/test_command_cert.py
git commit -m "feat(cli): add cert renew subcommand"
```

---

### Task 11: `doctor` サブコマンド

**Files:**
- Create: `scripts/server_base_cli/commands/doctor.py`
- Modify: `scripts/server_base_cli/main.py`
- Test: `scripts/tests/test_command_doctor.py`

**Interfaces:**
- Consumes: `shell.capture` (Task 2), `paths.SSL_DIR`, `paths.COMPOSE_GENERATED` (Task 1)
- Produces:
  - `commands.doctor.register(subparsers)`
  - `commands.doctor._CHECKS: list[tuple[str, Callable[[], tuple[str, str]]]]` — 各チェック関数は `(status, message)` を返す。`status` は `"ok"` / `"warn"` / `"fail"`

- [ ] **Step 1: 失敗するテストを書く**

`scripts/tests/test_command_doctor.py`:
```python
import socket
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from server_base_cli import paths
from server_base_cli.commands import doctor
from server_base_cli.main import build_parser


def test_port_in_use_detects_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("0.0.0.0", 0))
        free_port = probe.getsockname()[1]

    assert doctor._port_in_use(free_port, "tcp") is False


def test_port_in_use_detects_busy_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as holder:
        holder.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        holder.bind(("0.0.0.0", 0))
        holder.listen(1)
        busy_port = holder.getsockname()[1]

        assert doctor._port_in_use(busy_port, "tcp") is True


def test_check_docker_ok_when_docker_info_succeeds():
    with patch("server_base_cli.commands.doctor.shell.capture") as mock_capture:
        mock_capture.return_value = MagicMock(returncode=0)
        status, _ = doctor._check_docker()

    assert status == "ok"


def test_check_docker_fail_when_docker_info_fails():
    with patch("server_base_cli.commands.doctor.shell.capture") as mock_capture:
        mock_capture.return_value = MagicMock(returncode=1)
        status, _ = doctor._check_docker()

    assert status == "fail"


def test_check_dns_ok_when_resolves():
    with patch("server_base_cli.commands.doctor.shell.capture") as mock_capture:
        mock_capture.return_value = MagicMock(returncode=0, stdout="192.168.1.10\n")
        status, _ = doctor._check_dns()

    assert status == "ok"


def test_check_dns_fail_when_not_resolved():
    with patch("server_base_cli.commands.doctor.shell.capture") as mock_capture:
        mock_capture.return_value = MagicMock(returncode=0, stdout="")
        status, _ = doctor._check_dns()

    assert status == "fail"


def test_check_cert_fail_when_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "SSL_DIR", tmp_path)
    status, _ = doctor._check_cert()
    assert status == "fail"


def test_check_cert_ok_when_far_from_expiry(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "SSL_DIR", tmp_path)
    (tmp_path / "ubuntu.local-cert.pem").write_text("dummy")
    future = (datetime.utcnow() + timedelta(days=100)).strftime("%b %d %H:%M:%S %Y GMT")
    with patch("server_base_cli.commands.doctor.shell.capture") as mock_capture:
        mock_capture.return_value = MagicMock(returncode=0, stdout=f"notAfter={future}\n")
        status, _ = doctor._check_cert()

    assert status == "ok"


def test_check_cert_warn_when_expiring_soon(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "SSL_DIR", tmp_path)
    (tmp_path / "ubuntu.local-cert.pem").write_text("dummy")
    soon = (datetime.utcnow() + timedelta(days=10)).strftime("%b %d %H:%M:%S %Y GMT")
    with patch("server_base_cli.commands.doctor.shell.capture") as mock_capture:
        mock_capture.return_value = MagicMock(returncode=0, stdout=f"notAfter={soon}\n")
        status, _ = doctor._check_cert()

    assert status == "warn"


def test_check_nginx_config_skips_when_not_running():
    with patch("server_base_cli.commands.doctor.shell.capture") as mock_capture:
        mock_capture.return_value = MagicMock(stdout="")
        status, _ = doctor._check_nginx_config()

    assert status == "warn"


def test_check_nginx_config_ok_when_running_and_valid():
    responses = [MagicMock(stdout="running\n"), MagicMock(returncode=0, stderr="")]
    with patch("server_base_cli.commands.doctor.shell.capture", side_effect=responses):
        status, _ = doctor._check_nginx_config()

    assert status == "ok"


def test_check_nginx_config_fail_when_running_but_invalid():
    responses = [MagicMock(stdout="running\n"), MagicMock(returncode=1, stderr="nginx: [emerg] boom")]
    with patch("server_base_cli.commands.doctor.shell.capture", side_effect=responses):
        status, _ = doctor._check_nginx_config()

    assert status == "fail"


def test_check_systemd_service_ok_when_enabled():
    with patch("server_base_cli.commands.doctor.shell.capture") as mock_capture:
        mock_capture.return_value = MagicMock(returncode=0, stdout="enabled\n")
        status, _ = doctor._check_systemd_service()

    assert status == "ok"


def test_check_systemd_service_warn_when_not_registered():
    with patch("server_base_cli.commands.doctor.shell.capture") as mock_capture:
        mock_capture.return_value = MagicMock(returncode=1, stdout="")
        status, _ = doctor._check_systemd_service()

    assert status == "warn"


def test_doctor_command_returns_zero_when_no_failures():
    fake_checks = [("A", lambda: ("ok", "fine")), ("B", lambda: ("warn", "meh"))]
    with patch("server_base_cli.commands.doctor._CHECKS", fake_checks):
        parser = build_parser()
        args = parser.parse_args(["doctor"])
        code = args.func(args)

    assert code == 0


def test_doctor_command_returns_one_when_any_failure():
    fake_checks = [("A", lambda: ("ok", "fine")), ("B", lambda: ("fail", "broken"))]
    with patch("server_base_cli.commands.doctor._CHECKS", fake_checks):
        parser = build_parser()
        args = parser.parse_args(["doctor"])
        code = args.func(args)

    assert code == 1
```

- [ ] **Step 2: テストを実行し失敗を確認する**

Run: `python3 -m pytest scripts/tests/test_command_doctor.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'server_base_cli.commands.doctor'`)

- [ ] **Step 3: `commands/doctor.py` を実装する**

`scripts/server_base_cli/commands/doctor.py`:
```python
"""`server-base doctor` — 起動前の環境チェック一式。"""
from __future__ import annotations

import argparse
import socket
from datetime import datetime, timedelta

from .. import paths, shell

_CORE_TCP_PORTS = [80, 443]


def _port_in_use(port: int, kind: str) -> bool:
    sock_type = socket.SOCK_STREAM if kind == "tcp" else socket.SOCK_DGRAM
    with socket.socket(socket.AF_INET, sock_type) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("0.0.0.0", port))
        except OSError:
            return True
        return False


def _check_docker() -> tuple[str, str]:
    result = shell.capture(["docker", "info"])
    if result.returncode == 0:
        return "ok", "Dockerデーモンに接続できます"
    return "fail", "Dockerデーモンに接続できません(`docker info` が失敗)"


def _check_ports() -> tuple[str, str]:
    busy = [f"{p}/tcp" for p in _CORE_TCP_PORTS if _port_in_use(p, "tcp")]
    if _port_in_use(53, "tcp"):
        busy.append("53/tcp")
    if _port_in_use(53, "udp"):
        busy.append("53/udp")
    if not busy:
        return "ok", "ポート80/443/53は空いています(またはserver_baseのコンテナが使用中です)"
    return "warn", f"以下のポートが使用中です: {', '.join(busy)}(nginx/dnsmasq以外のプロセスの可能性)"


def _check_dns() -> tuple[str, str]:
    result = shell.capture(["dig", "@127.0.0.1", "ubuntu.local", "+short"])
    if result.returncode == 0 and result.stdout.strip():
        return "ok", f"ubuntu.local は 127.0.0.1 経由で解決できます({result.stdout.strip()})"
    return "fail", "ubuntu.local を 127.0.0.1 経由で解決できません(dnsmasqコンテナが未起動の可能性)"


def _check_cert() -> tuple[str, str]:
    cert_path = paths.SSL_DIR / "ubuntu.local-cert.pem"
    if not cert_path.is_file():
        return "fail", f"{cert_path} が見つかりません(`server-base cert renew` 未実行)"

    result = shell.capture(["openssl", "x509", "-enddate", "-noout", "-in", str(cert_path)])
    if result.returncode != 0:
        return "fail", "証明書の有効期限を読み取れませんでした"

    end_str = result.stdout.strip().split("=", 1)[-1]
    end_date = datetime.strptime(end_str, "%b %d %H:%M:%S %Y %Z")
    remaining = end_date - datetime.utcnow()

    if remaining < timedelta(days=0):
        return "fail", f"証明書の有効期限が切れています({end_date.date()})"
    if remaining < timedelta(days=30):
        return "warn", f"証明書の有効期限が近づいています(残り{remaining.days}日, {end_date.date()})"
    return "ok", f"証明書は有効です(残り{remaining.days}日, {end_date.date()})"


def _check_nginx_config() -> tuple[str, str]:
    state_result = shell.capture(
        ["docker", "compose", "-f", str(paths.COMPOSE_GENERATED), "ps", "--format", "{{.State}}", "nginx"]
    )
    if state_result.stdout.strip() != "running":
        return "warn", "nginxコンテナが起動していないため設定確認をスキップしました"

    test_result = shell.capture(
        ["docker", "compose", "-f", str(paths.COMPOSE_GENERATED), "exec", "-T", "nginx", "nginx", "-t"]
    )
    if test_result.returncode == 0:
        return "ok", "nginx設定は正常です(nginx -t)"
    return "fail", f"nginx -t が失敗しました: {test_result.stderr.strip()}"


def _check_systemd_service() -> tuple[str, str]:
    result = shell.capture(["systemctl", "--user", "is-enabled", "core-stack.service"])
    if result.returncode == 0:
        return "ok", f"systemdユーザーサービスは有効です({result.stdout.strip()})"
    return "warn", "systemdユーザーサービスは未登録です(`server-base service add` で登録できます)"


_CHECKS: list[tuple[str, "Callable[[], tuple[str, str]]"]] = [
    ("Docker", _check_docker),
    ("ポート(80/443/53)", _check_ports),
    ("DNS解決", _check_dns),
    ("TLS証明書", _check_cert),
    ("nginx設定", _check_nginx_config),
    ("systemdサービス", _check_systemd_service),
]

_SYMBOLS = {"ok": "✓", "warn": "⚠", "fail": "✗"}


def _doctor(args: argparse.Namespace) -> int:
    has_failure = False
    for label, check_fn in _CHECKS:
        status, message = check_fn()
        if status == "fail":
            has_failure = True
        print(f"{_SYMBOLS[status]} {label}: {message}")
    return 1 if has_failure else 0


def register(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("doctor", help="起動前の環境チェックを一括で行う")
    parser.set_defaults(func=_doctor)
```

`Callable` の型ヒントを文字列で書いているため、実行時に `typing.Callable` を
importしなくても動作する(`from __future__ import annotations` によりモジュール
内の全アノテーションが遅延評価されるため)。

- [ ] **Step 4: `main.py` に `doctor` を登録する**

`scripts/server_base_cli/main.py` を編集する:
```python
from .commands import app, cert, doctor, init, logs, restart, service
```
```python
    app.register(subparsers)
    cert.register(subparsers)
    doctor.register(subparsers)
    init.register(subparsers)
    logs.register(subparsers)
    restart.register(subparsers)
    service.register(subparsers)
```

- [ ] **Step 5: テストを実行し成功を確認する**

Run: `python3 -m pytest scripts/tests/test_command_doctor.py -v`
Expected: 16 passed

- [ ] **Step 6: コミット**

```bash
git add scripts/server_base_cli/commands/doctor.py scripts/server_base_cli/main.py scripts/tests/test_command_doctor.py
git commit -m "feat(cli): add doctor subcommand"
```

---

### Task 12: `status` サブコマンド

**Files:**
- Create: `scripts/server_base_cli/commands/status.py`
- Modify: `scripts/server_base_cli/main.py`
- Test: `scripts/tests/test_command_status.py`

**Interfaces:**
- Consumes: `shell.capture` (Task 2), `stacks.list_apps`, `stacks.app_services` (Task 3), `paths.COMPOSE_GENERATED` (Task 1)
- Produces: `commands.status.register(subparsers)`

- [ ] **Step 1: 失敗するテストを書く**

`scripts/tests/test_command_status.py`:
```python
from unittest.mock import MagicMock, patch

from server_base_cli.commands import status
from server_base_cli.main import build_parser


def test_container_state_returns_state_string():
    with patch("server_base_cli.commands.status.shell.capture") as mock_capture:
        mock_capture.return_value = MagicMock(stdout="running\n")
        assert status._container_state("nginx") == "running"


def test_container_state_returns_stopped_when_output_empty():
    with patch("server_base_cli.commands.status.shell.capture") as mock_capture:
        mock_capture.return_value = MagicMock(stdout="")
        assert status._container_state("nginx") == "stopped"


def test_url_reachable_true_for_2xx_response():
    with patch("server_base_cli.commands.status.shell.capture") as mock_capture:
        mock_capture.return_value = MagicMock(returncode=0, stdout="200")
        assert status._url_reachable("https://x.ubuntu.local/") is True


def test_url_reachable_false_when_curl_fails():
    with patch("server_base_cli.commands.status.shell.capture") as mock_capture:
        mock_capture.return_value = MagicMock(returncode=7, stdout="")
        assert status._url_reachable("https://x.ubuntu.local/") is False


def test_systemd_enabled_true_when_is_enabled_succeeds():
    with patch("server_base_cli.commands.status.shell.capture") as mock_capture:
        mock_capture.return_value = MagicMock(returncode=0)
        assert status._systemd_enabled() is True


def test_status_command_prints_core_and_each_app(capsys):
    with patch("server_base_cli.commands.status.stacks.list_apps", return_value=["myapp"]), \
         patch("server_base_cli.commands.status.stacks.app_services", return_value=["myapp"]), \
         patch("server_base_cli.commands.status._container_state", return_value="running"), \
         patch("server_base_cli.commands.status._url_reachable", return_value=True), \
         patch("server_base_cli.commands.status._systemd_enabled", return_value=True):
        parser = build_parser()
        args = parser.parse_args(["status"])
        code = args.func(args)

    out = capsys.readouterr().out
    assert code == 0
    assert "nginx" in out
    assert "dnsmasq" in out
    assert "myapp" in out
    assert "https://myapp.ubuntu.local/" in out
    assert "到達可" in out
```

- [ ] **Step 2: テストを実行し失敗を確認する**

Run: `python3 -m pytest scripts/tests/test_command_status.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'server_base_cli.commands.status'`)

- [ ] **Step 3: `commands/status.py` を実装する**

`scripts/server_base_cli/commands/status.py`:
```python
"""`server-base status` — coreと各アプリの稼働状況を表示する。"""
from __future__ import annotations

import argparse

from .. import paths, shell, stacks

_CORE_SERVICES = ["nginx", "dnsmasq"]


def _container_state(service: str) -> str:
    result = shell.capture(
        ["docker", "compose", "-f", str(paths.COMPOSE_GENERATED), "ps", "--format", "{{.State}}", service]
    )
    state = result.stdout.strip()
    return state if state else "stopped"


def _url_reachable(url: str) -> bool:
    result = shell.capture(["curl", "-k", "-s", "-o", "/dev/null", "-w", "%{http_code}", url])
    return result.returncode == 0 and result.stdout.strip().startswith(("2", "3"))


def _systemd_enabled() -> bool:
    result = shell.capture(["systemctl", "--user", "is-enabled", "core-stack.service"])
    return result.returncode == 0


def _status(args: argparse.Namespace) -> int:
    print("== core ==")
    for service in _CORE_SERVICES:
        print(f"  {service}: {_container_state(service)}")
    print(f"  systemdサービス: {'有効' if _systemd_enabled() else '未登録/無効'}")

    print("== apps ==")
    apps = stacks.list_apps()
    if not apps:
        print("  (登録済みアプリはありません)")
    for app_name in apps:
        services = stacks.app_services(app_name)
        states = ", ".join(f"{s}={_container_state(s)}" for s in services)
        url = f"https://{app_name}.ubuntu.local/"
        reachable = "到達可" if _url_reachable(url) else "到達不可"
        print(f"  {app_name}: {states} | {url} ({reachable})")

    return 0


def register(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("status", help="coreと各アプリの稼働状況を表示する")
    parser.set_defaults(func=_status)
```

- [ ] **Step 4: `main.py` に `status` を登録する**

`scripts/server_base_cli/main.py` を編集する:
```python
from .commands import app, cert, doctor, init, logs, restart, service, status
```
```python
    app.register(subparsers)
    cert.register(subparsers)
    doctor.register(subparsers)
    init.register(subparsers)
    logs.register(subparsers)
    restart.register(subparsers)
    service.register(subparsers)
    status.register(subparsers)
```

- [ ] **Step 5: テストを実行し成功を確認する**

Run: `python3 -m pytest scripts/tests/test_command_status.py -v`
Expected: 6 passed

- [ ] **Step 6: CLI全体のテストを実行し、これまでの全タスクがそろって壊れていないことを確認する**

Run: `python3 -m pytest scripts/tests/ -v`
Expected: 全件 passed

Run: `./scripts/server-base --help`
Expected: `app`, `cert`, `doctor`, `init`, `logs`, `restart`, `service`, `status` が一覧に出る

- [ ] **Step 7: コミット**

```bash
git add scripts/server_base_cli/commands/status.py scripts/server_base_cli/main.py scripts/tests/test_command_status.py
git commit -m "feat(cli): add status subcommand"
```

---

### Task 13: `install-cli.sh` / `uninstall-cli.sh`

**Files:**
- Create: `scripts/install-cli.sh`
- Create: `scripts/uninstall-cli.sh`

**Interfaces:**
- Consumes: `scripts/server-base`(Task 4で作成済み)
- Produces: `~/.local/bin/server-base` へのシンボリックリンク運用

- [ ] **Step 1: `install-cli.sh` を実装する**

`scripts/install-cli.sh`:
```bash
#!/bin/bash
# server-base CLI を ~/.local/bin にインストールするスクリプト

set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BIN_DIR="$HOME/.local/bin"
TARGET="$BIN_DIR/server-base"

echo "=== server-base CLI のインストール ==="

echo ""
echo "1. python3の存在を確認しています..."
if ! command -v python3 &> /dev/null; then
    echo "エラー: python3 が見つかりません。インストールしてから再実行してください。" >&2
    exit 1
fi
echo "✓ python3が見つかりました ($(command -v python3))"

echo ""
echo "2. scripts/server-base に実行権限を付与しています..."
chmod +x "$ROOT/scripts/server-base"
echo "✓ 実行権限を付与しました"

echo ""
echo "3. $BIN_DIR を作成しています..."
mkdir -p "$BIN_DIR"
echo "✓ $BIN_DIR を作成しました"

echo ""
echo "4. シンボリックリンクを作成しています..."
ln -sf "$ROOT/scripts/server-base" "$TARGET"
echo "✓ $TARGET -> $ROOT/scripts/server-base"

echo ""
echo "5. \$PATHを確認しています..."
case ":$PATH:" in
    *":$BIN_DIR:"*)
        echo "✓ $BIN_DIR は \$PATH に含まれています"
        ;;
    *)
        echo "⚠ $BIN_DIR が \$PATH に含まれていません。以下をシェル設定に追加してください:"
        echo ""
        echo "  export PATH=\"\$HOME/.local/bin:\$PATH\""
        echo ""
        echo "  (bash: ~/.bashrc, zsh: ~/.zshrc に追記後、シェルを再起動してください)"
        ;;
esac

echo ""
echo "=== インストール完了！ ==="
echo ""
echo "使い方: server-base --help"
```

Run: `chmod +x scripts/install-cli.sh`

- [ ] **Step 2: `uninstall-cli.sh` を実装する**

`scripts/uninstall-cli.sh`:
```bash
#!/bin/bash
# server-base CLI のアンインストールスクリプト

set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BIN_DIR="$HOME/.local/bin"
TARGET="$BIN_DIR/server-base"
EXPECTED="$ROOT/scripts/server-base"

echo "=== server-base CLI のアンインストール ==="

echo ""
if [ ! -e "$TARGET" ]; then
    echo "  ($TARGET は存在しません。既にアンインストール済みです)"
elif [ ! -L "$TARGET" ]; then
    echo "警告: $TARGET はシンボリックリンクではありません。誤削除を避けるため何もしません。" >&2
    echo "  手動で確認・削除してください。" >&2
    exit 1
else
    LINK_TARGET="$(readlink "$TARGET")"
    if [ "$LINK_TARGET" != "$EXPECTED" ]; then
        echo "警告: $TARGET は別の場所を指しています ($LINK_TARGET)。誤削除を避けるため何もしません。" >&2
        exit 1
    fi
    rm "$TARGET"
    echo "✓ $TARGET を削除しました"
fi

echo ""
echo "=== アンインストール完了！ ==="
```

Run: `chmod +x scripts/uninstall-cli.sh`

- [ ] **Step 3: 実際に実行して動作確認する(docker不要なのでこの環境でも検証可能)**

Run: `./scripts/install-cli.sh`
Expected: エラー無く完了メッセージが出る

Run: `ls -la ~/.local/bin/server-base`
Expected: `scripts/server-base` を指すシンボリックリンクが表示される

Run: `~/.local/bin/server-base --help`
Expected: `server-base --help` と同じusageが表示される

Run: `./scripts/uninstall-cli.sh`
Expected: `✓ ... を削除しました` と表示される

Run: `ls ~/.local/bin/server-base 2>&1`
Expected: `No such file or directory`(削除されている)

- [ ] **Step 4: 再度インストールしてこのタスクを完了状態(インストール済み)で終える**

Run: `./scripts/install-cli.sh`

- [ ] **Step 5: コミット**

```bash
git add scripts/install-cli.sh scripts/uninstall-cli.sh
git commit -m "feat(cli): add install-cli.sh and uninstall-cli.sh"
```

---

### Task 14: ドキュメント更新と最終動作確認

**Files:**
- Modify: `scripts/README.md`
- Modify: `README.md`

**Interfaces:**
- Consumes: なし(ドキュメントのみ)
- Produces: なし

- [ ] **Step 1: `scripts/README.md` の一覧表に `server-base` CLI関連の行を追加する**

`scripts/README.md` のテーブル(`| install-service.sh | ... |` の行の直後)に追記する:
```markdown
| `server-base` | `up.sh`/`down.sh`/`new-app.sh`等をラップした統合CLI。`init`/`service add|remove`/`app add|remove`/`status`/`logs`/`restart`/`doctor`/`cert renew` を提供。詳細は `./scripts/server-base --help` |
| `install-cli.sh` | `server-base` を `~/.local/bin` にシンボリックリンクし、どこからでも実行できるようにする |
| `uninstall-cli.sh` | 上記の解除 |
```

- [ ] **Step 2: ルート `README.md` の構成図に `server-base` CLI 関連ファイルを追加する**

`README.md:32-43` の `scripts/` ツリーに以下を追記する(`new-app.sh` の行の直後):
```
    ├── server-base                # 統合CLI本体(init/service/app/status/logs/restart/doctor/cert)
    ├── server_base_cli/           # ↑の実装パッケージ
    ├── install-cli.sh             # server-baseを~/.local/binにインストール
    ├── uninstall-cli.sh           # 上記の解除
```

- [ ] **Step 3: ルート `README.md` の「日常操作」セクションにCLIの案内を追記する**

`README.md` の `## 日常操作` セクション(`README.md:154-171`)の直前に新しいセクションを追記する:
```markdown
## CLI (server-base)

`scripts/*.sh` を個別に呼ぶ代わりに、統合CLI `server-base` でも同じ操作ができる。
`./scripts/install-cli.sh` を一度実行すると `~/.local/bin/server-base` に
シンボリックリンクが張られ、リポジトリの外からでも `server-base` として呼べる。

```bash
server-base init                 # DNS+証明書発行+core起動(初回セットアップ一括)
server-base service add          # systemdユーザーサービスの登録
server-base service remove       # 上記の解除
server-base app add <app名> <repo> <compose> [--service NAME] <subdomain> <port>
server-base app remove <app名>   # 確認プロンプトあり(-yで省略可)
server-base status                # core+各アプリの稼働状況・URL・到達性を一覧表示
server-base logs [app名]          # 省略時はcore(nginx/dnsmasq)
server-base restart [app名]       # 省略時は全体
server-base doctor                # 起動前の環境チェック一式
server-base cert renew [domain]   # TLS証明書の再発行(省略時ubuntu.local)
```

各サブコマンドの詳細は `server-base <サブコマンド> --help` を参照。
```

- [ ] **Step 4: 全体の最終確認**

Run: `python3 -m pytest scripts/tests/ -v`
Expected: 全件 passed

Run: `./scripts/server-base --help`
Run: `./scripts/server-base init --help`
Run: `./scripts/server-base service --help`
Run: `./scripts/server-base app --help`
Run: `./scripts/server-base app add --help`
Run: `./scripts/server-base app remove --help`
Run: `./scripts/server-base status --help`
Run: `./scripts/server-base logs --help`
Run: `./scripts/server-base restart --help`
Run: `./scripts/server-base doctor --help`
Run: `./scripts/server-base cert renew --help`
Expected: いずれもエラー無くusageが表示される

- [ ] **Step 5: コミット**

```bash
git add scripts/README.md README.md
git commit -m "docs: document server-base CLI"
```

---

## 実機での確認事項(このセッションでは検証できない部分)

以下はDocker/systemd/実DNSが必要なため、ユーザーの運用PC上で最終確認すること:

- `server-base init` を新規環境相当で実行し、`core/nginx` と `core/dnsmasq` が
  実際に起動すること
- `server-base app add` → `server-base status` で追加したアプリが `到達可` と
  表示されること
- `server-base app remove` で対象アプリのコンテナ・ネットワーク・`stacks/<app名>/`
  が実際に削除され、`server-base status` から消えること
- `server-base service add` 後、PCを再起動して(あるいは新しいログインセッションで)
  `systemctl --user status core-stack.service` が有効化されていること
- `server-base doctor` が実機のポート使用状況・証明書有効期限・nginx設定を
  正しく検出すること
