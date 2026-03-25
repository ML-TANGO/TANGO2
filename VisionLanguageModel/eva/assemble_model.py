import torch
import torch.nn as nn
from transformers import (
    LlamaConfig,
    LlamaForCausalLM,
    CLIPVisionConfig,
    CLIPVisionModel,
    LlavaConfig,
    LlavaForConditionalGeneration
)
from accelerate import init_empty_weights

# 경로 설정
MODEL_PATH = "/home/yvvyee/data/llamarine"
VISION_TOWER = "openai/clip-vit-large-patch14-336"
SAVE_PATH = "./llava-70b-init"  # 합체된 모델이 저장될 폴더


def main():
    print("llama/clip 설정 불러오기...")
    llm_config = LlamaConfig.from_pretrained(MODEL_PATH)
    vision_config = CLIPVisionConfig.from_pretrained(VISION_TOWER)

    configuration = LlavaConfig(
        vision_config=vision_config,
        text_config=llm_config,
        vision_feature_select_strategy="default",
        vision_feature_layer=-2,
        torch_dtype=torch.bfloat16,
        attn_implementation="flash_attention_2",
        image_grid_pinpoints=[[336, 336]],
    )

    # 파라미터를 실제 메모리에 올리지 않고 빈 껍데기(구조)만 생성하여 메모리 낭비 방지
    print("Initializing Llava model structure...")
    with init_empty_weights():
        model = LlavaForConditionalGeneration(configuration)

    # 빈 껍데기 모델에 실제 GPU 메모리를 할당하고 데이터 타입을 맞춤
    # model = model.to_empty(device="cuda")
    # 수정 후: CPU 메모리에 빈 텐서 할당
    model = model.to_empty(device="cpu")
    model = model.to(torch.bfloat16)

    # =========================================================
    # [최종 수정] 내부 아키텍처에 맞게 '알맹이'와 '머리'를 분리해서 이식
    # =========================================================

    # 1. 언어 모델(Llama-3.1) 가중치 로드 및 이식
    print("Loading Llama-3.1 weights...")
    # llm_model = LlamaForCausalLM.from_pretrained(MODEL_PATH, torch_dtype=torch.bfloat16).to("cuda")
    llm_model = LlamaForCausalLM.from_pretrained(MODEL_PATH, torch_dtype=torch.bfloat16)  # 수정 후

    # LLaVA 구조 내부에 맞춰 Llama 모델의 알맹이(Hidden state 계산부)만 정확히 이식
    if hasattr(model, 'model') and hasattr(model.model, 'language_model'):
        model.model.language_model = llm_model.model
    elif hasattr(model, 'language_model'):
        model.language_model = llm_model

    # Llama 모델의 언어 생성부(lm_head: 단어 예측기) 이식
    if hasattr(model, 'lm_head'):
        model.lm_head = llm_model.lm_head

    print("4. CLIP 가중치 이식 중...")
    vision_tower_model = CLIPVisionModel.from_pretrained(VISION_TOWER, torch_dtype=torch.bfloat16)
    # LLaVA 구조 내부에 맞춰 CLIP 모델을 정확히 이식
    if hasattr(model, 'model') and hasattr(model.model, 'vision_tower'):
        model.model.vision_tower = vision_tower_model
    elif hasattr(model, 'vision_tower'):
        model.vision_tower = vision_tower_model

    # 3. 비전과 언어를 연결하는 Projector 모듈 위치 탐색
    if hasattr(model, 'model') and hasattr(model.model, 'multi_modal_projector'):
        projector = model.model.multi_modal_projector
    elif hasattr(model, 'multi_modal_projector'):
        projector = model.multi_modal_projector
    else:
        raise AttributeError("Projector를 찾을 수 없습니다.")

    print("5. Projector 초기화 중...")
    # 빈 메모리로 할당되어 쓰레기값이 들어있는 Projector 가중치를 정상 초기화함
    print("Initializing Projector weights...")
    for module in projector.modules():
        if isinstance(module, nn.Linear):
            nn.init.xavier_uniform_(module.weight)  # 가중치는 Xavier Uniform 분포로 초기화
            if module.bias is not None:
                nn.init.zeros_(module.bias)  # 편향(Bias)은 0으로 초기화

    print(f"6. 합체 완료! {SAVE_PATH} 에 모델을 저장합니다...")
    model.save_pretrained(SAVE_PATH)
    print("✨ 저장 완료! 이제 이 폴더를 학습에 사용하시면 됩니다.")


if __name__ == "__main__":
    main()