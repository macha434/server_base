# Dev Container セットアップ

## 使い方

### 1. Dev Containerで開く

1. VS Codeでこのフォルダを開く
2. コマンドパレット（Ctrl+Shift+P）を開く
3. "Dev Containers: Reopen in Container" を選択

### 2. Nginxを起動

Dev Container内のターミナルで以下を実行：

```bash
cd /workspace/nginx
docker compose up -d
```

### 3. 動作確認

```bash
# ヘルスチェック
curl http://localhost/health

# natureアプリ（外部で起動している場合）
curl http://nature.localhost/
```

## 開発環境の構成

```
.devcontainer/
├── devcontainer.json       # Dev Container設定
└── docker-compose.yml      # 開発環境用コンテナ構成

nginx/
├── conf.d/                 # Nginx設定ファイル
├── logs/                   # ログ出力先
├── ssl/                    # SSL証明書（オプション）
└── docker-compose.yml      # Nginx本体のdocker-compose
```

## ネットワーク

- Dev Container: `devnet` ネットワーク
- 外部アプリケーション: `webnet` ネットワーク（nginx/docker-compose.yml）

外部で起動するアプリケーションコンテナは `webnet` ネットワークに接続してください。

## 便利なコマンド

```bash
# Nginxの再起動
cd /workspace/nginx && docker compose restart nginx

# Nginx設定のテスト
docker exec nginx-dev nginx -t

# Nginxログの確認
tail -f /workspace/nginx/logs/access.log
tail -f /workspace/nginx/logs/error.log
```

## トラブルシューティング

### ポートが既に使用されている

Dev Containerを開く前に、ホスト側のNginxを停止してください：

```bash
# ホスト側で実行
cd nginx
docker compose down
```

### アプリケーションコンテナに接続できない

外部のアプリケーションコンテナが `webnet` ネットワークに接続されているか確認：

```bash
docker network inspect webnet
```
