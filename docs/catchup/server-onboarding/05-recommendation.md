# 05. 推奨構成と移行手順

[01](./01-current-state.md)〜[04](./04-alternatives.md) の調査を踏まえた具体案。
**Phase 0 と Phase 1 は独立しており、どちらから着手してもよい。**
どちらも既存の動作を壊さず段階導入できる。

## 目標とする「アプリ追加手順」

```bash
# 1. アプリを兄弟ディレクトリにクローン
git clone https://github.com/coresync-fukuhara/time-announcement-frontend ../

# 2. オーバーライドを 1 枚書く (8 行)
vim stacks/time-announcement.yml

# 3. nginx の vhost を 1 枚書く (22 行、テンプレートから sed で生成可)
./scripts/add-site.sh time schedule-ui 3000

# 4. compose.yaml に include を 4 行追加して起動
docker compose --profile time-announcement up -d
docker compose exec nginx nginx -s reload
```

**アプリ側リポジトリの改変はゼロ。**

---

## Phase 0 — nginx 設定の整理（追加依存なし・即効）

### 0-1. snippet 化

```
nginx/conf.d/
├── 00-http.conf          # 新規: resolver / map をまとめる (http コンテキスト)
├── snippets/             # 新規: サブディレクトリなので conf.d/*.conf の glob に拾われない
│   ├── ssl.conf
│   ├── security.conf
│   └── proxy.conf
├── default.conf
├── nature.conf
└── time-announcement.conf
```

`nginx/conf.d/00-http.conf`:

```nginx
# Docker 埋め込み DNS。ipv6=off がないと解決に失敗しやすい
resolver 127.0.0.11 valid=10s ipv6=off;

# WebSocket の Connection ヘッダを正しく振り分ける
map $http_upgrade $connection_upgrade {
    default upgrade;
    ''      close;
}
```

snippet 3 枚の中身は [03-nginx-modularization.md](./03-nginx-modularization.md#level-1--include-で共通部分を-snippet-化) を参照。

### 0-2. `resolver` ＋ 変数 `proxy_pass` へ移行

**これが Phase 0 の本命。** 各 vhost の `upstream` ブロックを廃止し:

```nginx
location / {
    set $upstream http://schedule-ui:3000;
    proxy_pass $upstream;
    include snippets/proxy.conf;
}
```

効果: **アプリが 1 個落ちていても nginx が起動・リロードできる**
（[B3](./01-current-state.md#b3--static-upstream-による起動時依存) の解消）。
アプリを増やす作業が既存アプリを巻き添えにしなくなる。

> `location /` 以外（`/api/` など）で使う場合は、変数 `proxy_pass` が
> プレフィックス除去をしない点に注意。[03 の落とし穴](./03-nginx-modularization.md#落とし穴) 参照。

### 0-3. テンプレートを実運用に合わせる

現在の `nginx/template/template.conf` は HTTP のみ・`.localhost` で、
実運用（`nature.conf`）と乖離していて使えない（[B2](./01-current-state.md#b2--nginx-設定のコピペ)）。
Phase 0 適用後の形に差し替える:

`nginx/template/site.conf.template`:

```nginx
server {
    listen      443 ssl;
    listen [::]:443 ssl;
    http2 on;
    server_name __SUBDOMAIN__.ubuntu.local;

    include snippets/ssl.conf;
    include snippets/security.conf;

    location / {
        set $upstream http://__SERVICE__:__PORT__;
        proxy_pass $upstream;
        include snippets/proxy.conf;
    }
}

server {
    listen      80;
    listen [::]:80;
    server_name __SUBDOMAIN__.ubuntu.local;
    return 301 https://$host$request_uri;
}
```

`scripts/add-site.sh`:

```bash
#!/usr/bin/env bash
# 使い方: ./scripts/add-site.sh <サブドメイン> <compose のサービス名> <ポート>
set -euo pipefail

[ $# -eq 3 ] || { echo "usage: $0 <subdomain> <service> <port>" >&2; exit 1; }
SUBDOMAIN=$1 SERVICE=$2 PORT=$3
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/nginx/conf.d/${SUBDOMAIN}.conf"

[ -e "$OUT" ] && { echo "既に存在します: $OUT" >&2; exit 1; }

sed -e "s|__SUBDOMAIN__|${SUBDOMAIN}|g" \
    -e "s|__SERVICE__|${SERVICE}|g" \
    -e "s|__PORT__|${PORT}|g" \
    "$ROOT/nginx/template/site.conf.template" > "$OUT"

echo "生成しました: $OUT"
echo "反映するには: docker compose exec nginx nginx -t && docker compose exec nginx nginx -s reload"
```

### 0-4. 旧記法の修正（ついで）

`listen 443 ssl http2;` は nginx 1.25.1 で deprecated。
`listen 443 ssl;` ＋ `http2 on;` に直す。

---

## Phase 1 — server_base を composition root にする（本命）

### 1-1. ディレクトリ構成

サーバー上の配置（アプリを**兄弟ディレクトリ**に置く前提）:

```
/opt/                                     ← 任意のベースディレクトリ
├── server_base/
│   ├── compose.yaml                      # 新規: composition root
│   ├── stacks/                           # 新規: アプリごとのオーバーライド
│   │   ├── README.md
│   │   └── time-announcement.yml
│   ├── scripts/add-site.sh               # 新規
│   ├── nginx/
│   └── dnsmasq/
└── time-announcement-frontend/           # 改変しない (git clone したまま)
    └── deploy/docker-compose.yaml
```

> `include` の `path` は相対パスなので、**server_base とアプリの相対位置が
> 固定されている**必要がある。README に配置規約として明記すること。
> 位置を可変にしたい場合は `${APPS_DIR}/time-announcement-frontend/...` のように
> 変数補間して `.env` で与える手もある。

### 1-2. `webnet` を external 化

現在 `nginx/docker-compose.yml` が `webnet` を所有しているため、
他プロジェクトが `external: true` で参照するには nginx を先に上げる必要がある
（起動順序の依存）。一度だけ手で作って、全員が external 参照する形にする。

```bash
docker network create webnet
```

`nginx/docker-compose.yml` の変更:

```diff
 networks:
   webnet:
     name: webnet
-    driver: bridge
+    external: true
```

### 1-3. アプリ用オーバーライド

`stacks/time-announcement.yml`（**これが「サーバーを 1 個足す」の実体**）:

```yaml
# time-announcement-frontend を server_base 配下で動かすための差分。
# アプリ側リポジトリ (coresync-fukuhara/time-announcement-frontend) は改変しない。
services:
  schedule-ui:
    # nginx から http://schedule-ui:3000 で到達できるようにする
    networks: [webnet]
    # ホストへの publish を取り消す (nginx/TLS 経由のみに強制、ポート採番も不要に)
    ports: !reset []
    # 個別に起動/停止できるようにする
    profiles: [time-announcement]

networks:
  webnet:
    name: webnet
    external: true
```

> ⚠️ ここで `networks.default` を差し替える書き方をしてはいけない。
> プロジェクト全体の既定ネットワークが変わり、dnsmasq まで `webnet` に載る。
> 実測済み → [02 TEST11](./02-compose-modularization.md#test11--default-差し替えの漏れと安全な書き方-)

### 1-4. composition root

`compose.yaml`:

```yaml
name: server-base

include:
  # --- 基盤 ---
  - path: ./nginx/docker-compose.yml
  - path: ./dnsmasq/docker-compose.yml

  # --- アプリ ---
  # アプリを足すときはこのブロックを 4 行コピーするだけ
  - path:
      - ../time-announcement-frontend/deploy/docker-compose.yaml
      - ./stacks/time-announcement.yml
    project_directory: ../time-announcement-frontend/deploy
```

### 1-5. 検証済みのマージ結果

上記構成を**実リポジトリのファイルで** `docker compose config` にかけて確認済み:

| 確認項目 | 結果 |
| --- | --- |
| `build.context` がアプリリポジトリのルートを指す | ✅ |
| external volume 3 つがそのまま引き継がれる | ✅ 再宣言不要 |
| `schedule-ui` と `nginx` が `webnet` に載る | ✅ |
| `dnsmasq` は `server-base_default` のまま隔離される | ✅ |
| `ports: 3000:3000` が消える | ✅ `!reset` |
| profile 未指定なら `schedule-ui` が対象外になる | ✅ |
| `webnet` のキー重複でエラーにならない | ✅ Compose v5.3.1 |

### 1-6. 運用コマンド

```bash
cd /opt/server_base

# 基盤のみ起動
docker compose up -d

# アプリも含めて起動
docker compose --profile time-announcement up -d

# アプリだけ再ビルド・再起動
docker compose --profile time-announcement up -d --build schedule-ui

# nginx 設定の反映 (Phase 0 適用後は他アプリが落ちていても通る)
docker compose exec nginx nginx -t && docker compose exec nginx nginx -s reload

# 何がマージされるかの事前確認 (デーモン不要・破壊的操作なし)
docker compose --profile time-announcement config
```

`COMPOSE_PROFILES` を `.env` に書けば `--profile` の指定を省ける:

```dotenv
COMPOSE_PROFILES=time-announcement,nature
```

### 1-7. systemd

既存の [dnsmasq/systemd/](../../../dnsmasq/systemd/) と同じ要領で、
composition root を 1 つの unit にまとめられる（サービスごとの unit が不要になる）:

```ini
[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/server_base
ExecStart=/usr/bin/docker compose up -d
ExecStop=/usr/bin/docker compose down
```

`COMPOSE_PROFILES` を `.env` に書いておけば、この unit だけで全アプリが起動する。

---

## Phase 2（任意）— Traefik へ載せ替えて nginx conf も消す

Phase 1 まで来ていれば、Traefik への移行は
**`stacks/<app>.yml` にラベルを足して nginx conf を捨てるだけ**で済む。

```yaml
# stacks/time-announcement.yml
services:
  schedule-ui:
    networks: [webnet]
    ports: !reset []
    profiles: [time-announcement]
    labels:
      traefik.enable: "true"
      traefik.http.routers.ta.rule: "Host(`time.ubuntu.local`)"
      traefik.http.routers.ta.tls: "true"
      traefik.http.services.ta.loadbalancer.server.port: "3000"

networks:
  webnet: { name: webnet, external: true }
```

これで **アプリ追加＝ファイル 1 枚**。既存の mkcert 証明書は
`defaultCertificate` としてそのまま流用できる（[04](./04-alternatives.md#tls-の注意) 参照）。

**ただし急ぐ必要はない。** Phase 0 + 1 の時点で nginx conf は 22 行・
可変部分 2 行まで落ちており、Traefik 導入で減るのは「ファイル 1 枚」。
それと引き換えに Docker ソケットの露出とデバッグの難しさを負う。
アプリが 5 個を超えて手作業が本当に苦になってから判断すればよい。

---

## 併せて直したい既存の課題

| 項目 | 内容 |
| --- | --- |
| devcontainer との二重起動 | [.devcontainer/docker-compose.yml](../../../.devcontainer/docker-compose.yml) の `nginx-dev` が `:80`/`:443` を publish しており、`nginx/docker-compose.yml` と衝突する。composition root に一本化するなら devcontainer 側から nginx を外すのが素直 |
| dnsmasq README の古い記述 | `docker-compose`（ハイフンあり）表記が残っている。また「全て `192.168.3.17` に解決されれば成功」と書かれているが、IP は `setup-dns.sh` の引数で決まる |
| dnsmasq README の壊れた文 | 「これにより`dnsmasq.conf`が再生成され、コンテナが再起動されます。は再起動：」— 編集ミスが残っている |
| systemd unit のパス | `dnsmasq/systemd/dnsmasq-ubuntu-local.service` の `WorkingDirectory=/opt/server_base/dnsmasq` がハードコード。composition root 化の際に整理 |
| ルート README | Phase 0/1 適用後の手順に全面的に書き直しが必要。現在の「テンプレートをコピーして 4 箇所編集」は実態と合っていない |
| サービス名の衝突 | `webnet` 上ではサービス名がネットワークエイリアスになる。今後 `web` / `app` のような一般名のサービスを持つアプリが来ると解決先が曖昧になる。`stacks/` の README に命名規約（アプリ名を含めること、必要なら override で `container_name` や `aliases` を指定）を書いておく |

---

## やらないほうがいいこと

| 案 | 理由 |
| --- | --- |
| `docker network connect` で後から繋ぐ | コンテナ再作成で消える。恒久運用に耐えない |
| `extends` でアプリを取り込む | external volume 3 つを server_base 側に再宣言する必要があり、アプリ側の変更に追従し続けることになる（[02 TEST7](./02-compose-modularization.md#test6--test7--extends)）|
| `-f` 複数指定で server_base 側を先頭にする | `build.context: ..` が壊れる（[02 TEST5](./02-compose-modularization.md#test5---f-マージの順序ミス--パスが壊れる)）|
| Nginx Proxy Manager の GUI に移行 | 設定が DB に入り Git 管理・再現性が失われる。現在のリポジトリ駆動の運用と衝突 |
| いきなり k3s / Swarm | アプリ側 compose を再利用できず、manifest を別途書く手間が増える。単一ホストには過剰 |

---

## 実施順の提案

1. **Phase 0-2（`resolver` 化）** — 一番効くわりに変更が小さい。
   これだけで「アプリ追加が既存を巻き添えにする」問題が消える
2. **Phase 0-1 / 0-3 / 0-4（snippet 化・テンプレート刷新）** — 65 行 → 22 行
3. **Phase 1（composition root）** — アプリ側リポジトリ無改変を達成
4. ルート README の全面改訂
5. （必要になったら）Phase 2 or Dokploy 移行を検討
