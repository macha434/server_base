# LAN内でubuntu.localをHTTPSで公開する手順

このガイドでは、ローカルネットワーク内で `ubuntu.local` としてサーバーをHTTPSで公開する方法を説明します。

## 前提条件

- Docker と Docker Compose がインストールされていること
- Linux または macOS 環境

## セットアップ手順

### 1. SSL証明書の生成

```bash
# 証明書生成スクリプトに実行権限を付与
chmod +x nginx/ssl/generate-cert.sh

# 証明書を生成（ubuntu.localドメイン用）
cd nginx/ssl
./generate-cert.sh ubuntu.local
```

このスクリプトは以下を実行します：
- `mkcert` のインストール（未インストールの場合）
- ローカルCA（認証局）のセットアップ
- `ubuntu.local` 用の証明書とキーを生成

生成されるファイル：
- `ubuntu.local-cert.pem` - SSL証明書
- `ubuntu.local-key.pem` - 秘密鍵

### 2. ホスト名の設定

サーバーマシンのホスト名を `ubuntu.local` に設定します：

```bash
# 現在のホスト名を確認
hostname

# ホスト名を変更（一時的）
sudo hostname ubuntu.local

# 永続的に変更
sudo hostnamectl set-hostname ubuntu.local

# /etc/hostsに追加
echo "127.0.0.1 ubuntu.local" | sudo tee -a /etc/hosts
```

### 3. Avahi（mDNS）のセットアップ

LAN内の他のデバイスから `ubuntu.local` でアクセスできるようにします：

```bash
# Avahiをインストール
sudo apt-get update
sudo apt-get install -y avahi-daemon avahi-utils

# Avahiを起動
sudo systemctl start avahi-daemon
sudo systemctl enable avahi-daemon

# 動作確認
avahi-browse -a -t
```

### 4. Nginxコンテナの起動

```bash
# nginx ディレクトリに移動
cd /workspace/nginx

# コンテナを起動
docker compose up -d

# ログを確認
docker compose logs -f
```

### 5. 証明書の信頼設定（クライアント側）

各クライアントマシンでmkcertのCAを信頼する必要があります。

#### サーバーマシン（証明書を生成したマシン）
既に `mkcert -install` で設定済み

#### 他のクライアントマシン

**Option A: mkcertを使用（推奨）**

```bash
# mkcertをインストール
# Linux
wget https://github.com/FiloSottile/mkcert/releases/download/v1.4.4/mkcert-v1.4.4-linux-amd64
chmod +x mkcert-v1.4.4-linux-amd64
sudo mv mkcert-v1.4.4-linux-amd64 /usr/local/bin/mkcert

# macOS
brew install mkcert

# サーバーマシンからCA証明書をコピー
# サーバー側で実行
mkcert -CAROOT
# 表示されたディレクトリのrootCA.pemをクライアントにコピー

# クライアント側で実行
export CAROOT=/path/to/copied/ca
mkcert -install
```

**Option B: 手動で証明書を信頼**

```bash
# Linux (Ubuntu/Debian)
sudo cp rootCA.pem /usr/local/share/ca-certificates/mkcert-root.crt
sudo update-ca-certificates

# macOS
sudo security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain rootCA.pem
```

### 6. クライアントマシンのhosts設定

LAN内の各クライアントマシンで `/etc/hosts` を編集します：

```bash
# サーバーのIPアドレスを確認（サーバー側で実行）
ip addr show | grep "inet "

# クライアントマシンで /etc/hosts に追加
# 例: サーバーのIPが 192.168.1.100 の場合
echo "192.168.1.100 ubuntu.local" | sudo tee -a /etc/hosts
```

## 動作確認

### サーバー側

```bash
# HTTPSで接続テスト
curl -v https://ubuntu.local/health

# 証明書の確認
openssl s_client -connect ubuntu.local:443 -servername ubuntu.local
```

### クライアント側

ブラウザで以下のURLにアクセス：
- `https://ubuntu.local/health`

証明書エラーが表示されず、緑の鍵アイコンが表示されればOK！

## トラブルシューティング

### 証明書エラーが出る

```bash
# ブラウザのキャッシュをクリア
# Chromeの場合: chrome://settings/clearBrowserData

# 証明書を再生成
cd /workspace/nginx/ssl
rm ubuntu.local-*.pem
./generate-cert.sh ubuntu.local

# nginxを再起動
cd /workspace/nginx
docker compose restart
```

### ubuntu.localに接続できない

```bash
# Avahiが動作しているか確認
sudo systemctl status avahi-daemon

# mDNS名前解決を確認
avahi-resolve -n ubuntu.local

# ファイアウォール設定を確認
sudo ufw status
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 5353/udp  # mDNS用
```

### Nginxが起動しない

```bash
# ログを確認
docker compose logs nginx

# 設定ファイルのシンタックスチェック
docker compose exec nginx nginx -t

# 証明書ファイルのパーミッション確認
ls -la /workspace/nginx/ssl/
```

## セキュリティ注意事項

- **プライベート鍵の保護**: `ubuntu.local-key.pem` は機密情報です。適切に保護してください。
- **LAN内のみ**: この証明書はローカル開発用です。インターネットに公開しないでください。
- **本番環境**: 本番環境ではLet's Encryptなどの公式認証局の証明書を使用してください。

## 参考資料

- [mkcert GitHub](https://github.com/FiloSottile/mkcert)
- [Nginx SSL Configuration](https://nginx.org/en/docs/http/configuring_https_servers.html)
- [Avahi/mDNS Configuration](https://www.avahi.org/)
