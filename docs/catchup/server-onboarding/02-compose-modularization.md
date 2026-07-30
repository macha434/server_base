# 02. Docker Compose のモジュール化

「docker compose をモジュール化したらいい感じにならないか」への回答。**結論: なる。**
ただし効くのは自分の compose を分割することではなく、**アプリ側 compose を "部品として取り込む"**
使い方。Compose にはそのための機構が 4 つあり、性質がかなり違う。

## 0. 結論先出し — 4 方式の比較

| 方式 | アプリ側改変 | 相対パス（`build.context: ..`）の解決 | 依存リソース（volume 等）の再宣言 | オーバーライド | 判定 |
| --- | --- | --- | --- | --- | --- |
| **`include`（長形式）** | 不要 | ✅ **included ファイル自身の位置基準**で正しく解決 | ✅ 不要（自動で引き継ぐ）| ✅ `path` にリストで指定 | 🏆 **本命** |
| `-f` 複数指定 / `COMPOSE_FILE` | 不要 | ⚠️ **最初のファイル基準**。アプリ側を先頭にすれば OK、逆にすると壊れる | ✅ 不要 | ✅ 後勝ちマージ | 🥈 次点（順序に注意）|
| `extends` | 不要 | ✅ 正しく解決（実測）| ❌ **必須**。忘れるとエラー | ✅ 同一サービス内に記述 | 🥉 volume 再宣言が負債 |
| `docker network connect` | 不要 | — | — | — | ❌ コンテナ再作成で消える |

以下、根拠と実測。

## 1. `include`（本命）

Compose v2.20.0 / Docker Desktop 4.22 以降で使えるトップレベル要素。
[公式ドキュメント](https://docs.docker.com/compose/how-tos/multiple-compose-files/include/) /
[compose-spec](https://github.com/compose-spec/compose-spec/blob/main/14-include.md)

### 短形式

```yaml
include:
  - ../time-announcement-frontend/deploy/docker-compose.yaml
```

### 長形式（オーバーライド付き）— これが欲しい形

```yaml
include:
  - path:
      - ../time-announcement-frontend/deploy/docker-compose.yaml   # ベース（改変禁止）
      - ./stacks/time-announcement.yml                             # 差分（server_base 所有）
    project_directory: ../time-announcement-frontend/deploy
```

`path` にリストを渡すと、**1 つ目がベース、2 つ目以降がオーバーライド**として
マージされる。これで「アプリ側は読むだけ、差分は自分のリポジトリに置く」が成立する。

### 属性

| 属性 | 意味 |
| --- | --- |
| `path`（必須）| 取り込む compose ファイル。文字列 or リスト |
| `project_directory` | 相対パスの解決基準。**既定は included ファイルのあるディレクトリ** |
| `env_file` | 変数補間に使う env ファイル。既定は `project_directory` 直下の `.env` |

### `include` の決定的な利点 — 相対パス解決

compose-spec の記述:

> Relative paths in Compose files being referred by `include` are resolved relative to
> their own Compose file path, not based on the local project's directory.

**included ファイル内の相対パスは、そのファイル自身の位置を基準に解決される。**
これが `-f` マージとの決定的な差。アプリ側の `build.context: ..` が正しく
アプリリポジトリのルートを指す。

その他:

- **再帰的**: included ファイルがさらに `include` を持っていれば辿る
- **OCI レジストリからの取得**も可能（`oci://docker.io/user/app:tag`）
- **`.env` の独立**: 各アプリが自分の `.env` を持ったまま取り込める（`env_file` で上書き可）

### 落とし穴

1. **リソース名の衝突**: `include` されたリソースと呼び出し側のリソースが衝突すると
   警告またはエラー。特に「複数アプリが同じ外部ネットワークを宣言する」ケースで
   `imported compose file defines conflicting network` が出る不具合が報告されていた
   （[docker/compose#10841](https://github.com/docker/compose/issues/10841)）。
   → **v5.3.1 では再現しないことを実測で確認**（後述 TEST2 / TEST4）。
   ただし古い Compose を使う環境では注意。
2. **サービス名のエイリアス衝突**: `webnet` 上ではサービス名がネットワークエイリアスに
   なるため、別アプリが同名サービス（`web`, `app` 等）を持つと解決先が曖昧になる。
   命名規律が要る。
3. Compose v2.20 未満では使えない。

## 2. `-f` を複数指定 / `COMPOSE_FILE`

[公式ドキュメント](https://docs.docker.com/compose/how-tos/multiple-compose-files/merge/)

```bash
docker compose -p time-announcement \
  -f ../time-announcement-frontend/deploy/docker-compose.yaml \
  -f ./stacks/time-announcement.yml \
  up -d
```

`.env` に書いて常用する形にもできる（区切りは `:`）:

```dotenv
COMPOSE_FILE=../time-announcement-frontend/deploy/docker-compose.yaml:./stacks/time-announcement.yml
COMPOSE_PROJECT_NAME=time-announcement
```

### マージ規則

| 種別 | 挙動 |
| --- | --- |
| 単一値（`image`, `command`, `restart`…）| 後のファイルが**置換** |
| リスト（`ports`, `dns`, `expose`…）| **連結**（＝消せない。`!reset` が必要）|
| マップ（`environment`, `labels`）| キー単位で後勝ち |
| `volumes` | コンテナ側マウントパス単位で後勝ち |

### 最大の落とし穴 — 相対パスは「最初のファイル」基準

> Paths are evaluated relative to the base file. When you use multiple Compose files,
> you must make sure all paths in the files are relative to the base Compose file.

公式も「monorepo では `include` を使え」と誘導している。実測でも、server_base 側の
ファイルを先に指定すると `build.context: ..` が**まったく別のディレクトリ**を指した
（TEST5）。**アプリ側 compose を必ず先頭に置く**という規律で回避できるが、
アプリが増えるほど事故りやすい。

## 3. `extends`

```yaml
services:
  time-announcement:
    extends:
      file: ../time-announcement-frontend/deploy/docker-compose.yaml
      service: schedule-ui
    networks: [webnet]
```

サービス単位で継承する。実測では `build.context` も正しく解決された（TEST6）。

**ただし致命的な手間がある**: 公式ドキュメントの通り、
参照先が使っている volume / network / secret / config を**呼び出し側で再宣言しないと
プロジェクトが不正になる**。

```console
$ docker compose -f extends-novol.yml config
service "time-announcement" refers to undefined volume time-announcement-settings: invalid compose project
```

（実測 TEST7）

今回のアプリは external volume を 3 つ使っているので、server_base 側にその 3 つを
コピーして書く必要がある。**アプリ側が volume を増やしたら server_base 側も追従が必要**＝
「改変しない」の趣旨は守れても、疎結合にはならない。`include` にはこの問題がない。

その他の制約: 循環参照不可、`docker stack deploy` では非対応。

## 4. `docker network connect`（非推奨）

```bash
docker network connect webnet deploy-schedule-ui-1
```

起動後に手で繋ぐ。**コンテナを再作成すると消える**（`docker compose up` で再作成されれば失われる）。
恒久運用には向かない。緊急の切り分け用途に留めるべき。

---

## 実測検証

Docker デーモンなしでもマージ結果を確認できる `docker compose config` で検証した。

```
Docker Compose version v5.3.1 / Docker version 29.6.2
```

再現用のフィクスチャ（アプリ側の実ファイルを模したもの）:

```bash
LAB=/tmp/compose-lab
mkdir -p "$LAB/time-announcement-frontend/deploy" "$LAB/server_base/stacks"

cat > "$LAB/time-announcement-frontend/deploy/docker-compose.yaml" <<'EOF'
services:
  schedule-ui:
    build:
      context: ..
      dockerfile: deploy/Dockerfile
    ports:
      - "3000:3000"
    volumes:
      - time-announcement-settings:/data/settings
    environment:
      - SETTINGS_DIR=/data/settings
    restart: unless-stopped
volumes:
  time-announcement-settings:
    external: true
EOF
```

### TEST1 — `include` 長形式 ＋ default ネットワーク差し替え ✅

```yaml
# server_base/stacks/time-announcement.yml
networks:
  default:
    name: webnet
    external: true
```

```yaml
# server_base/compose.yaml
name: server-base
include:
  - path:
      - ../time-announcement-frontend/deploy/docker-compose.yaml
      - ./stacks/time-announcement.yml
    project_directory: ../time-announcement-frontend/deploy
```

結果:

```yaml
services:
  schedule-ui:
    build:
      context: /tmp/compose-lab/time-announcement-frontend   # ← ✅ 正しく解決
      dockerfile: deploy/Dockerfile
    networks:
      default: null
    ...
networks:
  default:
    name: webnet        # ← ✅ 実体は webnet
    external: true
volumes:
  time-announcement-settings:
    name: time-announcement-settings
    external: true      # ← ✅ 再宣言なしで引き継がれた
```

この **"default ネットワークの実体を webnet にすり替える"** テクニックは、
サービス名を知らなくても書けるので単体では便利。

> 🔴 **ただし composition root で複数を include する場合は使ってはいけない。**
> `networks.default` はマージ後のプロジェクト**全体**に効くため、
> ネットワーク未指定の他サービス（dnsmasq など）まで巻き込んで `webnet` に載せてしまう。
> 実測で確認済み（[TEST11](#test11--default-差し替えの漏れと安全な書き方-)）。
>
> **composition root では、サービス単位で指定する形を使うこと:**
>
> ```yaml
> services:
>   schedule-ui:
>     networks: [webnet]
> networks:
>   webnet:
>     name: webnet
>     external: true
> ```
>
> `default` 差し替えは「そのアプリを単独プロジェクトとして起動する」場合に限って使う。

### TEST2 / TEST4 — 外部ネットワークのキー衝突 ✅ 問題なし

`include` されたオーバーライドと master 側の両方が `webnet`（外部ネットワーク）を
宣言するケース。issue #10841 で報告されていたパターンだが、**v5.3.1 では
エラーにならずマージされた**。キー名を `default` にした場合（TEST2）も、
両方 `webnet` にした場合（TEST4）も成功。

### TEST5 — `-f` マージの順序ミス ❌ パスが壊れる

server_base 側のファイルを先頭にして `-f` マージした結果:

```yaml
build:
  context: /tmp/compose-lab          # ← ❌ アプリリポジトリではなくラボ直下を指した
  dockerfile: deploy/Dockerfile
```

`-f` を使うなら**アプリ側 compose を必ず先頭**にすること。

### TEST6 / TEST7 — `extends`

- TEST6: `build.context` は正しく解決された ✅
- TEST7: top-level `volumes` を再宣言しないと `invalid compose project` エラー ❌

### TEST8 — `include` ＋ profiles ✅

オーバーライドで profile を後付けできる:

```yaml
# stacks/time-announcement.yml
services:
  schedule-ui:
    profiles: [time-announcement]
networks:
  default: { name: webnet, external: true }
```

```console
$ docker compose config --services
nginx

$ docker compose --profile time-announcement config --services
nginx
schedule-ui
```

**アプリ単位の起動/停止スイッチを server_base 側から後付けできる。**
「全部いっぺんに上げたくない」「特定アプリだけ一時的に外したい」に効く。

### TEST9 — 既定プロジェクト名 ⚠️

```console
$ docker compose -f deploy/docker-compose.yaml config | head -1
name: deploy
```

[01 の B4](./01-current-state.md#b4--プロジェクト名とホストポートの衝突) の通り、
`deploy/` 規約のアプリが複数来ると衝突する。composition root 側で `name:` を
明示すれば回避できる。

### TEST10 — ラベル注入 ＋ `!reset` でポート剥がし ✅

```yaml
# stacks/time-announcement.yml
services:
  schedule-ui:
    ports: !reset []            # ホストへの publish を取り消す
    labels:
      traefik.enable: "true"
      traefik.http.routers.ta.rule: "Host(`time.ubuntu.local`)"
      traefik.http.services.ta.loadbalancer.server.port: "3000"
networks:
  default: { name: webnet, external: true }
```

結果: `ports` が消え、labels が注入された。

これが重要なのは 2 点:

1. **`!reset` タグでリスト項目を消せる。** 通常マージではリストは連結されるだけで
   消せないが、`!reset` を使えば `ports: "3000:3000"` を打ち消せる。
   → **アプリのホストポート publish をやめさせて、nginx 経由のみに強制できる**
   （TLS バイパスの穴を塞げる。ポート採番の管理も不要になる）。
   部分的に置き換えたいときは `!override` タグも使える。
2. **Traefik / nginx-proxy 系が要求するラベルや環境変数を、アプリ側リポジトリを
   触らずに注入できる。** ラベルベースの自動検出プロキシは「アプリ側 compose に
   ラベルを書く」前提なので今回の制約と相性が悪いと思われがちだが、
   **オーバーライド経由なら成立する**。→ [04-alternatives.md](./04-alternatives.md)

### TEST11 — `default` 差し替えの漏れと安全な書き方 🔴

実リポジトリの `nginx/docker-compose.yml` ＋ `dnsmasq/docker-compose.yml` ＋
アプリ compose を 1 つの composition root に include して検証した。

**NG パターン**（オーバーライドで `networks.default` を差し替え）:

```yaml
# stacks/time-announcement.yml
networks:
  default: { name: webnet, external: true }
```

```yaml
# マージ結果
services:
  dnsmasq:
    networks:
      default: null     # ← 🔴 dnsmasq まで webnet に載ってしまった
  schedule-ui:
    networks:
      default: null
networks:
  default:
    name: webnet        # ← プロジェクト全体の default が webnet になった
    external: true
```

アプリを include しない場合は `default` は `server-base_default` という
独立したネットワークになる。つまり**アプリ用オーバーライドの 1 行が、
無関係な dnsmasq のネットワーク所属を書き換えてしまった。**

**OK パターン**（サービス単位で指定）:

```yaml
# stacks/time-announcement.yml
services:
  schedule-ui:
    networks: [webnet]
networks:
  webnet: { name: webnet, external: true }
```

```yaml
# マージ結果
services:
  dnsmasq:
    networks:
      default: null     # ← ✅ server-base_default のまま。隔離が保たれる
  nginx:
    networks:
      webnet: null      # ✅
  schedule-ui:
    networks:
      webnet: null      # ✅
```

**教訓: `include` は複数ファイルを 1 つのプロジェクトモデルにマージするので、
トップレベル要素（`networks`, `volumes`）への変更はグローバルに効く。
アプリ固有の変更は必ず `services.<name>` の下に閉じ込めること。**

---

## まとめ

- **`include` の長形式 ＋ オーバーライドファイル**が今回の制約に対する最適解。
  相対パスが正しく解決され、依存リソースも自動で引き継がれ、アプリ側は無改変。
- オーバーライドファイルで可能なこと:
  - `services.<name>.networks` に `webnet` を足す（到達性の解決）
    ※ `networks.default` の差し替えは他サービスを巻き込むので composition root では使わない
  - `ports: !reset []` でホスト publish を剥がす
  - `profiles` で起動対象を切り替える
  - `labels` / `environment` を注入する
- `-f` マージは順序依存の罠があり、`extends` は依存リソースの再宣言が負債になる。
- `docker network connect` は再作成で消えるので恒久運用不可。

## 参考

- [Include | Docker Docs](https://docs.docker.com/compose/how-tos/multiple-compose-files/include/)
- [compose-spec 14-include.md](https://github.com/compose-spec/compose-spec/blob/main/14-include.md)
- [Merge Compose files | Docker Docs](https://docs.docker.com/compose/how-tos/multiple-compose-files/merge/)
- [`extends` | Docker Docs](https://docs.docker.com/reference/compose-file/services/#extends)
- [Networks top-level element | Docker Docs](https://docs.docker.com/reference/compose-file/networks/)
- [docker/compose#10841 — include と外部ネットワークの衝突](https://github.com/docker/compose/issues/10841)
- [What is Compose Include and what problem does it solve?](https://dev.to/ajeetraina/what-is-compose-include-and-what-problem-does-it-solve-295c)
- [How to Set Up Communication Between Docker Compose Projects](https://oneuptime.com/blog/post/2026-01-25-communication-between-docker-compose-projects/view)
