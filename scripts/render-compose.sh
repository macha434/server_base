#!/usr/bin/env bash
# core/compose.yaml と stacks/*/docker-compose.yml を 1 枚の compose.generated.yaml に
# 集約する。標準出力に生成したファイルの絶対パスを返す。
#
# なぜ `-f` の複数指定ではなくこの方式を取るか:
# `docker compose -f core/compose.yaml -f stacks/<app>/docker-compose.yml ...` のように
# CLI の -f を複数指定すると、各ファイルが持つ `include:` の相対パスは
# 「先頭に指定したファイルの位置」基準で解決されてしまう（実測で確認済み）。
# アプリが 2 つ以上になると、先頭ファイル以外のアプリの `include:` パスが壊れる。
#
# 対して、1 枚の compose ファイルからトップレベルの `include:` で列挙した場合は、
# 列挙された各ファイル自身の `include:` がそのファイル自身の位置を基準に正しく解決される
# （compose-spec の仕様通り）。そのため、このスクリプトで stacks/*/docker-compose.yml を
# 動的に列挙した include リストを作り、それを使って起動・conf 生成の両方を行う。
#
# `include:` は glob 未対応なので、ファイルを列挙する部分だけは毎回このスクリプトで
# 再生成する必要がある（"ファイルを置くだけ" にするための唯一のからくり）。

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/compose.generated.yaml"

{
    echo "# 自動生成ファイル。手で編集しないこと。scripts/render-compose.sh が再生成する。"
    echo "name: server-base"
    echo "include:"
    echo "  - path: core/compose.yaml"
    shopt -s nullglob
    for f in "$ROOT"/stacks/*/docker-compose.yml; do
        app="$(basename "$(dirname "$f")")"
        echo "  - path: stacks/${app}/docker-compose.yml"
    done
} > "$OUT"

echo "$OUT"
