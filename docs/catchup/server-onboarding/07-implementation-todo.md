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

## Phase 1: nginx 基盤の整理

- [ ] `nginx/conf.d/snippets/` に `ssl.conf`・`security.conf`・`proxy.conf` を作成する
      ([03 Level 1](./03-nginx-modularization.md#level-1--include-で共通部分を-snippet-化))
- [ ] `resolver 127.0.0.11` と `Upgrade` ヘッダ用の `map` を設定する
      （アプリが1個落ちていても nginx が起動・リロードできるようにする。
      [03 Level 2](./03-nginx-modularization.md#level-2--resolver--変数-proxy_pass-で起動時依存を断つ)）
- [ ] `nginx/template/site.conf.template` を variable `proxy_pass` 方式で作成する

## Phase 2: core/compose.yaml への統合

- [ ] `core/compose.yaml` を作成し、nginx と dnsmasq を1つの compose に統合する
- [ ] 旧 `nginx/docker-compose.yml`・`dnsmasq/docker-compose.yml` を廃止し、設定を `core/` へ移行する
- [ ] `dnsmasq.conf` 生成(`setup-dns.sh` 相当)を `core/` 構成に合わせて調整する

## Phase 3: stacks 雛形生成スクリプト

- [ ] `stacks/<app名>/docker-compose.yml` の雛形テンプレート(`include`・専用ネットワーク・
      `ports: !reset []`・`aliases`・`labels`)を用意する
- [ ] `scripts/new-app.*` を実装する — パラメータ(アプリ名・リポジトリの相対パス・
      ホスト名・ポート番号など)から `stacks/<app名>/docker-compose.yml` を生成する

## Phase 4: nginx conf 生成スクリプト

- [ ] `scripts/gen-nginx-conf.py` を実装する — 全 `stacks/*/docker-compose.yml` を
      `docker compose config --format json` で合成し、`site.*` labels から vhost を生成する。
      **`default` 網に残ったサービスがあればエラーで停止する**
      (アプリ側が後からサービスを増やしても気づけるようにする。[06 TEST21](./06-selection.md#実測検証-test12test23) 対策)

## Phase 5: 起動オーケストレーション

- [ ] 起動・停止スクリプトを作成する — `core/compose.yaml` と `stacks/*/docker-compose.yml` を
      `-f` で展開し、「conf 生成 → `up -d` → `nginx -t && nginx -s reload`」の順で実行する

## Phase 6: 実アプリでの検証 (time-announcement-frontend)

- [ ] `time-announcement-frontend` を兄弟ディレクトリにクローンする
- [ ] `scripts/new-app.*` で `stacks/time-announcement/docker-compose.yml` を生成する
- [ ] external volume(`time-announcement-settings` 等)をテスト用に用意する
- [ ] 起動スクリプトを実行し、生成された nginx conf と起動結果を確認する
- [ ] `https://time.ubuntu.local/` 相当で疎通確認する
      (mkcert 証明書・dnsmasq のワイルドカード解決が機能することも合わせて確認)

## Phase 7: ネットワーク分離とアプリ側変更耐性の検証

- [ ] ダミーの2つ目アプリを追加し、専用ネットワーク同士が相互到達不可であることを確認する
- [ ] `stacks` に書いていないサービスを意図的に追加し、生成スクリプトの検査で
      エラー停止することを確認する

## Phase 8: 既存資産の移行・整理

- [ ] 既存の `nginx/conf.d/nature.conf` を新方式(`stacks/nature/docker-compose.yml`)に移行する
- [ ] `.devcontainer` 側の `webnet` 参照・`nginx-dev` の扱いを新構成に合わせて整理する
- [ ] systemd unit を新しい起動コマンド・ディレクトリ構成(`core/compose.yaml`)に合わせて更新する

## Phase 9: ドキュメント整備・最終確認

- [ ] ルート `README.md` を新しい「アプリ追加手順」(`scripts/new-app.*` の使い方含む)に書き換える
- [ ] `docker compose down` → `up` でクリーンな状態からの再現性を確認する
