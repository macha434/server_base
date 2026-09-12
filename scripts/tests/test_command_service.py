from unittest.mock import patch

from server_base_cli.main import build_parser


def test_service_add_invokes_install_service_sh():
    with patch("server_base_cli.commands.service.shell.run_script") as mock_run:
        mock_run.return_value = 0
        parser = build_parser()
        args = parser.parse_args(["cli", "service", "add"])
        code = args.func(args)

    mock_run.assert_called_once_with("install-service.sh")
    assert code == 0


def test_service_remove_invokes_uninstall_service_sh():
    with patch("server_base_cli.commands.service.shell.run_script") as mock_run:
        mock_run.return_value = 0
        parser = build_parser()
        args = parser.parse_args(["cli", "service", "remove"])
        code = args.func(args)

    mock_run.assert_called_once_with("uninstall-service.sh")
    assert code == 0


def test_service_add_propagates_nonzero_exit_code():
    with patch("server_base_cli.commands.service.shell.run_script") as mock_run:
        mock_run.return_value = 1
        parser = build_parser()
        args = parser.parse_args(["cli", "service", "add"])
        code = args.func(args)

    assert code == 1


def test_top_level_help_lists_cli_and_tui():
    parser = build_parser()
    with_help = parser.format_help()
    assert "cli" in with_help
    assert "tui" in with_help


def test_cli_subcommand_help_lists_service():
    parser = build_parser()
    top_level = next(a for a in parser._actions if a.dest == "command")
    cli_parser = top_level.choices["cli"]
    assert "service" in cli_parser.format_help()
