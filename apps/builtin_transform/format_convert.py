#!/usr/bin/env python3
"""빌트인 전처리 — 데이터 포맷 변환 (CSV / TXT / Parquet → JSON / JSONL).

fb_preprocessing 빌트인(TYPE_BUILT_IN.FORMAT_CONVERT) 잡이 이미지 안에서
``python3 -u /built_in/format_convert.py <params> --input_data=/dataset/<path>`` 로 실행.

- 입력: 데이터셋 파일(또는 디렉터리) — CSV/TXT/Parquet.
- 출력: **원본 옆 파일**(sidecar) ``<dir>/<result_file_name>.<json|jsonl>``.
- 컬럼→학습 필드 매핑은 **규약 자동**(컬럼명 휴리스틱) + 사용자는 target_format 만 선택.

파라미터(스케줄러가 `--key value` 공백 형식으로 전달; --input_data 는 `=` 형식):
  --input_data       입력 파일/디렉터리 경로 (필수)
  --target_format    text | instruction | chat   (기본 instruction)
  --output_format    json | jsonl                (기본 jsonl)
  --result_file_name 출력 파일 베이스명           (기본 converted)
"""
import argparse
import json
import os
import sys

# 컬럼명 휴리스틱(소문자 비교). instruction/chat 의 입력·출력 필드를 데이터셋 컬럼에서 자동 매핑.
_PROMPT_KEYS = ("instruction", "prompt", "question", "query", "input_text", "instruction_text")
_INPUT_KEYS = ("input", "context", "passage")
_OUTPUT_KEYS = ("output", "response", "answer", "completion", "label", "target", "reply")
_TEXT_KEYS = ("text", "content", "sentence", "document", "body")
_SUPPORTED_EXTS = (".csv", ".txt", ".parquet")
_MAX_FIELD = 100000  # 단일 필드 길이 cap(이상치 방어)
# 텍스트 입력 인코딩 후보(순차 시도). 국내 공공데이터·Excel 내보내기 CSV 는 대부분
# CP949 라 UTF-8 고정이면 첫 바이트에서 UnicodeDecodeError 로 파일 전체가 스킵된다.
# CP949 는 EUC-KR 상위호환이라 둘 다 커버.
# ⚠️ UTF-8 을 먼저 두는 건 최선일 뿐 무해하지는 않다 — 현대 한글 11,172자 중 345자(3.1%)는
# CP949 2바이트가 그대로 valid UTF-8 이라('짜'=b'\xc2\xa5' → '¥'), 그 대역 글자만으로 이뤄진
# CP949 파일은 UTF-8 로 조용히 디코드돼 mojibake 가 된다. 폐쇄망이라 chardet 류 자동판별을
# 쓸 수 없으므로 이 잔여 위험은 감수하되, 어떤 인코딩으로 읽었는지 항상 로그에 남긴다.
_ENCODINGS = ("utf-8-sig", "cp949")
_ENCODING_LABEL = "UTF-8 / CP949(EUC-KR)"
# 0건 안내 로그 상한 — 컬럼명은 사용자 데이터라 개수·길이가 무제한이면 로그 폭주가 된다.
_MAX_LOG_COLUMNS = 30
_MAX_LOG_COLUMN_LEN = 60


def _pick(row, keys):
    """row(dict)에서 keys 중 첫 비어있지 않은 값(대소문자 무시). 없으면 None."""
    lower = {str(k).lower(): k for k in row.keys()}
    for k in keys:
        actual = lower.get(k)
        if actual is None:
            continue
        v = row.get(actual)
        if v is None:
            continue
        s = str(v).strip()
        # pandas/pyarrow null 센티넬(NaN/NaT/<NA>/None) 문자열화 값 제외.
        if s and s.lower() not in ("nan", "nat", "<na>", "none", "null"):
            return s[:_MAX_FIELD]
    return None


def _read_with_encoding(path, loader):
    """loader(encoding) 을 _ENCODINGS 순서로 시도. 전부 실패하면 지원 인코딩을 알리며 ValueError."""
    last_err = None
    for enc in _ENCODINGS:
        try:
            result = loader(enc)
        except UnicodeDecodeError as e:
            last_err = e
            continue
        print(f"[format_convert] {os.path.basename(path)}: encoding={enc}", flush=True)
        return result
    raise ValueError(f"문자 인코딩을 인식할 수 없습니다(지원: {_ENCODING_LABEL}). "
                     f"원본 오류: {last_err}")


def _read_rows(path):
    """파일 → row(dict) 리스트. CSV/Parquet 는 표 행, TXT 는 줄당 {text:...}."""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".csv":
        import pandas as pd
        df = _read_with_encoding(
            path,
            lambda enc: pd.read_csv(path, dtype=str, keep_default_na=False, encoding=enc))
        return df.to_dict(orient="records")
    if ext == ".parquet":
        import pandas as pd
        df = pd.read_parquet(path)  # 바이너리 포맷(문자열은 내부 UTF-8) — 인코딩 후보 불필요
        return df.astype(str).to_dict(orient="records")
    if ext == ".txt":
        def _load(enc):
            # 파일 객체를 직접 줄 반복(스트리밍). `f.read()` + `splitlines()` 는 ① 원문 전체와
            # 줄 리스트를 동시에 들고 있어 피크 메모리가 배로 늘고 ② splitlines() 가
            # \x0b·\x0c·\x1c~\x1e·\x85·U+2028/2029 에서도 줄을 쪼개 기존 레코드 경계를 바꾼다.
            # 디코드 실패는 반복 도중 나므로 with 안에서 리스트로 소진해야 폴백이 걸린다.
            with open(path, encoding=enc) as f:
                return [{"text": s} for s in (line.strip() for line in f) if s]
        return _read_with_encoding(path, _load)
    return []


def _to_record(row, target_format):
    """row → 학습 포맷 레코드. 매핑 불가(필수 필드 없음)면 None."""
    prompt = _pick(row, _PROMPT_KEYS)
    output = _pick(row, _OUTPUT_KEYS)
    extra_in = _pick(row, _INPUT_KEYS)
    text = _pick(row, _TEXT_KEYS)

    if target_format == "text":
        if text:
            return {"text": text}
        # instruction/response 컬럼만 있으면 Alpaca 텍스트로 합성
        if prompt and output:
            return {"text": f"### Instruction:\n{prompt}\n\n### Response:\n{output}"}
        if prompt:
            return {"text": prompt}
        return None

    if target_format == "chat":
        user = prompt or text
        if not user:
            return None
        if extra_in:
            user = f"{user}\n\n{extra_in}"
        # chat 샘플은 항상 user+assistant 2턴(무출력이면 빈 assistant) — user 단독은
        # 다운스트림에서 malformed(리뷰). instruction 의 output or "" 와 동일 정책.
        messages = [{"role": "user", "content": user},
                    {"role": "assistant", "content": output or ""}]
        return {"messages": messages}

    # instruction (기본)
    if prompt is None and text is not None:
        prompt = text  # text 컬럼만 있으면 instruction 으로
    if prompt is None:
        return None
    rec = {"instruction": prompt, "output": output or ""}
    if extra_in:
        rec["input"] = extra_in
    return rec


def _iter_input_files(input_data):
    if os.path.isdir(input_data):
        for r, _d, fs in os.walk(input_data):
            for fn in sorted(fs):
                if os.path.splitext(fn)[1].lower() in _SUPPORTED_EXTS:
                    yield os.path.join(r, fn)
    elif os.path.isfile(input_data):
        yield input_data


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input_data", required=True)
    ap.add_argument("--target_format", default="instruction",
                    choices=["text", "instruction", "chat"])
    ap.add_argument("--output_format", default="jsonl", choices=["json", "jsonl"])
    ap.add_argument("--result_file_name", default="converted")
    args, _unknown = ap.parse_known_args()

    files = list(_iter_input_files(args.input_data))
    if not files:
        print(f"[format_convert] no supported input files under {args.input_data!r} "
              f"(supported: {_SUPPORTED_EXTS})", flush=True)
        sys.exit(1)

    records = []
    skipped = 0
    seen_columns = []  # 0건일 때 "무슨 컬럼이 들어왔는지" 안내용(첫 읽힌 행 기준)
    seen_column_total = 0
    for fp in files:
        try:
            for row in _read_rows(fp):
                if not seen_columns:
                    keys = [str(k) for k in row.keys()]
                    seen_column_total = len(keys)
                    seen_columns = [k[:_MAX_LOG_COLUMN_LEN]
                                    for k in keys[:_MAX_LOG_COLUMNS]]
                rec = _to_record(row, args.target_format)
                if rec is not None:
                    records.append(rec)
                else:
                    skipped += 1
        except Exception as e:  # 파일 단위 실패는 스킵(전체 중단 방지)
            print(f"[format_convert] failed to read {fp}: {e}", flush=True)
            skipped += 1

    if not records:
        print(f"[format_convert] produced 0 records (skipped={skipped}).", flush=True)
        if seen_columns:
            more = (f" (총 {seen_column_total}개 중 앞 {len(seen_columns)}개만 표시)"
                    if seen_column_total > len(seen_columns) else "")
            print(f"[format_convert] 입력 컬럼{more}: {seen_columns}", flush=True)
            print("[format_convert] 변환하려면 다음 중 하나에 해당하는 컬럼이 필요합니다(대소문자 무시) — "
                  f"지시/질문: {list(_PROMPT_KEYS)} · 답변: {list(_OUTPUT_KEYS)} · "
                  f"단일 텍스트: {list(_TEXT_KEYS)}. "
                  "학습용 컬럼이 없는 일반 통계·수치 표는 변환 대상이 아닙니다.", flush=True)
        else:
            print(f"[format_convert] 읽을 수 있는 행이 없습니다"
                  f"(지원 인코딩: {_ENCODING_LABEL}).", flush=True)
        sys.exit(1)

    # 출력 = 원본 옆 파일(sidecar). service.py 가 dirname(dataset_data_path) 로 결과를
    # 찾으므로 항상 입력의 디렉터리에 쓴다(file/dir 모두 dirname — 일치). result_file_name 은
    # basename 으로 경로조작(`../`) 차단.
    in_real = os.path.realpath(args.input_data)
    out_dir = os.path.dirname(in_real)
    safe_name = os.path.basename(args.result_file_name) or "converted"
    out_path = os.path.join(out_dir, f"{safe_name}.{args.output_format}")
    with open(out_path, "w", encoding="utf-8") as f:
        if args.output_format == "jsonl":
            for rec in records:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        else:  # json (배열)
            json.dump(records, f, ensure_ascii=False, indent=2)

    print(f"[format_convert] wrote {len(records)} records (skipped={skipped}) → {out_path}",
          flush=True)


if __name__ == "__main__":
    main()
