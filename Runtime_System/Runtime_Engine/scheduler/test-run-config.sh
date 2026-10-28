#!/usr/bin/env bash
set -euo pipefail
binary=${1:?usage: test-run-config.sh /path/to/scx_rtst_orin}
temporary=$(mktemp -d)
trap 'rm -rf "$temporary"' EXIT
# An existing pin stops valid configurations before any BPF operation.
export SCX_RTST_ORIN_MAP_PIN="$temporary/pin"
touch "$SCX_RTST_ORIN_MAP_PIN"

check() {
    local expected=$1
    shift
    local result=0
    "$binary" run "$@" >"$temporary/output" 2>&1 || result=$?
    if [[ "$result" != "$expected" ]]; then
        cat "$temporary/output" >&2
        echo "expected exit $expected, got $result: $*" >&2
        exit 1
    fi
    if [[ "$expected" == 1 ]]; then
        grep -q 'refusing to replace existing intent map pin' "$temporary/output"
    fi
}

check 1
check 1 --rt-cpu 4 --online-mask 0xfff --shared-mask 0xfef --background-mask 0xfe0
check 1 --rt-cpu 11 --online-mask 0xfff --shared-mask 0x7ff --background-mask 0x700
check 2 --online-mask 0x1fff
check 2 --rt-cpu 12
check 2 --online-mask 0xfff --shared-mask 0xfff
check 2 --online-mask 0xfff --shared-mask 0xfef --background-mask 0x10
echo 'run_config_tests=PASS'
