"""`server-base status` — coreと各アプリの稼働状況を表示する。"""
from __future__ import annotations

import argparse

from .. import paths, shell, stacks

_CORE_SERVICES = ["nginx", "dnsmasq"]


def _container_state(service: str) -> str:
    try:
        result = shell.capture(
            ["docker", "compose", "-f", str(paths.COMPOSE_GENERATED), "ps", "--format", "{{.State}}", service]
        )
    except Exception:
        return "確認不可"
    if result.returncode != 0:
        # dockerデーモンに到達できない等。コンテナが停止しているのとは区別する。
        return "確認不可"
    state = result.stdout.strip()
    return state if state else "stopped"


def _url_reachable(url: str) -> bool:
    try:
        result = shell.capture(["curl", "-k", "-s", "-o", "/dev/null", "-w", "%{http_code}", url])
    except Exception:
        return False
    return result.returncode == 0 and result.stdout.strip().startswith(("2", "3"))


def _systemd_enabled() -> bool:
    try:
        result = shell.capture(["systemctl", "--user", "is-enabled", "core-stack.service"])
    except Exception:
        return False
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
        try:
            services = stacks.app_services(app_name)
            host = stacks.app_site_host(app_name)
        except Exception:
            print(f"  {app_name}: (サービス情報が確認できません)")
            continue

        states = ", ".join(f"{s}={_container_state(s)}" for s in services)

        if host is None:
            print(f"  {app_name}: {states} | (site.hostラベルが見つかりません)")
            continue

        url = f"https://{host}/"
        reachable = "到達可" if _url_reachable(url) else "到達不可"
        print(f"  {app_name}: {states} | {url} ({reachable})")

    return 0


def register(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("status", help="coreと各アプリの稼働状況を表示する")
    parser.set_defaults(func=_status)
