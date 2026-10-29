import json
import logging
import os
import re

import requests

from request_generator.generate_request import SYSTEM_PROMPT, build_user_prompt
from .validator import apply_action_correction

OLLAMA_URL = os.getenv("OLLAMA_URL", "")
MODEL = os.getenv("OLLAMA_MODEL", "gemma4:e4b")
OLLAMA_API_KEY = os.getenv("OLLAMA_API_KEY", "")

log = logging.getLogger("sdf_agent")


# 생성형AI API 요청/응답
def _call_ollama(user_prompt: str) -> str:
    log.debug("=== SYSTEM PROMPT ===\n%s", SYSTEM_PROMPT)
    log.debug("=== USER PROMPT ===\n%s", user_prompt)
    headers = {"Authorization": f"Bearer {OLLAMA_API_KEY}"} if OLLAMA_API_KEY else None
    resp = requests.post(
        OLLAMA_URL,
        json={
            "model": MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            "options": {"num_ctx": 8192},
        },
        headers=headers,
        timeout=300,
    )
    resp.raise_for_status()
    raw = resp.json()["message"]["content"]
    log.debug("=== LLM RESPONSE ===\n%s", raw)
    return raw


# 생성형AI 응답 파싱 및 형식 검증
def _parse(raw: str) -> dict | None:
    cleaned = re.sub(r"```json|```", "", raw).strip()
    data = None
    for candidate in [cleaned, cleaned + "\n}"]:
        try:
            data = json.loads(candidate)
            break
        except json.JSONDecodeError:
            pass
    if data is None:
        log.debug("parse failed (JSONDecodeError)")
        return None
    plan = data.get("plan", [])
    if len(plan) != 5:
        log.debug("parse failed: plan length=%d (expected 5)", len(plan))
        return None
    for row in plan:
        if any(not isinstance(row.get(f"probe_{i}"), int) for i in range(1, 7)):
            log.debug("parse failed: non-int probe value in row %s", row)
            return None
    return data


# 생성형AI API 연동 실행
def run(facility_df) -> dict | None:
    facility_id = facility_df["facility_id"].iloc[0]
    rows = facility_df.tail(5).to_dict("records")
    if len(rows) < 5:
        log.warning("LAM skip %s: only %d rows", facility_id, len(rows))
        return None
    try:
        raw = _call_ollama(build_user_prompt(rows))
        plan = _parse(raw)
        if plan is None:
            log.warning("LAM parse error %s", facility_id)
            return None
        log.info("LAM ok   %s", facility_id)
        return apply_action_correction(plan, rows)
    except Exception as e:
        log.error("LAM err  %s: %s", facility_id, e)
        return None
