"""
model_manager.py — 에바(Eva) VLM 모델 로드·추론·체크포인트 관리자

환경 변수:
    EVA_LLM_MODEL_PATH          LLM 모델 디렉토리 (필수)
    EVA_CHECKPOINT_PATH         초기 로드할 체크포인트 디렉토리 (필수)
    EVA_VISION_MODEL_NAME       비전 모델 이름/경로 (기본: openai/clip-vit-large-patch14-336)
    EVA_DEVICE                  추론 디바이스 (기본: cuda:0)
    EVA_VLM_ROOT                VLM 소스 루트 (기본: /app/vlm)
    EVA_CHECKPOINTS_ROOT        체크포인트 탐색 루트 (기본: /models/checkpoints)
"""
from __future__ import annotations

import gc
import io
import os
import base64
import sys
import time
import traceback
from datetime import datetime, timezone
from typing import List, Optional

import torch
from PIL import Image

from schemas import AISRow, CheckpointInfo


# ── 프롬프트 매핑 ──────────────────────────────────────────────────────────────

PROMPT_MAP: dict[str, str] = {
    "영문 해상상황묘사":
        "Based on the camera image and AIS data provided, describe the current maritime situation in detail.",
    "한글 해상상황묘사":
        "제공된 카메라 이미지와 AIS 데이터를 기반으로 현재 해상 상황을 상세히 묘사하시오.",
    "영문 항해조력메시지":
        "Based on the camera image and AIS data provided, provide navigational advice "
        "for the own vessel in accordance with COLREG rules.",
    "한글 항해조력메시지":
        "제공된 카메라 이미지와 AIS 데이터를 기반으로 COLREG 규칙에 따른 "
        "자선의 항해 조력 메시지를 제공하시오.",
    "간결 항해조력메시지":
        "제공된 카메라 이미지와 AIS 데이터를 기반으로 간결한 항해 조력 메시지를 제공하시오. "
        "속도 조치, 방향 조치, 적용 근거(COLREG 조항)를 포함하시오.",
}


# ── AIS 텍스트 포맷터 ─────────────────────────────────────────────────────────

def format_ais_text(ais_rows: List[AISRow], lang: str = "en") -> str:
    if not ais_rows:
        return ""

    if lang == "en":
        lines = ["[Vessel AIS Information]"]
        for row in ais_rows:
            spd   = f"{row.knot:.1f}kt"
            hdg   = f"{row.heading:.1f}°"
            lat   = f"{row.latitude:.6f}"
            lon   = f"{row.longitude:.6f}"
            lw    = f"{row.length}m x {row.width}m"
            draft = f"{row.draft}m"
            if row.my_ship == 1:
                lines.append(
                    f"- Own vessel (ID:{row.ship_id}) | Lat:{lat} Lon:{lon} | "
                    f"Speed:{spd} Heading:{hdg} | Size:{lw} Draft:{draft}"
                )
            else:
                bbox_str = ""
                if row.bbox_x is not None:
                    bbox_str = (
                        f" | BoundingBox:[x={row.bbox_x:.0f} y={row.bbox_y:.0f} "
                        f"w={row.bbox_width:.0f} h={row.bbox_height:.0f}]"
                    )
                lines.append(
                    f"- Nearby vessel (ID:{row.ship_id}) | Lat:{lat} Lon:{lon} | "
                    f"Speed:{spd} Heading:{hdg} | Size:{lw} Draft:{draft}{bbox_str}"
                )
    else:
        lines = ["[선박 AIS 정보]"]
        for row in ais_rows:
            spd   = f"{row.knot:.1f}kt"
            hdg   = f"{row.heading:.1f}°"
            lat   = f"{row.latitude:.6f}"
            lon   = f"{row.longitude:.6f}"
            lw    = f"{row.length}m × {row.width}m"
            draft = f"{row.draft}m"
            if row.my_ship == 1:
                lines.append(
                    f"- 자선 (ID:{row.ship_id}) | 위도:{lat} 경도:{lon} | "
                    f"속도:{spd} 방향:{hdg} | 선체:{lw} 흘수:{draft}"
                )
            else:
                bbox_str = ""
                if row.bbox_x is not None:
                    bbox_str = (
                        f" | 바운딩박스:[x={row.bbox_x:.0f} y={row.bbox_y:.0f} "
                        f"w={row.bbox_width:.0f} h={row.bbox_height:.0f}]"
                    )
                lines.append(
                    f"- 주변선박 (ID:{row.ship_id}) | 위도:{lat} 경도:{lon} | "
                    f"속도:{spd} 방향:{hdg} | 선체:{lw} 흘수:{draft}{bbox_str}"
                )

    return "\n".join(lines)


# ── 모델 관리자 ───────────────────────────────────────────────────────────────

class ModelManager:
    """에바 VLM 모델 싱글톤 관리자. 동적 체크포인트 전환을 지원한다."""

    def __init__(self) -> None:
        self._model             = None
        self._device: Optional[torch.device] = None
        self._checkpoint_path:   Optional[str] = None
        self._vision_model_name: Optional[str] = None
        self._llm_model_path:    Optional[str] = None
        self._load_error:        Optional[str] = None
        self._loading:           bool = False

    # ── 상태 조회 ─────────────────────────────────────────────────────────────

    @property
    def is_loaded(self)  -> bool: return self._model is not None
    @property
    def is_loading(self) -> bool: return self._loading
    @property
    def load_error(self) -> Optional[str]: return self._load_error
    @property
    def device_str(self) -> Optional[str]: return str(self._device) if self._device else None
    @property
    def checkpoint_path(self) -> Optional[str]: return self._checkpoint_path
    @property
    def vision_model_name(self) -> Optional[str]: return self._vision_model_name
    @property
    def llm_model_path(self) -> Optional[str]: return self._llm_model_path

    @property
    def vram_used_gb(self) -> Optional[float]:
        if self._device and self._device.type == "cuda":
            return torch.cuda.memory_allocated(self._device) / 1e9
        return None

    # ── 모델 로드 ─────────────────────────────────────────────────────────────

    def _ensure_vlm_in_path(self) -> None:
        vlm_root = os.environ.get("EVA_VLM_ROOT", "/app/vlm")
        if vlm_root not in sys.path:
            sys.path.insert(0, vlm_root)

    def load(self) -> None:
        """환경 변수에 지정된 초기 체크포인트로 모델을 로드한다."""
        self._ensure_vlm_in_path()
        llm_path    = os.environ["EVA_LLM_MODEL_PATH"]
        ckpt_path   = os.environ["EVA_CHECKPOINT_PATH"]
        vision_name = os.environ.get("EVA_VISION_MODEL_NAME", "openai/clip-vit-large-patch14-336")
        device_str  = os.environ.get("EVA_DEVICE", "cuda:0")
        self._load_checkpoint(ckpt_path, vision_name, llm_path, device_str)

    def switch_checkpoint(
        self,
        checkpoint_name: str,
        vision_model_name: Optional[str] = None,
        llm_model_path: Optional[str]    = None,
    ) -> None:
        """실행 중에 체크포인트를 전환한다. 기존 모델은 먼저 해제된다."""
        checkpoints_root = os.environ.get("EVA_CHECKPOINTS_ROOT", "/models/checkpoints")
        ckpt_path   = os.path.join(checkpoints_root, checkpoint_name)
        vision_name = vision_model_name or self._vision_model_name or \
                      os.environ.get("EVA_VISION_MODEL_NAME", "openai/clip-vit-large-patch14-336")
        llm_path    = llm_model_path or self._llm_model_path or \
                      os.environ["EVA_LLM_MODEL_PATH"]
        device_str  = self.device_str or os.environ.get("EVA_DEVICE", "cuda:0")
        self._load_checkpoint(ckpt_path, vision_name, llm_path, device_str)

    def _load_checkpoint(
        self,
        ckpt_path:    str,
        vision_name:  str,
        llm_path:     str,
        device_str:   str,
    ) -> None:
        self._ensure_vlm_in_path()

        projector_file = os.path.join(ckpt_path, "projector.bin")
        if not os.path.exists(projector_file):
            raise FileNotFoundError(f"projector.bin 없음: {projector_file}")

        has_lora = os.path.exists(os.path.join(ckpt_path, "adapter_config.json"))

        self._loading    = True
        self._load_error = None
        try:
            from model import VLMConfig, build_model as _build

            config = VLMConfig(
                vision_model_name=vision_name,
                llm_model_name=llm_path,
                projector_type="mlp2x_gelu",
                freeze_vision=True,
                freeze_llm=not has_lora,
            )

            # 기존 모델 해제 후 새 모델 로드
            self._unload()
            m = _build(config, torch_dtype=torch.bfloat16)

            proj_state = torch.load(projector_file, map_location="cpu", weights_only=True)
            m.projector.load_weights(proj_state)

            if has_lora:
                from peft import PeftModel
                m.language_model = PeftModel.from_pretrained(
                    m.language_model, ckpt_path, torch_dtype=torch.bfloat16,
                )
                m.language_model = m.language_model.merge_and_unload()

            device = torch.device(device_str if torch.cuda.is_available() else "cpu")
            m = m.to(device)
            m.eval()

            self._model             = m
            self._device            = device
            self._checkpoint_path   = ckpt_path
            self._vision_model_name = vision_name
            self._llm_model_path    = llm_path

        except Exception:
            self._load_error = traceback.format_exc()
            self._unload()
            raise
        finally:
            self._loading = False

    def _unload(self) -> None:
        if self._model is not None:
            self._model.cpu()
            del self._model
            self._model = None
            gc.collect()
            torch.cuda.empty_cache()

    # ── 체크포인트 목록 조회 ──────────────────────────────────────────────────

    def list_checkpoints(self) -> List[CheckpointInfo]:
        """NFS 체크포인트 루트를 스캔하여 유효한 체크포인트 목록을 반환한다."""
        self._ensure_vlm_in_path()
        root = os.environ.get("EVA_CHECKPOINTS_ROOT", "/models/checkpoints")
        result: List[CheckpointInfo] = []

        if not os.path.isdir(root):
            return result

        for entry in sorted(os.scandir(root), key=lambda e: e.name):
            if not entry.is_dir():
                continue
            proj_file = os.path.join(entry.path, "projector.bin")
            if not os.path.exists(proj_file):
                continue

            has_lora  = os.path.exists(os.path.join(entry.path, "adapter_config.json"))
            is_active = (self._checkpoint_path == entry.path)

            # 디렉토리 전체 크기 (MB)
            try:
                size_bytes = sum(
                    f.stat().st_size
                    for f in Path(entry.path).rglob("*")
                    if f.is_file()
                )
                size_mb = round(size_bytes / 1e6, 1)
            except Exception:
                size_mb = None

            # 생성 시각 (projector.bin mtime 기준)
            try:
                mtime = os.path.getmtime(proj_file)
                created_at = datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()
            except Exception:
                created_at = None

            result.append(CheckpointInfo(
                name=entry.name,
                path=entry.path,
                has_lora=has_lora,
                size_mb=size_mb,
                created_at=created_at,
                is_active=is_active,
            ))

        return result

    # ── 추론 ─────────────────────────────────────────────────────────────────

    def infer(
        self,
        image_base64:       str,
        ais_rows:           List[AISRow],
        output_type:        str,
        custom_prompt:      Optional[str] = None,
        max_new_tokens:     int   = 512,
        repetition_penalty: float = 1.1,
        do_sample:          bool  = False,
    ) -> tuple[str, float]:
        """추론 실행. (생성 텍스트, 소요 시간(초)) 반환."""
        if self._model is None:
            raise RuntimeError("모델이 로드되지 않았습니다.")

        img_bytes = base64.b64decode(image_base64)
        image = Image.open(io.BytesIO(img_bytes)).convert("RGB")

        lang = "en" if "영문" in output_type else "ko"
        ais_text  = format_ais_text(ais_rows, lang=lang)
        question  = custom_prompt.strip() if custom_prompt else PROMPT_MAP.get(output_type, "")
        full_q    = f"{ais_text}\n\n{question}" if ais_text else question

        tokenizer       = self._model.tokenizer
        image_processor = self._model.vision_encoder.image_processor

        messages    = [{"role": "user", "content": f"<image>\n{full_q}"}]
        prompt_text = tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True,
        )

        pixel_values = image_processor(images=image, return_tensors="pt").pixel_values
        pixel_values = pixel_values.to(self._device, dtype=torch.bfloat16)

        input_ids = tokenizer(
            prompt_text, add_special_tokens=False, return_tensors="pt"
        ).input_ids.to(self._device)
        attention_mask = torch.ones_like(input_ids)

        t0 = time.perf_counter()
        with torch.no_grad():
            output_ids = self._model.generate(
                input_ids=input_ids,
                attention_mask=attention_mask,
                pixel_values=pixel_values,
                max_new_tokens=max_new_tokens,
                do_sample=do_sample,
                pad_token_id=tokenizer.pad_token_id,
                eos_token_id=tokenizer.eos_token_id,
                repetition_penalty=repetition_penalty,
            )
        elapsed = time.perf_counter() - t0

        response = tokenizer.decode(output_ids[0], skip_special_tokens=True)
        if "</think>" in response:
            response = response.split("</think>")[-1].strip()
        elif full_q in response:
            response = response.split(full_q)[-1].strip()

        return response, elapsed


# ── 싱글톤 ────────────────────────────────────────────────────────────────────

_manager = ModelManager()

def get_manager() -> ModelManager:
    return _manager
