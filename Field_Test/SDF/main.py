import logging
import os
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

from data_loader.get_raw_data import get_raw_data, get_agsmotor_controls
from preprocessor.main import preprocess
from action_agent.main import run as run_lam
from action_agent.mqtt_sender import schedule_plan, set_facility_controls, start_scheduler

INTERVAL_SECONDS = int(os.getenv("INTERVAL_SECONDS", "180"))
DEBUG = os.getenv("DEBUG", "").lower() in ("1", "true")

log = logging.getLogger("sdf_agent")


# 로그 설정 (DEBUG 시 파일 로그 추가)
def _setup_logging() -> None:
    log.setLevel(logging.DEBUG if DEBUG else logging.INFO)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    log.addHandler(ch)

    if DEBUG:
        log_dir = Path(__file__).parent / "logs"
        log_dir.mkdir(exist_ok=True)
        fh = logging.FileHandler(log_dir / f"debug_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
        fh.setFormatter(fmt)
        log.addHandler(fh)


# 로드된 센서 및 제어기 데이터 크기 디버그 로그 출력
def _log_raw_data(data_dict: dict) -> None:
    log.debug("=== RAW DATA ===")
    for key, df in data_dict["site_env"].items():
        if hasattr(df, "shape"):
            log.debug("  site_env.%s: %s", key, df.shape)
    for fid, sensors in data_dict["facility_env"].items():
        short = fid[:8]
        for skey, val in sensors.items():
            if skey == "agsmotor_green":
                for probe, pdata in val.items():
                    log.debug("  facility[%s].%s.%s: %s", short, skey, probe, pdata["data"].shape)
            elif hasattr(val, "shape"):
                log.debug("  facility[%s].%s: %s", short, skey, val.shape)


# 온실 동별 제어기 정보 조회 및 MQTT 전송용 등록
def _load_motor_controls() -> None:
    site_id = os.getenv("SITE_ID", "").strip()
    if not site_id:
        log.error("SITE_ID 없음 — 제어 정보를 조회할 수 없어 MQTT 발행이 전부 막힌다")
        return
    try:
        set_facility_controls(get_agsmotor_controls(site_id))
    except Exception as e:
        log.error("제어 정보 조회 실패 (%s) — MQTT 발행이 전부 막힌다", e)


# SDF 반복 실행 루프
def run() -> None:
    _load_motor_controls()
    scheduler = start_scheduler()

    while True:
        if not scheduler.is_alive():
            log.error("mqtt-scheduler 스레드 죽음, 재시작")
            scheduler = start_scheduler()

        try:
            raw_data = get_raw_data()
            _log_raw_data(raw_data)

            preprocessed_df = preprocess(raw_data)
            log.debug("=== PREPROCESSED DF shape=%s ===\n%s", preprocessed_df.shape, preprocessed_df.to_string())

            groups = list(preprocessed_df.groupby("facility_id"))
            started = time.monotonic()
            plans = []
            for facility_id, facility_df in groups:
                try:
                    plan = run_lam(facility_df)
                except Exception as e:
                    log.error("LAM 실패 %s: %s", facility_id, e)
                    continue
                if plan is None:
                    continue
                plans.append(facility_id)
                base_ts = facility_df["ts"].iloc[-1].to_pydatetime().replace(tzinfo=None)
                try:
                    schedule_plan(plan, facility_df, base_ts)
                except Exception as e:
                    log.error("mqtt 큐 적재 실패 %s: %s", facility_id, e)
            log.info("done. shape=%s, %d/%d동 plan (%.0f초), plans=%s",
                     preprocessed_df.shape, len(plans), len(groups),
                     time.monotonic() - started, plans)
        except Exception as e:
            log.error("사이클 실패 %s", e, exc_info=True)

        time.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    _setup_logging()
    run()
