from __future__ import annotations

from pathlib import Path
from typing import Iterable

import pandas as pd


KEY_COLS = ["ts", "site_id", "facility_id"]
META_COLS = {"ts", "site_id", "facility_id", "sensor_type", "probe", "sensor_id"}


def _normalize_probe_value(probe) -> str:
    if pd.isna(probe):
        return "na"
    try:
        f = float(probe)
        if f.is_integer():
            return str(int(f))
        return str(f)
    except Exception:
        return str(probe)


def _prepare_for_merge(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str], bool]:
    """
    단일 time_sync CSV(df)를 merge 가능한 형태로 변환한다.

    반환:
    - prepared_df: 키 컬럼 + prefix가 적용된 value 컬럼을 가진 DF
    - value_cols: prepared_df 안에서 키를 제외한 value 컬럼들
    - broadcast_by_ts_site: facility_id가 전부 null인 파일이면 True (ts,site_id로만 합쳐야 함)
    """
    if df.empty:
        return df.copy(), [], False

    df = df.copy()

    # 키 컬럼 보정
    if "ts" not in df.columns:
        raise ValueError("입력 df에 'ts' 컬럼이 없습니다.")
    df["ts"] = pd.to_datetime(df["ts"], format="ISO8601", utc=True)

    if "site_id" not in df.columns:
        df["site_id"] = pd.NA
    if "facility_id" not in df.columns:
        df["facility_id"] = pd.NA

    # 빈 문자열 facility_id도 NA로 처리
    df["facility_id"] = df["facility_id"].replace("", pd.NA)

    broadcast_by_ts_site = df["facility_id"].isna().all()

    sensor_type = df["sensor_type"].iloc[0] if "sensor_type" in df.columns else "unknown"

    has_probe = "probe" in df.columns
    probe_value = _normalize_probe_value(df["probe"].iloc[0]) if has_probe else None

    # 합병 대상(value) 컬럼 선정
    value_src_cols = [c for c in df.columns if c not in META_COLS]

    # 컬럼명 prefix 규칙 적용
    rename_map: dict[str, str] = {}
    for c in value_src_cols:
        if has_probe:
            rename_map[c] = f"probe_{probe_value}_{sensor_type}_{c}"
        else:
            rename_map[c] = f"{sensor_type}_{c}"

    prepared = df[KEY_COLS + value_src_cols].rename(columns=rename_map)
    value_cols = [rename_map[c] for c in value_src_cols]

    return prepared, value_cols, broadcast_by_ts_site


def merge_time_sync_dfs(dfs: Iterable[pd.DataFrame]) -> pd.DataFrame:
    """
    여러 time_sync 결과 DF들을 규칙대로 하나로 머지한다.

    - 기본 키: ts, site_id, facility_id
    - facility_id가 전부 null인 DF는 ts, site_id로만 머지(모든 facility_id row에 브로드캐스트)
    - 센서별 value 컬럼명은 sensor_type / probe 규칙으로 prefix 처리
    """
    prepared_items: list[tuple[pd.DataFrame, list[str], bool]] = []
    for df in dfs:
        p, value_cols, broadcast = _prepare_for_merge(df)
        if not p.empty and value_cols:
            prepared_items.append((p, value_cols, broadcast))

    if not prepared_items:
        return pd.DataFrame(columns=KEY_COLS)

    # base key 구성: facility_id가 있는 데이터들의 (ts,site_id,facility_id) 전체
    base_keys_parts = []
    null_facility_parts = []
    for p, _, broadcast in prepared_items:
        if broadcast:
            null_facility_parts.append(p[["ts", "site_id"]].drop_duplicates())
        else:
            base_keys_parts.append(p[KEY_COLS].drop_duplicates())

    if base_keys_parts:
        base_keys = pd.concat(base_keys_parts, ignore_index=True).drop_duplicates()
    else:
        # 전부 facility_id가 null이면, (ts,site_id)만으로 base 만들고 facility_id는 NA
        base_ts_site = pd.concat(null_facility_parts, ignore_index=True).drop_duplicates()
        base_keys = base_ts_site.assign(facility_id=pd.NA)[KEY_COLS]

    merged = base_keys.copy()

    # 순차적으로 컬럼 추가 (충돌 시 suffix로 받고 combine_first 처리)
    for p, value_cols, broadcast in prepared_items:
        if broadcast:
            # facility_id 무시하고 ts,site_id로 머지 → 모든 facility_id row에 값이 들어감
            p2 = p.drop(columns=["facility_id"])
            merged = merged.merge(p2, on=["ts", "site_id"], how="left", suffixes=("", "__dup"))
        else:
            merged = merged.merge(p, on=KEY_COLS, how="left", suffixes=("", "__dup"))

        # 컬럼 충돌 처리: __dup 컬럼이 생기면 기존 컬럼의 결측만 채우고 제거
        dup_cols = [c for c in merged.columns if c.endswith("__dup")]
        for dup in dup_cols:
            orig = dup[: -len("__dup")]
            if orig in merged.columns:
                merged[orig] = merged[orig].combine_first(merged[dup])
            else:
                merged[orig] = merged[dup]
            merged.drop(columns=[dup], inplace=True)

    merged = merged.sort_values(["ts", "site_id", "facility_id"], kind="mergesort").reset_index(drop=True)
    return merged


def merge_time_sync_folder(time_sync_valid_data_dir: str | Path) -> pd.DataFrame:
    base_dir = Path(time_sync_valid_data_dir)
    csv_paths = sorted(base_dir.rglob("*.csv"))
    dfs = [pd.read_csv(p) for p in csv_paths]
    return merge_time_sync_dfs(dfs)


def main() -> None:
    base_dir = Path(__file__).resolve().parent
    input_dir = base_dir / "5_time_sync_valid_data"
    output_dir = base_dir / "6_merged_data"
    output_dir.mkdir(parents=True, exist_ok=True)

    merged = merge_time_sync_folder(input_dir)

    # 원본 머지 결과
    out_path = output_dir / "time_sync_valid_data_merged.csv"
    merged.to_csv(out_path, index=False)
    print(f"saved: {out_path}")

    # 결측값이 하나도 없는 행만 남긴 버전
    out_path_no_na = output_dir / "time_sync_valid_data_merged_no_na.csv"
    merged.dropna(how="any").to_csv(out_path_no_na, index=False)
    print(f"saved: {out_path_no_na}")


if __name__ == "__main__":
    main()

