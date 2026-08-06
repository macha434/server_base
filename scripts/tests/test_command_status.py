from unittest.mock import MagicMock, patch

from server_base_cli.commands import status
from server_base_cli.main import build_parser


def test_container_state_returns_state_string():
    with patch("server_base_cli.commands.status.shell.capture") as mock_capture:
        mock_capture.return_value = MagicMock(stdout="running\n")
        assert status._container_state("nginx") == "running"


def test_container_state_returns_stopped_when_output_empty():
    with patch("server_base_cli.commands.status.shell.capture") as mock_capture:
        mock_capture.return_value = MagicMock(stdout="")
        assert status._container_state("nginx") == "stopped"


def test_url_reachable_true_for_2xx_response():
    with patch("server_base_cli.commands.status.shell.capture") as mock_capture:
        mock_capture.return_value = MagicMock(returncode=0, stdout="200")
        assert status._url_reachable("https://x.ubuntu.local/") is True


def test_url_reachable_false_when_curl_fails():
    with patch("server_base_cli.commands.status.shell.capture") as mock_capture:
        mock_capture.return_value = MagicMock(returncode=7, stdout="")
        assert status._url_reachable("https://x.ubuntu.local/") is False


def test_systemd_enabled_true_when_is_enabled_succeeds():
    with patch("server_base_cli.commands.status.shell.capture") as mock_capture:
        mock_capture.return_value = MagicMock(returncode=0)
        assert status._systemd_enabled() is True


def test_status_command_prints_core_and_each_app(capsys):
    with patch("server_base_cli.commands.status.stacks.list_apps", return_value=["myapp"]), \
         patch("server_base_cli.commands.status.stacks.app_services", return_value=["myapp"]), \
         patch("server_base_cli.commands.status._container_state", return_value="running"), \
         patch("server_base_cli.commands.status._url_reachable", return_value=True), \
         patch("server_base_cli.commands.status._systemd_enabled", return_value=True):
        parser = build_parser()
        args = parser.parse_args(["status"])
        code = args.func(args)

    out = capsys.readouterr().out
    assert code == 0
    assert "nginx" in out
    assert "dnsmasq" in out
    assert "myapp" in out
    assert "https://myapp.ubuntu.local/" in out
    assert "到達可" in out
