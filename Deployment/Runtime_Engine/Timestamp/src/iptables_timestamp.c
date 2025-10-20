#include <linux/bpf.h>
#include <linux/if_ether.h>
#include <linux/in.h>
#include <linux/ip.h>
#include <linux/udp.h>
// TC_ACT_OK
#include <linux/pkt_cls.h>
#include "bpf_helpers.h"

#include <stdint.h>
#define SEC(NAME) __attribute__((section(NAME), used))

#define bpf_htons(x) ((__be16)___constant_swab16((x)))
#define bpf_htonl(x) ((__be32)___constant_swab32((x)))
#define memcpy(dest, src, n) __builtin_memcpy((dest), (src), (n))

#define BPF_F_RECOMPUTE_CSUM		(1ULL << 0)
#define IPTABLES_HEADER_OFFSET 28
#define TIMESTAMP_OFFSET IPTABLES_HEADER_OFFSET + 16

SEC("socket_filter")
int _iptables_tstmp(struct __sk_buff *skb)
{
//	uint16_t debug;
//	int ret;
//	char fmt2[] = "bpf_skb_load_bytes: %d\n";
// for debug
//	if((ret = bpf_skb_load_bytes(skb, 10, &debug, sizeof(debug))) <0)
//	{
//		bpf_trace_printk(fmt, sizeof(fmt), ret);
//	}
//	bpf_trace_printk(fmt2, sizeof(fmt2), eth_proto);
	uint64_t time = bpf_ktime_get_ns(); // iptables_egress time
	bpf_skb_store_bytes(skb, TIMESTAMP_OFFSET, &time, sizeof(time), BPF_F_RECOMPUTE_CSUM); // write timestamp

	return 0;
}

char _license[] SEC("license") = "GPL";
