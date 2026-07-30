# サーバー追加を簡単にする — 調査まとめ

- 調査日: 2026-07-30
- 対象リポジトリ: [server_base](https://github.com/macha434/server_base)（このリポジトリ）
- 制約: [time-announcement-frontend](https://github.com/coresync-fukuhara/time-announcement-frontend) を**一切改変しない**こと

## 一行でいうと

**「docker compose をモジュール化したらいい感じになる」という見立ては正しい。**
ただし効くのは `docker-compose.yml` を分割することではなく、**Compose の `include` を使って
server_base 側を "composition root"（合成の起点）にし、アプリ側 compose を読み込んだうえで
差分だけを上書きする**という使い方。これでアプリ側リポジトリは 1 行も触らずに済む。

nginx 設定側にも同じ発想（共通部分の snippet 化）が効くので、両方やると
**アプリ追加＝小さいファイル 2 枚**になる。

## 結論サマリ

### 現状、アプリ追加を面倒にしている要因は 4 つ

| # | ボトルネック | 深刻度 | 解決策 |
| --- | --- | --- | --- |
| B1 | アプリ側 compose に `networks: webnet` を書かないと nginx から到達できない → **アプリ側リポジトリの改変が必須** | 🔴 本件の主問題 | Compose `include` ＋ オーバーライドファイル |
| B2 | nginx の vhost 設定が 1 アプリ約 65 行、うち約 30 行が SSL/ヘッダの定型文コピペ。しかも `template/template.conf` が実運用（`nature.conf`）と乖離していて使えない | 🟡 | nginx `include` で snippet 化、テンプレート刷新 |
| B3 | `upstream { server nature:3001; }` は**設定読み込み時に名前解決する**ため、対象コンテナが落ちていると nginx 自体が起動・リロードできない → アプリを 1 個増やすと既存全部が巻き添えで落ちうる | 🔴 地味に致命的 | `resolver 127.0.0.11` ＋ 変数 `proxy_pass` |
| B4 | アプリ側は `deploy/` ディレクトリで compose を起動するため Compose プロジェクト名が **`deploy`** になる。同じ規約のアプリが 2 つ来ると衝突する。ホストポート（`3000:3000`）も手動採番が必要 | 🟡 | composition root 側で `name:` とポートを制御 |

**すでに解決済みで追加作業が要らない部分**（ここは今の構成が良くできている）:

- **DNS**: dnsmasq が `address=/.ubuntu.local/<IP>` でワイルドカード解決 → サブドメインを増やしても DNS 変更不要
- **TLS**: mkcert 証明書が `*.ubuntu.local` を含む → サブドメインを増やしても証明書の再発行不要

### 推奨する着地点

| フェーズ | 内容 | アプリ追加時の作業量 |
| --- | --- | --- |
| 現状 | 手作業 | アプリ側リポジトリ改変 ＋ nginx conf 65 行 ＋ 手動起動 |
| **Phase 0** | nginx の snippet 化 ＋ `resolver` 化 ＋ テンプレート刷新 | nginx conf **約 15 行**（アプリ側改変はまだ必要） |
| **Phase 1（本命）** | server_base を composition root 化（Compose `include`） | `stacks/<app>.yml` **約 8 行** ＋ nginx conf 約 15 行、**アプリ側改変ゼロ** |
| Phase 2（任意） | nginx → Traefik へ載せ替え | `stacks/<app>.yml` **1 枚のみ**（nginx conf 不要） |

Phase 0 と Phase 1 は独立に導入でき、どちらも既存構成を壊さない。詳細と実ファイル例は
[05-recommendation.md](./05-recommendation.md) を参照。

### ゼロから作り直す場合は → [06-selection.md](./06-selection.md)

「既存の nginx 資産を活かす」制約を外すと結論が変わる。追加調査の要点:

- **アプリ 1 個 = `stacks/` に YAML 1 枚**が Compose の機能だけで成立することを実測で確認
  （1 ファイル内で `include` ＋ 上書きが両立する / シェルで glob 展開して `-f` 列挙）
- したがって残る選択は「**そのラベルを誰が読んでルーティングするか**」だけになる
- 推奨は **nginx ＋ ラベル駆動の生成スクリプト**（Docker socket 不要で 1 ファイル運用を実現）。
  対抗は **Traefik ＋ socket-proxy**
- **Nginx Proxy Manager は除外推奨**（認証済み RCE を含む CVE 実績 ＋ 設定が DB に入り IaC 不可）

## 目次

| 文書 | 内容 |
| --- | --- |
| [01-current-state.md](./01-current-state.md) | 現状構成の棚卸しと、ボトルネック B1〜B4 の根拠 |
| [02-compose-modularization.md](./02-compose-modularization.md) | **本命**。Compose の `include` / `-f` マージ / `extends` / profiles の比較と実測検証 |
| [03-nginx-modularization.md](./03-nginx-modularization.md) | nginx 設定側のモジュール化（snippet / `resolver` / `map` によるワイルドカード vhost）|
| [04-alternatives.md](./04-alternatives.md) | nginx 以外の選択肢（Traefik / Caddy / nginx-proxy / NPM / Coolify / Dokploy / Swarm / k3s）|
| [05-recommendation.md](./05-recommendation.md) | 既存構成を活かす場合の推奨構成・実ファイル例・移行手順 |
| [06-selection.md](./06-selection.md) | **ゼロから作り直す前提**での技術選定（セキュリティ / 設定・導入の簡易さ / キャッチアップ難易度など 12 軸で比較）|
| [07-implementation-todo.md](./07-implementation-todo.md) | 実装 TODO。確定した構成（`core/compose.yaml`・`stacks/<app名>/docker-compose.yml`・生成スクリプト）とフェーズ別チェックリスト |

## 検証環境

本調査の Compose 挙動はドキュメントを読むだけでなく、**実際に `docker compose config` で
マージ結果を出力して確認**した（`config` は Docker デーモン不要でパース・マージのみ行う）。

```
Docker Compose version v5.3.1
Docker version 29.6.2, build dfc4efb
```

再現手順は [02-compose-modularization.md](./02-compose-modularization.md#実測検証) に記載。
