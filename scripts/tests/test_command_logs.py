from unittest.mock import patch

from server_base_cli import paths
from server_base_cli.main import build_parser


def test_logs_without_app_targets_core_services():
    with patch("server_base_cli.commands.logs.shell.run") as mock_run:
        mock_run.return_value = 0
        parser = build_parser()
        args = parser.parse_args(["logs"])
        code = args.func(args)

    mock_run.assert_called_once_with(
        ["docker", "compose", "-f", str(paths.COMPOSE_GENERATED), "logs", "-f", "nginx", "dnsmasq"]
    )
    assert code == 0


def test_logs_with_app_targets_that_apps_services():
    with patch("server_base_cli.commands.logs.stacks.app_exists", return_value=True), \
         patch("server_base_cli.commands.logs.stacks.app_services", return_value=["web"]), \
         patch("server_base_cli.commands.logs.shell.run") as mock_run:
        mock_run.return_value = 0
        parser = build_parser()
        args = parser.parse_args(["logs", "myapp"])
        code = args.func(args)

    mock_run.assert_called_once_with(
        ["docker", "compose", "-f", str(paths.COMPOSE_GENERATED), "logs", "-f", "web"]
    )
    assert code == 0


def test_logs_with_unknown_app_fails_fast():
    with patch("server_base_cli.commands.logs.stacks.app_exists", return_value=False), \
         patch("server_base_cli.commands.logs.shell.run") as mock_run:
        parser = build_parser()
        args = parser.parse_args(["logs", "missing-app"])
        code = args.func(args)

    mock_run.assert_not_called()
    assert code == 1


def test_logs_returns_1_when_app_services_raises_runtime_error(capsys):
    with patch("server_base_cli.commands.logs.stacks.app_exists", return_value=True), \
         patch(
             "server_base_cli.commands.logs.stacks.app_services",
             side_effect=RuntimeError("docker compose config が失敗しました(myapp): boom"),
         ), \
         patch("server_base_cli.commands.logs.shell.run") as mock_run:
        parser = build_parser()
        args = parser.parse_args(["logs", "myapp"])
        code = args.func(args)

    assert code == 1
    mock_run.assert_not_called()
    assert "boom" in capsys.readouterr().err

