#!/usr/bin/env bash
# core/compose.yaml + stacks/*/docker-compose.yml をまとめて起動する。
#
# 手順: conf 生成 → up -d → nginx -t && nginx -s reload
# (この順序なら、他アプリが落ちていても nginx は起動・リロードできる。
#  core/nginx/conf.d/00-http.conf の resolver 化が前提)
#
# 使い方:
#   ./scripts/up.sh                       # 全プロファイルなしで起動（core のみ）
#   ./scripts/up.sh --profile time        # 特定プロファイルのみ起動（stacks 側で設定していれば）
#   COMPOSE_PROFILES=a,b ./scripts/up.sh  # .env / 環境変数でも指定可

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "==> compose.generated.yaml を生成"
COMPOSE_FILE="$(./scripts/render-compose.sh)"
echo "    -> $COMPOSE_FILE"

echo "==> nginx vhost 設定を生成 (site.* ラベル駆動)"
python3 ./scripts/gen-nginx-conf.py

echo "==> コンテナを起動"
docker compose -f "$COMPOSE_FILE" up -d "$@"

echo "==> nginx の設定を検証してリロード"
docker compose -f "$COMPOSE_FILE" exec -T nginx nginx -t
docker compose -f "$COMPOSE_FILE" exec -T nginx nginx -s reload

echo "==> 完了"
