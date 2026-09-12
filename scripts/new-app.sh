#!/usr/bin/env bash
# stacks/<app名>/docker-compose.yml の雛形を生成するスクリプト。
#
# アプリ側リポジトリ (deploy/docker-compose.yaml 等) は一切改変せず、
# server-base-core 側の stacks/<app名>/docker-compose.yml だけを新規生成する。
# 生成されるファイルは:
#   - include でアプリ側 compose を取り込む（相対パスはこのスクリプトが計算する）
#   - アプリのサービスを専用ネットワーク net-<app名> に載せる
#   - ports: !reset [] でホストへの publish を剥がす
#   - site.host / site.upstream / site.port ラベルを付与する
#     (scripts/gen-nginx-conf.py がこのラベルを読んで vhost を生成する)
#   - nginx を net-<app名> に参加させる
#
# 使い方:
#   scripts/new-app.sh <repoのURL> [--service NAME] [--compose-file PATH] [--subdomain NAME] [--port N]
#
# app名はリポジトリURLから導出し、../<app名> に未cloneならこのスクリプトがcloneする
# (既にcloneされていればそのまま使う)。
#
# サブドメイン・ポート番号は、アプリ側composeの対象サービスに付与された
# labels (site.subdomain / site.port) から自動検出する(規約は
# docs/superpowers/specs/2026-09-12-app-compose-convention-design.md 参照)。
# site.port が無い場合は自動検出できないため、エラーで案内して終了する。
# site.subdomain が無い場合は app名をそのまま使う。
# --subdomain / --port でそれぞれ個別に上書きできる。
#
# compose ファイルの場所も、省略時は
#   deploy/docker-compose.yaml → docker-compose.yaml → docker-compose.yml
# の順で自動探索する。見つからない場合のみ --compose-file で明示する。
#
# サービス名も省略可。アプリ側composeのサービスが1個だけなら自動検出する。
# 2個以上ある場合は省略できず、--service で明示する必要がある。
#
# 例（time-announcement-frontend。deploy/docker-compose.yaml の
#     schedule-ui サービスに site.port: "3000" ラベルが付与済みの場合）:
#   scripts/new-app.sh https://github.com/coresync-fukuhara/time-announcement-frontend

set -euo pipefail

usage() {
    cat >&2 <<'USAGE'
使い方: scripts/new-app.sh <repoのURL> [--service NAME] [--compose-file PATH] [--subdomain NAME] [--port N]

  <repoのURL>          アプリ側リポジトリのgit URL。../<app名> に未cloneならcloneする
                       (app名はURLから導出。既にcloneされていればそのまま使う)
  --service NAME       アプリ側composeのサービス名。省略時、サービスが1個だけなら自動検出
  --compose-file PATH  アプリ側composeファイルの相対パス。省略時は
                       deploy/docker-compose.yaml → docker-compose.yaml → docker-compose.yml
                       の順で探索
  --subdomain NAME     省略時は対象サービスの labels.site.subdomain 、それも無ければapp名を使う
  --port N             省略時は対象サービスの labels.site.port を使う(必須の情報。
                       アプリ側composeに無ければエラーで案内する)

例:
  scripts/new-app.sh https://github.com/coresync-fukuhara/time-announcement-frontend
USAGE
}

if [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ]; then
    usage
    exit 0
fi
if [ $# -lt 1 ]; then
    usage
    exit 1
fi

REPO_URL=$1
shift

SERVICE_NAME=""
COMPOSE_FILE_OPT=""
HOST_SUBDOMAIN_OPT=""
PORT_OPT=""
while [ $# -gt 0 ]; do
    case "$1" in
        --service)
            SERVICE_NAME=${2:?"--service には値が必要です"}
            shift 2
            ;;
        --compose-file)
            COMPOSE_FILE_OPT=${2:?"--compose-file には値が必要です"}
            shift 2
            ;;
        --subdomain)
            HOST_SUBDOMAIN_OPT=${2:?"--subdomain には値が必要です"}
            shift 2
            ;;
        --port)
            PORT_OPT=${2:?"--port には値が必要です"}
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "エラー: 不明な引数です: $1" >&2
            usage
            exit 1
            ;;
    esac
done

if [ -n "$SERVICE_NAME" ] && ! [[ "$SERVICE_NAME" =~ ^[a-zA-Z0-9._-]+$ ]]; then
    echo "エラー: <サービス名> に使える文字は英数字・._- のみです: $SERVICE_NAME" >&2
    exit 1
fi

# リポジトリURLの最後のパスセグメントからapp名を導出する(.gitサフィックス除去、
# 大文字→小文字・アンダースコア→ハイフンに正規化)。
derive_app_name() {
    local name="${1%/}"
    name="${name##*/}"
    name="${name%.git}"
    printf '%s' "$name" | tr '[:upper:]_' '[:lower:]-'
}
APP_NAME="$(derive_app_name "$REPO_URL")"

if ! [[ "$APP_NAME" =~ ^[a-z0-9][a-z0-9-]*$ ]]; then
    echo "エラー: リポジトリ名からapp名(小文字英数字とハイフンのみ)を導出できませんでした: $APP_NAME" >&2
    echo "リポジトリ名を変更するか、事前に '../<app名>' としてcloneしておいてから再実行してください。" >&2
    exit 1
fi

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
STACK_DIR="$ROOT/stacks/$APP_NAME"
OUT="$STACK_DIR/docker-compose.yml"

if [ -e "$OUT" ]; then
    echo "既に存在します: $OUT" >&2
    exit 1
fi

APP_DIR="$ROOT/../$APP_NAME"
if [ ! -d "$APP_DIR" ]; then
    git clone "$REPO_URL" "$APP_DIR"
fi
ABS_REPO="$(cd "$APP_DIR" && pwd)"

if [ -n "$COMPOSE_FILE_OPT" ]; then
    COMPOSE_FILE="$COMPOSE_FILE_OPT"
    if [ ! -f "$ABS_REPO/$COMPOSE_FILE" ]; then
        echo "エラー: composeファイルが見つかりません: $ABS_REPO/$COMPOSE_FILE" >&2
        exit 1
    fi
else
    COMPOSE_FILE=""
    for candidate in deploy/docker-compose.yaml docker-compose.yaml docker-compose.yml; do
        if [ -f "$ABS_REPO/$candidate" ]; then
            COMPOSE_FILE="$candidate"
            break
        fi
    done
    if [ -z "$COMPOSE_FILE" ]; then
        echo "エラー: composeファイルを自動検出できませんでした(deploy/docker-compose.yaml / docker-compose.yaml / docker-compose.yml のいずれも見つかりません): $ABS_REPO" >&2
        echo "--compose-file で明示してください。" >&2
        exit 1
    fi
    echo "composeファイルを自動検出しました: $COMPOSE_FILE"
fi
ABS_COMPOSE="$ABS_REPO/$COMPOSE_FILE"

# <サービス名> がタイプミスだと、アプリ側compose内に存在しないサービスを指す
# 空のservicesブロックが生成されてしまい、docker compose config で分かりにくい
# エラーになる(image/buildが無い等)。ここで実際に存在するサービス名か検証する
# (省略時はここで自動検出も行う)。
AVAILABLE_SERVICES="$(docker compose -f "$ABS_COMPOSE" --project-directory "$(dirname "$ABS_COMPOSE")" config --services 2>/dev/null || true)"

if [ -z "$SERVICE_NAME" ]; then
    if [ -z "$AVAILABLE_SERVICES" ]; then
        echo "エラー: ${COMPOSE_FILE} のサービス一覧取得に失敗したため自動検出できません。" >&2
        echo "--service で明示して再実行してください。" >&2
        exit 1
    fi
    SERVICE_COUNT="$(wc -l <<< "$AVAILABLE_SERVICES")"
    if [ "$SERVICE_COUNT" -ne 1 ]; then
        echo "エラー: ${COMPOSE_FILE} にサービスが複数あるため自動検出できません。" >&2
        echo "存在するサービス: $(tr '\n' ' ' <<< "$AVAILABLE_SERVICES")" >&2
        echo "--service で明示して再実行してください。" >&2
        exit 1
    fi
    SERVICE_NAME="$AVAILABLE_SERVICES"
    echo "サービス名を自動検出しました: $SERVICE_NAME"
elif [ -z "$AVAILABLE_SERVICES" ]; then
    echo "警告: ${COMPOSE_FILE} のサービス一覧取得に失敗したため、--service の実在チェックをスキップします" >&2
elif ! grep -qxF "$SERVICE_NAME" <<< "$AVAILABLE_SERVICES"; then
    echo "エラー: サービス '$SERVICE_NAME' は ${COMPOSE_FILE} に存在しません。" >&2
    echo "存在するサービス: $(tr '\n' ' ' <<< "$AVAILABLE_SERVICES")" >&2
    exit 1
fi

# site.port / site.subdomain ラベルをアプリ側composeから読み取る。
CONFIG_JSON="$(docker compose -f "$ABS_COMPOSE" --project-directory "$(dirname "$ABS_COMPOSE")" config --format json 2>/dev/null || true)"

read_label() {
    local key="$1"
    python3 -c '
import json, sys

cfg_json, service, key = sys.argv[1], sys.argv[2], sys.argv[3]
try:
    cfg = json.loads(cfg_json)
except Exception:
    sys.exit(0)
labels = cfg.get("services", {}).get(service, {}).get("labels") or {}
if isinstance(labels, list):
    labels = dict(item.split("=", 1) for item in labels if "=" in item)
value = labels.get(key)
if value is not None:
    print(value)
' "$CONFIG_JSON" "$SERVICE_NAME" "$key"
}

if [ -n "$PORT_OPT" ]; then
    PORT="$PORT_OPT"
else
    PORT="$(read_label "site.port")"
    if [ -z "$PORT" ]; then
        echo "エラー: ポート番号を自動検出できませんでした。" >&2
        echo "アプリ側compose(${COMPOSE_FILE})の '${SERVICE_NAME}' サービスに以下のlabelを追加してください:" >&2
        echo "  labels:" >&2
        echo "    site.port: \"3000\"   # 実際のポート番号に置き換える" >&2
        echo "(または --port で明示してください)" >&2
        exit 1
    fi
fi

if [ -n "$HOST_SUBDOMAIN_OPT" ]; then
    HOST_SUBDOMAIN="$HOST_SUBDOMAIN_OPT"
else
    HOST_SUBDOMAIN="$(read_label "site.subdomain")"
    if [ -z "$HOST_SUBDOMAIN" ]; then
        HOST_SUBDOMAIN="$APP_NAME"
    fi
fi

if ! [[ "$HOST_SUBDOMAIN" =~ ^[a-z0-9][a-z0-9-]*$ ]]; then
    echo "エラー: <サブドメイン> は小文字英数字とハイフンのみ使用できます: $HOST_SUBDOMAIN" >&2
    exit 1
fi
if ! [[ "$PORT" =~ ^[0-9]+$ ]]; then
    echo "エラー: <ポート> は数値である必要があります: $PORT" >&2
    exit 1
fi

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
# ${APP_NAME} を server-base-core 配下で動かすための差分。
# アプリ側リポジトリ (${REPO_URL}) は改変しない。
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
    # setup-dns.sh がホストのsystemd-resolvedに設定する DNS=127.0.0.1 が
    # upstream server として紛れ込むと、コンテナの埋め込みDNS(127.0.0.11)が
    # その127.0.0.1（コンテナ自身のloopback、何も listen していない）に転送しようとして
    # 外部ドメインの名前解決が失敗することがある。ここで明示的に到達可能なDNSを指定して回避する。
    dns:
      - 1.1.1.1
      - 8.8.8.8
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
