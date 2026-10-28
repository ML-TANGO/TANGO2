"""Generated FINDINGS text -> structured report, with gpt-6-luna.

Only the generated report text is sent (no image, no DICOM header, no patient data).
The labeler is told to reorganise, never to add: every statement must come from the
generated text. Statements that cannot hold for a single study (comparisons with a
"previous examination"), that contradict another statement, or that are advice rather
than findings are moved out of the report into `excluded_statements`, so they stay
visible instead of silently vanishing.
"""
from __future__ import annotations

import json
import os

MODEL = "gpt-6-luna"

SECTIONS = [
    ("airways", "Trachea & Airways"),
    ("lungs", "Lungs"),
    ("pleura", "Pleura"),
    ("heart", "Heart & Pericardium"),
    ("mediastinum", "Mediastinum & Hila"),
    ("vessels", "Vessels"),
    ("esophagus", "Esophagus"),
    ("upper_abdomen", "Upper Abdomen"),
    ("bones", "Bones & Soft Tissue"),
]

INSTRUCTION = """You are a radiology report editor. You receive the FINDINGS text of one chest CT report written by an AI model. Rewrite it as a structured report in the JSON schema.

Rules:
1. Use only information in the text. Never add a finding, measurement, location or recommendation that is not written there.
2. Keep laterality, lobe, size, number and severity exactly as written.
3. Put each statement in the matching section. Write findings as short radiology phrases, one finding per item. Merge statements that say the same thing.
4. A section is "abnormal" if it has any positive finding, "normal" if the text only describes it as normal, and "not_mentioned" if the text does not describe it. For a normal section give one short normal statement.
5. Only one study is available. Any statement that compares with a previous or prior examination, or describes change over time, goes to excluded_statements with reason "refers to a prior examination" and not into a section.
6. If two statements contradict each other, keep neither in the sections; put both in excluded_statements with reason "contradicts another statement".
7. A recommendation or advice (for example "clinical correlation is recommended", "follow-up is advised") is not a finding: put it in excluded_statements with reason "recommendation, not a finding".
8. impression: the clinically significant positive findings, most important first, each a short phrase. If there are none, one item: "No significant abnormality."
"""


def schema() -> dict:
    section = {
        "type": "object",
        "properties": {
            "status": {"type": "string", "enum": ["normal", "abnormal", "not_mentioned"]},
            "findings": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["status", "findings"],
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {
            "sections": {
                "type": "object",
                "properties": {k: section for k, _ in SECTIONS},
                "required": [k for k, _ in SECTIONS],
                "additionalProperties": False,
            },
            "impression": {"type": "array", "items": {"type": "string"}},
            "excluded_statements": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string"},
                        "reason": {"type": "string", "enum": [
                            "refers to a prior examination", "contradicts another statement",
                            "recommendation, not a finding"]},
                    },
                    "required": ["text", "reason"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["sections", "impression", "excluded_statements"],
        "additionalProperties": False,
    }


def structure(report: str) -> dict:
    import openai
    client = openai.OpenAI(timeout=90, max_retries=3)
    r = client.responses.create(
        model=MODEL, instructions=INSTRUCTION, input=f"FINDINGS:\n{report}",
        text={"format": {"type": "json_schema", "name": "structured_ct_report",
                         "schema": schema(), "strict": True}},
        reasoning={"effort": "none"}, store=False)
    if r.model != MODEL:
        raise RuntimeError(f"requested {MODEL}, response came from {r.model}")
    out = json.loads(r.output_text)
    out["_meta"] = {"model": r.model, "response_id": r.id}
    return out


def available() -> bool:
    return bool(os.environ.get("OPENAI_API_KEY"))
