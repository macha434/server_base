# Server Base CLI 設計書

作成日: 2026-08-03

## 背景・目的

現状の server_base は `scripts/*.sh`（`up.sh` / `down.sh` / `new-app.sh` /
`install-service.sh` / `uninstall-service.sh` / `setup-dns.sh` /
`generate-cert.sh` 等）を個別に実行する運用になっている。日常操作
（初期セットアップ・アプリの追加削除・自動起動サービスの登録解除・稼働状況の
確認）を1つのCLIにまとめ、`server-base <サブコマンド>` という統一的な
インターフェースで扱えるようにする。

既存の `scripts/*.sh` は削除・改変しない。CLIはそれらを `subprocess` 経由で
呼び出す薄いオーケストレーション層として追加し、`./scripts/up.sh` などの
直接実行も引き続き可能な状態を維持する（後方互換）。

## 技術選定

- **実装言語**: Python3
  - `scripts/gen-nginx-conf.py` で既にPython3依存が確立済みのため、追加の
    前提条件が発生しない
  - Bashよりステータス表示・表形式出力・エラーハンドリングが書きやすい
- **既存スクリプトとの関係**: ラップする。ロジックの二重実装を避け、
  `new-app.sh` 等が持つ実機検証済みのバリデーション（例: サービス名の
  存在チェック、`networks: !override` の必要性判定）をそのまま活かす
- **コマンド名**: `server-base`
- **コード構成**: パッケージ化（複数ファイル）。将来的な機能追加に対して
  1ファイルへの機能の詰め込みを避ける

## ディレクトリ構成

CLIは `scripts/` の中に完結させる（リポジトリ直下には新規ディレクトリを
作らない）。

```
scripts/
├── server-base                     # 実行エントリポイント（chmod +x, shebang: python3）
├── install-cli.sh                  # server-base を ~/.local/bin にインストール
├── uninstall-cli.sh                # 上記の解除
└── server_base_cli/
    ├── __init__.py
    ├── main.py                     # argparse トップレベルパーサ、サブコマンド登録
    ├── shell.py                    # subprocess共通ヘルパー（既存.sh実行・exit code伝播・stdout/stderr垂れ流し）
    ├── paths.py                    # ROOT/stacks/core等のパス解決
    └── commands/
        ├── __init__.py
        ├── init.py                 # setup-dns.sh → generate-cert.sh → up.sh(core)
        ├── service.py              # add=install-service.sh / remove=uninstall-service.sh
        ├── app.py                  # add=new-app.shラップ / remove=新規ロジック
        ├── status.py               # core+アプリの状態一覧
        ├── logs.py                 # docker compose logs -f のラップ
        ├── restart.py              # docker compose restart のラップ
        ├── doctor.py               # 事前チェック
        └── cert.py                 # renew = generate-cert.sh再実行
```

既存の `scripts/README.md` のスクリプト一覧に、`server-base` CLI（および
`install-cli.sh` / `uninstall-cli.sh`）を追記する。

## コマンド仕様

| コマンド | 内容 |
|---|---|
| `server-base init` | `setup-dns.sh` → `generate-cert.sh ubuntu.local` → `up.sh`（core起動）を順に実行。途中で失敗したらそこで停止し、案内を表示する |
| `server-base service add` | `install-service.sh` を実行（systemdユーザーサービス `core-stack.service` の登録） |
| `server-base service remove` | `uninstall-service.sh` を実行 |
| `server-base app add <app名> <repo> <compose> [--service NAME] <subdomain> <port>` | `new-app.sh` に引数をそのまま渡す薄いラッパー。バリデーションは `new-app.sh` に一任する |
| `server-base app remove <app名> [-y]` | 下記「app remove の処理」参照。破壊的操作のため確認プロンプトあり（`-y` で省略可） |
| `server-base status` | core（nginx/dnsmasq）と各アプリの状態一覧。コンテナ状態・URL・HTTPヘルスチェック結果・systemdサービスの有効状態を表示 |
| `server-base logs [app名]` | 省略時はcore(nginx/dnsmasq)、指定時はそのアプリの `docker compose logs -f` |
| `server-base restart [app名]` | 省略時は全体（`down.sh` → `up.sh`相当）、指定時はそのアプリのサービスのみ `docker compose restart <service>` |
| `server-base doctor` | 事前チェック一式（下記参照）。1つでも失敗があれば exit code 1 |
| `server-base cert renew [domain]` | `generate-cert.sh` 再実行。省略時 `ubuntu.local` |

CLIには含めない機能（YAGNI・今回のスコープ外）:
- shell補完（bash/zsh）: 将来的にargparseから自動生成する形で追加可能だが、
  現時点では優先度が低いため見送り
- core配下の基盤サービス（nginx/dnsmasq以外）の追加・削除: 現状core構成は
  固定の2サービスのみで、将来的な拡張ニーズが顕在化してから検討する

## `app add` の処理

`new-app.sh <app名> <リポジトリパス> <composeファイル> [<サービス名>] <サブドメイン> <ポート>`
を、受け取った引数の順でそのまま呼び出す。事前バリデーション（重複チェック等）は
追加しない。`new-app.sh` 自身が実機検証済みのチェックを行っているため、その
出力・exit codeをそのままCLI利用者に見せる。

## `app remove` の処理

```
1. stacks/<app名>/docker-compose.yml の存在確認（無ければエラー終了）
2. 確認プロンプトを表示（-y で省略可）:
   "以下を削除します: stacks/<app名>/ ・コンテナ ・net-<app名> ネットワーク"
3. render-compose.sh を実行し、削除前の状態の compose.generated.yaml を得る
4. 対象サービス名を特定する:
   docker compose -f compose.generated.yaml config --format json
   を読み、net-<app名> に載っているサービスのうち core サービス
   （nginx / dnsmasq）を除いたものを対象とする。
   ※ stacks/<app名>/docker-compose.yml を単体で config にかけてはいけない。
     このファイルが持つ nginx の networks 追記には image が無く
     （image は core/compose.yaml にしかない）、
     "service nginx has neither an image nor a build context specified"
     で必ず失敗する。core と合成済みの compose.generated.yaml 経由なら通る
     （scripts/gen-nginx-conf.py も同じ方法で読んでいる）。
     nginx は全アプリの net-<app名> に参加するため、除外は必須
     （怠ると app remove が nginx を巻き込んで削除してしまう）。
5. docker compose -f compose.generated.yaml rm -f -s -v <対象サービス名...>
   （-s で先に停止、-v でアプリ専用の匿名ボリュームも削除）
6. docker network rm net-<app名>（存在しなければ黙って無視する）
7. rm -rf stacks/<app名>/
8. scripts/up.sh を実行し直す
   （compose.generated.yaml・nginx vhost を再生成し、nginx -t && reload。
    up -d は他の起動中アプリには影響を与えない）
```

## `doctor` のチェック項目

| チェック | 方法 |
|---|---|
| Docker導入・デーモン疎通 | `docker info` |
| ポート80/443の空き | ソケット占有状況を確認し、既知のnginxコンテナ以外が掴んでいたら警告 |
| ポート53(tcp/udp)の空き | 同上、dnsmasq以外の占有を警告 |
| `*.ubuntu.local` のDNS解決 | `127.0.0.1` に対して名前解決できるか確認（setup-dns.shの検証と同等） |
| TLS証明書の有無・有効期限 | `ssl/*-cert.pem` を `openssl x509 -enddate` で確認。残り30日未満で警告 |
| nginx設定の妥当性 | nginxコンテナが起動していれば `docker compose exec nginx nginx -t` |
| systemdユーザーサービスの登録状況（参考情報） | `systemctl --user is-enabled core-stack.service`。未登録でもエラー扱いにはしない |

各項目を ✓/✗/⚠ で一覧表示する。1つでも✗があれば `doctor` の exit codeは1。

## `status` の表示内容

- core: nginx・dnsmasqコンテナの稼働状態
- 各アプリ（`stacks/*/docker-compose.yml` から検出）:
  - コンテナの稼働状態（`docker compose ps` 相当）
  - `site.host` ラベルから導出したURL（`https://<app>.ubuntu.local/`）
  - nginx経由での実際のHTTP到達性（`curl -k` 等で確認）
- systemdユーザーサービス（`core-stack.service`）の有効/無効状態

## エラーハンドリング方針

- 全コマンド共通: ラップ先スクリプト・`docker`コマンドの exit code を
  そのまま CLI の exit code として返す。stdout/stderr はリアルタイムに
  素通しし、バッファリングして握りつぶさない
- `app add`: 追加の事前バリデーションはしない（`new-app.sh` に一任、
  重複ロジックを避ける）
- `app remove`: 対象が存在しない場合は明確なエラーメッセージで即終了。
  破壊的操作のため `-y` 無指定時は必ず確認プロンプトを挟む

## テスト方針

このセッションの開発環境は実際のサーバー機ではないため、`docker` /
`systemctl --user` / 実DNS に依存する部分は実機（ユーザーの運用PC）でしか
最終確認ができない。そのため以下の方針で進める:

- 外部コマンド呼び出しを伴わない部分（引数パース、パス解決、
  `app remove` のサービス名抽出ロジック等）は pytest による unit test を書く
- `docker` / `systemctl` 等の呼び出し箇所は `shell.py` に薄く集約し、
  呼び出しコマンドの組み立てをモックで検証する（実際の実行結果ではなく
  「正しいコマンドが組み立てられているか」を検証する）
- 実機での結合的な動作確認（`init`・`app add/remove`・`doctor` の実挙動等）は
  ユーザー側で実施してもらう

## `install-cli.sh` / `uninstall-cli.sh`

`server-base` コマンドを `~/.local/bin` にシンボリックリンクし、リポジトリの
外からでも `server-base` として実行できるようにする。`install-service.sh` /
`uninstall-service.sh` と対になる命名・置き場所（`scripts/` 直下）にする。
sudoは不要（`/usr/local/bin` は使わない）。

`scripts/install-cli.sh`:
```
1. chmod +x scripts/server-base
2. python3 の存在確認（無ければエラー終了、案内メッセージを表示）
3. mkdir -p ~/.local/bin
4. ln -sf "$REPO_ROOT/scripts/server-base" ~/.local/bin/server-base
   （symlinkなので再実行しても常に最新のrepoパスを指す。install-service.shの
    「@@REPO_ROOT@@を都度実パスに置換」と同じ思想）
5. ~/.local/bin が $PATH に無ければ警告し、bash/zsh向けの追加手順を表示
   （setup-dns.shのクライアント設定案内と同じスタイル）
6. 完了メッセージ + `server-base --help` の実行例を表示
```

`scripts/uninstall-cli.sh`:
```
1. ~/.local/bin/server-base が「このリポジトリのscripts/server-baseを指す
   symlinkかどうか」を確認する（無関係なファイルを誤って消さないための
   安全チェック）
2. 条件を満たせば rm、満たさなければ警告して何もしない
3. 完了メッセージ
```

## スコープ外（今回はやらないこと）

- linger（`loginctl enable-linger`）の設定・案内は行わない（ユーザーの
  明示的な要望により不要と判断済み）
- リポジトリ分割はしない。CLIはこのリポジトリ内に置く
- core配下の基盤サービス（nginx/dnsmasq以外）の追加・削除機能
- shell補完
