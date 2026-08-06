from unittest.mock import patch

from server_base_cli.main import build_parser


def test_cert_renew_defaults_to_ubuntu_local():
    with patch("server_base_cli.commands.cert.shell.run_script") as mock_run:
        mock_run.return_value = 0
        parser = build_parser()
        args = parser.parse_args(["cert", "renew"])
        code = args.func(args)

    mock_run.assert_called_once_with("generate-cert.sh", ["ubuntu.local"])
    assert code == 0


def test_cert_renew_accepts_custom_domain():
    with patch("server_base_cli.commands.cert.shell.run_script") as mock_run:
        mock_run.return_value = 0
        parser = build_parser()
        args = parser.parse_args(["cert", "renew", "example.local"])
        code = args.func(args)

    mock_run.assert_called_once_with("generate-cert.sh", ["example.local"])
    assert code == 0
