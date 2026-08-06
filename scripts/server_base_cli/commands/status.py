"""`server-base status` — coreと各アプリの稼働状況を表示する。"""
from __future__ import annotations

import argparse

from .. import paths, shell, stacks

_CORE_SERVICES = ["nginx", "dnsmasq"]


def _container_state(service: str) -> str:
    result = shell.capture(
        ["docker", "compose", "-f", str(paths.COMPOSE_GENERATED), "ps", "--format", "{{.State}}", service]
    )
    state = result.stdout.strip()
    return state if state else "stopped"


def _url_reachable(url: str) -> bool:
    result = shell.capture(["curl", "-k", "-s", "-o", "/dev/null", "-w", "%{http_code}", url])
    return result.returncode == 0 and result.stdout.strip().startswith(("2", "3"))


def _systemd_enabled() -> bool:
    result = shell.capture(["systemctl", "--user", "is-enabled", "core-stack.service"])
    return result.returncode == 0


def _status(args: argparse.Namespace) -> int:
    print("== core ==")
    for service in _CORE_SERVICES:
        print(f"  {service}: {_container_state(service)}")
    print(f"  systemdサービス: {'有効' if _systemd_enabled() else '未登録/無効'}")

    print("== apps ==")
    apps = stacks.list_apps()
    if not apps:
        print("  (登録済みアプリはありません)")
    for app_name in apps:
        services = stacks.app_services(app_name)
        states = ", ".join(f"{s}={_container_state(s)}" for s in services)
        url = f"https://{app_name}.ubuntu.local/"
        reachable = "到達可" if _url_reachable(url) else "到達不可"
        print(f"  {app_name}: {states} | {url} ({reachable})")

    return 0


def register(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("status", help="coreと各アプリの稼働状況を表示する")
    parser.set_defaults(func=_status)
