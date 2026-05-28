# GAA — Geometric Attention Alignment

CLIP 비전 인코더의 CLS 토큰 어텐션이 배경 패치에 집중되는 현상을 억제하는 보조 손실 함수입니다.  
바운딩 박스 어노테이션을 **학습 시 특권 정보(privileged information)** 로만 활용하며, 추론 시에는 사용하지 않습니다.

---

## 알고리즘 개요

### 핵심 직관

LLaVA 계열 VLM에서 CLIP은 배경 텍스처(파도, 하늘)에 과도한 어텐션을 두어 선박 객체 인식을 방해하는 경향이 있습니다.  
GAA는 바운딩 박스로 정의된 전경 영역 밖의 패치에 대한 CLS 어텐션을 페널티하여 이를 완화합니다.

```
이미지 + BBox (학습 전용)
       │
       ▼
  [CLIP ViT — eager attention]
       │ output_attentions=True
       ▼
  CLS 어텐션 맵 A_h  (B, H, 24, 24)
       │
       ▼
  Geometric Mask M   (B, 24, 24)  ← BBox 투영
       │
       ▼
  L_geo = ||A_h ⊙ (1-M)||²₂ / |background|
       │
       ▼
  L_total = L_SFT + λ · L_geo
```

### 수식

**기하 마스크 (Eq. 4)**

패치 *i*가 바운딩 박스 *b*에 대해 전경인 경우:

```
M_i = 1[ coverage(patch_i, b) > τ ]

coverage = intersection_area(patch_i, b) / cell_area
```

> 표준 IoU 대신 **커버리지(inter/cell)** 를 사용합니다.  
> 대형 바운딩 박스 내부의 작은 패치는 IoU가 항상 τ(=0.5)에 미달하기 때문입니다.

**기하 일관성 손실 (Eq. 5)**

```
L_geo = (1/N_B) Σ_k  (1/||1-M^(k)||₁) * Σ_h ||A_h^(k) ⊙ (1-M^(k))||²₂
```

- `A_h^(k)` : k번째 샘플, h번째 헤드의 CLS→patch 어텐션 벡터
- `(1-M^(k))` : 배경 마스크 (1=배경, 0=전경)
- `||1-M^(k)||₁` : 배경 패치 수 (크기 편향 제거용 정규화)

**최종 손실 (Eq. 6)**

```
L_total = L_SFT + λ · L_geo        (λ = 0.5, 논문 최적값)
```

### LUPI 패러다임

| 단계 | 바운딩 박스 사용 |
|------|----------------|
| 학습 | O (L_geo 계산용) |
| 추론 | X (표준 VLM과 동일) |

---

## 디렉토리 구조

```
gaa/
├── geometric_loss.py    # Eq. 4, 5 구현 (compute_geometric_mask, compute_geometric_loss)
├── gaa_dataset.py       # GAADataset / GAADataCollator — bboxes 필드 추가
├── gaa_trainer.py       # GAATrainer — compute_loss()에 L_geo 합산
├── train_gaa.py         # 학습 진입점 (freeze_vision=False, eager attention 재로드)
├── sds_reformat.py      # SDS 에피소드 → GAA chat.json 변환 스크립트
├── compare_models.py    # Baseline vs GAA 모델 나란히 비교
└── README.md
```

---

## 기존 코드와의 차이점

| 항목 | 기존 (`train.py`) | GAA (`train_gaa.py`) |
|------|-------------------|----------------------|
| `freeze_vision` | `True` | `False` (L_geo 역전파 필요) |
| CLIP attention 구현 | SDPA (기본) | Eager (`attn_implementation="eager"`) |
| 손실 함수 | L_SFT | L_SFT + λ·L_geo |
| 데이터 포맷 | `conversations` + `image` | + `bboxes` 필드 |
| CLIP forward | 1회 (SFT용) | 2회 (SFT + attention 추출) |

**기존 코드 무변경** — `model/`, `data/`, `train.py`에 수정 없이 `gaa/` 하위에만 구현됩니다.

---

## 데이터 준비

SDS 에피소드 디렉토리를 GAA용 chat.json으로 변환합니다.

```bash
# 영문 (기본)
python gaa/sds_reformat.py \
    --dataset_dir /path/to/SDS/dataset/20260227 \
    --output      data/sds_gaa_en.json \
    --lang        en

# 한글
python gaa/sds_reformat.py \
    --dataset_dir /path/to/SDS/dataset/20260227 \
    --output      data/sds_gaa_ko.json \
    --lang        kor
```

생성되는 JSON 샘플 구조:

```json
{
  "id": "ep001_en",
  "image": "ep001/input_image.png",
  "conversations": [
    { "from": "human", "value": "<image>\n[Vessel AIS Information]\n..." },
    { "from": "gpt",   "value": "Crossing Situation detected..." }
  ],
  "bboxes": [[0.508, 0.294, 0.721, 0.538]]
}
```

`bboxes` 필드: `[x1, y1, x2, y2]` (0~1 정규화 좌표) 리스트.  
샘플당 여러 박스 지원. 박스 없는 샘플은 빈 리스트 `[]`.

---

## 학습

### 단일 GPU

```bash
conda activate eva

CUDA_VISIBLE_DEVICES=0 python gaa/train_gaa.py \
    --vision_model  openai/clip-vit-large-patch14-336 \
    --llm_model     /path/to/Llama-3.1-8B-Instruct \
    --projector_path /path/to/checkpoints/projector.bin \
    --resume_lora_path /path/to/checkpoints/lora_adapter \
    --data_path     data/sds_gaa_en.json \
    --image_dir     /path/to/SDS/dataset/20260227 \
    --output_dir    checkpoints/gaa_sds_en \
    --num_epochs    1 \
    --batch_size    1 \
    --grad_accum    16 \
    --lora_r        16 \
    --lora_alpha    32 \
    --geo_loss_weight 0.5 \
    --geo_tau       0.5 \
    --dtype         bfloat16
```

### 멀티 GPU (DeepSpeed)

```bash
# scripts/train_lora_gaa.sh 상단의 경로 수정 후
bash scripts/train_lora_gaa.sh
```

### 주요 인수

| 인수 | 기본값 | 설명 |
|------|--------|------|
| `--geo_loss_weight` | `0.5` | λ: geometric loss 가중치 (논문 최적값) |
| `--geo_tau` | `0.5` | τ: 전경 패치 커버리지 임계값 |
| `--feature_size` | `-1` | ViT 패치 그리드 변(edge). -1=자동 감지 (CLIP-ViT-L: 24) |
| `--resume_lora_path` | None | 기존 LoRA 어댑터 이어받기 경로 |
| `--lora_r` | `128` | LoRA rank (소규모 데이터셋: 16~32 권장) |

### 학습 로그 항목

```
{'loss/sft': 2.73, 'loss/geo': 0.00142, 'loss/total': 2.731, 'epoch': 0}
```

- `loss/sft` : 표준 SFT 크로스엔트로피
- `loss/geo` : 기하 어텐션 손실 (초기 ~0.001, 수렴 후 ~4.8e-05)
- `loss/total` : L_SFT + λ·L_geo

> **참고**: `loss/geo ≈ 4.8e-05`는 CLS 어텐션이 균등 분포에 수렴한 상태의 이론값입니다  
> (16 heads × 400 bg patches × (1/576)² / 400 ≈ 4.83e-05).  
> 초기의 높은 값에서 이 수준으로 감소하면 CLIP이 배경 집중 어텐션을 억제한 것입니다.

---

## 모델 비교

학습된 GAA 체크포인트와 Baseline SFT 체크포인트를 동일 입력으로 비교합니다.

```bash
python gaa/compare_models.py \
    --baseline  /path/to/checkpoints/sds_lora_en \
    --gaa_model /path/to/checkpoints/gaa_sds_en \
    --data_path data/sds_gaa_en.json \
    --image_dir /path/to/SDS/dataset/20260227 \
    --num_samples 10
```

두 모델을 **순차 로드** (Baseline → 삭제 → GAA)하여 GPU OOM을 방지합니다.

---

## GPU 메모리 참고

CLIP-ViT-L + Llama-3.1-8B 기준 (RTX 5090, 32 GB):

| 설정 | 소요 메모리 |
|------|------------|
| `batch_size=4` (2× CLIP forward) | OOM (~35 GB 필요) |
| `batch_size=1, grad_accum=16` | ~28 GB (정상) |

2차 CLIP forward pass (output_attentions=True, eager mode)가 추가 메모리를 소비합니다.  
OOM 발생 시 `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True` 환경변수를 설정하세요.

---

## 주의사항

- **SDPA 비호환**: `output_attentions=True`는 SDPA 백엔드를 지원하지 않습니다.  
  `train_gaa.py`가 CLIP을 eager attention으로 자동 재로드합니다.
- **freeze_vision=False**: GAA gradient이 CLIP을 통해 역전파되므로 비전 인코더가 학습됩니다.  
  소규모 데이터셋에서는 과적합에 주의하세요.
- **과적합 방지**: 100개 미만 샘플에서는 `--num_epochs 1`, `--lora_r 16` 권장.
