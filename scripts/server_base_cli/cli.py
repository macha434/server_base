"""`server-base cli <サブコマンド>` — 個別のCLI操作をまとめるサブパーサ。

status/logs/restart/doctor/app/cert/service/init は元々トップレベルの
サブコマンドだったが、TUI(`server-base` を引数無しで実行)をデフォルトの
入り口にするため `cli` の下にまとめた。各コマンドモジュール自体は無変更。
"""
from __future__ import annotations

import argparse

from .commands import app, cert, doctor, init, logs, restart, service, status


def register(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "cli", help="個別のCLI操作(status/logs/restart/doctor/app/cert/service/init)"
    )
    cli_sub = parser.add_subparsers(dest="cli_command", required=True)

    app.register(cli_sub)
    cert.register(cli_sub)
    doctor.register(cli_sub)
    init.register(cli_sub)
    logs.register(cli_sub)
    restart.register(cli_sub)
    service.register(cli_sub)
    status.register(cli_sub)
