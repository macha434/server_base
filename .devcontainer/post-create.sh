#!/usr/bin/env bash
set -euo pipefail

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
    git config --global --add safe.directory /workspace/server-base/core
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
    (cd /workspace/server-base/core && "$HOME/.local/bin/uv" sync)
}

# server-base-features を兄弟ディレクトリとして clone し、VS Code のマルチルート
# workspace(server_base本体 + features)を用意する。
# `/workspace` はdocker-composeのbind mountで自動生成される root所有ディレクトリなので、
# `/workspace/server-base` だけを vscode ユーザーに chown する(core/ 配下は
# 既存のbind mountで正しい所有権が付いているため再帰chownは不要)。
# clone・workspaceファイルとも「無ければ作る、あれば触らない」(未コミットの
# 作業や手動編集を消さないため。compose.generated.yaml等の「都度再生成する
# 生成物」とは扱いが異なる)。
setup_workspace() {
    sudo mkdir -p /workspace/server-base
    sudo chown vscode:vscode /workspace/server-base

    if [ ! -d /workspace/server-base/features ]; then
        # server-base-features は補助的なworkspace用リポジトリなので、
        # 未公開・ネットワーク不通等で失敗してもpost-create.sh全体を止めない。
        git clone https://github.com/macha434/server-base-features.git /workspace/server-base/features \
            || echo "警告: server-base-features のcloneに失敗しました(後で手動で '/workspace/server-base/features' に clone してください)" >&2
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

main() {
    install_system_packages
    configure_git
    claude_ownership
    setup_apm
    setup_uv
    setup_workspace
}

main "$@"
