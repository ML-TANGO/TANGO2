# 7.1_devide_dataset.py 처럼, 데이터를 시각화하여 분석할 수 있게 해주는 도구
# 7.1_devide_dataset.py 처럼 그 파일의 data를 action인지 아닌지 판별한다.

# x축을 시간으로 두고, y축엔 액션이면 1, 아니면 0으로 둔다.
# 그렇게 그래프 png를 7.1.1_analysis_dataset 폴더에 저장한다.
# 그 폴더에는 저 png 말고도, 그래서 각 action데이터가 몇개고, 비 액션데이터가 몇개인지, 그리고 action데이터의 30분 전후 범위 안에 있는 비 액션데이터가 몇개인지 정보를 담은 txt 파일을 저장한다.

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

DEFAULT_INPUT = "7_merged_data_postprocessed/time_sync_valid_data_merged_no_na_post_round0.csv"
DEFAULT_OUT_DIR = "7.1_analysis_dataset"
MOTOR_COLS = [f"probe_{i}_agsmotor_green_open_rate" for i in range(1, 9)]
NEAR_MINUTES = 30


def _validate_columns(df: pd.DataFrame) -> None:
    required = ["ts", "facility_id"] + MOTOR_COLS
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"입력 CSV에 필요한 컬럼이 없습니다: {missing}")


def detect_action_rows(df: pd.DataFrame, *, facility_col: str = "facility_id") -> pd.Series:
    """
    액션 판정 (facility_id 단위):
    같은 facility_id 안에서 ts 정렬 후 직후 row가 정확히 1분 뒤이고,
    motor 8개 중 하나라도 변하면 현재 row를 액션으로 판정.
    """
    ts = pd.to_datetime(df["ts"], format="ISO8601", utc=True, errors="coerce")
    if ts.isna().any():
        raise ValueError("ts 컬럼 파싱에 실패한 값이 있습니다.")

    work = df.assign(_ts=ts)
    work = work.sort_values([facility_col, "_ts"], kind="mergesort")
    grp = work.groupby(facility_col, sort=False)
    next_ts = grp["_ts"].shift(-1)
    one_minute_later = (next_ts - work["_ts"]) == pd.Timedelta(minutes=1)

    changed = pd.Series(False, index=work.index)
    for c in MOTOR_COLS:
        cur = pd.to_numeric(work[c], errors="coerce")
        nxt = grp[c].transform(lambda s: pd.to_numeric(s, errors="coerce").shift(-1))
        changed |= (cur != nxt) & ~(cur.isna() & nxt.isna())

    action_sorted = one_minute_later & changed
    return action_sorted.reindex(df.index, fill_value=False)


def _save_action_timeline_png(
    ts: pd.Series,
    action_mask: pd.Series,
    near_non_action_mask: pd.Series,
    *,
    title: str,
    path: Path,
) -> None:
    """y=1 액션, y=0 비액션. 근처 비액션은 주황, 그 외 비액션은 청색 계열."""
    act = action_mask.astype(bool).reindex(ts.index, fill_value=False)
    near_na = near_non_action_mask.astype(bool).reindex(ts.index, fill_value=False)
    far_na = (~act) & (~near_na)
    y0 = pd.Series(0.0, index=ts.index)
    y1 = pd.Series(1.0, index=ts.index)

    fig, ax = plt.subplots(figsize=(14, 4))
    # 뒤에서 앞 순: 멀리 비액션 → 근처 비액션 → 액션
    if far_na.any():
        ax.scatter(
            ts.loc[far_na],
            y0.loc[far_na],
            s=2,
            c="#4a90d9",
            alpha=0.35,
            label="non-action",
            rasterized=True,
        )
    if near_na.any():
        ax.scatter(
            ts.loc[near_na],
            y0.loc[near_na],
            s=3,
            c="#e67e22",
            alpha=0.55,
            label="non-action (near action, ±window)",
            rasterized=True,
        )
    if act.any():
        ax.scatter(
            ts.loc[act],
            y1.loc[act],
            s=3,
            c="#c0392b",
            alpha=0.75,
            label="action",
            rasterized=True,
        )
    ax.set_xlabel("time")
    ax.set_ylabel("action (1) / non-action (0)")
    ax.set_yticks([0, 1])
    ax.set_title(title)
    ax.grid(True, alpha=0.3)
    ax.legend(loc="upper right", fontsize=8, framealpha=0.9)
    fig.autofmt_xdate()
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150)
    plt.close(fig)


def mark_near_action_non_action_rows(
    df: pd.DataFrame,
    action_mask: pd.Series,
    *,
    near_minutes: int = NEAR_MINUTES,
    facility_col: str = "facility_id",
) -> pd.Series:
    ts = pd.to_datetime(df["ts"], format="ISO8601", utc=True, errors="coerce")
    near_any = pd.Series(False, index=df.index)
    window = pd.Timedelta(minutes=near_minutes)

    for _, idx in df.groupby(facility_col, sort=False).groups.items():
        idx = pd.Index(idx)
        ts_f = ts.reindex(idx)
        act_f = action_mask.reindex(idx, fill_value=False)
        action_ts = ts_f[act_f].sort_values()
        if action_ts.empty:
            continue
        near_f = pd.Series(False, index=idx)
        for t in action_ts:
            near_f |= (ts_f >= t - window) & (ts_f <= t + window)
        near_any.loc[idx] = near_f.to_numpy()

    return near_any & ~action_mask


def run_analysis(
    df: pd.DataFrame,
    *,
    out_dir: Path,
    near_minutes: int = NEAR_MINUTES,
    png_name: str = "action_timeline.png",
    txt_name: str = "action_stats.txt",
    labeled_csv_name: str = "labeled_with_action.csv",
) -> None:
    action_mask = detect_action_rows(df)
    near_non_action_mask = mark_near_action_non_action_rows(
        df, action_mask, near_minutes=near_minutes
    )

    n_action = int(action_mask.sum())
    n_non_action = int((~action_mask).sum())
    n_non_action_within_30m_of_action = int(near_non_action_mask.sum())
    n_total = int(len(df))

    print(f"total_rows: {n_total}")
    print(f"action_rows: {n_action}")
    print(f"non_action_rows: {n_non_action}")

    out_dir.mkdir(parents=True, exist_ok=True)

    # x축은 시간, y축은 액션여부(액션이면 1, 아니면 0)
    ts = pd.to_datetime(df["ts"], format="ISO8601", utc=True, errors="coerce")

    png_path = out_dir / png_name
    _save_action_timeline_png(
        ts,
        action_mask,
        near_non_action_mask,
        title="Action vs time (full)",
        path=png_path,
    )

    # 날짜(UTC 일자)별 타임라인 PNG
    png_stem = Path(png_name).stem
    plot_df = pd.DataFrame(
        {
            "ts": ts,
            "action": action_mask.reindex(ts.index, fill_value=False),
            "near_na": near_non_action_mask.reindex(ts.index, fill_value=False),
        }
    )
    for day, g in plot_df.groupby(plot_df["ts"].dt.date, sort=True):
        day_str = day.isoformat() if hasattr(day, "isoformat") else str(day)
        daily_path = out_dir / f"{png_stem}_{day_str}.png"
        _save_action_timeline_png(
            g["ts"],
            g["action"],
            g["near_na"],
            title=f"Action vs time ({day_str}, UTC)",
            path=daily_path,
        )

    # 통계 정보 저장
    txt_path = out_dir / txt_name
    lines = [
        f"input_rows: {len(df)}",
        f"action_rows: {n_action}",
        f"non_action_rows: {n_non_action}",
        (
            f"non_action_rows_within_{near_minutes}min_before_or_after_any_action: "
            f"{n_non_action_within_30m_of_action}"
        ),
    ]
    txt_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # 입력 CSV에 action 여부 컬럼 추가하여 저장
    labeled_csv_path = out_dir / labeled_csv_name
    df_labeled = df.copy()
    df_labeled["action"] = action_mask.reindex(df.index, fill_value=False).astype(int)
    df_labeled.to_csv(labeled_csv_path, index=False)

    n_daily = ts.dt.date.nunique()
    print(f"saved: {png_path}")
    print(f"saved: {n_daily} daily PNG(s) under {out_dir} ({png_stem}_YYYY-MM-DD.png)")
    print(f"saved: {txt_path}")
    print(f"saved: {labeled_csv_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="액션/비액션 판별 후 타임라인 PNG와 통계 TXT를 저장합니다."
    )
    parser.add_argument(
        "input_csv",
        nargs="?",
        default=DEFAULT_INPUT,
        help=f"입력 CSV (기본: {DEFAULT_INPUT})",
    )
    parser.add_argument(
        "--out-dir",
        default=DEFAULT_OUT_DIR,
        help=f"출력 폴더 (기본: {DEFAULT_OUT_DIR})",
    )
    parser.add_argument(
        "--near-minutes",
        type=int,
        default=NEAR_MINUTES,
        help=f"액션 전후 비액션 집계 구간(분) (기본: {NEAR_MINUTES})",
    )
    parser.add_argument(
        "--labeled-csv-name",
        default=None,
        help="action 컬럼이 추가된 CSV 파일명(미지정 시 입력 stem 기반 자동 생성)",
    )
    args = parser.parse_args()

    in_path = Path(args.input_csv)
    if not in_path.is_file():
        raise FileNotFoundError(f"입력 CSV가 없습니다: {in_path}")

    df = pd.read_csv(in_path)
    _validate_columns(df)

    stem = in_path.stem
    labeled_csv_name = (
        args.labeled_csv_name
        if args.labeled_csv_name is not None
        else f"{stem}_with_action.csv"
    )
    run_analysis(
        df,
        out_dir=Path(args.out_dir),
        near_minutes=args.near_minutes,
        png_name=f"{stem}_action_timeline.png",
        txt_name=f"{stem}_action_stats.txt",
        labeled_csv_name=labeled_csv_name,
    )


if __name__ == "__main__":
    main()
