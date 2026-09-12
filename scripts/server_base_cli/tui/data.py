"""ダッシュボード・Doctor画面で表示するデータの収集(ブロッキング処理)。

いずれもdocker/curl/systemctlを叩くため呼び出し側(TUI)は必ずワーカー
スレッドから呼ぶこと。UIウィジェットの更新はここでは行わない。
"""
from __future__ import annotations

from typing import NamedTuple

from ..commands import doctor, status
from .. import stacks

_CORE_SERVICES = ["nginx", "dnsmasq"]


class DashboardRow(NamedTuple):
    category: str
    name: str
    state: str
    url: str
    reachable: str


def collect_dashboard_rows() -> list[DashboardRow]:
    rows: list[DashboardRow] = []

    for service in _CORE_SERVICES:
        rows.append(DashboardRow("core", service, status._container_state(service), "", ""))
    rows.append(
        DashboardRow(
            "core", "systemd", "有効" if status._systemd_enabled() else "未登録/無効", "", ""
        )
    )

    for app_name in stacks.list_apps():
        try:
            services = stacks.app_services(app_name)
            host = stacks.app_site_host(app_name)
        except Exception:
            rows.append(DashboardRow("app", app_name, "(サービス情報が確認できません)", "", ""))
            continue

        state = ", ".join(f"{s}={status._container_state(s)}" for s in services) or "(サービス無し)"

        if host is None:
            rows.append(DashboardRow("app", app_name, state, "(site.hostラベル無し)", ""))
            continue

        url = f"https://{host}/"
        reachable = "到達可" if status._url_reachable(url) else "到達不可"
        rows.append(DashboardRow("app", app_name, state, url, reachable))

    return rows


class DoctorRow(NamedTuple):
    symbol: str
    label: str
    message: str


def collect_doctor_rows() -> list[DoctorRow]:
    rows: list[DoctorRow] = []
    for label, check_fn in doctor._CHECKS:
        state, message = check_fn()
        rows.append(DoctorRow(doctor._SYMBOLS[state], label, message))
    return rows
