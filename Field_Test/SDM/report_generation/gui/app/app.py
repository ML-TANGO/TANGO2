#!/usr/bin/env python3
"""Chest CT -> report: the interactive demo.

Upload a chest CT (NIfTI, DICOM files, or a .zip of a DICOM series). The server
segments the lungs, applies the TC1 preprocessing and generates the FINDINGS text with
the TC1 model; gpt-6-luna turns that text into a structured report. CT data stays on
the server; only the generated report text goes to the OpenAI API.

Layout: upload -> three orthogonal views -> report (Structured / Original) beside the
findings the classifier marks positive.
"""
from __future__ import annotations

import json
import os
import time
import traceback

import gradio as gr

import engine
import render
import structurer

WORK = os.environ.get("GUI_WORK", "/work")
os.environ["GUI_WORK"] = WORK
os.makedirs(WORK, exist_ok=True)

print("[gui] loading model…", flush=True)
MODEL = engine.Model()
print(f"[gui] model loaded in {MODEL.load_s} s", flush=True)

SAMPLES = sorted(os.path.join("/samples", f) for f in os.listdir("/samples")
                 if f.endswith((".nii", ".nii.gz", ".zip"))) if os.path.isdir("/samples") else []
# Viewer planes in display order, with the volume axis each slider moves along.
PLANES = tuple((name, render.VIEWS[name][0]) for name in ("axial", "coronal", "sagittal"))

# Open in dark mode unless the viewer chose otherwise.
HEAD = """<script>if (!location.search.includes('__theme')) {
  const u = new URL(location); u.searchParams.set('__theme', 'dark'); location.replace(u); }</script>"""

HERO = """<div class="hero">
  <h1>Chest CT Foundation</h1>
  <div class="tag">3D chest CT → radiology report · on-premises inference</div>
  <div class="badges"><span class="badge">JECT_Generator</span>
  <span class="badge">TotalSegmentator lung crop</span></div>
</div>"""

PLACEHOLDER = "<div class='sr' style='opacity:.55;padding:2.5rem 0;text-align:center'>{}</div>"


def analyse(files, progress=gr.Progress()):
    engine.cleanup_old(WORK)
    paths = [f if isinstance(f, str) else f.name for f in (files or [])]
    try:
        progress(0.03, desc="Reading the upload…")
        case = engine.load_input(paths)
        engine.run(case, MODEL, lambda p, d: progress(p, desc=d))
        rows = MODEL.tiers(case)
        progress(0.85, desc="Structuring the report…")
        t = time.perf_counter()
        sr = structurer.structure(case.report)
        case.timing["structuring_s"] = round(time.perf_counter() - t, 1)
    except engine.InputError as e:
        raise gr.Error(str(e))
    except Exception as e:
        traceback.print_exc()
        raise gr.Error(f"{type(e).__name__}: {e}")

    progress(0.97, desc="Rendering…")
    base = os.path.join(case.workdir, "chest_ct_report")
    json.dump({"structured_report": {k: v for k, v in sr.items() if k != "_meta"}, "generated_findings": case.report,
               "positive_findings": [r for r in rows if r["tier"] == "present"],
               "input": {"source": case.source, "shape": case.shape, "spacing_mm": case.spacing},
               "timing_s": case.timing}, open(base + ".json", "w"), indent=2)
    open(base + ".html", "w").write(render.printable(sr, case, rows))

    state = {"vol": case.volume, "lungs": case.lungs}
    mids = {name: case.volume.shape[axis] // 2 for name, axis in PLANES}
    images = [render.slice_image(case.volume, case.lungs, name, mids[name]) for name, _ in PLANES]
    sliders = [gr.update(value=mids[name], interactive=True) for name, _ in PLANES]
    done = (f"✓ Report ready in **{sum(case.timing.values()):.0f} s** · {case.source} · "
            f"{case.shape[0]}×{case.shape[1]}×{case.shape[2]}")
    return (render.structured_html(sr, case), render.original_html(case),
            render.findings_html(rows), [base + ".html", base + ".json"], state,
            *images, *sliders, done)


def redraw(state, plane, idx, overlay):
    if not state:
        return None
    return render.slice_image(state["vol"], state["lungs"], plane, int(idx), overlay)


with gr.Blocks(title="Chest CT Foundation") as demo:
    state = gr.State(None)
    images, sliders = {}, {}

    with gr.Row(equal_height=True):
        with gr.Column(scale=5):
            gr.HTML(HERO)
        with gr.Column(scale=4):
            files = gr.File(label="Chest CT — NIfTI, DICOM files, or .zip of one series",
                            file_count="multiple", height=110)
        with gr.Column(scale=2, min_width=180):
            go = gr.Button("Generate report", variant="primary", size="lg")
            status = gr.Markdown("")
    if SAMPLES:
        gr.Examples([[[s]] for s in SAMPLES], inputs=[files], label="Sample cases",
                    examples_per_page=6)

    with gr.Row():
        for name, _ in PLANES:
            with gr.Column(min_width=220):
                gr.HTML(f"<div class='view-label'>{name}</div>")
                images[name] = gr.Image(show_label=False, type="pil", interactive=False,
                                        height=330, container=False)
                sliders[name] = gr.Slider(0, 255, value=128, step=1, show_label=False,
                                          interactive=False)
    overlay = gr.Checkbox(value=True, label="Lung segmentation overlay")

    with gr.Row():
        with gr.Column(scale=7):
            with gr.Tabs():
                with gr.Tab("Structured report"):
                    structured = gr.HTML(PLACEHOLDER.format("The structured report appears here."))
                with gr.Tab("Original report"):
                    original = gr.HTML(PLACEHOLDER.format("The model's original text appears here."))
        with gr.Column(scale=4):
            findings = gr.HTML(PLACEHOLDER.format("Positive findings appear here."))
            downloads = gr.File(label="Download (HTML · JSON)", interactive=False, height=90)

    go.click(analyse, inputs=[files],
             outputs=[structured, original, findings, downloads, state,
                      *[images[n] for n, _ in PLANES], *[sliders[n] for n, _ in PLANES], status])
    for name, _ in PLANES:
        args = [state, gr.State(name), sliders[name], overlay]
        sliders[name].change(redraw, inputs=args, outputs=images[name], show_progress="hidden")
        overlay.change(redraw, inputs=args, outputs=images[name], show_progress="hidden")

if __name__ == "__main__":
    if not structurer.available():
        print("[gui] WARNING: OPENAI_API_KEY not set — structuring will fail", flush=True)
    demo.queue(default_concurrency_limit=1, max_size=8)
    # SHARE=1 opens a public gradio.live link (traffic relayed through Gradio's servers);
    # GUI_PASSWORD then puts a login in front of it.
    share = os.environ.get("SHARE") == "1"
    password = os.environ.get("GUI_PASSWORD")
    demo.launch(server_name="0.0.0.0", server_port=7860, share=share,
                auth=(os.environ.get("GUI_USER", "demo"), password) if password else None,
                theme=gr.themes.Soft(primary_hue="indigo", neutral_hue="slate"),
                css=render.CSS, head=HEAD, allowed_paths=[WORK], max_file_size="2gb",
                footer_links=[])
