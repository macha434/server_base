#!/usr/bin/env bash
set -euo pipefail

# BASH_SOURCE から逆算し、cwd に依存せず server-base-core / server-base を検出する
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
# (未コミットの作業や手動編集を消さないため)。
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

    # VS Code は .code-workspace と同じ場所に .devcontainer があれば最優先で使うため
    # 複製する(シンボリックリンクだと docker-compose.yml の volumes(../..) の相対パス
    # 解決が1階層ずれるため不採用)。
    #
    # core側のdevcontainer.json/docker-compose.ymlをsedで一部だけ書き換えて使い回すと
    # workspaceFolder のようなcore固有の値を直し忘れたまま複製されるバグを踏むため、
    # ../ (workspace root) 用の定義は workspace-root/ に別途正としてそのまま保持し、
    # ここでは無加工でコピーするだけにする。root側の定義を変えたい場合は
    # workspace-root/ 以下を直接編集すること。
    if [ ! -d "$workspace_devcontainer_dir" ]; then
        mkdir -p "$workspace_devcontainer_dir"
        cp "$SCRIPT_DIR/workspace-root/devcontainer.json" "$workspace_devcontainer_dir/devcontainer.json"
        cp "$SCRIPT_DIR/workspace-root/docker-compose.yml" "$workspace_devcontainer_dir/docker-compose.yml"
        cp "$SCRIPT_DIR/workspace-root/devcontainer-lock.json" "$workspace_devcontainer_dir/devcontainer-lock.json"
        cp "$SCRIPT_DIR/workspace-root/post-create.sh" "$workspace_devcontainer_dir/post-create.sh"
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
