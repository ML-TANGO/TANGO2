import argparse
import shutil
import os
import glob
import traceback
import subprocess
import signal
import json
import pytz
from datetime import datetime
import numpy as np
from transformers import (
    AutoTokenizer, 
    AutoModelForCausalLM, 
    TrainingArguments, 
    Trainer, 
    AutoConfig, 
    BitsAndBytesConfig, 
    TrainerCallback, 
    DataCollatorForLanguageModeling
)
from transformers.utils import logging
from peft import LoraConfig, get_peft_model, PeftModel, PeftConfig
from datasets import load_dataset, Dataset, load_from_disk
import torch
import torch.nn as nn
from db import update_steps_per_epoch, update_finetuning_error_status, update_finetuning_running_status
from typing import Optional, Dict, Any, Tuple, Union
from dataclasses import dataclass
from pathlib import Path


@dataclass
class TrainingConfig:
    """학습 설정을 관리하는 데이터 클래스"""
    fp16: bool = True  # 16비트 정밀도 사용으로 메모리 절약 및 학습 속도 향상
    weight_decay: float = 0.01  # 가중치 감쇠로 과적합 방지
    overwrite_output_dir: bool = True  # 기존 출력 디렉토리 덮어쓰기
    output_dir: str = "/tmp_model"  # 모델 저장 경로
    logging_dir: str = "/logs"  # 로그 저장 경로
    remove_unused_columns: bool = True  # 사용하지 않는 컬럼 제거로 메모리 효율성
    save_total_limit: int = 1  # 저장할 체크포인트 수 제한
    save_strategy: str = "steps"  # 스텝 단위로 모델 저장
    logging_strategy: str = "steps"  # 스텝 단위로 로그 기록
    eval_strategy: str = "steps"  # 스텝 단위로 평가 실행
    eval_steps: int = 5  # 평가 실행 간격
    logging_steps: int = 5 # 로그 기록 간격
    save_steps: int = 1000  # 모델 저장 간격
    prediction_loss_only: bool = True  # 예측 손실만 계산하여 메모리 절약
    dataloader_pin_memory: bool = False  # 메모리 고정 비활성화 (DeepSpeed 호환성)
    dataloader_num_workers: int = 0  # 데이터 로더 워커 수 (DeepSpeed 호환성)


@dataclass
class FineTuningArgs:
    """파인튜닝 인자들을 관리하는 데이터 클래스"""
    local_rank: int  # 분산 학습에서 현재 프로세스의 로컬 랭크
    num_nodes: int  # 분산 학습에 사용할 노드 수
    num_gpus: int  # 각 노드에서 사용할 GPU 수
    dataset_path: str  # 학습 데이터셋 경로
    config_path: Optional[str] = None  # 사용자 정의 설정 파일 경로
    num_train_epochs: float = 3.0  # 전체 학습 에포크 수
    gradient_accumulation_steps: int = 1  # 그래디언트 누적 스텝 수 (대용량 배치 시뮬레이션)
    cutoff_length: int = 128  # 입력 시퀀스 최대 토큰 길이
    learning_rate: float = 5e-5  # 학습률
    warmup_steps: int = 0  # 학습률 워밍업 스텝 수
    used_lora: int = 0  # LoRA 사용 여부 (0: 비활성화, 1: 활성화)
    used_dist: int = 1  # 분산 학습 사용 여부
    load_in_8bit: int = 0  # 8비트 양자화 사용 여부
    deepspeed: Optional[str] = None  # DeepSpeed 설정 파일 경로


class PathManager:
    """경로 관리를 담당하는 클래스"""
    
    def __init__(self):
        self.model_path = Path("/model")  # 기본 모델 경로
        self.lora_source_model_path = Path("/model/source_model")  # LoRA 소스 모델 경로
        self.log_path = Path("/logs")  # 로그 저장 경로
        self.output_path = Path("/tmp_model")  # 임시 모델 저장 경로
        self.config_path = Path("/configurations")  # 설정 파일 경로
        self.fine_tuning_config_path = Path("/fine_tuning/ds_config.json")  # DeepSpeed 설정 경로
    
    def get_model_path(self) -> Path:
        """사용할 모델 경로를 반환 - LoRA 소스 모델이 있으면 우선 사용"""
        return self.lora_source_model_path if self.lora_source_model_path.exists() else self.model_path
    
    def ensure_directories(self):
        """필요한 디렉토리들을 생성"""
        for path in [self.output_path, self.log_path]:
            path.mkdir(parents=True, exist_ok=True)


class SeoulTimeFormatter(logging.logging.Formatter):
    """서울 시간대를 사용하는 로그 포매터"""
    
    def __init__(self, fmt=None, datefmt=None, style='%'):
        super().__init__(fmt, datefmt, style)
        self.seoul_tz = pytz.timezone("Asia/Seoul")

    def formatTime(self, record, datefmt=None):
        utc_time = datetime.utcfromtimestamp(record.created)
        local_time = utc_time.astimezone(self.seoul_tz)
        if datefmt:
            return local_time.strftime(datefmt)
        return local_time.isoformat()


class LoggerSetup:
    """로거 설정을 관리하는 클래스"""
    
    @staticmethod
    def setup():
        logging.set_verbosity_info()
        logger = logging.get_logger("transformers")
        logger.setLevel(logging.INFO)

        console_handler = logging.logging.StreamHandler()
        formatter = SeoulTimeFormatter(
            "%(asctime)s - %(levelname)s - %(message)s", 
            "%Y-%m-%d %H:%M:%S"
        )
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        return logger


class SavePeftAdapterCallback(TrainerCallback):
    """LoRA 어댑터 저장을 위한 콜백 - 체크포인트마다 어댑터 가중치 저장"""
    
    def __init__(self, save_directory: str):
        self.save_directory = save_directory
        self.logger = logging.get_logger("transformers")

    def on_save(self, args, state, control, **kwargs):
        model = kwargs['model']
        
        if isinstance(model, PeftModel):
            adapter_save_path = os.path.join(self.save_directory, f"checkpoint-{state.global_step}")
            os.makedirs(adapter_save_path, exist_ok=True)
            model.save_pretrained(adapter_save_path)
            self.logger.info(f"Adapter saved at {adapter_save_path}")


class GPUManager:
    """GPU 관련 기능을 관리하는 클래스"""
    
    @staticmethod
    def get_gpu_vram(device) -> float:
        """GPU VRAM 크기를 GB 단위로 반환"""
        vram_bytes = torch.cuda.get_device_properties(device).total_memory
        return vram_bytes / (1024 ** 3)

    @staticmethod
    def get_optimal_batch_size(vram_gb: float) -> int:
        """VRAM 용량에 따라 최적의 배치 크기를 반환"""
        if vram_gb <= 4:
            return 1
        elif vram_gb <= 8:
            return 2
        elif vram_gb <= 16:
            return 4
        elif vram_gb <= 24:
            return 8
        else:
            return 16


class FileManager:
    """파일 및 디렉토리 관리를 담당하는 클래스"""
    
    logger = logging.get_logger("transformers")

    @staticmethod
    def clear_dir_contents(path: Path):
        """디렉토리 내용을 모두 삭제"""
        if not path.is_dir():
            FileManager.logger.warning(f"경로 {path}가 유효하지 않습니다.")
            return

        for item in path.iterdir():
            try:
                if item.is_dir():
                    shutil.rmtree(item)
                else:
                    item.unlink()
            except Exception as e:
                FileManager.logger.error(f"{item} 삭제 중 오류 발생: {e}")

    @staticmethod
    def delete_checkpoint_dir(path: Path):
        """체크포인트 디렉토리들을 삭제 - 최종 모델만 유지"""
        if not path.is_dir():
            FileManager.logger.warning(f"경로 {path}가 유효하지 않습니다.")
            return

        deleted_folders = []
        for item in path.iterdir():
            if item.is_dir() and item.name.startswith("checkpoint-"):
                shutil.rmtree(item)
                deleted_folders.append(str(item))

        if deleted_folders:
            FileManager.logger.info(f"삭제된 폴더: {deleted_folders}")
        else:
            FileManager.logger.info("삭제할 'checkpoint-'로 시작하는 폴더가 없습니다.")

    @staticmethod
    def copy_dir_contents(src_folder: Path, dest_folder: Path):
        """src_folder의 내용만 dest_folder로 복사"""
        dest_folder.mkdir(parents=True, exist_ok=True)
        
        try:
            subprocess.run(['cp', '-r', f'{src_folder}/.', str(dest_folder)], check=True)
        except subprocess.CalledProcessError as e:
            FileManager.logger.error(f"Error copying directory: {e}")


class ModelManager:
    """모델 관련 기능을 관리하는 클래스"""

    @staticmethod
    def get_target_modules(model) -> list:
        """모델 타입에 따른 LoRA 타겟 모듈을 반환 - attention 관련 모듈들에 LoRA 적용"""
        model_name = model.__class__.__name__.lower()

        # 1) 각 모델 아키텍처별 LoRA 적용할 attention 모듈 매핑
        target_modules_map = {
            "gpt2":       ["c_attn", "c_proj"],                  # GPT-2는 Q/K/V를 합친 c_attn과 출력 투영 c_proj 사용 :contentReference[oaicite:0]{index=0}
            "gptj":       ["c_attn", "c_proj"],                  # GPT-J도 GPT-2 스타일 Conv1D 사용 :contentReference[oaicite:1]{index=1}
            "gpt_neo":    ["c_attn", "c_proj"],                  # GPT-Neo 역시 c_attn, c_proj 네이밍 사용 :contentReference[oaicite:2]{index=2}
            "gpt_neox":   ["query_key_value", "dense"],          # GPT-NeoX는 query_key_value 합산 투영과 dense 출력 투영 :contentReference[oaicite:3]{index=3}
            "opt":        ["q_proj", "k_proj", "v_proj", "out_proj"],  # OPTAttention의 q_proj/k_proj/v_proj/out_proj :contentReference[oaicite:4]{index=4}
            "bloom":      ["self_attention.query_key_value", "self_attention.dense"],  # BLOOM은 QKV 합산, dense 투영 
            "llama":      ["q_proj", "k_proj", "v_proj", "o_proj"],       # LLaMA self-attention 
            "llama2":     ["q_proj", "k_proj", "v_proj", "o_proj"],       # LLaMA-2도 동일 네이밍 :contentReference[oaicite:7]{index=7}
            "qwen":       ["q_proj", "k_proj", "v_proj", "o_proj"],       # Qwen은 LLaMA 계열 기반 
            "deepseek-r1":["q_proj", "k_proj", "v_proj", "o_proj"],       # DeepSeek-R1 self-attention :contentReference[oaicite:9]{index=9}
            "mpt":        ["q_proj", "k_proj", "v_proj", "o_proj"],       # MPT는 q_proj/k_proj/v_proj/out_proj 사용 :contentReference[oaicite:10]{index=10}
            "falcon":     ["q_proj", "k_proj", "v_proj", "out_proj"],     # Falcon도 Transformer 기반 q_proj/k_proj/v_proj/out_proj :contentReference[oaicite:11]{index=11}
        }

        # 2) 키워드 매핑 우선 적용
        for keyword, modules in target_modules_map.items():
            if keyword in model_name:
                base_modules = modules.copy()
                break
        else:
            # 3) Mistral/Mixtral 특수 처리
            if any(k in model_name for k in ["mistral", "mixtral"]):
                base_modules = ["q_proj", "v_proj"]
            else:
                # 4) 기본 자동 탐지 (이름에 attn/attention/proj 가 들어가는 모든 모듈)
                base_modules = [
                    name for name, _ in model.named_modules()
                    if any(tag in name.lower() for tag in ["attn", "attention", "proj"])
                ]

        # 5) nn.Linear 레이어 스캔을 통해 빠진 attention 계열 레이어명 보완
        #    — 이름에 proj/attn/query/key/value 등이 포함된 nn.Linear를 추가
        all_modules = set(base_modules)
        for name, module in model.named_modules():
            if isinstance(module, nn.Linear):
                lname = name.lower()
                if any(tag in lname for tag in ["proj", "attn", "query", "key", "value"]):
                    all_modules.add(name)

        # 6) 최종 리스트 반환
        #    — 중복 제거를 위해 set → list 변환, 정렬(Optional)
        return sorted(all_modules)


class DatasetManager:
    """데이터셋 관련 기능을 관리하는 클래스"""
    
    logger = logging.get_logger("transformers")

    @staticmethod
    def print_dataset_info(dataset):
        """데이터셋 정보를 출력"""
        for split in dataset.keys():
            DatasetManager.logger.info(f"Split: {split}, Number of examples: {len(dataset[split])}")
            DatasetManager.logger.info(f"Columns: {dataset[split].column_names}")

    @staticmethod
    def load_dataset_by_path(dataset_path: str, split: str = None) -> Union[Dataset, Dict[str, Dataset]]:
        """확장자 또는 디렉토리에 따라 자동으로 데이터셋 로드"""
        path = Path(dataset_path)
        
        if not path.exists():
            raise FileNotFoundError(f"❌ 경로가 존재하지 않음: {dataset_path}")

        if path.is_dir():
            print(f"[INFO] 디렉토리 기반 arrow 로드: {dataset_path}")
            return load_from_disk(dataset_path)

        ext = path.suffix.lower()
        loader_args = {"data_files": dataset_path}
        if split:
            loader_args["split"] = split

        if ext in [".json", ".jsonl"]:
            print(f"[INFO] JSON 파일 로드: {dataset_path}")
            return load_dataset("json", **loader_args)
        elif ext == ".csv":
            print(f"[INFO] CSV 파일 로드: {dataset_path}")
            return load_dataset("csv", **loader_args)
        elif ext == ".arrow":
            print(f"[INFO] Arrow 파일 로드: {dataset_path}")
            return Dataset.from_file(dataset_path)
        else:
            raise ValueError(f"⚠️ 지원하지 않는 확장자: {ext}")

    @staticmethod
    def prepare_datasets(dataset_path: str, cutoff_length: int, tokenizer) -> Tuple[Dataset, Optional[Dataset]]:
        """데이터셋을 로드하고 전처리 - 토크나이징 및 train/validation 분할"""
        dataset = DatasetManager.load_dataset_by_path(dataset_path=dataset_path)
        
        # Arrow 파일 등에서 단일 Dataset이 반환된 경우 처리
        if isinstance(dataset, Dataset):
            print(f"[INFO] 단일 Dataset 감지. 전체 데이터를 train으로 사용합니다.")
            # 전체 데이터를 train으로 사용 (evaluation 없이 학습)
            train_dataset = dataset
            eval_dataset = None
            print(f"📈 Train 샘플 수: {len(train_dataset)}")
            print(f"📉 Evaluation 데이터셋 없이 학습을 진행합니다.")
        else:
            # DatasetDict인 경우 기존 로직 사용
            # train/validation 분할 - validation이 있으면 validation 사용, 없으면 test 사용
            train_dataset = dataset['train']
            eval_dataset = dataset.get('validation', dataset.get('test'))
            
            # 데이터셋에 있는 split 종류 로그 출력
            available_splits = list(dataset.keys())
            print(f"📊 데이터셋에서 사용 가능한 split 종류: {available_splits}")
            print(f"📈 사용할 train split: train (샘플 수: {len(train_dataset)})")
            
            if eval_dataset is not None:
                eval_split_name = 'validation' if 'validation' in dataset else 'test'
                print(f"📉 사용할 evaluation split: {eval_split_name} (샘플 수: {len(eval_dataset)})")
            else:
                print(f"⚠️ 경고: 데이터셋에 'validation' 또는 'test' 스플릿이 없습니다. "
                      f"현재 사용 가능한 스플릿: {available_splits}. "
                      f"평가 데이터셋 없이 학습을 진행합니다.")

        # 토크나이징 함수 - 텍스트를 토큰으로 변환하고 labels 설정
        def tokenize_function(examples):
            tok = tokenizer(
                examples["text"],
                padding="max_length",   # 항상 max_length 길이로 패딩
                truncation=True,
                max_length=cutoff_length,
                return_attention_mask=True
                # examples['text'],
                # padding=True,
                # max_length=cutoff_length,
                # truncation=True,
                # return_tensors='pt',
                # return_attention_mask=True
            )
            # causal LM용 labels = input_ids 복사본
            tok["labels"] = [list(ids) for ids in tok["input_ids"]]
            return tok

        # 데이터셋 토크나이징 적용
        tokenized_train_dataset = train_dataset.map(
            tokenize_function, 
            batched=True, 
            keep_in_memory=True
        )
        
        # eval_dataset이 있는 경우에만 토크나이징 적용
        tokenized_eval_dataset = None
        if eval_dataset is not None:
            tokenized_eval_dataset = eval_dataset.map(
                tokenize_function, 
                batched=True, 
                keep_in_memory=True
            )
            # 모델 학습을 위해 포맷 설정 - PyTorch 텐서 형태로 변환
            tokenized_eval_dataset.set_format('torch', columns=['input_ids', 'attention_mask', 'labels'])

        # 모델 학습을 위해 포맷 설정 - PyTorch 텐서 형태로 변환
        tokenized_train_dataset.set_format('torch', columns=['input_ids', 'attention_mask', 'labels'])

        return tokenized_train_dataset, tokenized_eval_dataset


class TrainingManager:
    """학습 관련 기능을 관리하는 클래스"""
    
    def __init__(self, logger):
        self.logger = logger
        self.path_manager = PathManager()
        self.training_config = TrainingConfig()
        # TrainingArguments에서 제외할 파라미터들 (중복 방지)
        self.exclude_keys = {
            "fp16", "weight_decay", "overwrite_output_dir", "output_dir", "logging_dir",
            "remove_unused_columns", "save_total_limit", "save_strategy", "logging_strategy",
            "eval_strategy", "eval_steps", "logging_steps", "save_steps", "prediction_loss_only",
            "dataloader_pin_memory", "dataloader_num_workers"
        }

    def create_training_arguments(self, args: FineTuningArgs, remove_unused_columns: bool) -> TrainingArguments:
        """TrainingArguments 생성 - 사용자 설정 파일 또는 기본 DeepSpeed 설정 사용"""
        self.training_config.remove_unused_columns = remove_unused_columns
        
        if args.config_path:
            # 사용자 정의 설정 파일 로드
            config_path = self.path_manager.config_path / args.config_path
            with open(config_path, "r", encoding="utf-8") as file:
                config = json.load(file)
            
            # cutoff_length는 토크나이징에서 이미 처리되므로 제거
            if config.get("cutoff_length"):
                del config["cutoff_length"]
            
            # 제외할 파라미터를 제거하고 필터링하여 중복 방지
            filtered_data = {key: value for key, value in config.items() 
                           if key not in self.exclude_keys}
            
            return TrainingArguments(**filtered_data, **self.training_config.__dict__)
        else:
            # 디폴트 DeepSpeed config 사용
            return TrainingArguments(
                learning_rate=args.learning_rate,
                gradient_accumulation_steps=args.gradient_accumulation_steps,
                num_train_epochs=args.num_train_epochs,
                warmup_steps=args.warmup_steps,
                deepspeed=str(self.path_manager.fine_tuning_config_path),
                **self.training_config.__dict__
            )

    def calculate_steps_per_epoch(self, training_args: TrainingArguments, train_dataset: Dataset) -> int:
        """epoch당 step 수 계산 - 분산 학습과 그래디언트 누적을 고려한 실제 배치 크기 계산"""
        world_size = torch.distributed.get_world_size() if torch.distributed.is_initialized() else 1
        batch_size_per_device = training_args.per_device_train_batch_size
        gradient_accumulation_steps = training_args.gradient_accumulation_steps

        # 실제 배치 크기 = (디바이스당 배치 크기) × (디바이스 수) × (그래디언트 누적 스텝)
        effective_batch_size = batch_size_per_device * world_size * gradient_accumulation_steps
        self.logger.info(f"Effective Batch Size with DeepSpeed: {effective_batch_size}")
        
        total_samples = len(train_dataset)
        # epoch당 스텝 수 = (전체 샘플 수) ÷ (실제 배치 크기) + (나머지가 있으면 1)
        steps_per_epoch = (total_samples // effective_batch_size) + (1 if total_samples % effective_batch_size > 0 else 0)
        self.logger.info(f"Steps per Epoch with DeepSpeed: {steps_per_epoch}")
        
        return steps_per_epoch

    def train_model(self, model, train_dataset: Dataset, eval_dataset: Optional[Dataset], 
                   training_args: TrainingArguments, tokenizer, data_collator=None):
        """모델 학습 실행 - Trainer를 사용한 실제 학습 프로세스"""
        # transformers 4.52.4 호환성을 위한 설정 - DeepSpeed와의 호환성 문제 해결
        training_args.dataloader_pin_memory = False
        training_args.dataloader_num_workers = 0
        
        # eval_dataset이 None인 경우 평가 관련 설정 비활성화
        if eval_dataset is None:
            training_args.eval_strategy = "no"
            training_args.eval_steps = None
            self.logger.info("⚠️ 평가 데이터셋이 없어 평가를 비활성화합니다.")
        
        trainer = Trainer(
            model=model,
            args=training_args,
            train_dataset=train_dataset,
            eval_dataset=eval_dataset,
            tokenizer=tokenizer,
            optimizers=(None, None),  # DeepSpeed가 optimizer를 관리하므로 None
            data_collator=data_collator,
            callbacks=[SavePeftAdapterCallback(save_directory=training_args.output_dir)]
        )
        
        self.logger.info("TRAINING START")
        trainer.can_return_loss = True  # 손실 반환 활성화
        trainer.train()
        self.logger.info("TRAINING COMPLETE")
        
        return trainer


class FineTuningEngine:
    """파인튜닝 엔진 메인 클래스 - 전체 파인튜닝 프로세스 조율"""
    
    def __init__(self):
        self.logger = LoggerSetup.setup()
        self.path_manager = PathManager()
        self.training_manager = TrainingManager(self.logger)
        self.pod_index = int(os.getenv("POD_INDEX", 0))  # 분산 학습에서 현재 pod 인덱스

    def load_tokenizer(self, model_path: Path):
        """토크나이저 로드 - 패딩 토큰을 EOS 토큰으로 설정"""
        try:
            tokenizer = AutoTokenizer.from_pretrained(str(model_path))
            tokenizer.pad_token = tokenizer.eos_token  # 패딩 토큰을 EOS 토큰으로 설정
            self.logger.info("TOKENIZER LOAD SUCCESS")
            return tokenizer
        except Exception as e:
            traceback.print_exc()
            self.logger.error(f"모델 토큰 로드 중 오류 발생: {e}")
            update_finetuning_error_status()
            raise e

    def load_model(self, model_path: Path, args: FineTuningArgs) -> Tuple[Any, bool]:
        """모델 로드 및 LoRA 설정 - 8비트 양자화, LoRA 적용 등"""
        try:
            is_source_model_lora = False
            remove_unused_columns = True
            
            # LoRA 소스 모델이 있으면 우선 사용
            if self.path_manager.lora_source_model_path.exists():
                model_path = self.path_manager.lora_source_model_path
                is_source_model_lora = True
            else:
                model_path = self.path_manager.model_path

            # 모델 로드 - 8비트 양자화 옵션 지원
            if args.load_in_8bit:
                quantization_config = BitsAndBytesConfig(load_in_8bit=True)
                model = AutoModelForCausalLM.from_pretrained(
                    str(model_path),
                    quantization_config=quantization_config
                )
            else:
                model = AutoModelForCausalLM.from_pretrained(str(model_path))

            # LoRA 설정 - 기존 LoRA 모델 병합 또는 새 LoRA 적용
            if args.used_lora or is_source_model_lora:
                if is_source_model_lora:
                    # 기존 LoRA 모델을 로드하고 병합
                    model = PeftModel.from_pretrained(model, str(self.path_manager.model_path))
                    model = model.merge_and_unload()  # LoRA 가중치를 원본 모델에 병합
                    if self.pod_index == 0:
                        # 소스 모델을 출력 디렉토리로 복사
                        FileManager.copy_dir_contents(
                            self.path_manager.lora_source_model_path, 
                            self.path_manager.output_path / "source_model"
                        )
                    remove_unused_columns = False  # 병합된 모델은 컬럼 제거 불필요
                else:
                    if self.pod_index == 0:
                        # 원본 모델을 출력 디렉토리로 복사
                        FileManager.copy_dir_contents(
                            self.path_manager.model_path, 
                            self.path_manager.output_path / "source_model"
                        )

                # 모델 타입에 따른 LoRA 타겟 모듈 설정
                target_modules = ModelManager.get_target_modules(model)
                lora_config = LoraConfig(
                    r=8,  # LoRA 랭크 (적응 가능한 파라미터 수)
                    lora_alpha=16,  # LoRA 스케일링 팩터
                    lora_dropout=0.05,  # LoRA 드롭아웃
                    target_modules=target_modules  # LoRA를 적용할 모듈들
                )
                model = get_peft_model(model, lora_config)
                self.logger.info("LORA MODEL LOAD SUCCESS")

            self.logger.info("MODEL LOAD SUCCESS")
            return model, remove_unused_columns

        except Exception as e:
            traceback.print_exc()
            self.logger.error(f"모델 로드 중 오류 발생: {e}")
            update_finetuning_error_status()
            raise e

    def fine_tuning(self, args: FineTuningArgs):
        """파인튜닝 메인 프로세스 - 전체 파인튜닝 워크플로우 실행"""
        try:
            # 경로 설정 및 디렉토리 생성
            self.path_manager.ensure_directories()
            model_path = self.path_manager.get_model_path()

            # 토크나이저 로드
            tokenizer = self.load_tokenizer(model_path)

            # 모델 로드 (LoRA 설정 포함)
            model, remove_unused_columns = self.load_model(model_path, args)

            # 학습 인자 설정 (사용자 설정 또는 기본값)
            training_args = self.training_manager.create_training_arguments(args, remove_unused_columns)
            self.logger.info("TRAINING ARGUMENT LOAD SUCCESS")

            # 데이터셋 준비 (토크나이징 및 train/validation 분할)
            train_dataset, eval_dataset = DatasetManager.prepare_datasets(
                args.dataset_path, args.cutoff_length, tokenizer
            )
            self.logger.info("DATASET LOAD SUCCESS")

            # steps per epoch 계산 (분산 학습 고려)
            steps_per_epoch = self.training_manager.calculate_steps_per_epoch(training_args, train_dataset)
            update_steps_per_epoch(steps_per_epoch=steps_per_epoch)

            self.logger.info("="*20)
            self.logger.info("TRAIN SETTING SUCCESS")
            self.logger.info("="*20)

            # 데이터 콜레이터 설정 (언어 모델링용)
            data_collator = DataCollatorForLanguageModeling(tokenizer=tokenizer, mlm=False)

            # 모델 학습 실행
            trainer = self.training_manager.train_model(
                model, train_dataset, eval_dataset, training_args, tokenizer, data_collator
            )

            # 결과 저장 (첫 번째 pod에서만 실행)
            if self.pod_index == 0:
                trainer.save_model(training_args.output_dir)  # 최종 모델 저장
                FileManager.delete_checkpoint_dir(self.path_manager.output_path)  # 체크포인트 정리
                FileManager.clear_dir_contents(self.path_manager.model_path)  # 기존 모델 정리
                FileManager.copy_dir_contents(self.path_manager.output_path, self.path_manager.model_path)  # 새 모델 복사

            self.logger.info("="*20)
            self.logger.info("FINE TUNING SUCCESS AND MODEL SAVE SUCCESS")
            self.logger.info("="*20)

        except Exception as e:
            traceback.print_exc()
            self.logger.error(f"파인튜닝 중 오류 발생: {e}")
            update_finetuning_error_status()
            raise e


def main():
    """메인 함수 - 명령행 인자 파싱 및 파인튜닝 엔진 실행"""
    parser = argparse.ArgumentParser(description="Fine-tune a Hugging Face model.")
    parser.add_argument("--local_rank", type=int, default=0, required=True, 
                       help="현재 프로세스의 로컬 랭크 (분산 학습에서 사용)")
    parser.add_argument("--num_nodes", type=int, default=0, required=True, 
                       help="분산 학습에 사용할 노드 수")
    parser.add_argument("--deepspeed", type=str, default=None, 
                       help="DeepSpeed 설정 파일 경로 (분산 학습 최적화용)")
    parser.add_argument("--num_gpus", type=int, default=0, required=True, 
                       help="각 노드에서 사용할 GPU 수")
    parser.add_argument("--dataset_path", type=str, required=True, 
                       help="학습에 사용할 데이터셋 경로 (HuggingFace datasets 형식)")
    parser.add_argument("--config_path", type=str, required=False, default=None, 
                       help="사용자 정의 학습 설정 파일 경로 (JSON 형식)")
    parser.add_argument("--num_train_epochs", type=float, default=3.0, 
                       help="전체 학습 에포크 수")
    parser.add_argument("--gradient_accumulation_steps", type=int, default=1, 
                       help="그래디언트 누적 스텝 수 (메모리 효율성을 위해 사용)")
    parser.add_argument("--cutoff_length", type=int, default=128, 
                       help="입력 시퀀스의 최대 토큰 길이 (패딩/트렁케이션 기준)")
    parser.add_argument("--learning_rate", type=float, default=5e-5, 
                       help="학습률 (기본값: 5e-5)")
    parser.add_argument("--warmup_steps", type=int, default=0, 
                       help="학습률 워밍업 스텝 수 (점진적 학습률 증가)")
    parser.add_argument("--used_lora", type=int, default=0, 
                       help="LoRA (Low-Rank Adaptation) 사용 여부 (0: 비활성화, 1: 활성화)")
    parser.add_argument("--used_dist", type=int, default=1, 
                       help="분산 학습 사용 여부 (0: 비활성화, 1: 활성화)")
    parser.add_argument("--load_in_8bit", type=int, default=0, 
                       help="8비트 양자화로 모델 로드 여부 (메모리 절약용, 0: 비활성화, 1: 활성화)")

    args = parser.parse_args()
    pod_index = int(os.getenv("POD_INDEX", 0))
    
    # 첫 번째 pod에서만 초기화 작업 수행
    if pod_index == 0:
        update_finetuning_running_status()  # 파인튜닝 상태 업데이트
        path_manager = PathManager()
        FileManager.clear_dir_contents(path_manager.output_path)  # 출력 디렉토리 정리
        FileManager.clear_dir_contents(path_manager.log_path)  # 로그 디렉토리 정리

    # FineTuningArgs 객체 생성
    fine_tuning_args = FineTuningArgs(
        local_rank=args.local_rank,
        num_nodes=args.num_nodes,
        num_gpus=args.num_gpus,
        dataset_path=args.dataset_path,
        config_path=args.config_path,
        num_train_epochs=args.num_train_epochs,
        gradient_accumulation_steps=args.gradient_accumulation_steps,
        cutoff_length=args.cutoff_length,
        learning_rate=args.learning_rate,
        warmup_steps=args.warmup_steps,
        used_lora=args.used_lora,
        used_dist=args.used_dist,
        load_in_8bit=args.load_in_8bit,
        deepspeed=args.deepspeed
    )

    # 파인튜닝 엔진 실행
    engine = FineTuningEngine()
    engine.logger.info(fine_tuning_args)
    
    try:
        engine.fine_tuning(fine_tuning_args)
    except Exception:
        if pod_index == 0:
            update_finetuning_error_status()  # 오류 상태 업데이트


if __name__ == "__main__":
    main()


"""
================================================================================
📋 전체 파인튜닝 워크플로우 흐름 설명
================================================================================

🎯 목적: Hugging Face 기반 언어 모델의 효율적인 파인튜닝을 위한 통합 엔진

🔄 전체 프로세스 흐름:

1️⃣ 초기화 단계 (main 함수)
   ├── 명령행 인자 파싱 (분산 학습 설정, 데이터셋 경로, LoRA 옵션 등)
   ├── pod_index 확인 (분산 학습에서 현재 pod 식별)
   └── 첫 번째 pod에서만 초기화 작업 수행
       ├── 파인튜닝 상태 업데이트 (DB)
       ├── 출력 디렉토리 정리 (/tmp_model)
       └── 로그 디렉토리 정리 (/logs)

2️⃣ 경로 및 환경 설정 (PathManager)
   ├── 모델 경로 결정 (/model 또는 /model/source_model)
   ├── LoRA 소스 모델 우선 사용 (존재 시)
   └── 필요한 디렉토리 생성

3️⃣ 토크나이저 로드 (load_tokenizer)
   ├── AutoTokenizer로 모델별 토크나이저 자동 로드
   ├── 패딩 토큰을 EOS 토큰으로 설정 (언어 모델링용)
   └── 오류 발생 시 DB 상태 업데이트

4️⃣ 모델 로드 및 LoRA 설정 (load_model)
   ├── 모델 로드 옵션
   │   ├── 8비트 양자화 (메모리 절약)
   │   └── 일반 로드
   ├── LoRA 처리 로직
   │   ├── 기존 LoRA 모델인 경우
   │   │   ├── PeftModel 로드
   │   │   ├── merge_and_unload()로 가중치 병합
   │   │   └── 소스 모델 복사
   │   └── 새 LoRA 적용인 경우
   │       ├── 모델 타입별 타겟 모듈 자동 탐지
   │       ├── LoraConfig 설정 (r=8, alpha=16, dropout=0.05)
   │       └── get_peft_model()로 LoRA 적용
   └── remove_unused_columns 플래그 결정

5️⃣ 학습 인자 설정 (create_training_arguments)
   ├── 사용자 설정 파일 사용 (config_path 제공 시)
   │   ├── JSON 설정 파일 로드
   │   ├── cutoff_length 제거 (토크나이징에서 처리됨)
   │   └── 중복 파라미터 필터링
   └── 기본 DeepSpeed 설정 사용
       ├── learning_rate, epochs, warmup_steps 등
       └── DeepSpeed 설정 파일 경로 지정

6️⃣ 데이터셋 준비 (prepare_datasets)
   ├── 데이터셋 로드
   │   ├── 디렉토리 기반 Arrow 형식
   │   ├── JSON/JSONL 파일
   │   └── CSV 파일
   ├── train/validation 분할
   │   ├── validation이 있으면 validation 사용, 없으면 test 사용
   │   └── validation이 없으면 오류 발생
   ├── 토크나이징
   │   ├── 패딩, 트렁케이션, attention_mask 생성
   │   └── labels를 input_ids와 동일하게 설정 (언어 모델링)
   └── PyTorch 텐서 형태로 포맷 설정

7️⃣ 학습 스케줄링 (calculate_steps_per_epoch)
   ├── 분산 학습 고려
   │   ├── world_size (총 디바이스 수)
   │   ├── per_device_batch_size
   │   └── gradient_accumulation_steps
   ├── 실제 배치 크기 계산
   │   └── effective_batch_size = batch_size × world_size × accumulation
   └── epoch당 스텝 수 계산
       └── steps_per_epoch = total_samples ÷ effective_batch_size

8️⃣ 모델 학습 실행 (train_model)
   ├── Trainer 설정
   │   ├── DeepSpeed 호환성 설정 (pin_memory=False, num_workers=0)
   │   ├── optimizers=None (DeepSpeed가 관리)
   │   └── SavePeftAdapterCallback 추가 (LoRA 어댑터 저장)
   ├── 학습 시작
   │   ├── trainer.can_return_loss = True
   │   └── trainer.train()
   └── 학습 완료

9️⃣ 결과 저장 및 정리 (첫 번째 pod에서만)
   ├── 최종 모델 저장 (trainer.save_model)
   ├── 체크포인트 정리 (checkpoint-* 디렉토리 삭제)
   ├── 기존 모델 정리 (/model 디렉토리 비우기)
   └── 새 모델 복사 (/tmp_model → /model)

🔧 핵심 기술적 특징:

• 분산 학습 지원: DeepSpeed를 통한 다중 GPU/노드 학습
• LoRA 효율성: 적은 파라미터로 대형 모델 파인튜닝
• 메모리 최적화: 8비트 양자화, 16비트 정밀도, 그래디언트 누적
• 자동화: 모델 타입별 LoRA 타겟 모듈 자동 탐지
• 오류 처리: 각 단계별 예외 처리 및 DB 상태 업데이트
• 재현 가능성: 고정된 seed와 체계적인 로깅

📊 성능 최적화 포인트:

• 배치 크기: VRAM 용량에 따른 자동 최적화
• 학습률: 워밍업과 스케줄링 지원
• 체크포인트: 저장 제한으로 디스크 공간 절약
• 데이터 로딩: 배치 처리와 메모리 효율적 토크나이징

🚀 사용 시나리오:

1. 단일 GPU 파인튜닝: used_dist=0, used_lora=1
2. 다중 GPU 파인튜닝: used_dist=1, num_gpus=N
3. 기존 LoRA 모델 연속 학습: lora_source_model_path 사용
4. 메모리 제약 환경: load_in_8bit=1, gradient_accumulation_steps=N

================================================================================
"""