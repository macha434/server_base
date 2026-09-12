from unittest.mock import MagicMock, patch

from server_base_cli import paths, shell


def test_run_script_builds_correct_command_and_returns_exit_code():
    with patch("server_base_cli.shell.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        code = shell.run_script("up.sh", ["--profile", "time"])

    called_cmd = mock_run.call_args.args[0]
    assert called_cmd == [str(paths.script_path("up.sh")), "--profile", "time"]
    assert code == 0


def test_run_script_defaults_to_no_extra_args():
    with patch("server_base_cli.shell.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        shell.run_script("install-service.sh")

    called_cmd = mock_run.call_args.args[0]
    assert called_cmd == [str(paths.script_path("install-service.sh"))]


def test_run_streams_output_and_returns_exit_code():
    with patch("server_base_cli.shell.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=3)
        code = shell.run(["docker", "compose", "ps"])

    called_cmd = mock_run.call_args.args[0]
    assert called_cmd == ["docker", "compose", "ps"]
    assert mock_run.call_args.kwargs.get("capture_output") in (None, False)
    assert code == 3


def test_capture_sets_capture_output_and_text_and_does_not_raise():
    with patch("server_base_cli.shell.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stdout="web\n", stderr="boom")
        result = shell.capture(["docker", "compose", "config", "--services"])

    assert mock_run.call_args.kwargs["capture_output"] is True
    assert mock_run.call_args.kwargs["text"] is True
    assert result.returncode == 1
    assert result.stdout == "web\n"
