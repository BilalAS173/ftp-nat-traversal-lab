#!/bin/bash
# Usage: sudo bash setup/run_condition.sh C1|C2|C3 <label> [-- command ...]
# Example: sudo bash setup/run_condition.sh C2 ping_test -- ip netns exec client ping -c 5 203.0.113.10
# C1 = 0 ms, 0% loss | C2 = 20 ms, 0% loss | C3 = 50 ms, 1% loss

if [ "$EUID" -ne 0 ]; then echo "Run with sudo"; exit 1; fi

COND=$1
LABEL=${2:-test}
shift
[ $# -gt 0 ] && shift
[ "$1" = "--" ] && shift

case $COND in
  C1) DELAY=0ms;  LOSS=0% ;;
  C2) DELAY=20ms; LOSS=0% ;;
  C3) DELAY=50ms; LOSS=1% ;;
  *) echo "Usage: sudo bash $0 C1|C2|C3 <label> [-- command ...]"; exit 1 ;;
esac

# default command: 5 pings from client to server
if [ $# -eq 0 ]; then set -- ip netns exec client ping -c 5 203.0.113.10; fi

OUT="captures/${LABEL}_${COND}_$(date +%H%M%S)"
mkdir -p "$OUT"

echo "[1/5] Setting condition $COND (delay $DELAY, loss $LOSS)"
ip netns exec r1 tc qdisc change dev r1-b handle 1: netem delay $DELAY loss $LOSS || exit 1
ip netns exec r1 conntrack -F 2>/dev/null

echo "[2/5] Starting captures on r1-a (client side) and r1-b (server side)"
ip netns exec r1 tcpdump -U -i r1-a -w "$OUT/client_side.pcap" 2>/dev/null &
P1=$!
ip netns exec r1 tcpdump -U -i r1-b -w "$OUT/server_side.pcap" 2>/dev/null &
P2=$!
sleep 1

echo "[3/5] Running: $*"
ip netns exec r1 conntrack -L > "$OUT/conntrack_before.txt" 2>/dev/null
"$@" &
CMD=$!
sleep 2
ip netns exec r1 conntrack -L > "$OUT/conntrack_during.txt" 2>/dev/null
wait $CMD
sleep 1
ip netns exec r1 conntrack -L > "$OUT/conntrack_after.txt" 2>/dev/null

echo "[4/5] Stopping captures"
kill -INT $P1 $P2
wait $P1 $P2 2>/dev/null
if command -v editcap >/dev/null; then
  for f in client_side server_side; do
    editcap -F pcapng "$OUT/$f.pcap" "$OUT/$f.pcapng" && rm "$OUT/$f.pcap"
  done
fi

echo "[5/5] Saved in $OUT:"
ls -lh "$OUT"
