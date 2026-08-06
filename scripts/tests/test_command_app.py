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


from server_base_cli import paths


def test_app_remove_fails_fast_when_app_not_found():
    with patch("server_base_cli.commands.app.stacks.app_exists", return_value=False):
        parser = build_parser()
        args = parser.parse_args(["app", "remove", "missing-app"])
        code = args.func(args)

    assert code == 1


def test_app_remove_aborts_when_user_declines_confirmation():
    with patch("server_base_cli.commands.app.stacks.app_exists", return_value=True), \
         patch("builtins.input", return_value="n"), \
         patch("server_base_cli.commands.app.shell.run_script") as mock_run_script:
        parser = build_parser()
        args = parser.parse_args(["app", "remove", "myapp"])
        code = args.func(args)

    mock_run_script.assert_not_called()
    assert code == 1


def test_app_remove_skips_confirmation_with_yes_flag(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "STACKS_DIR", tmp_path)
    app_dir = tmp_path / "myapp"
    app_dir.mkdir()
    (app_dir / "docker-compose.yml").write_text("services:\n  web: {}\n")

    calls = []

    def fake_run_script(name, args=()):
        calls.append(("run_script", name, tuple(args)))
        return 0

    def fake_run(cmd):
        calls.append(("run", tuple(cmd)))
        return 0

    with patch("server_base_cli.commands.app.shell.run_script", side_effect=fake_run_script), \
         patch("server_base_cli.commands.app.shell.run", side_effect=fake_run), \
         patch("server_base_cli.commands.app.stacks.app_services", return_value=["web"]):
        parser = build_parser()
        args = parser.parse_args(["app", "remove", "myapp", "-y"])
        code = args.func(args)

    assert code == 0
    assert not app_dir.exists()
    assert ("run_script", "render-compose.sh", ()) in calls
    assert (
        "run",
        ("docker", "compose", "-f", str(paths.COMPOSE_GENERATED), "rm", "-f", "-s", "-v", "web"),
    ) in calls
    assert ("run", ("docker", "network", "rm", "net-myapp")) in calls
    assert ("run_script", "up.sh", ()) in calls
    # render-compose.sh -> rm -> network rm -> up.sh の順で呼ばれること
    run_script_order = [c[1] for c in calls if c[0] == "run_script"]
    assert run_script_order == ["render-compose.sh", "up.sh"]


def test_app_remove_stops_when_render_compose_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "STACKS_DIR", tmp_path)
    app_dir = tmp_path / "myapp"
    app_dir.mkdir()
    (app_dir / "docker-compose.yml").write_text("services:\n  web: {}\n")

    with patch("server_base_cli.commands.app.shell.run_script", return_value=1) as mock_run_script, \
         patch("server_base_cli.commands.app.shell.run") as mock_run:
        parser = build_parser()
        args = parser.parse_args(["app", "remove", "myapp", "-y"])
        code = args.func(args)

    assert code == 1
    mock_run.assert_not_called()
    assert app_dir.exists()  # render-compose.sh失敗時はまだ削除しない
