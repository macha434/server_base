# 01. 現状構成の棚卸しとボトルネック

## 1. 現状の全体像

```
                      LAN のクライアント
                             │
                   *.ubuntu.local を問い合わせ
                             ▼
              ┌──────────────────────────────┐
              │ dnsmasq (dnsmasq/)           │  address=/.ubuntu.local/<IP>
              │ container: dnsmasq-ubuntu-…  │  ワイルドカード解決
              └──────────────────────────────┘
                             │ 全部ホストの IP に解決
                             ▼
              ┌──────────────────────────────┐
              │ nginx (nginx/)               │  :80 / :443
              │ container_name: nginx        │  mkcert 証明書 *.ubuntu.local
              │ network: webnet              │
              └──────────────────────────────┘
                             │ conf.d/*.conf の upstream 経由
              ┌──────────────┴──────────────┐
              ▼                             ▼
      ┌───────────────┐            ┌─────────────────────────┐
      │ nature:3001   │            │ 追加したいアプリ          │
      │ (webnet 上)   │            │ schedule-ui:3000         │
      └───────────────┘            │ ← webnet に居ない ✗       │
                                   └─────────────────────────┘
```

構成要素:

| パス | 役割 |
| --- | --- |
| [nginx/docker-compose.yml](../../../nginx/docker-compose.yml) | nginx コンテナ。`:80`/`:443` を公開、`webnet` を**このプロジェクトが作成**する |
| [nginx/conf.d/](../../../nginx/conf.d/) | vhost 設定。`default.conf`（localhost / ubuntu.local）、`nature.conf`（アプリ 1 個目）|
| [nginx/template/template.conf](../../../nginx/template/template.conf) | 新規アプリ用テンプレート |
| [nginx/ssl/generate-cert.sh](../../../nginx/ssl/generate-cert.sh) | mkcert でローカル CA 証明書を生成 |
| [dnsmasq/setup-dns.sh](../../../dnsmasq/setup-dns.sh) | `*.ubuntu.local` を指定 IP に向ける dnsmasq 設定を生成して起動 |

## 2. 追加したいアプリ側の実態

[time-announcement-frontend](https://github.com/coresync-fukuhara/time-announcement-frontend) の
`deploy/docker-compose.yaml`（**改変禁止**）:

```yaml
services:
  schedule-ui:
    build:
      context: ..
      dockerfile: deploy/Dockerfile
    ports:
      - "3000:3000"
    volumes:
      - time-announcement-settings:/data/settings
      - time-announcement-db:/data/db
      - time-announcement-sounds:/app/sounds
    environment:
      - SETTINGS_DIR=/data/settings
      - DB_DIR=/data/db
      - SOUNDS_DIR=/app/sounds
    restart: unless-stopped

volumes:
  time-announcement-settings:
    external: true
  time-announcement-db:
    external: true
  time-announcement-sounds:
    external: true
```

注目すべき性質:

1. **`networks:` の宣言が一切ない** → Compose の暗黙の `default` ネットワーク
   （プロジェクト名 + `_default`）に載る。`webnet` には居ない。
2. **`container_name:` がない** → コンテナ名は `<プロジェクト名>-schedule-ui-1` 。
   ただし Compose は参加した各ネットワークに**サービス名（`schedule-ui`）のエイリアス**を
   自動で付けるため、同じネットワークに居さえすれば `http://schedule-ui:3000` で届く。
3. **`build.context: ..`** → ビルドコンテキストがリポジトリ直下。
   相対パスなので、**どのディレクトリを基準に解決されるかがマージ方式によって変わる**
   （[02](./02-compose-modularization.md) の最重要ポイント）。
4. **named volume が 3 つとも `external: true`** → backend 側リポジトリが作る前提。
   server_base 側で作り直してはいけない。
5. **`ports: "3000:3000"`** → `0.0.0.0:3000` に bind される。nginx/TLS を経由せず
   LAN から直接叩ける状態。

## 3. ボトルネック詳細

### B1 🔴 ネットワーク到達性 — 本件の主問題

nginx が `proxy_pass http://schedule-ui:3000` で届くには、両者が同じ Docker ネットワークに
居る必要がある。素直にやるならアプリ側 compose に以下を足すことになるが、**これがまさに
「やりたくない改変」**:

```yaml
# ← これをアプリ側リポジトリに書きたくない
services:
  schedule-ui:
    networks: [webnet]
networks:
  webnet:
    external: true
```

→ 解決策は [02-compose-modularization.md](./02-compose-modularization.md)。

補足として、`webnet` は現在 [nginx/docker-compose.yml](../../../nginx/docker-compose.yml) が
`external` 指定なしで宣言している＝**nginx プロジェクトの所有物**になっている。
他プロジェクトから `external: true` で参照するには先に nginx を起動しておく必要があり、
起動順序の依存が生まれる。`docker network create webnet` で一度だけ作り、
全プロジェクトから `external: true` で参照する形にした方が疎結合。

### B2 🟡 nginx 設定のコピペ

[nginx/conf.d/nature.conf](../../../nginx/conf.d/nature.conf) は 65 行。うち各アプリで
まったく同じ内容が繰り返されるのは:

- SSL 証明書パス・プロトコル・暗号スイート・セッション設定（約 10 行）
- セキュリティヘッダ 4 種（約 5 行）
- `proxy_set_header` 4 種 ＋ WebSocket 用 3 行（約 8 行）
- HTTP → HTTPS リダイレクトの server ブロック（約 8 行）

= **約 30 行がアプリごとに複製**される。設定を直したくなったら全ファイルを直す羽目になる。

さらに悪いことに、**[nginx/template/template.conf](../../../nginx/template/template.conf) は
実運用と乖離している**:

| 項目 | template.conf | nature.conf（実際の運用）|
| --- | --- | --- |
| プロトコル | HTTP のみ | HTTPS ＋ HTTP リダイレクト |
| ドメイン | `template.localhost` | `nature.ubuntu.local` |
| SSL | なし | あり |
| WebSocket | なし | あり |

README が案内しているテンプレートをコピーしても実運用の形にはならず、
結局 `nature.conf` を見て真似することになる。**テンプレートが機能していない。**

→ 解決策は [03-nginx-modularization.md](./03-nginx-modularization.md)。

### B3 🔴 static upstream による起動時依存

```nginx
upstream nature_backend {
    server nature:3001;   # ← 設定読み込み時に DNS 解決される
}
```

nginx は `upstream` ブロックのホスト名を**設定ロード時**に解決する。解決できないと
`host not found in upstream "nature"` で **nginx プロセス自体が起動しない / リロードに失敗する**。

つまり現状は:

- アプリ A が停止中だと、アプリ B を追加するための `nginx -s reload` が通らない
- ホスト再起動時、アプリコンテナより nginx が先に立ち上がると nginx が起動失敗する
- **アプリを増やすほど「全部同時に生きていないと nginx が動かない」制約が強くなる**

サーバーを気軽に足したいという要望とは真っ向から相反する。
→ 解決策は [03-nginx-modularization.md](./03-nginx-modularization.md#level-2--resolver--変数-proxy_pass-で起動時依存を断つ)。

参考: [How to Fix 'host not found in upstream' Nginx Startup Errors](https://oneuptime.com/blog/post/2025-12-16-fix-host-not-found-in-upstream-nginx/view) /
[nginx proxy pitfalls](https://github.com/DmitryFillo/nginx-proxy-pitfalls)

### B4 🟡 プロジェクト名とホストポートの衝突

Compose のプロジェクト名は、明示しない場合**プロジェクトディレクトリ名**から決まる。
プロジェクトディレクトリは `-f` で指定した最初のファイルのディレクトリなので:

```console
$ docker compose -f deploy/docker-compose.yaml config | head -1
name: deploy
```

（実測。[02 の実測検証 TEST9](./02-compose-modularization.md#実測検証) 参照）

つまりアプリ側の運用手順 `docker compose -f deploy/docker-compose.yaml up -d` を
そのまま使うと、**プロジェクト名は `deploy`**。`deploy/` に compose を置く規約は一般的なので、
2 つ目のアプリが同じ規約だと**プロジェクト名が衝突してコンテナを奪い合う**。

ホストポートも同様で、`3000:3000` は先着順。アプリが増えるたびに空きポートを
人間が管理する必要がある。nginx 経由でアクセスするなら、そもそもホストへの
publish 自体が不要（かつ TLS バイパスの穴になる）。

### 番外: devcontainer との二重起動

[.devcontainer/docker-compose.yml](../../../.devcontainer/docker-compose.yml) も
`webnet` を宣言し、`:80`/`:443` を publish する `nginx-dev` コンテナを持つ。
[nginx/docker-compose.yml](../../../nginx/docker-compose.yml) と同時に起動すると
ポートが衝突する（[.devcontainer/README.md](../../../.devcontainer/README.md) にも注意書きあり）。
composition root を作るなら、この重複も整理対象。

## 4. 「アプリを 1 個追加する」現在の手順

| # | 作業 | 対象 | 改変が必要か |
| --- | --- | --- | --- |
| 1 | DNS レコード追加 | dnsmasq | **不要**（ワイルドカード）✅ |
| 2 | 証明書発行 | nginx/ssl | **不要**（`*.ubuntu.local`）✅ |
| 3 | `networks: [webnet]` 追加 | **アプリ側リポジトリ** | 必要 🔴 B1 |
| 4 | vhost 設定 65 行を作成 | nginx/conf.d | 必要 🟡 B2 |
| 5 | ホストポート採番 | アプリ側 compose | 必要 🟡 B4 |
| 6 | アプリを起動 | アプリ側 | 手動 |
| 7 | nginx をリロード | nginx | 手動・**他アプリが落ちていると失敗** 🔴 B3 |

1 と 2 が既に自動化されているのは大きい。残る 3〜7 を潰しにいく。

> 証明書の注意: mkcert が発行しているのは `ubuntu.local` と `*.ubuntu.local`。
> ワイルドカードは**1 レベルのみ**有効なので、`a.b.ubuntu.local` のような
> 2 段のサブドメインは証明書エラーになる。サブドメインは 1 階層で運用すること。
