# server_base

## 概要

複数の Web アプリケーションを、アプリ側リポジトリを一切改変せずに追加できる
Nginx ベースのサーバー基盤環境。Docker Compose の `include` を使って
server_base を composition root（合成の起点）にし、アプリ側 compose を読み込んで
差分だけを上書きする構成を取る。

背景・設計調査は [docs/catchup/server-onboarding/](docs/catchup/server-onboarding/README.md) を参照。

## 構成

```
server_base/
├── core/                        # 基盤サービス一式 (nginx + dnsmasq)
│   ├── compose.yaml
│   ├── nginx/
│   │   ├── conf.d/
│   │   │   ├── 00-http.conf     # resolver・WebSocket 用 map (http コンテキスト)
│   │   │   ├── snippets/        # ssl.conf / security.conf / proxy.conf
│   │   │   ├── default.conf     # localhost / ubuntu.local ヘルスチェック
│   │   │   └── *.conf           # ← アプリごとの vhost。gen-nginx-conf.py が生成(gitignore対象)
│   │   └── template/site.conf.template
│   ├── dnsmasq/                 # *.ubuntu.local のワイルドカード DNS
│   └── systemd/                 # core スタック全体の systemd ユーザーサービス
├── stacks/                      # アプリごとの override (1 app = 1 ディレクトリ)
│   └── <app名>/docker-compose.yml
├── ssl/                          # mkcert 証明書置き場(core/ の内部構造とは独立、データ専用)
│   └── mkcert-ca/                # ローカルCA(rootCA.pem等)。永続化して使い回す
└── scripts/
    ├── new-app.sh                # stacks/<app名>/docker-compose.yml の雛形生成
    ├── gen-nginx-conf.py         # site.* ラベルから nginx vhost を生成
    ├── render-compose.sh         # core + stacks を include でまとめた compose.generated.yaml を生成
    ├── generate-cert.sh          # mkcert同梱コンテナで ssl/ に証明書を生成(前提はDockerのみ)
    ├── mkcert.Dockerfile
    ├── up.sh                     # conf生成 → up -d → nginx -t && reload
    └── down.sh
```

アプリ側リポジトリは server_base の**兄弟ディレクトリ**にクローンする前提（`include` の
相対パスが固定されるため）:

```
/opt/                                     ← 任意のベースディレクトリ
├── server_base/
└── time-announcement-frontend/           # 改変しない (git clone したまま)
    └── deploy/docker-compose.yaml
```

## 設計の要点

- **アプリごとに専用ネットワーク**（`net-<app名>`）を切る。nginx だけが全網に参加し、
  アプリ同士は相互到達不可（[06-selection.md 6章](docs/catchup/server-onboarding/06-selection.md#6-ネットワーク分離の設計第一候補に組み込む)）
- **Docker socket 不要**。ルーティング定義は `stacks/*/docker-compose.yml` の
  `labels`（`site.host` / `site.upstream` / `site.port`）に置き、
  `scripts/gen-nginx-conf.py` が compose ファイルを読むだけで vhost を生成する
  （[06-selection.md A'](docs/catchup/server-onboarding/06-selection.md#a-nginx--ラベル駆動の生成スクリプト)）
- **`resolver` + 変数 `proxy_pass`** により、1 アプリが落ちていても nginx は
  起動・リロードできる（[03-nginx-modularization.md](docs/catchup/server-onboarding/03-nginx-modularization.md#level-2--resolver--変数-proxy_pass-で起動時依存を断つ)）
- **アプリ側が言及されていないサービスを追加すると `default` ネットワークに分断される**
  問題は、`gen-nginx-conf.py` がエラーで検知する（未然に壊れたまま気づかないことを防ぐ）
- アプリ側 compose 自身が独自の `networks:` を宣言している場合（例: `nature-controler`）、
  素直に override すると連結マージされて元のネットワークにも残ってしまうため、
  `networks: !override` で完全に置き換える（`scripts/new-app.sh` の雛形は常にこの形）
- 生成物の扱い: `core/nginx/conf.d/*.conf`（vhost）は**コミットする**。
  git diff でレビューできるようにするため
  （`compose.generated.yaml` は `stacks/` の一覧そのものなので gitignore）

## 新しいアプリケーションの追加方法

```bash
# 1. アプリを兄弟ディレクトリにクローン（例）
git clone <アプリのgit URL> ../my-app

# 2. stacks/<app名>/docker-compose.yml を生成
./scripts/new-app.sh my-app ../my-app deploy/docker-compose.yaml <サービス名> my-app 3000

# 3. アプリ側 compose に override していないサービス（DB 等）があれば
#    stacks/my-app/docker-compose.yml に追記して net-my-app に載せる

# 4. 起動（conf 生成 → up -d → nginx -t && reload まで一括）
./scripts/up.sh
```

`https://my-app.ubuntu.local/` でアクセスできる。停止は `./scripts/down.sh`。

## サーバーの起動

### 手動

```bash
./scripts/up.sh
```

### systemd（自動起動設定）

```bash
cd core/systemd
chmod +x install-service.sh
./install-service.sh
```

詳細は [core/systemd/README.md](core/systemd/README.md) を参照。

起動するアプリを固定したい場合は `.env` に `COMPOSE_PROFILES` を書く
（`stacks/*/docker-compose.yml` 側で `profiles:` を設定している場合）。

## DNS・TLS

- `*.ubuntu.local` のワイルドカード DNS: [core/dnsmasq/README.md](core/dnsmasq/README.md)
- mkcert によるローカル TLS 証明書: [ssl/README.md](ssl/README.md)

いずれもサブドメインを増やすたびの再設定は不要（ワイルドカード対応済み）。
証明書のワイルドカードは 1 階層のみ有効なので、サブドメインは 1 階層で運用すること。

## ヘルスチェック

```bash
curl http://localhost/health
curl -k https://ubuntu.local/health
```

## 詳細ドキュメント

設計調査の全体像・実測検証・実装 TODO は
[docs/catchup/server-onboarding/](docs/catchup/server-onboarding/README.md) にまとめてある。
