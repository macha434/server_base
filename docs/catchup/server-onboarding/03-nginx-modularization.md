# 03. nginx 設定のモジュール化

Compose 側を解決しても、vhost 設定 65 行を書く作業は残る。nginx にも「モジュール化」の
段階があるので、コストとリターンで 4 レベルに整理した。

| Level | 手法 | 1 アプリあたり | 追加依存 | 推奨 |
| --- | --- | --- | --- | --- |
| 0 | 現状（丸ごとコピペ）| 約 65 行 | なし | — |
| 1 | `include` で snippet 化 | 約 15 行 | なし | ✅ すぐやる |
| 2 | Level 1 ＋ `resolver` ＋ 変数 `proxy_pass` | 約 15 行 ＋ **起動時依存が消える** | なし | ✅ すぐやる |
| 3 | 正規表現 `server_name` ＋ `map` | **1 行** | なし | ⚠️ 制約あり・Level 2 の次の一手 |

## Level 1 — `include` で共通部分を snippet 化

nginx の `include` ディレクティブ（[ngx_core_module](https://nginx.org/en/docs/ngx_core_module.html#include)）:

```
Syntax:  include file | mask;
Context: any
```

- **任意のコンテキストで使える**（`http`, `server`, `location` の中でも可）
- **glob マスクをサポート**（`include vhosts/*.conf;`）
- glob は**再帰しない**
- 相対パスは nginx の prefix（公式イメージでは `/etc/nginx`）基準

### 重要な性質

公式 nginx イメージの `nginx.conf` は `http {}` の中で `include /etc/nginx/conf.d/*.conf;` を
実行する。この glob は**サブディレクトリを辿らない**ので、
**`conf.d/snippets/` に置いたファイルは自動ロードされない**。
= snippet 置き場として `conf.d/snippets/` はそのまま使える（別マウントを増やさなくてよい）。

### 構成案

```
nginx/conf.d/
├── snippets/
│   ├── ssl.conf          # 証明書・プロトコル・暗号スイート・セッション
│   ├── security.conf     # セキュリティヘッダ 4 種
│   └── proxy.conf        # proxy_set_header ＋ WebSocket
├── default.conf
├── nature.conf
└── time-announcement.conf
```

`snippets/ssl.conf`:

```nginx
ssl_certificate     /etc/nginx/ssl/ubuntu.local-cert.pem;
ssl_certificate_key /etc/nginx/ssl/ubuntu.local-key.pem;

ssl_protocols             TLSv1.2 TLSv1.3;
ssl_ciphers               HIGH:!aNULL:!MD5;
ssl_prefer_server_ciphers on;
ssl_session_cache         shared:SSL:10m;
ssl_session_timeout       10m;
```

`snippets/security.conf`:

```nginx
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
add_header X-Frame-Options           "SAMEORIGIN" always;
add_header X-Content-Type-Options    "nosniff" always;
add_header X-XSS-Protection          "1; mode=block" always;
```

`snippets/proxy.conf`:

```nginx
proxy_set_header Host              $host;
proxy_set_header X-Real-IP         $remote_addr;
proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
proxy_set_header X-Forwarded-Proto $scheme;

# WebSocket
proxy_http_version 1.1;
proxy_set_header Upgrade    $http_upgrade;
proxy_set_header Connection $connection_upgrade;
```

> ⚠️ `add_header` の継承規則に注意。**下位ブロックで `add_header` を 1 つでも書くと、
> 上位ブロックの `add_header` はすべて無効化される**。snippet を `server` で
> include したうえで `location` にも `add_header` を書くと、セキュリティヘッダが
> 消える。`location` 側では `add_header` を書かないか、書くなら snippet も
> 再 include すること。

> ⚠️ `Connection "upgrade"` を固定値で書くと、WebSocket を使わない通常リクエストにも
> `Connection: upgrade` が付いてしまう。現行 `nature.conf` はこの形。
> `http {}` に `map` を置いて振り分けるのが定石:
>
> ```nginx
> map $http_upgrade $connection_upgrade {
>     default upgrade;
>     ''      close;
> }
> ```
>
> ただし `map` は `http` コンテキスト専用で `conf.d/*.conf` の中には書けるが
> `server` の外に置く必要がある。`conf.d/00-maps.conf` のような専用ファイルを作る。

## Level 2 — `resolver` ＋ 変数 `proxy_pass` で起動時依存を断つ

[01 の B3](./01-current-state.md#b3--static-upstream-による起動時依存) の解決。
**これが「サーバーを気軽に足す」ために一番効く変更**かもしれない。

### 何が起きているか

`upstream { server nature:3001; }` も `proxy_pass http://nature:3001;` も、
ホスト名を**設定ロード時**に解決する。解決できなければ nginx は起動しない。

**nginx は `proxy_pass` の引数に変数が含まれる場合だけ、リクエスト時に解決する。**
この挙動を使って起動時依存を外す。

### 書き方

```nginx
server {
    listen 443 ssl;
    http2 on;
    server_name time.ubuntu.local;

    include snippets/ssl.conf;
    include snippets/security.conf;

    # Docker 組み込み DNS。ipv6=off は必須（Docker DNS は A のみ返すため）
    resolver 127.0.0.11 valid=10s ipv6=off;

    location / {
        set $upstream http://schedule-ui:3000;
        proxy_pass $upstream;
        include snippets/proxy.conf;
    }
}
```

これで:

- アプリコンテナが落ちていても **nginx は起動する**（そのアプリだけ 502 になる）
- アプリを再作成して IP が変わっても `valid=10s` で追従する
- **アプリ N+1 個目の追加が、既存 N 個を巻き添えにしない**

### 落とし穴

1. **URI 書き換えの挙動が変わる。**
   `proxy_pass http://backend/;`（末尾スラッシュあり）は location のプレフィックスを
   剥がして転送するが、**変数を使うとこの「置換」動作が働かず、リクエスト URI が
   そのまま渡る**。ルート `location /` に対して使うぶんには実害がないが、
   `location /api/` のようなサブパスを剥がしたい場合は明示的に書く:

   ```nginx
   location /api/ {
       set $upstream http://schedule-ui:3000;
       rewrite ^/api/(.*)$ /$1 break;
       proxy_pass $upstream;
   }
   ```

2. **`ipv6=off` を忘れると解決に失敗しがち。** Docker の埋め込み DNS は
   IPv4（A レコード）中心で、nginx は既定で AAAA も引きにいく。
3. **`resolver` は `http` / `server` / `location` コンテキストで有効。**
   全 vhost で使うなら `conf.d/00-maps.conf` などで `http` レベルに一度書けば済む
   （ただし公式イメージの `nginx.conf` は `conf.d/*.conf` を `http {}` 内で
   include するので、`server` の外に書けば `http` コンテキストになる）。
4. **`upstream` ブロックの機能（負荷分散・`keepalive`・ヘルスチェック）は使えなくなる。**
   家庭内 LAN で 1 コンテナ 1 アプリなら問題ない。負荷分散が要るなら
   Level 2 を使わず `upstream` のままにするか、商用 NGINX Plus の
   `resolve` パラメータ、あるいは [nginx-upstream-dynamic-servers](https://github.com/skaravad/nginx-upstream-dynamic-servers)
   のようなサードパーティモジュールが必要。

参考:
[How to reduce Nginx 502 errors with dynamic domain name resolution](https://ypereirareis.github.io/blog/2020/02/18/how-to-reduce-nginx-502-bad-gateway-errors-risks-with-dynamic-domain-name-resolution/) /
[nginx proxy pitfalls](https://github.com/DmitryFillo/nginx-proxy-pitfalls) /
[Docker Nginx: How to Prevent "Host Not Found" Error](https://prds98.com/post/49/)

### Level 1 ＋ 2 適用後の 1 アプリ分の設定

```nginx
# nginx/conf.d/time-announcement.conf
server {
    listen      443 ssl;
    listen [::]:443 ssl;
    http2 on;
    server_name time.ubuntu.local;

    include snippets/ssl.conf;
    include snippets/security.conf;

    location / {
        set $upstream http://schedule-ui:3000;
        proxy_pass $upstream;
        include snippets/proxy.conf;
    }
}

server {
    listen      80;
    listen [::]:80;
    server_name time.ubuntu.local;
    return 301 https://$host$request_uri;
}
```

**65 行 → 22 行**、うち可変部分は `server_name` と `set $upstream` の 2 行だけ。
ここまで来ればテンプレートが実用になる（`sed` 2 箇所で新規アプリ用が作れる）。

> 補足: `listen 443 ssl http2;` は nginx 1.25.1 で deprecated になり、
> `listen 443 ssl;` ＋ `http2 on;` が正しい書き方。現行の `default.conf` /
> `nature.conf` は旧記法なので、`nginx:latest` の更新で警告が出る。
> snippet 化のタイミングで直しておくとよい。

## Level 3 — 正規表現 `server_name` ＋ `map` で 1 アプリ 1 行

究極形。**vhost ファイルを 1 枚だけにして、サブドメイン → upstream の対応表を持つ。**

`conf.d/00-maps.conf`:

```nginx
map $http_upgrade $connection_upgrade {
    default upgrade;
    ''      close;
}

# ← サーバーを追加するときはここに 1 行足すだけ
map $subdomain $app_upstream {
    default           "";
    nature            "nature:3001";
    time              "schedule-ui:3000";
}
```

`conf.d/wildcard.conf`:

```nginx
server {
    listen      443 ssl;
    listen [::]:443 ssl;
    http2 on;
    server_name ~^(?<subdomain>[^.]+)\.ubuntu\.local$;

    include snippets/ssl.conf;
    include snippets/security.conf;

    resolver 127.0.0.11 valid=10s ipv6=off;

    location / {
        if ($app_upstream = "") { return 404; }
        set $upstream http://$app_upstream;
        proxy_pass $upstream;
        include snippets/proxy.conf;
    }
}

server {
    listen      80;
    listen [::]:80;
    server_name ~^[^.]+\.ubuntu\.local$;
    return 301 https://$host$request_uri;
}
```

**アプリ追加＝ `map` に 1 行。** nginx conf を新規作成する必要すらなくなる。

### 制約・注意

- **アプリごとの個別設定ができない。** `client_max_body_size`（音声ファイルの
  アップロードがあるアプリでは必要）、タイムアウト、認証、キャッシュなどを
  アプリ単位で変えたくなった時点でこの形は破綻する。
  → 「共通で済むアプリは `map`、個別設定が要るものだけ専用 conf を置く」
  ハイブリッドにできる（専用 `server` ブロックの方が正規表現 `server_name` より
  優先されるため、共存可能）。
- **`server_name` の正規表現は完全一致の後に評価される。** 個別 vhost を書けば
  そちらが勝つので、段階移行しやすい。
- `if` は nginx では非推奨扱いだが、`return` との組み合わせは公式に安全とされる
  ケースなので問題ない。
- サブドメインは 1 階層のみ（証明書のワイルドカードが 1 レベルまでなので整合する）。

参考:
[Resolving subdomains dynamically via Nginx](https://codex.so/resolving-subdomains-dynamically-via-nginx) /
[Multi-Tenancy in Nginx](https://serversforhackers.com/c/nginx-multi-tenancy) /
[Nginx Server_name Wildcard or Catch-all](https://betterstack.com/community/questions/nginx-server-name-wildcard-or-catchall/)

## reload 運用について

設定を足したあとの反映は、現在 README が案内している `restart` より
**`nginx -s reload` の方が無停止**でよい。ただし Level 2 を入れる前は、
他アプリが落ちていると `nginx -t` が失敗して reload できない
（＝ Level 2 が reload 運用の前提条件でもある）。

```bash
docker compose -f nginx/docker-compose.yml exec nginx nginx -t \
  && docker compose -f nginx/docker-compose.yml exec nginx nginx -s reload
```

## まとめ

- Level 1（snippet 化）と Level 2（`resolver` 化）は**追加依存ゼロ・すぐ効く・低リスク**。
  先にこれをやるべき。65 行 → 22 行、かつ nginx の起動が他アプリに依存しなくなる。
- Level 3（`map`）は 1 行運用まで行けるが、アプリ個別設定を捨てることになる。
  共通で済むものだけ `map`、特殊なものは専用 conf のハイブリッドが現実的。
- ここまで nginx を頑張るなら、**そもそもラベル駆動のプロキシに載せ替える**選択肢と
  比較検討する価値がある → [04-alternatives.md](./04-alternatives.md)
