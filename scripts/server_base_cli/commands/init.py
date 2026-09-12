"""`server-base init` — DNS・TLS証明書の発行とcoreの起動を一括で行う初回セットアップ。"""
from __future__ import annotations

import argparse
import sys

from .. import shell

_STEPS = [
    ("setup-dns.sh", []),
    ("generate-cert.sh", ["ubuntu.local"]),
    ("up.sh", []),
]


def _init(args: argparse.Namespace) -> int:
    for script_name, script_args in _STEPS:
        display = script_name if not script_args else f"{script_name} {' '.join(script_args)}"
        print(f"==> {display}")
        code = shell.run_script(script_name, script_args)
        if code != 0:
            print(f"!!! {script_name} が失敗しました(exit code {code})。ここで停止します。", file=sys.stderr)
            return code
    return 0


def register(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("init", help="DNS・TLS証明書の発行とcoreの起動を一括で行う")
    parser.set_defaults(func=_init)
