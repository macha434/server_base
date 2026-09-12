"""`server-base cert renew [domain]` — TLS証明書を再発行する。"""
from __future__ import annotations

import argparse

from .. import shell


def _renew(args: argparse.Namespace) -> int:
    return shell.run_script("generate-cert.sh", [args.domain])


def register(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("cert", help="TLS証明書の操作")
    cert_sub = parser.add_subparsers(dest="cert_command", required=True)

    renew_parser = cert_sub.add_parser("renew", help="TLS証明書を再発行する")
    renew_parser.add_argument("domain", nargs="?", default="ubuntu.local", help="省略時はubuntu.local")
    renew_parser.set_defaults(func=_renew)
