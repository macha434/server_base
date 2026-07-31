#!/bin/bash
# systemdユーザーサービスのアンインストールスクリプト

set -e

SERVICE_NAME="core-stack.service"
SYSTEMD_DIR="$HOME/.config/systemd/user"

echo "=== server_base core-stack systemdユーザーサービスのアンインストール ==="

echo "1. サービスを停止しています..."
# stderrは握りつぶさない。失敗理由が「未インストールだから」なのか、
# systemd --user セッション自体に問題があるのかを区別できるようにする。
if ! systemctl --user stop "$SERVICE_NAME"; then
    echo "  (停止に失敗しました。上のエラーを確認してください。未インストールなら無視してよい)"
fi

echo ""
echo "2. サービスを無効化しています..."
if ! systemctl --user disable "$SERVICE_NAME"; then
    echo "  (無効化に失敗しました。上のエラーを確認してください。未インストールなら無視してよい)"
fi

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
