from unittest.mock import patch

from server_base_cli.main import build_parser


def test_app_add_passes_through_args_without_service_name():
    with patch("server_base_cli.commands.app.shell.run_script") as mock_run:
        mock_run.return_value = 0
        parser = build_parser()
        args = parser.parse_args(
            ["app", "add", "time-announcement", "../time-announcement-frontend", "deploy/docker-compose.yaml", "time", "3000"]
        )
        code = args.func(args)

    mock_run.assert_called_once_with(
        "new-app.sh",
        ["time-announcement", "../time-announcement-frontend", "deploy/docker-compose.yaml", "time", "3000"],
    )
    assert code == 0


def test_app_add_inserts_service_name_when_given():
    with patch("server_base_cli.commands.app.shell.run_script") as mock_run:
        mock_run.return_value = 0
        parser = build_parser()
        args = parser.parse_args(
            [
                "app", "add", "myapp", "../myapp", "deploy/docker-compose.yaml",
                "--service", "web", "myapp", "3000",
            ]
        )
        code = args.func(args)

    mock_run.assert_called_once_with(
        "new-app.sh",
        ["myapp", "../myapp", "deploy/docker-compose.yaml", "web", "myapp", "3000"],
    )
    assert code == 0


def test_app_add_propagates_failure_exit_code():
    with patch("server_base_cli.commands.app.shell.run_script") as mock_run:
        mock_run.return_value = 1
        parser = build_parser()
        args = parser.parse_args(
            ["app", "add", "myapp", "../myapp", "deploy/docker-compose.yaml", "myapp", "3000"]
        )
        code = args.func(args)

    assert code == 1
