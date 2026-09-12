# stacks/

アプリを 1 個追加する単位。`scripts/new-app.sh` が雛形を生成する。

`stacks/<app名>/docker-compose.yml` は **gitignore 対象**（このディレクトリの
`README.md` 自体は除く）。`.env`・`ssl/` と同様、「どのアプリを実際にデプロイ
しているか」はサーバーインスタンスごとに異なる設定であり、server_base は
汎用フレームワークとして再利用される前提のため、リポジトリにはコミットしない。
新しく clone した server_base では `stacks/` は空の状態から始まり、
`scripts/new-app.sh` で自分のアプリを追加していく。

```bash
./scripts/new-app.sh <repoのURL> [--service NAME] [--compose-file PATH] [--subdomain NAME] [--port N]
```

`<repoのURL>` のみが必須。app名はリポジトリ名から導出し、`../<app名>` に未cloneなら
自動でcloneする。`--service`・`--compose-file`はそれぞれ省略可(アプリ側composeのサービスが
1個だけなら自動検出、composeファイルも`deploy/docker-compose.yaml`等を自動探索)。
`--subdomain`・`--port`も省略可で、アプリ側composeの対象サービスに付与された
`site.subdomain`・`site.port` ラベルから自動検出する(`site.port`は必須の情報なので、
ラベルも`--port`指定も無い場合はエラーになる)。詳細な規約は
[docs/superpowers/specs/2026-09-12-app-compose-convention-design.md](../docs/superpowers/specs/2026-09-12-app-compose-convention-design.md)
を参照。

## 前提

- アプリ側リポジトリは server_base の**兄弟ディレクトリ**にクローンする
  （`include` の相対パスが固定されるため）
- アプリ側リポジトリは一切改変しない
- 1 stacks ファイル = 1 つの専用ネットワーク（信頼境界）が基本単位。
  複数アプリを同じネットワークに同居させたい場合は
  [06-selection.md 6章](../docs/catchup/server-onboarding/06-selection.md#複数アプリを同じ網に入れたくなったら)
  を参照

## 命名規約

- `stacks/<app名>/docker-compose.yml` の `<app名>` は小文字英数字とハイフンのみ
- サービスに `aliases: [<app名>]` を必ず付ける。nginx は全アプリの専用ネットワークに
  参加するため、アプリ側のサービス名が `web` / `app` のような一般名だと衝突しうる。
  一意な alias を与えることで回避する
- `labels.site.upstream` は alias と一致させる（`scripts/gen-nginx-conf.py` が読む）

## 注意: アプリ側 compose が独自の `networks:` を宣言している場合

多くのアプリ（例: [time-announcement-frontend](../docs/catchup/server-onboarding/01-current-state.md)）は
`networks:` を宣言しないため Compose の暗黙の `default` に乗る。この場合は
override で `networks:` を足すだけで元のネットワークへの参加は自動的に消える。

一方、アプリ側 compose が **明示的に** 独自ネットワーク（例: `webnet`）を宣言している場合、
素直に `networks:` を足すと **連結マージされて元のネットワークにも残ってしまう**
（実測で確認済み）。この場合は `networks: !override` で完全に置き換える必要がある。

`scripts/new-app.sh` は常に `!override` を使った雛形を生成するため、
どちらのケースでも安全に動作する。

## サービスを追記する必要があるケース

アプリ側リポジトリが後から DB 等のサービスを追加すると、stacks ファイルで
言及していないサービスは `default` ネットワークに落ちて本体から分断される。
`scripts/gen-nginx-conf.py` がこれを検出してエラーで止まるので、
指摘されたサービスをこのファイルに追記して `net-<app名>` に載せること。

## 起動

`stacks/*/docker-compose.yml` を置くだけでよい。起動は `scripts/up.sh` が
`stacks/*/docker-compose.yml` を自動で拾う（`scripts/render-compose.sh` 参照）。
