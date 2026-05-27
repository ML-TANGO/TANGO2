#!/usr/bin/env python3
"""
2026-02-11 ~ 2026-05-11 기간 센서 데이터 품질/관계 분석 스크립트.

분석 항목:
1. 5시간 이상 비어있는 구간 식별
2. 비어있는 기간들의 길이 산출
3. 데이터 도착 주기 요약
4. ts와 created_at의 시간 차이가 3시간 이상인 데이터 탐지
5. 개폐율과 환경 센서 정보의 연관성 분석
6. 개폐율 예측 모델 설계에 반영할 주안점 정리
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib import font_manager

try:
    import seaborn as sns
except ImportError:  # seaborn이 없어도 CSV 분석은 수행되도록 처리
    sns = None


ANALYSIS_START = "2026-02-11 00:00:00"
ANALYSIS_END = "2026-05-11 17:00:00"
GAP_THRESHOLD = pd.Timedelta(hours=5)
TS_CREATED_DELAY_THRESHOLD = pd.Timedelta(hours=3)
RESAMPLE_RULE = "5min"
MIN_CORRELATION_ROWS = 30

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PIPELINE_OUTPUT_ROOT = PROJECT_ROOT / "pipeline_output"
ORGANIZED_SENSOR_ROOT = PIPELINE_OUTPUT_ROOT / "organized_by_sensor"
OUTPUT_ROOT = PROJECT_ROOT / "data_inspect" / "output" / "data_inspect_260211-260511"
PLOT_ROOT = OUTPUT_ROOT / "plots"

METADATA_COLUMNS = {
    "ts",
    "site_id",
    "sensor_id",
    "created_at",
    "facility_id",
    "probe",
    "source_file",
    "sensor_group",
    "sensor_label",
    "data_kind",
}


# 그래프 저장 시 한글 라벨이 깨지지 않도록 사용 가능한 한글 폰트를 우선 적용한다.
def configure_plot_fonts() -> None:
    preferred_fonts = ["Arial Unicode MS", "AppleGothic", "Nanum Gothic", "NanumGothic", "Malgun Gothic", "Noto Sans CJK KR"]
    available_fonts = {font.name for font in font_manager.fontManager.ttflist}
    for font_name in preferred_fonts:
        if font_name in available_fonts:
            plt.rcParams["font.family"] = "sans-serif"
            plt.rcParams["font.sans-serif"] = [font_name]
            break
    plt.rcParams["axes.unicode_minus"] = False


# 분석 기간은 DB CSV의 +00:00 표기를 기준으로 UTC timestamp로 맞춘다.
def to_utc_timestamp(value: str) -> pd.Timestamp:
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is None:
        return timestamp.tz_localize("UTC")
    return timestamp.tz_convert("UTC")


ANALYSIS_START_TS = to_utc_timestamp(ANALYSIS_START)
ANALYSIS_END_TS = to_utc_timestamp(ANALYSIS_END)


# pandas 버전에 따라 format="mixed" 지원 여부가 다르므로 fallback을 둔다.
def parse_datetime_column(series: pd.Series) -> pd.Series:
    try:
        return pd.to_datetime(series, errors="coerce", utc=True, format="mixed")
    except (TypeError, ValueError):
        return pd.to_datetime(series, errors="coerce", utc=True)


# 파일명과 컬럼 정보를 바탕으로 센서 종류를 구분한다.
def classify_data_kind(path: Path, columns: List[str]) -> str:
    column_set = set(columns)
    if "open_rate" in column_set:
        return "motor_open_rate"
    if {"temp", "humi"}.issubset(column_set):
        return "internal_environment" if path.name.startswith("In_") else "external_environment"
    if "rain" in column_set:
        return "external_rain"
    if {"wind_speed", "wind_direction"}.intersection(column_set):
        return "external_wind"
    return "unknown"


# 긴 uuid를 리포트와 그래프에서 읽기 쉽도록 앞 8자리만 사용한다.
def short_id(value: object) -> str:
    if pd.isna(value):
        return "none"
    text = str(value).strip()
    return text[:8] if text else "none"


# 센서 파일별 사람이 읽기 쉬운 라벨을 만든다.
def build_sensor_label(path: Path, frame: pd.DataFrame, data_kind: str) -> str:
    sensor_group = path.parent.name
    sensor_id = short_id(frame["sensor_id"].dropna().iloc[0]) if "sensor_id" in frame and frame["sensor_id"].notna().any() else "unknown"

    if data_kind == "motor_open_rate":
        probe = None
        if "probe" in frame and frame["probe"].notna().any():
            probe = str(frame["probe"].dropna().iloc[0])
        if probe is None:
            match = re.search(r"_ch(\d+)_", path.name)
            probe = match.group(1) if match else "unknown"
        return f"{sensor_group} | {sensor_id} | ch{probe}"

    direction = "In" if path.name.startswith("In_") else "Out"
    return f"{sensor_group} | {direction} | {sensor_id}"


# 그래프/CSV 컬럼명에 사용할 수 있도록 라벨을 짧고 안전하게 만든다.
def safe_metric_name(text: str) -> str:
    text = re.sub(r"\s+", "_", text.strip())
    text = re.sub(r"[^0-9A-Za-z가-힣_\-]+", "_", text)
    return re.sub(r"_+", "_", text).strip("_")


# 분석 대상 센서 CSV를 찾는다. organizing_summary.csv는 실제 시계열 데이터가 아니므로 제외한다.
def discover_sensor_files(root: Path) -> List[Path]:
    if not root.exists():
        return []
    return sorted(
        path
        for path in root.rglob("*.csv")
        if path.name != "organizing_summary.csv" and not path.name.startswith(".")
    )


# 센서 CSV를 읽고 ts/created_at 파싱 및 분석 기간 필터를 수행한다.
def load_sensor_frame(path: Path) -> Optional[Dict[str, object]]:
    try:
        frame = pd.read_csv(path)
    except Exception as exc:
        print(f"⚠️ 파일 읽기 실패: {path} ({exc})")
        return None

    frame.columns = [str(column).strip() for column in frame.columns]
    if "ts" not in frame.columns:
        print(f"⚠️ ts 컬럼이 없어 제외: {path}")
        return None

    original_row_count = len(frame)
    frame["ts"] = parse_datetime_column(frame["ts"])
    if "created_at" in frame.columns:
        frame["created_at"] = parse_datetime_column(frame["created_at"])

    data_kind = classify_data_kind(path, list(frame.columns))
    frame = frame[frame["ts"].between(ANALYSIS_START_TS, ANALYSIS_END_TS)].copy()

    sensor_label = build_sensor_label(path, frame, data_kind) if not frame.empty else f"{path.parent.name} | empty"
    relative_path = path.relative_to(PROJECT_ROOT)
    frame["source_file"] = str(relative_path)
    frame["sensor_group"] = path.parent.name
    frame["sensor_label"] = sensor_label
    frame["data_kind"] = data_kind

    return {
        "path": path,
        "relative_path": str(relative_path),
        "sensor_group": path.parent.name,
        "sensor_label": sensor_label,
        "data_kind": data_kind,
        "original_row_count": original_row_count,
        "frame": frame,
    }


# 각 센서 파일의 시작/끝/행 수/결측 여부를 한눈에 볼 수 있는 요약을 만든다.
def build_file_overview(records: List[Dict[str, object]]) -> pd.DataFrame:
    rows = []
    for record in records:
        frame = record["frame"]
        assert isinstance(frame, pd.DataFrame)
        valid_ts = frame["ts"].dropna().sort_values()
        interval_seconds = valid_ts.diff().dt.total_seconds().dropna() if len(valid_ts) > 1 else pd.Series(dtype=float)
        max_gap_hours = interval_seconds.max() / 3600 if not interval_seconds.empty else np.nan
        median_interval_seconds = interval_seconds.median() if not interval_seconds.empty else np.nan

        delay_over_count = 0
        delay_over_ratio = np.nan
        if "created_at" in frame.columns and not frame.empty:
            delay = (frame["created_at"] - frame["ts"]).abs()
            delay_over_count = int((delay >= TS_CREATED_DELAY_THRESHOLD).sum())
            delay_over_ratio = delay_over_count / len(frame) if len(frame) else np.nan

        rows.append(
            {
                "source_file": record["relative_path"],
                "sensor_group": record["sensor_group"],
                "sensor_label": record["sensor_label"],
                "data_kind": record["data_kind"],
                "original_row_count": record["original_row_count"],
                "analysis_row_count": len(frame),
                "valid_ts_count": int(valid_ts.notna().sum()),
                "first_ts": valid_ts.iloc[0] if not valid_ts.empty else pd.NaT,
                "last_ts": valid_ts.iloc[-1] if not valid_ts.empty else pd.NaT,
                "median_arrival_interval_seconds": median_interval_seconds,
                "max_gap_hours": max_gap_hours,
                "gap_count_over_5h_by_interval_only": int((interval_seconds >= GAP_THRESHOLD.total_seconds()).sum()) if not interval_seconds.empty else 0,
                "ts_created_delay_over_3h_count": delay_over_count,
                "ts_created_delay_over_3h_ratio": delay_over_ratio,
            }
        )
    return pd.DataFrame(rows)


# 분석 기간 시작/끝 경계까지 포함해 5시간 이상 비어있는 구간을 계산한다.
def analyze_gaps(records: List[Dict[str, object]]) -> pd.DataFrame:
    gap_rows = []
    for record in records:
        frame = record["frame"]
        assert isinstance(frame, pd.DataFrame)
        times = frame["ts"].dropna().sort_values().drop_duplicates().reset_index(drop=True)

        if times.empty:
            gap_rows.append(
                {
                    "source_file": record["relative_path"],
                    "sensor_label": record["sensor_label"],
                    "data_kind": record["data_kind"],
                    "gap_type": "entire_period_empty",
                    "gap_start": ANALYSIS_START_TS,
                    "gap_end": ANALYSIS_END_TS,
                    "gap_hours": (ANALYSIS_END_TS - ANALYSIS_START_TS).total_seconds() / 3600,
                }
            )
            continue

        first_ts = times.iloc[0]
        last_ts = times.iloc[-1]

        start_gap = first_ts - ANALYSIS_START_TS
        if start_gap >= GAP_THRESHOLD:
            gap_rows.append(
                {
                    "source_file": record["relative_path"],
                    "sensor_label": record["sensor_label"],
                    "data_kind": record["data_kind"],
                    "gap_type": "analysis_start_to_first_data",
                    "gap_start": ANALYSIS_START_TS,
                    "gap_end": first_ts,
                    "gap_hours": start_gap.total_seconds() / 3600,
                }
            )

        time_diff = times.diff()
        for index in time_diff[time_diff >= GAP_THRESHOLD].index:
            gap_rows.append(
                {
                    "source_file": record["relative_path"],
                    "sensor_label": record["sensor_label"],
                    "data_kind": record["data_kind"],
                    "gap_type": "between_data_points",
                    "gap_start": times.iloc[index - 1],
                    "gap_end": times.iloc[index],
                    "gap_hours": time_diff.iloc[index].total_seconds() / 3600,
                }
            )

        end_gap = ANALYSIS_END_TS - last_ts
        if end_gap >= GAP_THRESHOLD:
            gap_rows.append(
                {
                    "source_file": record["relative_path"],
                    "sensor_label": record["sensor_label"],
                    "data_kind": record["data_kind"],
                    "gap_type": "last_data_to_analysis_end",
                    "gap_start": last_ts,
                    "gap_end": ANALYSIS_END_TS,
                    "gap_hours": end_gap.total_seconds() / 3600,
                }
            )

    return pd.DataFrame(gap_rows).sort_values("gap_hours", ascending=False) if gap_rows else pd.DataFrame()


# 데이터 도착 주기는 ts 간격의 분포로 계산한다.
def analyze_arrival_intervals(records: List[Dict[str, object]]) -> Tuple[pd.DataFrame, pd.DataFrame]:
    summary_rows = []
    interval_rows = []

    for record in records:
        frame = record["frame"]
        assert isinstance(frame, pd.DataFrame)
        times = frame["ts"].dropna().sort_values().drop_duplicates()
        intervals = times.diff().dt.total_seconds().dropna()
        intervals = intervals[intervals > 0]

        if intervals.empty:
            summary_rows.append(
                {
                    "source_file": record["relative_path"],
                    "sensor_label": record["sensor_label"],
                    "data_kind": record["data_kind"],
                    "interval_count": 0,
                    "median_seconds": np.nan,
                    "mean_seconds": np.nan,
                    "p90_seconds": np.nan,
                    "p95_seconds": np.nan,
                    "max_seconds": np.nan,
                    "mode_seconds_rounded": np.nan,
                }
            )
            continue

        rounded_mode = intervals.round().mode()
        summary_rows.append(
            {
                "source_file": record["relative_path"],
                "sensor_label": record["sensor_label"],
                "data_kind": record["data_kind"],
                "interval_count": len(intervals),
                "median_seconds": intervals.median(),
                "mean_seconds": intervals.mean(),
                "p90_seconds": intervals.quantile(0.90),
                "p95_seconds": intervals.quantile(0.95),
                "max_seconds": intervals.max(),
                "mode_seconds_rounded": rounded_mode.iloc[0] if not rounded_mode.empty else np.nan,
            }
        )

        for ts_end, value in zip(times.iloc[1:].loc[intervals.index], intervals.values):
            interval_rows.append(
                {
                    "source_file": record["relative_path"],
                    "sensor_label": record["sensor_label"],
                    "data_kind": record["data_kind"],
                    "ts_end": ts_end,
                    "interval_seconds": value,
                    "interval_minutes": value / 60,
                    "interval_hours": value / 3600,
                }
            )

    return pd.DataFrame(summary_rows), pd.DataFrame(interval_rows)


# ts와 created_at의 차이가 3시간 이상인 행을 원시 데이터 오류 후보로 본다.
def analyze_ts_created_delay(records: List[Dict[str, object]]) -> Tuple[pd.DataFrame, pd.DataFrame]:
    summary_rows = []
    abnormal_rows = []

    for record in records:
        frame = record["frame"]
        assert isinstance(frame, pd.DataFrame)
        if "created_at" not in frame.columns or frame.empty:
            continue

        delay = frame["created_at"] - frame["ts"]
        delay_hours = delay.dt.total_seconds() / 3600
        abs_delay_hours = delay_hours.abs()
        abnormal_mask = abs_delay_hours >= TS_CREATED_DELAY_THRESHOLD.total_seconds() / 3600

        summary_rows.append(
            {
                "source_file": record["relative_path"],
                "sensor_label": record["sensor_label"],
                "data_kind": record["data_kind"],
                "row_count": len(frame),
                "median_delay_seconds": delay.dt.total_seconds().median(),
                "mean_delay_seconds": delay.dt.total_seconds().mean(),
                "p95_abs_delay_seconds": abs_delay_hours.quantile(0.95) * 3600,
                "max_abs_delay_hours": abs_delay_hours.max(),
                "delay_over_3h_count": int(abnormal_mask.sum()),
                "delay_over_3h_ratio": abnormal_mask.mean(),
            }
        )

        if abnormal_mask.any():
            abnormal = frame.loc[abnormal_mask, ["ts", "created_at", "source_file", "sensor_label", "data_kind"]].copy()
            abnormal["delay_hours"] = delay_hours.loc[abnormal_mask].values
            abnormal["abs_delay_hours"] = abs_delay_hours.loc[abnormal_mask].values
            abnormal_rows.append(abnormal)

    summary = pd.DataFrame(summary_rows)
    abnormal = pd.concat(abnormal_rows, ignore_index=True) if abnormal_rows else pd.DataFrame()
    if not abnormal.empty:
        abnormal = abnormal.sort_values("abs_delay_hours", ascending=False)
    return summary, abnormal


# 숫자 센서 컬럼만 골라 correlation matrix에 사용할 series를 만든다.
def get_numeric_measurement_columns(frame: pd.DataFrame) -> List[str]:
    measurement_columns = []
    for column in frame.columns:
        if column in METADATA_COLUMNS:
            continue
        converted = pd.to_numeric(frame[column], errors="coerce")
        if converted.notna().any():
            measurement_columns.append(column)
    return measurement_columns


# 센서별 numeric 컬럼을 5분 단위 시계열로 리샘플링한다.
def build_resampled_sensor_matrices(records: List[Dict[str, object]]) -> Tuple[pd.DataFrame, pd.DataFrame]:
    motor_series: Dict[str, pd.Series] = {}
    environment_series: Dict[str, pd.Series] = {}

    for record in records:
        frame = record["frame"]
        assert isinstance(frame, pd.DataFrame)
        if frame.empty:
            continue

        data_kind = str(record["data_kind"])
        sensor_label = safe_metric_name(str(record["sensor_label"])).replace("AGS_Green_", "")
        numeric_columns = get_numeric_measurement_columns(frame)

        for column in numeric_columns:
            values = frame[["ts", column]].copy()
            values[column] = pd.to_numeric(values[column], errors="coerce")
            values = values.dropna(subset=["ts", column]).sort_values("ts")
            if values.empty:
                continue

            series = values.set_index("ts")[column].resample(RESAMPLE_RULE).median()
            metric_name = f"{sensor_label}_{column}"

            if data_kind == "motor_open_rate" and column == "open_rate":
                motor_series[metric_name] = series
            elif data_kind != "motor_open_rate":
                environment_series[metric_name] = series

    motor_matrix = pd.concat(motor_series, axis=1).sort_index() if motor_series else pd.DataFrame()
    environment_matrix = pd.concat(environment_series, axis=1).sort_index() if environment_series else pd.DataFrame()

    # 환경 센서는 도착 주기가 완전히 동일하지 않으므로 짧은 결측만 시간 보간한다.
    if not environment_matrix.empty:
        environment_matrix = environment_matrix.interpolate(method="time", limit=3)

    return motor_matrix, environment_matrix


# 개폐율과 환경 변수의 동시점 상관계수 및 lag 상관계수를 계산한다.
def analyze_open_rate_environment_relationship(
    motor_matrix: pd.DataFrame,
    environment_matrix: pd.DataFrame,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    correlation_rows = []
    lag_rows = []

    if motor_matrix.empty or environment_matrix.empty:
        return pd.DataFrame(), pd.DataFrame()

    lag_minutes_candidates = [-120, -60, -30, -15, 0, 15, 30, 60, 120]
    step_minutes = int(pd.Timedelta(RESAMPLE_RULE).total_seconds() / 60)

    for motor_column in motor_matrix.columns:
        motor_series = motor_matrix[motor_column]
        motor_change = motor_series.diff().abs()

        for env_column in environment_matrix.columns:
            env_series = environment_matrix[env_column]
            pair = pd.concat([motor_series, env_series], axis=1, keys=["open_rate", "environment"]).dropna()
            if len(pair) < MIN_CORRELATION_ROWS:
                continue
            if pair["open_rate"].nunique() <= 1 or pair["environment"].nunique() <= 1:
                continue

            pearson = pair.corr(method="pearson").loc["open_rate", "environment"]
            spearman = pair.corr(method="spearman").loc["open_rate", "environment"]

            change_pair = pd.concat(
                [motor_change, env_series.diff()],
                axis=1,
                keys=["open_rate_abs_change", "environment_change"],
            ).dropna()
            change_pearson = np.nan
            if len(change_pair) >= MIN_CORRELATION_ROWS and change_pair.nunique().min() > 1:
                change_pearson = change_pair.corr(method="pearson").loc["open_rate_abs_change", "environment_change"]

            correlation_rows.append(
                {
                    "motor_metric": motor_column,
                    "environment_metric": env_column,
                    "row_count": len(pair),
                    "pearson_corr": pearson,
                    "spearman_corr": spearman,
                    "open_rate_change_vs_environment_change_pearson": change_pearson,
                }
            )

            best_lag = None
            best_corr = np.nan
            for lag_minutes in lag_minutes_candidates:
                periods = int(round(lag_minutes / step_minutes))
                shifted_environment = env_series.shift(periods=periods)
                lag_pair = pd.concat(
                    [motor_series, shifted_environment],
                    axis=1,
                    keys=["open_rate", "environment_shifted"],
                ).dropna()
                if len(lag_pair) < MIN_CORRELATION_ROWS or lag_pair.nunique().min() <= 1:
                    continue
                lag_corr = lag_pair.corr(method="pearson").loc["open_rate", "environment_shifted"]
                lag_rows.append(
                    {
                        "motor_metric": motor_column,
                        "environment_metric": env_column,
                        "lag_minutes": lag_minutes,
                        "row_count": len(lag_pair),
                        "pearson_corr": lag_corr,
                        "abs_pearson_corr": abs(lag_corr),
                    }
                )
                if pd.notna(lag_corr) and (pd.isna(best_corr) or abs(lag_corr) > abs(best_corr)):
                    best_lag = lag_minutes
                    best_corr = lag_corr

            if best_lag is not None:
                correlation_rows[-1]["best_lag_minutes_by_abs_corr"] = best_lag
                correlation_rows[-1]["best_lag_pearson_corr"] = best_corr

    correlations = pd.DataFrame(correlation_rows)
    lags = pd.DataFrame(lag_rows)

    if not correlations.empty:
        correlations["abs_pearson_corr"] = correlations["pearson_corr"].abs()
        correlations = correlations.sort_values("abs_pearson_corr", ascending=False)
    if not lags.empty:
        lags = lags.sort_values("abs_pearson_corr", ascending=False)

    return correlations, lags


# CSV 저장 시 빈 결과도 명시적으로 파일을 생성한다.
def save_dataframe(frame: pd.DataFrame, file_name: str) -> Path:
    path = OUTPUT_ROOT / file_name
    frame.to_csv(path, index=False, encoding="utf-8-sig")
    return path


# 도착 간격 분포를 로그 스케일로 확인한다.
def plot_arrival_interval_distribution(intervals: pd.DataFrame) -> None:
    if intervals.empty:
        return
    plot_data = intervals[intervals["interval_seconds"] > 0].copy()
    if plot_data.empty:
        return

    plt.figure(figsize=(12, 6))
    if sns is not None:
        sns.histplot(plot_data["interval_minutes"], bins=80, log_scale=(True, False))
    else:
        plt.hist(plot_data["interval_minutes"], bins=80)
        plt.xscale("log")
    plt.xlabel("Arrival interval (minutes, log scale)")
    plt.ylabel("Count")
    plt.title("Data arrival interval distribution")
    plt.tight_layout()
    plt.savefig(PLOT_ROOT / "arrival_interval_distribution.png", dpi=150)
    plt.close()


# 가장 긴 결측 구간들을 막대그래프로 저장한다.
def plot_gap_duration(gaps: pd.DataFrame) -> None:
    if gaps.empty:
        return
    plot_data = gaps.head(30).copy()
    plot_data["label"] = plot_data["sensor_label"].astype(str).str.slice(0, 45) + "..."

    plt.figure(figsize=(12, max(6, len(plot_data) * 0.3)))
    if sns is not None:
        sns.barplot(data=plot_data, y="label", x="gap_hours", hue="gap_type", dodge=False)
    else:
        plt.barh(plot_data["label"], plot_data["gap_hours"])
    plt.xlabel("Gap duration (hours)")
    plt.ylabel("Sensor")
    plt.title("Top gaps over 5 hours")
    plt.tight_layout()
    plt.savefig(PLOT_ROOT / "gap_duration_top30.png", dpi=150)
    plt.close()


# ts-created_at 지연 분포를 파일 단위 최대값 중심으로 시각화한다.
def plot_delay_summary(delay_summary: pd.DataFrame) -> None:
    if delay_summary.empty:
        return
    plot_data = delay_summary.sort_values("max_abs_delay_hours", ascending=False).head(30).copy()
    plot_data["label"] = plot_data["sensor_label"].astype(str).str.slice(0, 45) + "..."

    plt.figure(figsize=(12, max(6, len(plot_data) * 0.3)))
    plt.barh(plot_data["label"], plot_data["max_abs_delay_hours"])
    plt.axvline(3, color="red", linestyle="--", label="3 hours threshold")
    plt.xlabel("Max |created_at - ts| (hours)")
    plt.ylabel("Sensor")
    plt.title("Maximum timestamp ingestion delay by sensor")
    plt.legend()
    plt.tight_layout()
    plt.savefig(PLOT_ROOT / "ts_created_delay_max_by_sensor.png", dpi=150)
    plt.close()


# 개폐율-환경변수 상관계수 heatmap을 저장한다.
def plot_correlation_heatmap(correlations: pd.DataFrame) -> None:
    if correlations.empty:
        return

    top_env = correlations.groupby("environment_metric")["abs_pearson_corr"].max().nlargest(20).index
    top_motor = correlations.groupby("motor_metric")["abs_pearson_corr"].max().nlargest(20).index
    plot_data = correlations[
        correlations["environment_metric"].isin(top_env) & correlations["motor_metric"].isin(top_motor)
    ]
    pivot = plot_data.pivot_table(
        index="environment_metric",
        columns="motor_metric",
        values="pearson_corr",
        aggfunc="mean",
    )
    if pivot.empty:
        return

    plt.figure(figsize=(16, max(8, len(pivot) * 0.35)))
    if sns is not None:
        sns.heatmap(pivot, cmap="coolwarm", center=0, vmin=-1, vmax=1)
    else:
        plt.imshow(pivot.fillna(0).values, aspect="auto", cmap="coolwarm", vmin=-1, vmax=1)
        plt.colorbar(label="Pearson correlation")
        plt.yticks(range(len(pivot.index)), pivot.index)
        plt.xticks(range(len(pivot.columns)), pivot.columns, rotation=90)
    plt.title("Open-rate vs environment Pearson correlation")
    plt.tight_layout()
    plt.savefig(PLOT_ROOT / "open_rate_environment_correlation_heatmap.png", dpi=150)
    plt.close()


# 대표 개폐율과 가장 관련성이 큰 환경변수의 같은 기간 변화를 함께 그린다.
def plot_representative_timeseries(
    motor_matrix: pd.DataFrame,
    environment_matrix: pd.DataFrame,
    correlations: pd.DataFrame,
) -> None:
    if motor_matrix.empty or environment_matrix.empty or correlations.empty:
        return

    normalized = pd.DataFrame()
    motor_column = ""
    env_column = ""

    for _, top in correlations.head(30).iterrows():
        candidate_motor_column = top["motor_metric"]
        candidate_env_column = top["environment_metric"]
        combined = pd.concat(
            [motor_matrix[candidate_motor_column], environment_matrix[candidate_env_column]],
            axis=1,
        ).dropna()
        if combined.empty:
            continue

        # 전체 기간이 너무 길기 때문에 먼저 마지막 7일을 예시로 시도하고, 변동성이 부족하면 전체 tail을 사용한다.
        end_time = combined.index.max()
        candidate_samples = [
            combined[combined.index >= end_time - pd.Timedelta(days=7)].copy(),
            combined.tail(3000).copy(),
            combined.copy(),
        ]

        for sample in candidate_samples:
            if sample.empty:
                continue
            ranges = sample.max() - sample.min()
            if (ranges <= 0).any():
                continue
            candidate_normalized = (sample - sample.min()) / ranges
            candidate_normalized = candidate_normalized.replace([np.inf, -np.inf], np.nan).dropna()
            if not candidate_normalized.empty:
                normalized = candidate_normalized
                motor_column = candidate_motor_column
                env_column = candidate_env_column
                break

        if not normalized.empty:
            break

    if normalized.empty:
        return

    plt.figure(figsize=(16, 6))
    plt.plot(normalized.index, normalized.iloc[:, 0], label=f"open_rate: {motor_column}")
    plt.plot(normalized.index, normalized.iloc[:, 1], label=f"environment: {env_column}")
    plt.xlabel("Time")
    plt.ylabel("Normalized value (0~1)")
    plt.title("Representative open-rate/environment time-series comparison")
    plt.legend(loc="upper right")
    plt.tight_layout()
    plt.savefig(PLOT_ROOT / "representative_open_rate_environment_timeseries.png", dpi=150)
    plt.close()


# 요구사항의 마지막 항목인 모델 설계 주안점을 자동 리포트에 포함한다.
def build_modeling_design_points(
    gaps: pd.DataFrame,
    delay_abnormal: pd.DataFrame,
    correlations: pd.DataFrame,
    arrival_summary: pd.DataFrame,
) -> List[str]:
    points = []

    if not gaps.empty:
        points.append(
            "5시간 이상 비어있는 구간은 단순 보간 대상으로 보기 어렵다. "
            "학습/검증 분할 시 해당 구간을 경계로 시계열 세그먼트를 나누고, 결측 마스크와 최근 관측 후 경과시간 feature를 추가하는 것이 좋다."
        )
    else:
        points.append(
            "5시간 이상 장기 결측 구간이 확인되지 않더라도, 운영 중 장기 결측 가능성을 대비해 결측 마스크 feature를 유지하는 것이 좋다."
        )

    if not delay_abnormal.empty:
        points.append(
            "ts와 created_at 차이가 3시간 이상인 원시 데이터가 존재한다. "
            "모델 학습에는 이벤트 발생 시각인 ts를 기준으로 정렬하되, 지연 수집 데이터는 별도 플래그로 관리하거나 제외 기준을 둔다."
        )
    else:
        points.append(
            "3시간 이상 ts-created_at 지연 데이터가 발견되지 않았다면 ts 기준 정렬을 기본으로 사용하되, 신규 수집분 검증 로직은 유지한다."
        )

    if not arrival_summary.empty:
        median_of_medians = arrival_summary["median_seconds"].dropna().median()
        if pd.notna(median_of_medians):
            points.append(
                f"파일별 중앙 도착 주기의 중앙값은 약 {median_of_medians:.1f}초이다. "
                f"예측 모델 입력은 원시 주기 그대로보다 {RESAMPLE_RULE} 또는 1분 단위로 리샘플링한 뒤 rolling/diff feature를 만드는 편이 안정적이다."
            )

    if not correlations.empty:
        top = correlations.iloc[0]
        points.append(
            "개폐율과 환경 변수의 상관은 채널/시설별로 다르게 나타날 수 있다. "
            f"현재 분석에서 가장 큰 절대 Pearson 상관 조합은 `{top['motor_metric']}`와 `{top['environment_metric']}`이며, "
            f"상관계수는 {top['pearson_corr']:.3f}이다. 채널별 모델 또는 facility/channel 식별 feature를 고려한다."
        )
        points.append(
            "환경 변화가 개폐율보다 선행/후행할 수 있으므로 온도·습도·강우·풍속의 lag feature, rolling mean, rolling slope를 함께 생성한다."
        )
    else:
        points.append(
            "개폐율-환경 상관계수를 계산할 충분한 겹침 데이터가 부족하다면, 먼저 시간 정렬과 센서 매핑 품질을 확인해야 한다."
        )

    points.extend(
        [
            "개폐율 자체의 이전 값, 변화량, 최근 N분 내 변화 횟수는 강한 autoregressive feature가 될 가능성이 높다.",
            "개폐율이 장시간 변하지 않는 구간이 많으면 회귀 문제와 함께 변화 여부 분류 문제를 병행하거나, 변화 이벤트에 가중치를 주는 학습 전략이 필요하다.",
            "일사량/일조량, 시간대, 주야간 여부, 계절성(sin/cos hour, day-of-year)은 온실 제어 예측에 중요한 외생 변수로 추가하는 것이 좋다.",
            "검증은 랜덤 분할보다 시간 순서 기반 walk-forward split을 사용해 미래 누수를 방지한다.",
        ]
    )
    return points


# 분석 결과를 사람이 읽을 수 있는 Markdown 리포트로 저장한다.
def write_markdown_report(
    file_overview: pd.DataFrame,
    gaps: pd.DataFrame,
    arrival_summary: pd.DataFrame,
    delay_summary: pd.DataFrame,
    delay_abnormal: pd.DataFrame,
    correlations: pd.DataFrame,
    lag_correlations: pd.DataFrame,
) -> Path:
    report_path = OUTPUT_ROOT / "analysis_report.md"
    modeling_points = build_modeling_design_points(gaps, delay_abnormal, correlations, arrival_summary)

    lines = [
        "# 2026-02-11 ~ 2026-05-11 데이터 분석 리포트",
        "",
        "## 분석 설정",
        f"- 분석 기간: `{ANALYSIS_START_TS}` ~ `{ANALYSIS_END_TS}`",
        f"- 입력 폴더: `{ORGANIZED_SENSOR_ROOT.relative_to(PROJECT_ROOT)}`",
        f"- 출력 폴더: `{OUTPUT_ROOT.relative_to(PROJECT_ROOT)}`",
        f"- 장기 결측 기준: `{GAP_THRESHOLD}` 이상",
        f"- ts-created_at 이상 지연 기준: `{TS_CREATED_DELAY_THRESHOLD}` 이상",
        f"- 상관 분석 리샘플링 단위: `{RESAMPLE_RULE}`",
        "",
        "## 파일 개요",
        f"- 분석 파일 수: `{len(file_overview)}`",
        f"- 개폐율 파일 수: `{(file_overview['data_kind'] == 'motor_open_rate').sum() if not file_overview.empty else 0}`",
        f"- 환경/외부 센서 파일 수: `{(file_overview['data_kind'] != 'motor_open_rate').sum() if not file_overview.empty else 0}`",
        "",
        "## 5시간 이상 비어있는 구간",
        f"- 발견 구간 수: `{len(gaps)}`",
    ]

    if not gaps.empty:
        lines.extend(
            [
                f"- 최장 결측 시간: `{gaps['gap_hours'].max():.2f}` 시간",
                "",
                "|순위|센서|구간 유형|시작|끝|시간|",
                "|---:|---|---|---|---|---:|",
            ]
        )
        for rank, row in gaps.head(10).reset_index(drop=True).iterrows():
            lines.append(
                f"|{rank + 1}|{row['sensor_label']}|{row['gap_type']}|{row['gap_start']}|{row['gap_end']}|{row['gap_hours']:.2f}|"
            )
    else:
        lines.append("- 기준을 넘는 장기 결측 구간이 발견되지 않았다.")

    lines.extend(["", "## 데이터 도착 주기"])
    if not arrival_summary.empty:
        lines.extend(
            [
                f"- 파일별 중앙 도착 주기의 중앙값: `{arrival_summary['median_seconds'].dropna().median():.2f}`초",
                f"- 파일별 p95 도착 주기의 중앙값: `{arrival_summary['p95_seconds'].dropna().median():.2f}`초",
                f"- 파일별 최대 도착 주기의 최대값: `{arrival_summary['max_seconds'].dropna().max():.2f}`초",
            ]
        )
    else:
        lines.append("- 도착 주기를 계산할 수 있는 데이터가 없다.")

    lines.extend(["", "## ts와 created_at 차이 3시간 이상 데이터"])
    if not delay_summary.empty:
        lines.extend(
            [
                f"- 3시간 이상 지연 행 수: `{len(delay_abnormal)}`",
                f"- 파일별 최대 절대 지연시간의 최대값: `{delay_summary['max_abs_delay_hours'].dropna().max():.4f}`시간",
            ]
        )
    else:
        lines.append("- created_at 컬럼이 있는 분석 대상 데이터가 없다.")

    lines.extend(["", "## 개폐율과 환경 센서 정보의 연관성"])
    if not correlations.empty:
        lines.extend(
            [
                "|순위|개폐율|환경 변수|Pearson|Spearman|최적 lag(분)|",
                "|---:|---|---|---:|---:|---:|",
            ]
        )
        for rank, row in correlations.head(10).reset_index(drop=True).iterrows():
            best_lag = row.get("best_lag_minutes_by_abs_corr", np.nan)
            lines.append(
                f"|{rank + 1}|{row['motor_metric']}|{row['environment_metric']}|{row['pearson_corr']:.3f}|{row['spearman_corr']:.3f}|{best_lag}|"
            )
    else:
        lines.append("- 충분한 겹침 데이터가 없어 상관계수를 계산하지 못했다.")

    if not lag_correlations.empty:
        best_lag = lag_correlations.iloc[0]
        lines.extend(
            [
                "",
                "## Lag 상관 요약",
                f"- 가장 큰 절대 lag 상관 조합: `{best_lag['motor_metric']}` vs `{best_lag['environment_metric']}`",
                f"- lag: `{best_lag['lag_minutes']}`분, Pearson: `{best_lag['pearson_corr']:.3f}`",
            ]
        )

    lines.extend(["", "## 개폐율 예측 모델 설계 주안점"])
    for point in modeling_points:
        lines.append(f"- {point}")

    lines.extend(
        [
            "",
            "## 생성 파일",
            "- `file_overview.csv`",
            "- `gaps_over_5h.csv`",
            "- `arrival_interval_summary.csv`",
            "- `arrival_intervals_long.csv`",
            "- `ts_created_delay_summary.csv`",
            "- `ts_created_delay_over_3h.csv`",
            "- `open_rate_environment_correlations.csv`",
            "- `open_rate_environment_lag_correlations.csv`",
            "- `plots/*.png`",
        ]
    )

    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


# 전체 분석 파이프라인을 실행한다.
def main() -> Dict[str, pd.DataFrame]:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    PLOT_ROOT.mkdir(parents=True, exist_ok=True)
    configure_plot_fonts()

    sensor_files = discover_sensor_files(ORGANIZED_SENSOR_ROOT)
    if not sensor_files:
        raise FileNotFoundError(f"분석 대상 CSV 파일이 없습니다: {ORGANIZED_SENSOR_ROOT}")

    print("=" * 80)
    print("2026-02-11 ~ 2026-05-11 데이터 분석 시작")
    print("=" * 80)
    print(f"분석 대상 파일 수: {len(sensor_files)}")

    records = [record for path in sensor_files if (record := load_sensor_frame(path)) is not None]

    file_overview = build_file_overview(records)
    gaps = analyze_gaps(records)
    arrival_summary, arrival_intervals = analyze_arrival_intervals(records)
    delay_summary, delay_abnormal = analyze_ts_created_delay(records)
    motor_matrix, environment_matrix = build_resampled_sensor_matrices(records)
    correlations, lag_correlations = analyze_open_rate_environment_relationship(motor_matrix, environment_matrix)

    save_dataframe(file_overview, "file_overview.csv")
    save_dataframe(gaps, "gaps_over_5h.csv")
    save_dataframe(arrival_summary, "arrival_interval_summary.csv")
    save_dataframe(arrival_intervals, "arrival_intervals_long.csv")
    save_dataframe(delay_summary, "ts_created_delay_summary.csv")
    save_dataframe(delay_abnormal, "ts_created_delay_over_3h.csv")
    save_dataframe(correlations, "open_rate_environment_correlations.csv")
    save_dataframe(lag_correlations, "open_rate_environment_lag_correlations.csv")

    plot_arrival_interval_distribution(arrival_intervals)
    plot_gap_duration(gaps)
    plot_delay_summary(delay_summary)
    plot_correlation_heatmap(correlations)
    plot_representative_timeseries(motor_matrix, environment_matrix, correlations)

    report_path = write_markdown_report(
        file_overview=file_overview,
        gaps=gaps,
        arrival_summary=arrival_summary,
        delay_summary=delay_summary,
        delay_abnormal=delay_abnormal,
        correlations=correlations,
        lag_correlations=lag_correlations,
    )

    print("\n분석 완료")
    print(f"출력 폴더: {OUTPUT_ROOT.relative_to(PROJECT_ROOT)}")
    print(f"리포트: {report_path.relative_to(PROJECT_ROOT)}")
    print(f"5시간 이상 결측 구간 수: {len(gaps)}")
    print(f"ts-created_at 3시간 이상 지연 행 수: {len(delay_abnormal)}")
    print(f"상관계수 계산 행 수: {len(correlations)}")
    print("=" * 80)

    return {
        "file_overview": file_overview,
        "gaps": gaps,
        "arrival_summary": arrival_summary,
        "arrival_intervals": arrival_intervals,
        "delay_summary": delay_summary,
        "delay_abnormal": delay_abnormal,
        "correlations": correlations,
        "lag_correlations": lag_correlations,
        "motor_matrix": motor_matrix,
        "environment_matrix": environment_matrix,
    }


if __name__ == "__main__":
    main()
