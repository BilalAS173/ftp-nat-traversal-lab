#!/bin/bash
set -e
for ns in client r1 r2 server; do ip netns add $ns; done

# links: A = client-r1, B = r1-r2, C = r2-server
ip link add veth-c type veth peer name r1-a
ip link add r1-b   type veth peer name r2-b
ip link add r2-c   type veth peer name veth-s
ip link set veth-c netns client
ip link set r1-a netns r1;  ip link set r1-b netns r1
ip link set r2-b netns r2;  ip link set r2-c netns r2
ip link set veth-s netns server

# addresses
ip netns exec client ip addr add 192.168.1.10/24 dev veth-c
ip netns exec r1 ip addr add 192.168.1.1/24 dev r1-a
ip netns exec r1 ip addr add 10.0.12.1/30 dev r1-b
ip netns exec r2 ip addr add 10.0.12.2/30 dev r2-b
ip netns exec r2 ip addr add 203.0.113.1/24 dev r2-c
ip netns exec server ip addr add 203.0.113.10/24 dev veth-s

# bring interfaces up
for ns in client r1 r2 server; do ip netns exec $ns ip link set lo up; done
ip netns exec client ip link set veth-c up
ip netns exec r1 ip link set r1-a up;  ip netns exec r1 ip link set r1-b up
ip netns exec r2 ip link set r2-b up;  ip netns exec r2 ip link set r2-c up
ip netns exec server ip link set veth-s up

# routers forward packets
ip netns exec r1 sysctl -qw net.ipv4.ip_forward=1
ip netns exec r2 sysctl -qw net.ipv4.ip_forward=1

# static routes (R2 has NO route to 192.168.1.0/24)
ip netns exec client ip route add default via 192.168.1.1
ip netns exec r1 ip route add default via 10.0.12.2
ip netns exec server ip route add default via 203.0.113.1

# F2:
ip netns exec r1 nft add table ip nat
ip netns exec r1 nft add chain ip nat postrouting '{ type nat hook postrouting priority 100 ; }'
ip netns exec r1 nft add rule ip nat postrouting oifname "r1-b" masquerade

# F3: 
ip netns exec r1 tc qdisc add dev r1-b root handle 1: netem delay 50ms loss 1%
ip netns exec r1 tc qdisc add dev r1-b parent 1:1 handle 10: tbf rate 20mbit burst 32kbit latency 400ms
