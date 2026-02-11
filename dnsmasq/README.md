# ubuntu.local 専用DNSサーバー

ubuntu.localドメインとそのサブドメイン（`*.ubuntu.local`）を自動的に192.168.3.17に解決するDNSサーバーです。

## 特徴

- **ubuntu.localドメイン専用**: 他のドメインには影響しません
- **ワイルドカード対応**: `nature.ubuntu.local`, `api.ubuntu.local` など全てのサブドメインを自動解決
- **/etc/hosts編集不要**: システムのDNS設定のみで動作

## セットアップ

### 1. DNSサーバーを起動

```bash
cd /workspace/dnsmasq
chmod +x setup-dns.sh

# IPアドレスを指定して起動（必須）
./setup-dns.sh 127.0.0.1

# または別のIPアドレス
./setup-dns.sh 192.168.1.100
```

スクリプトは自動的に：
1. IPアドレスに基づいて`dnsmasq.conf`を生成
2. dnsmasqコンテナを起動
3. DNS解決をテスト

### 2. システムのDNS設定

#### Linux (systemd-resolved)

```bash
sudo mkdir -p /etc/systemd/resolved.conf.d
sudo tee /etc/systemd/resolved.conf.d/ubuntu-local.conf <<EOF
[Resolve]
DNS=127.0.0.1
Domains=~ubuntu.local
EOF
sudo systemctl restart systemd-resolved
```

#### macOS

```bash
sudo mkdir -p /etc/resolver
sudo tee /etc/resolver/ubuntu.local <<EOF
nameserver 127.0.0.1
EOF
```

#### Windows

1. ネットワーク設定 → アダプターオプションの変更
2. 使用中の接続を右クリック → プロパティ
3. IPv4 → プロパティ
4. 優先DNSサーバー: `127.0.0.1`
5. 代替DNSサーバー: `8.8.8.8`

### 3. 動作確認

```bash
nslookup ubuntu.local
nslookup nature.ubuntu.local
nslookup api.ubuntu.local
```

全て `192.168.3.17` に解決されれば成功です。

## 管理

### systemdユーザーサービスとして管理（推奨）

ログイン時に自動起動させたい場合は、systemdユーザーサービスとしてインストールします：

```bash
cd /workspace/dnsmasq/systemd
chmod +x install-service.sh
./install-service.sh
```

詳細は[systemd/README.md](systemd/README.md)を参照してください。

### Web UI

http://localhost:5380 で管理画面にアクセスできます。

### ログ確認

```bash
docker-compose logs -f dnsmasq
```

### 再起動

```bash
docker-compose restart
```

### 停止

```bash
docker-compose down
```

新しいIPアドレスでセットアップスクリプトを再実行：

```bash
./setup-dns.sh 新しいIPアドレス
```

例：
```bash
./setup-dns.sh 127.0.0.1
```

これにより`dnsmasq.conf`が再生成され、コンテナが再起動されます。は再起動：

```bash
docker-compose restart
```

## トラブルシューティング

### ポート53が既に使用されている

```bash
# 使用中のプロセスを確認
sudo lsof -i :53

# systemd-resolvedがポート53を使用している場合
sudo sed -i 's/#DNSStubListener=yes/DNSStubListener=no/' /etc/systemd/resolved.conf
sudo systemctl restart systemd-resolved
```

### DNSが解決されない

1. dnsmasqが起動しているか確認:
   ```bash
   docker ps | grep dnsmasq
   ```

2. 直接クエリして確認:
   ```bash
   dig @127.0.0.1 ubuntu.local
   ```

3. システムのDNS設定を確認:
   ```bash
   # Linux
   resolvectl status
   
   # macOS
   scutil --dns
   
   # Windows
   ipconfig /all
   ```
