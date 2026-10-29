import os


VENT_OVERLAP_MARGIN = min(100, max(0, int(os.getenv("VENT_OVERLAP_MARGIN", "20"))))
MAX_VENT_GAP = 100 - VENT_OVERLAP_MARGIN

VENT_OVERLAP_PAIRS = ((5, 3), (6, 4))


# 측창과 천창의 개도 차이가 허용 범위를 넘지 않도록 제어 명령 보정
def enforce_vent_overlap(plan: dict, rows: list[dict] | None = None) -> dict:
    for side_probe, roof_probe in VENT_OVERLAP_PAIRS:
        last = rows[-1] if rows else {}
        first = plan["plan"][0]
        side_now = last.get(f"probe_{side_probe}_agsmotor_green_open_rate",
                            first[f"probe_{side_probe}"])
        roof_now = last.get(f"probe_{roof_probe}_agsmotor_green_open_rate",
                            first[f"probe_{roof_probe}"])

        for step in plan["plan"]:
            side = step[f"probe_{side_probe}"]
            roof = step[f"probe_{roof_probe}"]

            if side - roof > MAX_VENT_GAP:

                roof_fixed = side - MAX_VENT_GAP
                side_fixed = roof + MAX_VENT_GAP
                move_if_roof = abs(side - side_now) + abs(roof_fixed - roof_now)
                move_if_side = abs(side_fixed - side_now) + abs(roof - roof_now)

                if move_if_roof <= move_if_side:
                    step[f"probe_{roof_probe}"] = roof_fixed
                else:
                    step[f"probe_{side_probe}"] = side_fixed

            side_now = step[f"probe_{side_probe}"]
            roof_now = step[f"probe_{roof_probe}"]
    return plan


# 제어 명령 검증 및 보정 실행
def apply_action_correction(plan: dict, rows: list[dict]) -> dict:

    return enforce_vent_overlap(plan, rows)
