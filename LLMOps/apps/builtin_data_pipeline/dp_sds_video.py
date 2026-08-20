#!/usr/bin/env python3
"""데이터 파이프라인 — 항해 영상 수집 노드(kind=src, stage=sds_video).

스케줄러가 빌트인 잡 pod 안에서 아래로 실행한다.

    python3 -u /built_in/dp_sds_video.py --params_path=/dataset/_runs/<run_id>/<node_index>/params.json

브리지 카메라 MP4 를 타임스탬프가 붙은 프레임 시퀀스로 바꾼다. 시정·날씨·선박 외형처럼
AIS 기하로는 알 수 없는 시각 정보의 유일한 출처라, 여기서 프레임을 놓치면 뒤 단계가
아무리 정확해도 복구할 수 없다.

입력 마운트
  /datasets/{access}/{name}/...   RO — 소스 데이터셋(voyage.mp4 + frames_index.csv)
  /dataset                        RW — 이 파이프라인의 작업 데이터셋

타임스탬프 출처 (우선순위)
  1) frames_index.csv  — frame_idx · timestamp · scene_id. 있으면 이걸 정본으로 쓴다.
  2) 컨테이너 creation_time 메타 + PTS 경과
  3) 없으면 T0 기준 상대시각으로 진행하고 경고를 남긴다.
     (여기서 죽이지 않는 이유: 조인 노드가 어차피 허용오차로 걸러내므로, 실행을
      막기보다 사람이 결과를 보고 판단하게 두는 편이 낫다.)

산출(out_dir 아래)
  config.json    이 실행에 쓴 기능 목록·파라미터 (비교의 기준)
  assets.jsonl   프레임 1장 = 1줄 (frame_idx · timestamp · scene_id 포함)
  drops.jsonl    제외된 프레임: 어느 기능에서 왜
  funnel.json    [{stage, in, out, dropped{사유:건수}}]
  assets/        프레임 이미지(다음 노드의 입력)
  samples/       화면에 보여줄 썸네일 일부
"""
import argparse
import csv
import json
import os
import time
from datetime import datetime, timedelta

# ── 기능 이름 (BE constants.SDS_VIDEO_LIBRARY 의 key 와 문자 단위로 같아야 한다) ──
STEP_SAMPLE = "타임스탬프 프레임"
STEP_LIMIT = "장면 수 제한"

TS_FMT = "%Y-%m-%d %H:%M:%S"
EPOCH = datetime(1970, 1, 1)
VIDEO_EXT = {".mp4", ".mov", ".mkv", ".avi", ".m4v"}
INDEX_NAME = "frames_index.csv"
SAMPLE_LIMIT = 24          # 화면 썸네일 상한. 전량 뽑으면 용량이 터진다.
THUMB_EDGE = 320


def log(event, **kw):
    """stdout JSON Lines. 플랫폼이 로그를 그대로 보관하고 사람이 읽는다."""
    print(json.dumps({"event": event, **kw}, ensure_ascii=False), flush=True)


# ── 소스 찾기 ────────────────────────────────────────────────────────────────
def _walk(datasets_root, sources):
    """소스로 지정된 하위 경로만 훑는다. 지정이 없으면 마운트 전체를 훑는다."""
    # 소스가 비었을 때 /datasets 전체로 폴백하지 않는다 — 워크스페이스의 무관한
    # 데이터셋까지 빨아들이면서 화면상으로는 정상으로 보인다(가장 찾기 어려운 실패다).
    if not sources:
        raise RuntimeError("읽을 소스가 지정되지 않았습니다 — 데이터 소스(데이터셋 · 폴더)를 "
                           "먼저 고르세요 (params.sources 가 비어 있습니다)")
    roots = [os.path.join(datasets_root, s.lstrip("/")) for s in sources]
    for root in roots:
        if not os.path.isdir(root):
            log("log", level="warn", message=f"소스 경로가 없습니다: {root}")
            continue
        for dirpath, _dirnames, filenames in os.walk(root):
            for name in sorted(filenames):
                yield os.path.join(dirpath, name)


def find_video(datasets_root, sources):
    """첫 번째 영상 파일. 여러 개면 경로 정렬 순으로 하나만 쓰고 나머지는 로그에 남긴다."""
    found = [p for p in _walk(datasets_root, sources)
             if os.path.splitext(p)[1].lower() in VIDEO_EXT]
    if not found:
        return None
    if len(found) > 1:
        log("log", level="warn",
            message=f"영상이 {len(found)}개입니다 — 첫 번째만 사용합니다: {found[0]}",
            skipped=found[1:])
    return found[0]


def find_index(video_path, datasets_root, sources):
    """frames_index.csv. 영상과 같은 디렉터리를 먼저 보고, 없으면 소스 전체에서 찾는다."""
    same_dir = os.path.join(os.path.dirname(video_path), INDEX_NAME)
    if os.path.isfile(same_dir):
        return same_dir
    for p in _walk(datasets_root, sources):
        if os.path.basename(p) == INDEX_NAME:
            return p
    return None


def read_index(path):
    """frame_idx → {timestamp, scene_id}. 숫자로 못 읽는 행은 건너뛴다."""
    rows = {}
    with open(path, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            try:
                idx = int(r["frame_idx"])
            except (KeyError, TypeError, ValueError):
                continue
            rows[idx] = {"timestamp": (r.get("timestamp") or "").strip(),
                         "scene_id": (r.get("scene_id") or "").strip()}
    return rows


def parse_dt(s):
    """ISO / 공백구분 / 압축형을 모두 받아 naive datetime 으로."""
    s = (s or "").strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(s).replace(tzinfo=None)
    except ValueError:
        pass
    head = s.split("+")[0].split(".")[0]
    for fmt in (TS_FMT, "%Y-%m-%dT%H:%M:%S", "%Y%m%dT%H%M%S"):
        try:
            return datetime.strptime(head, fmt)
        except ValueError:
            continue
    raise ValueError(f"읽을 수 없는 시각 표기: {s!r}")


def resolve_start(container):
    """(기준시각, 상대시각인가). 메타가 없으면 T0 기준으로 진행하고 호출부가 경고한다."""
    meta = (container.metadata or {}).get("creation_time")
    if meta:
        try:
            return parse_dt(meta), False
        except ValueError:
            log("log", level="warn", message=f"영상 creation_time 을 읽지 못했습니다: {meta!r}")
    return EPOCH, True


# ── 프레임 추출 ──────────────────────────────────────────────────────────────
def decode_indexed(container, index, limit):
    """frames_index.csv 에 적힌 프레임만 뽑는다.

    인덱스가 정본이므로 fps 파라미터는 무시한다 — 어느 프레임을 쓸지 데이터가 이미
    정해 놓은 상황에서 다시 샘플링하면 인덱스와 어긋난 자산이 나온다.
    """
    wanted = dict(sorted(index.items())[:limit]) if limit else dict(index)
    out, missing = [], set(wanted)
    for i, vframe in enumerate(container.decode(video=0)):
        if i not in wanted:
            continue
        meta = wanted[i]
        out.append((i, meta["timestamp"], meta.get("scene_id") or "", vframe.to_image()))
        missing.discard(i)
        if not missing:
            break
    out.sort(key=lambda t: t[0])
    return out, sorted(missing)


def decode_sampled(container, fps, limit, start):
    """PTS 기준 ~fps 장/초로 솎아 낸다. fps 가 0 이면 전 프레임."""
    stream = container.streams.video[0]
    rate = float(stream.average_rate) if stream.average_rate else (fps or 1.0)
    step = (1.0 / fps) if fps else 0.0
    next_keep = 0.0
    out = []
    for i, vframe in enumerate(container.decode(video=0)):
        t = vframe.time
        if t is None:
            t = i / rate                     # PTS 가 없는 컨테이너 대비
        if fps and t + 1e-9 < next_keep:
            continue
        ts = (start + timedelta(seconds=t)).strftime(TS_FMT)
        out.append((len(out), ts, "", vframe.to_image()))
        if fps:
            next_keep += step
        if limit and len(out) >= limit:
            break
    return out, []


# ── 실행 ────────────────────────────────────────────────────────────────────
def _step_params(steps):
    """[[기능명, {파라미터}], ...] → {기능명: {파라미터}}. 꺼진 기능은 애초에 안 온다."""
    enabled = {}
    for s in steps or []:
        if isinstance(s, (list, tuple)) and s:
            enabled[s[0]] = (s[1] if len(s) > 1 and isinstance(s[1], dict) else {})
        elif isinstance(s, str):
            enabled[s] = {}
    return enabled


def run(params):
    import av                                  # 무거운 임포트는 실행 시점으로 미룬다

    out_dir = params["out_dir"]
    steps = params.get("steps") or []
    dry_run = bool(params.get("dry_run"))
    sample_size = int(params.get("sample_size", 10))
    run_id = str(params.get("run_id", "run"))
    datasets_root = params.get("datasets_root", "/datasets")

    os.makedirs(os.path.join(out_dir, "assets"), exist_ok=True)
    os.makedirs(os.path.join(out_dir, "samples"), exist_ok=True)

    enabled = _step_params(steps)
    fps = float((enabled.get(STEP_SAMPLE) or {}).get("fps", 1) or 0)
    scenes_cap = int((enabled.get(STEP_LIMIT) or {}).get("scenes", 0) or 0)

    limit = scenes_cap
    if dry_run:
        limit = min(sample_size, scenes_cap) if scenes_cap else sample_size

    video = find_video(datasets_root, params.get("sources") or [])
    if not video:
        raise RuntimeError("소스에서 영상 파일(.mp4 등)을 찾지 못했습니다")
    log("phase", name="collect", video=video, dry_run=dry_run)

    index_path = find_index(video, datasets_root, params.get("sources") or [])
    index = read_index(index_path) if index_path else {}

    container = av.open(video)
    try:
        if index:
            log("log", level="info",
                message=f"{INDEX_NAME} 를 정본으로 사용합니다 ({len(index)}행) — fps 설정은 무시됩니다")
            frames, missing = decode_indexed(container, index, limit)
            n_in = min(limit, len(index)) if limit else len(index)
        else:
            start, relative = resolve_start(container)
            if relative:
                log("log", level="warn",
                    message=f"{INDEX_NAME} 도 영상 creation_time 도 없어 T0 기준 상대시각을 씁니다 "
                            "— 조인 단계에서 AIS 와 시각이 맞지 않을 수 있습니다")
            frames, missing = decode_sampled(container, fps, limit, start)
            n_in = len(frames)
    finally:
        container.close()

    drops = [{"frame_idx": i, "reason": "not_in_video",
              "message": f"{INDEX_NAME} 에는 있으나 영상에서 디코딩되지 않았습니다"}
             for i in missing]

    funnel = [{"stage": "수집", "in": n_in, "out": len(frames),
               "dropped": {"not_in_video": len(missing)} if missing else {},
               "kind": "source"}]

    bad_ts = 0
    n_sample = 0
    with open(os.path.join(out_dir, "assets.jsonl"), "w", encoding="utf-8") as f:
        for frame_idx, ts, scene_id, image in frames:
            asset_id = f"f{frame_idx:06d}"
            rel = f"assets/{asset_id}.jpg"
            image.save(os.path.join(out_dir, rel), quality=90)
            if n_sample < SAMPLE_LIMIT:
                th = image.copy()
                th.thumbnail((THUMB_EDGE, THUMB_EDGE))
                th.save(os.path.join(out_dir, "samples", f"{asset_id}.jpg"), quality=80)
                n_sample += 1
            try:
                parse_dt(ts)
            except ValueError:
                bad_ts += 1
            w, h = image.size
            row = {"asset_id": asset_id, "src": video, "path": rel, "w": w, "h": h,
                   "frame_idx": frame_idx, "timestamp": ts}
            if scene_id:
                row["scene_id"] = scene_id
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    with open(os.path.join(out_dir, "drops.jsonl"), "w", encoding="utf-8") as f:
        for d in drops:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")

    summary = {
        "node": "sds_video", "run_id": run_id, "node_index": params.get("node_index"),
        "dry_run": dry_run, "in": n_in, "out": len(frames),
        "dropped_total": len(drops), "sample_count": n_sample,
        "source_video": video, "frames_index": index_path or "",
        "warn_bad_timestamp": bad_ts,
        "funnel": funnel,
    }
    with open(os.path.join(out_dir, "funnel.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    # 어떤 설정으로 돌렸는지를 산출물 옆에 남긴다. 이게 없으면 두 결과를 나란히 놔도
    # 무엇이 달라서 그런지 알 수 없어 비교가 의미를 잃는다.
    with open(os.path.join(out_dir, "config.json"), "w", encoding="utf-8") as f:
        json.dump({"steps": steps, "sources": params.get("sources"),
                   "dry_run": dry_run, "sample_size": sample_size,
                   "created_at": time.strftime(TS_FMT)},
                  f, ensure_ascii=False, indent=2)

    log("metric", name="sds_video/in", value=n_in)
    log("metric", name="sds_video/out", value=len(frames))
    log("metric", name="sds_video/dropped", value=len(drops))
    if bad_ts:
        log("log", level="warn",
            message=f"시각을 읽을 수 없는 프레임 {bad_ts}건 — 조인에서 짝을 찾지 못합니다")
    print(f"[dp_sds_video] {n_in} → {len(frames)} (제외 {len(drops)}) → {out_dir}", flush=True)
    return summary


def main(argv=None):
    ap = argparse.ArgumentParser(description="데이터 파이프라인 항해 영상 수집 노드")
    ap.add_argument("--params_path", required=True, help="노드 설정 JSON 경로")
    args = ap.parse_args(argv)

    with open(args.params_path, encoding="utf-8") as f:
        params = json.load(f)
    if not params.get("out_dir"):
        params["out_dir"] = os.path.dirname(os.path.abspath(args.params_path))

    try:
        run(params)
    except Exception as e:  # noqa: BLE001 - 사유를 남기고 비-0 으로 죽는다
        log("error", code="E_SDS_VIDEO_FAILED", message=f"{type(e).__name__}: {e}", fatal=True)
        raise


if __name__ == "__main__":
    main()
