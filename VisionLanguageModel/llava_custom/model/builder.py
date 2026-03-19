from transformers import AutoTokenizer, AutoModelForCausalLM, AutoConfig
from llava_custom.model.language_model.llava_llama import LlavaLlamaForCausalLM

def load_pretrained_model(model_path, model_base=None, is_lora=False, **kwargs):
    """
    - 사전 학습된 모델 가중치를 기반으로 토크나이저 및 멀티모달 모델 로드
    """
    try:
        if "attn_implementation" not in kwargs:
            kwargs["attn_implementation"] = "flash_attention_2"
            
        if is_lora:
            # - 베이스 모델 불러오고 peft 적용 (추론용)
            if model_base is not None:
                # If model_base is provided, load the base model from model_base
                model = LlavaLlamaForCausalLM.from_pretrained(model_base, **kwargs)
                tokenizer = AutoTokenizer.from_pretrained(model_base, use_fast=False)
            else:
                # If model_base is None, assume model_path contains the base model
                # and the LoRA weights are merged or to be applied on it.
                # In this case, model_path serves as the base model path.
                model = LlavaLlamaForCausalLM.from_pretrained(model_path, **kwargs)
                tokenizer = AutoTokenizer.from_pretrained(model_path, use_fast=False)
            
            from peft import PeftModel
            model = PeftModel.from_pretrained(model, model_path)
        else:
            # - 일반 모델 로딩
            tokenizer = AutoTokenizer.from_pretrained(model_path, use_fast=False)
            model = LlavaLlamaForCausalLM.from_pretrained(model_path, **kwargs)

        return tokenizer, model
    except Exception as e:
        raise RuntimeError(f"모델 로딩 중 오류 발생: {e}")
