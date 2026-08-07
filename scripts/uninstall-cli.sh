#!/bin/bash
# server-base CLI のアンインストールスクリプト

set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BIN_DIR="$HOME/.local/bin"
TARGET="$BIN_DIR/server-base"
EXPECTED="$ROOT/scripts/server-base"

echo "=== server-base CLI のアンインストール ==="

echo ""
if [ ! -e "$TARGET" ]; then
    echo "  ($TARGET は存在しません。既にアンインストール済みです)"
elif [ ! -L "$TARGET" ]; then
    echo "警告: $TARGET はシンボリックリンクではありません。誤削除を避けるため何もしません。" >&2
    echo "  手動で確認・削除してください。" >&2
    exit 1
else
    LINK_TARGET="$(readlink "$TARGET")"
    if [ "$LINK_TARGET" != "$EXPECTED" ]; then
        echo "警告: $TARGET は別の場所を指しています ($LINK_TARGET)。誤削除を避けるため何もしません。" >&2
        exit 1
    fi
    rm "$TARGET"
    echo "✓ $TARGET を削除しました"
fi

echo ""
echo "=== アンインストール完了！ ==="
