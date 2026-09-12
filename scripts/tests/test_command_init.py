from unittest.mock import patch

from server_base_cli.main import build_parser


def test_init_runs_setup_dns_then_cert_then_up_in_order():
    calls = []

    def fake_run_script(name, args=()):
        calls.append((name, tuple(args)))
        return 0

    with patch("server_base_cli.commands.init.shell.run_script", side_effect=fake_run_script):
        parser = build_parser()
        args = parser.parse_args(["cli", "init"])
        code = args.func(args)

    assert calls == [
        ("setup-dns.sh", ()),
        ("generate-cert.sh", ("ubuntu.local",)),
        ("up.sh", ()),
    ]
    assert code == 0


def test_init_stops_after_first_failure():
    calls = []

    def fake_run_script(name, args=()):
        calls.append(name)
        return 0 if name != "generate-cert.sh" else 1

    with patch("server_base_cli.commands.init.shell.run_script", side_effect=fake_run_script):
        parser = build_parser()
        args = parser.parse_args(["cli", "init"])
        code = args.func(args)

    assert calls == ["setup-dns.sh", "generate-cert.sh"]
    assert code == 1
