import csv
import json
import logging
import os
import threading
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from paho.mqtt import publish

MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", ""))
PUBLISH_TOPIC_TEMPLATE = os.getenv("MQTT_PUBLISH_TOPIC", "")
RESPONSE_TOPIC_TEMPLATE = os.getenv("MQTT_RESPONSE_TOPIC", "")
CLIENT_ID_MAX_BYTES = 20
CLIENT_ID_RANDOM_LEN = 6
_CLIENT_ID_PREFIX = "".join(
    c for c in os.getenv("SITE_ID", "sdf") if c.isascii() and c.isalnum()
)[: CLIENT_ID_MAX_BYTES - CLIENT_ID_RANDOM_LEN]
MQTT_ENABLED = os.getenv("MQTT_ENABLED", "false").strip().lower() == "true"
MQTT_ENABLED_FACILITIES = {
    t for t in os.getenv("MQTT_ENABLED_FACILITIES", "").replace(",", " ").split() if t
}

log = logging.getLogger("sdf_agent")


# MQTT 클라이언트 ID 생성
def _client_id() -> str:
    return _CLIENT_ID_PREFIX + uuid.uuid4().hex[:CLIENT_ID_RANDOM_LEN]


MIN_SEND_INTERVAL = timedelta(minutes=1)

_queues: dict[str, list[dict]] = {}
_queue_lock = threading.Lock()
_wakeup = threading.Event()
_last_sent_at: dict[str, datetime] = {}
_pending_cooldown: dict[str, bool] = {}

_facility_controls: dict[str, dict] = {}


# 온실 동의 MQTT 전송 허용 여부 확인
def is_facility_enabled(facility_id: str) -> bool:
    return any(facility_id == t or facility_id.startswith(t) for t in MQTT_ENABLED_FACILITIES)


# 온실 동별 제어기 정보 등록 및 전송 허용 동 점검
def set_facility_controls(mapping: dict) -> None:
    _facility_controls.clear()
    _facility_controls.update({str(k): dict(v) for k, v in mapping.items()})
    log.info("mqtt: 동별 제어 정보 %d개 등록 %s", len(_facility_controls),
             {k[:8]: f"addr={v['address']} gw={v['gateway_id']}"
              for k, v in _facility_controls.items()})

    if not MQTT_ENABLED:
        log.info("mqtt: MQTT_ENABLED=false — 전 동 전송 안 함 (로그·이력만 기록)")
        return
    if not MQTT_ENABLED_FACILITIES:
        log.warning("mqtt: MQTT_ENABLED_FACILITIES 가 비어 있다 — 전 동 전송 안 함. "
                    "제어할 동을 명시해야 명령이 나간다")
        return
    on = sorted(f[:8] for f in _facility_controls if is_facility_enabled(f))
    off = sorted(f[:8] for f in _facility_controls if not is_facility_enabled(f))
    log.info("mqtt: 전송 허용 동 %s / 차단 동 %s", on, off)
    for t in sorted(MQTT_ENABLED_FACILITIES):
        hit = [f[:8] for f in _facility_controls if f == t or f.startswith(t)]
        if not hit:
            log.error("mqtt: MQTT_ENABLED_FACILITIES 의 %r 가 사이트에 없는 동이다 — 오타 확인", t)
        elif len(hit) > 1:
            log.error("mqtt: MQTT_ENABLED_FACILITIES 의 %r 가 %d개 동에 걸린다 %s — "
                      "의도한 게 아니면 앞자리를 더 길게 지정", t, len(hit), sorted(hit))

_HISTORY_DIR = Path(__file__).parent.parent / "logs"
_HISTORY_CSV = _HISTORY_DIR / "mqtt_history.csv"
_HISTORY_FIELDS = ["timestamp", "send_at", "site_id", "facility_id"] + [f"probe_{i}" for i in range(1, 9)]


# 온실 동별 전송 이력 파일 경로 생성
def _facility_history_path(facility_id: str) -> Path:
    tag = "".join(c for c in facility_id[:8] if c.isalnum()) or "unknown"
    return _HISTORY_DIR / f"mqtt_history_{tag}.csv"


# 전송 이력 CSV에 한 행 추가
def _append_history_row(path: Path, row: dict) -> None:
    is_new = not path.exists()
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_HISTORY_FIELDS)
        if is_new:
            writer.writeheader()
        writer.writerow(row)


# 제어 명령 전송 이력 기록
def _record_history(item: dict) -> None:
    _HISTORY_DIR.mkdir(exist_ok=True)
    row = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "send_at": item["send_at"].isoformat(timespec="seconds"),
        "site_id": item.get("site_id", ""),
        "facility_id": item.get("facility_id", ""),
        **{f"probe_{i}": item["probes"].get(str(i), "") for i in range(1, 9)},
    }
    _append_history_row(_HISTORY_CSV, row)

    facility_id = str(item.get("facility_id", "")).strip()
    if facility_id:
        _append_history_row(_facility_history_path(facility_id), row)


# 전송 대기열 디버그 로그 출력
def _log_queue(facility_id: str, queue: list[dict]) -> None:
    log.debug("=== MQTT QUEUE [%s] (%d개) ===", facility_id[:8], len(queue))
    for item in queue:
        log.debug("  send_at=%s probes=%s", item["send_at"].strftime("%H:%M:%S"), item["probes"])


# 온실 동의 전송 대기열 교체
def _replace_queue(facility_id: str, new_queue: list[dict]) -> None:
    with _queue_lock:
        _queues[facility_id] = list(new_queue)
        _pending_cooldown[facility_id] = True
        _log_queue(facility_id, new_queue)
    _wakeup.set()


# 생성형AI 응답을 분 단위 제어 명령으로 변환하여 전송 대기열에 등록
def schedule_plan(plan: dict, facility_df, base_ts: datetime) -> None:
    last_row = facility_df.iloc[-1]
    site_id = str(last_row.get("site_id", ""))
    facility_id = str(last_row.get("facility_id", ""))

    def _current_rate(col: str) -> int:
        try:
            return int(last_row[col])
        except (KeyError, TypeError, ValueError):
            return 0

    probe_7 = _current_rate("probe_7_agsmotor_green_open_rate")
    probe_8 = _current_rate("probe_8_agsmotor_green_open_rate")

    control = _facility_controls.get(facility_id)
    if control is None:
        log.error("mqtt: %s 의 제어 정보(modbus·게이트웨이)를 모른다 — 이 동은 발행하지 않는다",
                  facility_id[:8])
        return

    new_queue = []
    for step in plan["plan"]:
        probes = {str(i): step[f"probe_{i}"] for i in range(1, 7)}
        probes["7"] = probe_7
        probes["8"] = probe_8
        new_queue.append({
            "send_at": base_ts + timedelta(minutes=step["t_plus_min"]),
            "probes": probes,
            "site_id": site_id,
            "facility_id": facility_id,
            **control,
        })

    _replace_queue(facility_id, new_queue)


# 비상 제어 명령을 전송 대기열에 등록
def schedule_emergency(facility_id: str, steps: list[dict]) -> None:
    control = _facility_controls.get(facility_id)
    if control is None:
        log.error("mqtt: %s 의 제어 정보를 모른다 — 비상 명령을 발행하지 않는다", facility_id[:8])
        return
    _replace_queue(facility_id, [
        {**control, **s, "facility_id": facility_id} for s in steps
    ])


# 제어 명령 MQTT 전송
def _publish(item: dict) -> None:
    facility_id = str(item.get("facility_id", ""))
    site_id = str(item.get("site_id", ""))
    address = item.get("address")
    node_id = item.get("node_id")
    gateway_id = item.get("gateway_id")
    tag = f"{facility_id[:8]} addr={address} gw={gateway_id}"

    if address is None or node_id is None or gateway_id is None:
        log.error("mqtt: 제어 정보 누락 [%s] — 발행하지 않는다 (addr/node/gateway 확인)", tag)
        _record_history(item)
        return

    topic = PUBLISH_TOPIC_TEMPLATE.format(site_id=site_id, gateway_id=gateway_id,
                                          node_id=node_id, facility_id=facility_id)
    response_topic = RESPONSE_TOPIC_TEMPLATE.format(site_id=site_id, gateway_id=gateway_id,
                                                    node_id=node_id, facility_id=facility_id)
    payload = json.dumps({
        str(address): item["probes"],
        "command": "set_agsmotor_operation_req",
        "node_id": node_id,
        "response_topic": response_topic,
        "seq": str(int(time.time() * 1000)),
    })

    if not MQTT_ENABLED:
        skip = "MQTT_ENABLED=false"
    elif not is_facility_enabled(facility_id):
        skip = "MQTT_ENABLED_FACILITIES 에 없는 동"
    else:
        skip = ""

    if skip:
        log.info("mqtt: 전송 생략(%s) [%s] send_at=%s probes=%s",
                 skip, tag, item["send_at"].strftime("%H:%M:%S"), item["probes"])
        _record_history(item)
        return
    try:
        publish.single(topic, payload, qos=0, hostname=MQTT_HOST, port=MQTT_PORT,
                       client_id=_client_id())
        log.info("mqtt: 전송 → [%s] topic=%s send_at=%s probes=%s",
                 tag, topic, item["send_at"].strftime("%H:%M:%S"), item["probes"])
        _record_history(item)
    except Exception as e:
        log.error("mqtt: 전송 실패 [%s] send_at=%s: %s",
                  tag, item["send_at"].strftime("%H:%M:%S"), e)


# 전송 시각이 된 제어 명령을 MQTT 전송하는 스케줄러 루프
def _scheduler_loop() -> None:
    while True:
        _wakeup.clear()
        now = datetime.now()
        ready: list[tuple[str, dict]] = []
        next_due: datetime | None = None

        with _queue_lock:
            for facility_id, queue in _queues.items():
                due = sorted((i for i in queue if i["send_at"] <= now), key=lambda x: x["send_at"])
                if due:
                    if len(due) > 1:
                        log.info("mqtt: 밀린 명령 %d개 스킵 [%s] send_at=%s",
                                 len(due) - 1, facility_id[:8],
                                 [i["send_at"].strftime("%H:%M:%S") for i in due[:-1]])
                    for i in due:
                        queue.remove(i)
                    ready.append((facility_id, due[-1]))
                elif queue:
                    nxt = min(i["send_at"] for i in queue)
                    next_due = nxt if next_due is None else min(next_due, nxt)

            checks = {fid: _pending_cooldown.pop(fid, False) for fid, _ in ready}

        for facility_id, item in ready:
            last = _last_sent_at.get(facility_id)
            if checks[facility_id] and last is not None and datetime.now() - last < MIN_SEND_INTERVAL:
                log.info("mqtt: 새 plan 첫 명령이 마지막 전송 후 %s 미만이라 스킵 [%s] send_at=%s",
                         MIN_SEND_INTERVAL, facility_id[:8], item["send_at"].strftime("%H:%M:%S"))
                continue
            _publish(item)
            _last_sent_at[facility_id] = datetime.now()

        if ready:
            continue
        if next_due is None:
            _wakeup.wait()
        else:
            _wakeup.wait(timeout=max(0.05, (next_due - datetime.now()).total_seconds()))


# 제어 명령 전송 스케줄러 시작
def start_scheduler() -> threading.Thread:
    t = threading.Thread(target=_scheduler_loop, daemon=True, name="mqtt-scheduler")
    t.start()
    return t
