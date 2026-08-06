"""server-base CLI の argparse エントリポイント。"""
from __future__ import annotations

import argparse

from .commands import app, cert, doctor, init, logs, restart, service, status


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="server-base",
        description="server_base の運用操作(初回セットアップ・アプリ追加削除・稼働確認等)をまとめて行うCLI",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    app.register(subparsers)
    cert.register(subparsers)
    doctor.register(subparsers)
    init.register(subparsers)
    logs.register(subparsers)
    restart.register(subparsers)
    service.register(subparsers)
    status.register(subparsers)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)
