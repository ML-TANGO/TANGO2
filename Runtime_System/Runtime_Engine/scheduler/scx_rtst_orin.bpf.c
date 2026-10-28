/* SPDX-License-Identifier: GPL-2.0 */
/*
 * TANGO2 Orin S1b: protect the FIFO lane and schedule Kubernetes cgroups
 * according to explicit userspace intent.
 */
#include <scx/common.bpf.h>

char _license[] SEC("license") = "GPL";

const volatile s32 rt_cpu = 4;
const volatile u64 online_cpu_mask = 0xff;
const volatile u64 shared_cpu_mask = 0xef;
const volatile u64 background_cpu_mask = 0xe0;

UEI_DEFINE(uei);

#define NORMAL_DSQ		0
#define BACKGROUND_DSQ		1
#define RT_HELPER_DSQ		2
#define CRITICAL_DSQ		3
#define ORIN_NR_CPUS		12

enum workload_class {
	WORKLOAD_NORMAL,
	WORKLOAD_CRITICAL,
	WORKLOAD_BACKGROUND,
	WORKLOAD_CLASS_NR,
};

enum stat_idx {
	STAT_LOCAL_DISPATCH,
	STAT_NORMAL_ENQUEUE,
	STAT_BACKGROUND_ENQUEUE,
	STAT_NORMAL_DISPATCH,
	STAT_BACKGROUND_DISPATCH,
	STAT_BACKGROUND_DIRECT,
	STAT_BACKGROUND_FALLBACK,
	STAT_BACKGROUND_PLACEMENT_VIOLATION,
	STAT_RT_HELPER_ENQUEUE,
	STAT_RT_HELPER_DISPATCH,
	STAT_NORMAL_SELECT_FALLBACK,
	STAT_NORMAL_CPU4_VIOLATION,
	STAT_CRITICAL_ENQUEUE,
	STAT_CRITICAL_DISPATCH,
	STAT_CRITICAL_DIRECT,
	STAT_CRITICAL_PLACEMENT_VIOLATION,
	STAT_INTENT_HIT,
	STAT_INTENT_MISS,
	STAT_INTENT_INVALID,
	STAT_NR,
};

struct {
	__uint(type, BPF_MAP_TYPE_PERCPU_ARRAY);
	__uint(key_size, sizeof(u32));
	__uint(value_size, sizeof(u64));
	__uint(max_entries, STAT_NR);
} stats SEC(".maps");

struct {
	__uint(type, BPF_MAP_TYPE_PERCPU_ARRAY);
	__uint(key_size, sizeof(u32));
	__uint(value_size, sizeof(u32));
	__uint(max_entries, 1);
} dispatch_turn SEC(".maps");

struct {
	__uint(type, BPF_MAP_TYPE_HASH);
	__uint(key_size, sizeof(u64));
	__uint(value_size, sizeof(u32));
	__uint(max_entries, 4096);
} cgroup_intents SEC(".maps");

static void stat_inc(u32 idx)
{
	u64 *cnt = bpf_map_lookup_elem(&stats, &idx);

	if (cnt)
		(*cnt)++;
}

static u32 task_class(const struct task_struct *p)
{
	struct cgroup *cgrp;
	u32 *intent;
	u32 class = WORKLOAD_NORMAL;
	u64 cgid;

	cgrp = __COMPAT_scx_bpf_task_cgroup((struct task_struct *)p);
	if (!cgrp) {
		stat_inc(STAT_INTENT_MISS);
		return class;
	}

	cgid = cgrp->kn->id;
	intent = bpf_map_lookup_elem(&cgroup_intents, &cgid);
	if (!intent) {
		stat_inc(STAT_INTENT_MISS);
		goto out;
	}
	if (*intent >= WORKLOAD_CLASS_NR) {
		stat_inc(STAT_INTENT_INVALID);
		goto out;
	}

	stat_inc(STAT_INTENT_HIT);
	class = *intent;
out:
	bpf_cgroup_release(cgrp);
	return class;
}

static bool cpu_in_mask(s32 cpu, u64 mask)
{
	return cpu >= 0 && cpu < ORIN_NR_CPUS && (mask & (1ULL << cpu));
}

static bool is_shared_cpu(s32 cpu)
{
	return cpu_in_mask(cpu, shared_cpu_mask & online_cpu_mask);
}

static bool is_background_cpu(s32 cpu)
{
	return cpu_in_mask(cpu, background_cpu_mask & online_cpu_mask);
}

static bool is_pinned_kthread(const struct task_struct *p)
{
	return (p->flags & PF_KTHREAD) && p->nr_cpus_allowed == 1;
}

static bool task_has_shared_cpu(const struct task_struct *p)
{
	s32 cpu;

#pragma unroll
	for (cpu = 0; cpu < ORIN_NR_CPUS; cpu++) {
		if (is_shared_cpu(cpu) &&
		    bpf_cpumask_test_cpu(cpu, p->cpus_ptr))
			return true;
	}
	return false;
}

static bool is_rt_helper(const struct task_struct *p)
{
	return bpf_cpumask_test_cpu(rt_cpu, p->cpus_ptr) &&
	       !task_has_shared_cpu(p);
}

static bool task_has_background_cpu(const struct task_struct *p)
{
	s32 cpu;

#pragma unroll
	for (cpu = 0; cpu < ORIN_NR_CPUS; cpu++) {
		if (is_background_cpu(cpu) &&
		    bpf_cpumask_test_cpu(cpu, p->cpus_ptr))
			return true;
	}
	return false;
}

static s32 pick_background_cpu(struct task_struct *p, s32 prev_cpu,
			       bool *is_idle)
{
	s32 cpu;

	if (is_background_cpu(prev_cpu) &&
	    bpf_cpumask_test_cpu(prev_cpu, p->cpus_ptr) &&
	    scx_bpf_test_and_clear_cpu_idle(prev_cpu)) {
		*is_idle = true;
		return prev_cpu;
	}

#pragma unroll
	for (cpu = 0; cpu < ORIN_NR_CPUS; cpu++) {
		if (!is_background_cpu(cpu) ||
		    !bpf_cpumask_test_cpu(cpu, p->cpus_ptr))
			continue;
		if (scx_bpf_test_and_clear_cpu_idle(cpu)) {
			*is_idle = true;
			return cpu;
		}
	}

	if (is_background_cpu(prev_cpu) &&
	    bpf_cpumask_test_cpu(prev_cpu, p->cpus_ptr))
		return prev_cpu;

#pragma unroll
	for (cpu = 0; cpu < ORIN_NR_CPUS; cpu++) {
		if (is_background_cpu(cpu) &&
		    bpf_cpumask_test_cpu(cpu, p->cpus_ptr))
			return cpu;
	}

	return prev_cpu;
}

static s32 pick_shared_cpu(struct task_struct *p, s32 prev_cpu, bool *is_idle)
{
	s32 cpu;

	if (prev_cpu >= 0 && prev_cpu < ORIN_NR_CPUS &&
	    is_shared_cpu(prev_cpu) &&
	    bpf_cpumask_test_cpu(prev_cpu, p->cpus_ptr) &&
	    scx_bpf_test_and_clear_cpu_idle(prev_cpu)) {
		*is_idle = true;
		return prev_cpu;
	}

#pragma unroll
	for (cpu = 0; cpu < ORIN_NR_CPUS; cpu++) {
		if (!is_shared_cpu(cpu) ||
		    !bpf_cpumask_test_cpu(cpu, p->cpus_ptr))
			continue;
		if (scx_bpf_test_and_clear_cpu_idle(cpu)) {
			*is_idle = true;
			return cpu;
		}
	}

	if (prev_cpu >= 0 && prev_cpu < ORIN_NR_CPUS &&
	    is_shared_cpu(prev_cpu) &&
	    bpf_cpumask_test_cpu(prev_cpu, p->cpus_ptr))
		return prev_cpu;

#pragma unroll
	for (cpu = 0; cpu < ORIN_NR_CPUS; cpu++) {
		if (is_shared_cpu(cpu) &&
		    bpf_cpumask_test_cpu(cpu, p->cpus_ptr))
			return cpu;
	}

	return -1;
}

s32 BPF_STRUCT_OPS(rtst_orin_select_cpu, struct task_struct *p,
		   s32 prev_cpu, u64 wake_flags)
{
	bool is_idle = false;
	u32 class;
	s32 cpu;

	if (is_pinned_kthread(p) || is_rt_helper(p)) {
		cpu = scx_bpf_select_cpu_dfl(p, prev_cpu, wake_flags, &is_idle);
		if (is_idle) {
			stat_inc(STAT_LOCAL_DISPATCH);
			scx_bpf_dispatch(p, SCX_DSQ_LOCAL, SCX_SLICE_DFL, 0);
		}
		return cpu;
	}

	class = task_class(p);
	if (class == WORKLOAD_BACKGROUND && task_has_background_cpu(p)) {
		cpu = pick_background_cpu(p, prev_cpu, &is_idle);
		if (is_idle) {
			stat_inc(STAT_BACKGROUND_DIRECT);
			scx_bpf_dispatch(p, SCX_DSQ_LOCAL, SCX_SLICE_DFL, 0);
		}
		return cpu;
	}

	cpu = pick_shared_cpu(p, prev_cpu, &is_idle);
	if (cpu < 0) {
		stat_inc(STAT_NORMAL_SELECT_FALLBACK);
		return scx_bpf_select_cpu_dfl(p, prev_cpu, wake_flags, &is_idle);
	}
	if (is_idle) {
		if (class == WORKLOAD_CRITICAL)
			stat_inc(STAT_CRITICAL_DIRECT);
		else
			stat_inc(STAT_LOCAL_DISPATCH);
		scx_bpf_dispatch(p, SCX_DSQ_LOCAL, SCX_SLICE_DFL, 0);
	}
	return cpu;
}

void BPF_STRUCT_OPS(rtst_orin_enqueue, struct task_struct *p, u64 enq_flags)
{
	u32 class;

	/*
	 * Per-CPU kthreads must not wait behind a shared DSQ. Forward progress
	 * of IRQ and other kernel work depends on them.
	 */
	if (is_pinned_kthread(p)) {
		stat_inc(STAT_LOCAL_DISPATCH);
		scx_bpf_dispatch(p, SCX_DSQ_LOCAL, SCX_SLICE_INF,
				 enq_flags | SCX_ENQ_PREEMPT);
		return;
	}

	if (is_rt_helper(p)) {
		stat_inc(STAT_RT_HELPER_ENQUEUE);
		scx_bpf_dispatch(p, RT_HELPER_DSQ, SCX_SLICE_DFL, enq_flags);
		return;
	}

	class = task_class(p);
	if (class == WORKLOAD_BACKGROUND && task_has_background_cpu(p)) {
		stat_inc(STAT_BACKGROUND_ENQUEUE);
		scx_bpf_dispatch(p, BACKGROUND_DSQ, SCX_SLICE_DFL, enq_flags);
		return;
	}

	if (class == WORKLOAD_BACKGROUND)
		stat_inc(STAT_BACKGROUND_FALLBACK);

	if (class == WORKLOAD_CRITICAL) {
		stat_inc(STAT_CRITICAL_ENQUEUE);
		scx_bpf_dispatch(p, CRITICAL_DSQ, SCX_SLICE_DFL, enq_flags);
		return;
	}

	stat_inc(STAT_NORMAL_ENQUEUE);
	scx_bpf_dispatch(p, NORMAL_DSQ, SCX_SLICE_DFL, enq_flags);
}

void BPF_STRUCT_OPS(rtst_orin_dispatch, s32 cpu, struct task_struct *prev)
{
	u32 zero = 0;
	u32 *turn;
	bool background_first;

	if (cpu == rt_cpu) {
		if (scx_bpf_consume(RT_HELPER_DSQ))
			stat_inc(STAT_RT_HELPER_DISPATCH);
		return;
	}

	if (!is_shared_cpu(cpu))
		return;

	if (scx_bpf_consume(CRITICAL_DSQ)) {
		stat_inc(STAT_CRITICAL_DISPATCH);
		return;
	}

	if (!is_background_cpu(cpu)) {
		if (scx_bpf_consume(NORMAL_DSQ))
			stat_inc(STAT_NORMAL_DISPATCH);
		return;
	}

	/*
	 * Background CPUs alternate the first DSQ they try. If both classes remain
	 * backlogged, each receives bounded service instead of background
	 * tasks waiting behind an indefinitely non-empty normal DSQ.
	 */
	turn = bpf_map_lookup_elem(&dispatch_turn, &zero);
	if (!turn) {
		if (scx_bpf_consume(BACKGROUND_DSQ))
			stat_inc(STAT_BACKGROUND_DISPATCH);
		else if (scx_bpf_consume(NORMAL_DSQ))
			stat_inc(STAT_NORMAL_DISPATCH);
		return;
	}

	background_first = *turn != 0;
	*turn = !*turn;

	if (background_first) {
		if (scx_bpf_consume(BACKGROUND_DSQ)) {
			stat_inc(STAT_BACKGROUND_DISPATCH);
			return;
		}
		if (scx_bpf_consume(NORMAL_DSQ))
			stat_inc(STAT_NORMAL_DISPATCH);
		return;
	}

	if (scx_bpf_consume(NORMAL_DSQ)) {
		stat_inc(STAT_NORMAL_DISPATCH);
		return;
	}
	if (scx_bpf_consume(BACKGROUND_DSQ))
		stat_inc(STAT_BACKGROUND_DISPATCH);
}

void BPF_STRUCT_OPS(rtst_orin_running, struct task_struct *p)
{
	u32 class;
	s32 cpu;

	cpu = bpf_get_smp_processor_id();
	class = task_class(p);
	if (class == WORKLOAD_BACKGROUND) {
		if (!is_background_cpu(cpu))
			stat_inc(STAT_BACKGROUND_PLACEMENT_VIOLATION);
		return;
	}
	if (class == WORKLOAD_CRITICAL) {
		if (!is_shared_cpu(cpu))
			stat_inc(STAT_CRITICAL_PLACEMENT_VIOLATION);
		return;
	}

	if (cpu == rt_cpu &&
	    !is_pinned_kthread(p) &&
	    !is_rt_helper(p))
		stat_inc(STAT_NORMAL_CPU4_VIOLATION);
}

s32 BPF_STRUCT_OPS_SLEEPABLE(rtst_orin_init)
{
	s32 ret;

	ret = scx_bpf_create_dsq(NORMAL_DSQ, -1);
	if (ret)
		return ret;
	ret = scx_bpf_create_dsq(BACKGROUND_DSQ, -1);
	if (ret)
		return ret;
	ret = scx_bpf_create_dsq(RT_HELPER_DSQ, -1);
	if (ret)
		return ret;
	return scx_bpf_create_dsq(CRITICAL_DSQ, -1);
}

void BPF_STRUCT_OPS(rtst_orin_exit, struct scx_exit_info *ei)
{
	UEI_RECORD(uei, ei);
}

SCX_OPS_DEFINE(rtst_orin_ops,
	       .select_cpu	= (void *)rtst_orin_select_cpu,
	       .enqueue		= (void *)rtst_orin_enqueue,
	       .dispatch	= (void *)rtst_orin_dispatch,
	       .running		= (void *)rtst_orin_running,
	       .init		= (void *)rtst_orin_init,
	       .exit		= (void *)rtst_orin_exit,
	       .name		= "rtst_orin_s1b");
