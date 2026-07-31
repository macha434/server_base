#!/usr/bin/env bash
# ローカル開発用SSL証明書生成スクリプト。
# 事前準備はDockerのみ(mkcertをホストにインストールする必要はない)。
# scripts/mkcert.Dockerfile でmkcertを同梱したイメージをビルドし、コンテナ内で実行する。

set -euo pipefail

DOMAIN="${1:-ubuntu.local}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SSL_DIR="$ROOT/ssl"
IMAGE="server-base-mkcert"
# CA(rootCA.pem/rootCA-key.pem)はssl/mkcert-ca/に永続化する。
# ここを消さない限り、再実行しても同じCAが再利用され、既存クライアントの信頼設定は壊れない。
CAROOT_DIR="$SSL_DIR/mkcert-ca"

echo "=== ローカル開発用SSL証明書を生成します ==="
echo "ドメイン: $DOMAIN"
echo "出力先: $SSL_DIR"
echo ""

mkdir -p "$CAROOT_DIR"

echo "==> mkcertイメージをビルド"
docker build -q -t "$IMAGE" -f "$ROOT/scripts/mkcert.Dockerfile" "$ROOT/scripts" >/dev/null

echo "==> ローカルCA(認証局)をセットアップ(初回のみ新規作成、以降は再利用)"
docker run --rm -e CAROOT=/ssl/mkcert-ca -v "$SSL_DIR:/ssl" "$IMAGE" -install

echo "==> 証明書を生成"
docker run --rm -e CAROOT=/ssl/mkcert-ca -v "$SSL_DIR:/ssl" -w /ssl "$IMAGE" \
    -key-file "${DOMAIN}-key.pem" -cert-file "${DOMAIN}-cert.pem" \
    "$DOMAIN" "*.${DOMAIN}" localhost 127.0.0.1 ::1

echo ""
echo "=== 証明書生成完了！ ==="
echo "証明書ファイル:"
echo "  - ${SSL_DIR}/${DOMAIN}-cert.pem"
echo "  - ${SSL_DIR}/${DOMAIN}-key.pem"
echo "CAのルート証明書(クライアント側の信頼設定に使う):"
echo "  - ${CAROOT_DIR}/rootCA.pem"
echo ""
echo "次のステップ:"
echo "1. nginx設定でこれらの証明書を使用してください"
echo "2. /etc/hosts に '$DOMAIN' を追加してください"
echo "3. nginxを再起動してください"
