"""server-base TUI アプリ本体。引数無し実行時のデフォルトエントリポイント。"""
from __future__ import annotations

from typing import Callable

from textual import work
from textual.app import App
from textual.binding import Binding
from textual.screen import ModalScreen

from . import actions
from .screens import (
    AppManageScreen,
    ConfirmScreen,
    ActionRunningScreen,
    DashboardScreen,
    DoctorScreen,
    LogsScreen,
    ServiceScreen,
)


class ServerBaseApp(App):
    """server-base TUI ダッシュボードアプリ。"""

    TITLE = "server-base"

    BINDINGS = [
        Binding("q", "quit", "終了"),
        Binding("d", "show_doctor", "Doctor"),
        Binding("l", "show_logs", "Logs"),
        Binding("a", "show_apps", "アプリ管理"),
        Binding("i", "run_init", "初回セットアップ"),
        Binding("c", "renew_cert", "証明書更新"),
        Binding("s", "show_service", "systemdサービス"),
        Binding("escape", "back_to_dashboard", "戻る", show=False),
        Binding("b", "back_to_dashboard", "戻る"),
    ]

    def on_mount(self) -> None:
        self.push_screen(DashboardScreen())

    def _navigate(self, screen_factory) -> None:
        # モーダル(確認/実行結果)表示中はメイン画面のナビゲーションを無視する。
        # モーダル自身のescape/bバインディングが優先されるのが通常だが、
        # d/l/a/i/c/sはモーダル側で束縛していないため念のためガードする。
        if isinstance(self.screen, ModalScreen):
            return
        self.switch_screen(screen_factory())

    def action_show_doctor(self) -> None:
        self._navigate(DoctorScreen)

    def action_show_logs(self) -> None:
        self._navigate(LogsScreen)

    def action_show_apps(self) -> None:
        self._navigate(AppManageScreen)

    def action_show_service(self) -> None:
        self._navigate(ServiceScreen)

    def action_back_to_dashboard(self) -> None:
        self._navigate(DashboardScreen)

    async def confirm_and_run(
        self, message: str, title: str, action: Callable[[], tuple[bool, str]]
    ) -> None:
        """確認モーダル→実行結果モーダルの順に表示し、完了後にダッシュボードへ戻る。

        `push_screen_wait` はワーカー内からしか呼べないため、呼び出し元
        (Button/OptionListのメッセージハンドラ等)は必ず `@work` を付けた
        メソッドから呼ぶこと(モーダル遷移をメッセージハンドラの呼び出し
        フレーム内で同期的に完結させると、textualの内部で画面遷移が
        デッドロックする既知の問題があるため)。
        """
        confirmed = await self.push_screen_wait(ConfirmScreen(message, title=title))
        if not confirmed:
            return
        await self.push_screen_wait(ActionRunningScreen(title, action))
        self.switch_screen(DashboardScreen())

    @work
    async def action_run_init(self) -> None:
        if isinstance(self.screen, ModalScreen):
            return
        await self.confirm_and_run(
            "DNS設定・TLS証明書発行・core起動を順に行います。よろしいですか?",
            "初回セットアップ",
            actions.run_init,
        )

    @work
    async def action_renew_cert(self) -> None:
        if isinstance(self.screen, ModalScreen):
            return
        await self.confirm_and_run(
            "ubuntu.local のTLS証明書を再発行します。よろしいですか?",
            "証明書更新",
            actions.renew_cert,
        )


def run_tui() -> int:
    ServerBaseApp().run()
    return 0
