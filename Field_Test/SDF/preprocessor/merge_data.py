from __future__ import annotations

from typing import Iterable

import pandas as pd


KEY_COLS = ["ts", "site_id", "facility_id"]
META_COLS = {"ts", "site_id", "facility_id", "sensor_type", "probe", "sensor_id"}


# probe 번호 정규화
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


# 병합용 컬럼명 변환
def _prepare_for_merge(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str], bool]:
    if df.empty:
        return df.copy(), [], False

    df = df.copy()

    if "ts" not in df.columns:
        raise ValueError("입력 df에 'ts' 컬럼이 없습니다.")
    if "site_id" not in df.columns:
        df["site_id"] = pd.NA
    if "facility_id" not in df.columns:
        df["facility_id"] = pd.NA

    df["facility_id"] = df["facility_id"].replace("", pd.NA)

    broadcast_by_ts_site = df["facility_id"].isna().all()

    sensor_type = df["sensor_type"].iloc[0] if "sensor_type" in df.columns else "unknown"

    has_probe = "probe" in df.columns
    probe_value = _normalize_probe_value(df["probe"].iloc[0]) if has_probe else None

    value_src_cols = [c for c in df.columns if c not in META_COLS]

    rename_map: dict[str, str] = {}
    for c in value_src_cols:
        if has_probe:
            rename_map[c] = f"probe_{probe_value}_{sensor_type}_{c}"
        else:
            rename_map[c] = f"{sensor_type}_{c}"

    prepared = df[KEY_COLS + value_src_cols].rename(columns=rename_map)
    value_cols = [rename_map[c] for c in value_src_cols]

    return prepared, value_cols, broadcast_by_ts_site


# 센서 및 제어기 데이터 병합
def merge_time_sync_dfs(dfs: Iterable[pd.DataFrame]) -> pd.DataFrame:
    prepared_items: list[tuple[pd.DataFrame, list[str], bool]] = []
    for df in dfs:
        prepared_df, value_cols, broadcast = _prepare_for_merge(df)
        if not prepared_df.empty and value_cols:
            prepared_items.append((prepared_df, value_cols, broadcast))

    if not prepared_items:
        return pd.DataFrame(columns=KEY_COLS)

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
        base_ts_site = pd.concat(null_facility_parts, ignore_index=True).drop_duplicates()
        base_keys = base_ts_site.assign(facility_id=pd.NA)[KEY_COLS]

    merged = base_keys.copy()

    for p, value_cols, broadcast in prepared_items:
        if broadcast:
            p2 = p.drop(columns=["facility_id"])
            merged = merged.merge(p2, on=["ts", "site_id"], how="left", suffixes=("", "__dup"))
        else:
            merged = merged.merge(p, on=KEY_COLS, how="left", suffixes=("", "__dup"))

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
