from unittest.mock import patch

from server_base_cli.main import build_parser


def test_service_add_invokes_install_service_sh():
    with patch("server_base_cli.commands.service.shell.run_script") as mock_run:
        mock_run.return_value = 0
        parser = build_parser()
        args = parser.parse_args(["service", "add"])
        code = args.func(args)

    mock_run.assert_called_once_with("install-service.sh")
    assert code == 0


def test_service_remove_invokes_uninstall_service_sh():
    with patch("server_base_cli.commands.service.shell.run_script") as mock_run:
        mock_run.return_value = 0
        parser = build_parser()
        args = parser.parse_args(["service", "remove"])
        code = args.func(args)

    mock_run.assert_called_once_with("uninstall-service.sh")
    assert code == 0


def test_service_add_propagates_nonzero_exit_code():
    with patch("server_base_cli.commands.service.shell.run_script") as mock_run:
        mock_run.return_value = 1
        parser = build_parser()
        args = parser.parse_args(["service", "add"])
        code = args.func(args)

    assert code == 1


def test_top_level_help_does_not_raise():
    parser = build_parser()
    with_help = parser.format_help()
    assert "service" in with_help
