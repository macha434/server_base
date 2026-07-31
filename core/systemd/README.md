# core-stack systemd ユーザーサービス

`core/compose.yaml`（nginx + dnsmasq）と `stacks/*/docker-compose.yml`（各アプリ）を
まとめて `scripts/up.sh` / `scripts/down.sh` 経由で起動・停止する systemd ユーザーサービスです。

旧構成では nginx と dnsmasq に別々の systemd unit がありましたが、
`core/compose.yaml` への統合に合わせて 1 つの unit にまとめました。

## インストール

```bash
cd core/systemd
chmod +x install-service.sh
./install-service.sh
```

`core-stack.service` の `WorkingDirectory`/`ExecStart`/`ExecStop` はリポジトリパスを
決め打ちせず `@@REPO_ROOT@@` というプレースホルダにしてあり、`install-service.sh` が
自身の実行位置からリポジトリの実パスを算出して置換したものを
`~/.config/systemd/user/core-stack.service` に書き出す（symlink ではなく実体ファイル）。
そのため **リポジトリを別の場所に移動した場合は `install-service.sh` を再実行**すること。

## アンインストール

```bash
cd core/systemd
./uninstall-service.sh
```

## 起動対象アプリの指定

`stacks/<app名>/docker-compose.yml` 側のサービスに `profiles:` を設定している場合のみ、
`.env` に `COMPOSE_PROFILES` を書いてログイン時に起動するアプリを制御できます。

```dotenv
COMPOSE_PROFILES=time-announcement
```

**注意:** 現状の `stacks/time-announcement` は `profiles:` を設定していないため、
`COMPOSE_PROFILES` を設定しても効果はなく、常に全アプリが起動します。
特定アプリだけ起動を制御したい場合は、まず対象の `stacks/<app名>/docker-compose.yml` に
`profiles:` を追加すること。
