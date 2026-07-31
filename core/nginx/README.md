# core/nginx/ - LAN内でubuntu.localをHTTPSで公開する

このガイドでは、ローカルネットワーク内で `ubuntu.local` としてサーバーをHTTPSで公開する方法を説明します。

`*.ubuntu.local` のDNS解決(ワイルドカード対応)は [core/dnsmasq/README.md](../dnsmasq/README.md)
が別途担当します。ホスト名変更やAvahi(mDNS)は不要です(mDNSはワイルドカードサブドメインを
解決できないため、そもそもこの用途には使えません)。

## 構成

- `conf.d/00-http.conf` - resolver・WebSocket用map(httpコンテキスト)
- `conf.d/snippets/` - `ssl.conf`・`security.conf`・`proxy.conf`(各vhostからinclude)
- `conf.d/default.conf` - localhost・ubuntu.localのヘルスチェック用vhost
- `conf.d/*.ubuntu.local.conf` - アプリごとのvhost。`scripts/gen-nginx-conf.py` が生成(gitignore対象)
- `template/site.conf.template` - 上記vhost生成のテンプレート

TLS証明書自体は `ssl/`(リポジトリ直下、`core/` の内部構造とは独立)に置く。

## 前提条件

- Docker と Docker Compose がインストールされていること
- [core/dnsmasq/README.md](../dnsmasq/README.md) の手順で `*.ubuntu.local` が解決できること
  (クライアント側のDNS設定も含む)

## セットアップ手順

### 1. SSL証明書の生成

事前準備はDockerのみです。mkcert自体をホストにインストールする必要はありません
（`scripts/mkcert.Dockerfile` で同梱したイメージをコンテナ内で使う）。

```bash
# リポジトリルートから実行する（出力先は常に ssl/ 配下に固定される）
./scripts/generate-cert.sh ubuntu.local
```

このスクリプトは以下を実行します：
- `scripts/mkcert.Dockerfile` から mkcert 同梱イメージをビルド（初回のみ。以降は Docker のレイヤーキャッシュが効く）
- コンテナ内でローカルCA（認証局）をセットアップ（`ssl/mkcert-ca/` に永続化。既に存在すれば再利用するので、
  再実行しても別のCAに変わってクライアントの信頼設定が壊れることはない）
- `ubuntu.local` 用の証明書とキーを `ssl/` 配下に生成

生成されるファイル：
- `ssl/ubuntu.local-cert.pem` - SSL証明書
- `ssl/ubuntu.local-key.pem` - 秘密鍵
- `ssl/mkcert-ca/rootCA.pem` - ローカルCAのルート証明書（クライアント側の信頼設定に使う。下記3.参照）

### 2. Nginxコンテナの起動

```bash
# リポジトリルートから起動スクリプトを実行
./scripts/up.sh

# ログを確認
docker compose -f core/compose.yaml logs -f nginx
```

### 3. 証明書の信頼設定（クライアント側）

各クライアントマシンでmkcertのCAを信頼する必要があります。

#### サーバーマシン（証明書を生成したマシン）

`mkcert -install` はコンテナ内で実行されるため、**サーバー機自体のOS証明書ストアには
入っていません**。サーバー機のブラウザで直接 `https://ubuntu.local/` を開く場合も、
下記の他クライアントと同じ手順で `ssl/mkcert-ca/rootCA.pem` を信頼させる必要があります。

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

# サーバー側の ssl/mkcert-ca/ をクライアントにコピー

# クライアント側で実行
export CAROOT=/path/to/copied/ssl/mkcert-ca
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

### 4. クライアント側のDNS設定

`*.ubuntu.local` を名前解決できるようにする設定です。[core/dnsmasq/README.md](../dnsmasq/README.md)
の「2. システムのDNS設定」を参照してください（`/etc/hosts` 編集は不要です）。

## 動作確認

### サーバー側

```bash
# HTTPSで接続テスト
curl -v https://ubuntu.local/health

# 証明書の確認
openssl s_client -connect ubuntu.local:443 -servername ubuntu.local
```

DNS設定がまだの場合は `--resolve` でDNSを経由せず直接確認できます：

```bash
curl -v --resolve ubuntu.local:443:127.0.0.1 https://ubuntu.local/health
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

# 証明書を再生成（リポジトリルートから実行）
rm ssl/ubuntu.local-*.pem
./scripts/generate-cert.sh ubuntu.local

# nginxを再起動
docker compose -f core/compose.yaml restart nginx
```

### ubuntu.localに接続できない

DNS解決の問題は [core/dnsmasq/README.md](../dnsmasq/README.md) の
トラブルシューティングを参照してください。ファイアウォールを使っている場合は
以下のポートを開放してください：

```bash
sudo ufw status
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 53/tcp    # dnsmasq
sudo ufw allow 53/udp    # dnsmasq
```

### Nginxが起動しない

```bash
# ログを確認
docker compose -f core/compose.yaml logs nginx

# 設定ファイルのシンタックスチェック
docker compose -f core/compose.yaml exec nginx nginx -t

# 証明書ファイルのパーミッション確認
ls -la ssl/
```

## セキュリティ注意事項

- **プライベート鍵の保護**: `ubuntu.local-key.pem` は機密情報です。適切に保護してください。
- **LAN内のみ**: この証明書はローカル開発用です。インターネットに公開しないでください。
- **本番環境**: 本番環境ではLet's Encryptなどの公式認証局の証明書を使用してください。

## 参考資料

- [mkcert GitHub](https://github.com/FiloSottile/mkcert)
- [Nginx SSL Configuration](https://nginx.org/en/docs/http/configuring_https_servers.html)
- [core/dnsmasq/README.md](../dnsmasq/README.md) - `*.ubuntu.local` のDNS解決
