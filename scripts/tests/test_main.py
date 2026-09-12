import sys
from unittest.mock import patch

import pytest

from server_base_cli.main import build_parser, main


def test_main_dispatches_to_subcommand_and_returns_its_exit_code():
    with patch("server_base_cli.commands.status._status", return_value=3) as mock_status:
        assert main(["cli", "status"]) == 3

    mock_status.assert_called_once()


def test_main_returns_130_on_keyboard_interrupt():
    """Ctrl-C(`server-base cli logs -f` 等)で生のトレースバックを出さず130を返す(I2)。"""
    with patch("server_base_cli.commands.status._status", side_effect=KeyboardInterrupt):
        assert main(["cli", "status"]) == 130


def test_main_does_not_swallow_other_exceptions():
    """KeyboardInterrupt以外は握り潰さない(バグを隠さないため)。"""
    with patch("server_base_cli.commands.status._status", side_effect=ValueError("boom")):
        with pytest.raises(ValueError):
            main(["cli", "status"])


def test_main_with_no_args_launches_tui():
    with patch("server_base_cli.tui.app.run_tui", return_value=0) as mock_run_tui:
        assert main([]) == 0

    mock_run_tui.assert_called_once()


def test_main_tui_subcommand_also_launches_tui():
    with patch("server_base_cli.tui.app.run_tui", return_value=0) as mock_run_tui:
        assert main(["tui"]) == 0

    mock_run_tui.assert_called_once()


def test_main_prints_friendly_message_when_textual_not_installed(capsys):
    """`uv sync` 未実行でtextualが無い環境でも生のImportErrorを出さない。

    `sys.modules[name] = None` は、その名前のimportを強制的にImportErrorに
    する標準的な手法(importlib documented behavior)。
    """
    with patch.dict(sys.modules, {"server_base_cli.tui.app": None}):
        assert main([]) == 1

    assert "uv sync" in capsys.readouterr().err


def test_build_parser_registers_all_subcommands():
    parser = build_parser()
    subparsers = next(
        a for a in parser._actions if a.dest == "command" and hasattr(a, "choices")
    )
    assert set(subparsers.choices) == {"cli", "tui"}


def test_build_parser_registers_all_cli_subcommands():
    parser = build_parser()
    top_level = next(a for a in parser._actions if a.dest == "command")
    cli_parser = top_level.choices["cli"]
    cli_subparsers = next(
        a for a in cli_parser._actions if a.dest == "cli_command" and hasattr(a, "choices")
    )
    assert set(cli_subparsers.choices) == {
        "app", "cert", "doctor", "init", "logs", "restart", "service", "status",
    }
