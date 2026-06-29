#!/bin/bash
# Kensho TCP RTT 揺らぎ注入 - WSL2 eth0 にRTT変動を追加
# 全発信トラフィックに軽い遅延+揺らぎを加え、実ネットワークに近い特性にする
#
# 使用法: sudo bash setup_tcp_rtt.sh [apply|remove|status]

IFACE="eth0"
ACTION="${1:-apply}"

apply_netem() {
    echo "=== Applying TCP RTT fluctuation ==="
    # 現在のroot qdisc退避不要 - replaceで上書き
    tc qdisc replace dev "$IFACE" root netem delay 25ms 10ms distribution normal loss 0.3% 25%
    echo "✅ Applied: delay 25ms ±10ms, loss 0.3%"
}

remove_netem() {
    echo "=== Removing TCP RTT fluctuation ==="
    tc qdisc del dev "$IFACE" root 2>/dev/null || true
    echo "✅ Removed (WSL2 default qdisc restored)"
    sleep 1
    tc qdisc show dev "$IFACE" | head -1
}

status_netem() {
    echo "=== Current qdisc on $IFACE ==="
    tc qdisc show dev "$IFACE"
}

case "$ACTION" in
    apply) apply_netem ;;
    remove|rm) remove_netem ;;
    status) status_netem ;;
    *)
        echo "Usage: $0 [apply|remove|status]"
        echo "  apply  - Apply netem delay+loss (default)"
        echo "  remove - Remove netem, restore defaults"
        echo "  status - Show current qdisc"
        exit 1
        ;;
esac
