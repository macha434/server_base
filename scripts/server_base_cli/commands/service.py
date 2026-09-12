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
