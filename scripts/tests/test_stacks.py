import json
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


# core+全stacksを合成した compose.generated.yaml の `config --format json` 出力を模した
# フィクスチャ。nginx は全アプリのネットワークに参加し、dnsmasq も core サービスなので、
# どちらも myapp の net-myapp に載っていても app_services には現れてはならない。
_GENERATED_CONFIG_JSON = json.dumps(
    {
        "services": {
            "nginx": {
                "image": "nginx:alpine",
                "networks": {"net-myapp": {}, "net-otherapp": {}},
                "labels": {},
            },
            "dnsmasq": {
                "image": "dnsmasq:latest",
                "networks": {"net-myapp": {}, "net-otherapp": {}},
                "labels": {},
            },
            "worker": {
                "networks": {"net-myapp": {}},
                "labels": {},
            },
            "web": {
                "networks": {"net-myapp": {"aliases": ["myapp"]}},
                "labels": {
                    "site.host": "my.ubuntu.local",
                    "site.upstream": "myapp",
                    "site.port": "3000",
                },
            },
            "other-web": {
                "networks": {"net-otherapp": {"aliases": ["otherapp"]}},
                "labels": {"site.host": "other.ubuntu.local"},
            },
        }
    }
)

_RENDER_CMD = [str(paths.script_path("render-compose.sh"))]
_CONFIG_CMD = [
    "docker",
    "compose",
    "-f",
    str(paths.COMPOSE_GENERATED),
    "config",
    "--format",
    "json",
]


def _capture_side_effect(render_rc=0, config_rc=0, config_stdout=_GENERATED_CONFIG_JSON):
    """render-compose.sh -> docker compose config の2回呼び出しを模したside_effectを返す。"""

    def side_effect(cmd, *args, **kwargs):
        if cmd == _RENDER_CMD:
            return MagicMock(returncode=render_rc, stdout="", stderr="render boom")
        if cmd == _CONFIG_CMD:
            return MagicMock(returncode=config_rc, stdout=config_stdout, stderr="config boom")
        raise AssertionError(f"想定外のコマンド呼び出し: {cmd}")

    return side_effect


def test_app_services_returns_services_on_that_apps_network():
    with patch("server_base_cli.stacks.shell.capture") as mock_capture:
        mock_capture.side_effect = _capture_side_effect()
        services = stacks.app_services("myapp")

    assert services == ["web", "worker"]
    # 必ず render-compose.sh -> compose.generated.yaml の config の順で呼ばれること
    assert [c.args[0] for c in mock_capture.call_args_list] == [_RENDER_CMD, _CONFIG_CMD]


def test_app_services_never_returns_core_services():
    """回帰テスト(C2): nginx/dnsmasq は net-<app名> に載っていても返してはならない。

    nginx は全アプリのネットワークに参加してルーティングするため、
    compose.generated.yaml 上では常に net-<app名> のメンバーとして現れる。
    """
    with patch("server_base_cli.stacks.shell.capture") as mock_capture:
        mock_capture.side_effect = _capture_side_effect()
        services = stacks.app_services("myapp")

    assert "nginx" not in services
    assert "dnsmasq" not in services


def test_app_services_excludes_other_apps_services():
    with patch("server_base_cli.stacks.shell.capture") as mock_capture:
        mock_capture.side_effect = _capture_side_effect()
        services = stacks.app_services("otherapp")

    assert services == ["other-web"]


def test_app_services_reads_generated_project_not_isolated_stack_file():
    """回帰テスト(C1): stacks/<app>/docker-compose.yml 単体を読んではならない。"""
    with patch("server_base_cli.stacks.shell.capture") as mock_capture:
        mock_capture.side_effect = _capture_side_effect()
        stacks.app_services("myapp")

    for call in mock_capture.call_args_list:
        assert str(paths.stack_compose_path("myapp")) not in call.args[0]


def test_app_services_raises_runtime_error_when_render_compose_fails():
    with patch("server_base_cli.stacks.shell.capture") as mock_capture:
        mock_capture.side_effect = _capture_side_effect(render_rc=1)
        with pytest.raises(RuntimeError, match="render-compose.sh"):
            stacks.app_services("myapp")

    # render-compose.sh が失敗した時点で docker compose は呼ばない
    assert [c.args[0] for c in mock_capture.call_args_list] == [_RENDER_CMD]


def test_app_services_raises_runtime_error_when_compose_config_fails():
    with patch("server_base_cli.stacks.shell.capture") as mock_capture:
        mock_capture.side_effect = _capture_side_effect(config_rc=1, config_stdout="")
        with pytest.raises(RuntimeError, match="docker compose config"):
            stacks.app_services("myapp")

    assert [c.args[0] for c in mock_capture.call_args_list] == [_RENDER_CMD, _CONFIG_CMD]


def test_app_services_returns_empty_list_for_unknown_app():
    with patch("server_base_cli.stacks.shell.capture") as mock_capture:
        mock_capture.side_effect = _capture_side_effect()
        assert stacks.app_services("nosuchapp") == []


def test_app_site_host_returns_label_value_when_found():
    with patch("server_base_cli.stacks.shell.capture") as mock_capture:
        mock_capture.side_effect = _capture_side_effect()
        assert stacks.app_site_host("myapp") == "my.ubuntu.local"


def test_app_site_host_returns_none_when_label_not_found():
    config = json.dumps(
        {"services": {"web": {"networks": {"net-myapp": {}}, "labels": {}}}}
    )
    with patch("server_base_cli.stacks.shell.capture") as mock_capture:
        mock_capture.side_effect = _capture_side_effect(config_stdout=config)
        assert stacks.app_site_host("myapp") is None


def test_app_site_host_ignores_core_service_labels():
    """nginx等のcoreサービスにsite.hostが付いていても拾ってはならない。"""
    config = json.dumps(
        {
            "services": {
                "nginx": {
                    "networks": {"net-myapp": {}},
                    "labels": {"site.host": "core.ubuntu.local"},
                },
                "web": {"networks": {"net-myapp": {}}, "labels": {}},
            }
        }
    )
    with patch("server_base_cli.stacks.shell.capture") as mock_capture:
        mock_capture.side_effect = _capture_side_effect(config_stdout=config)
        assert stacks.app_site_host("myapp") is None


def test_app_site_host_raises_runtime_error_when_render_compose_fails():
    with patch("server_base_cli.stacks.shell.capture") as mock_capture:
        mock_capture.side_effect = _capture_side_effect(render_rc=1)
        with pytest.raises(RuntimeError, match="render-compose.sh"):
            stacks.app_site_host("myapp")


def test_app_site_host_raises_runtime_error_when_compose_config_fails():
    with patch("server_base_cli.stacks.shell.capture") as mock_capture:
        mock_capture.side_effect = _capture_side_effect(config_rc=1, config_stdout="")
        with pytest.raises(RuntimeError, match="docker compose config"):
            stacks.app_site_host("myapp")
