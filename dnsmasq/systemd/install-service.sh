#!/bin/bash
# systemdユーザーサービスのインストールスクリプト

set -e

SERVICE_NAME="dnsmasq-ubuntu-local.service"
SERVICE_FILE="$(dirname "$0")/$SERVICE_NAME"
SYSTEMD_DIR="$HOME/.config/systemd/user"

echo "=== dnsmasq systemdユーザーサービスのインストール ==="

# サービスファイルの存在確認
if [ ! -f "$SERVICE_FILE" ]; then
    echo "エラー: サービスファイルが見つかりません: $SERVICE_FILE"
    exit 1
fi

# 1. ユーザーsystemdディレクトリを作成
echo "1. ユーザーsystemdディレクトリを作成しています..."
mkdir -p "$SYSTEMD_DIR"
echo "✓ $SYSTEMD_DIR を作成しました"

# 2. サービスファイルをシンボリックリンク
echo ""
echo "2. サービスファイルをインストールしています..."
# 絶対パスを取得
SERVICE_FILE_ABS="$(cd "$(dirname "$SERVICE_FILE")" && pwd)/$(basename "$SERVICE_FILE")"
ln -sf "$SERVICE_FILE_ABS" "$SYSTEMD_DIR/$SERVICE_NAME"
echo "✓ $SYSTEMD_DIR/$SERVICE_NAME にシンボリックリンクを作成しました"

# 3. systemdをリロード
echo ""
echo "3. systemdをリロードしています..."
systemctl --user daemon-reload
echo "✓ systemdをリロードしました"

# 4. サービスを有効化
echo ""
echo "4. サービスを有効化しています..."
systemctl --user enable $SERVICE_NAME
echo "✓ サービスを有効化しました（ログイン時に自動起動します）"

# 5. サービスを開始
echo ""
echo "5. サービスを開始しています..."
systemctl --user start $SERVICE_NAME
echo "✓ サービスを開始しました"

# 6. ステータス確認
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
