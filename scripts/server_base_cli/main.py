"""server-base CLI の argparse エントリポイント。

引数無しで実行すると TUI ダッシュボード(`tui`)が起動する。個別のCLI操作
(status/logs/restart/doctor/app/cert/service/init)は `cli` サブコマンドの下に
まとまっている(例: `server-base cli status`)。
"""
from __future__ import annotations

import argparse
import sys

from . import cli, tui


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="server-base",
        description="server_base の運用操作(初回セットアップ・アプリ追加削除・稼働確認等)をまとめて行うCLI/TUI",
    )
    subparsers = parser.add_subparsers(dest="command")

    cli.register(subparsers)
    tui.register(subparsers)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command is None:
            try:
                from .tui.app import run_tui
            except ImportError as exc:
                print(
                    f"エラー: TUIの起動に失敗しました({exc})。\n"
                    "'uv sync' を実行して依存関係(textual)をインストールしてください。\n"
                    "個別のCLI操作は 'server-base cli <サブコマンド>' で(標準ライブラリのみで動作します)。",
                    file=sys.stderr,
                )
                return 1

            return run_tui()
        return args.func(args)
    except KeyboardInterrupt:
        # `server-base cli logs -f` などの長時間実行コマンドをCtrl-Cで止めたときに
        # 生のトレースバックを出さない。130はSIGINTの慣例的なexit code。
        return 130
