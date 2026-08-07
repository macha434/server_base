#!/bin/bash
# server-base CLI を ~/.local/bin にインストールするスクリプト

set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BIN_DIR="$HOME/.local/bin"
TARGET="$BIN_DIR/server-base"

echo "=== server-base CLI のインストール ==="

echo ""
echo "1. python3の存在を確認しています..."
if ! command -v python3 &> /dev/null; then
    echo "エラー: python3 が見つかりません。インストールしてから再実行してください。" >&2
    exit 1
fi
echo "✓ python3が見つかりました ($(command -v python3))"

echo ""
echo "2. scripts/server-base に実行権限を付与しています..."
chmod +x "$ROOT/scripts/server-base"
echo "✓ 実行権限を付与しました"

echo ""
echo "3. $BIN_DIR を作成しています..."
mkdir -p "$BIN_DIR"
echo "✓ $BIN_DIR を作成しました"

echo ""
echo "4. シンボリックリンクを作成しています..."
ln -sf "$ROOT/scripts/server-base" "$TARGET"
echo "✓ $TARGET -> $ROOT/scripts/server-base"

echo ""
echo "5. \$PATHを確認しています..."
case ":$PATH:" in
    *":$BIN_DIR:"*)
        echo "✓ $BIN_DIR は \$PATH に含まれています"
        ;;
    *)
        echo "⚠ $BIN_DIR が \$PATH に含まれていません。以下をシェル設定に追加してください:"
        echo ""
        echo "  export PATH=\"\$HOME/.local/bin:\$PATH\""
        echo ""
        echo "  (bash: ~/.bashrc, zsh: ~/.zshrc に追記後、シェルを再起動してください)"
        ;;
esac

echo ""
echo "=== インストール完了！ ==="
echo ""
echo "使い方: server-base --help"
