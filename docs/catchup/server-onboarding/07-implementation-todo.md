# 07. 実装 TODO

[01](./01-current-state.md)〜[06](./06-selection.md) の調査結果を踏まえた、実装の道のり。
実装が進むにつれてこのファイルのチェックボックスを更新していく。

## 確定した構成

- **dnsmasq は単体のディレクトリ/compose としては廃止**し、機能(ワイルドカード DNS 解決)は
  **nginx と合わせて `core/compose.yaml` に残す**。`*.ubuntu.local` がクライアント側の
  `/etc/hosts` 編集なしで解決できる今の利点は維持する
- **`core/compose.yaml`**: nginx・dnsmasq を含む基盤サービス一式（旧 `nginx/docker-compose.yml`・
  `dnsmasq/docker-compose.yml` を統合)
- **`stacks/<app名>/docker-compose.yml`**: アプリ 1 個の単位。中でアプリ側 compose を
  `include` し、専用ネットワーク・`ports: !reset []`・`labels` などの差分を上書きする
- **`stacks/<app名>/docker-compose.yml` 自体は script が雛形生成する**
  （アプリ名・リポジトリパス・ホスト・ポートなどのパラメータから生成）
- **nginx の vhost conf は別のスクリプトが生成する**
  （全 `stacks/*/docker-compose.yml` を合成し、`labels` を読んで生成。[06 の A' 案](./06-selection.md#a-nginx--ラベル駆動の生成スクリプト)）
- アプリごとに専用ネットワークを切り、nginx だけが全網に参加する
  ([06 の 6 章](./06-selection.md#6-ネットワーク分離の設計第一候補に組み込む))
- アプリ側リポジトリは一切改変しない

## 実装中に確定した追加事項

01〜06 の調査時点では分かっていなかった、実装作業中に判明した点。

- **`docker compose -f A -f B ...` の複数 `-f` 指定は、`include:` の相対パス解決には
  使えない。** B が持つ `include:` の相対パスは（B 自身の位置ではなく）**先頭に指定した
  ファイルの位置**基準で解決されることを実測で確認した。アプリが 2 つ以上になると、
  先頭ファイル以外の `include:` が壊れる。
  → 対策として `scripts/render-compose.sh` が `core/compose.yaml` と
  `stacks/*/docker-compose.yml` を列挙したトップレベル `include:` を持つ
  `compose.generated.yaml` を都度生成し、これを使って起動・conf 生成の両方を行う
  （`include:` は glob 非対応なので列挙自体は動的に行う必要がある）。
- **アプリ側 compose が独自の `networks:` を明示的に宣言しているケース**
  （例: `nature-controler` が `networks: [webnet]` を持つ）では、stacks 側で
  `networks:` を単純に追記しても**連結マージされて元のネットワークにも残ってしまう**。
  `networks: !override` で完全に置き換える必要がある（実測で確認済み。
  01〜06 が検証に使った time-announcement-frontend は `networks:` 無宣言だったため、
  このケースには気づいていなかった）。`scripts/new-app.sh` は常に `!override` を使う。

## Phase 1: nginx 基盤の整理

- [x] `nginx/conf.d/snippets/` に `ssl.conf`・`security.conf`・`proxy.conf` を作成する
      ([03 Level 1](./03-nginx-modularization.md#level-1--include-で共通部分を-snippet-化))
      → `core/nginx/conf.d/snippets/`
- [x] `resolver 127.0.0.11` と `Upgrade` ヘッダ用の `map` を設定する
      （アプリが1個落ちていても nginx が起動・リロードできるようにする。
      [03 Level 2](./03-nginx-modularization.md#level-2--resolver--変数-proxy_pass-で起動時依存を断つ)）
      → `core/nginx/conf.d/00-http.conf`
- [x] `nginx/template/site.conf.template` を variable `proxy_pass` 方式で作成する
      → `core/nginx/template/site.conf.template`（`__HOST__`/`__UPSTREAM__`/`__PORT__` を
      `scripts/gen-nginx-conf.py` が置換する）

## Phase 2: core/compose.yaml への統合

- [x] `core/compose.yaml` を作成し、nginx と dnsmasq を1つの compose に統合する
- [x] 旧 `nginx/docker-compose.yml`・`dnsmasq/docker-compose.yml` を廃止し、設定を `core/` へ移行する
- [x] `dnsmasq.conf` 生成(`setup-dns.sh` 相当)を `core/` 構成に合わせて調整する
      → `core/dnsmasq/setup-dns.sh`（`core/compose.yaml` 経由で起動するように変更）

## Phase 3: stacks 雛形生成スクリプト

- [x] `stacks/<app名>/docker-compose.yml` の雛形テンプレート(`include`・専用ネットワーク・
      `ports: !reset []`・`aliases`・`labels`)を用意する
- [x] `scripts/new-app.*` を実装する — パラメータ(アプリ名・リポジトリの相対パス・
      ホスト名・ポート番号など)から `stacks/<app名>/docker-compose.yml` を生成する
      → `scripts/new-app.sh`。相対パス（`include.path`/`project_directory`）は
      スクリプトが自動計算するため、手でパスを数える必要はない

## Phase 4: nginx conf 生成スクリプト

- [x] `scripts/gen-nginx-conf.py` を実装する — 全 `stacks/*/docker-compose.yml` を
      `docker compose config --format json` で合成し、`site.*` labels から vhost を生成する。
      **`default` 網に残ったサービスがあればエラーで停止する**
      (アプリ側が後からサービスを増やしても気づけるようにする。[06 TEST21](./06-selection.md#実測検証-test12test23) 対策)
      → 実測で orphan 検知・stale conf の自動削除まで動作確認済み

## Phase 5: 起動オーケストレーション

- [x] 起動・停止スクリプトを作成する — `core/compose.yaml` と `stacks/*/docker-compose.yml` を
      `-f` で展開し、「conf 生成 → `up -d` → `nginx -t && nginx -s reload`」の順で実行する
      → `scripts/up.sh` / `scripts/down.sh`。上記の理由により実体は `-f` 複数指定ではなく
      `scripts/render-compose.sh` が生成する `compose.generated.yaml` を単一の `-f` で使う

## Phase 6: 実アプリでの検証 (time-announcement-frontend)

- [x] `time-announcement-frontend` を兄弟ディレクトリにクローンする
- [x] `scripts/new-app.*` で `stacks/time-announcement/docker-compose.yml` を生成する
- [ ] external volume(`time-announcement-settings` 等)をテスト用に用意する
- [ ] 起動スクリプトを実行し、生成された nginx conf と起動結果を確認する
- [ ] `https://time.ubuntu.local/` 相当で疎通確認する
      (mkcert 証明書・dnsmasq のワイルドカード解決が機能することも合わせて確認)

> **検証環境の制約:** この作業を行ったセッションには Docker デーモンはあるが、
> コンテナイメージ registry への出口が塞がれておりイメージ pull ができない
> （実サーバーとは異なる制約）。そのため `docker compose config`（デーモン不要・
> パースのみ）による構成検証までは実施したが、実際の `up -d`・`nginx -t`・
> HTTPS 疎通・mkcert・DNS 解決は**未検証**。実サーバー上で
> `./scripts/up.sh` を実行して最終確認すること。

## Phase 7: ネットワーク分離とアプリ側変更耐性の検証

- [x] ダミーの2つ目アプリを追加し、専用ネットワーク同士が相互到達不可であることを確認する
      → `docker compose config` 上で `nature` / `schedule-ui` が異なる専用ネットワークに
      分離され、`nginx` のみが両方に参加していることを確認（実コンテナでの到達性テストは
      Phase 6 と同じ制約で未実施）
- [x] `stacks` に書いていないサービスを意図的に追加し、生成スクリプトの検査で
      エラー停止することを確認する
      → `scripts/gen-nginx-conf.py` が orphan サービスを検出しエラー終了することを確認済み

## Phase 8: 既存資産の移行・整理

- [x] 既存の `nginx/conf.d/nature.conf` を新方式(`stacks/nature/docker-compose.yml`)に移行する
      → 実体は [macha434/nature-controler](https://github.com/macha434/nature-controler)。
      アプリ側 compose が `networks: [webnet]` を明示的に持つため `!override` で置き換えている
      （上記「実装中に確定した追加事項」参照）
- [x] `.devcontainer` 側の `webnet` 参照・`nginx-dev` の扱いを新構成に合わせて整理する
      → `.devcontainer/docker-compose.yml` から `nginx-dev`/`webnet` を削除し、
      `workspace` コンテナから `./scripts/up.sh` を使う運用に変更
- [x] systemd unit を新しい起動コマンド・ディレクトリ構成(`core/compose.yaml`)に合わせて更新する
      → `core/systemd/core-stack.service` に統合（旧 nginx/dnsmasq 別々の unit は廃止）

## Phase 9: ドキュメント整備・最終確認

- [x] ルート `README.md` を新しい「アプリ追加手順」(`scripts/new-app.*` の使い方含む)に書き換える
- [ ] `docker compose down` → `up` でクリーンな状態からの再現性を確認する
      → Phase 6/7 と同じ制約（registry 到達不可）のため実サーバーでの確認が必要
