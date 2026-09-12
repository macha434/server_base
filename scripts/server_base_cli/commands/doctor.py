"""`server-base doctor` — 起動前の環境チェック一式。"""
from __future__ import annotations

import argparse
import socket
from datetime import datetime, timedelta

from .. import paths, shell

_CORE_TCP_PORTS = [80, 443]


def _port_in_use(port: int, kind: str) -> bool | None:
    """指定ポートの使用状況を調べる。

    戻り値:
        True  — 使用中
        False — 空いている
        None  — 権限不足(EACCES)などで判定できない
    """
    sock_type = socket.SOCK_STREAM if kind == "tcp" else socket.SOCK_DGRAM
    with socket.socket(socket.AF_INET, sock_type) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("0.0.0.0", port))
        except PermissionError:
            return None
        except OSError:
            return True
        return False


def _check_docker() -> tuple[str, str]:
    try:
        result = shell.capture(["docker", "info"])
    except Exception as exc:
        return "fail", f"`docker info` を実行できませんでした(Docker未インストールの可能性): {exc}"
    if result.returncode == 0:
        return "ok", "Dockerデーモンに接続できます"
    return "fail", "Dockerデーモンに接続できません(`docker info` が失敗)"


def _check_ports() -> tuple[str, str]:
    try:
        targets = [(p, "tcp") for p in _CORE_TCP_PORTS] + [(53, "tcp"), (53, "udp")]
        busy = []
        unknown = []
        for port, kind in targets:
            state = _port_in_use(port, kind)
            if state is True:
                busy.append(f"{port}/{kind}")
            elif state is None:
                unknown.append(f"{port}/{kind}")
    except Exception as exc:
        return "fail", f"ポート確認中にエラーが発生しました: {exc}"

    if not busy and not unknown:
        return "ok", "ポート80/443/53は空いています(またはserver_baseのコンテナが使用中です)"

    parts = []
    if busy:
        parts.append(f"使用中: {', '.join(busy)}")
    if unknown:
        parts.append(f"確認不可(権限不足): {', '.join(unknown)}")
    return "warn", f"{'; '.join(parts)}(nginx/dnsmasq以外のプロセスの可能性)"


def _check_dns() -> tuple[str, str]:
    try:
        result = shell.capture(["dig", "@127.0.0.1", "ubuntu.local", "+short"])
    except Exception as exc:
        return "fail", f"`dig` を実行できませんでした(dig未インストールの可能性): {exc}"
    if result.returncode == 0 and result.stdout.strip():
        return "ok", f"ubuntu.local は 127.0.0.1 経由で解決できます({result.stdout.strip()})"
    return "fail", "ubuntu.local を 127.0.0.1 経由で解決できません(dnsmasqコンテナが未起動の可能性)"


def _check_cert() -> tuple[str, str]:
    cert_path = paths.SSL_DIR / "ubuntu.local-cert.pem"
    if not cert_path.is_file():
        return "fail", f"{cert_path} が見つかりません(`server-base cert renew` 未実行)"

    try:
        result = shell.capture(["openssl", "x509", "-enddate", "-noout", "-in", str(cert_path)])
    except Exception as exc:
        return "fail", f"`openssl` を実行できませんでした(openssl未インストールの可能性): {exc}"
    if result.returncode != 0:
        return "fail", "証明書の有効期限を読み取れませんでした"

    end_str = result.stdout.strip().split("=", 1)[-1]
    try:
        end_date = datetime.strptime(end_str, "%b %d %H:%M:%S %Y %Z")
    except ValueError as exc:
        return "fail", f"証明書の有効期限を解析できませんでした({exc})"
    remaining = end_date - datetime.utcnow()

    if remaining < timedelta(days=0):
        return "fail", f"証明書の有効期限が切れています({end_date.date()})"
    if remaining < timedelta(days=30):
        return "warn", f"証明書の有効期限が近づいています(残り{remaining.days}日, {end_date.date()})"
    return "ok", f"証明書は有効です(残り{remaining.days}日, {end_date.date()})"


def _check_nginx_config() -> tuple[str, str]:
    try:
        state_result = shell.capture(
            ["docker", "compose", "-f", str(paths.COMPOSE_GENERATED), "ps", "--format", "{{.State}}", "nginx"]
        )
    except Exception as exc:
        return "fail", f"`docker compose ps` を実行できませんでした: {exc}"
    if state_result.stdout.strip() != "running":
        return "warn", "nginxコンテナが起動していないため設定確認をスキップしました"

    try:
        test_result = shell.capture(
            ["docker", "compose", "-f", str(paths.COMPOSE_GENERATED), "exec", "-T", "nginx", "nginx", "-t"]
        )
    except Exception as exc:
        return "fail", f"`nginx -t` を実行できませんでした: {exc}"
    if test_result.returncode == 0:
        return "ok", "nginx設定は正常です(nginx -t)"
    return "fail", f"nginx -t が失敗しました: {test_result.stderr.strip()}"


def _check_systemd_service() -> tuple[str, str]:
    try:
        result = shell.capture(["systemctl", "--user", "is-enabled", "core-stack.service"])
    except Exception as exc:
        return "fail", f"`systemctl` を実行できませんでした: {exc}"
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
