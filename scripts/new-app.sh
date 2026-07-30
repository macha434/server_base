#!/usr/bin/env bash
# stacks/<app名>/docker-compose.yml の雛形を生成するスクリプト。
#
# アプリ側リポジトリ (deploy/docker-compose.yaml 等) は一切改変せず、
# server_base 側の stacks/<app名>/docker-compose.yml だけを新規生成する。
# 生成されるファイルは:
#   - include でアプリ側 compose を取り込む（相対パスはこのスクリプトが計算する）
#   - アプリのサービスを専用ネットワーク net-<app名> に載せる
#   - ports: !reset [] でホストへの publish を剥がす
#   - site.host / site.upstream / site.port ラベルを付与する
#     (scripts/gen-nginx-conf.py がこのラベルを読んで vhost を生成する)
#   - nginx を net-<app名> に参加させる
#
# 使い方:
#   scripts/new-app.sh <app名> <リポジトリパス> <composeファイル> <サービス名> <サブドメイン> <ポート>
#
# 例（time-announcement-frontend を server_base の兄弟ディレクトリにクローンした場合）:
#   scripts/new-app.sh time-announcement ../time-announcement-frontend deploy/docker-compose.yaml schedule-ui time 3000
#
#   <リポジトリパス>   … server_base ルートから見た相対パス（絶対パスも可）
#   <composeファイル> … <リポジトリパス> から見た相対パス
#   <サブドメイン>     … time なら time.ubuntu.local になる

set -euo pipefail

if [ $# -ne 6 ]; then
    echo "使い方: $0 <app名> <リポジトリパス> <composeファイル> <サービス名> <サブドメイン> <ポート>" >&2
    echo "例:     $0 time-announcement ../time-announcement-frontend deploy/docker-compose.yaml schedule-ui time 3000" >&2
    exit 1
fi

APP_NAME=$1
REPO_PATH=$2
COMPOSE_FILE=$3
SERVICE_NAME=$4
HOST_SUBDOMAIN=$5
PORT=$6

if ! [[ "$APP_NAME" =~ ^[a-z0-9][a-z0-9-]*$ ]]; then
    echo "エラー: <app名> は小文字英数字とハイフンのみ使用できます: $APP_NAME" >&2
    exit 1
fi
if ! [[ "$PORT" =~ ^[0-9]+$ ]]; then
    echo "エラー: <ポート> は数値である必要があります: $PORT" >&2
    exit 1
fi

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
STACK_DIR="$ROOT/stacks/$APP_NAME"
OUT="$STACK_DIR/docker-compose.yml"

if [ -e "$OUT" ]; then
    echo "既に存在します: $OUT" >&2
    exit 1
fi

ABS_REPO="$(cd "$ROOT" && realpath -m "$REPO_PATH")"
if [ ! -d "$ABS_REPO" ]; then
    echo "エラー: リポジトリディレクトリが見つかりません: $ABS_REPO" >&2
    exit 1
fi

ABS_COMPOSE="$ABS_REPO/$COMPOSE_FILE"
mkdir -p "$STACK_DIR"

# include の path / project_directory は「stacks/<app名>/docker-compose.yml 自身の位置」
# を基準に解決されるので、そこからの相対パスをこのスクリプトが計算する。
REL_COMPOSE=$(python3 - "$ABS_COMPOSE" "$STACK_DIR" <<'EOF'
import os, sys
print(os.path.relpath(sys.argv[1], sys.argv[2]))
EOF
)
REL_PROJECT_DIR=$(python3 - "$(dirname "$ABS_COMPOSE")" "$STACK_DIR" <<'EOF'
import os, sys
print(os.path.relpath(sys.argv[1], sys.argv[2]))
EOF
)

cat > "$OUT" <<YAML
# ${APP_NAME} を server_base 配下で動かすための差分。
# アプリ側リポジトリ (${REPO_PATH}) は改変しない。
include:
  - path: ${REL_COMPOSE}
    project_directory: ${REL_PROJECT_DIR}

services:
  ${SERVICE_NAME}:
    # nginx から到達できるよう専用ネットワークに載せる。
    # aliases で一意な upstream 名を明示する（nginx は全網に参加するため名前衝突を避ける）
    # !override: アプリ側 compose 自身が独自の networks を宣言している場合、単純に
    # 追記すると連結マージされて元のネットワークにも残ってしまう。完全に置き換える。
    networks: !override
      net-${APP_NAME}:
        aliases: [${APP_NAME}]
    # ホストへの publish を取り消す（nginx/TLS 経由のみに強制、ポート採番も不要に）
    ports: !reset []
    # scripts/gen-nginx-conf.py が読む vhost 定義
    labels:
      site.host: ${HOST_SUBDOMAIN}.ubuntu.local
      site.upstream: ${APP_NAME}
      site.port: "${PORT}"

  # nginx をこのアプリ専用網に参加させる（他の stacks ファイルとは連結マージされる）
  nginx:
    networks: [net-${APP_NAME}]

networks:
  net-${APP_NAME}:
    name: net-${APP_NAME}
YAML

echo "生成しました: $OUT"
echo ""
echo "次のステップ:"
echo "  1. アプリ側 compose に他にもサービス（DB 等）があれば、このファイルに追記して"
echo "     net-${APP_NAME} に載せてください（載せ忘れは scripts/gen-nginx-conf.py が検出します）"
echo "  2. ./scripts/up.sh を実行して起動してください"
