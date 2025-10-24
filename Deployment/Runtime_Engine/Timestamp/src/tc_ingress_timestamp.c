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
#define TIMESTAMP_OFFSET sizeof(struct ethhdr) + sizeof(struct iphdr) + sizeof(struct udphdr) + 8 

SEC("classifier")
int _classifier(struct __sk_buff *skb)
{
	void *data_end = (void *)(long)skb->data_end;
	void *data = (void *)(long)skb->data;
	struct ethhdr *eth = data;
		
	uint64_t nh_off = sizeof(*eth);
	if (data + nh_off > data_end) {
		return TC_ACT_OK;
	}
	uint16_t h_proto = eth->h_proto;
	
	if(h_proto == bpf_htons(ETH_P_IP)) {
		struct iphdr *iph = data + nh_off;
		struct udphdr *udph = data + nh_off + sizeof(struct iphdr);
		if(udph +1 > (struct udphdr *)data_end) {
			return TC_ACT_OK;
		}
		if(iph->protocol == IPPROTO_UDP && ((udph->dest) == bpf_htons(5000))) // set udp port here.
		{
			if(data + nh_off + sizeof(struct iphdr) + sizeof(struct udphdr) + 16 > data_end) {
				return TC_ACT_OK;
			}

			uint64_t time = bpf_ktime_get_ns(); // tc_ingress time
			void *payload = (void*)(long)udph + sizeof(struct udphdr) + 8;
			*(uint64_t*)payload = time;
			udph->check = 0;
			return TC_ACT_OK;
		}
	}
	return TC_ACT_OK;
}

char _license[] SEC("license") = "GPL";
