# Dev Container セットアップ

## 使い方

### 1. Dev Containerで開く

1. VS Codeでこのフォルダを開く
2. コマンドパレット（Ctrl+Shift+P）を開く
3. "Dev Containers: Reopen in Container" を選択

### 2. core スタックを起動

Dev Container内のターミナルで以下を実行：

```bash
cd /workspace/server-base/server-base-core
./scripts/up.sh
```

`workspace` コンテナは `docker-in-docker` feature による**隔離されたDockerデーモン**
(DinD)を使う。`core/compose.yaml`（nginx + dnsmasq）と `stacks/*/docker-compose.yml`
は、ホスト側のDockerデーモンではなく、このコンテナ内で完結したDinD上に起動する
（`core/compose.yaml` が `./nginx/conf.d` 等の相対パスbind mountを使っており、
ホストのデーモンを直接共有する方式(docker outside of docker)だとdevcontainer内の
パスとホストの実パスが食い違ってbind mountが壊れうるため、あえてDinDに一本化している）。

DinD配下のコンテナがpublishしたポートは `workspace` コンテナ自身のネットワーク名前空間に
乗るため、`devcontainer.json` の `forwardPorts: [80, 443]` がそのまま拾い、WSL経由で
Windows側からも `curl`/ブラウザで到達できる想定。もし到達できない場合のフォールバックとして、
`.devcontainer/docker-compose.yml` の `workspace` サービスに
`ports: ["80:80", "443:443"]` を追加する(Composeネイティブのpublish機能を使う)。

### 3. 動作確認

```bash
# ヘルスチェック
curl http://localhost/health

# アプリ経由（stacks に追加済みの場合）
curl -k https://time.ubuntu.local/
```

### 4. server-base-features と並べて開く(任意)

post-create.sh が [server-base-features](https://github.com/macha434/server-base-features)
を `/workspace/server-base/server-base-features` に clone し、`/workspace/server-base/server-base.code-workspace`
を生成する(初回のみ。既に存在する場合は上書きしない)。コンテナにアタッチした状態で
`File > Open Workspace from File...` からこのファイルを開くと、`core`（本リポジトリ）と
`features`（`server-base-features`）が並んだマルチルート表示になる（表示名は
`.code-workspace` の `name` で `core`/`features` に付け替えており、実際のフォルダ名は
`server-base-core`/`features` のまま）。

## 開発環境の構成

コンテナ内では、ホスト側の `server-base-core` リポジトリ（フォルダ名はリポジトリ名のまま）
がそのまま `/workspace/server-base/server-base-core` にマウントされる（`workspaceFolder`
もここ）。`/workspace/server-base/server-base-features` は上記の `server-base-features` の
clone置き場で、どちらも `/workspace/server-base` 配下の兄弟ディレクトリになる（フォルダ名は
どちらもリポジトリ名のまま）。

```
.devcontainer/
├── devcontainer.json       # Dev Container設定
└── docker-compose.yml      # workspace コンテナのみ定義（nginx/dnsmasq は core/ 側）

core/                        # nginx + dnsmasq (composition root)
stacks/                      # アプリごとの override
scripts/                     # up.sh / down.sh / new-app.sh / gen-nginx-conf.py
```

> 以前は `.devcontainer/docker-compose.yml` 自身が `nginx-dev`（`:80`/`:443` を publish）を
> 持っていたが、`core/compose.yaml` の nginx と同じポートを取り合うため廃止した。
> Dev Container 内でも `core/compose.yaml` 側の nginx をそのまま使う。

## ネットワーク

- Dev Container 自体: `devnet` ネットワーク（`workspace` コンテナ専用）
- アプリ用ネットワーク: `net-<app名>`（`stacks/<app名>/docker-compose.yml` が宣言し、nginx だけが全網に参加する）

フラットな共有ネットワーク（旧 `webnet`）は廃止し、アプリごとに専用ネットワークを切る構成にした。
詳細は [docs/catchup/server-onboarding/06-selection.md](../docs/catchup/server-onboarding/06-selection.md#6-ネットワーク分離の設計第一候補に組み込む) を参照。

## 便利なコマンド

```bash
# 停止
./scripts/down.sh

# nginx の設定テスト
docker compose -f compose.generated.yaml exec nginx nginx -t

# nginx ログの確認
tail -f core/nginx/logs/access.log
tail -f core/nginx/logs/error.log
```

## トラブルシューティング

### ポートが既に使用されている

Dev Containerを開く前に、ホスト側で起動している core スタックを停止してください：

```bash
# ホスト側で実行
./scripts/down.sh
```

### アプリケーションコンテナに接続できない

アプリが所属する専用ネットワークに nginx も参加しているか確認：

```bash
docker network inspect net-<app名>
```
