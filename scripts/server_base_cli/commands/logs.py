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
        try:
            services = stacks.app_services(args.app_name)
        except RuntimeError as exc:
            print(f"エラー: {exc}", file=sys.stderr)
            return 1
    else:
        services = _CORE_SERVICES

    return shell.run(["docker", "compose", "-f", str(paths.COMPOSE_GENERATED), "logs", "-f", *services])


def register(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("logs", help="coreまたは指定アプリのログを表示する(docker compose logs -f)")
    parser.add_argument("app_name", nargs="?", default=None, help="省略時はcore(nginx/dnsmasq)")
    parser.set_defaults(func=_logs)
