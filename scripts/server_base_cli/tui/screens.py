"""server-base TUI の各画面(Screen)定義。

画面遷移は基本的に「メイン画面は switch_screen で1枚だけ入れ替える」
「確認/実行結果はModalScreenとして上に重ねる」という2パターンに統一する。
これにより `escape`/`b` の挙動(モーダルはキャンセル・メイン画面は
ダッシュボードに戻る)がどの画面でも一貫する。
"""
from __future__ import annotations

import argparse
import asyncio
from typing import Callable

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen, Screen
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    LoadingIndicator,
    OptionList,
    RichLog,
    Static,
)
from textual.widgets.option_list import Option

from .. import paths, stacks
from ..commands import status
from . import actions, data


class ConfirmScreen(ModalScreen[bool]):
    """Yes/Noの確認モーダル。dismiss(True/False)で結果を返す。"""

    DEFAULT_CSS = """
    ConfirmScreen {
        align: center middle;
    }
    ConfirmScreen > Vertical {
        width: 70%;
        max-width: 80;
        height: auto;
        padding: 1 2;
        border: round $primary;
        background: $surface;
    }
    ConfirmScreen #confirm-buttons {
        height: auto;
        margin-top: 1;
        align: right middle;
    }
    ConfirmScreen Button {
        margin-left: 1;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "キャンセル"),
        Binding("n", "cancel", "いいえ"),
        Binding("y", "confirm", "はい"),
    ]

    def __init__(self, message: str, title: str = "確認") -> None:
        super().__init__()
        self._message = message
        self._title = title

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static(self._title, id="confirm-title")
            yield Static(self._message, id="confirm-message")
            with Horizontal(id="confirm-buttons"):
                yield Button("キャンセル (n)", id="confirm-no")
                yield Button("実行 (y)", id="confirm-yes", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "confirm-yes")

    def action_confirm(self) -> None:
        self.dismiss(True)

    def action_cancel(self) -> None:
        self.dismiss(False)


class ActionRunningScreen(ModalScreen[None]):
    """確認後にワーカースレッドで操作を実行し、完了後に成功/失敗と出力を表示するモーダル。"""

    DEFAULT_CSS = """
    ActionRunningScreen {
        align: center middle;
    }
    ActionRunningScreen > Vertical {
        width: 90%;
        height: 80%;
        padding: 1 2;
        border: round $primary;
        background: $surface;
    }
    ActionRunningScreen #action-output {
        height: 1fr;
        border: round $panel;
    }
    ActionRunningScreen #action-close {
        margin-top: 1;
    }
    """

    BINDINGS = [
        Binding("escape", "close", "閉じる"),
        Binding("b", "close", "閉じる"),
    ]

    def __init__(self, title: str, action: Callable[[], tuple[bool, str]]) -> None:
        super().__init__()
        self._title = title
        self._action = action
        self._done = False

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static(f"{self._title} — 実行中...", id="action-title")
            yield LoadingIndicator(id="action-spinner")
            yield RichLog(id="action-output", wrap=True, markup=False, highlight=False)
            yield Button("閉じる", id="action-close", disabled=True)

    def on_mount(self) -> None:
        self.query_one("#action-output", RichLog).display = False
        self.run_action()

    @work(thread=True)
    def run_action(self) -> None:
        try:
            success, output = self._action()
        except Exception as exc:  # 操作側の想定外の例外もTUIをクラッシュさせない
            success, output = False, f"予期しないエラーが発生しました: {exc}"
        self.app.call_from_thread(self._show_result, success, output)

    def _show_result(self, success: bool, output: str) -> None:
        self._done = True
        self.query_one("#action-spinner", LoadingIndicator).display = False
        self.query_one("#action-title", Static).update(
            f"{self._title} — {'成功' if success else '失敗'}"
        )
        out = self.query_one("#action-output", RichLog)
        out.display = True
        out.write(output.strip() or "(出力なし)")
        self.query_one("#action-close", Button).disabled = False

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "action-close" and self._done:
            self.dismiss(None)

    def action_close(self) -> None:
        if self._done:
            self.dismiss(None)


class DashboardScreen(Screen):
    """ダッシュボード(デフォルト画面)。coreとアプリの稼働状況を一覧表示する。"""

    BINDINGS = [
        Binding("r", "refresh", "更新"),
        Binding("R", "restart_all", "全体再起動"),
        Binding("enter", "restart_selected", "選択アプリ再起動"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        yield DataTable(id="dashboard-table")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#dashboard-table", DataTable)
        table.add_columns("区分", "名前", "状態", "URL", "到達性")
        table.cursor_type = "row"
        self.refresh_data()
        self.set_interval(5, self.refresh_data)

    def action_refresh(self) -> None:
        self.refresh_data()

    @work(thread=True, exclusive=True)
    def refresh_data(self) -> None:
        rows = data.collect_dashboard_rows()
        self.app.call_from_thread(self._render_rows, rows)

    def _render_rows(self, rows: list[data.DashboardRow]) -> None:
        table = self.query_one("#dashboard-table", DataTable)
        # 5秒ごとの自動更新でtable.clear()するとカーソルが先頭行に戻ってしまうため、
        # 更新前のカーソル位置を保存し、再描画後に(行数が減っていた場合は末尾に丸めて)復元する。
        previous_cursor_row = table.cursor_row
        table.clear()
        for row in rows:
            table.add_row(row.category, row.name, row.state, row.url, row.reachable)
        if previous_cursor_row is not None and table.row_count:
            table.move_cursor(row=min(previous_cursor_row, table.row_count - 1))

    @work
    async def action_restart_all(self) -> None:
        await self.app.confirm_and_run(
            "core+全アプリを再起動します(down→up)。よろしいですか?",
            "全体再起動",
            actions.restart_all,
        )

    @work
    async def action_restart_selected(self) -> None:
        table = self.query_one("#dashboard-table", DataTable)
        if table.cursor_row is None or table.row_count == 0:
            return
        category, name = table.get_row_at(table.cursor_row)[:2]
        if category != "app":
            self.notify("再起動できるのはアプリの行のみです('R'でcore+全体を再起動)。", severity="warning")
            return
        await self.app.confirm_and_run(
            f"{name} を再起動します。よろしいですか?",
            f"再起動: {name}",
            lambda: actions.restart_app(name),
        )


class DoctorScreen(Screen):
    """`server-base cli doctor` 相当のチェック結果を表示する。"""

    BINDINGS = [
        Binding("escape", "back", "戻る", show=False),
        Binding("b", "back", "戻る"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        yield DataTable(id="doctor-table")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#doctor-table", DataTable)
        table.add_columns("", "チェック", "メッセージ")
        self.refresh_data()

    @work(thread=True, exclusive=True)
    def refresh_data(self) -> None:
        rows = data.collect_doctor_rows()
        self.app.call_from_thread(self._render_rows, rows)

    def _render_rows(self, rows: list[data.DoctorRow]) -> None:
        table = self.query_one("#doctor-table", DataTable)
        table.clear()
        for row in rows:
            table.add_row(row.symbol, row.label, row.message)

    def action_back(self) -> None:
        self.app.switch_screen(DashboardScreen())


class LogsScreen(Screen):
    """coreまたは指定アプリのログをライブテールする(自前asyncio実装)。"""

    BINDINGS = [
        Binding("escape", "back", "戻る", show=False),
        Binding("b", "back", "戻る"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._proc: asyncio.subprocess.Process | None = None
        self._tail_worker = None

    def compose(self) -> ComposeResult:
        yield Header()
        options = [Option("core (nginx/dnsmasq)", id="core")]
        options += [Option(name, id=name) for name in stacks.list_apps()]
        yield OptionList(*options, id="log-target-list")
        yield RichLog(id="log-view", wrap=True, markup=False, highlight=False)
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#log-view", RichLog).display = False

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        target = event.option_id
        if target is None:
            return
        self.query_one("#log-target-list", OptionList).display = False
        log_view = self.query_one("#log-view", RichLog)
        log_view.display = True
        self._tail_worker = self._start_tail(target)

    @work(exclusive=True)
    async def _start_tail(self, target: str) -> None:
        log_view = self.query_one("#log-view", RichLog)
        if target == "core":
            services = list(status._CORE_SERVICES)
        else:
            try:
                services = stacks.app_services(target)
            except RuntimeError as exc:
                log_view.write(f"エラー: {exc}")
                return
            if not services:
                log_view.write(f"エラー: net-{target} に載っているサービスが見つかりません。")
                return

        cmd = ["docker", "compose", "-f", str(paths.COMPOSE_GENERATED), "logs", "-f", *services]
        log_view.write(f"$ {' '.join(cmd)}")
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT
            )
        except OSError as exc:
            log_view.write(f"エラー: ログ取得コマンドを起動できませんでした: {exc}")
            return

        self._proc = proc
        try:
            stdout = proc.stdout
            if stdout is None:
                return
            while True:
                line = await stdout.readline()
                if not line:
                    break
                log_view.write(line.decode(errors="replace").rstrip("\n"))
        finally:
            self._kill_proc()

    def _kill_proc(self) -> None:
        proc, self._proc = self._proc, None
        if proc is not None and proc.returncode is None:
            for signal_fn in (proc.terminate, proc.kill):
                try:
                    signal_fn()
                except ProcessLookupError:
                    break

    def action_back(self) -> None:
        self.app.switch_screen(DashboardScreen())

    def on_unmount(self) -> None:
        if self._tail_worker is not None:
            self._tail_worker.cancel()
        self._kill_proc()


class AppAddScreen(Screen):
    """アプリ追加フォーム(new-app.sh相当)。"""

    BINDINGS = [
        Binding("escape", "cancel", "戻る", show=False),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(id="add-app-form"):
            yield Label("アプリ名 (app_name)")
            yield Input(placeholder="myapp", id="input-app-name")
            yield Label("リポジトリパス (repo_path)")
            yield Input(placeholder="../myapp-repo", id="input-repo-path")
            yield Label("composeファイルパス (compose_file)")
            yield Input(placeholder="docker-compose.yml", id="input-compose-file")
            yield Label("サービス名(任意・省略時は自動検出)")
            yield Input(placeholder="", id="input-service-name")
            yield Label("サブドメイン (subdomain)")
            yield Input(placeholder="myapp", id="input-subdomain")
            yield Label("ポート番号 (port)")
            yield Input(placeholder="3000", id="input-port")
            yield Button("追加を実行", id="submit-add", variant="primary")
        yield Footer()

    def _value(self, input_id: str) -> str:
        return self.query_one(input_id, Input).value.strip()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id != "submit-add":
            return

        app_name = self._value("#input-app-name")
        repo_path = self._value("#input-repo-path")
        compose_file = self._value("#input-compose-file")
        service_name = self._value("#input-service-name") or None
        subdomain = self._value("#input-subdomain")
        port = self._value("#input-port")

        if not all([app_name, repo_path, compose_file, subdomain, port]):
            self.app.bell()
            self.notify("app_name/repo_path/compose_file/subdomain/port は必須です。", severity="warning")
            return

        ns = argparse.Namespace(
            app_name=app_name,
            repo_path=repo_path,
            compose_file=compose_file,
            service_name=service_name,
            subdomain=subdomain,
            port=port,
        )
        self._submit(app_name, ns)

    @work
    async def _submit(self, app_name: str, ns: argparse.Namespace) -> None:
        # ConfirmScreen→ActionRunningScreenの遷移は`@work`のワーカー内で
        # `push_screen_wait`を使って行う(on_button_pressedの呼び出しフレーム内で
        # 同期的にpush_screenの連鎖を完結させるとtextualの画面遷移がデッドロック
        # する既知の問題があるため)。
        await self.app.confirm_and_run(
            f"stacks/{app_name}/ を追加します。よろしいですか?",
            f"アプリ追加: {app_name}",
            lambda: actions.add_app(ns),
        )

    def action_cancel(self) -> None:
        self.app.switch_screen(AppManageScreen())


class AppManageScreen(Screen):
    """アプリの追加・削除。"""

    BINDINGS = [
        Binding("n", "open_add_form", "追加"),
        Binding("escape", "back", "戻る", show=False),
        Binding("b", "back", "戻る"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("登録済みアプリ一覧(Enterで削除、'n'で新規追加)", id="app-manage-help")
        yield OptionList(id="app-list")
        yield Footer()

    def on_mount(self) -> None:
        self._reload_apps()

    def _reload_apps(self) -> None:
        option_list = self.query_one("#app-list", OptionList)
        option_list.clear_options()
        apps = stacks.list_apps()
        if not apps:
            option_list.add_option(Option("(登録済みアプリはありません)", id="__none__", disabled=True))
            return
        for name in apps:
            option_list.add_option(Option(name, id=name))

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        app_name = event.option_id
        if not app_name or app_name == "__none__":
            return
        self._confirm_remove(app_name)

    @work
    async def _confirm_remove(self, app_name: str) -> None:
        await self.app.confirm_and_run(
            f"以下を削除します: stacks/{app_name}/ ・コンテナ ・net-{app_name} ネットワーク\n続行しますか?",
            f"アプリ削除: {app_name}",
            lambda: actions.remove_app(app_name),
        )

    def action_open_add_form(self) -> None:
        self.app.switch_screen(AppAddScreen())

    def action_back(self) -> None:
        self.app.switch_screen(DashboardScreen())


class ServiceScreen(Screen):
    """systemdユーザーサービス(core-stack.service)の登録・解除。"""

    BINDINGS = [
        Binding("escape", "back", "戻る", show=False),
        Binding("b", "back", "戻る"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("systemdユーザーサービス(core-stack.service)を選択してください", id="service-help")
        yield OptionList(
            Option("登録する (install-service.sh)", id="add"),
            Option("解除する (uninstall-service.sh)", id="remove"),
            id="service-options",
        )
        yield Footer()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option_id == "add":
            title = "systemdサービス登録"
            message = "core-stack.service を登録します。よろしいですか?"
            action_fn: Callable[[], tuple[bool, str]] = actions.service_add
        else:
            title = "systemdサービス解除"
            message = "core-stack.service の登録を解除します。よろしいですか?"
            action_fn = actions.service_remove
        self._confirm_service(title, message, action_fn)

    @work
    async def _confirm_service(
        self, title: str, message: str, action_fn: Callable[[], tuple[bool, str]]
    ) -> None:
        await self.app.confirm_and_run(message, title, action_fn)

    def action_back(self) -> None:
        self.app.switch_screen(DashboardScreen())
