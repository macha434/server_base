#!/bin/bash
# ローカル開発用SSL証明書生成スクリプト

set -e

DOMAIN="${1:-ubuntu.local}"
SSL_DIR="$(dirname "$0")"

echo "=== ローカル開発用SSL証明書を生成します ==="
echo "ドメイン: $DOMAIN"
echo "出力先: $SSL_DIR"
echo ""

# mkcertがインストールされているか確認
if ! command -v mkcert &> /dev/null; then
    echo "mkcertがインストールされていません。インストールを開始します..."
    
    # OS検出
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        # Linuxの場合
        if command -v apt-get &> /dev/null; then
            sudo apt-get update
            sudo apt-get install -y libnss3-tools wget
            
            # mkcertのバイナリをダウンロード
            MKCERT_VERSION="v1.4.4"
            wget -O /tmp/mkcert "https://github.com/FiloSottile/mkcert/releases/download/${MKCERT_VERSION}/mkcert-${MKCERT_VERSION}-linux-amd64"
            chmod +x /tmp/mkcert
            sudo mv /tmp/mkcert /usr/local/bin/mkcert
        fi
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        # macOSの場合
        if command -v brew &> /dev/null; then
            brew install mkcert
        else
            echo "Homebrewがインストールされていません。"
            exit 1
        fi
    else
        echo "サポートされていないOS: $OSTYPE"
        exit 1
    fi
fi

# ローカルCAをインストール（初回のみ）
echo "ローカルCA（認証局）をセットアップします..."
mkcert -install

# 証明書を生成
echo "証明書を生成しています..."
cd "$SSL_DIR"
mkcert -key-file "${DOMAIN}-key.pem" -cert-file "${DOMAIN}-cert.pem" "$DOMAIN" "*.${DOMAIN}" localhost 127.0.0.1 ::1

echo ""
echo "=== 証明書生成完了！ ==="
echo "証明書ファイル:"
echo "  - ${SSL_DIR}/${DOMAIN}-cert.pem"
echo "  - ${SSL_DIR}/${DOMAIN}-key.pem"
echo ""
echo "次のステップ:"
echo "1. nginx設定でこれらの証明書を使用してください"
echo "2. /etc/hosts に '$DOMAIN' を追加してください"
echo "3. nginxを再起動してください"
