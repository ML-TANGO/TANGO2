import argparse
import logging
import os
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))

from utility import load_env, fetch_data_by_site


# 실행 인자 및 환경변수에서 사이트·온실 동·조회 기간 읽기
def _parse_args(argv: list[str] | None = None) -> tuple[str, list[str] | None, int, str | None, str | None, str | None, bool]:
    parser = argparse.ArgumentParser(
        description="온실 센서 데이터 수집 (실시간 / 기간 지정)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--site-id",
        metavar="SITE_ID",
        help="수집할 사이트 ID (예: site_001)",
    )
    parser.add_argument(
        "--facility-id",
        metavar="FACILITY_ID",
        nargs="+",
        help="수집할 시설(동) UUID. 복수 지정 가능. 생략하면 전체 동 수집.",
    )
    parser.add_argument(
        "--window-minutes",
        metavar="N",
        type=int,
        default=int(os.getenv("WINDOW_MINUTES", "30")),
        help="수집할 과거 데이터 범위(분) (기본: WINDOW_MINUTES 환경변수 또는 30) — 실시간 모드에서만 사용",
    )
    parser.add_argument(
        "--start-date",
        metavar="DATETIME",
        help='조회 시작 시각 KST "YYYY-MM-DD HH:MM:SS" — 지정 시 기간 지정 모드',
    )
    parser.add_argument(
        "--end-date",
        metavar="DATETIME",
        help='조회 종료 시각 KST "YYYY-MM-DD HH:MM:SS" — 지정 시 기간 지정 모드',
    )

    args = parser.parse_args(argv)

    env_site_id = os.getenv("SITE_ID", "").strip()
    env_facility_ids = os.getenv("FACILITY_IDS", "").strip()

    interactive = (
        not args.site_id and not args.facility_id
        and not env_site_id and not env_facility_ids
        and sys.stdin.isatty()
    )

    site_id = args.site_id or env_site_id
    if not site_id:
        if not sys.stdin.isatty():
            print("사이트 ID가 없습니다. --site-id 인자 또는 SITE_ID 환경변수를 지정하세요.")
            sys.exit(1)
        site_id = input("사이트 ID를 입력하세요 (예: site_001): ").strip()
        if not site_id:
            print("사이트 ID가 입력되지 않았습니다.")
            sys.exit(1)

    facility_ids: list[str] | None = args.facility_id or env_facility_ids.split() or None

    if facility_ids is None and interactive:
        raw = input("시설(동) UUID를 입력하세요 (공백으로 구분, 생략하면 전체 동): ").strip()
        facility_ids = raw.split() if raw else None

    return site_id, facility_ids, args.window_minutes, args.start_date, args.end_date


# 로그 설정
def setup_logging(logging_cfg: dict) -> None:
    from logging.handlers import RotatingFileHandler

    level = getattr(logging, logging_cfg.get("level", "INFO"))
    fmt = logging.Formatter("%(asctime)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

    handlers = [logging.StreamHandler()]
    log_file = logging_cfg.get("file")
    if log_file:
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        handlers.append(RotatingFileHandler(
            log_file,
            maxBytes=logging_cfg.get("max_bytes", 1 * 1024 * 1024),
            backupCount=logging_cfg.get("backup_count", 5),
            encoding="utf-8",
        ))

    logging.basicConfig(
        level=level,
        handlers=handlers,
    )
    for h in logging.getLogger().handlers:
        h.setFormatter(fmt)


# 온실 동별 예상/실제 수집 건수 계산
def _facility_stats(fenv: dict, window_minutes: int) -> tuple[int, int]:
    actual = 0
    sensor_count = 0
    for val in fenv.values():
        if isinstance(val, pd.DataFrame):
            actual += len(val)
            sensor_count += 1
        elif isinstance(val, dict):
            for probe in val.values():
                if isinstance(probe, dict) and isinstance(probe.get("data"), pd.DataFrame):
                    actual += len(probe["data"])
                    sensor_count += 1
    return window_minutes * sensor_count, actual


# 외부 센서 예상/실제 수집 건수 계산
def _site_stats(site_env: dict, window_minutes: int) -> tuple[int, int]:
    actual = 0
    sensor_count = 0
    for key, val in site_env.items():
        if key == "kma":
            continue
        if isinstance(val, pd.DataFrame):
            actual += len(val)
            sensor_count += 1
    return window_minutes * sensor_count, actual


# 온실 동별 센서 및 제어기 데이터 로드 호출 및 작물 정보 결합
def real_data_main(
    start_date: str | None = None,
    end_date: str | None = None,
    facility_ids: list[str] | None = None,
) -> dict:
    overrides = {"start_date": start_date, "end_date": end_date, "facility_ids": facility_ids}
    argv = [] if any(v is not None for v in overrides.values()) else None
    site_id, parsed_facility_ids, window_minutes, parsed_start, parsed_end = _parse_args(argv)
    start_date = start_date or parsed_start
    end_date = end_date or parsed_end
    facility_ids = facility_ids or parsed_facility_ids

    cfg = load_env(window_minutes=window_minutes)
    setup_logging(cfg.get("logging", {}))
    logger = logging.getLogger(__name__)

    is_period_mode = bool(start_date and end_date)
    if is_period_mode:
        logger.info(f"기간 지정 모드: site_id={site_id}, {start_date} ~ {end_date}")
    else:
        logger.info(f"실시간 모드: site_id={site_id} (최근 {window_minutes}분)")

    try:
        result = fetch_data_by_site(
            site_id, facility_ids,
            start_date=start_date,
            end_date=end_date,
        )
        crop_df = pd.read_csv('data_loader/real_time_db_load/config/crop_info.csv', parse_dates=['planting_date'])
        crop_map = crop_df.set_index('facility_id').to_dict(orient='index')
        for fid, fenv in result['facility_env'].items():
            if fid in crop_map:
                fenv['crop_info'] = crop_map[fid]

        for fid, fenv in result['facility_env'].items():
            short_id = fid[:8]
            expected, actual = _facility_stats(fenv, window_minutes)
            if actual >= expected:
                logger.info(f"[동 {short_id}] 정상 - 예상 {expected}건, 수집 {actual}건")
            else:
                logger.error(f"[동 {short_id}] 에러 - 예상 {expected}건, 수집 {actual}건")

        expected, actual = _site_stats(result['site_env'], window_minutes)
        if actual >= expected:
            logger.info(f"[외부] 정상 - 예상 {expected}건, 수집 {actual}건")
        else:
            logger.error(f"[외부] 에러 - 예상 {expected}건, 수집 {actual}건")

        return result
    except Exception as e:
        logger.error(f"에러 - {e}", exc_info=False)
        sys.exit(1)


if __name__ == "__main__":
    real_data_main()
