#!/usr/bin/env python3
"""Generate a shareable markdown report from B notebook outputs (channel-level only)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_ROOT = PROJECT_ROOT / "data_inspect" / "output" / "motor_temperature_daily_pattern_260211-260511"
PLOT_ROOT = OUTPUT_ROOT / "plots"
REPORT_PATH = OUTPUT_ROOT / "B_notebook_channel_analysis_report.md"


def read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path) if path.exists() else pd.DataFrame()


def df_to_md_table(df: pd.DataFrame, max_rows: int = 20, float_fmt: str = "{:.2f}") -> str:
    if df.empty:
        return "*(데이터 없음)*\n"
    display_df = df.head(max_rows).copy()
    for col in display_df.columns:
        if display_df[col].dtype == "float64":
            display_df[col] = display_df[col].apply(lambda x: float_fmt.format(x) if pd.notna(x) else "")
    return display_df.to_markdown(index=False) + "\n"


def build_report() -> str:
    lines: list[str] = []

    # Title
    lines.append("# 모터 개폐 채널별 분석 및 온도 변화 보고서\n")
    lines.append("> **분석 기간**: 2026-02-11 ~ 2026-05-11  ")
    lines.append("> **기준 시간대**: Asia/Seoul (KST)  ")
    lines.append("> **출처 노트북**: `data_inspect_260211-260511_B.ipynb`  ")
    lines.append("> **핵심 원칙**: 전체 평균 개폐율 자료은 제외하고, **채널별** 자료와 **시간대/날짜별 온도 변화**만 다룬다.\n")

    # 1. Overview
    lines.append("## 1. 개요\n")
    lines.append("이 보고서는 온실 제어 동작을 채널 단위로 해석하기 위해 작성되었다.  ")
    lines.append("16개 모터 채널(단동 7동 8채널, 단동 8동 8채널)의 개폐 이벤트와 시간대/날짜별 온도 변화를 중심으로 구성한다.\n")

    # 2. Motor event definition
    lines.append("## 2. 모터 개폐 이벤트 정의\n")
    lines.append("- `open_rate`가 직전 관측값보다 **1.0%p 이상 증가**하면 `open`(열림) 이벤트로 본다.")
    lines.append("- `open_rate`가 직전 관측값보다 **1.0%p 이상 감소**하면 `close`(닫힘) 이벤트로 본다.")
    lines.append("- 이 방식은 개폐 명령 자체가 아니라, 결과 상태값인 개폐율 변화를 이용한 추정이다.")
    lines.append("- 따라서 해석할 때는 '모터가 열린/닫힌 것으로 관측된 시각'으로 이해하는 것이 안전하다.\n")

    motor_events = read_csv(OUTPUT_ROOT / "motor_open_close_events.csv")
    if not motor_events.empty:
        event_count = int(len(motor_events))
        open_count = int((motor_events["event_type"] == "open").sum())
        close_count = int((motor_events["event_type"] == "close").sum())
        channel_count = int(motor_events["sensor_label"].nunique())
        lines.append(f"**전체 이벤트 수**: {event_count:,}건 (open {open_count:,}, close {close_count:,})  ")
        lines.append(f"**분석 채널 수**: {channel_count}개\n")

    # 3. Channel-level heatmaps
    lines.append("## 3. 채널별 시간대 개폐 패턴\n")
    lines.append("아래 히트맵은 각 채널이 하루 24시간 중 어느 시간대에 개폐 변화가 많았는지를 보여준다.  ")
    lines.append("색이 진할수록 해당 채널과 시간대에 이벤트가 집중되었음을 의미한다.\n")
    lines.append(f"![채널별 열림 이벤트 히트맵]({PLOT_ROOT / 'motor_open_events_channel_hour_heatmap.png'})\n")
    lines.append(f"![채널별 닫힘 이벤트 히트맵]({PLOT_ROOT / 'motor_close_events_channel_hour_heatmap.png'})\n")

    # 4. Channel peak hours
    lines.append("## 4. 채널별 피크 시간\n")
    lines.append("각 채널의 open/close 이벤트가 가장 많이 발생한 시간대를 정리한다.  ")
    lines.append("같은 시설 내에서도 채널별로 피크 시간이 다를 수 있음을 확인할 수 있다.\n")

    peak = read_csv(OUTPUT_ROOT / "motor_channel_open_close_peak_hours.csv")
    if not peak.empty:
        lines.append("### 전체 기간 채널별 피크 시간\n")
        lines.append(df_to_md_table(peak, max_rows=20))

    monthly_peak = read_csv(OUTPUT_ROOT / "monthly_motor_channel_open_close_peak_hours.csv")
    if not monthly_peak.empty:
        lines.append("### 월별 채널별 피크 시간\n")
        for month, group in monthly_peak.groupby("month"):
            lines.append(f"#### {month}\n")
            lines.append(df_to_md_table(group.drop(columns=["month"]).reset_index(drop=True), max_rows=20))

    # 5. Hourly temperature profile
    lines.append("## 5. 시간대별 내부/외부 온도 변화\n")
    lines.append("기간 전체를 하루 24시간으로 접어 평균적인 일중 온도 곡선을 확인한다.  ")
    lines.append("- **선**: 시간대별 평균 온도  ")
    lines.append("- **음영**: 10~90 percentile 범위 (같은 시간대라도 날짜에 따라 온도가 얼마나 달랐는지)\n")

    temp_profile = read_csv(OUTPUT_ROOT / "temperature_hourly_profile.csv")
    if not temp_profile.empty:
        lines.append("### 내부/외부 온도 시간대별 요약\n")
        lines.append(df_to_md_table(temp_profile, max_rows=48))

    lines.append(f"![시간대별 내부/외부 온도 변화]({PLOT_ROOT / 'temperature_hourly_profile_internal_external.png'})\n")

    # 6. Internal-external gap
    lines.append("## 6. 시간대별 내부-외부 온도 차이\n")
    lines.append("내부온도에서 외부온도를 뺀 값이다.  ")
    lines.append("낮 시간대(9~15시)에 차이가 가장 크고, 야간에는 상대적으로 줄어든다.  ")
    lines.append("이 차이가 클 때 환기 개방 가능성이 높아지는지 채널별 오버레이 그래프에서 추가로 확인할 수 있다.\n")

    gap = read_csv(OUTPUT_ROOT / "temperature_internal_external_gap_by_hour.csv")
    if not gap.empty:
        lines.append(df_to_md_table(gap, max_rows=24))
    lines.append(f"![시간대별 내부-외부 온도 차이]({PLOT_ROOT / 'temperature_internal_external_gap_by_hour.png'})\n")

    # 7. Daily temperature summary
    lines.append("## 7. 일별 내부/외부 온도 요약\n")
    lines.append("분석 기간 동안 매일의 내부온도와 외부온도 평균/중앙값/p10/p90을 날짜별로 정리한다.\n")

    daily_temp = read_csv(OUTPUT_ROOT / "daily_temperature_summary.csv")
    if not daily_temp.empty:
        lines.append(df_to_md_table(daily_temp, max_rows=30))

    # 8. Monthly temperature hourly profile
    lines.append("## 8. 월별 시간대별 온도 프로필\n")
    lines.append("월마다 하루 24시간의 온도 패턴이 어떻게 달라지는지 확인한다.  ")
    lines.append("2월과 5월의 낮 최고 온도, 야간 최저 온도 차이를 비교할 수 있다.\n")

    monthly_temp = read_csv(OUTPUT_ROOT / "monthly_temperature_hourly_profile.csv")
    if not monthly_temp.empty:
        for month, group in monthly_temp.groupby("month"):
            lines.append(f"### {month}\n")
            lines.append(df_to_md_table(group.drop(columns=["month"]).reset_index(drop=True), max_rows=24))

    # 9. Monthly internal-external gap
    lines.append("## 9. 월별 시간대별 내부-외부 온도 차이\n")
    lines.append("월마다 내부-외부 온도 차이의 시간대별 패턴을 비교한다.  ")
    lines.append("4~5월에 낮 시간대 차이가 어떻게 변화하는지 확인할 수 있다.\n")

    monthly_gap = read_csv(OUTPUT_ROOT / "monthly_temperature_internal_external_gap_by_hour.csv")
    if not monthly_gap.empty:
        for month, group in monthly_gap.groupby("month"):
            lines.append(f"### {month}\n")
            lines.append(df_to_md_table(group.drop(columns=["month"]).reset_index(drop=True), max_rows=24))

    # 10. Channel overlay graphs
    lines.append("## 10. 채널별 모터 개폐와 온도 변화 오버레이\n")
    lines.append("각 채널별로 시간대별 열림/닫힘 이벤트 수와 전체 내부/외부온도 평균 곡선을 같은 그래프에 표시했다.  ")
    lines.append("이 그래프를 보면 다음을 구분할 수 있다.  ")
    lines.append("- 특정 채널만 집중적으로 동작하는 시간대가 있는가?  ")
    lines.append("- 같은 시설 안에서도 채널별 열림/닫힘 패턴이 다른가?  ")
    lines.append("- 채널별 개폐 시각이 내부온도 상승 또는 외부온도 변화와 겹치는가?\n")

    overlay_files = sorted((PLOT_ROOT / "channel_overlay").glob("*.png"))
    for path in overlay_files:
        rel = path.name.replace("motor_temperature_overlay_", "").replace(".png", "")
        lines.append(f"- `{rel}`: `plots/channel_overlay/{path.name}`")
    lines.append("")

    # 11. Monthly channel heatmaps
    lines.append("## 11. 월별 채널별 개폐 히트맵\n")
    lines.append("월 단위로 채널-시간대별 open/close 이벤트 수를 히트맵으로 정리했다.  ")
    lines.append("월이 지남에 따라 어떤 채널이 더 자주(또는 덜 자주) 움직였는지 비교할 수 있다.\n")

    for month in ["2026_02", "2026_03", "2026_04", "2026_05"]:
        lines.append(f"### {month}\n")
        open_img = PLOT_ROOT / f"monthly_motor_open_channel_hour_heatmap_{month}.png"
        close_img = PLOT_ROOT / f"monthly_motor_close_channel_hour_heatmap_{month}.png"
        if open_img.exists():
            lines.append(f"![{month} open 히트맵]({open_img})\n")
        if close_img.exists():
            lines.append(f"![{month} close 히트맵]({close_img})\n")

    # 12. Daily open_rate by channel
    lines.append("## 12. 채널별 일별 개폐율 추세\n")
    lines.append("각 채널의 일별 평균 개폐율을 전체 기간에 걸쳐 시계열로 표시했다.  ")
    lines.append("어떤 채널이 먼저 개폐율이 상승했고, 어떤 채널이 상승 시점이 늦었는지 확인할 수 있다.\n")

    daily_or_files = sorted((PLOT_ROOT / "daily_channel_open_rate").glob("*.png"))
    for path in daily_or_files:
        rel = path.name.replace("daily_open_rate_", "").replace(".png", "")
        lines.append(f"- `{rel}`: `plots/daily_channel_open_rate/{path.name}`")
    lines.append("")

    # 13. Monthly channel open_rate overlay
    lines.append("## 13. 채널별 월별 개폐율과 온도 오버레이\n")
    lines.append("각 채널을 월 단위로 분리해서, 해당 월의 시간별 개폐율과 내부/외부온도를 함께 표시했다.  ")
    lines.append("같은 채널이라도 월마다 개폐율-온도 관계가 어떻게 달라지는지 확인할 수 있다.\n")

    monthly_overlay_root = PLOT_ROOT / "monthly_channel_open_rate_overlay"
    for month_dir in sorted(monthly_overlay_root.glob("*")):
        if not month_dir.is_dir():
            continue
        month_label = month_dir.name
        lines.append(f"### {month_label}\n")
        for path in sorted(month_dir.glob("*.png")):
            rel = path.name.replace("open_rate_temperature_overlay_", "").replace(".png", "")
            lines.append(f"- `{rel}`: `plots/monthly_channel_open_rate_overlay/{month_label}/{path.name}`")
        lines.append("")

    # 14. Artifacts list
    lines.append("## 14. 참조 CSV 파일 목록\n")
    lines.append("| 파일명 | 설명 |")
    lines.append("|---|---|")
    lines.append("| `motor_open_close_events.csv` | 모든 채널의 개폐 이벤트 원본 (2,938행) |")
    lines.append("| `motor_open_close_events_by_channel_hour.csv` | 채널-시간대별 이벤트 수 |")
    lines.append("| `motor_channel_open_close_peak_hours.csv` | 채널별 피크 open/close 시간 |")
    lines.append("| `monthly_motor_channel_open_close_peak_hours.csv` | 월별 채널별 피크 시간 |")
    lines.append("| `temperature_hourly_long.csv` | 시간별 내부/외부 온도 (long format) |")
    lines.append("| `temperature_hourly_profile.csv` | 시간대별 내부/외부 온도 평균/p10/p90 |")
    lines.append("| `temperature_internal_external_gap_by_hour.csv` | 시간대별 내부-외부 온도차 |")
    lines.append("| `temperature_internal_external_gap_hourly.csv` | 시간별 내부-외부 온도차 (long) |")
    lines.append("| `daily_temperature_summary.csv` | 일별 내부/외부 온도 요약 |")
    lines.append("| `monthly_temperature_hourly_profile.csv` | 월별 시간대별 온도 프로필 |")
    lines.append("| `monthly_temperature_internal_external_gap_by_hour.csv` | 월별 시간대별 온도차 |")
    lines.append("| `daily_open_rate_by_channel.csv` | 일별 채널별 개폐율 요약 |")
    lines.append("| `monthly_open_rate_by_channel_hour.csv` | 월별 채널-시간대별 개폐율 |")
    lines.append("")

    lines.append("---\n")
    lines.append("*본 보고서는 `data_inspect/scripts/generate_B_notebook_channel_report.py`를 실행하여 자동 생성되었다.*\n")

    return "\n".join(lines)


def main() -> None:
    report = build_report()
    REPORT_PATH.write_text(report, encoding="utf-8")
    print(REPORT_PATH)


if __name__ == "__main__":
    main()
