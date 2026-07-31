# scripts/

server_base の運用スクリプト一式。各スクリプトの詳しい使い方はスクリプト冒頭の
コメントを参照。ここでは一覧だけ示す。

| スクリプト | 役割 |
| --- | --- |
| `up.sh` | `core/compose.yaml` + `stacks/*/docker-compose.yml` をまとめて起動(conf生成 → up -d → nginx -t && reload) |
| `down.sh` | 同じ構成をまとめて停止 |
| `render-compose.sh` | `core/compose.yaml` と `stacks/*/docker-compose.yml` を列挙した `compose.generated.yaml` を生成(`up.sh`/`down.sh`/`gen-nginx-conf.py` が内部で使う) |
| `gen-nginx-conf.py` | `stacks/*/docker-compose.yml` の `site.*` ラベルから nginx vhost (`core/nginx/conf.d/<host>.conf`) を生成 |
| `new-app.sh` | 新しいアプリ用の `stacks/<app名>/docker-compose.yml` の雛形を生成 |
| `generate-cert.sh` | mkcert同梱コンテナ(`mkcert.Dockerfile`)で `ssl/` にTLS証明書を生成。詳細は [core/nginx/README.md](../core/nginx/README.md) |
| `mkcert.Dockerfile` | `generate-cert.sh` が使う、mkcert を同梱した使い捨てビルド用イメージ定義 |

## アプリを追加する流れ

1. アプリ側リポジトリを server_base の兄弟ディレクトリにクローン
2. `./scripts/new-app.sh <app名> <リポジトリパス> <composeファイル> [<サービス名>] <サブドメイン> <ポート>`
   (アプリ側composeのサービスが1個だけなら`<サービス名>`は省略可。自動検出する)
3. `./scripts/up.sh`

詳細はルートの [README.md](../README.md) を参照。
