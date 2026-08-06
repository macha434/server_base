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
