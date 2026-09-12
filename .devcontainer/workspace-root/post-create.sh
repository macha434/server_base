#!/usr/bin/env bash
set -euo pipefail

# workspace root (../) 用のエントリポイント。
# コンテナ自体は core を単独で開いた場合と同一の環境であるべきなので、
# セットアップ内容は複製せず core 側の post-create.sh にそのまま委譲する。
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVER_BASE_ROOT="$(dirname "$SCRIPT_DIR")"

exec bash "$SERVER_BASE_ROOT/server-base-core/.devcontainer/post-create.sh"
