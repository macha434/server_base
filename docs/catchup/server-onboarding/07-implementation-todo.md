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
- **`include snippets/*.conf;` は nginx の設定 prefix (`/etc/nginx`) 基準で解決される**
  ため、`conf.d/*.conf` の中から書くと `/etc/nginx/snippets/...` を探しに行ってしまい
  **`nginx -t` が失敗する**（`conf.d/snippets/` に置いているため）。実機の nginx（Ubuntu
  パッケージ版で `nginx -t` を実測）で確認・修正済み。`core/nginx/conf.d/default.conf`・
  `core/nginx/template/site.conf.template`・生成済みの `core/nginx/conf.d/*.ubuntu.local.conf`
  はすべて `include conf.d/snippets/...` に修正した。
- **`include:` で取り込んだサービスを同じファイル内で上書きする(`services: nature: ...` +
  `networks: !override` 等)パターンは、古い Docker Compose では動かない。**
  実サーバーに入っていた Compose plugin v2.27.0（2024年5月ビルド）で実行すると、
  1アプリだけの構成でも `services.nature conflicts with imported resource` で
  即座に失敗する（`include` 元・`include` 先が同じファイルでも、別ファイル同士の
  sibling `include:` 同士でも同様に失敗した。多階層に検証して確認済み）。
  Compose v5.3.1 に入れ替えると同じリポジトリのファイルのまま何も変更せずに解決した。
  → **`core/compose.yaml` の `include:` ベースの上書きが機能するには、比較的新しい
  Docker Compose CLI plugin が必須**（v2.27.0 では不可、v5.3.1 で動作確認済み。
  正確な最小バージョンは未特定）。system 全体の plugin (`/usr/libexec/docker/cli-plugins/`)
  を書き換えるには root 権限が要るが、**`~/.docker/cli-plugins/docker-compose` に
  ユーザー権限で置くだけで docker CLI がそちらを優先して使う**ため、sudo なしで
  アップグレードできる。同様に `docker compose build`(schedule-ui・nature の
  イメージビルド)には **buildx 0.17.0 以上が必須**で、実サーバーの buildx 0.14.0 では
  `compose build requires buildx 0.17.0 or later` で失敗した。こちらも
  `~/.docker/cli-plugins/docker-buildx` にユーザー権限で新しいバイナリを置いて解決した。
  → 新しいサーバーにこの構成をデプロイする際は、事前に
  `docker compose version` / `docker buildx version` を確認し、古ければ
  `~/.docker/cli-plugins/` にユーザー権限で新しいバイナリを配置すること。
- **`core-stack.service`（systemd `--user` unit）に `After=docker.service` /
  `Requires=docker.service` を書くと `Unit docker.service not found` で起動に失敗する。**
  `docker.service` は system 側の unit であり、`systemctl --user` の unit namespace
  からは参照できない。旧構成の `nginx-stack.service` も同じ依存を宣言しており、
  実は一度も systemd 経由では起動できておらず(`systemctl --user status` は
  常に `inactive (dead)`)、コンテナは手動 `docker compose up -d` で起動されたまま
  放置されていたことが実機で判明した(対照的に依存を書いていなかった
  `dnsmasq-ubuntu-local.service` は `active (exited)` として正常に機能していた)。
  → `core/systemd/core-stack.service` から `After=`/`Requires=docker.service` を削除。
  また `WorkingDirectory`/`ExecStart`/`ExecStop` が `%h/server_base` 決め打ちだったが、
  実サーバーでのリポジトリ配置は `~/Projects/server_base` だったため
  `%h/Projects/server_base` に修正した。

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
- [x] external volume(`time-announcement-settings` 等)をテスト用に用意する
      → `time-announcement-settings` / `time-announcement-db` / `time-announcement-sounds`
      の3つ(空の状態でOK。本番データはまだ存在しないため新規作成)
- [x] 起動スクリプトを実行し、生成された nginx conf と起動結果を確認する
- [x] `https://time.ubuntu.local/` 相当で疎通確認する
      (mkcert 証明書・dnsmasq のワイルドカード解決が機能することも合わせて確認)
      → 2026-07-31、実サーバーで実施。旧 `/opt/server_base`(nginx・dnsmasq)・
      `/opt/nature-controler` の3コンテナを停止した上で新構成を起動し、
      `https://nature.ubuntu.local/` `https://time.ubuntu.local/` とも 200・
      実アプリの HTML を確認。`dig @127.0.0.1 *.ubuntu.local` も 192.168.3.17 を返す。
      mkcert 証明書は新規生成せず、旧 `/opt/server_base/nginx/ssl/` の鍵(root 所有・
      600権限のためユーザーに sudo cp してもらった)をそのまま再利用し、
      既存クライアントの信頼チェーンを維持した(新規生成すると別 CA になり、
      家庭内の端末で証明書警告が出るところだった)。
      **前提条件の Docker Compose / buildx バージョンについては上記
      「実装中に確定した追加事項」を参照**(実サーバーの初期バージョンでは動かず、
      ユーザー権限での plugin 差し替えが必要だった)。

> **検証環境の制約:** この作業を行ったセッションには Docker デーモンはあるが、
> コンテナイメージ registry への出口が塞がれておりイメージ pull ができない
> （実サーバーとは異なる制約）。そのため `docker compose config`（デーモン不要・
> パースのみ）による構成検証までは実施したが、実際の `up -d`・`nginx -t`・
> HTTPS 疎通・mkcert・DNS 解決は**未検証**。実サーバー上で
> `./scripts/up.sh` を実行して最終確認すること。
>
> **追記(別セッションでの再検証):** このリポジトリの devcontainer は
> `/var/run/docker.sock` を直接マウントしており、実ホーム機の Docker デーモンを共有する
> 構成だった（既存の他プロジェクト用ネットワークや `nginx-dev` コンテナの存在で確認）。
> このため `scripts/up.sh` をこのコンテナ内から実行すると、compose の相対パスは
> コンテナ側の `/workspace` 基準で解決されるが、デーモンは実ホストのファイルシステムで
> それを解釈してしまい、bind mount が意図しない場所を指す。したがって
> **実コンテナの起動・停止はこのセッションでも実施していない**（実サーバーで直接
> 実行する必要があるのは変わらず）。代わりに、a) 兄弟リポジトリを一時的に clone した
> 上で `docker compose config` の再検証、b) 実際の nginx バイナリ（Ubuntu パッケージ）
> による `nginx -t` 構文検証、を追加で実施した。(b) で `include snippets/*.conf;` の
> パス解決バグを発見・修正済み（上記「実装中に確定した追加事項」参照）。
> external volume の用意・実際の起動確認・HTTPS 疎通・`down`→`up` の再現性確認は
> 引き続き実サーバーでの確認が必要。

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
      → `core/systemd/core-stack.service` に統合（旧 nginx/dnsmasq 別々の unit は廃止）。
      2026-07-31、実サーバーに実際にインストールして確認(それまではファイルを
      作っただけで実機導入は未検証だった)。`After=`/`Requires=docker.service` が
      `systemctl --user` では解決できずインストール時に起動失敗することが判明し修正
      (詳細は上記「実装中に確定した追加事項」)。旧 `nginx-stack.service`・
      `dnsmasq-ubuntu-local.service`・`nature-controler.service`(nature 単体の旧 unit)は
      いずれも `systemctl --user disable` 済み。

## Phase 9: ドキュメント整備・最終確認

- [x] ルート `README.md` を新しい「アプリ追加手順」(`scripts/new-app.*` の使い方含む)に書き換える
- [x] `docker compose down` → `up` でクリーンな状態からの再現性を確認する
      → 2026-07-31、実サーバーで実施。`scripts/down.sh` で全コンテナ・ネットワークが
      きれいに消えることを確認した上で `scripts/up.sh` を再実行。イメージキャッシュが
      効くため2秒弱で再起動し、`https://nature.ubuntu.local/` `https://time.ubuntu.local/`
      とも即座に 200 が返ることを確認済み。

## Phase 9 後の追加修正 (2026-07-31)

実サーバーでの検証を経て判明した、リポジトリ内パスの決め打ちに起因する問題を修正した。

- **`core/systemd/core-stack.service` のリポジトリパス決め打ち**: `WorkingDirectory`/
  `ExecStart`/`ExecStop` が `%h/Projects/server_base` に決め打ちされており、clone 先が
  変わると動かない。unit ファイル側は `@@REPO_ROOT@@` プレースホルダにし、
  `install-service.sh` が自身の実行位置から実パスを算出して置換した実体ファイルを
  `~/.config/systemd/user/` に書き出す方式に変更（symlink ではない。プレースホルダの
  ままでは systemd がそのまま解釈してしまうため）。リポジトリを移動した場合は
  `install-service.sh` の再実行が必要。
- **mkcert 証明書の格納場所**: 旧 `/opt/server_base/nginx/ssl/` からの移行時に
  `sudo cp`(root 所有・600権限のため)が必要だったのは、証明書が `core/nginx/ssl/` という
  **`core/` の内部構造に紐づいた場所**に置かれていたため。証明書はサーバー機・ドメイン
  (`*.ubuntu.local`)に紐づくものであり `core/` の内部構造とは無関係なので、
  リポジトリ直下の `ssl/` ディレクトリに切り出した(`.gitkeep` でディレクトリ自体は保持し、
  `*.pem` 等の証明書本体のみ `.gitignore`)。`core/compose.yaml` の bind mount 元も
  `./nginx/ssl` → `../ssl` に変更。これで今後 `core/` 配下がどう再編されても
  証明書を再配置する必要はない。あわせて `generate-cert.sh` は他の運用スクリプトと
  同じ `scripts/` 配下に移し(出力先は常に `<repo root>/ssl/` を指すよう固定)、
  `ssl/` はデータ専用ディレクトリにした。
- **`scripts/gen-nginx-conf.py` が生成する vhost (`core/nginx/conf.d/*.ubuntu.local.conf`)
  は方針転換してコミット対象から外した。** 当初は「生成物もコミットして git diff で
  レビューできるようにする」方針だった([06-selection.md](./06-selection.md)参照)が、
  `stacks/*/docker-compose.yml` の labels から `scripts/up.sh` 実行時に毎回再生成される
  ため、コミットしても差分がノイズになるだけと判断し `.gitignore` に追加(実ファイルは
  そのまま残し `git rm --cached` で追跡のみ解除)。`00-http.conf`・`default.conf` など
  手書きファイルは引き続きコミット対象。
- **`ssl/.gitignore` はルートの `.gitignore` に統合した。** このリポジトリは大半の除外
  ルールをルート直下 1 枚に集約する流儀だったため、`ssl/.gitignore` がネストされた
  例外になっていた。`ssl/*.pem` 等としてルートに統合し、`ssl/.gitignore` は削除。
  (2026-07-31 コードレビューで判明: `core/dnsmasq/.gitignore` も同じ理由で
  ネストされた例外として残っていた上、ルートの `.gitignore` と内容が完全に重複していた
  ため、あわせて削除した。)
- **mkcert 証明書生成の事前準備を Docker のみにした。** 従来の `generate-cert.sh` は
  ホストに直接 mkcert をインストールしていた(apt-get/wget/sudo)。
  `scripts/mkcert.Dockerfile`(alpine + mkcert公式バイナリを wget で取得)でイメージを
  ビルドし、コンテナ内で `mkcert -install`・証明書生成を行う方式に変更。CA
  (`rootCA.pem`/`rootCA-key.pem`)は `ssl/mkcert-ca/` に bind mount して永続化し(
  `.gitignore` 済み)、再実行しても同じ CA が再利用される。ビルド・mkcert 自体の動作
  (証明書生成ロジック)はこのセッションでも実機の Docker デーモンで確認したが、
  bind mount 経由での `ssl/` への書き込みは devcontainer の docker-outside-of-docker
  制約(Phase 6 の追記参照)により未確認。実サーバーでの最終確認が必要。
- **セットアップ手順の README は `ssl/` から `core/nginx/README.md` へ移し、
  スクリプト一覧は `scripts/README.md` に新設した。** `ssl/` はデータ専用ディレクトリ
  (証明書本体のみ)という方針に合わせ、手順書は「証明書を実際に使う nginx」側
  (`core/dnsmasq/README.md`・`core/systemd/README.md` と同じ並び)に置く形に統一。
  あわせて `ssl/README.md` にあった「ホスト名の設定」「Avahi(mDNS)のセットアップ」は
  `core/dnsmasq/README.md` のワイルドカードDNSと重複・不要だったため削除。

## マージ前コードレビューでの修正 (2026-07-31)

PR全体を code-reviewer・silent-failure-hunter の2エージェントでレビューし、
実機のDockerデーモンで再現・検証した上で以下を修正した。

- **`--profile` フラグが効いていなかった。** `up.sh`/`down.sh` が `"$@"` を
  `up -d`/`down` の**後ろ**に渡していたため、`--profile` のような docker compose
  本体のフラグを付けると `unknown flag` で失敗していた(実測で確認)。
  サブコマンドの**前**に渡すよう修正。
- **`gen-nginx-conf.py` が失敗理由を握りつぶしていた。** `docker compose config`
  失敗時、`subprocess.CalledProcessError` を捕捉しておらず、実際のエラー内容
  (`stderr`)が一切表示されないまま素っ気ないトレースバックだけで終わっていた
  (`new-app.sh` でサービス名をタイプミスした場合などで再現)。`stderr` を表示して
  から終了するよう修正。
- **オーファン検知が `default` ネットワークしか見ていなかった。** アプリ側 compose
  が独自ネットワーク(例: `webnet`)を宣言していて `!override` し忘れたサービスは
  `default` に落ちないため、既存の検査をすり抜けて何のエラーも出さずvhostが
  生成されてしまうことを実機で再現。`net-<app名>` 規約に合っていないネットワークを
  一律検知するよう修正。
- **`site.host` の重複を検知していなかった。** 2つのサービスが同じ `site.host` を
  宣言すると、後勝ちで片方のvhostが無言で消える動作を実機で再現。`site.port`
  同様にエラーで停止するよう修正。
- **`up.sh` の「他アプリが落ちていてもnginxは起動できる」という前提が、
  compose全体のエラー(イメージpull失敗等)には効いていなかった。** 1つのアプリの
  イメージがpullできないだけで `docker compose up -d` 自体が exit 1 になり、
  core(nginx・dnsmasq)を含め**何も起動されない**ことを実機で再現(通常の
  「起動はしたが後で落ちた」ケースとは異なり、これは資源が1つも作られない)。
  core(nginx・dnsmasq)を先に単独で `up -d` してから、アプリ一式を `up -d` する
  二段階に変更。アプリ側が失敗しても core は起動済みのまま残ることを実機で確認済み。
- **`new-app.sh` の `<サービス名>` にタイプミスがあっても検知できなかった。**
  `<app名>`/`<ポート>` は正規表現検証していたが `<サービス名>`/`<サブドメイン>` は
  無検証だった。文字種チェックに加えて、アプリ側composeに実在するサービス名かどうか
  (`docker compose config --services`)も事前検証するよう修正(実機で
  タイプミスを検知できることを確認)。
- **`core/systemd/{un,}install-service.sh` のエラー握りつぶし。**
  `uninstall-service.sh` は `stderr` を `/dev/null` に捨てた上で、失敗理由を
  問わず「既に停止/無効化されています」と決め打ちしていた。`install-service.sh` は
  `set -e` のため `systemctl --user start` が失敗すると診断用の
  status・journalctl案内が出せないまま終了していた。両方修正。
- 上記に加え、以下も修正: README.mdに残っていた「vhostはコミットする」という
  古い方針の記述(既にgitignore化されている実態と矛盾)、`core/compose.yaml`・
  `up.sh` のコメントが実態(複数`-f`は使わない/常に全アプリ起動)と食い違っていた点、
  `core/systemd/README.md` の `COMPOSE_PROFILES` 例が実際には無効(どのstacksも
  `profiles:` を設定していない)なのにそう見えなかった点、`core/dnsmasq/.gitignore`
  がルートの `.gitignore` と内容重複していた点、`.env` が `.gitignore` に無かった点、
  READMEの兄弟ディレクトリ例に `nature-controler` が抜けていた点(`time-announcement-frontend`
  のみ記載で、実際は両方無いと `./scripts/up.sh` が失敗する)。
