# server-base-core

## 概要

複数の Web アプリケーションを、アプリ側リポジトリを一切改変せずに追加できる
Nginx ベースのサーバー基盤環境。Docker Compose の `include` を使って
server-base-core を composition root（合成の起点）にし、アプリ側 compose を読み込んで
差分だけを上書きする構成を取る。

背景・設計調査は [docs/catchup/server-onboarding/](docs/catchup/server-onboarding/README.md) を参照。

## 構成

```
server-base-core/
├── core/                        # 基盤サービス一式 (nginx + dnsmasq)
│   ├── compose.yaml
│   ├── nginx/
│   │   ├── conf.d/
│   │   │   ├── 00-http.conf     # resolver・WebSocket 用 map (http コンテキスト)
│   │   │   ├── snippets/        # ssl.conf / security.conf / proxy.conf
│   │   │   ├── default.conf     # localhost / ubuntu.local ヘルスチェック
│   │   │   └── *.conf           # ← アプリごとの vhost。gen-nginx-conf.py が生成(gitignore対象)
│   │   ├── template/site.conf.template
│   │   └── README.md            # ubuntu.localをHTTPSで公開する手順
│   ├── dnsmasq/                 # *.ubuntu.local のワイルドカード DNS
│   └── systemd/                 # core スタック全体の systemd ユーザーサービス
├── stacks/                      # アプリごとの override (1 app = 1 ディレクトリ)
│   └── <app名>/docker-compose.yml
├── ssl/                          # mkcert 証明書置き場(core/ の内部構造とは独立、データ専用)
│   └── mkcert-ca/                # ローカルCA(rootCA.pem等)。永続化して使い回す
└── scripts/
    ├── README.md                 # 各スクリプトの一覧
    ├── new-app.sh                # stacks/<app名>/docker-compose.yml の雛形生成
    ├── server-base                # 統合CLI本体(init/service/app/status/logs/restart/doctor/cert)
    ├── server_base_cli/           # ↑の実装パッケージ
    ├── install-cli.sh             # server-baseを~/.local/binにインストール
    ├── uninstall-cli.sh           # 上記の解除
    ├── gen-nginx-conf.py         # site.* ラベルから nginx vhost を生成
    ├── render-compose.sh         # core + stacks を include でまとめた compose.generated.yaml を生成
    ├── generate-cert.sh          # mkcert同梱コンテナで ssl/ に証明書を生成(前提はDockerのみ)
    ├── mkcert.Dockerfile
    ├── setup-dns.sh              # core/dnsmasq/ の *.ubuntu.local ワイルドカードDNSをセットアップ
    ├── install-service.sh        # core/systemd/core-stack.service をsystemdユーザーサービスとして登録
    ├── uninstall-service.sh
    ├── up.sh                     # conf生成 → up -d → nginx -t && reload
    └── down.sh
```

アプリ側リポジトリは server-base-core の**兄弟ディレクトリ**にクローンする前提（`include` の
相対パスが固定されるため）:

```
/opt/                                     ← 任意のベースディレクトリ
├── server-base-core/
└── my-app/                               # 改変しない (git clone したまま)
    └── deploy/docker-compose.yaml
```

`stacks/*/docker-compose.yml` はサーバーインスタンスごとに異なる設定なので
gitignore 対象（詳細は [stacks/README.md](stacks/README.md)）。clone した直後は
`stacks/` は空で、`./scripts/up.sh` は core（nginx・dnsmasq）だけを起動する。
アプリは「新しいアプリケーションの追加方法」の手順で追加していく。

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
- アプリ側 compose 自身が独自の `networks:` を宣言している場合、
  素直に override すると連結マージされて元のネットワークにも残ってしまうため、
  `networks: !override` で完全に置き換える（`scripts/new-app.sh` の雛形は常にこの形）
- 生成物の扱い: `core/nginx/conf.d/*.ubuntu.local.conf`（vhost）・`compose.generated.yaml` は
  どちらも `stacks/*/docker-compose.yml` から都度再生成できるため gitignore（コミット不要）

## 初回セットアップ（サーバーの立ち上げ）

前提: Docker・Docker Compose がインストールされていること。

```bash
# 1. server-base-core をクローン
git clone <server-base-coreのURL> server-base-core
cd server-base-core

# 2. *.ubuntu.local のワイルドカードDNSを起動（IPアドレスは省略するとLAN IPを自動検出する）
./scripts/setup-dns.sh

# 3. TLS証明書を生成（前提はDockerのみ。mkcertのホストインストールは不要）
./scripts/generate-cert.sh ubuntu.local

# 4. core(nginx・dnsmasq)を起動（この時点でアプリはまだ無い。conf生成 → up -d → nginx -t && reload）
./scripts/up.sh
```

続けて以下も設定する:

- **クライアント側のDNS設定**: [core/dnsmasq/README.md](core/dnsmasq/README.md) の
  「2. システムのDNS設定」を参照（`/etc/hosts` 編集は不要）
- **クライアント側の証明書信頼設定**: [core/nginx/README.md](core/nginx/README.md) の
  「3. 証明書の信頼設定」を参照
- **ログイン時の自動起動**（任意）: systemd ユーザーサービスとして登録する

  ```bash
  ./scripts/install-service.sh
  ```

  詳細は [core/systemd/README.md](core/systemd/README.md) を参照。

動作確認（アプリはまだ無いので `core/nginx/conf.d/default.conf` のヘルスチェックのみ）:

```bash
curl http://localhost/health
curl -k https://ubuntu.local/health
```

証明書エラーが出ずにアクセスできれば完了。続けて「新しいアプリケーションの
追加方法」でアプリを追加する。停止は `./scripts/down.sh`。

## 新しいアプリケーションの追加方法

`new-app.sh` はアプリ側リポジトリのURLだけで動く。サブドメイン・ポート番号・compose
ファイルの場所は、アプリ側composeの対象サービスに付与された `labels` から自動検出する
（規約の詳細は [docs/superpowers/specs/2026-09-12-app-compose-convention-design.md](docs/superpowers/specs/2026-09-12-app-compose-convention-design.md)）。

```bash
# 1. アプリ側リポジトリ(の対象サービス)に labels を付与しておく(devcontainerを
#    使っているなら、この規約はClaude Codeスキル経由で自動的に反映される想定。
#    手動で書く場合は以下のように追記する)
#      labels:
#        site.port: "3000"        # 必須: コンテナ内でリッスンしているポート
#        site.subdomain: "my-app" # 任意: 省略時はリポジトリ名を使う

# 2. stacks/<app名>/docker-compose.yml を生成(../my-app に未cloneなら自動clone)
./scripts/new-app.sh <アプリのgit URL>

# 3. アプリ側 compose に override していないサービス（DB 等）があれば
#    stacks/my-app/docker-compose.yml に追記して net-my-app に載せる

# 4. 起動（conf生成 → core → アプリ → nginx -t && reload まで一括）
./scripts/up.sh
```

`https://my-app.ubuntu.local/` でアクセスできる（サブドメインは `site.subdomain` ラベルか
リポジトリ名）。停止は `./scripts/down.sh`。

compose ファイルの場所・サービス名・サブドメイン・ポート番号は、それぞれ
`--compose-file` / `--service` / `--subdomain` / `--port` で個別に上書きできる
（`./scripts/new-app.sh --help` 参照）。

### 具体例（time-announcement-frontend）

`deploy/docker-compose.yaml` の `schedule-ui` サービスに `site.port: "3000"` ラベルが
付与済みなら、以下だけで追加できる:

```bash
./scripts/new-app.sh https://github.com/coresync-fukuhara/time-announcement-frontend
./scripts/up.sh
```

サブドメインは `site.subdomain` ラベルが無ければリポジトリ名(`time-announcement-frontend`)に
なるので、`time` にしたい場合は `--subdomain time` を付ける:

```bash
./scripts/new-app.sh https://github.com/coresync-fukuhara/time-announcement-frontend --subdomain time
```

`https://time.ubuntu.local/` でアクセスできる。

## CLI (server-base)

`scripts/*.sh` を個別に呼ぶ代わりに、統合CLI `server-base` でも同じ操作ができる。
`./scripts/install-cli.sh` を一度実行すると `~/.local/bin/server-base` に
シンボリックリンクが張られ、リポジトリの外からでも `server-base` として呼べる。
`install-cli.sh` は内部で [uv](https://docs.astral.sh/uv/) を使って依存関係(`.venv`)を
用意するため、事前に uv のインストールが必要(`curl -LsSf https://astral.sh/uv/install.sh | sh`)。

引数無しで `server-base` を実行する(または `server-base tui`)とTUIダッシュボードが
起動する。従来のサブコマンド群は `server-base cli <サブコマンド>` として呼び出す。

```bash
server-base                              # 引数無し → TUIダッシュボード起動
server-base tui                          # 上と同じ

server-base cli init                 # DNS+証明書発行+core起動(初回セットアップ一括)
server-base cli service add          # systemdユーザーサービスの登録
server-base cli service remove       # 上記の解除
server-base cli app add <repoのURL> [--service NAME] [--compose-file PATH] [--subdomain NAME] [--port N]
server-base cli app remove <app名>   # 確認プロンプトあり(-yで省略可)
server-base cli status                # core+各アプリの稼働状況・URL・到達性を一覧表示
server-base cli logs [app名]          # 省略時はcore(nginx/dnsmasq)
server-base cli restart [app名]       # 省略時は全体
server-base cli doctor                # 起動前の環境チェック一式
server-base cli cert renew [domain]   # TLS証明書の再発行(省略時ubuntu.local)
```

各サブコマンドの詳細は `server-base cli <サブコマンド> --help` を参照。

### TUIダッシュボードのキー操作

| キー | 動作 |
| --- | --- |
| `r` | ダッシュボードを手動更新(5秒毎に自動更新もされる) |
| `R` | core+全アプリを再起動(down→up) |
| `Enter` | ダッシュボードで選択中のアプリ行のみ再起動 |
| `d` | Doctor(環境チェック)画面 |
| `l` | Logs(ライブテール)画面。core/アプリを選んで表示 |
| `a` | アプリ管理画面(`n`で追加フォーム、Enterで削除) |
| `i` | 初回セットアップ(init)を実行 |
| `c` | TLS証明書を再発行 |
| `s` | systemdサービスの登録/解除 |
| `b` / `Esc` | ダッシュボードに戻る(モーダル表示中はキャンセル) |
| `q` | 終了 |

## 日常操作

初回セットアップ後の、通常時の起動・停止・確認コマンド。

```bash
./scripts/up.sh      # 起動（conf生成 → core → アプリ → nginx -t && reload）
./scripts/down.sh     # 停止

curl http://localhost/health
curl -k https://ubuntu.local/health
```

systemdユーザーサービスとして登録済みなら、`systemctl --user {start,stop,restart}
core-stack` でも同様に操作できる（詳細は [core/systemd/README.md](core/systemd/README.md)）。

起動するアプリを固定したい場合は `.env` に `COMPOSE_PROFILES` を書く
（`stacks/*/docker-compose.yml` 側で `profiles:` を設定している場合。デフォルトでは
`profiles:` を設定していないアプリは常に全部起動する）。

`*.ubuntu.local` のDNS・TLSはサブドメインを増やすたびの再設定は不要（ワイルドカード
対応済み）。証明書のワイルドカードは1階層のみ有効なので、サブドメインは1階層で
運用すること（詳細は [core/dnsmasq/README.md](core/dnsmasq/README.md)・
[core/nginx/README.md](core/nginx/README.md)）。

## 詳細ドキュメント

設計調査の全体像・実測検証・実装 TODO は
[docs/catchup/server-onboarding/](docs/catchup/server-onboarding/README.md) にまとめてある。
