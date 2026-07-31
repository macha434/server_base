#!/bin/bash
# systemdユーザーサービスのインストールスクリプト

set -e

SERVICE_NAME="core-stack.service"
SERVICE_FILE="$(dirname "$0")/$SERVICE_NAME"
SYSTEMD_DIR="$HOME/.config/systemd/user"
# core/systemd/install-service.sh から見てリポジトリルートは2階層上。
# clone先を決め打ちにせず、このスクリプトが実際に置かれている場所から都度算出する。
REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

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
# シンボリックリンクではなく、@@REPO_ROOT@@ をこのリポジトリの実パスに置換した
# 実体ファイルとして書き出す(WorkingDirectory/ExecStart/ExecStop を固定パスに
# 決め打ちしないため)。リポジトリを移動した場合は再度このスクリプトを実行すること。
sed "s|@@REPO_ROOT@@|$REPO_ROOT|g" "$SERVICE_FILE" > "$SYSTEMD_DIR/$SERVICE_NAME"
echo "✓ $SYSTEMD_DIR/$SERVICE_NAME に生成しました (REPO_ROOT=$REPO_ROOT)"

echo ""
echo "3. systemdをリロードしています..."
systemctl --user daemon-reload
echo "✓ systemdをリロードしました"

echo ""
echo "4. サービスを有効化しています..."
systemctl --user enable "$SERVICE_NAME"
echo "✓ サービスを有効化しました（ログイン時に自動起動します）"

echo ""
echo "5. サービスを開始しています..."
# set -e 下で start が失敗するとここに到達できず、原因調査に必要な
# status・journalctl の案内が出せないまま終了してしまう。
# 失敗時もステータスを表示してから exit するようにする。
if ! systemctl --user start "$SERVICE_NAME"; then
    echo "✗ サービスの開始に失敗しました" >&2
    systemctl --user status "$SERVICE_NAME" --no-pager || true
    echo "詳細は次のコマンドで確認できます: journalctl --user -u $SERVICE_NAME -e" >&2
    exit 1
fi
echo "✓ サービスを開始しました"

echo ""
echo "6. サービスステータス:"
systemctl --user status "$SERVICE_NAME" --no-pager

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
