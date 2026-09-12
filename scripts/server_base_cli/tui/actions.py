"""TUIから呼び出す「重い」操作の実行ヘルパー。

`shell.run_script`/`shell.run` は標準出力・標準エラーを端末にそのまま流す
(inherit stdio)実装になっているが、これはtextualの代替スクリーンバッファと
衝突して描画が崩れる。そのためTUI専用に、同じコマンド組み立てを
`subprocess.run(..., capture_output=True)` で自前実行し、結果をまとめて
文字列で返す関数群をここに用意する(`commands/*.py` の重複にはなるが、
意図的なトレードオフとして許容する。`commands/*.py` 自体は変更しない)。

各関数は `(成功したか, 出力テキスト)` のタプルを返す。ブロッキングするので
呼び出し側(TUI)は必ずワーカースレッドから呼ぶこと。
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path
from typing import Sequence

from .. import paths, stacks

_CORE_SERVICES = ["nginx", "dnsmasq"]


def _run_capture(cmd: Sequence[str], cwd: Path | None = None) -> tuple[int, str]:
    """任意のコマンドを実行し、(exit code, 標準出力+標準エラー) を返す。例外は投げない。"""
    try:
        result = subprocess.run(
            list(cmd), cwd=str(cwd or paths.REPO_ROOT), capture_output=True, text=True
        )
    except OSError as exc:
        return 1, f"$ {' '.join(str(c) for c in cmd)}\nエラー: コマンドを実行できませんでした: {exc}\n"

    lines = [f"$ {' '.join(str(c) for c in cmd)}"]
    if result.stdout:
        lines.append(result.stdout.rstrip("\n"))
    if result.stderr:
        lines.append(result.stderr.rstrip("\n"))
    return result.returncode, "\n".join(lines) + "\n"


def _run_script_capture(script_name: str, args: Sequence[str] = ()) -> tuple[int, str]:
    return _run_capture([str(paths.script_path(script_name)), *args])


def add_app(ns: argparse.Namespace) -> tuple[bool, str]:
    """`commands.app._add` 相当。new-app.sh を出力キャプチャ付きで実行する。"""
    cmd_args = [ns.app_name, ns.repo_path, ns.compose_file]
    if ns.service_name:
        cmd_args.append(ns.service_name)
    cmd_args += [ns.subdomain, ns.port]
    code, output = _run_script_capture("new-app.sh", cmd_args)
    return code == 0, output


def remove_app(app_name: str) -> tuple[bool, str]:
    """`commands.app._remove` 相当(確認プロンプト無し版)。出力はキャプチャして返す。"""
    if not stacks.app_exists(app_name):
        return False, f"エラー: stacks/{app_name}/docker-compose.yml が見つかりません。\n"

    logs: list[str] = []

    code, output = _run_script_capture("render-compose.sh")
    logs.append(output)
    if code != 0:
        logs.append("エラー: render-compose.sh の実行に失敗しました。\n")
        return False, "\n".join(logs)

    try:
        services = stacks.app_services(app_name)
    except RuntimeError as exc:
        logs.append(f"エラー: {exc}\n")
        return False, "\n".join(logs)

    if services:
        code, output = _run_capture(
            ["docker", "compose", "-f", str(paths.COMPOSE_GENERATED), "rm", "-f", "-s", "-v", *services]
        )
        logs.append(output)
        if code != 0:
            logs.append(f"エラー: コンテナの削除に失敗しました(exit code {code})。\n")
            return False, "\n".join(logs)
    else:
        logs.append(
            f"注意: net-{app_name} に載っているサービスが見つかりませんでした"
            "(profilesで無効化されている可能性があります)。コンテナ削除はスキップします。\n"
        )

    _, output = _run_capture(["docker", "network", "rm", f"net-{app_name}"])
    logs.append(output)

    try:
        shutil.rmtree(paths.stack_dir(app_name))
    except OSError as exc:
        logs.append(
            f"エラー: stacks/{app_name}/ の削除に失敗しました: {exc}\n"
            f"コンテナと net-{app_name} ネットワークは既に削除済みです。"
            f"削除が中途半端な状態のため up.sh は実行していません。\n"
        )
        return False, "\n".join(logs)

    code, output = _run_script_capture("up.sh")
    logs.append(output)
    return code == 0, "\n".join(logs)


def restart_all() -> tuple[bool, str]:
    """`commands.restart._restart`(app_name無し)相当。down.sh→up.shを実行する。"""
    logs: list[str] = []
    code, output = _run_script_capture("down.sh")
    logs.append(output)
    if code != 0:
        return False, "\n".join(logs)
    code, output = _run_script_capture("up.sh")
    logs.append(output)
    return code == 0, "\n".join(logs)


def restart_app(app_name: str) -> tuple[bool, str]:
    """`commands.restart._restart`(app_name指定)相当。"""
    if not stacks.app_exists(app_name):
        return False, f"エラー: stacks/{app_name}/docker-compose.yml が見つかりません。\n"
    try:
        services = stacks.app_services(app_name)
    except RuntimeError as exc:
        return False, f"エラー: {exc}\n"
    if not services:
        return False, (
            f"エラー: net-{app_name} に載っているサービスが見つかりません"
            "(profilesで無効化されている可能性があります)。\n"
        )
    code, output = _run_capture(
        ["docker", "compose", "-f", str(paths.COMPOSE_GENERATED), "restart", *services]
    )
    return code == 0, output


def renew_cert(domain: str = "ubuntu.local") -> tuple[bool, str]:
    """`commands.cert._renew` 相当。"""
    code, output = _run_script_capture("generate-cert.sh", [domain])
    return code == 0, output


def service_add() -> tuple[bool, str]:
    """`commands.service._add` 相当。"""
    code, output = _run_script_capture("install-service.sh")
    return code == 0, output


def service_remove() -> tuple[bool, str]:
    """`commands.service._remove` 相当。"""
    code, output = _run_script_capture("uninstall-service.sh")
    return code == 0, output


def run_init() -> tuple[bool, str]:
    """`commands.init._init` 相当。setup-dns.sh → generate-cert.sh → up.sh を順に実行する。"""
    steps: list[tuple[str, list[str]]] = [
        ("setup-dns.sh", []),
        ("generate-cert.sh", ["ubuntu.local"]),
        ("up.sh", []),
    ]
    logs: list[str] = []
    for script_name, script_args in steps:
        display = script_name if not script_args else f"{script_name} {' '.join(script_args)}"
        logs.append(f"==> {display}")
        code, output = _run_script_capture(script_name, script_args)
        logs.append(output)
        if code != 0:
            logs.append(f"!!! {script_name} が失敗しました(exit code {code})。ここで停止します。\n")
            return False, "\n".join(logs)
    return True, "\n".join(logs)
