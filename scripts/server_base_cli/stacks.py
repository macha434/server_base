"""stacks/*/docker-compose.yml のアプリ一覧・サービス名解決。"""
from __future__ import annotations

from . import paths, shell


def list_apps() -> list[str]:
    """docker-compose.ymlを持つアプリ名を昇順で返す。"""
    if not paths.STACKS_DIR.is_dir():
        return []
    return sorted(p.parent.name for p in paths.STACKS_DIR.glob("*/docker-compose.yml"))


def app_exists(app_name: str) -> bool:
    return paths.stack_compose_path(app_name).is_file()


def app_services(app_name: str) -> list[str]:
    """stacks/<app_name>/docker-compose.yml が定義するサービス名一覧を返す。"""
    compose_file = paths.stack_compose_path(app_name)
    result = shell.capture(["docker", "compose", "-f", str(compose_file), "config", "--services"])
    if result.returncode != 0:
        raise RuntimeError(
            f"docker compose config --services が失敗しました({app_name}): {result.stderr}"
        )
    return [line for line in result.stdout.splitlines() if line.strip()]
