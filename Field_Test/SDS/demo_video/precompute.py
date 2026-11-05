#!/usr/bin/env python3
"""
demo_video/precompute.py — 시나리오마다 일정 간격 프레임을 미리 추론해 results.json 에 저장한다.

표준 라이브러리만 쓴다 (Orin 에서 llama-server 와 함께 실행).
이미 저장된 프레임은 건너뛰므로 중단 후 다시 실행하면 이어서 계산한다.

사용:
  python3 demo_video/precompute.py --llm http://127.0.0.1:8080 --every 60
"""
import argparse
import base64
import datetime
import json
import os
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))


def strip_think(text):
    return text.split("</think>")[-1].strip()


def post(url, body, timeout=900):
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def main():
    ap = argparse.ArgumentParser("영상 데모 사전 추론")
    ap.add_argument("--llm", default="http://127.0.0.1:8080")
    ap.add_argument("--data", default=os.path.join(HERE, "data"))
    ap.add_argument("--every", type=int, default=60, help="분석 간격 (프레임, 분석 격자의 배수)")
    ap.add_argument("--n_predict", type=int, default=512)
    ap.add_argument("--device", default="Jetson AGX Orin 32GB", help="결과에 기록할 장비 이름")
    args = ap.parse_args()

    llm = args.llm.rstrip("/")
    with urllib.request.urlopen(llm + "/props", timeout=10) as r:
        props = json.loads(r.read())
    marker = props["media_marker"]
    model = os.path.basename(props.get("model_path", ""))
    index = json.load(open(os.path.join(args.data, "scenarios.json"), encoding="utf-8"))
    if args.every % index["grid"]:
        raise SystemExit(f"--every 는 분석 격자 간격({index['grid']})의 배수여야 합니다")

    for s in index["scenarios"]:
        sdir = os.path.join(args.data, s["id"])
        frames = json.load(open(os.path.join(sdir, "frames.json"), encoding="utf-8"))
        out_path = os.path.join(sdir, "results.json")
        results = {"model": model, "device": args.device, "every": args.every, "frames": {}}
        if os.path.exists(out_path):
            old = json.load(open(out_path, encoding="utf-8"))
            if old.get("model") == model:
                results["frames"] = old["frames"]
        targets = frames["grid"][:: args.every // index["grid"]]
        for frame in targets:
            if str(frame) in results["frames"]:
                continue
            with open(os.path.join(sdir, "inputs", f"f{frame:06d}.png"), "rb") as f:
                image = base64.b64encode(f.read()).decode()
            t0 = time.time()
            j = post(llm + "/completion", {
                "prompt": {"prompt_string": frames["prompts"][str(frame)].replace("<image>", marker),
                           "multimodal_data": [image]},
                "n_predict": args.n_predict, "temperature": 0.0, "top_k": 1,
                "cache_prompt": False, "stream": False})
            wall = time.time() - t0
            tm = j.get("timings", {})
            results["frames"][str(frame)] = {
                "text": strip_think(j["content"]),
                "stop_type": j.get("stop_type"),
                "wall_s": round(wall, 3),
                "prompt_n": tm.get("prompt_n"), "prompt_ms": tm.get("prompt_ms"),
                "predicted_n": tm.get("predicted_n"),
                "predicted_per_second": tm.get("predicted_per_second"),
                "created": datetime.datetime.now().isoformat(timespec="seconds"),
            }
            with open(out_path, "w", encoding="utf-8") as fp:      # 프레임마다 저장 (중단 대비)
                json.dump(results, fp, ensure_ascii=False, indent=1)
            print(f"[Pre] {s['title']:<12} frame {frame:4d}  {wall:5.1f}s  "
                  f"{tm.get('predicted_per_second', 0):.1f} tok/s", flush=True)
    print("[Pre] 완료", flush=True)


if __name__ == "__main__":
    main()
