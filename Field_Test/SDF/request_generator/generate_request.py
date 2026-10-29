import math
import re
from datetime import datetime
from pathlib import Path

_template = (Path(__file__).parent / "prompt_sample.md").read_text(encoding="utf-8")

_match = re.search(r"## SYSTEM PROMPT\n\n(.+?)\n\n---\n\n## USER PROMPT", _template, re.DOTALL)
SYSTEM_PROMPT = _match.group(1).strip()


# 최근 데이터를 항목별로 정리하여 요청 메시지 생성
def build_user_prompt(rows: list[dict]) -> str:
    latest_dt = datetime.fromisoformat(str(rows[-1]["ts"]).split("+")[0])
    first_dt = datetime.fromisoformat(str(rows[0]["ts"]).split("+")[0])

    plant = rows[-1]["plant_name"]
    days = int(float(rows[-1]["days_after_planting"]))
    time_range = f"{first_dt.strftime('%H:%M')}→{latest_dt.strftime('%H:%M')}"

    def fmt_temp(key):  return ", ".join(f"{float(r[key]):.2f}" for r in rows)
    def fmt_rain(key):  return ", ".join(f"{float(r[key]):.2f}" for r in rows)
    def fmt_solar(key): return ", ".join(f"{float(r[key]):.4f}" for r in rows)
    def fmt_win(key):   return ", ".join(str(int(float(r[key]))) for r in rows)

    return f"""Current time: {rows[-1]["ts"]}
Crop: {plant} / {days} days after transplanting

Target temperature: 15°C ~ 20°C
Allowed range: 5°C ~ 30°C
Note: Even if within the allowed range, always control toward 15°C ~ 20°C as closely as possible.

Last 5 min sensor data ({time_range}):
Indoor temp (°C):          {fmt_temp("thermohygro_in_temp")}
Outdoor temp (°C):         {fmt_temp("thermohygro_out_temp")}
Rainfall (0~1):             {fmt_rain("raindrop_rain")}
Solar irradiance (MJ/m²):   {fmt_solar("si")}
Vent1 (%): {fmt_win("probe_1_agsmotor_green_open_rate")}
Vent2 (%): {fmt_win("probe_2_agsmotor_green_open_rate")}
Vent3 (%): {fmt_win("probe_3_agsmotor_green_open_rate")}
Vent4 (%): {fmt_win("probe_4_agsmotor_green_open_rate")}
Vent5 (%): {fmt_win("probe_5_agsmotor_green_open_rate")}
Vent6 (%): {fmt_win("probe_6_agsmotor_green_open_rate")}

Output the 5-minute vent control plan as JSON based on the data above."""
