"""`server-base app add|remove` — stacks/<app名>/docker-compose.yml の追加・削除。"""
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

    try:
        services = stacks.app_services(app_name)
    except RuntimeError as exc:
        print(f"エラー: {exc}", file=sys.stderr)
        return 1

    if services:
        code = shell.run(
            ["docker", "compose", "-f", str(paths.COMPOSE_GENERATED), "rm", "-f", "-s", "-v", *services]
        )
        if code != 0:
            print(f"エラー: コンテナの削除に失敗しました(exit code {code})。", file=sys.stderr)
            return code

    shell.run(["docker", "network", "rm", f"net-{app_name}"])

    try:
        shutil.rmtree(paths.stack_dir(app_name))
    except OSError as exc:
        print(
            f"エラー: stacks/{app_name}/ の削除に失敗しました: {exc}\n"
            f"コンテナと net-{app_name} ネットワークは既に削除済みです。"
            f"削除が中途半端な状態のため up.sh は実行していません。\n"
            f"stacks/{app_name}/ を手動で削除してから ./scripts/up.sh を実行してください。",
            file=sys.stderr,
        )
        return 1

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
