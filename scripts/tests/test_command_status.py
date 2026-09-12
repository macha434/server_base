from unittest.mock import MagicMock, patch

from server_base_cli import paths
from server_base_cli.commands import status
from server_base_cli.main import build_parser


def test_container_state_returns_state_string():
    with patch("server_base_cli.commands.status.shell.capture") as mock_capture:
        mock_capture.return_value = MagicMock(returncode=0, stdout="running\n")
        assert status._container_state("nginx") == "running"

    mock_capture.assert_called_once_with(
        ["docker", "compose", "-f", str(paths.COMPOSE_GENERATED), "ps", "--format", "{{.State}}", "nginx"]
    )


def test_container_state_returns_stopped_when_output_empty():
    with patch("server_base_cli.commands.status.shell.capture") as mock_capture:
        mock_capture.return_value = MagicMock(returncode=0, stdout="")
        assert status._container_state("nginx") == "stopped"

    mock_capture.assert_called_once_with(
        ["docker", "compose", "-f", str(paths.COMPOSE_GENERATED), "ps", "--format", "{{.State}}", "nginx"]
    )


def test_container_state_returns_unable_when_docker_missing():
    with patch(
        "server_base_cli.commands.status.shell.capture",
        side_effect=FileNotFoundError("No such file or directory: 'docker'"),
    ):
        assert status._container_state("nginx") == "確認不可"


def test_container_state_returns_unable_when_docker_command_fails():
    """dockerデーモンに到達できない場合、stoppedではなく確認不可を返す(I3)。"""
    with patch("server_base_cli.commands.status.shell.capture") as mock_capture:
        mock_capture.return_value = MagicMock(returncode=1, stdout="", stderr="Cannot connect to the Docker daemon")
        assert status._container_state("nginx") == "確認不可"


def test_url_reachable_true_for_2xx_response():
    with patch("server_base_cli.commands.status.shell.capture") as mock_capture:
        mock_capture.return_value = MagicMock(returncode=0, stdout="200")
        assert status._url_reachable("https://x.ubuntu.local/") is True

    mock_capture.assert_called_once_with(["curl", "-k", "-s", "-o", "/dev/null", "-w", "%{http_code}", "https://x.ubuntu.local/"])


def test_url_reachable_false_when_curl_fails():
    with patch("server_base_cli.commands.status.shell.capture") as mock_capture:
        mock_capture.return_value = MagicMock(returncode=7, stdout="")
        assert status._url_reachable("https://x.ubuntu.local/") is False

    mock_capture.assert_called_once_with(["curl", "-k", "-s", "-o", "/dev/null", "-w", "%{http_code}", "https://x.ubuntu.local/"])


def test_url_reachable_false_when_curl_missing():
    with patch(
        "server_base_cli.commands.status.shell.capture",
        side_effect=FileNotFoundError("No such file or directory: 'curl'"),
    ):
        assert status._url_reachable("https://x.ubuntu.local/") is False


def test_systemd_enabled_true_when_is_enabled_succeeds():
    with patch("server_base_cli.commands.status.shell.capture") as mock_capture:
        mock_capture.return_value = MagicMock(returncode=0)
        assert status._systemd_enabled() is True

    mock_capture.assert_called_once_with(["systemctl", "--user", "is-enabled", "core-stack.service"])


def test_systemd_enabled_false_when_systemctl_missing():
    with patch(
        "server_base_cli.commands.status.shell.capture",
        side_effect=FileNotFoundError("No such file or directory: 'systemctl'"),
    ):
        assert status._systemd_enabled() is False


def test_status_command_prints_core_and_each_app(capsys):
    with patch("server_base_cli.commands.status.stacks.list_apps", return_value=["myapp"]), \
         patch("server_base_cli.commands.status.stacks.app_services", return_value=["myapp"]), \
         patch("server_base_cli.commands.status._container_state", return_value="running"), \
         patch("server_base_cli.commands.status._url_reachable", return_value=True), \
         patch("server_base_cli.commands.status._systemd_enabled", return_value=True), \
         patch("server_base_cli.commands.status.stacks.app_site_host", return_value="example.ubuntu.local"):
        parser = build_parser()
        args = parser.parse_args(["cli", "status"])
        code = args.func(args)

    out = capsys.readouterr().out
    assert code == 0
    assert "nginx" in out
    assert "dnsmasq" in out
    assert "myapp" in out
    assert "https://example.ubuntu.local/" in out
    assert "到達可" in out


def test_status_handles_missing_site_host_label(capsys):
    with patch("server_base_cli.commands.status.stacks.list_apps", return_value=["brokenapp"]), \
         patch("server_base_cli.commands.status.stacks.app_services", return_value=["svc"]), \
         patch("server_base_cli.commands.status._container_state", return_value="running"), \
         patch("server_base_cli.commands.status._systemd_enabled", return_value=True), \
         patch("server_base_cli.commands.status.stacks.app_site_host", return_value=None):
        parser = build_parser()
        args = parser.parse_args(["cli", "status"])
        code = args.func(args)

    out = capsys.readouterr().out
    assert code == 0
    assert "brokenapp" in out
    assert "site.hostラベルが見つかりません" in out


def test_status_handles_broken_app_services(capsys):
    with patch("server_base_cli.commands.status.stacks.list_apps", return_value=["brokenapp"]), \
         patch(
             "server_base_cli.commands.status.stacks.app_services",
             side_effect=RuntimeError("docker compose config failed")
         ), \
         patch("server_base_cli.commands.status._systemd_enabled", return_value=True):
        parser = build_parser()
        args = parser.parse_args(["cli", "status"])
        code = args.func(args)

    out = capsys.readouterr().out
    assert code == 0
    assert "brokenapp" in out
    assert "サービス情報が確認できません" in out


def test_status_handles_broken_app_site_host(capsys):
    """app_site_host が RuntimeError を投げても行が半端に出力されず、次のアプリへ進む。"""
    with patch("server_base_cli.commands.status.stacks.list_apps", return_value=["brokenapp"]), \
         patch("server_base_cli.commands.status.stacks.app_services", return_value=["svc"]), \
         patch(
             "server_base_cli.commands.status.stacks.app_site_host",
             side_effect=RuntimeError("docker compose config failed"),
         ), \
         patch("server_base_cli.commands.status._container_state", return_value="running"), \
         patch("server_base_cli.commands.status._systemd_enabled", return_value=True):
        parser = build_parser()
        args = parser.parse_args(["cli", "status"])
        code = args.func(args)

    out = capsys.readouterr().out
    assert code == 0
    assert "brokenapp: (サービス情報が確認できません)" in out
    # 半端な行(サービス状態だけ出てURLが出ない行)が出ていないこと
    assert "svc=running" not in out


def test_status_no_longer_defines_local_site_host():
    """_site_host は stacks.app_site_host に移管され、status.py からは削除された。"""
    assert not hasattr(status, "_site_host")
