from unittest.mock import patch

from server_base_cli import paths
from server_base_cli.main import build_parser


def test_restart_without_app_runs_down_then_up():
    calls = []

    def fake_run_script(name, args=()):
        calls.append(name)
        return 0

    with patch("server_base_cli.commands.restart.shell.run_script", side_effect=fake_run_script):
        parser = build_parser()
        args = parser.parse_args(["restart"])
        code = args.func(args)

    assert calls == ["down.sh", "up.sh"]
    assert code == 0


def test_restart_without_app_stops_if_down_fails():
    with patch("server_base_cli.commands.restart.shell.run_script", return_value=1) as mock_run_script:
        parser = build_parser()
        args = parser.parse_args(["restart"])
        code = args.func(args)

    mock_run_script.assert_called_once_with("down.sh")
    assert code == 1


def test_restart_with_app_restarts_only_that_apps_services():
    with patch("server_base_cli.commands.restart.stacks.app_exists", return_value=True), \
         patch("server_base_cli.commands.restart.stacks.app_services", return_value=["web"]), \
         patch("server_base_cli.commands.restart.shell.run") as mock_run:
        mock_run.return_value = 0
        parser = build_parser()
        args = parser.parse_args(["restart", "myapp"])
        code = args.func(args)

    mock_run.assert_called_once_with(
        ["docker", "compose", "-f", str(paths.COMPOSE_GENERATED), "restart", "web"]
    )
    assert code == 0


def test_restart_with_unknown_app_fails_fast():
    with patch("server_base_cli.commands.restart.stacks.app_exists", return_value=False), \
         patch("server_base_cli.commands.restart.shell.run") as mock_run:
        parser = build_parser()
        args = parser.parse_args(["restart", "missing-app"])
        code = args.func(args)

    mock_run.assert_not_called()
    assert code == 1


def test_restart_returns_1_when_app_services_is_empty(capsys):
    with patch("server_base_cli.commands.restart.stacks.app_exists", return_value=True), \
         patch("server_base_cli.commands.restart.stacks.app_services", return_value=[]), \
         patch("server_base_cli.commands.restart.shell.run") as mock_run:
        parser = build_parser()
        args = parser.parse_args(["restart", "myapp"])
        code = args.func(args)

    assert code == 1
    mock_run.assert_not_called()
    err = capsys.readouterr().err
    assert "net-myapp" in err
    assert "profiles" in err


def test_restart_returns_1_when_app_services_raises_runtime_error(capsys):
    with patch("server_base_cli.commands.restart.stacks.app_exists", return_value=True), \
         patch(
             "server_base_cli.commands.restart.stacks.app_services",
             side_effect=RuntimeError("docker compose config が失敗しました(myapp): boom"),
         ), \
         patch("server_base_cli.commands.restart.shell.run") as mock_run:
        parser = build_parser()
        args = parser.parse_args(["restart", "myapp"])
        code = args.func(args)

    assert code == 1
    mock_run.assert_not_called()
    assert "boom" in capsys.readouterr().err

