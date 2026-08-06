from unittest.mock import MagicMock, patch

import pytest

from server_base_cli import paths, stacks


def test_list_apps_returns_sorted_names_with_compose_file(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "STACKS_DIR", tmp_path)
    (tmp_path / "zeta").mkdir()
    (tmp_path / "zeta" / "docker-compose.yml").write_text("services: {}\n")
    (tmp_path / "alpha").mkdir()
    (tmp_path / "alpha" / "docker-compose.yml").write_text("services: {}\n")
    (tmp_path / "no-compose-yet").mkdir()

    assert stacks.list_apps() == ["alpha", "zeta"]


def test_list_apps_returns_empty_list_when_stacks_dir_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "STACKS_DIR", tmp_path / "does-not-exist")

    assert stacks.list_apps() == []


def test_app_exists_true_and_false(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "STACKS_DIR", tmp_path)
    (tmp_path / "myapp").mkdir()
    (tmp_path / "myapp" / "docker-compose.yml").write_text("services: {}\n")

    assert stacks.app_exists("myapp") is True
    assert stacks.app_exists("missing") is False


def test_app_services_parses_stdout_lines():
    with patch("server_base_cli.stacks.shell.capture") as mock_capture:
        mock_capture.return_value = MagicMock(returncode=0, stdout="web\nworker\n", stderr="")
        services = stacks.app_services("myapp")

    assert services == ["web", "worker"]
    mock_capture.assert_called_once_with(
        ["docker", "compose", "-f", str(paths.stack_compose_path("myapp")), "config", "--services"]
    )


def test_app_services_raises_runtime_error_on_failure():
    with patch("server_base_cli.stacks.shell.capture") as mock_capture:
        mock_capture.return_value = MagicMock(returncode=1, stdout="", stderr="boom")
        with pytest.raises(RuntimeError):
            stacks.app_services("myapp")

    mock_capture.assert_called_once_with(
        ["docker", "compose", "-f", str(paths.stack_compose_path("myapp")), "config", "--services"]
    )
