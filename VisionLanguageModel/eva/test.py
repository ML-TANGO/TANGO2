import os
import torch
import argparse
from PIL import Image
from accelerate import init_empty_weights
from transformers import (
    LlamaConfig,
    LlamaForCausalLM,
    CLIPVisionConfig,
    CLIPVisionModel,
    LlavaConfig,
    LlavaForConditionalGeneration,
    LlavaProcessor,
    AutoImageProcessor,  # [NEW] 동적 Image Processor 로드용
    LlamaTokenizer
)
from peft import PeftModel
import deepspeed


# --- 1. 터미널 인자 파서 (Argparse) 설정 ---
def parse_args():
    parser = argparse.ArgumentParser(description="LLaVA Dynamic Vision Inference Script")

    parser.add_argument("--model_path", type=str, required=True, help="베이스 언어 모델 경로 (또는 조립된 LLaVA 모델 경로)")
    parser.add_argument("--vision_tower", type=str, default="openai/clip-vit-large-patch14-336", help="비전 타워 모델명 (어떤 해상도/패치든 가능)")

    parser.add_argument("--projector_path", type=str, default=None, help="학습된 mm_projector.bin 파일 경로")
    parser.add_argument("--lora_path", type=str, default=None, help="학습된 LoRA 어댑터 폴더 경로")

    parser.add_argument("--image_path", type=str, required=True, help="테스트할 이미지 경로")
    parser.add_argument("--prompt", type=str, default="Describe this image", help="모델에게 던질 질문")

    parser.add_argument("--local_rank", type=int, default=-1, help="DeepSpeed 로컬 랭크")
    parser.add_argument('--use_assembled_model', action='store_true', default=False, help="사전에 병합된 체크포인트(llama+clip)를 사용")

    return parser.parse_args()


# --- 2. 모델 로드 및 가중치 주입 함수 ---
def load_llava_for_inference(args, device):
    print(f"\n[1/4] Initializing Tokenizer...")
    tokenizer = LlamaTokenizer.from_pretrained(args.model_path)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    if "<image>" not in tokenizer.get_vocab():
        tokenizer.add_tokens(["<image>"], special_tokens=True)

    # =========================================================
    # [🔥 핵심 변경] 하드코딩 제거! 비전 모델 Config 동적 추출
    # =========================================================
    if args.use_assembled_model:
        print(f"[2/4] Loading assembled LLaVA base model from: {args.model_path}")
        model = LlavaForConditionalGeneration.from_pretrained(
            args.model_path,
            torch_dtype=torch.bfloat16,
            attn_implementation="flash_attention_2"
        )
        # 조립된 모델 내부의 비전 설정에서 정보 추출
        vision_config = model.config.vision_config
        image_size = getattr(vision_config, "image_size", 336)
        patch_size = getattr(vision_config, "patch_size", 14)

    else:
        print(f"[2/4] Manually assembling LLaVA structure from: {args.model_path}")
        llm_config = LlamaConfig.from_pretrained(args.model_path)

        # # 외부 비전 타워에서 설정 동적 로드 (예: patch16-224 등 대응)
        # vision_config = AutoConfig.from_pretrained(args.vision_tower)
        # image_size = getattr(vision_config, "image_size", 336)
        # patch_size = getattr(vision_config, "patch_size", 14)

        # 외부 비전 타워에서 설정 동적 로드 (예: patch16-224 등 대응)
        raw_config = CLIPVisionConfig.from_pretrained(args.vision_tower)

        # [🔥 핵심 수정] CLIP 등 복합 모델인 경우, 껍데기를 벗기고 내부의 vision_config만 추출합니다.
        if hasattr(raw_config, "vision_config"):
            vision_config = raw_config.vision_config
        else:
            vision_config = raw_config

        image_size = getattr(vision_config, "image_size", 336)
        patch_size = getattr(vision_config, "patch_size", 14)

        configuration = LlavaConfig(
            vision_config=vision_config,
            text_config=llm_config,
            vision_feature_select_strategy="default",
            vision_feature_layer=-2,
            torch_dtype=torch.bfloat16,
            attn_implementation="flash_attention_2",
            image_grid_pinpoints=[[image_size, image_size]],  # 동적 해상도 적용
            vision_use_feature_layer_stack=False,
        )

        with init_empty_weights():
            model = LlavaForConditionalGeneration(configuration)
        model = model.to_empty(device="cpu").to(torch.bfloat16)

        # =========================================================
        for param in model.parameters():
            param.data.zero_()
        # =========================================================

        llm_model = LlamaForCausalLM.from_pretrained(args.model_path, torch_dtype=torch.bfloat16)
        if hasattr(model, 'model') and hasattr(model.model, 'language_model'):
            model.model.language_model = llm_model.model
        if hasattr(model, 'lm_head'):
            model.lm_head = llm_model.lm_head

        vision_tower = CLIPVisionModel.from_pretrained(args.vision_tower, torch_dtype=torch.bfloat16)
        if hasattr(model, 'model') and hasattr(model.model, 'vision_tower'):
            model.model.vision_tower = vision_tower

        del llm_model, vision_tower

    print(f" -> Vision Config Detected: image_size={image_size}, patch_size={patch_size}")

    model.resize_token_embeddings(len(tokenizer))

    print(f"\n[3/4] Injecting Trained Weights...")

    if args.projector_path:
        proj_path = args.projector_path
        if os.path.isdir(proj_path):
            proj_path = os.path.join(proj_path, "mm_projector.bin")

        print(f" -> Injecting Projector from: {proj_path}")
        trained_projector_weights = torch.load(proj_path, map_location="cpu")

        new_state_dict = {}
        prefix = 'model.multi_modal_projector' if hasattr(model, 'model') else 'multi_modal_projector'

        for k, v in trained_projector_weights.items():
            clean_k = k.split('multi_modal_projector.')[-1]
            new_state_dict[f"{prefix}.{clean_k}"] = v

        model.load_state_dict(new_state_dict, strict=False)
        print("    ✅ Projector weights successfully injected!")

    if args.lora_path:
        print(f" -> Injecting LoRA adapter from: {args.lora_path}")
        model = PeftModel.from_pretrained(model, args.lora_path)
        print("    🔄 Merging LoRA weights into base model...")
        model = model.merge_and_unload()
        print("    ✅ LoRA weights successfully merged!")

    print(f"\n[4/4] Moving model to {device}...")
    model = model.to(device)
    model.eval()

    # 정보 반환 시 추출한 해상도/패치 사이즈도 함께 넘김
    return model, tokenizer, image_size, patch_size


# --- 3. 메인 실행 함수 ---
def main():
    args = parse_args()

    local_rank = int(os.environ.get("LOCAL_RANK", 0))
    world_size = int(os.environ.get("WORLD_SIZE", 1))
    device = torch.device(f"cuda:{local_rank}")

    if local_rank == 0:
        print(f"Initializing Inference on {world_size} GPU(s)...")

    # 모델 생성 시 동적으로 감지된 비전 해상도 정보를 받아옴
    model, tokenizer, image_size, patch_size = load_llava_for_inference(args, device)

    ds_model = deepspeed.init_inference(
        model,
        tensor_parallel={"tp_size": world_size},
        dtype=torch.bfloat16,
        replace_with_kernel_inject=False
    )
    model = ds_model.module

    # =========================================================
    # [🔥 핵심 변경] 동적 Image Processor 및 Tokenizer Bug Fix
    # =========================================================
    image_processor = AutoImageProcessor.from_pretrained(args.vision_tower)

    # 프로세서의 속성 구조에 따라 동적으로 해상도 강제 동기화
    if hasattr(image_processor, "size"):
        image_processor.size = {"shortest_edge": image_size}
    if hasattr(image_processor, "crop_size"):
        image_processor.crop_size = {"height": image_size, "width": image_size}

    processor = LlavaProcessor(image_processor=image_processor, tokenizer=tokenizer)
    processor.patch_size = patch_size
    processor.vision_feature_select_strategy = "default"

    model.config.image_token_id = tokenizer.convert_tokens_to_ids("<image>")
    model.config.pad_token_id = tokenizer.pad_token_id

    try:
        image = Image.open(args.image_path).convert('RGB')
    except FileNotFoundError:
        if local_rank == 0:
            print(f"\n❌ Error: Image file '{args.image_path}' not found.")
        return

    # prompt_text = f"USER: <image>\n{args.prompt} ASSISTANT:"
    # inputs = processor(text=prompt_text, images=image, return_tensors="pt")
    # inputs = {k: v.to(device) for k, v in inputs.items()}

    prompt_text = f"USER: <image>\n{args.prompt} ASSISTANT:"
    inputs = processor(text=prompt_text, images=image, return_tensors="pt")

    # [🔥 핵심 수정] pixel_values(이미지) 텐서를 float32에서 bfloat16으로 강제 변환하여 NaN 폭발을 막습니다.
    inputs = {
        k: v.to(device=device, dtype=torch.bfloat16) if k == "pixel_values" else v.to(device)
        for k, v in inputs.items()
    }

    # 동적으로 생성되어야 할 타겟 이미지 토큰 개수 자동 계산
    # 예: (224 // 16) ** 2 = 196, (336 // 14) ** 2 = 576
    expected_img_tokens = (image_size // patch_size) ** 2

    input_ids = inputs["input_ids"].squeeze(0)
    image_token_id = tokenizer.convert_tokens_to_ids("<image>")
    img_token_cnt = (input_ids == image_token_id).sum().item()

    # 토크나이저 버그가 발생하여 토큰이 모자란 경우 우회
    if 0 < img_token_cnt < expected_img_tokens:
        diff = expected_img_tokens - img_token_cnt
        img_indices = (input_ids == image_token_id).nonzero(as_tuple=True)[0]
        last_idx = img_indices[-1]

        insert_tensor = torch.full((diff,), image_token_id, dtype=input_ids.dtype, device=device)
        input_ids = torch.cat([input_ids[:last_idx + 1], insert_tensor, input_ids[last_idx + 1:]])
        inputs["input_ids"] = input_ids.unsqueeze(0)

        if "attention_mask" in inputs:
            attn_mask = inputs["attention_mask"].squeeze(0)
            insert_attn = torch.ones(diff, dtype=attn_mask.dtype, device=device)
            attn_mask = torch.cat([attn_mask[:last_idx + 1], insert_attn, attn_mask[last_idx + 1:]])
            inputs["attention_mask"] = attn_mask.unsqueeze(0)
    # =========================================================

    if local_rank == 0:
        print(f"\nGenerating response...")

    with torch.no_grad():
        output_ids = model.generate(
            **inputs,
            max_new_tokens=512,
            do_sample=True,
            temperature=0.2,
            top_p=0.9,
            use_cache=True,
            pad_token_id=tokenizer.pad_token_id,
            eos_token_id=tokenizer.eos_token_id
        )

    if local_rank == 0:
        response = tokenizer.decode(output_ids[0], skip_special_tokens=True).strip()
        if "ASSISTANT:" in response:
            final_answer = response.split("ASSISTANT:")[1].strip()
        else:
            final_answer = response

        print(f"\n" + "=" * 50)
        print(f"[LLaVA MODEL RESPONSE]")
        print(f"=" * 50)
        print(final_answer)
        print(f"=" * 50)

    torch.cuda.empty_cache()


if __name__ == "__main__":
    main()