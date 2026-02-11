# systemdユーザーサービス

dnsmasqコンテナをsystemdユーザーサービスとして管理し、ログイン時に自動起動させます。

## インストール

### 前提条件

1. dnsmasq.confが生成されていること（setup-dns.shを実行済み）
2. docker-composeがインストールされていること

### インストール手順

```bash
cd /workspace/dnsmasq/systemd
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
systemctl --user status dnsmasq-ubuntu-local
```

### サービスの開始

```bash
systemctl --user start dnsmasq-ubuntu-local
```

### サービスの停止

```bash
systemctl --user stop dnsmasq-ubuntu-local
```

### サービスの再起動

```bash
systemctl --user restart dnsmasq-ubuntu-local
```

### 自動起動の有効化/無効化

```bash
# 有効化（ログイン時に自動起動）
systemctl --user enable dnsmasq-ubuntu-local

# 無効化
systemctl --user disable dnsmasq-ubuntu-local
```

### ログの確認

```bash
# リアルタイムでログを表示
journalctl --user -u dnsmasq-ubuntu-local -f

# 最新のログを表示
journalctl --user -u dnsmasq-ubuntu-local -n 50

# 起動時のログを表示
journalctl --user -u dnsmasq-ubuntu-local -b
```

## アンインストール

```bash
cd /workspace/dnsmasq/systemd
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

2. WorkingDirectoryが正しいか確認:
   ```bash
   sudo systemctl cat dnsmasq-ubuntu-local
   ```

3. 手動でdocker-composeを実行してエラーを確認:
   ```bash
   cd /workspace/dnsmasq
   docker-compose up -d
   ```

### サービスファイルを編集する

```bash
# サービスファイルを編集
systemctl --user edit --full dnsmasq-ubuntu-local

# 変更を反映
systemctl --user daemon-reload
systemctl --user restart dnsmasq-ubuntu-local
```

## 注意事項

- サービスは `/workspace/dnsmasq` ディレクトリが存在することを前提としています
- docker-composeコマンドが `/usr/bin/docker-compose` にあることを前提としています
- サービスは `docker.service` が起動した後に開始されます
