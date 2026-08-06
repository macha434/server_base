import socket
from datetime import datetime, timedelta
from unittest.mock import MagicMock, call, patch

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


def test_port_in_use_returns_none_on_permission_error(monkeypatch):
    def fake_bind(self, addr):
        raise PermissionError("Permission denied")

    monkeypatch.setattr(socket.socket, "bind", fake_bind)

    assert doctor._port_in_use(80, "tcp") is None


def test_check_docker_ok_when_docker_info_succeeds():
    with patch("server_base_cli.commands.doctor.shell.capture") as mock_capture:
        mock_capture.return_value = MagicMock(returncode=0)
        status, _ = doctor._check_docker()

    mock_capture.assert_called_once_with(["docker", "info"])
    assert status == "ok"


def test_check_docker_fail_when_docker_info_fails():
    with patch("server_base_cli.commands.doctor.shell.capture") as mock_capture:
        mock_capture.return_value = MagicMock(returncode=1)
        status, _ = doctor._check_docker()

    mock_capture.assert_called_once_with(["docker", "info"])
    assert status == "fail"


def test_check_docker_fail_when_docker_binary_missing():
    with patch(
        "server_base_cli.commands.doctor.shell.capture",
        side_effect=FileNotFoundError("[Errno 2] No such file or directory: 'docker'"),
    ):
        status, message = doctor._check_docker()

    assert status == "fail"
    assert "docker" in message.lower()


def test_check_ports_ok_when_all_free(monkeypatch):
    monkeypatch.setattr(doctor, "_port_in_use", lambda port, kind: False)

    status, _ = doctor._check_ports()

    assert status == "ok"


def test_check_ports_warn_when_busy(monkeypatch):
    monkeypatch.setattr(doctor, "_port_in_use", lambda port, kind: True)

    status, message = doctor._check_ports()

    assert status == "warn"
    assert "使用中" in message


def test_check_ports_warn_when_permission_denied(monkeypatch):
    monkeypatch.setattr(doctor, "_port_in_use", lambda port, kind: None)

    status, message = doctor._check_ports()

    assert status == "warn"
    assert "権限不足" in message


def test_check_ports_fail_when_port_check_raises(monkeypatch):
    def raise_error(port, kind):
        raise OSError("boom")

    monkeypatch.setattr(doctor, "_port_in_use", raise_error)

    status, _ = doctor._check_ports()

    assert status == "fail"


def test_check_dns_ok_when_resolves():
    with patch("server_base_cli.commands.doctor.shell.capture") as mock_capture:
        mock_capture.return_value = MagicMock(returncode=0, stdout="192.168.1.10\n")
        status, _ = doctor._check_dns()

    mock_capture.assert_called_once_with(["dig", "@127.0.0.1", "ubuntu.local", "+short"])
    assert status == "ok"


def test_check_dns_fail_when_not_resolved():
    with patch("server_base_cli.commands.doctor.shell.capture") as mock_capture:
        mock_capture.return_value = MagicMock(returncode=0, stdout="")
        status, _ = doctor._check_dns()

    mock_capture.assert_called_once_with(["dig", "@127.0.0.1", "ubuntu.local", "+short"])
    assert status == "fail"


def test_check_dns_fail_when_dig_binary_missing():
    with patch(
        "server_base_cli.commands.doctor.shell.capture",
        side_effect=FileNotFoundError("[Errno 2] No such file or directory: 'dig'"),
    ):
        status, message = doctor._check_dns()

    assert status == "fail"
    assert "dig" in message.lower()


def test_check_cert_fail_when_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "SSL_DIR", tmp_path)
    status, _ = doctor._check_cert()
    assert status == "fail"


def test_check_cert_ok_when_far_from_expiry(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "SSL_DIR", tmp_path)
    cert_path = tmp_path / "ubuntu.local-cert.pem"
    cert_path.write_text("dummy")
    future = (datetime.utcnow() + timedelta(days=100)).strftime("%b %d %H:%M:%S %Y GMT")
    with patch("server_base_cli.commands.doctor.shell.capture") as mock_capture:
        mock_capture.return_value = MagicMock(returncode=0, stdout=f"notAfter={future}\n")
        status, _ = doctor._check_cert()

    mock_capture.assert_called_once_with(
        ["openssl", "x509", "-enddate", "-noout", "-in", str(cert_path)]
    )
    assert status == "ok"


def test_check_cert_warn_when_expiring_soon(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "SSL_DIR", tmp_path)
    cert_path = tmp_path / "ubuntu.local-cert.pem"
    cert_path.write_text("dummy")
    soon = (datetime.utcnow() + timedelta(days=10)).strftime("%b %d %H:%M:%S %Y GMT")
    with patch("server_base_cli.commands.doctor.shell.capture") as mock_capture:
        mock_capture.return_value = MagicMock(returncode=0, stdout=f"notAfter={soon}\n")
        status, _ = doctor._check_cert()

    mock_capture.assert_called_once_with(
        ["openssl", "x509", "-enddate", "-noout", "-in", str(cert_path)]
    )
    assert status == "warn"


def test_check_cert_fail_when_notafter_unparseable(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "SSL_DIR", tmp_path)
    (tmp_path / "ubuntu.local-cert.pem").write_text("dummy")
    with patch("server_base_cli.commands.doctor.shell.capture") as mock_capture:
        mock_capture.return_value = MagicMock(returncode=0, stdout="notAfter=not-a-real-date\n")
        status, message = doctor._check_cert()

    assert status == "fail"
    assert "解析" in message


def test_check_cert_fail_when_openssl_binary_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "SSL_DIR", tmp_path)
    (tmp_path / "ubuntu.local-cert.pem").write_text("dummy")
    with patch(
        "server_base_cli.commands.doctor.shell.capture",
        side_effect=FileNotFoundError("[Errno 2] No such file or directory: 'openssl'"),
    ):
        status, message = doctor._check_cert()

    assert status == "fail"
    assert "openssl" in message.lower()


def test_check_nginx_config_skips_when_not_running():
    with patch("server_base_cli.commands.doctor.shell.capture") as mock_capture:
        mock_capture.return_value = MagicMock(stdout="")
        status, _ = doctor._check_nginx_config()

    mock_capture.assert_called_once_with(
        ["docker", "compose", "-f", str(paths.COMPOSE_GENERATED), "ps", "--format", "{{.State}}", "nginx"]
    )
    assert status == "warn"


def test_check_nginx_config_ok_when_running_and_valid():
    responses = [MagicMock(stdout="running\n"), MagicMock(returncode=0, stderr="")]
    with patch("server_base_cli.commands.doctor.shell.capture", side_effect=responses) as mock_capture:
        status, _ = doctor._check_nginx_config()

    assert mock_capture.call_args_list == [
        call(["docker", "compose", "-f", str(paths.COMPOSE_GENERATED), "ps", "--format", "{{.State}}", "nginx"]),
        call(["docker", "compose", "-f", str(paths.COMPOSE_GENERATED), "exec", "-T", "nginx", "nginx", "-t"]),
    ]
    assert status == "ok"


def test_check_nginx_config_fail_when_running_but_invalid():
    responses = [MagicMock(stdout="running\n"), MagicMock(returncode=1, stderr="nginx: [emerg] boom")]
    with patch("server_base_cli.commands.doctor.shell.capture", side_effect=responses) as mock_capture:
        status, _ = doctor._check_nginx_config()

    assert mock_capture.call_args_list == [
        call(["docker", "compose", "-f", str(paths.COMPOSE_GENERATED), "ps", "--format", "{{.State}}", "nginx"]),
        call(["docker", "compose", "-f", str(paths.COMPOSE_GENERATED), "exec", "-T", "nginx", "nginx", "-t"]),
    ]
    assert status == "fail"


def test_check_nginx_config_fail_when_docker_binary_missing():
    with patch(
        "server_base_cli.commands.doctor.shell.capture",
        side_effect=FileNotFoundError("[Errno 2] No such file or directory: 'docker'"),
    ):
        status, message = doctor._check_nginx_config()

    assert status == "fail"
    assert "docker" in message.lower()


def test_check_systemd_service_ok_when_enabled():
    with patch("server_base_cli.commands.doctor.shell.capture") as mock_capture:
        mock_capture.return_value = MagicMock(returncode=0, stdout="enabled\n")
        status, _ = doctor._check_systemd_service()

    mock_capture.assert_called_once_with(["systemctl", "--user", "is-enabled", "core-stack.service"])
    assert status == "ok"


def test_check_systemd_service_warn_when_not_registered():
    with patch("server_base_cli.commands.doctor.shell.capture") as mock_capture:
        mock_capture.return_value = MagicMock(returncode=1, stdout="")
        status, _ = doctor._check_systemd_service()

    mock_capture.assert_called_once_with(["systemctl", "--user", "is-enabled", "core-stack.service"])
    assert status == "warn"


def test_check_systemd_service_fail_when_systemctl_binary_missing():
    with patch(
        "server_base_cli.commands.doctor.shell.capture",
        side_effect=FileNotFoundError("[Errno 2] No such file or directory: 'systemctl'"),
    ):
        status, message = doctor._check_systemd_service()

    assert status == "fail"
    assert "systemctl" in message.lower()


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
