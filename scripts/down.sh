#!/usr/bin/env bash
# core/compose.yaml + stacks/*/docker-compose.yml をまとめて停止する。
#
# 使い方:
#   ./scripts/down.sh                # 全部停止
#   ./scripts/down.sh --profile time # 特定プロファイルのみ（docker compose down の引数をそのまま渡せる）

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

COMPOSE_FILE="$(./scripts/render-compose.sh)"
docker compose -f "$COMPOSE_FILE" down "$@"
