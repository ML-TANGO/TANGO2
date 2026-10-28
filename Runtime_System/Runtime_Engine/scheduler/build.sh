#!/usr/bin/env bash
# Build only the adjacent RTST scheduler using an external Linux 6.12 SDK.
set -euo pipefail

source_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
: "${KSRC:?set KSRC to the target Linux 6.12 source tree}"
: "${KOUT:?set KOUT to the target kernel build containing vmlinux}"
: "${SYSROOT:?set SYSROOT to the ARM64 library sysroot}"
: "${BPFTOOL:?set BPFTOOL to a host bpftool executable}"
build=${BUILD:-"${source_dir}/build"}
cross_compile=${CROSS_COMPILE:-aarch64-linux-gnu-}
clang=${CLANG:-clang}
jobs=${JOBS:-$(getconf _NPROCESSORS_ONLN)}

for path in \
    "$KSRC/tools/sched_ext/Makefile" \
    "$KSRC/tools/sched_ext/include" \
    "$KOUT/vmlinux" \
    "$SYSROOT/lib/libelf.so" \
    "$SYSROOT/lib/libz.so" \
    "$SYSROOT/lib/libzstd.so" \
    "$BPFTOOL" \
    "$source_dir/scx_rtst_orin.c" \
    "$source_dir/scx_rtst_orin.bpf.c"; do
    [[ -e "$path" ]] || { printf 'missing build input: %s\n' "$path" >&2; exit 1; }
done

# Make's relative SDK paths need absolute inputs, including in archive exports.
ksrc=$(cd -- "$KSRC" && pwd)
kout=$(cd -- "$KOUT" && pwd)
sysroot=$(cd -- "$SYSROOT" && pwd)
bpftool=$(cd -- "$(dirname -- "$BPFTOOL")" && pwd)/$(basename -- "$BPFTOOL")
mkdir -p "$build"
build=$(cd -- "$build" && pwd)
stage=$(mktemp -d "$build/source.XXXXXX")
trap 'rm -rf -- "$stage"' EXIT

# Only SDK support directories are linked. No external scheduler .c is staged,
# and the external kernel source tree is never modified.
mkdir -p "$stage/tools/sched_ext"
ln -s "$ksrc/include" "$stage/include"
for directory in build scripts lib include bpf; do
    ln -s "$ksrc/tools/$directory" "$stage/tools/$directory"
done
ln -s "$ksrc/tools/sched_ext/Makefile" "$stage/tools/sched_ext/Makefile"
ln -s "$ksrc/tools/sched_ext/include" "$stage/tools/sched_ext/include"
cp "$source_dir/scx_rtst_orin.c" "$source_dir/scx_rtst_orin.bpf.c" \
    "$stage/tools/sched_ext/"

make -C "$stage/tools/sched_ext" \
    ARCH=arm64 \
    CROSS_COMPILE="$cross_compile" \
    CLANG="$clang" \
    O="$build" \
    VMLINUX_BTF="$kout/vmlinux" \
    BPFTOOL="$bpftool" \
    HOST_BUILD_DIR="$build/build/obj" \
    LDFLAGS="-L$sysroot/lib -Wl,--allow-shlib-undefined -lelf -lz -lzstd -lpthread" \
    c-sched-targets=scx_rtst_orin \
    -j"$jobs" scx_rtst_orin

sha256sum "$source_dir/scx_rtst_orin.c" "$source_dir/scx_rtst_orin.bpf.c" \
    "$kout/vmlinux" "$build/build/bin/scx_rtst_orin" > "$build/BUILD.sha256"
file "$build/build/bin/scx_rtst_orin"
printf 'binary: %s\n' "$build/build/bin/scx_rtst_orin"
