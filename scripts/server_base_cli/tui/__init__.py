"""`server-base tui`(および引数無し実行のデフォルト)のサブパーサ登録。"""
from __future__ import annotations

import argparse


def _run(args: argparse.Namespace) -> int:
    from .app import run_tui

    return run_tui()


def register(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("tui", help="TUIダッシュボードを起動する(引数無し実行時のデフォルト)")
    parser.set_defaults(func=_run)
