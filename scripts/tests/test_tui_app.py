"""server-base TUI のスモークテスト。

docker/systemd/実DNSに依存する関数はモックし、dockerが動いていない
CI/サンドボックス環境でも通るようにする。配線が壊れていないことの
確認が目的で、厳密な網羅は行わない。
"""
from __future__ import annotations

import asyncio
from unittest.mock import patch

from textual.widgets import Input, Button, OptionList

from server_base_cli.tui.app import ServerBaseApp
from server_base_cli.tui.screens import (
    ActionRunningScreen,
    AppAddScreen,
    AppManageScreen,
    ConfirmScreen,
    DashboardScreen,
    DoctorScreen,
    LogsScreen,
    ServiceScreen,
)


def run_scenario(coro_factory) -> None:
    """`async def scenario(): ...` を pytest-asyncio 無しで実行するヘルパー。"""
    asyncio.run(coro_factory())


def test_app_starts_and_shows_dashboard():
    """引数無し起動相当(ServerBaseApp)がクラッシュせず、最初にダッシュボードを表示する。"""

    async def scenario():
        with patch("server_base_cli.commands.status._container_state", return_value="running"), \
             patch("server_base_cli.commands.status._systemd_enabled", return_value=True), \
             patch("server_base_cli.commands.status._url_reachable", return_value=True), \
             patch("server_base_cli.stacks.list_apps", return_value=["myapp"]), \
             patch("server_base_cli.stacks.app_services", return_value=["myapp"]), \
             patch("server_base_cli.stacks.app_site_host", return_value="myapp.ubuntu.local"):
            app = ServerBaseApp()
            async with app.run_test() as pilot:
                assert isinstance(app.screen, DashboardScreen)
                await asyncio.sleep(0.2)
                await pilot.pause()
                table = app.screen.query_one("#dashboard-table")
                # core(nginx/dnsmasq/systemd) 3行 + myapp 1行
                assert table.row_count >= 4

    run_scenario(scenario)


def test_dashboard_manual_refresh_key_does_not_crash():
    async def scenario():
        with patch("server_base_cli.commands.status._container_state", return_value="stopped"), \
             patch("server_base_cli.commands.status._systemd_enabled", return_value=False), \
             patch("server_base_cli.stacks.list_apps", return_value=[]):
            app = ServerBaseApp()
            async with app.run_test() as pilot:
                await pilot.pause()
                await pilot.press("r")
                await asyncio.sleep(0.2)
                await pilot.pause()
                assert isinstance(app.screen, DashboardScreen)

    run_scenario(scenario)


def test_navigate_to_doctor_and_back():
    async def scenario():
        with patch("server_base_cli.stacks.list_apps", return_value=[]):
            app = ServerBaseApp()
            async with app.run_test() as pilot:
                await pilot.pause()
                await pilot.press("d")
                await pilot.pause()
                assert isinstance(app.screen, DoctorScreen)
                await asyncio.sleep(0.2)
                await pilot.pause()

                await pilot.press("b")
                await pilot.pause()
                assert isinstance(app.screen, DashboardScreen)

    run_scenario(scenario)


def test_navigate_to_logs_shows_target_list_and_back():
    async def scenario():
        with patch("server_base_cli.commands.status._container_state", return_value="running"), \
             patch("server_base_cli.commands.status._systemd_enabled", return_value=True), \
             patch("server_base_cli.stacks.list_apps", return_value=["myapp"]):
            app = ServerBaseApp()
            async with app.run_test() as pilot:
                await pilot.pause()
                await pilot.press("l")
                await pilot.pause()
                assert isinstance(app.screen, LogsScreen)
                option_list = app.screen.query_one("#log-target-list", OptionList)
                assert [opt.id for opt in option_list._options] == ["core", "myapp"]

                await pilot.press("escape")
                await pilot.pause()
                assert isinstance(app.screen, DashboardScreen)

    run_scenario(scenario)


def test_app_manage_navigation_and_add_form_cancel():
    async def scenario():
        with patch("server_base_cli.commands.status._container_state", return_value="running"), \
             patch("server_base_cli.commands.status._systemd_enabled", return_value=True), \
             patch("server_base_cli.stacks.list_apps", return_value=["myapp"]):
            app = ServerBaseApp()
            async with app.run_test(size=(80, 60)) as pilot:
                await pilot.pause()
                await pilot.press("a")
                await pilot.pause()
                assert isinstance(app.screen, AppManageScreen)

                await pilot.press("n")
                await pilot.pause()
                assert isinstance(app.screen, AppAddScreen)

                await pilot.press("escape")
                await pilot.pause()
                assert isinstance(app.screen, AppManageScreen)

    run_scenario(scenario)


def test_app_add_flow_runs_action_and_returns_to_dashboard():
    """Buttonクリック起点のConfirm→ActionRunning→ダッシュボード復帰の配線を確認する。"""

    async def scenario():
        with patch("server_base_cli.commands.status._container_state", return_value="running"), \
             patch("server_base_cli.commands.status._systemd_enabled", return_value=True), \
             patch("server_base_cli.stacks.list_apps", return_value=[]), \
             patch("server_base_cli.tui.actions.add_app", return_value=(True, "added")) as mock_add:
            app = ServerBaseApp()
            async with app.run_test(size=(80, 60)) as pilot:
                await pilot.pause()
                app.switch_screen(AppAddScreen())
                await pilot.pause()

                for field_id, value in [
                    ("#input-repo-url", "https://github.com/org/newapp"),
                    ("#input-compose-file", "docker-compose.yml"),
                    ("#input-subdomain", "newapp"),
                    ("#input-port", "3000"),
                ]:
                    app.screen.query_one(field_id, Input).value = value

                app.screen.query_one("#submit-add", Button).press()
                await pilot.pause()
                assert isinstance(app.screen, ConfirmScreen)

                await pilot.press("y")
                await pilot.pause()
                assert isinstance(app.screen, ActionRunningScreen)

                await asyncio.sleep(0.3)
                await pilot.pause()
                await pilot.press("b")
                await pilot.pause()

                assert isinstance(app.screen, DashboardScreen)
                assert mock_add.called

    run_scenario(scenario)


def test_confirm_screen_cancel_does_not_run_action():
    """確認モーダルで'n'を押すと操作は実行されない。"""

    async def scenario():
        with patch("server_base_cli.commands.status._container_state", return_value="running"), \
             patch("server_base_cli.commands.status._systemd_enabled", return_value=True), \
             patch("server_base_cli.stacks.list_apps", return_value=[]), \
             patch("server_base_cli.tui.actions.renew_cert", return_value=(True, "ok")) as mock_cert:
            app = ServerBaseApp()
            async with app.run_test() as pilot:
                await pilot.pause()
                await pilot.press("c")
                await pilot.pause()
                assert isinstance(app.screen, ConfirmScreen)

                await pilot.press("n")
                await pilot.pause()
                assert not isinstance(app.screen, ConfirmScreen)
                assert not mock_cert.called

    run_scenario(scenario)


def test_service_screen_navigation():
    async def scenario():
        with patch("server_base_cli.stacks.list_apps", return_value=[]):
            app = ServerBaseApp()
            async with app.run_test() as pilot:
                await pilot.pause()
                await pilot.press("s")
                await pilot.pause()
                assert isinstance(app.screen, ServiceScreen)

                await pilot.press("b")
                await pilot.pause()
                assert isinstance(app.screen, DashboardScreen)

    run_scenario(scenario)


def test_dashboard_restart_all_flow():
    async def scenario():
        with patch("server_base_cli.commands.status._container_state", return_value="running"), \
             patch("server_base_cli.commands.status._systemd_enabled", return_value=True), \
             patch("server_base_cli.stacks.list_apps", return_value=[]), \
             patch("server_base_cli.tui.actions.restart_all", return_value=(True, "restarted")) as mock_restart:
            app = ServerBaseApp()
            async with app.run_test() as pilot:
                await pilot.pause()
                await pilot.press("R")
                await pilot.pause()
                assert isinstance(app.screen, ConfirmScreen)

                await pilot.press("y")
                await pilot.pause()
                assert isinstance(app.screen, ActionRunningScreen)

                await asyncio.sleep(0.3)
                await pilot.pause()
                await pilot.press("b")
                await pilot.pause()

                assert isinstance(app.screen, DashboardScreen)
                assert mock_restart.called

    run_scenario(scenario)


def test_dashboard_restart_selected_rejects_core_row():
    """core行を選んで再起動しようとしても actions.restart_app は呼ばれない。"""

    async def scenario():
        with patch("server_base_cli.commands.status._container_state", return_value="running"), \
             patch("server_base_cli.commands.status._systemd_enabled", return_value=True), \
             patch("server_base_cli.stacks.list_apps", return_value=[]), \
             patch("server_base_cli.tui.actions.restart_app") as mock_restart:
            app = ServerBaseApp()
            async with app.run_test() as pilot:
                await pilot.pause()
                await asyncio.sleep(0.2)
                await pilot.pause()
                await pilot.press("enter")
                await pilot.pause()

                assert isinstance(app.screen, DashboardScreen)
                assert not mock_restart.called

    run_scenario(scenario)


def test_quit_key_exits_app():
    async def scenario():
        with patch("server_base_cli.stacks.list_apps", return_value=[]):
            app = ServerBaseApp()
            async with app.run_test() as pilot:
                await pilot.pause()
                await pilot.press("q")
                await pilot.pause()
                assert app._exit is True

    run_scenario(scenario)
