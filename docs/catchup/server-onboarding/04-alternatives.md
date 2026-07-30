# 04. nginx 以外の選択肢

「サーバーを簡単に追加する」を目的にした場合、nginx を手で書く以外の道も広く調べた。

## 0. 比較表

| 選択肢 | 設定の与え方 | アプリ側リポジトリ改変 | TLS | 学習/移行コスト | 今回の適合度 |
| --- | --- | --- | --- | --- | --- |
| **nginx（現状 ＋ [03](./03-nginx-modularization.md)）** | conf ファイル | 不要（[02](./02-compose-modularization.md) の override 併用）| mkcert 手動 | ゼロ（既存資産）| ⭐⭐⭐⭐ |
| **Traefik** | Docker ラベル / ファイルプロバイダ | 不要（override でラベル注入）| ACME 自動（内部 DNS では要 DNS-01）| 中 | ⭐⭐⭐⭐ |
| **Caddy ＋ caddy-docker-proxy** | Docker ラベル | 不要（同上）| 自動 | 中 | ⭐⭐⭐ |
| **nginx-proxy（docker-gen）** | 環境変数 `VIRTUAL_HOST` | 不要（override で env 注入）| companion で自動 | 低 | ⭐⭐⭐ |
| **Nginx Proxy Manager** | Web GUI | 不要 | GUI から Let's Encrypt | 低 | ⭐⭐⭐ |
| **Coolify / Dokploy** | Web UI ＋ Git 連携 | 不要 | 自動 | 高（母屋の建て替え）| ⭐⭐ |
| **Docker Swarm** | Compose 互換 stack | 不要 | 別途 | 中 | ⭐ |
| **k3s** | Kubernetes マニフェスト | 不要（別途 manifest）| cert-manager | 非常に高 | ⭐ |

## 1. Traefik — ラベル駆動の自動検出

Docker ソケットを監視し、コンテナのラベルからルーティングを自動構成する。
コンテナが起動した瞬間にルートが生える。

```yaml
labels:
  traefik.enable: "true"
  traefik.http.routers.ta.rule: "Host(`time.ubuntu.local`)"
  traefik.http.routers.ta.tls: "true"
  traefik.http.services.ta.loadbalancer.server.port: "3000"
```

### 「ラベルはアプリ側 compose に書くもの」問題は回避できる

一般に Traefik は「アプリの compose にラベルを書く」前提なので、今回の制約
（アプリ側無改変）と相性が悪いと思われがち。**しかし [02 の TEST10](./02-compose-modularization.md#test10--ラベル注入--reset-でポート剥がし-) で
実測した通り、`include` のオーバーライドファイル経由でラベルを注入できる。**
つまり:

```
server_base/stacks/time-announcement.yml   ← このファイル 1 枚だけで完結
  ├─ networks.default を webnet に
  ├─ ports を !reset で剥がす
  └─ traefik.* ラベルを注入
```

**nginx conf を書く必要が消えて、アプリ追加＝ファイル 1 枚**になる。これが最短形。

### もう一つの道 — ファイルプロバイダ

ラベルを使わず、Traefik 側の動的設定ファイルでルーティングを定義することもできる。

> Using only the file provider to define routers, middleware and services helps reduce
> labels and brings extra features like swapping different host names to different
> services dynamically without the need of restarting your container.

`dynamic/time-announcement.yml`:

```yaml
http:
  routers:
    time-announcement:
      rule: "Host(`time.ubuntu.local`)"
      service: time-announcement
      tls: {}
  services:
    time-announcement:
      loadBalancer:
        servers:
          - url: "http://schedule-ui:3000"
```

ファイルプロバイダは**ディレクトリ監視 ＋ ホットリロード**に対応するので、
ファイルを置くだけで反映される（nginx の reload に相当する操作が不要）。
ラベル方式とハイブリッドで併用もできる。

ただし今回はどのみち Compose のオーバーライドファイルを 1 枚置く必要があるので、
**ラベル注入方式の方がファイル数が少なくて済む**（ファイルプロバイダだと
「override 1 枚 ＋ 動的設定 1 枚」で 2 枚になる）。

### TLS の注意

`.local` ドメインは Let's Encrypt の HTTP-01 / TLS-ALPN-01 チャレンジが使えない
（外部から到達できない・公的 TLD ではない）。現行の mkcert 証明書をそのまま
Traefik に食わせる形になる:

```yaml
# dynamic/tls.yml
tls:
  stores:
    default:
      defaultCertificate:
        certFile: /etc/certs/ubuntu.local-cert.pem
        keyFile:  /etc/certs/ubuntu.local-key.pem
```

**既存の mkcert 資産はそのまま流用できる**ので、TLS 面での移行コストは低い。

### デメリット

- Docker ソケットを Traefik に渡すことになる（`/var/run/docker.sock:ro`）。
  実質 root 相当の権限なので、家庭内 LAN とはいえ理解して使うこと。
  socket-proxy を挟む緩和策もある。
- 設定のデバッグが nginx より難しい（ラベルのタイポが黙って無視される）。
  ダッシュボード（`:8080`）で確認する運用になる。
- 生 RPS は nginx より劣る。ただし家庭内 LAN の規模では体感差なし
  （「for a typical homelab with under 100 concurrent connections, performance
  differences between these proxies are imperceptible」）。

参考:
[Providing Dynamic Configuration to Traefik](https://doc.traefik.io/traefik/reference/routing-configuration/dynamic-configuration-methods/) /
[Traefik Providers Overview](https://doc.traefik.io/traefik/reference/install-configuration/providers/overview/) /
[HTTP routing with Traefik | Docker Docs](https://docs.docker.com/guides/traefik/) /
[Understand File Provider in Traefik 2](https://tech.aufomm.com/understand-file-provider-in-traefik-2/)

## 2. Caddy ＋ caddy-docker-proxy

Caddy 本体は Caddyfile が非常に簡潔で、`*.ubuntu.local` のワイルドカードも数行で書ける。
`caddy-docker-proxy` プラグインを入れると Traefik と同じくラベル駆動になる。

**評価**: 設定の読みやすさは随一だが、今回は
「既に nginx で動いていて、mkcert 証明書と dnsmasq が噛み合っている」状態。
Caddy の最大の売りである**自動 HTTPS が `.local` では活きない**ため、
乗り換えの動機が弱い。ゼロから作るなら有力候補。

## 3. nginx-proxy（jwilder/docker-gen 系）

コンテナの `VIRTUAL_HOST` 環境変数を見て nginx の設定を自動生成する老舗。

```yaml
environment:
  - VIRTUAL_HOST=time.ubuntu.local
  - VIRTUAL_PORT=3000
```

環境変数もオーバーライドファイルから注入できるので、アプリ側改変は不要。
**nginx をそのまま使い続けられる**のが利点で、既存資産との連続性が高い。

**評価**: Traefik ほど柔軟ではないが、「nginx を捨てたくないが自動化はしたい」という
中間解として現実的。`acme-companion` と組む前提の設計なので `.local` 環境では
証明書まわりを手動で組む必要がある。

## 4. Nginx Proxy Manager（NPM）

nginx ＋ Web GUI ＋ Let's Encrypt 自動化。

> Nginx Proxy Manager is a web GUI and automatic Let's Encrypt layer built on top of
> the same Nginx engine. You get the power of Nginx without hand-editing config files.

**評価**: GUI でポチポチ追加できるので「簡単に追加」という要望には最も直感的に応える。
ただし:

- 設定が**GUI/DB の中**に入るので、Git 管理・コードレビュー・再現性が失われる。
  現在のリポジトリ駆動の運用思想（server_base を Git で管理している）と衝突する。
- `.local` では Let's Encrypt 自動化という主要機能が使えない。

Infrastructure as Code を維持したいなら不適。

## 5. Coolify / Dokploy — セルフホスト PaaS

Docker を UI で包み、Git 連携 ＋ Traefik ＋ Let's Encrypt を丸ごと面倒見る。

- **Coolify** v4.0.0 stable（2026-04-27 リリース）。Apache 2.0。
  ワンクリックアプリのライブラリが大きく、ARM64 / Raspberry Pi 対応。
  「New Resource → Docker Compose」に compose を貼ると管理サービスとして起動し、
  **自前のネットワークとプロキシラベルを注入する**（＝今回やろうとしていることを
  プラットフォームがやってくれる）。
- **Dokploy** v0.29.4（2026-05-11）。
  「If you already have Compose files, Dokploy deploys them as-is rather than
  wrapping them in its own abstraction」＝既存 compose をそのまま扱う思想。
  アイドル時のオーバーヘッドが低く、マルチサーバー対応。

**評価**: やりたいこと（アプリ追加の摩擦をゼロにする）に対しては**最も完成度が高い**。
ただし server_base という自作基盤を丸ごと置き換える判断になるので、
今回のスコープ（server_base を修正する）とはズレる。

将来的にアプリが 5〜10 個規模になり、自作基盤の維持コストが上回るようなら
**Dokploy**（既存 compose をそのまま扱えるので移行が素直）への移行を検討する価値あり。

参考:
[Coolify vs Dokploy: Self-Hosted PaaS Compared](https://cloudzy.com/blog/coolify-vs-dokploy/) /
[Coolify vs Dokploy: Which Self-Hosted PaaS for Your VPS?](https://www.virtua.cloud/learn/en/concepts/coolify-vs-dokploy-self-hosted-paas) /
[Coolify Self-Hosted PaaS — Setup, Domains, and Power-User Cheats](https://blog.diengdoh.com/coolify-self-hosted-paas/)

## 6. Docker Swarm / k3s

- **Swarm**: Compose 互換の stack ファイルで複数ノードに展開できる。ただし
  `extends` 非対応、`build` 非対応（イメージを事前ビルド・push する必要がある）。
  今回のアプリは `build.context` を使っているので、CI でのイメージビルドが前提になる。
  単一ホスト運用ではメリットが薄い。
- **k3s**: 軽量 Kubernetes。Ingress で宣言的にルーティングでき、cert-manager で
  証明書も自動化できる。ただしアプリごとに Deployment / Service / Ingress の
  manifest を書く必要があり、**compose ファイルの再利用ができない**
  （＝アプリ側リポジトリと別に manifest を書く手間が発生）。
  単一ホストの家庭内サーバーには過剰。

**評価**: どちらも「アプリ追加を簡単にする」という目的に対しては逆にコストが増える。
今回は対象外。

## まとめ

- **[02](./02-compose-modularization.md) の override テクニックが効くので、
  ラベル/環境変数駆動のプロキシ（Traefik / Caddy / nginx-proxy）も
  「アプリ側リポジトリ無改変」の制約を満たせる。** ここが今回の調査で一番の発見。
- とはいえ nginx ＋ [03](./03-nginx-modularization.md) の改善で
  1 アプリ 22 行まで落ちるので、**まず nginx を改善し、それでも面倒なら Traefik**
  という順序が投資対効果が高い。
- GUI 系（NPM）は Git 管理との相性が悪い。PaaS 系（Coolify / Dokploy）は
  完成度は高いが基盤の建て替えになる。アプリが増えて自作維持がつらくなった時点で再検討。
- `.local` ドメインを使う限り Let's Encrypt 自動化の恩恵は受けられないので、
  「自動 HTTPS」を売りにするツールの魅力は目減りする。既存 mkcert 資産は
  どのプロキシでもそのまま使える。

## 参考

- [Traefik vs Caddy vs nginx Proxy Manager — Which Reverse Proxy Should You Choose in 2026?](https://selfhostwise.com/posts/traefik-vs-caddy-vs-nginx-proxy-manager-which-reverse-proxy-should-you-choose-in-2026/)
- [Nginx Proxy Manager vs Caddy vs Traefik: Homelab Comparison (2026)](https://homelabaddiction.com/nginx-proxy-manager-vs-caddy-vs-traefik/)
- [Homelab Reverse Proxy Showdown](https://homelabstarter.com/homelab-reverse-proxy-comparison/)
- [Caddy vs Nginx Proxy Manager vs Traefik: 2026 VPS Guide](https://hyehost.org/blog/caddy-vs-nginx-proxy-manager-vs-traefik)
