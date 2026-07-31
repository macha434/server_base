#!/usr/bin/env bash
# core/compose.yaml + stacks/*/docker-compose.yml をまとめて起動する。
#
# 手順: conf 生成 → core(nginx・dnsmasq)を先に up -d → アプリを up -d → nginx -t && reload
# (nginx・dnsmasqを先に単独で起動するのは、あるアプリのイメージがpull/build失敗する
#  ような compose 全体のエラーで `up -d` 自体が失敗すると、その一発呼び出しでは
#  core を含め何も起動されないため。実測で確認済み: 1つのサービスがpull失敗するだけで
#  `docker compose up -d` はコンテナを1つも作らずexit 1で終わる。
#  先にcoreだけ起動しておけば、後続のアプリ起動が失敗しても core は起動済みのまま残る。
#  core/nginx/conf.d/00-http.conf の resolver 化により、個々のアプリが未起動でも
#  nginx 自体は起動・リロードできる)
#
# 使い方:
#   ./scripts/up.sh                       # core + stacks/ の全アプリを起動
#                                          # (stacks/*/docker-compose.yml が profiles: を
#                                          #  設定していない限り、profile指定の有無に関わらず全部起動する)
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

echo "==> core (nginx・dnsmasq) を起動"
# --profile はサブコマンドではなく docker compose 本体のフラグなので、
# up より前に渡す必要がある("$@" を up -d の後ろに置くと unknown flag になる)。
docker compose -f "$COMPOSE_FILE" "$@" up -d nginx dnsmasq

echo "==> アプリを起動"
# アプリ側のイメージpull/build失敗はここで止めず、core は起動済みのまま次に進む
# (詳細は本ファイル冒頭のコメント参照)。
if ! docker compose -f "$COMPOSE_FILE" "$@" up -d; then
    echo "!!! 一部のアプリの起動に失敗しました(上のエラー参照)。" >&2
    echo "!!! core(nginx・dnsmasq)は起動済みのまま、正常なアプリの設定のみ反映します。" >&2
fi

echo "==> nginx の設定を検証してリロード"
docker compose -f "$COMPOSE_FILE" exec -T nginx nginx -t
docker compose -f "$COMPOSE_FILE" exec -T nginx nginx -s reload

echo "==> 完了"
