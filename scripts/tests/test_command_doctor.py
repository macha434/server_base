import socket
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from server_base_cli import paths
from server_base_cli.commands import doctor
from server_base_cli.main import build_parser


def test_port_in_use_detects_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("0.0.0.0", 0))
        free_port = probe.getsockname()[1]

    assert doctor._port_in_use(free_port, "tcp") is False


def test_port_in_use_detects_busy_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as holder:
        holder.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        holder.bind(("0.0.0.0", 0))
        holder.listen(1)
        busy_port = holder.getsockname()[1]

        assert doctor._port_in_use(busy_port, "tcp") is True


def test_check_docker_ok_when_docker_info_succeeds():
    with patch("server_base_cli.commands.doctor.shell.capture") as mock_capture:
        mock_capture.return_value = MagicMock(returncode=0)
        status, _ = doctor._check_docker()

    assert status == "ok"


def test_check_docker_fail_when_docker_info_fails():
    with patch("server_base_cli.commands.doctor.shell.capture") as mock_capture:
        mock_capture.return_value = MagicMock(returncode=1)
        status, _ = doctor._check_docker()

    assert status == "fail"


def test_check_dns_ok_when_resolves():
    with patch("server_base_cli.commands.doctor.shell.capture") as mock_capture:
        mock_capture.return_value = MagicMock(returncode=0, stdout="192.168.1.10\n")
        status, _ = doctor._check_dns()

    assert status == "ok"


def test_check_dns_fail_when_not_resolved():
    with patch("server_base_cli.commands.doctor.shell.capture") as mock_capture:
        mock_capture.return_value = MagicMock(returncode=0, stdout="")
        status, _ = doctor._check_dns()

    assert status == "fail"


def test_check_cert_fail_when_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "SSL_DIR", tmp_path)
    status, _ = doctor._check_cert()
    assert status == "fail"


def test_check_cert_ok_when_far_from_expiry(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "SSL_DIR", tmp_path)
    (tmp_path / "ubuntu.local-cert.pem").write_text("dummy")
    future = (datetime.utcnow() + timedelta(days=100)).strftime("%b %d %H:%M:%S %Y GMT")
    with patch("server_base_cli.commands.doctor.shell.capture") as mock_capture:
        mock_capture.return_value = MagicMock(returncode=0, stdout=f"notAfter={future}\n")
        status, _ = doctor._check_cert()

    assert status == "ok"


def test_check_cert_warn_when_expiring_soon(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "SSL_DIR", tmp_path)
    (tmp_path / "ubuntu.local-cert.pem").write_text("dummy")
    soon = (datetime.utcnow() + timedelta(days=10)).strftime("%b %d %H:%M:%S %Y GMT")
    with patch("server_base_cli.commands.doctor.shell.capture") as mock_capture:
        mock_capture.return_value = MagicMock(returncode=0, stdout=f"notAfter={soon}\n")
        status, _ = doctor._check_cert()

    assert status == "warn"


def test_check_nginx_config_skips_when_not_running():
    with patch("server_base_cli.commands.doctor.shell.capture") as mock_capture:
        mock_capture.return_value = MagicMock(stdout="")
        status, _ = doctor._check_nginx_config()

    assert status == "warn"


def test_check_nginx_config_ok_when_running_and_valid():
    responses = [MagicMock(stdout="running\n"), MagicMock(returncode=0, stderr="")]
    with patch("server_base_cli.commands.doctor.shell.capture", side_effect=responses):
        status, _ = doctor._check_nginx_config()

    assert status == "ok"


def test_check_nginx_config_fail_when_running_but_invalid():
    responses = [MagicMock(stdout="running\n"), MagicMock(returncode=1, stderr="nginx: [emerg] boom")]
    with patch("server_base_cli.commands.doctor.shell.capture", side_effect=responses):
        status, _ = doctor._check_nginx_config()

    assert status == "fail"


def test_check_systemd_service_ok_when_enabled():
    with patch("server_base_cli.commands.doctor.shell.capture") as mock_capture:
        mock_capture.return_value = MagicMock(returncode=0, stdout="enabled\n")
        status, _ = doctor._check_systemd_service()

    assert status == "ok"


def test_check_systemd_service_warn_when_not_registered():
    with patch("server_base_cli.commands.doctor.shell.capture") as mock_capture:
        mock_capture.return_value = MagicMock(returncode=1, stdout="")
        status, _ = doctor._check_systemd_service()

    assert status == "warn"


def test_doctor_command_returns_zero_when_no_failures():
    fake_checks = [("A", lambda: ("ok", "fine")), ("B", lambda: ("warn", "meh"))]
    with patch("server_base_cli.commands.doctor._CHECKS", fake_checks):
        parser = build_parser()
        args = parser.parse_args(["doctor"])
        code = args.func(args)

    assert code == 0


def test_doctor_command_returns_one_when_any_failure():
    fake_checks = [("A", lambda: ("ok", "fine")), ("B", lambda: ("fail", "broken"))]
    with patch("server_base_cli.commands.doctor._CHECKS", fake_checks):
        parser = build_parser()
        args = parser.parse_args(["doctor"])
        code = args.func(args)

    assert code == 1
