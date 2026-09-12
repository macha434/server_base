import shutil
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
         patch("server_base_cli.commands.app.shell.run_script") as mock_run_script, \
         patch("server_base_cli.commands.app.shell.run") as mock_run, \
         patch("server_base_cli.commands.app.shutil.rmtree") as mock_rmtree:
        parser = build_parser()
        args = parser.parse_args(["app", "remove", "myapp"])
        code = args.func(args)

    mock_run_script.assert_not_called()
    mock_run.assert_not_called()
    mock_rmtree.assert_not_called()
    assert code == 1


def test_app_remove_skips_confirmation_with_yes_flag(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "STACKS_DIR", tmp_path)
    app_dir = tmp_path / "myapp"
    app_dir.mkdir()
    (app_dir / "docker-compose.yml").write_text("services:\n  web: {}\n")

    calls = []
    real_rmtree = shutil.rmtree

    def fake_run_script(name, args=()):
        calls.append(("run_script", name, tuple(args)))
        return 0

    def fake_run(cmd):
        calls.append(("run", tuple(cmd)))
        return 0

    def fake_rmtree(path, *a, **kw):
        calls.append(("rmtree", str(path)))
        real_rmtree(path, *a, **kw)

    with patch("server_base_cli.commands.app.shell.run_script", side_effect=fake_run_script), \
         patch("server_base_cli.commands.app.shell.run", side_effect=fake_run), \
         patch("server_base_cli.commands.app.stacks.app_services", return_value=["web"]), \
         patch("server_base_cli.commands.app.shutil.rmtree", side_effect=fake_rmtree):
        parser = build_parser()
        args = parser.parse_args(["app", "remove", "myapp", "-y"])
        code = args.func(args)

    assert code == 0
    assert not app_dir.exists()
    # render-compose.sh -> docker compose rm -> docker network rm -> rmtree -> up.sh
    # の順で、かつこれ以外の呼び出しが無いことを厳密に確認する
    assert calls == [
        ("run_script", "render-compose.sh", ()),
        (
            "run",
            ("docker", "compose", "-f", str(paths.COMPOSE_GENERATED), "rm", "-f", "-s", "-v", "web"),
        ),
        ("run", ("docker", "network", "rm", "net-myapp")),
        ("rmtree", str(app_dir)),
        ("run_script", "up.sh", ()),
    ]


def test_app_remove_notes_and_continues_when_app_services_is_empty(tmp_path, monkeypatch, capsys):
    """servicesが空(profilesで無効化等)でも、コンテナ削除はスキップしつつ
    ネットワーク削除・rmtree・up.shは続行する。"""
    monkeypatch.setattr(paths, "STACKS_DIR", tmp_path)
    app_dir = tmp_path / "myapp"
    app_dir.mkdir()
    (app_dir / "docker-compose.yml").write_text("services:\n  web: {}\n")

    calls = []
    real_rmtree = shutil.rmtree

    def fake_run_script(name, args=()):
        calls.append(("run_script", name, tuple(args)))
        return 0

    def fake_run(cmd):
        calls.append(("run", tuple(cmd)))
        return 0

    def fake_rmtree(path, *a, **kw):
        calls.append(("rmtree", str(path)))
        real_rmtree(path, *a, **kw)

    with patch("server_base_cli.commands.app.shell.run_script", side_effect=fake_run_script), \
         patch("server_base_cli.commands.app.shell.run", side_effect=fake_run), \
         patch("server_base_cli.commands.app.stacks.app_services", return_value=[]), \
         patch("server_base_cli.commands.app.shutil.rmtree", side_effect=fake_rmtree):
        parser = build_parser()
        args = parser.parse_args(["app", "remove", "myapp", "-y"])
        code = args.func(args)

    assert code == 0
    assert not app_dir.exists()
    # docker compose rm は呼ばれない(services が空のため)が、
    # ネットワーク削除・rmtree・up.sh は続行する
    assert calls == [
        ("run_script", "render-compose.sh", ()),
        ("run", ("docker", "network", "rm", "net-myapp")),
        ("rmtree", str(app_dir)),
        ("run_script", "up.sh", ()),
    ]

    err = capsys.readouterr().err
    assert "net-myapp" in err
    assert "profiles" in err


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


def test_app_remove_returns_1_when_app_services_raises_runtime_error(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "STACKS_DIR", tmp_path)
    app_dir = tmp_path / "myapp"
    app_dir.mkdir()
    (app_dir / "docker-compose.yml").write_text("services:\n  web: {}\n")

    with patch("server_base_cli.commands.app.shell.run_script", return_value=0) as mock_run_script, \
         patch(
             "server_base_cli.commands.app.stacks.app_services",
             side_effect=RuntimeError(
                 "docker compose config --services が失敗しました(myapp): boom"
             ),
         ), \
         patch("server_base_cli.commands.app.shell.run") as mock_run, \
         patch("server_base_cli.commands.app.shutil.rmtree") as mock_rmtree:
        parser = build_parser()
        args = parser.parse_args(["app", "remove", "myapp", "-y"])
        code = args.func(args)

    # RuntimeErrorがトレースバックとして伝播せず、1を返すこと
    assert code == 1
    mock_run.assert_not_called()
    mock_rmtree.assert_not_called()
    assert app_dir.exists()  # app_services失敗時はまだ削除しない
    mock_run_script.assert_called_once_with("render-compose.sh")


def test_app_remove_reports_error_when_rmtree_fails(tmp_path, monkeypatch, capsys):
    """rmtree失敗時: コンテナ/ネットワーク削除は済んでおり、up.sh は実行せず非0を返す(I5)。"""
    monkeypatch.setattr(paths, "STACKS_DIR", tmp_path)
    app_dir = tmp_path / "myapp"
    app_dir.mkdir()
    (app_dir / "docker-compose.yml").write_text("services:\n  web: {}\n")

    calls = []

    def fake_run_script(name, args=()):
        calls.append(("run_script", name))
        return 0

    def fake_run(cmd):
        calls.append(("run", tuple(cmd)))
        return 0

    with patch("server_base_cli.commands.app.shell.run_script", side_effect=fake_run_script), \
         patch("server_base_cli.commands.app.shell.run", side_effect=fake_run), \
         patch("server_base_cli.commands.app.stacks.app_services", return_value=["web"]), \
         patch(
             "server_base_cli.commands.app.shutil.rmtree",
             side_effect=PermissionError(13, "Permission denied"),
         ) as mock_rmtree:
        parser = build_parser()
        args = parser.parse_args(["app", "remove", "myapp", "-y"])
        code = args.func(args)

    assert code != 0
    mock_rmtree.assert_called_once_with(paths.stack_dir("myapp"))
    # コンテナ削除とネットワーク削除は rmtree より前に既に実行済み
    assert calls == [
        ("run_script", "render-compose.sh"),
        (
            "run",
            ("docker", "compose", "-f", str(paths.COMPOSE_GENERATED), "rm", "-f", "-s", "-v", "web"),
        ),
        ("run", ("docker", "network", "rm", "net-myapp")),
    ]
    # 削除が中途半端なので up.sh は呼ばない
    assert ("run_script", "up.sh") not in calls

    err = capsys.readouterr().err
    assert "Permission denied" in err
    assert "stacks/myapp/" in err
    assert "up.sh" in err

