# アプリ側 docker-compose 規約の統一と new-app.sh の自動化

## 背景・目的

server_base に新しいアプリを追加する現在の手順は `./scripts/new-app.sh <app名> <リポジトリパス> <composeファイル> [<サービス名>] <サブドメイン> <ポート>` と、複数の引数を毎回手入力する必要がある。

アプリ側リポジトリは VS Code devcontainer で個別に開発されており、server_base とは別リポジトリである。ゴールは **`new-app.sh <リポジトリのURL>` だけでアプリを追加できるようにする**こと。そのためには、new-app.sh が今まで人間に聞いていた情報（サブドメイン名・ポート番号・compose ファイルの場所）を自動検出できる必要がある。

かつ、「アプリ側リポジトリで特に設定を行わなくても良い」という要件がある。矛盾するようだが、これは「アプリ側 compose に規約に沿った labels を書く必要はあるが、それを開発者が毎回意識して手作業で書く必要はない」という意味で解決する。VS Code の `dev.containers.defaultFeatures` を一度設定すれば以後どの devcontainer でも自動適用される、という体験をモデルにする。

## 1. アプリ側 compose の規約

対象サービス（1個だけならサービス名の指定は不要。既存の new-app.sh と同じ自動検出ルールを踏襲）に以下の labels を持たせる。

```yaml
services:
  web:
    labels:
      site.port: "3000"        # 必須: nginxがproxy_passする先のコンテナ内ポート
      site.subdomain: "time"   # 任意: 省略時はリポジトリ名をそのまま使う
```

compose ファイルの場所は固定パスを優先探索する: `deploy/docker-compose.yaml` → `docker-compose.yaml` → `docker-compose.yml`。見つからない/複数該当する場合のみ `--compose-file` で明示する。

`site.port` が無い場合、new-app.sh は「site.port ラベルを追加してください」と具体的に案内してエラー終了する（サイレント失敗にしない）。

## 2. new-app.sh の新しいCLI

```bash
scripts/new-app.sh <repoのURL> [--service NAME] [--compose-file PATH] [--subdomain NAME] [--port N]
```

- `<repoのURL>` のみが必須。リポジトリ名から app名を導出し、`../<app名>` に未clone なら `git clone` する。
- サービス名・composeファイルパス・サブドメイン・ポートは上記1の規約から自動検出し、`--service`/`--compose-file`/`--subdomain`/`--port` で個別上書き可能にする。
- 生成物・検証ロジック（`networks: !override`、`ports: !reset []`、`site.*` ラベル付与など）は現行の雛形をそのまま踏襲する。
- 既存の「6引数固定」形式からの後方互換は不要（`stacks/*/docker-compose.yml` はサーバーインスタンスごとに毎回生成されるものであり、過去の呼び出し方法を保持する意味がないため）。

## 3. 規約を配布する仕組み: Claude Code スキル + devcontainer Feature

「アプリ側リポジトリで設定不要」を実現する配布方法として、devcontainer Feature を使う。

- 新規リポジトリ `server-base-features`（public, GitHub）に Feature `app-compose-skill` を実装する。
- Feature の `install.sh` が、ユーザーレベルの Claude Code スキル配置場所（`~/.claude/skills/server-base-app-compose/`）に SKILL.md 一式を配置する。中身は本ドキュメントの1・2節の規約（vendoring: リポジトリ内に同梱し、Feature自体のバージョンと一緒に配布する。B案）。
- 個人のVS Code設定に一度だけ登録する:
  ```json
  "dev.containers.defaultFeatures": {
    "ghcr.io/macha434/server-base-features/app-compose-skill:1": {}
  }
  ```
- 以後どのアプリのdevcontainerでも、Claude Codeがこのスキルを自動的に参照し、規約に沿った labels 付きの deploy/docker-compose.yaml を書けるようになる。アプリ側リポジトリの改変は一切不要。
- 公開・配布は `devcontainers/action`（公式GitHub Action）で、push/tag をトリガに GHCR (`ghcr.io/macha434/server-base-features/app-compose-skill`) へ自動公開する。

### server-base-features のリポジトリ構成

```
server-base-features/
├── src/
│   └── app-compose-skill/
│       ├── devcontainer-feature.json
│       ├── install.sh
│       └── skill/SKILL.md
├── test/
│   └── app-compose-skill/
│       └── test.sh
├── .github/workflows/release.yml   # devcontainers/action でGHCRへ自動公開
└── README.md
```

devcontainer は持たない（開発・検証は server_base 側の devcontainer で行う。次節参照）。

## 4. server_base 側 devcontainer の変更

### ディレクトリ構成

```
/workspace/
└── server-base/
    ├── core/       ← server_base リポジトリ本体をマウント
    └── features/   ← server-base-features を git clone（post-create.shが一度だけ）
```

```yaml
# .devcontainer/docker-compose.yml
volumes:
  - ..:/workspace/server-base/core:cached
```

```json
// .devcontainer/devcontainer.json
"workspaceFolder": "/workspace/server-base/core",
```

`configure_git`（`safe.directory`）・`setup_uv`（`cd /workspace`）を `/workspace/server-base/core` に更新する。

`post-create.sh` に `setup_workspace()` を追加する:

```bash
setup_workspace() {
    sudo mkdir -p /workspace/server-base
    sudo chown vscode:vscode /workspace/server-base   # 再帰chownは不要(core/配下は既存マウントで正しい所有権)

    if [ ! -d /workspace/server-base/features ]; then
        git clone <server-base-featuresのURL> /workspace/server-base/features
    fi

    if [ ! -f /workspace/server-base/server-base.code-workspace ]; then
        cat > /workspace/server-base/server-base.code-workspace <<'JSON'
{
  "folders": [
    { "name": "server_base (core)", "path": "core" },
    { "name": "server-base-features", "path": "features" }
  ]
}
JSON
    fi
}
```

- `features` clone・`.code-workspace` 生成ともに「無ければ作る、あれば触らない」（未コミットの作業や手動編集を消さない。`compose.generated.yaml` のような「都度再生成」とは扱いが異なる）。
- 利用者はアタッチ後 `File > Open Workspace from File` で `/workspace/server-base/server-base.code-workspace` を開けば、2リポジトリが並んだマルチルート表示になる。

### Docker ランタイム: docker-in-docker に一本化

- `.devcontainer/docker-compose.yml` から `/var/run/docker.sock` の手動マウント行を削除する。
- `docker-in-docker` feature（既存）はそのまま維持し、これに一本化する。
- 背景: 現状は `docker-in-docker` feature を入れつつホストの `docker.sock` を手動マウントしており、DinDの隔離デーモンをホスト共有(DooD)に事実上上書きしていた。`core/compose.yaml` は `./nginx/conf.d`・`../ssl` など相対パスのbind mountを使っており、DooD方式（今の実装 or `docker-outside-of-docker` featureのどちらでも同様）だとdevcontainer内のパスとホストの実パスが一致せず、bind mountが壊れうるという制約がある。DinDに一本化すれば、compose fileとコンテナが同じコンテナ内ファイルシステムに閉じるため、この制約を回避できる。
- ポート到達性: DinD内部dockerdは別コンテナ/VMではなく同じコンテナ内の別プロセスとして動くため、`-p 80:80`等のpublishはdevcontainer本体(`workspace`コンテナ)のネットワーク名前空間にそのまま乗る想定。既存の `forwardPorts: [80, 443]` がそれを拾い、WSL経由でWindows側からも `curl`/ブラウザで到達できるはず。
- **要検証（実装後に確認する）**: 上記のポート到達性の想定が実際に成立するか。`up.sh` 実行後、VS Codeの「ポート」パネルに80/443が転送済みとして表示されるか、Windows側から到達できるかを確認する。
  - もし到達できない場合のフォールバック: `.devcontainer/docker-compose.yml` の `workspace` サービスに `ports: ["80:80", "443:443"]` を追加し、Composeネイティブのpublish機能を使う。
- `.devcontainer/README.md` の「ホストのDockerデーモン上にそのまま起動する」という記述を、「devcontainer内で隔離されたDinD上に起動する」に更新する。

## 5. 対象外・将来検討

- APMパッケージとしての配布（プロジェクト単位のapm.ymlが必要になりそうで、「設定不要」要件と衝突する可能性があるため今回は見送り。将来、APMがグローバル/ユーザーレベルの配布をサポートするなら再検討）。
- devcontainer Feature の vendoring 更新時のバージョニング運用（SemVerのどこを上げるか等の細則）は、実運用してから決める。
