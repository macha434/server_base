# server_base

## 概要

このリポジトリは、複数のWebアプリケーションを管理するためのNginxベースのサーバー基盤環境を提供します。Docker Composeを使用してNginxをコンテナとして実行し、リバースプロキシとして各アプリケーションへのルーティングを行います。

## 構成

```
server_base/
├── nginx/
│   ├── conf.d/              # Nginxの設定ファイルを配置
│   │   └── default.conf     # デフォルト設定（ヘルスチェック）
│   ├── template/            # 新規アプリケーション追加用のテンプレート
│   │   └── template.conf    # 設定ファイルのテンプレート
│   ├── systemd/             # systemdサービス設定
│   │   └── user/
│   │       └── nginx-stack.service
│   ├── logs/                # Nginxログファイルの出力先
│   └── docker-compose.yml   # Nginxコンテナの定義
└── README.md
```

## 機能

- **リバースプロキシ**: 複数のアプリケーションを単一のNginxインスタンスで管理
- **ヘルスチェック**: `/health` エンドポイントでサーバーの状態を確認
- **Docker化**: コンテナベースでの簡単なデプロイと管理
- **systemd統合**: システム起動時の自動起動をサポート

## 新しいアプリケーションの追加方法

新しいアプリケーションをNginxに登録する際は、`template/template.conf` をベースに設定ファイルを作成します。

### ステップ1: テンプレートファイルをコピー

リポジトリのルートディレクトリから以下のコマンドを実行します：

```bash
cp nginx/template/template.conf nginx/conf.d/your_app_name.conf
```

### ステップ2: 設定ファイルを編集

`conf.d/your_app_name.conf` を開き、以下の項目を変更します：

```nginx
# アップストリームの名前を変更
upstream your_app_backend {
    # アプリケーションのホスト名とポート番号を指定
    server your_app_container:port_number;
}

server {
    listen 80;
    server_name _;

    # ロケーションのパスを変更
    location /your_app_path {
        proxy_pass http://your_app_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

#### 変更する項目：

1. **upstream名** (`your_app_backend`): アプリケーションを識別する名前に変更
2. **server**: アプリケーションのコンテナ名とポート番号を指定
   - `your_app_container`: Dockerコンテナ名（docker-composeで定義された名前）
   - `port_number`: アプリケーションがリッスンしているポート番号
3. **location**: アプリケーションにアクセスするためのURLパス
   - 例: `/api`, `/admin`, `/app1` など
4. **proxy_pass**: upstreamの名前と一致させる（`http://`を前置）

### ステップ3: Nginxコンテナを再起動

設定ファイルを追加・変更したら、Nginxコンテナを再起動して設定を反映します：

```bash
cd nginx && docker compose restart nginx
```

または、設定ファイルの構文をチェックしてからリロード：

```bash
cd nginx && docker compose exec nginx nginx -t

# 問題がなければリロード
cd nginx && docker compose exec nginx nginx -s reload
```

### 設定例

例えば、`blog`というアプリケーションをポート3001で実行している場合：

```nginx
upstream blog_backend {
    server blog:3001;
}

server {
    listen 80;
    server_name _;

    location /blog {
        proxy_pass http://blog_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

この設定により、`http://your-server/blog` にアクセスすると、`blog`コンテナのポート3001にプロキシされます。

## 注意事項

- アプリケーション自体は別のリポジトリで管理されます
- アプリケーションのDockerコンテナは、Nginxと同じ `webnet` ネットワークに接続する必要があります
- 複数のアプリケーションを追加する場合は、各アプリケーションごとに別々の設定ファイルを作成してください
- `location` のパスが重複しないように注意してください

## サーバーの起動

### Docker Composeを使用

リポジトリのルートディレクトリから以下のコマンドを実行します：

```bash
cd nginx && docker compose up -d
```

### systemdを使用（自動起動設定）

リポジトリのルートディレクトリから以下のコマンドを実行します：

```bash
# サービスファイルをコピー
sudo cp nginx/systemd/user/nginx-stack.service /etc/systemd/system/

# サービスを有効化して起動
sudo systemctl enable nginx-stack.service
sudo systemctl start nginx-stack.service

# ステータス確認
sudo systemctl status nginx-stack.service
```

## ヘルスチェック

サーバーが正常に動作しているか確認：

```bash
curl http://localhost/health
# 出力: OK
```