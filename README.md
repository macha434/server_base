# server_base

自宅サーバー用のリポジトリ (Home Server Repository)

## 概要 (Overview)

このリポジトリは、自宅サーバーの設定と管理を行うためのものです。Docker Composeを使用して、複数のサービスをコンテナとして実行します。

This repository is for configuring and managing a home server. It uses Docker Compose to run multiple services as containers.

## 前提条件 (Prerequisites)

- Docker
- Docker Compose
- Git

## セットアップ (Setup)

1. リポジトリをクローン:
```bash
git clone https://github.com/macha434/server_base.git
cd server_base
```

2. 環境変数ファイルを作成:
```bash
cp .env.example .env
```

3. `.env`ファイルを編集して、必要な設定を行います。

4. サービスを起動:
```bash
./scripts/start.sh
# または
docker-compose up -d
```

## ディレクトリ構成 (Directory Structure)

```
server_base/
├── config/          # 設定ファイル
│   └── nginx/       # Nginx設定
├── scripts/         # 管理スクリプト
├── ssl/             # SSL証明書 (git管理外)
├── logs/            # ログファイル (git管理外)
├── docker-compose.yml
├── .env.example     # 環境変数のサンプル
└── README.md
```

## 管理スクリプト (Management Scripts)

- `./scripts/start.sh` - サービスを起動
- `./scripts/stop.sh` - サービスを停止
- `./scripts/restart.sh` - サービスを再起動

## サービス (Services)

### Nginx
リバースプロキシとして動作し、HTTPSでのアクセスを提供します。

- HTTP: ポート 80
- HTTPS: ポート 443

## SSL証明書 (SSL Certificates)

SSL証明書は`ssl/`ディレクトリに配置してください。Let's Encryptなどを使用して取得できます。

```bash
# Let's Encryptの例
certbot certonly --standalone -d yourdomain.com
```

## カスタマイズ (Customization)

新しいサービスを追加する場合は、`docker-compose.yml`を編集してください。

## ライセンス (License)

MIT