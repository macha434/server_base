"""stacks/*/docker-compose.yml のアプリ一覧・サービス名解決。"""
from __future__ import annotations

import json

from . import paths, shell

# core/compose.yaml のサービス。全アプリの net-<app名> に参加する(nginxがルーティングするため)
# が、アプリ固有のサービスではないので app_services/app_site_host からは除外する。
_CORE_SERVICES = {"nginx", "dnsmasq"}


def list_apps() -> list[str]:
    """docker-compose.ymlを持つアプリ名を昇順で返す。"""
    if not paths.STACKS_DIR.is_dir():
        return []
    return sorted(p.parent.name for p in paths.STACKS_DIR.glob("*/docker-compose.yml"))


def app_exists(app_name: str) -> bool:
    return paths.stack_compose_path(app_name).is_file()


def _app_services_config(app_name: str) -> dict:
    """<app_name>のネットワーク(net-<app_name>)に属するアプリ固有サービスのcompose設定を返す。

    stacks/<app_name>/docker-compose.yml単体では、そのファイルが追加するnginxの
    ネットワーク参加設定にnginx自体のimageが無く(core/compose.yamlにしか無いため)
    `docker compose config`が失敗する。そのため必ずcompose.generated.yaml
    (core+全stacksを合成した完全なプロジェクト)経由で読む。
    """
    render_result = shell.capture([str(paths.script_path("render-compose.sh"))])
    if render_result.returncode != 0:
        raise RuntimeError(f"render-compose.sh が失敗しました: {render_result.stderr}")

    result = shell.capture(
        ["docker", "compose", "-f", str(paths.COMPOSE_GENERATED), "config", "--format", "json"]
    )
    if result.returncode != 0:
        raise RuntimeError(f"docker compose config が失敗しました({app_name}): {result.stderr}")

    cfg = json.loads(result.stdout)
    network_name = f"net-{app_name}"
    services = {}
    for name, svc in (cfg.get("services") or {}).items():
        if name in _CORE_SERVICES:
            continue
        networks = svc.get("networks") or {}
        if network_name in networks:
            services[name] = svc
    return services


def app_services(app_name: str) -> list[str]:
    """<app_name>のnet-<app_name>に属するアプリ固有サービス名一覧を返す(nginx/dnsmasqは除く)。"""
    return sorted(_app_services_config(app_name).keys())


def app_site_host(app_name: str) -> str | None:
    """<app_name>のいずれかのサービスに付いたsite.hostラベルの値を返す。見つからなければNone。"""
    for svc in _app_services_config(app_name).values():
        labels = svc.get("labels") or {}
        if "site.host" in labels:
            return labels["site.host"]
    return None
