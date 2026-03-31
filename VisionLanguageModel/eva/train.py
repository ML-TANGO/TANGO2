import os
import json
import torch
import torch.nn as nn
import argparse
from typing import Dict, Optional, List
from torch.utils.data import Dataset
from PIL import Image
from accelerate import init_empty_weights
from pathlib import Path
from transformers import (
    LlamaConfig,
    LlamaForCausalLM,
    CLIPVisionConfig,
    CLIPVisionModel,
    LlavaConfig,
    LlavaForConditionalGeneration,
    LlavaProcessor,
    Trainer,
    TrainingArguments,
    CLIPImageProcessor,
    LlamaTokenizer,
    BitsAndBytesConfig
)
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training


# --- 터미널 인자 파서 (Argparse) 설정 ---
def parse_args():
    parser = argparse.ArgumentParser(description="LLaVA All-in-One Training Pipeline")

    # 학습 모드 설정
    parser.add_argument("--train_type", type=str, default="projector", choices=["projector", "full", "lora", "qlora"], help="학습 모드 선택")

    # LoRA 하이퍼파라미터
    parser.add_argument("--lora_r", type=int, default=64, help="LoRA 랭크(Rank)")
    parser.add_argument("--lora_alpha", type=int, default=16, help="LoRA 알파")
    parser.add_argument("--lora_dropout", type=float, default=0.05, help="LoRA 드롭아웃")

    # 경로 관련 인자
    parser.add_argument("--data_path", type=str, required=True, help="학습용 chat.json 데이터셋 경로")
    parser.add_argument("--image_folder", type=str, required=True, help="이미지 폴더 경로")
    parser.add_argument("--model_path", type=str, required=True, help="베이스 모델 경로")
    parser.add_argument("--vision_tower", type=str, default="openai/clip-vit-large-patch14-336", help="비전 타워 모델명")
    parser.add_argument("--output_dir", type=str, default="./checkpoints/multi-gpu-test", help="결과물 저장 경로")
    parser.add_argument("--pretrain_mm_mlp_adapter", type=str, default=None, help="사전 학습된 Projector 가중치 경로 (mm_projector.bin)")

    # 학습 하이퍼파라미터 인자
    parser.add_argument("--max_steps", type=int, default=-1, help="최대 학습 스텝 수")
    parser.add_argument("--save_steps", type=int, default=24000, help="학습 중 저장 스텝 수")
    parser.add_argument("--save_total_limit", type=int, default=1, help="최대 저장 할 체크포인트 수")
    parser.add_argument("--per_device_train_batch_size", type=int, default=8, help="GPU 1대당 배치 사이즈")
    parser.add_argument("--per_device_eval_batch_size", type=int, default=4, help="GPU 1대당 배치 사이즈")
    parser.add_argument("--grad_accum_steps", type=int, default=1, help="그래디언트 누적 스텝 수")
    parser.add_argument("--learning_rate", type=float, default=2e-3, help="학습률")
    parser.add_argument("--weight_decay", type=float, default=0., help="가중치 감쇠")
    parser.add_argument("--warmup_steps", type=float, default=0.03, help="학습 초반 동안 학습률 서서히 증가[0. ~ 1.]")
    parser.add_argument("--lr_scheduler_type", type=str, default="cosine", choices=["linear", "cosine", "constant", "constant_with_warmup"])

    # DeepSpeed 및 분산학습 인자
    parser.add_argument("--deepspeed", type=str, default="scripts/zero2.json", help="DeepSpeed 설정 JSON 파일 경로")
    parser.add_argument("--local_rank", type=int, default=-1, help="DeepSpeed 랭크")

    # 기타 파라미터
    parser.add_argument("--max_length", type=int, default=2048, help="모델의 최대 입력 토큰 수")
    parser.add_argument("--logging_steps", type=int, default=1, help="학습 로그 출력 주기")
    parser.add_argument("--num_train_epochs", type=int, default=1, help="전체 데이터셋 반복 학습 횟수")
    parser.add_argument('--bf16', action='store_true', default=False, help="bfloat16 연산 사용")
    parser.add_argument('--tf32', action='store_true', default=False, help="TensorFloat-32 사용")
    parser.add_argument("--report_to", type=str, default="none", choices=["none", "wandb"])
    parser.add_argument("--save_strategy", type=str, default="steps", choices=["no", "epoch", "steps", "best"])
    parser.add_argument("--dataloader_num_workers", type=int, default=1, help="GPU 당 데이터 로더 프로세스 수")
    parser.add_argument('--use_assembled_model', action='store_true', default=False, help="병합된 체크포인트 사용")

    return parser.parse_args()


# --- 모델 조립 함수 (llama-3.1 텍스트 모델 및 clip-vit 비전 모델) ---
def build_llava_model(model_path, vision_tower):
    print(f"Building Text/Vision model from: {model_path}")
    local_rank = int(os.environ.get("LOCAL_RANK", 0))
    # device = torch.device(f"cuda:{local_rank}")

    # 텍스트 모델 및 비전 모델의 설정 구조체를 먼저 로드
    llm_config = LlamaConfig.from_pretrained(model_path)
    vision_config = CLIPVisionConfig.from_pretrained(vision_tower)

    # 두 모델의 설정을 병합하여 llava 전용 설정 객체 생성
    configuration = LlavaConfig(
        vision_config=vision_config,                    # 비전 모델 설정
        text_config=llm_config,                         # 언어 모델 설정
        vision_feature_select_strategy="default",       # 비전 모델 특성 추출 방식
        vision_feature_layer=-2,                        # CLIP의 마지막 2개 계층의 출력만 사용
        torch_dtype=torch.bfloat16,                     # 연산 속도 및 안정성을 위해 bfloat16 사용
        attn_implementation="flash_attention_2",        # 메모리 최적화를 위해 flash attention 2 적용
        image_grid_pinpoints=[[336, 336]],              # 비전 모델의 기본 해상도 지정
        vision_use_feature_layer_stack=False,           # 단일 레이어 특성만 사용 (스택 미적용)
    )

    # 파라미터를 실제 메모리에 올리지 않고 구조만 생성하여 메모리 낭비 방지
    print("Initializing Llava model structure...")
    with init_empty_weights():
        model = LlavaForConditionalGeneration(configuration)

    # GPU 메모리 할당 및 데이터 타입 지정
    model = model.to_empty(device="cpu").to(torch.bfloat16)

    # 언어 모델의 가중치 로드
    print("Loading Llama weights...")
    llm_model = LlamaForCausalLM.from_pretrained(model_path, torch_dtype=torch.bfloat16)
    if hasattr(model, 'model') and hasattr(model.model, 'language_model'):
        model.model.language_model = llm_model.model
    elif hasattr(model, 'language_model'):
        model.language_model = llm_model

    # 언어 모델의 언어 생성부 이식
    if hasattr(model, 'lm_head'):
        model.lm_head = llm_model.lm_head

    # 비전 모델의 가중치 로드
    print("Loading CLIP weights...")
    vision_tower_model = CLIPVisionModel.from_pretrained(vision_tower, torch_dtype=torch.bfloat16)

    # llava 내부 구조에 맞추어 이식
    if hasattr(model, 'model') and hasattr(model.model, 'vision_tower'):
        model.model.vision_tower = vision_tower_model
    elif hasattr(model, 'vision_tower'):
        model.vision_tower = vision_tower_model

    # 언어 모델과 비전 모델을 연결하는 프로젝터 모듈 위치 탐색
    if hasattr(model, 'model') and hasattr(model.model, 'multi_modal_projector'):
        projector = model.model.multi_modal_projector
    elif hasattr(model, 'multi_modal_projector'):
        projector = model.multi_modal_projector
    else:
        raise AttributeError("Projector를 찾을 수 없습니다.")

    # 프로젝터의 가중치를 초기화
    print("Initializing Projector weights...")
    for module in projector.modules():
        if isinstance(module, nn.Linear):
            nn.init.xavier_uniform_(module.weight)
            if module.bias is not None:
                nn.init.zeros_(module.bias)

    # 임시 객체 메모리 해제 및 반환
    del llm_model, vision_tower_model
    return model


# --- 데이터셋 클래스 ---
class LlavaPretrainDataset(Dataset):
    def __init__(self, data_path, image_folder, processor, max_length):
        with open(data_path, "r") as f:
            self.list_data_dict = json.load(f)
        self.image_folder = image_folder
        self.processor = processor
        self.tokenizer = processor.tokenizer
        self.max_length = max_length

    def __len__(self):
        return len(self.list_data_dict)

    def __getitem__(self, i):
        item = self.list_data_dict[i]
        image_file = item.get('image')

        # 텍스트 추출 및 기본 포맷팅: 사용자 질문과 AI 답변을 분리하여 로드
        human_text = item['conversations'][0]['value']
        assistant_text = item['conversations'][1]['value']

        # 사용자 질문에 <image> 토큰을 강제 삽입
        if "<image>" not in human_text:
            human_text = "<image>\n" + human_text

        # 프롬프트와 전체 텍스트 구성: USER, ASSISTANT 태그를 붙여 대화 형식을 구성
        prompt = f"USER: {human_text} ASSISTANT:"
        # 정답까지 포함된 전체 학습용 텍스트 생성 (끝에 EOS 토큰 추가)
        full_text = f"{prompt} {assistant_text}{self.tokenizer.eos_token}"

        try:
            # 이미지 로드: RGB 모드
            image = Image.open(os.path.join(self.image_folder, image_file)).convert('RGB')
        except Exception as e:
            # 이미지가 없는 경우 흰색 더미 이미지를 생성하여 에러 방지
            image = Image.new('RGB', (336, 336), color='white')

        # 전체 텍스트 및 이미지 전처리 (토큰화 및 텐서 변환)
        inputs = self.processor(
            text=full_text,
            images=image,
            return_tensors="pt",
            padding="max_length",
            max_length=self.max_length,
            truncation=True
        )

        # 배치 차원을 제거하여 1차원 배열 형성
        input_ids = inputs["input_ids"].squeeze(0)

        # llama 3 토크나이저가 <image> 토큰 확장 시 누락되는 경우
        image_token_id = self.tokenizer.convert_tokens_to_ids("<image>")
        img_token_cnt = (input_ids == image_token_id).sum().item()  # 현재 생성된 이미지 토큰 수
        expected_img_tokens = 576   # 336 해상도, 14 패치 기준 (24x24=576)

        # expected_img_tokens 과 일치하지 않는 경우
        diff = 0
        if 0 < img_token_cnt < expected_img_tokens:
            # 부족한 토큰 수 계산
            diff = expected_img_tokens - img_token_cnt

            # <image> 토큰이 위치한 배열의 마지막 인덱스 탐색
            img_indices = (input_ids == image_token_id).nonzero(as_tuple=True)[0]
            last_idx = img_indices[-1]

            # 부족한 수만큼 채워 넣을 이미지 토큰 텐서 생성
            insert_tensor = torch.full((diff,), image_token_id, dtype=input_ids.dtype)

            # 기존 배열 중간에 강제 삽입, 뒷부분의 패딩을 잘라냄 (전체 길이 max_length 는 유지)
            input_ids = torch.cat([
                input_ids[:last_idx + 1],
                insert_tensor,
                input_ids[last_idx + 1: -diff]
            ])

        # labels = input_ids.clone()
        # prompt_inputs = self.tokenizer(prompt, return_tensors="pt", add_special_tokens=False)
        # prompt_length = prompt_inputs["input_ids"].shape[1]
        # labels[:prompt_length] = -100
        # labels[labels == self.tokenizer.pad_token_id] = -100

        # 손실 함수 계산을 위한 정답지(labels) 복제
        labels = input_ids.clone()

        # 정답 부분에만 손실 함수를 적용하기 위해 사용자 질문 영역 마스킹을 위한 길이 계산
        prompt_inputs = self.tokenizer(prompt, return_tensors="pt", add_special_tokens=False)
        prompt_length = prompt_inputs["input_ids"].shape[1]

        labels[:prompt_length + diff] = -100    # 삽입된 토큰 수(diff)만큼 마스킹 범위도 늘려주어야 함
        labels[labels == image_token_id] = -100  # <image> 토큰 자체도 정답(Loss)에서 제외하도록 설정
        labels[labels == self.tokenizer.pad_token_id] = -100 # 남는 공간을 채우고 있는 패딩 토큰들의 라벨을 -100으로 덮어씌움

        # loss 폭발 방지
        if (labels != -100).sum() == 0:
            labels[-1] = self.tokenizer.eos_token_id

        return {
            "input_ids": input_ids,
            "pixel_values": inputs["pixel_values"].squeeze(0).to(torch.bfloat16),
            "labels": labels,
        }


# --- 멀티 모드 지원 커스텀 Trainer ---
class LlavaTrainer(Trainer):
    def __init__(self, train_type, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.train_type = train_type

    def _save(self, output_dir: Optional[str] = None, state_dict=None):
        if output_dir is None:
            output_dir = self.args.output_dir
        os.makedirs(output_dir, exist_ok=True)

        if state_dict is None:
            state_dict = self.model.state_dict()

        # 1. Full Fine-Tuning 모드: 원본 그대로 전체 저장
        if self.train_type == "full":
            print(f"\n[Custom Save] Saving FULL model weights to {output_dir}")
            super()._save(output_dir, state_dict)

        # 2. Projector / LoRA / QLoRA 모드: 어댑터와 프로젝터만 저장
        else:
            print(f"\n[Custom Save] Saving PEFT Adapter & Projector weights to {output_dir}")

            # LoRA 가중치 저장 (PEFT 내장 함수)
            if self.train_type in ["lora", "qlora"]:
                self.model.save_pretrained(output_dir)

            # Projector 가중치 분리 저장
            projector_state_dict = {
                k: v for k, v in state_dict.items() if 'multi_modal_projector' in k
            }
            torch.save(projector_state_dict, os.path.join(output_dir, "mm_projector.bin"))

            if self.processing_class is not None:
                self.processing_class.save_pretrained(output_dir)


# --- 메인 학습 루프 ---
def main():
    args = parse_args()

    # 이미지 전처리기 로드
    image_processor = CLIPImageProcessor.from_pretrained(args.vision_tower)
    image_processor.size = {"shortest_edge": 336}
    image_processor.crop_size = {"height": 336, "width": 336}

    # 언어 토크나이저 로드
    tokenizer = LlamaTokenizer.from_pretrained(args.model_path)

    # 패딩 토큰 설정: llama 계열은 기본 패딩 토큰이 없으므로 EOS 토큰을 패딩으로 대체
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    # <image> 토큰 추가
    if "<image>" not in tokenizer.get_vocab():
        tokenizer.add_tokens(["<image>"], special_tokens=True)

    # llava 객체 생성
    processor = LlavaProcessor(image_processor=image_processor, tokenizer=tokenizer)
    processor.patch_size = 14   # 비전 처리기 패치 크기
    processor.vision_feature_select_strategy = "default"

    # 학습 파라미터 설정
    training_args = TrainingArguments(
        output_dir=args.output_dir,                                         # 결과 저장 경로
        per_device_train_batch_size=args.per_device_train_batch_size,       # GPU 1대당 학습 배치 크기
        per_device_eval_batch_size=args.per_device_eval_batch_size,         # GPU 1대당 테스트 배치 크기
        gradient_accumulation_steps=args.grad_accum_steps,                  # 그래디언트 누적 스텝 수
        learning_rate=args.learning_rate,                                   # 학습률
        logging_steps=args.logging_steps,                                   # 로그 출력 빈도
        num_train_epochs=args.num_train_epochs,                             # 전체 데이터셋 반복 학습 수
        max_steps=args.max_steps,                                           # XXX 스텝까지만 제한적으로 학습
        bf16=args.bf16,                                                     # bfloat16 연산 사용
        tf32=args.tf32,                                                     # TensorFloat-32 사용 (Ampere 이상 GPU 에서 속도 향상)
        gradient_checkpointing=True,                                        # 메모리 절약을 위한 체크포인팅 활성화
        save_strategy=args.save_strategy,                                   # 모델 저장 기준
        save_steps=args.save_steps,                                         # 모델 저장 빈도
        save_total_limit=args.save_total_limit,                             # 최대 저장되는 체크포인트의 수 (오랜된 것은 삭제)
        weight_decay=args.weight_decay,                                     # 가중치 감쇠
        warmup_steps=args.warmup_steps,                                     # 학습 초반 학습률 점진적으로 증가
        lr_scheduler_type=args.lr_scheduler_type,                           # 학습률 감소 전략
        push_to_hub=False,                                                  # HuggingFace 허브 자동 업로드
        report_to=args.report_to,                                           # 외부 로깅 도구 사용
        remove_unused_columns=False,                                        # pixel_values 유지 위해, False 로 둬야 이미지 데이터 보존
        deepspeed=args.deepspeed,                                           # deepspeed 설정 파일
        save_only_model=True,                                               # 모델만 저장 또는 옵티마지어 상태까지 저장
        dataloader_num_workers=args.dataloader_num_workers                  # 데이터로더 워커의 수
    )
    training_args.gradient_checkpointing_kwargs = {"use_reentrant": True}

    # QLoRA 양자화 설정 (4-bit)
    quantization_config = None
    if args.train_type == "qlora":
        quantization_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_compute_dtype=torch.bfloat16,
            bnb_4bit_use_double_quant=True,
            bnb_4bit_quant_type="nf4"
        )

    # 체크포인트 로드 - 텍스트 모델과 비전 모델이 미리 병합되어 있는 경우
    if args.use_assembled_model:
        print(f"Loading LLaVA model from {args.model_path} via {Path(args.deepspeed).stem}...")
        model = LlavaForConditionalGeneration.from_pretrained(
            args.model_path,
            torch_dtype=torch.bfloat16,
            attn_implementation="flash_attention_2",
            quantization_config=quantization_config  # QLoRA 시 4bit로 로드
        )
    # 체크포인트 로드 - 텍스트/비전 모델을 개별적으로 로드하고 조립
    else:
        model = build_llava_model(args.model_path, args.vision_tower)

    # 토크나이저 및 임베딩 크기 동기화
    print(f"Resizing token embeddings to {len(tokenizer)}...")
    model.resize_token_embeddings(len(tokenizer))
    model.config.image_token_id = tokenizer.convert_tokens_to_ids("<image>")
    model.config.pad_token_id = tokenizer.pad_token_id
    processor.tokenizer = tokenizer

    # =========================================================
    # 프로젝터 가중치 로드 및 덮어쓰기
    # =========================================================
    if args.pretrain_mm_mlp_adapter is not None:
        print(f"Loading pretrained projector weights from {args.pretrain_mm_mlp_adapter}...")
        projector_weights = torch.load(args.pretrain_mm_mlp_adapter, map_location="cpu")

        # 모델 구조에 맞춰 안전하게 키(Key) 매핑
        if hasattr(model, 'model') and hasattr(model.model, 'multi_modal_projector'):
            prefix = 'model.multi_modal_projector'
        else:
            prefix = 'multi_modal_projector'

        new_state_dict = {}
        for k, v in projector_weights.items():
            # 저장된 키에서 프로젝터 뒷부분 이름만 추출하여 현재 모델 구조에 맞춤
            clean_k = k.split('multi_modal_projector.')[-1]
            new_state_dict[f"{prefix}.{clean_k}"] = v

        # strict=False 로 설정하여 프로젝터 부분 덮어씌움
        model.load_state_dict(new_state_dict, strict=False)
        print("✅ Projector weights successfully injected!")
    # =========================================================

    # =========================================================
    # 학습 모드별 파라미터 고정/해제 및 PEFT(LoRA) 적용 로직
    # =========================================================
    model.requires_grad_(False)  # 기본적으로 전체 파라미터를 얼림

    # 모든 모드 공통: Projector는 무조건 학습
    if hasattr(model, 'model') and hasattr(model.model, 'multi_modal_projector'):
        projector = model.model.multi_modal_projector
    elif hasattr(model, 'multi_modal_projector'):
        projector = model.multi_modal_projector

    for param in projector.parameters():
        param.requires_grad_(True)

    # Full FT: Llama 전체 가중치 학습
    if args.train_type == "full":
        print("[Full FT Mode] 언어 모델(Llama) 전체 가중치를 학습합니다.")
        llm = model.model.language_model if hasattr(model.model, 'language_model') else model.language_model
        for param in llm.parameters():
            param.requires_grad_(True)

    # LoRA / QLoRA 모드: PEFT 어댑터 부착
    elif args.train_type in ["lora", "qlora"]:
        print(f"[{args.train_type.upper()} Mode] 언어 모델에 LoRA 어댑터를 부착합니다.")

        if args.train_type == "qlora":
            model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True)

        lora_config = LoraConfig(
            r=args.lora_r,
            lora_alpha=args.lora_alpha,
            target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
            # Llama 선형 레이어 전체
            lora_dropout=args.lora_dropout,
            bias="none",
            task_type="CAUSAL_LM"
        )

        # PEFT 모델로 래핑 (이 과정에서 lora 외의 파라미터는 자동으로 얼림)
        model = get_peft_model(model, lora_config)

        # PEFT 래핑 후 프로젝터가 다시 잠길 수 있으므로, 명시적으로 다시 개방
        if hasattr(model.base_model.model.model, 'multi_modal_projector'):
            proj = model.base_model.model.model.multi_modal_projector
        else:
            proj = model.base_model.model.multi_modal_projector
        for param in proj.parameters():
            param.requires_grad_(True)

    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"총 학습 가능 파라미터 수: {trainable_params:,}")

    # 데이터셋
    train_dataset = LlavaPretrainDataset(
        data_path=args.data_path,
        image_folder=args.image_folder,
        processor=processor,
        max_length=args.max_length
    )

    # 트레이너
    trainer = LlavaTrainer(
        train_type=args.train_type,  # 커스텀 Trainer에 모드 전달
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        processing_class=processor.tokenizer
    )

    if hasattr(model, "enable_input_require_grads"):
        model.enable_input_require_grads()
    model.config.use_cache = False

    print(f"Starting Training [{args.train_type.upper()} Stage]...")
    trainer.train()

    final_dir = os.path.join(args.output_dir, "final_model")
    trainer.save_model(final_dir)


if __name__ == "__main__":
    main()