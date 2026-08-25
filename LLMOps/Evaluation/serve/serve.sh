#!/usr/bin/env bash
# ETRI 평가 웹데모 서빙 제어기.
#   ./serve.sh start  [intent|logickor|all]
#   ./serve.sh stop   [intent|logickor|all]
#   ./serve.sh status
#   ./serve.sh logs   [intent|logickor]
set -euo pipefail
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/env.sh"
mkdir -p "${LOG_DIR}" "${RUN_DIR_PID}"

pidfile() { echo "${RUN_DIR_PID}/$1.pid"; }
logfile() { echo "${LOG_DIR}/$1.log"; }

is_up() {
  local pf; pf="$(pidfile "$1")"
  [[ -f "${pf}" ]] && kill -0 "$(cat "${pf}")" 2>/dev/null
}

start_intent() {
  if is_up intent; then echo "[intent] 이미 실행 중 (pid $(cat "$(pidfile intent)"))"; return; fi
  [[ -x "${INTENT_VENV}/bin/python" ]] || { echo "[intent] venv 없음 -> setup.sh 먼저" >&2; return 1; }
  # PATH 앞단 shim 으로 docker 호출을 sudo 로 넘긴다(julian 은 docker 그룹이 아님).
  # GPU_DEVICE / HF_TOKEN / IMAGE / CONTAINER_NAME 은 web_app.py 가 os.environ 을
  # 그대로 자식(auto2.sh)에게 물려주므로 여기서 주입하면 된다.
  # 서브셸 안에서 exec 해야 $! 가 실제 파이썬 프로세스 pid 와 일치한다.
  ( cd "${INTENT_DIR}" && exec env \
      PATH="${SHIM_BIN}:${PATH}" \
      PORT="${INTENT_PORT}" \
      GPU_DEVICE="${INTENT_GPU}" \
      HF_TOKEN="${HF_TOKEN}" \
      PYTHONUNBUFFERED=1 \
      "${INTENT_VENV}/bin/python" web_app.py \
      >> "$(logfile intent)" 2>&1 ) &
  echo $! > "$(pidfile intent)"
  sleep 2
  is_up intent && echo "[intent]   http://0.0.0.0:${INTENT_PORT}  (GPU ${INTENT_GPU}, pid $(cat "$(pidfile intent)"))" \
               || { echo "[intent] 기동 실패 — $(logfile intent) 확인" >&2; return 1; }
}

start_logickor() {
  if is_up logickor; then echo "[logickor] 이미 실행 중 (pid $(cat "$(pidfile logickor)"))"; return; fi
  [[ -x "${LOGICKOR_VENV}/bin/python" ]] || { echo "[logickor] venv 없음 -> setup.sh 먼저" >&2; return 1; }
  # GPU 는 web UI 의 settings.json(gpu) 이 auto.sh 로 전달한다. setup.sh 에서
  # 기본값을 ${LOGICKOR_GPU} 로 맞춰 두었고, 화면에서 바꿀 수도 있다.
  # auto.sh 는 맨 `python` 을 호출한다. venv 를 PATH 앞단에 올려야 그 자식들이
  # (train_lora.py / generator.py / evaluator.py) torch·vllm 이 있는 인터프리터를 쓴다.
  ( cd "${LOGICKOR_DIR}" && exec env \
      PATH="${LOGICKOR_VENV}/bin:${PATH}" \
      VIRTUAL_ENV="${LOGICKOR_VENV}" \
      HOST=0.0.0.0 PORT="${LOGICKOR_PORT}" \
      HF_HOME="${HF_HOME}" HF_TOKEN="${HF_TOKEN}" \
      PYTHONUNBUFFERED=1 \
      "${LOGICKOR_VENV}/bin/python" web/app.py \
      >> "$(logfile logickor)" 2>&1 ) &
  echo $! > "$(pidfile logickor)"
  sleep 3
  is_up logickor && echo "[logickor] http://0.0.0.0:${LOGICKOR_PORT}  (GPU ${LOGICKOR_GPU}, pid $(cat "$(pidfile logickor)"))" \
                 || { echo "[logickor] 기동 실패 — $(logfile logickor) 확인" >&2; return 1; }
}

# 포트를 아직 쥐고 있는 잔여 프로세스까지 정리한다(pidfile 이 어긋난 경우 대비).
kill_port() {
  local port="$1" pids
  pids="$(ss -ltnpH "sport = :${port}" 2>/dev/null | grep -oP 'pid=\K[0-9]+' | sort -u || true)"
  for pid in ${pids}; do
    kill "${pid}" 2>/dev/null || true
  done
}

stop_one() {
  local name="$1" port pf; pf="$(pidfile "${name}")"
  [[ "${name}" == intent ]] && port="${INTENT_PORT}" || port="${LOGICKOR_PORT}"
  if is_up "${name}"; then
    kill "$(cat "${pf}")" 2>/dev/null || true
    sleep 2
    kill -9 "$(cat "${pf}")" 2>/dev/null || true
    echo "[${name}] 중지"
  else
    echo "[${name}] pidfile 기준 실행 중 아님"
  fi
  kill_port "${port}"
  sleep 1
  rm -f "${pf}"
  # 웹을 내려도 파이프라인 컨테이너는 남을 수 있으므로 같이 정리한다.
  if [[ "${name}" == "intent" ]]; then
    PATH="${SHIM_BIN}:${PATH}" docker rm -f qwen3_web_run >/dev/null 2>&1 || true
  fi
}

status() {
  printf "%-10s %-8s %-28s %s\n" SERVICE STATE URL PID
  for n in intent logickor; do
    local port url state pid
    [[ "$n" == intent ]] && port="${INTENT_PORT}" || port="${LOGICKOR_PORT}"
    url="http://$(hostname -I | awk '{print $1}'):${port}"
    if is_up "$n"; then state=up; pid="$(cat "$(pidfile "$n")")"; else state=down; pid="-"; fi
    printf "%-10s %-8s %-28s %s\n" "$n" "$state" "$url" "$pid"
  done
  echo
  echo "GPU:"
  nvidia-smi --query-gpu=index,memory.used,memory.total,utilization.gpu --format=csv,noheader \
    | awk -v a="${INTENT_GPU}" -v b="${LOGICKOR_GPU}" -F, '$1+0==a || $1+0==b {print "  gpu"$0}'
}

svc="${2:-all}"
case "${1:-status}" in
  start)
    [[ "$svc" == all || "$svc" == intent   ]] && start_intent   || true
    [[ "$svc" == all || "$svc" == logickor ]] && start_logickor || true
    ;;
  stop)
    [[ "$svc" == all || "$svc" == intent   ]] && stop_one intent   || true
    [[ "$svc" == all || "$svc" == logickor ]] && stop_one logickor || true
    ;;
  restart) "$0" stop "$svc"; "$0" start "$svc" ;;
  status)  status ;;
  logs)    tail -f "$(logfile "${2:-logickor}")" ;;
  *) echo "usage: $0 {start|stop|restart|status|logs} [intent|logickor|all]" >&2; exit 2 ;;
esac
