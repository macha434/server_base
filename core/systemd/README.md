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

## アンインストール

```bash
cd core/systemd
./uninstall-service.sh
```

## 起動対象アプリの指定

`.env` に `COMPOSE_PROFILES` を書いておくと、ログイン時に起動するアプリを制御できます。

```dotenv
COMPOSE_PROFILES=time-announcement,nature
```
