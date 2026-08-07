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
        try:
            services = stacks.app_services(args.app_name)
        except RuntimeError as exc:
            print(f"エラー: {exc}", file=sys.stderr)
            return 1
        return shell.run(["docker", "compose", "-f", str(paths.COMPOSE_GENERATED), "restart", *services])

    code = shell.run_script("down.sh")
    if code != 0:
        return code
    return shell.run_script("up.sh")


def register(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("restart", help="coreまたは指定アプリを再起動する")
    parser.add_argument("app_name", nargs="?", default=None, help="省略時はcore+全アプリ(down→up)")
    parser.set_defaults(func=_restart)
