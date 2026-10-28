"""HTML for the structured report and classifier panel; CT slice images for the viewer."""
from __future__ import annotations

import html
from datetime import datetime
from typing import List, Optional

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from structurer import SECTIONS

LUNG_WINDOW = (-600, 1500)                          # level, width

CSS = """
.sr { font-family: Inter, system-ui, sans-serif; line-height: 1.45; color: var(--body-text-color); }
.sr h2 { font-size: 1.15rem; margin: 0 0 .25rem; letter-spacing: .02em; }
.sr .meta { color: var(--body-text-color-subdued); font-size: .82rem; margin-bottom: .9rem; }
.sr .imp { border-left: 4px solid #3b82f6; background: rgba(59,130,246,.08);
           padding: .6rem .9rem; border-radius: 6px; margin-bottom: 1rem; }
.sr .imp ol { margin: .3rem 0 0 1.1rem; padding: 0; }
.sr table { width: 100%; border-collapse: collapse; font-size: .92rem; }
.sr td { padding: .45rem .6rem; border-top: 1px solid var(--border-color-primary); vertical-align: top; }
.sr td.sec { width: 11.5rem; font-weight: 600; white-space: nowrap; }
.sr td ul { margin: 0; padding-left: 1rem; }
.sr .pill { display: inline-block; font-size: .72rem; font-weight: 700; padding: .05rem .5rem;
            border-radius: 999px; margin-left: .4rem; vertical-align: 1px; }
.sr .abnormal { background: rgba(239,68,68,.15); color: #ef4444; }
.sr .normal { background: rgba(34,197,94,.15); color: #16a34a; }
.sr .not_mentioned { background: rgba(148,163,184,.18); color: #94a3b8; }
.sr .excl { margin-top: 1rem; font-size: .85rem; border: 1px dashed #f59e0b; border-radius: 6px;
            padding: .5rem .8rem; background: rgba(245,158,11,.06); }
.sr .excl b { color: #d97706; }
.sr .fhead { font-weight: 700; font-size: 1rem; margin-bottom: .6rem; display: flex; align-items: center; gap: .5rem; }
.sr .count { background: #ef4444; color: #fff; border-radius: 999px; font-size: .75rem; padding: .05rem .55rem; }
.sr .fcard { display: grid; grid-template-columns: 1fr 90px 2.6rem; align-items: center; gap: .7rem;
             padding: .55rem .75rem; margin-bottom: .45rem; border-radius: 10px;
             background: linear-gradient(90deg, rgba(239,68,68,.14), rgba(239,68,68,.03));
             border: 1px solid rgba(239,68,68,.28); }
.sr .fname { font-weight: 600; font-size: .9rem; }
.sr .fbar { height: 6px; background: rgba(148,163,184,.25); border-radius: 3px; overflow: hidden; }
.sr .fbar span { display: block; height: 100%; background: linear-gradient(90deg, #f97316, #ef4444); }
.sr .fscore { font-variant-numeric: tabular-nums; font-size: .82rem; opacity: .8; text-align: right; }
.sr .fnone { opacity: .7; padding: .5rem 0; }
.sr .fsub { margin: .9rem 0 .4rem; font-size: .8rem; text-transform: uppercase; letter-spacing: .06em; opacity: .65; }
.sr .chips { display: flex; flex-wrap: wrap; gap: .35rem; }
.sr .chip { font-size: .78rem; padding: .2rem .6rem; border-radius: 999px;
            border: 1px solid rgba(245,158,11,.45); color: #f59e0b; background: rgba(245,158,11,.08); }
.sr .orig { white-space: pre-wrap; font-size: .92rem; line-height: 1.6; }
.hero h1 { margin: 0; font-size: 1.7rem; font-weight: 800; letter-spacing: -.01em;
           background: linear-gradient(90deg, #60a5fa, #a78bfa 55%, #f472b6);
           -webkit-background-clip: text; background-clip: text; color: transparent; }
.hero .tag { opacity: .7; font-size: .9rem; }
.hero .badges { margin-top: .45rem; display: flex; gap: .4rem; flex-wrap: wrap; }
.hero .badge { font-size: .72rem; padding: .15rem .55rem; border-radius: 999px;
               border: 1px solid rgba(148,163,184,.35); opacity: .85; }
.view-label { text-align: center; font-size: .75rem; letter-spacing: .12em; text-transform: uppercase; opacity: .7; }
.sr .disclaimer { margin-top: 1rem; font-size: .78rem; color: var(--body-text-color-subdued); }
"""

DISCLAIMER = ("AI-generated draft for research demonstration. Not a medical device; "
              "not for diagnostic use. Must be reviewed by a radiologist.")


def esc(s) -> str:
    return html.escape(str(s))


def structured_html(sr: dict, case, model_load_s: Optional[float] = None) -> str:
    imp = "".join(f"<li>{esc(x)}</li>" for x in sr["impression"])
    rows = []
    for key, title in SECTIONS:
        sec = sr["sections"][key]
        items = "".join(f"<li>{esc(f)}</li>" for f in sec["findings"]) or "<li>—</li>"
        label = sec["status"].replace("_", " ")
        rows.append(f"<tr><td class='sec'>{esc(title)}<br><span class='pill {sec['status']}'>"
                    f"{esc(label)}</span></td><td><ul>{items}</ul></td></tr>")
    excl = ""
    if sr["excluded_statements"]:
        lis = "".join(f"<li>{esc(e['text'])} <i>({esc(e['reason'])})</i></li>"
                      for e in sr["excluded_statements"])
        excl = (f"<div class='excl'><b>Excluded from the report</b> — model statements that "
                f"are not findings of this single study:<ul>{lis}</ul></div>")
    t = case.timing
    fixed = (" · <b>head–foot orientation corrected</b> (header disagreed with anatomy)"
             if case.si_flipped else "")
    meta = (f"Input: {esc(case.source)} · {case.shape[0]}×{case.shape[1]}×{case.shape[2]} · "
            f"spacing {case.spacing[0]}×{case.spacing[1]}×{case.spacing[2]} mm{fixed}<br>"
            f"Segmentation {t.get('segmentation_s', '—')} s · preprocessing "
            f"{t.get('preprocessing_s', '—')} s · generation {t.get('generation_s', '—')} s · "
            f"structuring {t.get('structuring_s', '—')} s")
    return (f"<div class='sr'><h2>CHEST CT — STRUCTURED REPORT</h2><div class='meta'>{meta}</div>"
            f"<div class='imp'><b>IMPRESSION</b><ol>{imp}</ol></div>"
            f"<table>{''.join(rows)}</table>{excl}"
            f"<div class='disclaimer'>{DISCLAIMER}</div></div>")


def findings_html(rows: List[dict]) -> str:
    """Positive findings as cards; lower-confidence 'possible' ones as small chips below."""
    pos = sorted((r for r in rows if r["tier"] == "present"), key=lambda r: -r["score"])
    possible = sorted((r for r in rows if r["tier"] == "possible"), key=lambda r: -r["score"])[:5]
    cards = "".join(
        f"<div class='fcard'><div class='fname'>{esc(r['finding'])}</div>"
        f"<div class='fbar'><span style='width:{r['score'] * 100:.0f}%'></span></div>"
        f"<div class='fscore'>{r['score']:.2f}</div></div>" for r in pos)
    if not cards:
        cards = "<div class='fnone'>No finding classified positive.</div>"
    chips = "".join(f"<span class='chip'>{esc(r['finding'])}</span>" for r in possible)
    poss = (f"<div class='fsub'>Possible · lower confidence</div><div class='chips'>{chips}</div>"
            if chips else "")
    return (f"<div class='sr'><div class='fhead'>Positive findings <span class='count'>{len(pos)}</span></div>"
            f"{cards}{poss}</div>")


def printable(sr: dict, case, classifier_rows: List[dict]) -> str:
    """A standalone HTML report for download / print."""
    body = structured_html(sr, case)
    raw = esc(case.report).replace("\n", "<br>")
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>Chest CT structured report</title>
<style>:root{{--body-text-color:#111;--body-text-color-subdued:#555;--border-color-primary:#ddd}}
body{{max-width:820px;margin:2rem auto;padding:0 1rem}}{CSS}</style></head><body>
{body}
<div class="sr" style="margin-top:1.5rem"><h2 style="font-size:1rem">Classifier findings</h2>{findings_html(classifier_rows)}</div>
<div class="sr" style="margin-top:1.5rem"><h2 style="font-size:1rem">Original model output (FINDINGS)</h2>
<p style="font-size:.88rem">{raw}</p></div>
<div class="sr disclaimer">Generated {datetime.now().astimezone().isoformat(timespec='seconds')}</div>
</body></html>"""


# ---------------------------------------------------------------- viewer

def _window(x: np.ndarray) -> np.ndarray:
    level, width = LUNG_WINDOW
    lo = level - width / 2
    return (np.clip((x.astype(np.float32) - lo) / width, 0, 1) * 255).astype(np.uint8)


def original_html(case) -> str:
    return (f"<div class='sr'><div class='meta'>Unedited model output — FINDINGS</div>"
            f"<div class='orig'>{esc(case.report)}</div>"
            f"<div class='disclaimer'>{DISCLAIMER}</div></div>")


# The preprocessed volume's axes are (I->S, R->L, A->P): correct LPS, with index 0 at
# the feet. (engine.preprocess fixes scans whose header has the head-foot direction
# reversed, so every volume arrives this way.) Each plane: (slice axis, how to cut it,
# orientation letters top/bottom/left/right). Display follows the LPS / DICOM
# convention: patient Right on screen-left, Anterior at the top of the axial view,
# Superior at the top of coronal and sagittal.
VIEWS = {
    "axial":    (0, lambda v, i: v[i].T,             ("A", "P", "R", "L")),
    "coronal":  (2, lambda v, i: v[::-1, :, i],      ("S", "I", "R", "L")),
    "sagittal": (1, lambda v, i: v[::-1, i, :],      ("S", "I", "A", "P")),
}


def slice_image(vol: np.ndarray, lungs: Optional[np.ndarray], plane: str, idx: int,
                overlay: bool = True, size: int = 384) -> Image.Image:
    _, cut, (top, bottom, left, right) = VIEWS[plane]
    g = _window(cut(vol, idx))
    rgb = np.stack([g, g, g], -1).astype(np.float32)
    if overlay and lungs is not None:
        m = cut(lungs, idx)
        tint = np.array([59, 130, 246], np.float32)
        rgb[m] = rgb[m] * 0.72 + tint * 0.28
    img = Image.fromarray(rgb.astype(np.uint8)).resize((size, size), Image.BILINEAR)
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default(size=18)
    for text, xy, anchor in ((top, (size / 2, 6), "mt"), (bottom, (size / 2, size - 6), "mb"),
                             (left, (8, size / 2), "lm"), (right, (size - 8, size / 2), "rm")):
        draw.text(xy, text, fill=(250, 204, 21), font=font, anchor=anchor,
                  stroke_width=2, stroke_fill=(0, 0, 0))
    draw.text((size - 8, size - 6), f"{idx + 1}/{vol.shape[VIEWS[plane][0]]}", fill=(203, 213, 225),
              font=ImageFont.load_default(size=13), anchor="rb", stroke_width=2, stroke_fill=(0, 0, 0))
    return img
