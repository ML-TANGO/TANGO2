import os
import torch
import transformers
from dataclasses import dataclass, field
from typing import Optional, Dict

from llava_custom.model.language_model.llava_llama import LlavaLlamaForCausalLM
from llava_custom.data.dataset import make_supervised_data_module

@dataclass
class ModelArguments:
    model_name_or_path: Optional[str] = field(default="meta-llama/Meta-Llama-3-8B-Instruct")
    version: Optional[str] = field(default="v1")
    freeze_backbone: bool = field(default=False)
    tune_mm_mlp_adapter: bool = field(default=False)
    mm_vision_tower: Optional[str] = field(default=None)
    mm_projector_type: Optional[str] = field(default='mlp2x_gelu')
    mm_vision_select_layer: Optional[int] = field(default=-1)
    mm_vision_select_feature: Optional[str] = field(default="patch")
    
    # LoRA 관련 설정
    lora_enable: bool = False
    lora_r: int = 128
    lora_alpha: int = 256
    lora_dropout: float = 0.05
    lora_weight_path: str = ""
    lora_bias: str = "none"
    model_max_length: int = field(default=2048, metadata={"help": "Maximum sequence length."})

@dataclass
class DataArguments:
    data_path: str = field(default=None, metadata={"help": "Path to the training data."})
    lazy_preprocess: bool = False
    is_multimodal: bool = field(default=False)
    image_folder: Optional[str] = field(default=None)


def maybe_zero_3(param, ignore_status=False):
    """
    - DeepSpeed ZeRO-3 분산 학습 환경에서 파라미터를 안전하게 CPU 로 수집
    - 분산 가중치 병합 실패 시 일어나는 NaN 텐서 발생 강제 회피
    """
    from deepspeed import zero
    from deepspeed.runtime.zero.partition_parameters import ZeroParamStatus
    
    if hasattr(param, "ds_id"):
        if param.ds_status == ZeroParamStatus.NOT_AVAILABLE:
            if not ignore_status:
                print("Warning: param.ds_status is NOT_AVAILABLE")
        with zero.GatheredParameters([param]):
            param = param.data.detach().cpu().clone()
    else:
        param = param.detach().cpu().clone()
    return param

def get_mm_projector_state_maybe_zero_3(named_params, keys_to_match):
    """
    - 프로젝터 모델 가중치만 선별하여 안전 수집 후 반환
    """
    to_return = {k: maybe_zero_3(v, ignore_status=True) for k, v in named_params if any(key_match in k for key_match in keys_to_match)}
    return to_return

def get_peft_state_maybe_zero_3(named_params, bias):
    """
    - PEFT 모델 가중치 안전 수집 후 반환
    """
    if bias == "none":
        to_return = {k: maybe_zero_3(v, ignore_status=True) for k, v in named_params if "lora_" in k}
    elif bias == "all":
        to_return = {k: maybe_zero_3(v, ignore_status=True) for k, v in named_params if "lora_" in k or "bias" in k}
    elif bias == "lora_only":
        to_return = {}
        maybe_lora_bias = {}
        lora_bias_names = set()
        for k, v in named_params:
            if "lora_" in k:
                to_return[k] = maybe_zero_3(v, ignore_status=True)
                bias_name = k.split("lora_")[0] + "bias"
                lora_bias_names.add(bias_name)
            elif "bias" in k:
                maybe_lora_bias[k] = maybe_zero_3(v, ignore_status=True)
        for k, v in maybe_lora_bias.items():
            if k in lora_bias_names:
                to_return[k] = v
    else:
        raise NotImplementedError
    return to_return

def safe_save_model_for_hf_trainer(trainer, output_dir: str):
    """
    - 기본 저장 모델 용량을 우회하여 필요 가중치 부분만 저장
    """
    try:
        model = trainer.model
        model_args = getattr(trainer, 'model_args', None)

        if model_args and getattr(model_args, 'lora_enable', False):
            # - LoRA 파인튜닝 시 PEFT 어댑터만 저장
            if trainer.args.local_rank == 0 or trainer.args.local_rank == -1:
                state_dict = get_peft_state_maybe_zero_3(model.named_parameters(), model_args.lora_bias)
                model.save_pretrained(output_dir, state_dict=state_dict)
            return

        if getattr(model.config, 'tune_mm_mlp_adapter', False):
            # - 프로젝터만 파인튜닝 시 전체 모델 저장 시도 생략, 프로젝터만 저장
            if trainer.args.local_rank == 0 or trainer.args.local_rank == -1:
                os.makedirs(output_dir, exist_ok=True)
                keys_to_match = ['mm_projector']
                weight_to_save = get_mm_projector_state_maybe_zero_3(model.named_parameters(), keys_to_match)
                torch.save(weight_to_save, os.path.join(output_dir, 'mm_projector.bin'))
            return

        state_dict = trainer.model.state_dict()
        if trainer.args.should_save:
            cpu_state_dict = {key: value.cpu() for key, value in state_dict.items()}
            del state_dict
            trainer._save(output_dir, state_dict=cpu_state_dict)
    except Exception as e:
        print(f"모델 저장 중 에러: {e}")

class LLaVATrainer(transformers.Trainer):
    """
    - 멀티모달 맞춤형 트레이너 오버로딩
    """
    def _save(self, output_dir: Optional[str] = None, state_dict=None):
        try:
            super(LLaVATrainer, self)._save(output_dir, state_dict)
        except Exception as e:
            print(f"Trainer _save 호출 실패: {e}")

    def save_model(self, output_dir: Optional[str] = None, _internal_call: bool = False):
        """
        - save_model 오버로딩을 통해 커스텀 safe_save_model 호출
        """
        try:
            output_dir = output_dir if output_dir is not None else self.args.output_dir
            safe_save_model_for_hf_trainer(self, output_dir)
        except Exception as e:
            print(f"save_model 실패: {e}")

def train():
    try:
        parser = transformers.HfArgumentParser((ModelArguments, DataArguments, transformers.TrainingArguments))
        model_args, data_args, training_args = parser.parse_args_into_dataclasses()

        # - 토크나이저 초기화
        tokenizer = transformers.AutoTokenizer.from_pretrained(
            model_args.model_name_or_path,
            model_max_length=getattr(training_args, 'model_max_length', 2048),
            padding_side="right",
            use_fast=False,
        )
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token

        # - 모델 초기화
        model = LlavaLlamaForCausalLM.from_pretrained(
            model_args.model_name_or_path,
            cache_dir=None,
            torch_dtype=(torch.bfloat16 if training_args.bf16 else None),
            attn_implementation="flash_attention_2",
        )
        model.config.use_cache = False

        if model_args.freeze_backbone:
            model.model.requires_grad_(False)

        # - 비전 모델 세팅
        if model_args.mm_vision_tower is not None:
            model.get_model().initialize_vision_modules(model_args)

            vision_tower = model.get_model().get_vision_tower()
            vision_tower.to(dtype=torch.bfloat16 if training_args.bf16 else torch.float16, device=training_args.device)

            data_args.image_processor = vision_tower.image_processor

            model.config.image_aspect_ratio = getattr(data_args, 'image_aspect_ratio', 'square')
            model.config.image_grid_pinpoints = getattr(data_args, 'image_grid_pinpoints', None)

            # - 프로젝터 학습 시 언어 모델 고정
            if model_args.tune_mm_mlp_adapter:
                model.requires_grad_(False)
                for p in model.get_model().mm_projector.parameters():
                    p.requires_grad = True

                model.config.tune_mm_mlp_adapter = True

        if getattr(training_args, 'gradient_checkpointing', False):
            if hasattr(model, "enable_input_require_grads"):
                model.enable_input_require_grads()
            else:
                def make_inputs_require_grad(module, input, output):
                    output.requires_grad_(True)
                model.get_input_embeddings().register_forward_hook(make_inputs_require_grad)

                
        # - LoRA 설정 (언어 모델 파인튜닝)
        if model_args.lora_enable:
            from peft import LoraConfig, get_peft_model
            lora_config = LoraConfig(
                r=model_args.lora_r,
                lora_alpha=model_args.lora_alpha,
                target_modules=["q_proj", "v_proj", "k_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
                lora_dropout=model_args.lora_dropout,
                bias=model_args.lora_bias,
                task_type="CAUSAL_LM",
            )
            model = get_peft_model(model, lora_config)
            model.print_trainable_parameters()

        data_module = make_supervised_data_module(tokenizer=tokenizer, data_args=data_args)

        trainer = LLaVATrainer(
            model=model,
            tokenizer=tokenizer,
            args=training_args,
            **data_module
        )
        trainer.model_args = model_args

        trainer.train()
        trainer.save_state()
        safe_save_model_for_hf_trainer(trainer, training_args.output_dir)
        
    except Exception as e:
        raise RuntimeError(f"학습 실패: {e}")

if __name__ == "__main__":
    train()
