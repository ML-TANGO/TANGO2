# Compile
```
clang -O2 -emit-llvm -c xdp_timestamp.c -o - | llc -march=bpf -filetype=obj -o xdp_timestamp.o
clang -O2 -emit-llvm -c tc_ingress_timestamp.c -o - | llc -march=bpf -filetype=obj -o tc_timestamp.o
clang -O2 -emit-llvm -c iptables_timestamp.c -o - | llc -march=bpf -filetype=obj -o iptables_timestamp.o
```

# Load / Unload
```
# iproute2
ip link set dev <dev_name> xdp obj xdp_timestamp.o
# bpftool
bpftool net attach xdp id 857 dev <dev_name>


# For attach BPF filter
tc qdisc add dev <dev_name> clsact 
tc filter add dev <dev_name> ingress prio 1 handle 1 bpf da obj tc_ingress_timestamp.o
bpftool prog load iptables_timestamp.o /sys/fs/bpf/iptables_timestamp type socket
iptables -N TSTAMP
iptables -A INPUT -i <dev_name> -p udp --dport 5000 -j TSTAMP
iptables -A TSTAMP -i <dev_name> -m bpf --object-pinned /sys/fs/bpf/iptables_timestamp -j LOG

# 언로드
ip link set dev <dev_name> xdp off
tc filter del dev <dev_name> ingress prio 1 handle 1 bpf
tc qdisc del dev <dev_name> clsact
iptables -D TSTAMP -i <dev_name> -m bpf --object-pinned /sys/fs/bpf/iptables_timestamp -j LOG
iptables -X TSTAMP
rm /sys/fs/bpf/iptables_timestamp
```
