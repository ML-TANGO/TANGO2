#!/usr/bin/env bash
# scripts/run_all_projector_chains.sh
#
# 남은 프로젝터 구조 네 가지를 각각 네 단계 전부 학습한다. 기존 mlp2x_gelu 는
# 이미 끝나 있으므로 제외한다.
#
#   CUDA_VISIBLE_DEVICES=2,3,4,5 bash scripts/run_all_projector_chains.sh
#
# 순서는 출력 토큰 수가 다른 구조를 번갈아 둔다. 중간에 멈추더라도 576 토큰
# 계열과 32 토큰 계열이 하나씩은 남게 하기 위함이다.
#
# 실측 기준 예상: linear 35.3h, cross_attn 30.7h, mlp3x_gelu 35.3h,
# qformer 30.7h. 합계 약 132시간.

set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CHAIN="$ROOT/scripts/train_projector_chain_qwen3.sh"

TYPES=("${@:-}")
if [ -z "${TYPES[0]:-}" ]; then
    TYPES=(linear cross_attn mlp3x_gelu qformer)
fi

echo "=== 프로젝터 체인 일괄 실행 ==="
echo "  대상: ${TYPES[*]}"
echo "  GPU : ${CUDA_VISIBLE_DEVICES:-all}"
echo ""

for pt in "${TYPES[@]}"; do
    log="$ROOT/logs/chain_${pt}.log"
    echo "### 시작: $pt  ($(date '+%F %T'))  -> $log"

    PROJECTOR_TYPE="$pt" bash "$CHAIN" > "$log" 2>&1
    rc=$?

    if [ $rc -ne 0 ]; then
        # 한 구조가 실패해도 나머지는 계속 돌린다. 실패한 것만 나중에 다시
        # 돌리면 되고, 여기서 멈추면 남은 GPU 시간을 통째로 버린다.
        echo "### 실패: $pt (rc=$rc)  로그 마지막 20줄:"
        tail -20 "$log" | sed 's/^/      /'
    else
        echo "### 완료: $pt  ($(date '+%F %T'))"
    fi
    echo ""
done

echo "=== 전체 종료 ==="
ls -d "$ROOT"/checkpoints/clip_qwen3_*_{linear,cross_attn,mlp3x_gelu,qformer} 2>/dev/null
exit 0
