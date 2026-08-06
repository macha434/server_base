"""`server-base doctor` — 起動前の環境チェック一式。"""
from __future__ import annotations

import argparse
import socket
from datetime import datetime, timedelta

from .. import paths, shell

_CORE_TCP_PORTS = [80, 443]


def _port_in_use(port: int, kind: str) -> bool:
    sock_type = socket.SOCK_STREAM if kind == "tcp" else socket.SOCK_DGRAM
    with socket.socket(socket.AF_INET, sock_type) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("0.0.0.0", port))
        except OSError:
            return True
        return False


def _check_docker() -> tuple[str, str]:
    result = shell.capture(["docker", "info"])
    if result.returncode == 0:
        return "ok", "Dockerデーモンに接続できます"
    return "fail", "Dockerデーモンに接続できません(`docker info` が失敗)"


def _check_ports() -> tuple[str, str]:
    busy = [f"{p}/tcp" for p in _CORE_TCP_PORTS if _port_in_use(p, "tcp")]
    if _port_in_use(53, "tcp"):
        busy.append("53/tcp")
    if _port_in_use(53, "udp"):
        busy.append("53/udp")
    if not busy:
        return "ok", "ポート80/443/53は空いています(またはserver_baseのコンテナが使用中です)"
    return "warn", f"以下のポートが使用中です: {', '.join(busy)}(nginx/dnsmasq以外のプロセスの可能性)"


def _check_dns() -> tuple[str, str]:
    result = shell.capture(["dig", "@127.0.0.1", "ubuntu.local", "+short"])
    if result.returncode == 0 and result.stdout.strip():
        return "ok", f"ubuntu.local は 127.0.0.1 経由で解決できます({result.stdout.strip()})"
    return "fail", "ubuntu.local を 127.0.0.1 経由で解決できません(dnsmasqコンテナが未起動の可能性)"


def _check_cert() -> tuple[str, str]:
    cert_path = paths.SSL_DIR / "ubuntu.local-cert.pem"
    if not cert_path.is_file():
        return "fail", f"{cert_path} が見つかりません(`server-base cert renew` 未実行)"

    result = shell.capture(["openssl", "x509", "-enddate", "-noout", "-in", str(cert_path)])
    if result.returncode != 0:
        return "fail", "証明書の有効期限を読み取れませんでした"

    end_str = result.stdout.strip().split("=", 1)[-1]
    end_date = datetime.strptime(end_str, "%b %d %H:%M:%S %Y %Z")
    remaining = end_date - datetime.utcnow()

    if remaining < timedelta(days=0):
        return "fail", f"証明書の有効期限が切れています({end_date.date()})"
    if remaining < timedelta(days=30):
        return "warn", f"証明書の有効期限が近づいています(残り{remaining.days}日, {end_date.date()})"
    return "ok", f"証明書は有効です(残り{remaining.days}日, {end_date.date()})"


def _check_nginx_config() -> tuple[str, str]:
    state_result = shell.capture(
        ["docker", "compose", "-f", str(paths.COMPOSE_GENERATED), "ps", "--format", "{{.State}}", "nginx"]
    )
    if state_result.stdout.strip() != "running":
        return "warn", "nginxコンテナが起動していないため設定確認をスキップしました"

    test_result = shell.capture(
        ["docker", "compose", "-f", str(paths.COMPOSE_GENERATED), "exec", "-T", "nginx", "nginx", "-t"]
    )
    if test_result.returncode == 0:
        return "ok", "nginx設定は正常です(nginx -t)"
    return "fail", f"nginx -t が失敗しました: {test_result.stderr.strip()}"


def _check_systemd_service() -> tuple[str, str]:
    result = shell.capture(["systemctl", "--user", "is-enabled", "core-stack.service"])
    if result.returncode == 0:
        return "ok", f"systemdユーザーサービスは有効です({result.stdout.strip()})"
    return "warn", "systemdユーザーサービスは未登録です(`server-base service add` で登録できます)"


_CHECKS: list[tuple[str, "Callable[[], tuple[str, str]]"]] = [
    ("Docker", _check_docker),
    ("ポート(80/443/53)", _check_ports),
    ("DNS解決", _check_dns),
    ("TLS証明書", _check_cert),
    ("nginx設定", _check_nginx_config),
    ("systemdサービス", _check_systemd_service),
]

_SYMBOLS = {"ok": "✓", "warn": "⚠", "fail": "✗"}


def _doctor(args: argparse.Namespace) -> int:
    has_failure = False
    for label, check_fn in _CHECKS:
        status, message = check_fn()
        if status == "fail":
            has_failure = True
        print(f"{_SYMBOLS[status]} {label}: {message}")
    return 1 if has_failure else 0


def register(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("doctor", help="起動前の環境チェックを一括で行う")
    parser.set_defaults(func=_doctor)
