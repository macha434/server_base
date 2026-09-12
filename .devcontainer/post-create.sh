#!/usr/bin/env bash
set -euo pipefail

# core単体でReopen in Containerした場合と、server-base.code-workspace経由で
# Reopen in Containerした場合(下記 setup_workspace が用意する複製 devcontainer.json
# を使う)の両方でこのスクリプトが実行されるが、どちらでもこのファイル自身の実体は
# server-base-core/.devcontainer/post-create.sh の1箇所だけなので、BASH_SOURCE から
# 逆算すれば cwd に依存せず server-base-core / server-base のルートを検出できる。
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CORE_DIR="$(dirname "$SCRIPT_DIR")"
SERVER_BASE_ROOT="$(dirname "$CORE_DIR")"

# システムライブラリの導入（PyGObject / PyAudio のネイティブビルド・音声再生に必要）
install_system_packages() {
    sudo apt-get update
    # sudo apt-get install -y --no-install-recommends
    # ベースイメージには python3-minimal しか入っておらず、shlex 等の標準ライブラリ
    # モジュールが欠けている（textual/pytest 等が ModuleNotFoundError になる）ため、
    # フルスタックの python3 を追加する
    sudo apt-get install -y --no-install-recommends python3
}

# Git の設定
configure_git() {
    git config --global --add safe.directory "$CORE_DIR"
}

# .claude の所有者を変更する (root でマウントされるため)
claude_ownership() {
    sudo chown -R vscode:vscode ~/.claude
}

# APM (Agent Package Manager, microsoft/apm) を導入する
setup_apm() {
    curl -sSL https://aka.ms/apm-unix | sh
    # apm.yml がまだ無い段階でも失敗しない (setup_node の package.json チェックと同じパターン)
    if [ -f apm.yml ]; then
        # .claude/ は空ディレクトリのため git 経由では復元されない。
        # 無い状態で apm install が Claude Code 向け設定の書き込みをスキップするため先に作る
        mkdir -p .claude
        if [ -f apm.lock.yaml ]; then
            apm install --frozen
        else
            apm install
        fi
    fi
}

# uv (Python パッケージ/venv 管理ツール) を導入し、CLI/TUI用の .venv を用意する
setup_uv() {
    curl -LsSf https://astral.sh/uv/install.sh | sh
    # インストール直後はこのシェル呼び出し内でPATHがまだ更新されていない可能性があるため、
    # インストール先を直接指定して実行する
    (cd "$CORE_DIR" && "$HOME/.local/bin/uv" sync)
}

# server-base-features を兄弟ディレクトリとして clone し、VS Code のマルチルート
# workspace(server-base-core本体 + features)を用意する。
# `$SERVER_BASE_ROOT` はdocker-composeでホストの server-base ディレクトリを
# 丸ごとbind mountしているため、所有権は既にホスト側と一致しており chown は不要。
# clone・workspaceファイル・.devcontainerとも「無ければ作る、あれば触らない」
# (未コミットの作業や手動編集を消さないため。compose.generated.yaml等の
# 「都度再生成する生成物」とは扱いが異なる)。
setup_workspace() {
    local features_dir="$SERVER_BASE_ROOT/server-base-features"
    local workspace_file="$SERVER_BASE_ROOT/server-base.code-workspace"
    local workspace_devcontainer_dir="$SERVER_BASE_ROOT/.devcontainer"

    if [ ! -d "$features_dir" ]; then
        # server-base-features は補助的なworkspace用リポジトリなので、
        # 未公開・ネットワーク不通等で失敗してもpost-create.sh全体を止めない。
        git clone https://github.com/macha434/server-base-features.git "$features_dir" \
            || echo "警告: server-base-features のcloneに失敗しました(後で手動で '$features_dir' に clone してください)" >&2
    fi

    if [ ! -f "$workspace_file" ]; then
        cat > "$workspace_file" <<'JSON'
{
  "folders": [
    { "name": "🛠️ core", "path": "server-base-core" },
    { "name": "🧩 features", "path": "server-base-features" }
  ]
}
JSON
    fi

    # VS Code は .code-workspace と同じ場所に .devcontainer があればそれを最優先で
    # 使う。無いと folders 内を走査して選択ダイアログ(picker)を出すことがあるため、
    # ホストで server-base.code-workspace を直に開いて Reopen in Container しても
    # 確実に server-base-core/.devcontainer が使われるようにしたい。
    #
    # ただしシンボリックリンクでは駄目: docker-compose.yml の volumes は
    # `../..:/workspace/server-base` という相対パスで、.devcontainer の
    # 実体がある場所(server-base-core/.devcontainer、2階層上がserver-base)基準で
    # 解決される。server-base/.devcontainer をそこへのシンボリックリンクにすると
    # docker compose がリンク先を辿らず「server-base/.devcontainer」という
    # 見かけ上の位置(1階層上がserver-base)から相対パスを解決してしまい、
    # bind mount 元がずれる(実測で1階層浅い場所を指した)。
    # そのため devcontainer.json と docker-compose.yml だけ実体をコピーし、
    # volumes の相対パスをこの階層に合わせて `..` に直す。post-create.sh自体は
    # コピーしない(postCreateCommandはworkspaceFolder基準の相対パスなので、
    # どちらのdevcontainer.json経由でもこの実体ファイルがそのまま実行される)。
    # core側のdevcontainer.jsonを変更したときは、features/customizations等の
    # 差分をこちらにも反映すること。
    if [ ! -d "$workspace_devcontainer_dir" ]; then
        mkdir -p "$workspace_devcontainer_dir"
        cp "$SCRIPT_DIR/devcontainer.json" "$workspace_devcontainer_dir/devcontainer.json"
        sed 's#- \.\./\.\.:/workspace/server-base#- ..:/workspace/server-base#' \
            "$SCRIPT_DIR/docker-compose.yml" > "$workspace_devcontainer_dir/docker-compose.yml"
    fi
}

main() {
    install_system_packages
    configure_git
    claude_ownership
    setup_apm
    setup_uv
    setup_workspace
}

main "$@"
