#!/bin/bash
# systemdユーザーサービスのインストールスクリプト

set -e

SERVICE_NAME="core-stack.service"
SERVICE_FILE="$(dirname "$0")/$SERVICE_NAME"
SYSTEMD_DIR="$HOME/.config/systemd/user"

echo "=== server_base core-stack systemdユーザーサービスのインストール ==="

if [ ! -f "$SERVICE_FILE" ]; then
    echo "エラー: サービスファイルが見つかりません: $SERVICE_FILE"
    exit 1
fi

echo "1. ユーザーsystemdディレクトリを作成しています..."
mkdir -p "$SYSTEMD_DIR"
echo "✓ $SYSTEMD_DIR を作成しました"

echo ""
echo "2. サービスファイルをインストールしています..."
SERVICE_FILE_ABS="$(cd "$(dirname "$SERVICE_FILE")" && pwd)/$(basename "$SERVICE_FILE")"
ln -sf "$SERVICE_FILE_ABS" "$SYSTEMD_DIR/$SERVICE_NAME"
echo "✓ $SYSTEMD_DIR/$SERVICE_NAME にシンボリックリンクを作成しました"

echo ""
echo "3. systemdをリロードしています..."
systemctl --user daemon-reload
echo "✓ systemdをリロードしました"

echo ""
echo "4. サービスを有効化しています..."
systemctl --user enable $SERVICE_NAME
echo "✓ サービスを有効化しました（ログイン時に自動起動します）"

echo ""
echo "5. サービスを開始しています..."
systemctl --user start $SERVICE_NAME
echo "✓ サービスを開始しました"

echo ""
echo "6. サービスステータス:"
systemctl --user status $SERVICE_NAME --no-pager

echo ""
echo "=== インストール完了！ ==="
echo ""
echo "便利なコマンド:"
echo "  サービス状態確認:   systemctl --user status $SERVICE_NAME"
echo "  サービス開始:       systemctl --user start $SERVICE_NAME"
echo "  サービス停止:       systemctl --user stop $SERVICE_NAME"
echo "  サービス再起動:     systemctl --user restart $SERVICE_NAME"
echo "  自動起動を無効化:   systemctl --user disable $SERVICE_NAME"
echo "  ログ確認:           journalctl --user -u $SERVICE_NAME -f"
