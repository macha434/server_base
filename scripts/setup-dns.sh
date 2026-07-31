#!/bin/bash
# ubuntu.local専用DNSサーバーのセットアップスクリプト

set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DNSMASQ_DIR="$ROOT/core/dnsmasq"

# IPアドレスは引数で明示指定できる。省略した場合は、外部への経路に使われる
# インターフェースのIPアドレスを自動検出する（LAN内から到達できるIPが欲しいため、
# 127.0.0.1 ではなく実際のLAN IPを既定値にする）。
IP_ADDRESS="${1:-}"
if [ -z "$IP_ADDRESS" ]; then
    if ! command -v ip &> /dev/null; then
        echo "エラー: IPアドレスの自動検出には 'ip' コマンドが必要です（iproute2）。" >&2
        echo "自動検出できない環境では引数で明示してください: $0 <IPアドレス>" >&2
        exit 1
    fi
    IP_ADDRESS="$(ip -4 route get 1.1.1.1 2>/dev/null | grep -oP 'src \K\S+' || true)"
    if [ -z "$IP_ADDRESS" ]; then
        echo "エラー: IPアドレスの自動検出に失敗しました。引数で明示してください: $0 <IPアドレス>" >&2
        exit 1
    fi
    echo "IPアドレスを自動検出しました: $IP_ADDRESS"
fi

# IPアドレスの検証
if ! [[ $IP_ADDRESS =~ ^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}$ ]]; then
    echo "エラー: 無効なIPアドレスです: $IP_ADDRESS"
    echo "使用方法: $0 [IPアドレス]"
    echo "例: $0 192.168.1.100"
    exit 1
fi

echo "=== ubuntu.local専用DNSサーバーのセットアップ ==="
echo "IPアドレス: $IP_ADDRESS"

# 1. dnsmasq.confを生成
echo ""
echo "1. dnsmasq.confを生成しています..."
cat > "$DNSMASQ_DIR/dnsmasq.conf" <<EOF
# ubuntu.local 専用DNSサーバー設定
# 自動生成日時: $(date)
# IPアドレス: $IP_ADDRESS

# ubuntu.localドメインとそのサブドメインのみ処理
# 他のドメインは上流DNSに転送

# ワイルドカードDNS設定（ubuntu.localドメイン専用）
address=/ubuntu.local/$IP_ADDRESS
address=/.ubuntu.local/$IP_ADDRESS

# 上流DNSサーバー（ubuntu.local以外のドメイン用）
server=8.8.8.8
server=8.8.4.4
server=1.1.1.1

# ubuntu.localのみを処理し、他は上流に転送
local=/ubuntu.local/

# キャッシュサイズ
cache-size=1000

# ローカルドメインのリバインディング保護を無効化
rebind-localhost-ok

# ログ（デバッグ用、本番では無効化可）
log-queries
log-facility=/var/log/dnsmasq.log
EOF

echo "✓ dnsmasq.confを生成しました"

# 2. dnsmasqコンテナを起動（core/compose.yaml 経由）
echo ""
echo "2. dnsmasqコンテナを起動しています..."
docker compose -f "$ROOT/core/compose.yaml" up -d dnsmasq

# コンテナが起動するまで少し待つ
sleep 2

# 3. 動作確認
echo ""
echo "3. 動作確認..."
if docker ps | grep -q dnsmasq-ubuntu-local; then
    echo "✓ dnsmasqコンテナが起動しました"
else
    echo "✗ dnsmasqコンテナの起動に失敗しました"
    exit 1
fi

# 4. DNS解決テスト
echo ""
echo "4. DNS解決テスト..."
echo "   ubuntu.local:"
dig @127.0.0.1 ubuntu.local +short 2>/dev/null || nslookup ubuntu.local 127.0.0.1 2>/dev/null | grep Address | tail -1

echo "   time.ubuntu.local:"
dig @127.0.0.1 time.ubuntu.local +short 2>/dev/null || nslookup time.ubuntu.local 127.0.0.1 2>/dev/null | grep Address | tail -1

echo ""
echo "期待値: $IP_ADDRESS"

# 5. セットアップ手順を表示
echo ""
echo "=== セットアップ完了！ ==="
echo ""
echo "次のステップ（/etc/hosts編集不要！）:"
echo ""
echo "【Linux (systemd-resolved使用)】"
echo "sudo mkdir -p /etc/systemd/resolved.conf.d"
echo "sudo tee /etc/systemd/resolved.conf.d/ubuntu-local.conf <<EOF"
echo "[Resolve]"
echo "DNS=127.0.0.1"
echo "Domains=~ubuntu.local"
echo "EOF"
echo "sudo systemctl restart systemd-resolved"
echo ""
echo "【macOS】"
echo "sudo mkdir -p /etc/resolver"
echo "sudo tee /etc/resolver/ubuntu.local <<EOF"
echo "nameserver 127.0.0.1"
echo "EOF"
echo ""
echo "【Windows】"
echo "1. ネットワーク設定 > アダプターオプションの変更"
echo "2. 使用中のネットワーク接続を右クリック > プロパティ"
echo "3. IPv4 > プロパティ > 優先DNSサーバー: 127.0.0.1"
echo "4. 代替DNSサーバー: 8.8.8.8"
echo ""
echo "※ この設定で *.ubuntu.local が自動的に解決され、"
echo "   他のドメインは通常通りアクセスできます"
echo ""
echo "Web UI: http://localhost:5380"
