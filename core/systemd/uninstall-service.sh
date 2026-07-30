#!/bin/bash
# systemdユーザーサービスのアンインストールスクリプト

set -e

SERVICE_NAME="core-stack.service"
SYSTEMD_DIR="$HOME/.config/systemd/user"

echo "=== server_base core-stack systemdユーザーサービスのアンインストール ==="

echo "1. サービスを停止しています..."
systemctl --user stop $SERVICE_NAME 2>/dev/null || echo "  (サービスは既に停止しています)"

echo ""
echo "2. サービスを無効化しています..."
systemctl --user disable $SERVICE_NAME 2>/dev/null || echo "  (サービスは既に無効化されています)"

echo ""
echo "3. サービスファイルを削除しています..."
if [ -f "$SYSTEMD_DIR/$SERVICE_NAME" ]; then
    rm "$SYSTEMD_DIR/$SERVICE_NAME"
    echo "✓ サービスファイルを削除しました"
else
    echo "  (サービスファイルは既に削除されています)"
fi

echo ""
echo "4. systemdをリロードしています..."
systemctl --user daemon-reload
echo "✓ systemdをリロードしました"

echo ""
echo "=== アンインストール完了！ ==="
