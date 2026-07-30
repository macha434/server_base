# 06. 技術選定 — ゼロから作り直す前提での比較

- 前提: **server_base を 1 から作り直してよい**
- 目標: **アプリ側リポジトリを一切触らず、server_base にファイルを置くだけでアプリが増やせる**
- [04-alternatives.md](./04-alternatives.md) で並べた候補を、実際に選ぶための評価軸で比較する

## 0. 前提が変わったことによる影響

[01](./01-current-state.md)〜[05](./05-recommendation.md) は「既存の nginx 資産を活かす」前提だった。
**作り直してよいなら nginx の既得権は消える**ので、比較の土俵が変わる:

| 変わること | 影響 |
| --- | --- |
| 「既に nginx で動いている」が加点にならない | Traefik / Caddy が相対的に有利に |
| 「mkcert 証明書がある」は**変わらず全候補で流用可** | TLS は差がつかない軸になる |
| 「dnsmasq のワイルドカード DNS」も全候補で流用可 | 同上 |
| 設計を最初から決められる | **ネットワーク分離**を最初から仕込める（後付けは難しい）|

## 1. まず確認: 「1 ファイル置くだけ」は実現可能か → **可能**

実測で確認した（検証手順は[末尾](#実測検証-test12test23)）。
**アプリ 1 個 = `stacks/` に YAML 1 枚**という形が Compose だけで成立する。

`stacks/time-announcement.yml`（これ 1 枚でアプリ 1 個が完結する）:

```yaml
# アプリ側 compose を読み込む（相対パスは自動で正しく解決される）
include:
  - path: ../../time-announcement-frontend/deploy/docker-compose.yaml
    project_directory: ../../time-announcement-frontend/deploy

# 差分だけ上書きする
services:
  schedule-ui:
    networks: [webnet]        # プロキシから到達可能に
    ports: !reset []          # ホストへの publish を剥がす
    labels:                   # ルーティング定義（記法は採用する方式による）
      site.host: time.ubuntu.local
      site.port: "3000"

networks:
  webnet: { name: webnet, external: true }
```

起動側は glob で拾えるので、**ファイルを置くだけで本当に終わる**:

```bash
docker compose -p server-base $(printf -- '-f %s ' stacks/*.yml) up -d
```

> ⚠️ `include:` に glob（`./stacks/*.yml`）は**使えない**（実測 TEST13）。
> ルート `compose.yaml` に 1 行ずつ列挙するか、上記のようにシェル側で展開する。
> 後者なら本当に「置くだけ」になる。

**この時点で「1 ファイルで完結」は Compose 側の機能で確定する。**
つまり残る選択は「**そのラベルを誰が読んでルーティングするか**」だけになった。

## 2. 候補（[04](./04-alternatives.md) から選定 ＋ 1 案追加）

| | 方式 | ルーティング定義の置き場 | Docker socket |
| --- | --- | --- | --- |
| **A** | nginx ＋ 手書き vhost | 別ファイル（vhost conf）| 不要 |
| **A'** | **nginx ＋ ラベル駆動の生成スクリプト**（本調査で追加）| stacks の label | **不要** |
| **B** | Traefik（ラベル駆動）| stacks の label | 必要 |
| **C** | Caddy ＋ caddy-docker-proxy | stacks の label | 必要 |
| **D** | nginx-proxy（docker-gen）| stacks の env（`VIRTUAL_HOST`）| 必要 |
| **E** | Nginx Proxy Manager | GUI / DB | 不要 |
| **F** | Coolify / Dokploy | Web UI | 必要（フルアクセス）|

> **A' は [04](./04-alternatives.md) には無かった案。** 本調査中に実測で成立を確認した。
> `docker compose config --format json` の出力からラベルを読んで nginx conf を生成する。
> **Docker socket を触らずにラベル駆動を実現できる**のが肝（詳細は [3-A'](#a-nginx--ラベル駆動の生成スクリプト)）。

## 3. 評価軸ごとの詳細

指定された 4 軸（セキュリティ / 設定の簡易さ / 導入の簡易さ / キャッチアップ難易度）に、
実運用で効く 5 軸を追加した。

<a id="a-nginx--ラベル駆動の生成スクリプト"></a>

### A' nginx ＋ ラベル駆動の生成スクリプト

`scripts/gen-nginx-conf.py`（実測ベースの動作イメージ、40 行程度）:

```python
# docker compose config --format json の出力から site.* ラベルを拾って vhost を生成する。
# Docker デーモンにも socket にも触らない（compose ファイルを読むだけ）。
import json, subprocess, pathlib, glob

cfg = json.loads(subprocess.check_output(
    ["docker", "compose", "-p", "server-base",
     *sum([["-f", f] for f in sorted(glob.glob("stacks/*.yml"))], []),
     "config", "--format", "json"]))

tmpl = pathlib.Path("nginx/template/site.conf.template").read_text()
for name, svc in cfg["services"].items():
    lbl = svc.get("labels") or {}
    if "site.host" not in lbl:
        continue
    pathlib.Path(f"nginx/conf.d/{lbl['site.host']}.conf").write_text(
        tmpl.replace("__HOST__", lbl["site.host"])
            .replace("__SERVICE__", name)
            .replace("__PORT__", str(lbl["site.port"])))
```

| 軸 | 評価 |
| --- | --- |
| 🔒 **セキュリティ** | ⭐⭐⭐⭐⭐ **Docker socket 不要**。攻撃面は nginx 本体のみ。管理 UI も認証情報も持たない。生成は人間が明示的に実行する（デプロイ時のみ）ので、コンテナ起動が勝手に設定を書き換えることもない |
| ⚙️ **設定の簡易さ** | ⭐⭐⭐⭐⭐ アプリ追加は stacks に 1 枚。ラベル 2 行 |
| 🚀 **導入の簡易さ** | ⭐⭐⭐ 生成スクリプト（約 40 行）とテンプレートを最初に書く必要がある |
| 📚 **キャッチアップ** | ⭐⭐⭐⭐ nginx の知識がそのまま使える。スクリプトは自作なので**全部読める**（外部ツールの「なぜか効かない」が無い）|
| 💥 **影響範囲** | ⭐⭐⭐⭐ `resolver` 化しておけば 1 アプリ停止が他に波及しない。生成後 `nginx -t` で事前検証できる |
| 🔍 **デバッグ** | ⭐⭐⭐⭐⭐ 生成された conf が**そのまま読める**。差分も git diff で見える |
| 📦 **Git / IaC** | ⭐⭐⭐⭐⭐ 生成物もコミットすれば完全再現。レビュー可能 |
| 🚪 **撤退コスト** | ⭐⭐⭐⭐⭐ 生成をやめて手書きに戻すだけ。ロックインゼロ |
| 🔧 **メンテ負荷** | ⭐⭐⭐ nginx の CVE 追従のみ。ただし**自作スクリプトの保守は自分持ち** |

**メリット**: セキュリティと透明性が最高。「魔法」がなく、壊れたときに必ず原因まで辿れる。
**デメリット**: 自作コードを持つことになる。動的検出ではないので、**アプリ追加時に生成コマンドの実行を忘れると反映されない**（手順に組み込む必要あり）。

### B Traefik（ラベル駆動）

| 軸 | 評価 |
| --- | --- |
| 🔒 **セキュリティ** | ⭐⭐⭐ **Docker socket が必要**なのが最大の弱点。「/var/run/docker.sock をコンテナに渡すのは、そのコンテナに sudo root を与えるのと等価」。**socket-proxy で読み取り専用に絞れば ⭐⭐⭐⭐** まで回復する（後述）|
| ⚙️ **設定の簡易さ** | ⭐⭐⭐⭐⭐ stacks に 1 枚、ラベル 4 行。**追加即反映**（再起動もリロードも不要）|
| 🚀 **導入の簡易さ** | ⭐⭐⭐ Traefik 本体 ＋ static config ＋ 証明書設定 ＋ socket-proxy で初期構築はやや重い |
| 📚 **キャッチアップ** | ⭐⭐⭐ router / service / middleware / entrypoint / provider の概念整理が要る。**ただし情報量は圧倒的に多い**（この用途の事実上の標準）|
| 💥 **影響範囲** | ⭐⭐⭐⭐⭐ アプリ単位で独立。1 個の設定ミスが他に波及しない |
| 🔍 **デバッグ** | ⭐⭐ **ラベルのタイポが黙って無視される**のが辛い。ダッシュボードで確認する運用が必須 |
| 📦 **Git / IaC** | ⭐⭐⭐⭐⭐ 全部 YAML |
| 🚪 **撤退コスト** | ⭐⭐⭐⭐ ラベルを捨てるだけ。標準的な構成なので移行しやすい |
| 🔧 **メンテ負荷** | ⭐⭐⭐⭐ Go 製・活発にメンテ。実績豊富 |
| 🕸️ **ネットワーク分離** | ⭐⭐⭐⭐⭐ `traefik.docker.network` で**アプリごとに専用ネットワーク**にできる。フラットな共有ネットを避けられる |

**socket-proxy による緩和**（採用するなら必須）:

Traefik が Docker API に求めるのは**コンテナとネットワークの一覧・監視だけ**で、
作成・変更・削除の権限は不要。読み取り専用プロキシを挟めば、
Traefik が乗っ取られてもホスト root は取られない。

```yaml
services:
  socket-proxy:
    image: ghcr.io/wollomatic/socket-proxy:1   # Go 製・from-scratch イメージ
    command: ["-loglevel=info", "-allowfrom=traefik",
              "-allowGET=/v1\\..{1,2}/(version|containers/.*|events.*)"]
    volumes: ["/var/run/docker.sock:/var/run/docker.sock:ro"]
    networks: [socket-net]
  traefik:
    image: traefik:v3
    command: ["--providers.docker.endpoint=tcp://socket-proxy:2375"]
    networks: [socket-net, webnet]
    # docker.sock は一切マウントしない
```

古典的には [tecnativa/docker-socket-proxy](https://hub.docker.com/r/tecnativa/docker-socket-proxy)、
2023 年 10 月以降は Go 製で軽量な [wollomatic/socket-proxy](https://github.com/wollomatic/socket-proxy) が推奨されている。

**メリット**: この問題領域の事実上の標準解。1 ファイル・即反映・ネットワーク分離が自然。将来 middleware（BASIC 認証、レート制限、IP 制限）を足したくなったときの伸びしろが大きい。
**デメリット**: socket 依存。設定ミスが黙殺される。概念の学習コスト。

### C Caddy ＋ caddy-docker-proxy

| 軸 | 評価 |
| --- | --- |
| 🔒 セキュリティ | ⭐⭐⭐ B と同じく socket 必要。Caddy 本体は Go でメモリ安全 |
| ⚙️ 設定の簡易さ | ⭐⭐⭐⭐⭐ Caddyfile 記法は全候補で最も読みやすい |
| 🚀 導入の簡易さ | ⭐⭐⭐⭐ 本体は非常に簡単 |
| 📚 キャッチアップ | ⭐⭐⭐⭐ 記法が直感的 |
| 🔧 メンテ負荷 | ⭐⭐ **`caddy-docker-proxy` は個人メンテのサードパーティプラグイン**。開発は活発だがバス係数リスクあり。Caddy 本体の更新に追従できないと詰む |
| 🔐 `.local` との相性 | ⭐⭐ **Caddy 最大の売りである自動 HTTPS が `.local` では活きない**（Let's Encrypt が使えない）。内部 CA の手動設定が必要で、優位性が消える |

**評価**: ゼロから作るなら有力だが、**今回は Caddy の主武器が封じられる**。
プラグイン依存のリスクを負ってまで選ぶ理由が弱い。

### D nginx-proxy（docker-gen）

| 軸 | 評価 |
| --- | --- |
| 🔒 セキュリティ | ⭐⭐⭐ socket 必要 |
| ⚙️ 設定の簡易さ | ⭐⭐⭐⭐ `VIRTUAL_HOST` / `VIRTUAL_PORT` の環境変数 2 つ。ただし**ラベルより表現力が低い**（複雑なルーティングができない）|
| 🚀 導入の簡易さ | ⭐⭐⭐⭐ 非常に簡単 |
| 📚 キャッチアップ | ⭐⭐⭐⭐ 覚えることが少ない |
| 🔧 メンテ負荷 | ⭐⭐⭐ ZeroSSL が公式にメンテしているが、**開発速度の停滞を懸念する声**もある |

**評価**: A'（自作生成）の「動的版」に相当するが、**socket を要求する分 A' の下位互換**になる。
A' を選べるなら D を選ぶ理由がない。

### E Nginx Proxy Manager — ❌ 除外推奨

| 軸 | 評価 |
| --- | --- |
| 🔒 セキュリティ | ⭐ **CVE-2026-40519（認証済み RCE、OS コマンドインジェクション）**。`child_process.exec()` にユーザー入力を文字列補間しており、**Docker では通常 root で実行される**。OpenCVE 追跡で 7 件の CVE、公式イメージのスキャンで 400 件超の脆弱性（うち相当数が CVSS 9.0 超）。過去にも CVE-2024-46256（Let's Encrypt 証明書追加機能経由の RCE）|
| 📦 Git / IaC | ⭐ 設定が**DB の中**。Git 管理・レビュー・再現性が全部失われる |
| 🔧 メンテ負荷 | ⭐⭐ 「反応的であって予防的ではない」セキュリティ姿勢との評価 |

**評価**: 「GUI で簡単」は魅力だが、**セキュリティ実績と IaC 適合性の両方で落第**。
現在のリポジトリ駆動の運用思想とも根本的に合わない。除外。

### F Coolify / Dokploy — 今回は見送り

| 軸 | 評価 |
| --- | --- |
| 🔒 セキュリティ | ⭐⭐ **Coolify は 2026 年 1 月に critical 11 件**を公表（v4.0.0 で修正）。「低権限の認証済みユーザーが到達できる攻撃面が広すぎた」。Dokploy も v0.29.3 で脆弱性修正。**両者とも Docker socket にフルアクセス**（デプロイする以上必然）。管理画面をインターネットに晒すのは厳禁 |
| ⚙️ 設定の簡易さ | ⭐⭐⭐⭐⭐ UI から追加。**「簡単さ」だけなら最強** |
| 🚀 導入の簡易さ | ⭐⭐ 基盤ごと乗り換える判断になる |
| 📚 キャッチアップ | ⭐⭐⭐ UI は簡単だが、内部（Traefik）を理解しないとトラブル時に詰む |
| 🚪 撤退コスト | ⭐⭐ プラットフォームに乗る。抜けるのは大仕事 |
| 💾 リソース | Coolify: アイドル 500MB〜1.2GB / 推奨 2vCPU・4GB。Dokploy: アイドル 300〜400MB / 1vCPU・2GB |

**評価**: 「アプリ追加の摩擦をゼロにする」目的への完成度は最も高い。
ただし**今回は「1 ファイル置くだけ」が Compose 単体で達成できてしまった**ので、
PaaS を導入する主要な動機が消えている。アプリが 10 個規模になり自作基盤の維持が
つらくなった時点で再検討する話。その際は既存 compose をそのまま扱える **Dokploy** が素直。

## 4. 総合比較表

| 軸 | A 手書き nginx | **A' nginx＋生成** | **B Traefik** | C Caddy | D nginx-proxy | E NPM | F PaaS |
| --- | :-: | :-: | :-: | :-: | :-: | :-: | :-: |
| 🔒 セキュリティ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐※ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐ | ⭐⭐ |
| ⚙️ 設定の簡易さ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| 🚀 導入の簡易さ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ |
| 📚 キャッチアップ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |
| 💥 影響範囲 | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ |
| 🔍 デバッグ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ |
| 📦 Git / IaC | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐ |
| 🚪 撤退コスト | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐ |
| 🔧 メンテ負荷 | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐ |
| 🕸️ NW 分離 | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ |
| 🔐 `.local` 相性 | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐ |
| 🤖 AI エージェント相性 | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐⭐ |
| **1 アプリの追加コスト** | 2 ファイル | **1 ファイル** | **1 ファイル** | 1 ファイル | 1 ファイル | GUI 操作 | GUI 操作 |

※ socket-proxy 併用時。生の `docker.sock` をマウントするなら ⭐⭐。

> 🤖 の軸を入れた理由: このリポジトリは `.claude/` と APM で Claude Code を
> 前提にした運用をしている。**設定がテキストファイルである方が AI に扱わせやすく、
> GUI / DB に入る方式は自動化の対象外になる**。E・F が特に不利。

## 5. 推奨

### 第一候補: **A' — nginx ＋ ラベル駆動の生成スクリプト**

理由:

1. **「1 ファイル置くだけ」が Docker socket なしで達成できる唯一の案。**
   今回のアプリ（time-announcement-frontend）は**ファイルアップロード機能を持つ
   Next.js アプリ**（`UploadDropzone` / `/api/tracks`）で、外部入力を扱う。
   仮にこれが踏み台にされた場合、**同じネットワーク上に socket 接続された
   プロキシが居ると、ホスト root への昇格経路になる**。
   socket を最初から持たない構成なら、この経路自体が存在しない。
2. **デバッグ可能性が最高。** 生成された nginx conf がそのまま読め、`git diff` で
   変更が見え、`nginx -t` で反映前に検証できる。Traefik の「ラベルのタイポが
   黙って無視される」が構造的に起きない。
3. **自作スクリプトの保守コストは、この構成では小さい。** 約 40 行で、
   やっていることは JSON からラベルを読んでテンプレートに埋めるだけ。
   Claude Code で保守する前提なら十分に扱える範囲。

### 対抗: **B — Traefik ＋ socket-proxy**

以下に当てはまるなら、こちらが優る:

- **自作コードを一切持ちたくない**（枯れた既製品だけで組みたい）
- **将来 BASIC 認証・レート制限・IP 制限・メトリクスを足したい**
  （middleware が標準で揃っている。A' だと nginx 設定を自分で書くことになる）
- **アプリごとにネットワークを分離したい**
  （`traefik.docker.network` で自然にできる。A' でも可能だが nginx を各ネットワークに
  繋ぐ手作業が増える）
- 「アプリを起動したら即座にルートが生える」動的検出に価値を感じる
  （A' は生成コマンドの実行を手順に組み込む必要がある）

採用する場合は **socket-proxy を必須**とし、生の `docker.sock` は絶対にマウントしない。

### 見送り

| | 理由 |
| --- | --- |
| A（手書き nginx）| A' の下位互換。生成スクリプトを書かない理由がない |
| C（Caddy）| `.local` で自動 HTTPS が活きず主武器が封じられる ＋ プラグインのバス係数リスク |
| D（nginx-proxy）| socket を要求する分 A' の下位互換 |
| E（NPM）| セキュリティ実績（RCE 複数）と IaC 非適合で落第 |
| F（PaaS）| 「1 ファイル置くだけ」が Compose 単体で達成できたため導入動機が消失。将来の再検討候補（Dokploy）|

### どちらを選んでも共通で決めておくこと

1. **アプリごとに専用ネットワークを切る**（[6 章](#6-ネットワーク分離の設計第一候補に組み込む)）。
   フラットな共有網（`webnet`）は作らない
2. **アプリのホストポート publish は `ports: !reset []` で必ず剥がす** —
   TLS バイパスの穴とポート採番の管理が同時に消える
3. **`aliases` で一意な upstream 名を与える** — nginx は全網に参加するため、
   アプリ側のサービス名が `web` / `app` のような一般名だと nginx 側で衝突する
4. **アプリのクローン先を相対パスで固定する**（`include` が相対パス依存のため）
5. `.local` である以上 Let's Encrypt は使えない。**mkcert 証明書を全候補で流用する**

---

## 6. ネットワーク分離の設計（第一候補に組み込む）

「Traefik のアプリごとネットワーク分離のメリットも欲しい」への回答。
**分離は実現できる。ただし server_base をアプリごとに作る必要はない。**

### 「アプリごとに server_base を作る」案が成立しない理由

| 問題 | 内容 |
| --- | --- |
| 🔴 **ポートの奪い合い** | nginx は `:80` / `:443` を bind する。ホスト上でこれを bind できるプロセスは**1 つだけ**。server_base を N 個作ると N 個目の nginx が起動できない |
| 🔴 **回避しても本末転倒** | 各 server_base を別ポートにすると `https://time.ubuntu.local:8443` のような URL になり、名前ベース vhost の利点が消える。前段にルーターを置くなら、**そのルーターが全アプリ網に参加する必要があり、結局「1 つのプロキシが N 網に繋がる」形に戻る**（＋ホップが 1 段増えるだけ）|
| 🟡 **重複コスト** | 証明書・dnsmasq・systemd unit・更新作業が N 重になる |

### 正しい形: **nginx 1 個 × アプリごとネットワーク N 個**

Docker のコンテナは**複数ネットワークに同時参加できる**。Traefik が
`traefik.docker.network` でやっているのもこれで、プロキシを分けているわけではない。

```
                    ┌─────────────────┐
                    │  nginx (1個)     │ :80 / :443
                    └────┬───────┬────┘
        net-time-announcement   net-nature      ← アプリごとに専用ネットワーク
                 │                  │
        ┌────────▼───────┐  ┌───────▼──────┐
        │ schedule-ui    │  │ nature       │
        └────────────────┘  └──────────────┘
             ✗ この2つは互いに到達不可 ✗
```

各ネットワークの参加者は **{nginx, そのアプリ}** だけ。
アプリ同士は相互に到達できない。**`webnet`（フラットな共有網）は廃止する。**

### 「1 ファイル 1 アプリ」は維持できる

ネットワーク定義と nginx の参加宣言を**同じ stacks ファイルに書ける**ため、
追加コストはゼロ。実測で確認済み（TEST19）:

```yaml
# stacks/time-announcement.yml ← これ1枚のまま
include:
  - path: ../../time-announcement-frontend/deploy/docker-compose.yaml
    project_directory: ../../time-announcement-frontend/deploy

services:
  schedule-ui:
    networks:
      net-time-announcement:
        aliases: [time-announcement]   # 一意な名前を明示（後述）
    ports: !reset []
    labels:
      site.host: time.ubuntu.local
      site.upstream: time-announcement
      site.port: "3000"

  # 同じファイルで nginx をこのアプリ専用網に参加させる
  nginx:
    networks: [net-time-announcement]

networks:
  net-time-announcement:
    name: net-time-announcement
```

サービス直下の `networks` はファイル間で**連結マージ**されるので、
stacks を増やすたびに nginx の参加網が自動的に積み上がる。実測結果:

```yaml
  nginx:
    networks:
      net-nature: null                 # ← stacks/nature.yml から
      net-time-announcement: null      # ← stacks/time-announcement.yml から
  nature:
    networks:
      net-nature: null                 # ← nature は自分の網だけ ✅
  schedule-ui:
    networks:
      net-time-announcement: null      # ← schedule-ui も自分の網だけ ✅
```

### 副次的に解決する問題: サービス名の衝突

[02](./02-compose-modularization.md) で挙げた「共有網ではサービス名がネットワーク
エイリアスになるため `web` / `app` のような一般名が衝突する」問題は、
網が分かれることで**アプリ同士では起きなくなる**。

ただし **nginx は全網に参加している**ため、nginx から見た名前解決では依然として
衝突しうる。そこで上記のように `aliases` で一意な名前を与え、
生成スクリプトは `site.upstream` ラベルを見る（無ければサービス名にフォールバック）:

```
nature.ubuntu.local      -> http://nature:3001
time.ubuntu.local        -> http://time-announcement:3000
```

これでアプリ側のサービス名が何であっても衝突しない。

### 注意点

| 項目 | 内容 |
| --- | --- |
| **ネットワーク数の上限** | Docker の既定アドレスプールは `172.17.0.0/16`〜`172.31.0.0/16` ＋ `192.168.0.0/20`〜`192.168.240.0/20`。既定設定では**ブリッジ網は約 32 個が上限**。家庭内サーバーの規模なら十分だが、枯渇したら `daemon.json` の `default-address-pools` で `/12` ベース・`/24` 刻みにすれば 256 網まで拡張できる |
| **アプリ間通信が必要になったら** | 同じ網に入れる。**stacks ファイルの単位は「1 アプリ」ではなく「1 つの網＝1 つの信頼境界」**と捉え直すのが正しい（下記）|
| 🔴 **アプリ側の全サービスを網羅する必要がある** | サービス単位で `networks` を上書きする方式のため、**stacks で言及していないサービスは `default` に落ちる**。アプリ側が後から DB 等を追加すると、本体（専用網）と DB（`default`）が分断され**アプリが壊れる**。実測済み（TEST21）。対策は下記 |
| **`resolver` は据え置き** | 分離しても [03 の `resolver` ＋ 変数 `proxy_pass`](./03-nginx-modularization.md#level-2--resolver--変数-proxy_pass-で起動時依存を断つ) は必須。むしろ網が増えるぶん、起動時依存を切っておく価値が上がる |

### 複数アプリを同じ網に入れたくなったら

**stacks ファイルの単位は「1 アプリ」ではなく「1 つの網＝1 つの信頼境界」。**
最初はたまたま 1 網 1 アプリなだけで、複数アプリを同居させるのは設計の逸脱ではない。
方法は 2 つあり、どちらも実測で成立を確認した。

#### 方法1: 1 つの stack ファイルに複数リポジトリを include する（推奨）

`include` はリストなので、1 ファイルから複数のアプリリポジトリを取り込める（TEST22）。

```yaml
# stacks/time-announcement.yml ← 「時報プロダクト一式」という単位のファイル
include:
  - path: ../../time-announcement-frontend/deploy/docker-compose.yaml
    project_directory: ../../time-announcement-frontend/deploy
  - path: ../../time-announcement-backend/deploy/docker-compose.yaml
    project_directory: ../../time-announcement-backend/deploy

services:
  schedule-ui:
    networks: { net-time-announcement: { aliases: [front] } }
    ports: !reset []
  announcer:
    networks: { net-time-announcement: { aliases: [back] } }
  nginx:
    networks: [net-time-announcement]

networks:
  net-time-announcement:
    name: net-time-announcement
```

- ✅ **信頼境界がファイル 1 枚に閉じて見える。** 誰と誰が通信可能かが一目でわかる
- ✅ ファイルを消せばグループごと消える
- ⚠️ 「1 ファイル = 1 アプリ」の対応は崩れる（が、そもそも単位は網なので問題ない）

**time-announcement は frontend と backend が named volume を共有する 1 プロダクト**なので、
このケースはまさに方法 1 が適切。

#### 方法2: ファイルは分けたまま、同じ網名を宣言する

別ファイルが同じ網名を宣言しても正しくマージされる（TEST23）。

```yaml
# stacks/ta-back.yml
services:
  announcer:
    networks: { net-time-announcement: { aliases: [back] } }
networks:
  net-time-announcement:
    name: net-time-announcement      # 別ファイルと同じ名前 → 同じ網に合流
```

- ✅ 1 ファイル 1 アプリの粒度を保てる
- ⚠️ **結合が暗黙的になる。** 誰が同じ網にいるかは grep しないとわからない。
  採用するなら各ファイルの冒頭コメントで相互参照を書くこと

#### 共通の注意

- **分離の粒度＝ stack の粒度。** 同居させた 2 つは相互に到達可能になる。
  「便利だから」で安易に同居させると、[6 章冒頭](#6-ネットワーク分離の設計第一候補に組み込む)で得た分離のメリットが薄れる
- 同一網内では**サービス名の衝突が復活する**ため、`aliases` で一意名を与える運用が必須

### 「アプリ側がサービスを増やす」問題への対策

アプリ側リポジトリは改変しない＝**こちらの都合でサービス構成を固定できない**。
`schedule-ui` だけを上書きしている状態でアプリ側が `db` を足すと、こうなる（TEST21）:

```yaml
  db:
    networks:
      default: null      # 🔴 sb_default に落ちる
  schedule-ui:
    networks:
      net-app: null      # 🔴 別網。db に到達できずアプリが壊れる
```

対策は 2 案。

**案 A（推奨）: 単一プロジェクトのまま、生成スクリプトに検査を入れる**

`default` に所属したままのサービスが 1 つでもあれば**エラーで止める**。
アプリ側の構成変更に気づけないまま壊れるのを防げる。

```python
orphans = [n for n, s in cfg["services"].items()
           if "default" in (s.get("networks") or {})]
if orphans:
    raise SystemExit(
        f"専用網に載っていないサービスがあります: {orphans}\n"
        f"アプリ側が構成を変更した可能性があります。stacks/*.yml に追記してください。")
```

- 利点: 1 ファイル・1 コマンドの運用を維持できる
- 欠点: アプリ側が増えるたびに stacks へ追記する手作業が残る（ただし**気づけないまま壊れることはなくなる**）

**案 B: アプリごとに別 Compose プロジェクトとして起動する**

プロジェクトが分かれれば `default` もアプリごとに独立するので、
[02 で「composition root では使うな」とした `networks.default` の差し替え](./02-compose-modularization.md#test11--default-差し替えの漏れと安全な書き方-)が
**この構成では逆に正解になる**。アプリ側が何個サービスを増やしても全部が専用網に載る。

```yaml
# stacks/time-announcement.yml （アプリ単独プロジェクトとして起動する場合）
networks:
  default:
    name: net-time-announcement
    external: true          # docker network create で先に作っておく
```

- 利点: **アプリ側のサービス追加に自動で追従する**（列挙不要）
- 欠点: nginx 側（server_base プロジェクト）に `net-*` を external として列挙する必要があり、
  **1 アプリ = 2 箇所**になる。起動コマンドもアプリごとに分かれる

**判断**: まずは案 A で始める。アプリ側の構成変更が頻繁で追記が負担になったら案 B へ移す。
案 A の検査があれば、案 B へ移すべきタイミングも自然に検知できる。

### これで Traefik との差はどうなるか

| | Traefik | **A' ＋ 網分離** |
| --- | :-: | :-: |
| アプリごとネットワーク分離 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ **同等** |
| Docker socket | 必要 | **不要** |
| 1 アプリの追加コスト | 1 ファイル | **1 ファイル** |

[4 の総合比較表](#4-総合比較表)で A' が Traefik に唯一負けていた「🕸️ NW 分離」の軸が
**⭐⭐⭐ → ⭐⭐⭐⭐⭐ に並ぶ**。Traefik を選ぶ理由は
「自作コードを持ちたくない」「middleware の伸びしろが欲しい」の 2 点に絞られる。

---

## 実測検証 (TEST12〜TEST23)

Compose v5.3.1 / Docker 29.6.2、`docker compose config`（デーモン不要）で確認。

| # | 検証内容 | 結果 |
| --- | --- | --- |
| TEST12 | 1 ファイル内で `include` ＋ 同サービスの上書きが両立するか | ✅ 成立。`build.context` も正しく解決 |
| TEST13 | `include:` に glob（`./stacks/*.yml`）が使えるか | ❌ **不可**（`no such file or directory`）|
| TEST14 | 2 アプリが各々 `webnet` external を宣言して衝突しないか | ✅ 衝突なし |
| TEST15 | シェルで glob 展開した `-f` 列挙で全アプリを合成できるか | ✅ 成立。相対パスも保たれる |
| TEST16 | `COMPOSE_FILE` 環境変数でも同等か | ✅ 成立 |
| TEST17 | サービス直下の `x-` 拡張フィールドが `config` 出力に残るか | ❌ **除去される** |
| TEST18 | `labels` は残り、そこからルーティング定義を抽出できるか | ✅ 成立（**A' の成立根拠**）|
| TEST19 | nginx 1 個をアプリごとの専用網 N 個に参加させ、アプリ同士を分離できるか | ✅ 成立。サービス直下の `networks` はファイル間で連結マージされる。**stacks ファイルが base（`-f` の先頭）でなくても `include` の相対パス解決は保たれた** |
| TEST20 | `aliases` で一意な upstream 名を与えられるか | ✅ 成立（**サービス名衝突の恒久対策**）|
| TEST21 | stacks で言及していないサービス（アプリ側が後から追加した DB 等）はどうなるか | 🔴 **`default` に落ちて本体から分断される**。検査が必要 |
| TEST22 | 1 つの stack ファイルから複数リポジトリを include し、同一網に入れられるか | ✅ 成立 |
| TEST23 | 別々の stack ファイルが同じ網名を宣言して合流できるか | ✅ 成立 |

TEST17 が失敗したため、A' のメタデータ置き場は `x-` ではなく **`labels` を使う**必要がある。
（ラベルは Traefik / caddy-docker-proxy とも同じ置き場なので、**後から B・C へ乗り換える際も
stacks ファイルの構造を変えずに済む**という副次的な利点がある。）

再現コマンド:

```bash
docker compose -p server-base $(printf -- '-f %s ' stacks/*.yml) config --format json \
  | python3 -c "
import json,sys
d = json.load(sys.stdin)
for name, svc in sorted(d['services'].items()):
    lbl = svc.get('labels') or {}
    if 'site.host' in lbl:
        print(f\"{lbl['site.host']} -> http://{name}:{lbl['site.port']}\")
"
```

出力例:

```
nature.ubuntu.local -> http://nature:3001
time.ubuntu.local -> http://schedule-ui:3000
```

## 参考

- [Docker Socket Proxy — Secure API Access Without Giving Away Root](https://blog.gntech.me/posts/2026-05-14-docker-socket-proxy/)
- [wollomatic/socket-proxy](https://github.com/wollomatic/socket-proxy) / [tecnativa/docker-socket-proxy](https://hub.docker.com/r/tecnativa/docker-socket-proxy)
- [traefik#4174 — Exposing Docker socket to Traefik is a serious security risk](https://github.com/traefik/traefik/issues/4174)
- [20 Docker Security Best Practices - Hardening Traefik Docker Stack](https://www.simplehomelab.com/traefik-docker-security-best-practices/)
- [CVE-2026-40519: Nginx Proxy Manager RCE](https://www.sentinelone.com/vulnerability-database/cve-2026-40519/) / [ZeroPath 解説](https://zeropath.com/blog/cve-2026-40519-nginx-proxy-manager-authenticated-rce)
- [CVE-2024-46256: Nginx Proxy Manager RCE](https://www.sentinelone.com/vulnerability-database/cve-2024-46256/)
- [Nginx Proxy Manager CVE 一覧 (OpenCVE)](https://app.opencve.io/cve/?product=nginx_proxy_manager&vendor=nginxproxymanager)
- [Coolify vs Dokploy: Self-Hosted PaaS Compared (CVEs, License, Sizing)](https://cloudzy.com/blog/coolify-vs-dokploy/)
- [lucaslorentz/caddy-docker-proxy](https://github.com/lucaslorentz/caddy-docker-proxy)
- [nginx-proxy/docker-gen releases](https://github.com/nginx-proxy/docker-gen/releases)
