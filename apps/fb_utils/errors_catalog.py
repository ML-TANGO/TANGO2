"""errors.yaml 런타임 매칭 (SP-3 I / SP-1 v2 §8).

외부 컨테이너나 플랫폼 코드가 발행한 에러 `code` 를 errors.yaml 카탈로그의
4-튜플(problem/cause/fix/docs_url + severity)로 변환해 UI 친화 메시지로 표시한다.
미등록 code 는 generic fallback(크래시 X). 카탈로그는 1회 로드 후 캐시.

사용: BFF 가 외부 잡 에러를 UI(SSE status)로 surface 할 때 enrich(code, message).
"""
from __future__ import annotations

import os
import re
from typing import Any, Dict, Optional

_ERRORS_YAML = os.path.join(os.path.dirname(__file__), "errors.yaml")

_CACHE: Optional[Dict[str, Any]] = None


def _catalog() -> Dict[str, Any]:
    """errors.yaml 의 errors 맵 (1회 로드 캐시). 파싱 실패/yaml 부재 시 빈 맵."""
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    try:
        import yaml  # PyYAML — 운영 이미지에 존재(6.x). 부재 시 graceful fallback.
        with open(_ERRORS_YAML, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        errors = data.get("errors")
        _CACHE = errors if isinstance(errors, dict) else {}
    except Exception:
        # yaml 부재 / 파일 손상 / 파싱 실패 — 전부 generic fallback 으로 동작.
        _CACHE = {}
    return _CACHE


def lookup(code: Optional[str]) -> Optional[Dict[str, Any]]:
    """code → 4-튜플 dict (등록된 경우) 또는 None (미등록)."""
    if not code:
        return None
    entry = _catalog().get(code)
    if not isinstance(entry, dict):
        return None
    return {
        "code": code,
        "problem": entry.get("problem"),
        "cause": entry.get("cause"),
        "fix": entry.get("fix"),
        "docs_url": entry.get("docs_url"),
        "severity": entry.get("severity", "error"),
    }


# 미등록(파트너 제공) code/message 는 신뢰 불가 — SSE/FE 메모리 bloat 방지 위해
# code 형식 정규화 + message 길이 cap. (FE 는 problem 을 텍스트로 렌더해야 함 — XSS 방지.)
_CODE_RE = re.compile(r"^E_[A-Z0-9_]{1,64}$")
_MAX_MSG = 1000


def _safe_code(code: Optional[str]) -> str:
    return code if (code and _CODE_RE.match(code)) else "E_UNKNOWN"


def _cap(s: Optional[str]) -> Optional[str]:
    if not s:
        return s
    return s if len(s) <= _MAX_MSG else (s[:_MAX_MSG] + "…")


def enrich(code: Optional[str], message: Optional[str] = None) -> Dict[str, Any]:
    """code → UI 표시용 에러 상세. 등록 code 면 4-튜플, 미등록이면 generic fallback
    (problem=원본 메시지, 길이 cap). 항상 dict 반환(크래시 X)."""
    message = _cap(message)
    hit = lookup(code)
    if hit:
        # problem 이 비어 있으면(카탈로그 누락) 원본 메시지로 보강. 변형 대신
        # dict-unpack(불변 — lookup 은 새 dict 를 주지만 스타일 일관성).
        if not hit.get("problem") and message:
            return {**hit, "problem": message}
        return hit
    return {
        # 미등록 code 는 형식 정규화(임의 긴 문자열 차단).
        "code": _safe_code(code),
        "problem": message or "작업 중 오류가 발생했습니다.",
        "cause": None,
        "fix": None,
        "docs_url": None,
        "severity": "error",
    }
