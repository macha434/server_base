from unittest.mock import patch

import pytest

from server_base_cli.main import build_parser, main


def test_main_dispatches_to_subcommand_and_returns_its_exit_code():
    with patch("server_base_cli.commands.status._status", return_value=3) as mock_status:
        assert main(["status"]) == 3

    mock_status.assert_called_once()


def test_main_returns_130_on_keyboard_interrupt():
    """Ctrl-C(`server-base logs -f` 等)で生のトレースバックを出さず130を返す(I2)。"""
    with patch("server_base_cli.commands.status._status", side_effect=KeyboardInterrupt):
        assert main(["status"]) == 130


def test_main_does_not_swallow_other_exceptions():
    """KeyboardInterrupt以外は握り潰さない(バグを隠さないため)。"""
    with patch("server_base_cli.commands.status._status", side_effect=ValueError("boom")):
        with pytest.raises(ValueError):
            main(["status"])


def test_main_requires_a_subcommand():
    with pytest.raises(SystemExit):
        main([])


def test_build_parser_registers_all_subcommands():
    parser = build_parser()
    subparsers = next(
        a for a in parser._actions if a.dest == "command" and hasattr(a, "choices")
    )
    assert set(subparsers.choices) == {
        "app", "cert", "doctor", "init", "logs", "restart", "service", "status",
    }
