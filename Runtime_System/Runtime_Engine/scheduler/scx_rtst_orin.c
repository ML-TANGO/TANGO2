/* SPDX-License-Identifier: GPL-2.0 */
#include <errno.h>
#include <getopt.h>
#include <libgen.h>
#include <linux/bpf.h>
#include <linux/magic.h>
#include <limits.h>
#include <signal.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/vfs.h>
#include <unistd.h>

#include <bpf/bpf.h>
#include <bpf/libbpf.h>
#include <scx/common.h>

#include "scx_rtst_orin.bpf.skel.h"

#define ORIN_NR_CPUS 12
#define DEFAULT_INTENT_MAP_PIN "/sys/fs/bpf/scx_rtst_orin_cgroup_intents"

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

struct run_config {
	int rt_cpu;
	__u64 online_cpu_mask;
	__u64 shared_cpu_mask;
	__u64 background_cpu_mask;
};

static const char help_fmt[] =
"TANGO2 Orin S1b sched_ext scheduler.\n"
"\n"
"Usage:\n"
"  %s [run] [OPTIONS]\n"
"  %s set <normal|critical|background> <cgroup-path>\n"
"  %s delete <cgroup-path>\n"
"  %s delete-id <cgroup-id>\n"
"  %s list\n"
"\n"
"Run options:\n"
"  -v, --verbose                 Print libbpf debug messages\n"
"  -r, --rt-cpu CPU              FIFO lane CPU (default: 4)\n"
"  -o, --online-mask MASK        Online CPU bit mask (default: 0xff)\n"
"  -s, --shared-mask MASK        Shared CPU bit mask (default: 0xef)\n"
"  -b, --background-mask MASK    Background CPU bit mask (default: 0xe0)\n"
"  -h, --help                    Display this help and exit\n"
"\n"
"SCX_RTST_ORIN_MAP_PIN overrides the control map pin path.\n";

static bool verbose;
static volatile int exit_req;

static const char *intent_map_pin(void)
{
	const char *path = getenv("SCX_RTST_ORIN_MAP_PIN");

	return path && path[0] ? path : DEFAULT_INTENT_MAP_PIN;
}

static const char *class_name(__u32 class)
{
	switch (class) {
	case WORKLOAD_NORMAL:
		return "normal";
	case WORKLOAD_CRITICAL:
		return "critical";
	case WORKLOAD_BACKGROUND:
		return "background";
	default:
		return "invalid";
	}
}

static int parse_class(const char *name, __u32 *class)
{
	if (!strcmp(name, "normal"))
		*class = WORKLOAD_NORMAL;
	else if (!strcmp(name, "critical"))
		*class = WORKLOAD_CRITICAL;
	else if (!strcmp(name, "background"))
		*class = WORKLOAD_BACKGROUND;
	else
		return -1;
	return 0;
}

static int resolve_cgroup(const char *path, char *resolved, __u64 *cgid)
{
	struct statfs fs;
	struct stat st;

	if (!realpath(path, resolved)) {
		fprintf(stderr, "failed to resolve cgroup path %s: %s\n",
			path, strerror(errno));
		return -1;
	}
	if (statfs(resolved, &fs)) {
		fprintf(stderr, "failed to statfs cgroup path %s: %s\n",
			resolved, strerror(errno));
		return -1;
	}
	if ((unsigned long)fs.f_type != CGROUP2_SUPER_MAGIC) {
		fprintf(stderr, "path is not on cgroup v2: %s\n", resolved);
		return -1;
	}
	if (stat(resolved, &st)) {
		fprintf(stderr, "failed to stat cgroup path %s: %s\n",
			resolved, strerror(errno));
		return -1;
	}
	if (!S_ISDIR(st.st_mode)) {
		fprintf(stderr, "cgroup path is not a directory: %s\n", resolved);
		return -1;
	}

	*cgid = st.st_ino;
	return 0;
}

static int open_intent_map(void)
{
	struct bpf_map_info info = {};
	__u32 info_len = sizeof(info);
	const char *pin = intent_map_pin();
	int fd;

	fd = bpf_obj_get(pin);
	if (fd < 0) {
		fprintf(stderr, "failed to open intent map %s: %s\n",
			pin, strerror(errno));
		return -1;
	}
	if (bpf_obj_get_info_by_fd(fd, &info, &info_len)) {
		fprintf(stderr, "failed to inspect intent map %s: %s\n",
			pin, strerror(errno));
		close(fd);
		return -1;
	}
	if (info.key_size != sizeof(__u64) ||
	    info.value_size != sizeof(__u32)) {
		fprintf(stderr,
			"intent map has incompatible key/value sizes: %u/%u\n",
			info.key_size, info.value_size);
		close(fd);
		return -1;
	}
	return fd;
}

static int control_set(const char *class_arg, const char *path)
{
	char resolved[PATH_MAX];
	__u32 class;
	__u32 readback;
	__u64 cgid;
	int fd;

	if (parse_class(class_arg, &class)) {
		fprintf(stderr, "unknown workload class: %s\n", class_arg);
		return 2;
	}
	if (resolve_cgroup(path, resolved, &cgid))
		return 1;
	fd = open_intent_map();
	if (fd < 0)
		return 1;

	if (bpf_map_update_elem(fd, &cgid, &class, BPF_ANY)) {
		fprintf(stderr, "failed to update cgroup intent: %s\n",
			strerror(errno));
		close(fd);
		return 1;
	}
	if (bpf_map_lookup_elem(fd, &cgid, &readback) ||
	    readback != class) {
		fprintf(stderr, "cgroup intent read-back failed\n");
		close(fd);
		return 1;
	}

	printf("ACK op=set cgroup_id=%llu class=%s path=%s\n",
	       (unsigned long long)cgid, class_name(readback), resolved);
	close(fd);
	return 0;
}

static int control_delete(const char *path)
{
	char resolved[PATH_MAX];
	__u32 readback;
	__u64 cgid;
	int fd;

	if (resolve_cgroup(path, resolved, &cgid))
		return 1;
	fd = open_intent_map();
	if (fd < 0)
		return 1;

	if (bpf_map_delete_elem(fd, &cgid)) {
		fprintf(stderr, "failed to delete cgroup intent: %s\n",
			strerror(errno));
		close(fd);
		return 1;
	}
	errno = 0;
	if (!bpf_map_lookup_elem(fd, &cgid, &readback) || errno != ENOENT) {
		fprintf(stderr, "deleted cgroup intent is still present\n");
		close(fd);
		return 1;
	}

	printf("ACK op=delete cgroup_id=%llu path=%s\n",
	       (unsigned long long)cgid, resolved);
	close(fd);
	return 0;
}

static int control_list(void)
{
	__u64 current;
	__u64 next;
	__u64 *previous = NULL;
	__u32 class;
	int fd;

	fd = open_intent_map();
	if (fd < 0)
		return 1;

	while (!bpf_map_get_next_key(fd, previous, &next)) {
		if (bpf_map_lookup_elem(fd, &next, &class)) {
			fprintf(stderr, "failed to read cgroup intent %llu: %s\n",
				(unsigned long long)next, strerror(errno));
			close(fd);
			return 1;
		}
		printf("cgroup_id=%llu class=%s\n",
		       (unsigned long long)next, class_name(class));
		current = next;
		previous = &current;
	}
	if (errno != ENOENT) {
		fprintf(stderr, "failed to enumerate cgroup intents: %s\n",
			strerror(errno));
		close(fd);
		return 1;
	}

	close(fd);
	return 0;
}

static int parse_int(const char *arg, int *value)
{
	char *end;
	long parsed;

	errno = 0;
	parsed = strtol(arg, &end, 0);
	if (errno || !arg[0] || *end || parsed < 0 || parsed >= ORIN_NR_CPUS)
		return -1;
	*value = (int)parsed;
	return 0;
}

static int parse_mask(const char *arg, __u64 *value)
{
	char *end;
	unsigned long long parsed;

	errno = 0;
	parsed = strtoull(arg, &end, 0);
	if (errno || !arg[0] || *end)
		return -1;
	*value = parsed;
	return 0;
}

static int control_delete_id(const char *arg)
{
	__u32 readback;
	__u64 cgid;
	int fd;

	if (parse_mask(arg, &cgid) || !cgid) {
		fprintf(stderr, "invalid cgroup ID: %s\n", arg);
		return 2;
	}
	fd = open_intent_map();
	if (fd < 0)
		return 1;

	if (bpf_map_delete_elem(fd, &cgid)) {
		fprintf(stderr, "failed to delete cgroup intent %llu: %s\n",
			(unsigned long long)cgid, strerror(errno));
		close(fd);
		return 1;
	}
	errno = 0;
	if (!bpf_map_lookup_elem(fd, &cgid, &readback) || errno != ENOENT) {
		fprintf(stderr, "deleted cgroup intent is still present\n");
		close(fd);
		return 1;
	}

	printf("ACK op=delete cgroup_id=%llu\n",
	       (unsigned long long)cgid);
	close(fd);
	return 0;
}

static int validate_run_config(const struct run_config *config)
{
	const __u64 valid_mask = (1ULL << ORIN_NR_CPUS) - 1;
	const __u64 rt_mask = 1ULL << config->rt_cpu;

	if (!config->online_cpu_mask ||
	    config->online_cpu_mask & ~valid_mask) {
		fprintf(stderr, "online mask must contain only CPUs 0-11\n");
		return -1;
	}
	if (!(config->online_cpu_mask & rt_mask)) {
		fprintf(stderr, "RT CPU is not in the online mask\n");
		return -1;
	}
	if (!config->shared_cpu_mask ||
	    config->shared_cpu_mask & ~config->online_cpu_mask ||
	    config->shared_cpu_mask & rt_mask) {
		fprintf(stderr,
			"shared mask must be a non-empty online subset without RT CPU\n");
		return -1;
	}
	if (!config->background_cpu_mask ||
	    config->background_cpu_mask & ~config->shared_cpu_mask) {
		fprintf(stderr,
			"background mask must be a non-empty shared-mask subset\n");
		return -1;
	}
	return 0;
}

static int parse_run_options(int argc, char **argv,
			     struct run_config *config)
{
	static const struct option long_options[] = {
		{ "verbose", no_argument, NULL, 'v' },
		{ "rt-cpu", required_argument, NULL, 'r' },
		{ "online-mask", required_argument, NULL, 'o' },
		{ "shared-mask", required_argument, NULL, 's' },
		{ "background-mask", required_argument, NULL, 'b' },
		{ "help", no_argument, NULL, 'h' },
		{},
	};
	int opt;

	while ((opt = getopt_long(argc, argv, "vr:o:s:b:h",
				  long_options, NULL)) != -1) {
		switch (opt) {
		case 'v':
			verbose = true;
			break;
		case 'r':
			if (parse_int(optarg, &config->rt_cpu))
				return -1;
			break;
		case 'o':
			if (parse_mask(optarg, &config->online_cpu_mask))
				return -1;
			break;
		case 's':
			if (parse_mask(optarg, &config->shared_cpu_mask))
				return -1;
			break;
		case 'b':
			if (parse_mask(optarg, &config->background_cpu_mask))
				return -1;
			break;
		case 'h':
			printf(help_fmt, basename(argv[0]), basename(argv[0]),
			       basename(argv[0]), basename(argv[0]),
			       basename(argv[0]));
			exit(0);
		default:
			return -1;
		}
	}
	if (optind != argc)
		return -1;
	return validate_run_config(config);
}

static int libbpf_print_fn(enum libbpf_print_level level,
			   const char *format, va_list args)
{
	if (level == LIBBPF_DEBUG && !verbose)
		return 0;
	return vfprintf(stderr, format, args);
}

static void signal_handler(int signo)
{
	exit_req = 1;
}

static int read_stats(struct scx_rtst_orin *skel, __u64 *stats)
{
	int nr_cpus = libbpf_num_possible_cpus();
	__u64 *cnts;
	__u32 idx;

	if (nr_cpus <= 0) {
		fprintf(stderr, "failed to determine possible CPUs: %d\n",
			nr_cpus);
		return -1;
	}

	cnts = calloc((size_t)nr_cpus, sizeof(*cnts));
	if (!cnts) {
		fprintf(stderr, "failed to allocate per-CPU stats: %s\n",
			strerror(errno));
		return -1;
	}

	memset(stats, 0, sizeof(stats[0]) * STAT_NR);

	for (idx = 0; idx < STAT_NR; idx++) {
		int cpu;

		if (bpf_map_lookup_elem(bpf_map__fd(skel->maps.stats),
					&idx, cnts)) {
			fprintf(stderr, "failed to read stats[%u]: %s\n",
				idx, strerror(errno));
			free(cnts);
			return -1;
		}
		for (cpu = 0; cpu < nr_cpus; cpu++)
			stats[idx] += cnts[cpu];
	}

	free(cnts);
	return 0;
}

static int run_scheduler(int argc, char **argv)
{
	struct run_config config = {
		.rt_cpu = 4,
		.online_cpu_mask = 0xff,
		.shared_cpu_mask = 0xef,
		.background_cpu_mask = 0xe0,
	};
	struct scx_rtst_orin *skel;
	struct bpf_link *link;
	const char *pin = intent_map_pin();
	__u64 ecode;
	bool stats_failed = false;
	bool map_pinned;

	if (argc > 1 && !strcmp(argv[1], "run")) {
		argc--;
		argv++;
	}
	if (parse_run_options(argc, argv, &config)) {
		fprintf(stderr, help_fmt, basename(argv[0]), basename(argv[0]),
			basename(argv[0]), basename(argv[0]),
			basename(argv[0]));
		return 2;
	}
	if (!access(pin, F_OK)) {
		fprintf(stderr,
			"refusing to replace existing intent map pin: %s\n", pin);
		return 1;
	}
	if (errno != ENOENT) {
		fprintf(stderr, "failed to inspect intent map pin %s: %s\n",
			pin, strerror(errno));
		return 1;
	}

	libbpf_set_print(libbpf_print_fn);
	signal(SIGINT, signal_handler);
	signal(SIGTERM, signal_handler);

restart:
	map_pinned = false;

	skel = SCX_OPS_OPEN(rtst_orin_ops, scx_rtst_orin);
	skel->rodata->rt_cpu = config.rt_cpu;
	skel->rodata->online_cpu_mask = config.online_cpu_mask;
	skel->rodata->shared_cpu_mask = config.shared_cpu_mask;
	skel->rodata->background_cpu_mask = config.background_cpu_mask;
	SCX_OPS_LOAD(skel, rtst_orin_ops, scx_rtst_orin, uei);
	link = SCX_OPS_ATTACH(skel, rtst_orin_ops, scx_rtst_orin);

	if (bpf_map__pin(skel->maps.cgroup_intents, pin)) {
		fprintf(stderr, "failed to pin intent map %s: %s\n",
			pin, strerror(errno));
		bpf_link__destroy(link);
		scx_rtst_orin__destroy(skel);
		return 1;
	}
	map_pinned = true;

	printf("attached ops=rtst_orin_s1b rt_cpu=%d "
	       "online_mask=0x%llx shared_mask=0x%llx "
	       "background_mask=0x%llx intent_map=%s\n",
	       skel->rodata->rt_cpu,
	       (unsigned long long)skel->rodata->online_cpu_mask,
	       (unsigned long long)skel->rodata->shared_cpu_mask,
	       (unsigned long long)skel->rodata->background_cpu_mask,
	       pin);

	while (!exit_req && !UEI_EXITED(skel, uei)) {
		__u64 stats[STAT_NR];

		if (read_stats(skel, stats)) {
			stats_failed = true;
			break;
		}
		printf("local=%llu normal_enqueued=%llu "
		       "background_enqueued=%llu normal_dispatched=%llu "
		       "background_dispatched=%llu background_direct=%llu "
		       "background_fallback=%llu "
		       "background_placement_violations=%llu "
		       "rt_helper_enqueued=%llu rt_helper_dispatched=%llu "
		       "normal_select_fallback=%llu "
		       "normal_cpu4_violations=%llu "
		       "critical_enqueued=%llu critical_dispatched=%llu "
		       "critical_direct=%llu "
		       "critical_placement_violations=%llu "
		       "intent_hit=%llu intent_miss=%llu intent_invalid=%llu\n",
		       stats[STAT_LOCAL_DISPATCH],
		       stats[STAT_NORMAL_ENQUEUE],
		       stats[STAT_BACKGROUND_ENQUEUE],
		       stats[STAT_NORMAL_DISPATCH],
		       stats[STAT_BACKGROUND_DISPATCH],
		       stats[STAT_BACKGROUND_DIRECT],
		       stats[STAT_BACKGROUND_FALLBACK],
		       stats[STAT_BACKGROUND_PLACEMENT_VIOLATION],
		       stats[STAT_RT_HELPER_ENQUEUE],
		       stats[STAT_RT_HELPER_DISPATCH],
		       stats[STAT_NORMAL_SELECT_FALLBACK],
		       stats[STAT_NORMAL_CPU4_VIOLATION],
		       stats[STAT_CRITICAL_ENQUEUE],
		       stats[STAT_CRITICAL_DISPATCH],
		       stats[STAT_CRITICAL_DIRECT],
		       stats[STAT_CRITICAL_PLACEMENT_VIOLATION],
		       stats[STAT_INTENT_HIT],
		       stats[STAT_INTENT_MISS],
		       stats[STAT_INTENT_INVALID]);
		fflush(stdout);
		sleep(1);
	}

	if (map_pinned && bpf_map__unpin(skel->maps.cgroup_intents, pin)) {
		fprintf(stderr, "failed to unpin intent map %s: %s\n",
			pin, strerror(errno));
		stats_failed = true;
	}
	bpf_link__destroy(link);
	ecode = UEI_REPORT(skel, uei);
	scx_rtst_orin__destroy(skel);

	if (UEI_ECODE_RESTART(ecode))
		goto restart;
	return exit_req && !stats_failed ? 0 : 1;
}

int main(int argc, char **argv)
{
	if (argc > 1 && !strcmp(argv[1], "set")) {
		if (argc != 4) {
			fprintf(stderr, help_fmt, basename(argv[0]),
				basename(argv[0]), basename(argv[0]),
				basename(argv[0]), basename(argv[0]));
			return 2;
		}
		return control_set(argv[2], argv[3]);
	}
	if (argc > 1 && !strcmp(argv[1], "delete")) {
		if (argc != 3) {
			fprintf(stderr, help_fmt, basename(argv[0]),
				basename(argv[0]), basename(argv[0]),
				basename(argv[0]), basename(argv[0]));
			return 2;
		}
		return control_delete(argv[2]);
	}
	if (argc > 1 && !strcmp(argv[1], "delete-id")) {
		if (argc != 3) {
			fprintf(stderr, help_fmt, basename(argv[0]),
				basename(argv[0]), basename(argv[0]),
				basename(argv[0]), basename(argv[0]));
			return 2;
		}
		return control_delete_id(argv[2]);
	}
	if (argc > 1 && !strcmp(argv[1], "list")) {
		if (argc != 2) {
			fprintf(stderr, help_fmt, basename(argv[0]),
				basename(argv[0]), basename(argv[0]),
				basename(argv[0]), basename(argv[0]));
			return 2;
		}
		return control_list();
	}
	return run_scheduler(argc, argv);
}
