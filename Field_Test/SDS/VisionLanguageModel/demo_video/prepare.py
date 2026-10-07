#!/usr/bin/env python3
"""
demo_video/prepare.py — 영상 데모용 데이터 묶음을 만든다 (개발 서버에서 실행).

입력: 시뮬레이터가 내보낸 영상 세션 (video_data_guide/<세션>/data/<시나리오>/)
출력: demo_video/data/
  scenarios.json                 시나리오 목록과 메타데이터
  <시나리오>/video.mp4           원본 영상 (라벨이 그려진 그대로, 재생용)
  <시나리오>/frames.json         프레임별 선박 상태, 분석 격자 프레임의 프롬프트
  <시나리오>/inputs/fNNNNNN.png  분석 격자 프레임의 모델 입력 이미지 (336x336)

모델 입력 이미지:
  1. 영상 하단의 라벨 표 영역을 잘라낸다 (y >= CUT_Y 제거, 1920x896 이 남는다).
  2. 학습과 같은 CLIPImageProcessor 의 resize(짧은 변 336) + center crop 을 적용한다.
  llama.cpp 는 336x336 입력을 리사이즈 없이 쓰므로, 이 PNG 가 그대로 모델 입력이 된다.

프롬프트:
  scripts/prepare_sds_dataset.py 의 format_ais(include_bbox=False) 와 PROMPT_KO 를
  그대로 쓰고, 체크포인트 토크나이저의 chat template 을 적용해 저장한다.
  서버는 <image> 를 llama-server 의 미디어 마커로 바꾸기만 한다.

사용:
  python demo_video/prepare.py \
      --session /home/ywlee/SSD/data/tango_conf_demo/video_data_guide/2026-09-30_13-05-39 \
      --ckpt    /home/ywlee/SSD/checkpoints/tango2-sds-vlm-eva/clip_qwen3_proj_lora_marine_sds_ko_9k \
      --clip    openai/clip-vit-large-patch14-336
"""
import argparse
import csv
import json
import os
import shutil
import subprocess
import sys

import numpy as np
import pandas as pd
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "scripts"))
from prepare_sds_dataset import PROMPT_KO, format_ais  # noqa: E402  학습 프롬프트와 같은 형식

# 영상 하단 라벨 표의 가장 높은 시작 위치는 y=900 이었다 (5개 시나리오, 측정값).
# 표는 행 수에 따라 900~956 에서 시작하므로 모든 시나리오에 같은 경계를 쓴다.
CUT_Y = 896

TYPE_KO = {
    "HeadOn": "마주침", "Crossing": "횡단", "Overtaking": "추월",
}

# 프레임별 선박 상태에 담는 열 (frames.json 의 ships 배열 순서)
SHIP_FIELDS = ["ship_id", "my_ship", "latitude", "longitude", "knot", "heading",
               "cpa", "tcpa", "length", "width"]


def parse_args():
    p = argparse.ArgumentParser("영상 데모 데이터 준비")
    p.add_argument("--session", required=True, help="세션 폴더 (session_manifest.json 이 있는 곳)")
    p.add_argument("--ckpt", required=True, help="체크포인트 디렉토리 (토크나이저, chat template)")
    p.add_argument("--clip", default="openai/clip-vit-large-patch14-336")
    p.add_argument("--out", default=os.path.join(HERE, "data"))
    p.add_argument("--grid", type=int, default=15,
                   help="분석 가능한 프레임 간격 (기본 15 = 0.5초)")
    return p.parse_args()


def read_frames(video_path, keep, counter, width=1920, height=1080):
    """영상을 처음부터 순서대로 디코딩하며 keep 에 든 디코더 인덱스의 프레임만 돌려준다.

    가이드 3장: H.264 에서 시킹하면 한두 프레임 어긋날 수 있으므로 순차 디코딩한다.
    passthrough 는 출력 단계에서 프레임을 복제하거나 버리지 않게 한다 (디코더 인덱스 유지).
    counter["n"] 에 디코딩한 전체 프레임 수를 남긴다.
    """
    proc = subprocess.Popen(
        ["ffmpeg", "-loglevel", "error", "-i", video_path, "-fps_mode", "passthrough",
         "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        stdout=subprocess.PIPE)
    size = width * height * 3
    idx = 0
    try:
        while True:
            buf = proc.stdout.read(size)
            if len(buf) < size:
                break
            if idx in keep:
                yield idx, np.frombuffer(buf, np.uint8).reshape(height, width, 3)
            idx += 1
    finally:
        counter["n"] = idx
        proc.stdout.close()
        proc.wait()


def model_input(frame, proc):
    """표 영역을 잘라내고 학습과 같은 CLIP resize + center crop 을 적용한 336x336 이미지."""
    img = Image.fromarray(frame[:CUT_Y])
    arr = proc(images=img, do_rescale=False, do_normalize=False,
               return_tensors="np").pixel_values[0]
    return Image.fromarray(np.round(arr).astype(np.uint8).transpose(1, 2, 0))


def load_samples(scn_dir):
    """video_frame → DataFrame. 가이드대로 파일 이름이 아니라 CSV 안의 video_frame 으로 찾는다."""
    by_frame = {}
    for name in sorted(os.listdir(os.path.join(scn_dir, "samples"))):
        if name.endswith(".csv"):
            df = pd.read_csv(os.path.join(scn_dir, "samples", name))
            df.columns = df.columns.str.lower()
            frame = int(df["video_frame"].iloc[0])
            if frame in by_frame:
                raise SystemExit(f"{scn_dir}: video_frame {frame} 를 가리키는 CSV 가 둘 이상입니다 ({name})")
            by_frame[frame] = df
    return by_frame


def first_video_frame(scn_dir):
    with open(os.path.join(scn_dir, "frame_timestamps.csv"), newline="", encoding="utf-8") as f:
        return int(next(csv.DictReader(f))["video_frame"])


def build_scenario(scn_dir, out_root, tok, proc, grid):
    meta = json.load(open(os.path.join(scn_dir, "scenario.json"), encoding="utf-8"))
    sid = meta["scenarioId"]
    out = os.path.join(out_root, sid)
    shutil.rmtree(os.path.join(out, "inputs"), ignore_errors=True)   # 이전 실행의 이미지가 섞이지 않게
    os.makedirs(os.path.join(out, "inputs"))
    shutil.copy2(os.path.join(scn_dir, meta["videoFile"]), os.path.join(out, "video.mp4"))

    samples = load_samples(scn_dir)
    first = first_video_frame(scn_dir)
    n = meta["frameCount"]
    frames = list(range(first, first + n))
    missing = [f for f in frames if f not in samples]
    if missing:
        raise SystemExit(f"{sid}: 라벨이 없는 프레임 {len(missing)}개 (예: {missing[:5]}). "
                         "이 데모는 모든 프레임에 라벨이 있는 세션을 가정한다.")

    # 프레임별 선박 상태 (재생 중 표와 레이더 표시에 쓴다)
    ships = []
    for f in frames:
        df = samples[f]
        ships.append([[round(float(r[k]), 6) for k in SHIP_FIELDS] for _, r in df.iterrows()])

    # 분석 격자 프레임: 프롬프트와 모델 입력 이미지
    grid_frames = frames[::grid]
    prompts, ais_texts = {}, {}
    for f in grid_frames:
        ais = format_ais(samples[f], "ko", include_bbox=False)
        human = f"<image>\n{ais}\n\n{PROMPT_KO}"
        prompts[f] = tok.apply_chat_template([{"role": "user", "content": human}],
                                             tokenize=False, add_generation_prompt=True)
        ais_texts[f] = ais
    keep = {f - first for f in grid_frames}
    decoded = {}
    for idx, frame in read_frames(os.path.join(out, "video.mp4"), keep, decoded,
                                  meta["videoWidth"], meta["videoHeight"]):
        model_input(frame, proc).save(os.path.join(out, "inputs", f"f{idx + first:06d}.png"))
    if decoded["n"] != n:
        raise SystemExit(f"{sid}: 디코딩한 프레임 {decoded['n']}개, scenario.json 의 frameCount {n}개")
    written = len(os.listdir(os.path.join(out, "inputs")))
    if written != len(grid_frames):
        raise SystemExit(f"{sid}: 모델 입력 이미지 {written}개, 기대 {len(grid_frames)}개")

    situation = meta["situationType"]
    base = situation.replace("_Collision", "")
    with open(os.path.join(out, "frames.json"), "w", encoding="utf-8") as fp:
        json.dump({
            "id": sid,
            "situation": situation,
            "first_frame": first,
            "fps": meta["videoFps"],
            "frame_count": n,
            "ship_fields": SHIP_FIELDS,
            "ships": ships,
            "grid": grid_frames,
            "prompts": prompts,
            "ais": ais_texts,
        }, fp, ensure_ascii=False)
    print(f"[Prepare] {sid}: 프레임 {n}, 분석 격자 {len(grid_frames)} (간격 {grid})")
    return {
        "id": sid,
        "situation": situation,
        "type_ko": TYPE_KO.get(base, base),
        "collision_course": situation.endswith("_Collision"),
        "duration_sec": n / meta["videoFps"],
        "num_targets": int((samples[first]["my_ship"] == 0).sum()),
    }


def main():
    args = parse_args()
    from transformers import AutoTokenizer, CLIPImageProcessor
    tok = AutoTokenizer.from_pretrained(args.ckpt)
    proc = CLIPImageProcessor.from_pretrained(args.clip)

    manifest = json.load(open(os.path.join(args.session, "session_manifest.json"), encoding="utf-8"))
    os.makedirs(args.out, exist_ok=True)
    scenarios = []
    for s in manifest["scenarios"]:
        if s["status"] != "accepted":
            continue
        scenarios.append(build_scenario(os.path.join(args.session, s["relativePath"]),
                                        args.out, tok, proc, args.grid))

    # 같은 유형이 여러 개면 A, B 로 구분한다
    seen = {}
    for s in scenarios:
        key = (s["type_ko"], s["collision_course"])
        seen[key] = seen.get(key, 0) + 1
    count = {}
    for s in scenarios:
        key = (s["type_ko"], s["collision_course"])
        count[key] = count.get(key, 0) + 1
        suffix = f" {chr(64 + count[key])}" if seen[key] > 1 else ""
        s["title"] = f"{s['type_ko']}{' · 충돌 코스' if s['collision_course'] else ''}{suffix}"

    with open(os.path.join(args.out, "scenarios.json"), "w", encoding="utf-8") as fp:
        json.dump({
            "session": manifest["sessionId"],
            "cut_y": CUT_Y,
            "grid": args.grid,
            "scenarios": scenarios,
        }, fp, ensure_ascii=False, indent=1)
    print(f"[Prepare] 완료 → {args.out}  (시나리오 {len(scenarios)}개)")


if __name__ == "__main__":
    main()
