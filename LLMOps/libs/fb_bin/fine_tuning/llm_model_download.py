import argparse
import shutil
import os
import sys
import torch

from huggingface_hub import login, snapshot_download
from requests.exceptions import HTTPError, ConnectionError, Timeout


def mode_directory(save_directory, dir_name="models--"):
    # 다운로드된 디렉토리 구조 변경
    for root, dirs, files in os.walk(save_directory):
        for dir_name in dirs:
            # "models--"로 시작하는 하위 디렉토리를 찾음
            if dir_name.startswith(dir_name):
                downloaded_model_path = os.path.join(root, dir_name)

                # 다운로드된 모든 파일을 save_directory로 이동
                for item in os.listdir(downloaded_model_path):
                    shutil.move(os.path.join(downloaded_model_path, item), save_directory)

                # 빈 디렉토리 제거
                shutil.rmtree(downloaded_model_path)
                break  # 해당 디렉토리만 찾으면 되므로 루프 종료

        # 첫 번째 루프 이후 break로 탈출
        break

def download_model(model_id: str, token: str, dst_model_path: str, latest_checkpoint_path : str):
    """
    Hugging Face에서 주어진 모델 ID로 모델을 다운로드하고 저장하는 함수.

    Parameters:
    model_id (str): 다운로드할 모델의 Hugging Face ID.
    token (str): Hugging Face API 토큰.
    dst_model_path (str): 모델이 저장될 디렉토리 경로. 기본값은 "./model".
    """
    
    try:
        from transformers import AutoTokenizer, AutoModelForCausalLM
        # Hugging Face 로그인 (토큰 기반)
        login(token=token, add_to_git_credential=False)

        # 저장할 디렉토리 생성
        os.makedirs(dst_model_path, exist_ok=True)

        # 토크나이저 및 모델 다운로드
        print(f"Downloading model '{model_id}'...")
        # tokenizer = AutoTokenizer.from_pretrained(model_id, use_auth_token=token)
        snapshot_download(repo_id=model_id, local_dir=dst_model_path, local_dir_use_symlinks=False)
        # 모델 및 토크나이저 저장
        # tokenizer.save_pretrained(tokenizer_dir)
        # mode_directory(dst_model_path) # depth 줄이기 
        print(f"Model '{model_id}' has been downloaded and saved to '{dst_model_path}'.")
        # latest checkpoint로 source model 옮기기
        shutil.copytree(dst_model_path, latest_checkpoint_path, dirs_exist_ok=True)
        print(f"Folder '{dst_model_path}' has been copied to '{latest_checkpoint_path}'.") 
    except HTTPError as e:
        # 허깅페이스 API 관련 오류 처리 (모델 ID가 잘못되었을 경우 포함)
        print(f"Error: Hugging Face model '{model_id}' not found or invalid token.")
        print(f"Details: {str(e).replace(token, '***') if token else e}")
        sys.exit(0)
    
    except (ConnectionError, Timeout) as e:
        # 네트워크 연결 문제
        print(f"Error: Network issue occurred while downloading the model '{model_id}'.")
        print(f"Details: {str(e).replace(token, '***') if token else e}")
        sys.exit(0)
    except OSError as e:
        # 파일 시스템 오류 (디렉토리 생성, 저장 문제 등)
        print(f"Error: Problem with saving the model to '{dst_model_path}'.")
        print(f"Details: {str(e).replace(token, '***') if token else e}")
        sys.exit(0)
    except Exception as e:
        # 기타 예상치 못한 예외 상황 처리
        print(f"An unexpected error occurred: {e}")
        sys.exit(0)
    
    
def _ensure_safetensors(model_dir):
    """torch<2.6 + transformers>=4.52 는 CVE-2025-32434 가드로 .bin(torch.load) 로딩을 차단.
    safetensors 가 없고 .bin 만 있는 repo 는 변환 — torch.load 직접 호출은 torch 2.5.x 에서 허용
    (가드는 transformers from_pretrained 내부에만 있음). 이후 from_pretrained 가 safetensors 사용."""
    import glob
    from safetensors.torch import save_file
    if glob.glob(os.path.join(model_dir, "*.safetensors")):
        return  # 이미 safetensors 보유 → 변환 불필요
    bins = sorted(glob.glob(os.path.join(model_dir, "pytorch_model*.bin")))
    if not bins:
        return  # .bin 도 없음(이미 다른 포맷) → from_pretrained 에 위임
    sd = {}
    for b in bins:
        sd.update(torch.load(b, map_location="cpu", weights_only=True))
    # 공유메모리(타이) 텐서는 save_file 가 거부 → clone 으로 분리(로드 시 tie 재구성).
    sd = {k: v.clone().contiguous() for k, v in sd.items() if hasattr(v, "clone")}
    save_file(sd, os.path.join(model_dir, "model.safetensors"))
    for b in bins:
        os.remove(b)
    idx = os.path.join(model_dir, "pytorch_model.bin.index.json")
    if os.path.exists(idx):
        os.remove(idx)
    print(f".bin -> safetensors converted in '{model_dir}'")


def compose_vlm(model_id: str, token: str, dst_model_path: str, latest_checkpoint_path: str,
                dtype: str = "bfloat16"):
    """비전 인코더 + LLM 두 HF 모델을 받아 학습 가능한 LLaVA(VLM)로 조립.

    model_id : "{vision_repo_id},{llm_repo_id}" (콤마 결합, 정확히 2개).
    - 둘 다 snapshot_download → LlavaConfig(vision_config, text_config) 로 LLaVA 구성.
      multi_modal_projector 는 랜덤 초기화(엔진 Stage1 이 정렬) — 직접 합성 불필요.
    - vision 가중치 → vision_tower / LLM 가중치 → language_model 적재.
    - <image> 토큰 / image_token_index / image_seq_length / select_strategy 배선
      (없으면 forward 에서 image-token-count mismatch 로 학습 크래시).
    - dst_model_path 저장 후 latest_checkpoint_path 로 복사 — FT 파드가 /model=latest_checkpoint
      로 마운트해 읽음(download_model 선례와 동일). 조립 결과는 기존 VLM 2-stage 엔진
      (llm_model_vlm_fine_tuning.py)이 무수정으로 로드.
    ⚠️ CPU-only(GPU 불필요). 풀 GPU e2e 는 A6000(3.4)에서 확인 예정.
    """
    try:
        from contextlib import nullcontext

        from transformers import (
            AutoConfig, AutoImageProcessor, AutoModelForCausalLM, AutoTokenizer,
            LlavaConfig, LlavaForConditionalGeneration, LlavaProcessor,
        )
        from transformers.models.llava.modeling_llava import LlavaMultiModalProjector

        parts = [p.strip() for p in (model_id or "").split(",")]
        if len(parts) != 2 or not all(parts):
            print(f"Error: compose_vlm requires model_id='{{vision}},{{llm}}' (정확히 2개), got '{model_id}'")
            sys.exit(1)
        vision_repo_id, llm_repo_id = parts

        torch_dtype = {"float32": torch.float32, "bfloat16": torch.bfloat16,
                       "float16": torch.float16}.get(dtype, torch.bfloat16)

        # 빈 토큰(offline/nexus 모드)에서는 login 생략 — login("") 은 huggingface_hub 예외.
        if token:
            login(token=token, add_to_git_credential=False)
        hf_token = token or None

        # 재실행/재사용 컨테이너에서 stale snapshot 혼입 방지 — work_dir 초기화.
        work_dir = "/tmp/compose_vlm"
        shutil.rmtree(work_dir, ignore_errors=True)
        vision_dir = os.path.join(work_dir, "vision")
        llm_dir = os.path.join(work_dir, "llm")
        print(f"Downloading vision encoder '{vision_repo_id}'...")
        snapshot_download(repo_id=vision_repo_id, local_dir=vision_dir,
                          local_dir_use_symlinks=False, token=hf_token)
        _ensure_safetensors(vision_dir)
        print(f"Downloading LLM '{llm_repo_id}'...")
        snapshot_download(repo_id=llm_repo_id, local_dir=llm_dir,
                          local_dir_use_symlinks=False, token=hf_token)
        _ensure_safetensors(llm_dir)

        # ── 비전 서브config 추출 (full CLIP/SigLIP 이면 .vision_config) ──
        # 보안: trust_remote_code=False — 표준 CLIP/SigLIP/Qwen/Llama 만 지원(생성 UI 제약과 일치,
        # 악성 HF repo 임의코드 실행 차단). 커스텀 아키텍처는 admin 의 의도적 결정 사항.
        raw_vision_cfg = AutoConfig.from_pretrained(vision_dir, trust_remote_code=False)
        vision_cfg = getattr(raw_vision_cfg, "vision_config", raw_vision_cfg)
        is_siglip = "siglip" in (getattr(vision_cfg, "model_type", "") or "").lower()
        # SigLIP=CLS 토큰 없음 → 전체 패치 유지("full"). CLIP=CLS 있음 → "default"(마지막 드롭).
        select_strategy = "full" if is_siglip else "default"
        num_extra = 0 if is_siglip else 1
        image_size = getattr(vision_cfg, "image_size", None)
        patch_size = getattr(vision_cfg, "patch_size", None)
        if isinstance(image_size, (tuple, list)):
            image_size = image_size[0]
        if not image_size or not patch_size:
            print("Error: vision config must expose image_size and patch_size")
            sys.exit(1)
        # 실제 선택 피처 길이 = 패치 수(CLIP default 는 CLS 드롭, SigLIP full 도 패치 수).
        # 추가 토큰(CLS 등)은 processor 의 num_additional_image_tokens 가 처리.
        image_seq_length = (int(image_size) // int(patch_size)) ** 2

        # ── 토크나이저 + <image> 토큰 ──
        tokenizer = AutoTokenizer.from_pretrained(llm_dir, trust_remote_code=False, use_fast=True)
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token
        if tokenizer.convert_tokens_to_ids("<image>") == tokenizer.unk_token_id:
            tokenizer.add_special_tokens({"additional_special_tokens": ["<image>"]})
        image_token_id = tokenizer.convert_tokens_to_ids("<image>")
        image_processor = AutoImageProcessor.from_pretrained(vision_dir, trust_remote_code=False)

        # ── 비전 타워(비전 전용 클래스) + LLM 로드 ──
        # CLIPVisionModel/SiglipVisionModel.from_pretrained 는 full CLIP/SigLIP repo 에서도
        # 비전부만 적재(텍스트부 무시) — full*Model 로딩 시 키 mismatch 회피.
        if is_siglip:
            from transformers import SiglipVisionModel as _VisionTower
        else:
            from transformers import CLIPVisionModel as _VisionTower
        vision_tower = _VisionTower.from_pretrained(
            vision_dir, torch_dtype=torch_dtype, low_cpu_mem_usage=True, trust_remote_code=False)
        lm = AutoModelForCausalLM.from_pretrained(
            llm_dir, torch_dtype=torch_dtype, low_cpu_mem_usage=True, trust_remote_code=False)
        lm.resize_token_embeddings(len(tokenizer))
        lm.config.vocab_size = len(tokenizer)
        lm.config.pad_token_id = tokenizer.pad_token_id

        # ── LLaVA config + 빈 모델(meta) → 서브모듈 결합 ──
        config = LlavaConfig(
            vision_config=vision_cfg.to_dict(),
            text_config=lm.config.to_dict(),
            image_token_index=image_token_id,
            vision_feature_select_strategy=select_strategy,
            vision_feature_layer=-2,
            image_seq_length=image_seq_length,
        )
        config.image_token_id = image_token_id   # 신버전 modeling_llava 내부 alias
        config.pad_token_id = tokenizer.pad_token_id

        # init_empty_weights: 빈 LLaVA 를 meta 에 만들어(랜덤 8B 중복할당 회피) 실제 서브모듈로 교체.
        # vision_tower/language_model/multi_modal_projector/lm_head 4개가 전 파라미터 → meta 잔여 없음.
        try:
            from accelerate import init_empty_weights
            init_ctx = init_empty_weights()
        except Exception:
            init_ctx = nullcontext()
        with init_ctx:
            model = LlavaForConditionalGeneration(config)

        # transformers 4.52.x = 서브모듈이 model.model.* 아래. 엔진 get_submodules 가 별칭으로 흡수.
        target = model.model if hasattr(model, "model") else model
        target.vision_tower = vision_tower
        # 디코더-only LLM(Llama/Qwen)은 get_decoder()=백본. 미보유 아키텍처는 .model 폴백.
        target.language_model = lm.get_decoder() if hasattr(lm, "get_decoder") else getattr(lm, "model", lm)
        target.multi_modal_projector = LlavaMultiModalProjector(config).to(dtype=torch_dtype)
        if hasattr(model, "lm_head"):
            model.lm_head = lm.get_output_embeddings()

        # ── processor (생성자 kwargs 로 전달해야 processor_config.json 에 영속) ──
        try:
            processor = LlavaProcessor(
                image_processor=image_processor, tokenizer=tokenizer,
                patch_size=int(patch_size), vision_feature_select_strategy=select_strategy,
                image_token="<image>", num_additional_image_tokens=num_extra)
        except TypeError:
            # 구버전 시그니처 폴백 — 속성으로 세팅.
            processor = LlavaProcessor(image_processor=image_processor, tokenizer=tokenizer)
            processor.patch_size = int(patch_size)
            processor.vision_feature_select_strategy = select_strategy
            processor.image_token = "<image>"

        # 임베딩 타이 모델은 lm_head 재타이(도너 가중치와 일관). 이후 meta 잔여 점검 — 있으면
        # save_pretrained 가 garbage 를 쓰므로 명시 실패(빈/손상 모델 DONE 마킹 방지).
        if getattr(lm.config, "tie_word_embeddings", False):
            model.tie_weights()
        meta_params = [n for n, p in model.named_parameters() if p.device.type == "meta"]
        if meta_params:
            print(f"Error: composed model has unmaterialized meta params: {meta_params[:5]}")
            sys.exit(1)

        os.makedirs(dst_model_path, exist_ok=True)
        model.save_pretrained(dst_model_path, safe_serialization=True)
        processor.save_pretrained(dst_model_path)
        print(f"Composed VLM saved to '{dst_model_path}' "
              f"(vision={vision_repo_id}, llm={llm_repo_id}, img_seq={image_seq_length}).")

        shutil.copytree(dst_model_path, latest_checkpoint_path, dirs_exist_ok=True)
        print(f"Folder '{dst_model_path}' has been copied to '{latest_checkpoint_path}'.")
    # SystemExit(=sys.exit) 는 BaseException 이라 아래 except Exception 이 삼키지 않음 → exit code 보존.
    except HTTPError as e:
        print(f"Error: Hugging Face access failed for '{model_id}'. Details: {e}")
        sys.exit(1)
    except (ConnectionError, Timeout) as e:
        print(f"Error: Network issue occurred while composing VLM '{model_id}'. Details: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"An unexpected error occurred composing VLM: {e}")
        sys.exit(1)


def copy_commit_model(  dst_model_path: str,  latest_checkpoint_path : str, \
    src_model_path: str = "", src_model_log_path : str = "", dst_log_dir : str ="", is_commit: int = 0):
    try:
        if is_commit: # 새로운 모델 생성 시 다른 모델의 commit을 가져올 경우
            shutil.copytree(src_model_path, dst_model_path, dirs_exist_ok=True)
            print(f"Folder '{src_model_path}' has been copied to '{dst_model_path}'.") 
            shutil.copytree(src_model_path, latest_checkpoint_path, dirs_exist_ok=True)
            print(f"Folder '{src_model_path}' has been copied to '{latest_checkpoint_path}'.") 
        else: # 파인튜닝 후 commit 시 
            # 복사 목록
            # 1. latest checkpoint 복사 
            # 2. training log 복사 
            shutil.copytree(latest_checkpoint_path, dst_model_path, dirs_exist_ok=True)
            print(f"Folder '{latest_checkpoint_path}' has been copied to '{dst_model_path}'.") 
            # src_model_log_path = f"/models/{model_name}/logs"
            shutil.copytree(src_model_log_path, dst_log_dir, dirs_exist_ok=True)
            print(f"Folder '{src_model_log_path}' has been copied to '{dst_log_dir}'.")
    except shutil.Error as e:
        print(f"Error occurred while copying folder: {e}")
        sys.exit(0)


def stop(tmp_model_path : str, latest_checkpoint_path : str):
    try:
        shutil.rmtree(latest_checkpoint_path)
        print(f"Folder '{latest_checkpoint_path}'rm success.") 
        shutil.copytree(tmp_model_path, latest_checkpoint_path, dirs_exist_ok=True)
        print(f"Folder '{tmp_model_path}' has been copied to '{latest_checkpoint_path}'.")
    except shutil.Error as e:
        print(f"Error occurred while copying folder: {e}")
        sys.exit(0)

def commit_load(latest_checkpoint_path : str, load_commit_model_path : str):
    try:
        shutil.rmtree(latest_checkpoint_path)
        print(f"Folder '{latest_checkpoint_path}'rm success.")
        shutil.copytree(load_commit_model_path, latest_checkpoint_path, dirs_exist_ok=True)
        print(f"Folder '{load_commit_model_path}' has been copied to '{latest_checkpoint_path}'.")
    except shutil.Error as e:
        print(f"Error occurred while copying folder: {e}")
        sys.exit(0)


def promote_checkpoint(src_model_path: str, best_adapter_path: str, target_adapter_path: str,
                       dst_model_path: str, dst_log_dir: str = "", src_model_log_path: str = "",
                       latest_checkpoint_path: str = ""):
    """체크포인트 promote (Phase 2-C C안) — 커밋 merged 모델(=base+best_delta)을 임의 step 으로 재타겟.

    base 스냅샷 없이 LoRA 델타 산술로 재현(스파이크 검증, peft 0.18.1):
      add_weighted_adapter(["best","target"], [-1.0, +1.0], combination_type="cat") → merge_and_unload()
      = (base + best_delta) + (target_delta - best_delta) = base + target_delta.
    ⚠️ combination_type 은 반드시 "cat" (rank 2r, 정확). linear/svd 는 rank 절단 lossy(스파이크 ~0.2~0.4 오차).
    VLM: vision LoRA 는 frozen(δ=0)이라 -best+target 에서 상쇄, projector 는 커밋 모델에 이미 포함 → LM 만 재타겟.
    어댑터=safetensors 라 torch.load(.bin) 신뢰 이슈 없음. trust_remote_code=False(엔진 정합)."""
    import traceback as _tb
    try:
        import torch
        import transformers
        from peft import PeftModel
        from transformers import AutoProcessor

        # 1. 커밋 merged 모델 + 프로세서 로드 (엔진과 동일 클래스 fallback·trust_remote_code=False)
        processor = None
        try:
            processor = AutoProcessor.from_pretrained(src_model_path, trust_remote_code=False)
        except Exception as e:
            print(f"[promote] processor load skipped: {e}")
        model = None
        last_err = None
        for cls_name in ("AutoModelForImageTextToText", "AutoModelForVision2Seq",
                         "LlavaForConditionalGeneration", "AutoModelForCausalLM"):
            cls = getattr(transformers, cls_name, None)
            if cls is None:
                continue
            try:
                # bfloat16 명시 — float32 fallback 시 CPU 메모리 2배(merge 피크 OOM 위험, 리뷰 MEDIUM).
                # 학습이 bf16 이라 커밋 모델도 bf16, 정밀도 동일. cat merge 의 미세 오차는 추론 허용 범위.
                model = cls.from_pretrained(src_model_path, trust_remote_code=False, torch_dtype=torch.bfloat16)
                print(f"[promote] loaded committed model via {cls_name}")
                break
            except Exception as e:
                last_err = e
        if model is None:
            raise RuntimeError(f"failed to load committed model at {src_model_path}: {last_err}")

        # 2. best·target 어댑터 attach (cat 결합엔 둘 다 로드돼 있어야 함)
        pm = PeftModel.from_pretrained(model, best_adapter_path, adapter_name="best")
        pm.load_adapter(target_adapter_path, adapter_name="target")

        # 3. cat[-best, +target] → merge (cat 필수)
        pm.add_weighted_adapter(["best", "target"], [-1.0, 1.0], "promote", combination_type="cat")
        pm.set_adapter("promote")
        merged = pm.merge_and_unload()

        # 4. 새 커밋 위치에 저장 (+프로세서)
        os.makedirs(dst_model_path, exist_ok=True)
        merged.save_pretrained(dst_model_path, safe_serialization=True)
        if processor is not None:
            processor.save_pretrained(dst_model_path)
        print(f"[promote] saved promoted model → {dst_model_path}")

        # 5. (옵션) 학습 로그 복사 — 커밋 상세 그래프(result_log) 재사용
        if src_model_log_path and dst_log_dir:
            try:
                shutil.copytree(src_model_log_path, dst_log_dir, dirs_exist_ok=True)
                print(f"[promote] copied logs '{src_model_log_path}' → '{dst_log_dir}'.")
            except Exception as e:
                print(f"[promote] log copy skipped: {e}")
        # 6. (옵션) 즉시 서빙 활성화 (latest_checkpoint 로 복사)
        if latest_checkpoint_path:
            shutil.copytree(dst_model_path, latest_checkpoint_path, dirs_exist_ok=True)
            print(f"[promote] copied '{dst_model_path}' → '{latest_checkpoint_path}' (serving).")
    except Exception as e:
        _tb.print_exc()
        print(f"[promote] FAILED: {e}")
        sys.exit(1)

if __name__ == "__main__":
    import argparse
    import sys

    # argparse를 사용하여 CLI 인자를 처리
    parser = argparse.ArgumentParser(description="Manage Hugging Face models and directory operations.")
    
    subparsers = parser.add_subparsers(dest="command", required=True, help="Choose an operation: download_model, copy_commit_model, stop_fine_tuning, load_commit_model.")
    
    # download_model 서브커맨드
    download_parser = subparsers.add_parser("download_model", help="Download a Hugging Face model.")
    download_parser.add_argument("--model_id", type=str, help="The model ID from Hugging Face (e.g., 'bert-base-uncased').")
    download_parser.add_argument("--token", type=str, help="Your Hugging Face API token.")
    download_parser.add_argument("--dst_model_path", type=str, help="The directory where the model will be saved (default: './model').")
    download_parser.add_argument("--latest_checkpoint_path", type=str, help="The directory for the latest model checkpoint.")

    # compose_vlm 서브커맨드 (멀티모달: 비전+LLM → LLaVA 조립)
    compose_parser = subparsers.add_parser("compose_vlm", help="Compose a LLaVA VLM from a vision encoder + LLM.")
    compose_parser.add_argument("--model_id", type=str, help="'{vision_repo_id},{llm_repo_id}' (콤마 결합).")
    compose_parser.add_argument("--token", type=str, default="", help="Your Hugging Face API token (빈 값=offline).")
    compose_parser.add_argument("--dst_model_path", type=str, help="The directory where the composed VLM will be saved.")
    compose_parser.add_argument("--latest_checkpoint_path", type=str, help="The directory for the latest model checkpoint.")
    compose_parser.add_argument("--dtype", type=str, default="bfloat16", choices=["float32", "bfloat16", "float16"], help="Assembly dtype.")

    # copy_commit_model 서브커맨드
    commit_parser = subparsers.add_parser("copy_commit_model", help="Copy or commit model and related files.")
    commit_parser.add_argument("--dst_model_path", type=str, help="The target directory for the model.")
    commit_parser.add_argument("--dst_log_dir", type=str, help="The target directory for logs.")
    commit_parser.add_argument("--latest_checkpoint_path", type=str, help="The path to the latest model checkpoint.")
    commit_parser.add_argument("--src_model_path", type=str, default="", help="Source model directory (if copying from an existing model).")
    commit_parser.add_argument("--src_model_log_path", type=str, default="", help="Source log directory (if copying logs from an existing model).")
    commit_parser.add_argument("--is_commit", type=int, default=0, choices=[0, 1], help="Whether this is a commit operation (1 for yes, 0 for no).")
    
    # stop_fine_tuning 서브커맨드
    stop_parser = subparsers.add_parser("stop_fine_tuning", help="Stop fine-tuning.")
    stop_parser.add_argument("--latest_checkpoint_path", type=str, help="The path to the latest model checkpoint.")
    stop_parser.add_argument("--tmp_model_path", type=str, help="The target directory for logs.")
    
    # load_commit_model 서브커맨드
    load_parser = subparsers.add_parser("load_commit_model", help="Load committed model.")
    load_parser.add_argument("--latest_checkpoint_path", type=str, help="The path to the latest model checkpoint.")
    load_parser.add_argument("--load_commit_model_path", type=str, help="The path to the committed model.")

    # promote_checkpoint 서브커맨드 (Phase 2-C: 커밋의 step 체크포인트를 새 버전으로 promote)
    promote_parser = subparsers.add_parser("promote_checkpoint", help="Promote a commit's step checkpoint to a new merged model via LoRA delta arithmetic (cat).")
    promote_parser.add_argument("--src_model_path", type=str, help="Committed merged model dir (=base+best_delta).")
    promote_parser.add_argument("--best_adapter_path", type=str, help="The commit's best adapter dir (checkpoint-{best}).")
    promote_parser.add_argument("--target_adapter_path", type=str, help="The target step adapter dir (checkpoint-{step}).")
    promote_parser.add_argument("--dst_model_path", type=str, help="The new commit's model output dir.")
    promote_parser.add_argument("--dst_log_dir", type=str, default="", help="Optional log dir for the new commit.")
    promote_parser.add_argument("--src_model_log_path", type=str, default="", help="Optional source log dir to copy.")
    promote_parser.add_argument("--latest_checkpoint_path", type=str, default="", help="Optional: also copy to latest_checkpoint (serve).")

    # 인자 파싱
    args = parser.parse_args()

    if args.command == "download_model":
        # download_model 함수 호출
        download_model(
            model_id=args.model_id,
            token=args.token,
            dst_model_path=args.dst_model_path,
            latest_checkpoint_path=args.latest_checkpoint_path
        )
    elif args.command == "compose_vlm":
        # compose_vlm 함수 호출
        compose_vlm(
            model_id=args.model_id,
            token=args.token,
            dst_model_path=args.dst_model_path,
            latest_checkpoint_path=args.latest_checkpoint_path,
            dtype=args.dtype,
        )
    elif args.command == "copy_commit_model":
        # copy_commit_model 함수 호출
        copy_commit_model(
            dst_model_path=args.dst_model_path,
            dst_log_dir=args.dst_log_dir,
            latest_checkpoint_path=args.latest_checkpoint_path,
            src_model_path=args.src_model_path,
            src_model_log_path=args.src_model_log_path,
            is_commit=args.is_commit
        )
    elif args.command == "stop_fine_tuning":
        # stop_fine_tuning 함수 호출
        stop(
            latest_checkpoint_path=args.latest_checkpoint_path,
            tmp_model_path=args.tmp_model_path
        )
    elif args.command == "load_commit_model":
        # load_commit_model 함수 호출
        commit_load(
            latest_checkpoint_path=args.latest_checkpoint_path,
            load_commit_model_path=args.load_commit_model_path,
        )
    elif args.command == "promote_checkpoint":
        # promote_checkpoint 함수 호출 (Phase 2-C)
        promote_checkpoint(
            src_model_path=args.src_model_path,
            best_adapter_path=args.best_adapter_path,
            target_adapter_path=args.target_adapter_path,
            dst_model_path=args.dst_model_path,
            dst_log_dir=args.dst_log_dir,
            src_model_log_path=args.src_model_log_path,
            latest_checkpoint_path=args.latest_checkpoint_path,
        )
    else:
        print("Invalid command. Use 'download_model', 'copy_commit_model', 'stop_fine_tuning', or 'load_commit_model'.")
        sys.exit(1)