# systemdユーザーサービス

Nginxコンテナをsystemdユーザーサービスとして管理し、ログイン時に自動起動させます。

## インストール

### 前提条件

1. docker-composeがインストールされていること
2. /workspace/nginx/docker-compose.yml が存在すること

### インストール手順

```bash
cd /workspace/nginx/systemd/user
chmod +x install-service.sh
./install-service.sh
```

これにより：
- サービスファイルが `~/.config/systemd/user/` にシンボリックリンクされます
- サービスが有効化され、ログイン時に自動起動します
- サービスがすぐに開始されます

※ sudo不要です

## 管理コマンド

### サービスの状態確認

```bash
systemctl --user status nginx-stack
```

### サービスの開始

```bash
systemctl --user start nginx-stack
```

### サービスの停止

```bash
systemctl --user stop nginx-stack
```

### サービスの再起動

```bash
systemctl --user restart nginx-stack
```

### 自動起動の有効化/無効化

```bash
# 有効化（ログイン時に自動起動）
systemctl --user enable nginx-stack

# 無効化
systemctl --user disable nginx-stack
```

### ログの確認

```bash
# リアルタイムでログを表示
journalctl --user -u nginx-stack -f

# 最新のログを表示
journalctl --user -u nginx-stack -n 50

# 起動時のログを表示
journalctl --user -u nginx-stack -b
```

## アンインストール

```bash
cd /workspace/nginx/systemd/user
chmod +x uninstall-service.sh
./uninstall-service.sh
```

これにより：
- サービスが停止されます
- 自動起動が無効化されます
- サービスファイルが削除されます

## トラブルシューティング

### サービスが起動しない

1. docker-composeのパスを確認:
   ```bash
   which docker-compose
   ```

2. 手動でdocker-composeを実行してエラーを確認:
   ```bash
   cd /workspace/nginx
   docker compose up -d
   ```

3. コンテナの状態を確認:
   ```bash
   docker ps -a
   docker logs nginx
   ```

### サービスファイルを編集する

```bash
# サービスファイルを編集
systemctl --user edit --full nginx-stack

# 変更を反映
systemctl --user daemon-reload
systemctl --user restart nginx-stack
```

## 注意事項

- サービスは `/workspace/nginx` ディレクトリが存在することを前提としています
- docker-composeコマンドが `/usr/bin/docker` にあることを前提としています
- ポート80と443が利用可能である必要があります
