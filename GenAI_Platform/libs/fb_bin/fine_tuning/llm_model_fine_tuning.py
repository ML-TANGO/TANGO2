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
import asyncio
import threading
import time
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

# aiokafka (옵셔널) - 없으면 리스너 비활성화
from aiokafka import AIOKafkaConsumer  # type: ignore




@dataclass
class TrainingConfig:
    """학습 설정을 관리하는 데이터 클래스"""
    fp16: bool = True  # 16비트 정밀도 (기본값, precision 자동 감지로 덮어씀)
    bf16: bool = False  # BF16 정밀도 (BF16 네이티브 모델에서 자동 활성화)
    weight_decay: float = 0.01  # 가중치 감쇠로 과적합 방지
    overwrite_output_dir: bool = True  # 기존 출력 디렉토리 덮어쓰기
    output_dir: str = "/model"  # 모델 저장 경로
    logging_dir: str = "/logs"  # 로그 저장 경로
    remove_unused_columns: bool = True  # 사용하지 않는 컬럼 제거로 메모리 효율성
    save_total_limit: int = 1  # 저장할 체크포인트 수 제한
    save_strategy: str = "steps"  # 스텝 단위로 모델 저장
    logging_strategy: str = "steps"  # 스텝 단위로 로그 기록
    eval_strategy: str = "steps"  # 스텝 단위로 평가 실행
    eval_steps: int = 500  # 평가 실행 간격
    logging_steps: int = 100  # 로그 기록 간격
    save_steps: int = 500  # 모델 저장 간격
    prediction_loss_only: bool = True  # 예측 손실만 계산하여 메모리 절약
    gradient_checkpointing: bool = True  # activation 재계산으로 VRAM 절약 (학습 속도 ~20% 감소, 메모리 대폭 절약)
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
    precision: str = "auto"  # 학습 정밀도: "auto" | "fp16" | "bf16"
    auto_target_modules: int = 1  # LoRA 타겟 모듈 자동 감지: 1=auto(all-linear), 0=static map
    dataset_format: str = "auto"  # 데이터셋 형식: "auto" | "text" | "chat" | "instruction"
    zero_stage: int = 1  # DeepSpeed ZeRO stage: 1, 2, 3


class PathManager:
    """경로 관리를 담당하는 클래스"""
    
    def __init__(self):
        self.model_path = Path("/model")  # 기본 모델 경로
        self.lora_source_model_path = Path("/source_model")  # LoRA 소스 모델 경로
        self.log_path = Path("/logs")  # 로그 저장 경로
        self.output_path = Path("/model")  # 임시 모델 저장 경로 # tmp_model
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


class KafkaStopTrainingCallback(TrainerCallback):
    """
    Kafka 중지 신호를 감지해 학습을 조기 종료하는 콜백

    Args:
        stop_signal_manager: 중지 신호 이벤트를 보유하는 매니저
        logger: 로거 인스턴스
    """

    def __init__(self, stop_signal_manager, logger):
        self.stop_signal_manager = stop_signal_manager
        self.logger = logger

    def on_step_end(self, args, state, control, **kwargs):
        try:
            if self.stop_signal_manager and self.stop_signal_manager.is_stop_requested():
                if state.is_world_process_zero:
                    self.logger.info("⛔ Kafka 중지 요청을 감지했습니다. 학습을 안전하게 종료합니다.")
                control.should_training_stop = True
                # 일부 버전 호환을 위해 epoch 중단 플래그도 설정
                if hasattr(control, "should_epoch_stop"):
                    control.should_epoch_stop = True
        except Exception as e:
            self.logger.warning(f"Kafka 중지 콜백 처리 중 경고: {e}")
        return control

    def on_step_begin(self, args, state, control, **kwargs):
        try:
            if self.stop_signal_manager and self.stop_signal_manager.is_stop_requested():
                if state.is_world_process_zero:
                    self.logger.info("⛔ 중지 신호 감지 - step begin에서 즉시 중단 플래그 설정")
                control.should_training_stop = True
                if hasattr(control, "should_epoch_stop"):
                    control.should_epoch_stop = True
        except Exception as e:
            self.logger.warning(f"Kafka 중지 콜백(step_begin) 처리 중 경고: {e}")
        return control

    def on_substep_end(self, args, state, control, **kwargs):
        # gradient_accumulation_steps>1 환경에서 더 빠른 중단을 유도
        try:
            if self.stop_signal_manager and self.stop_signal_manager.is_stop_requested():
                if state.is_world_process_zero:
                    self.logger.info("⛔ 중지 신호 감지 - substep end에서 중단 플래그 설정")
                control.should_training_stop = True
                if hasattr(control, "should_epoch_stop"):
                    control.should_epoch_stop = True
        except Exception as e:
            self.logger.warning(f"Kafka 중지 콜백(substep_end) 처리 중 경고: {e}")
        return control


class StopSignalManager:
    """
    Kafka Consumer를 백그라운드에서 실행하여 중지 요청을 감지하는 매니저
    
    메시지 포맷(JSON 문자열 권장): {"action": "stop", "job_id": "..."}
    - action == stop 이고, job_id가 일치하면 중지로 간주
    - JSON 파싱 실패 시 원시 문자열에 'stop' 포함 여부로 보조 판정
    """

    def __init__(
        self,
        enable_listener: bool,
        bootstrap_servers: Optional[str],
        topic: Optional[str],
        group_id: Optional[str],
        job_id: Optional[str],
        logger,
    ) -> None:
        self.enable_listener = bool(enable_listener)
        self.bootstrap_servers = bootstrap_servers
        self.topic = topic
        # 그룹을 비워두면(=None) 모든 컨슈머가 동일 메시지를 수신합니다.
        # 분산 학습(멀티 랭크)에서 모든 프로세스가 중지 신호를 받도록 기본 None 권장
        self.group_id = group_id or None
        self.job_id = job_id
        self.logger = logger
        self._consumer = None
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._stop_requested = threading.Event()

    def _create_consumer(self):
        if not self.enable_listener:
            return None
        if not self.bootstrap_servers or not self.topic:
            self.logger.warning("Kafka 서버 또는 토픽이 설정되지 않아 중지 리스너를 비활성화합니다.")
            return None
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            consumer = AIOKafkaConsumer(
                self.topic,
                loop=loop,
                bootstrap_servers=[s.strip() for s in self.bootstrap_servers.split(",") if s.strip()],
                group_id=self.group_id,
                enable_auto_commit=True,
                auto_offset_reset="latest",
                value_deserializer=lambda m: m.decode("utf-8", errors="ignore"),
            )
            return consumer
        except Exception as e:
            self.logger.warning(f"aiokafka Consumer 생성 중 경고: {e}")
            return None

    def start(self) -> None:
        if not self.enable_listener:
            return
        if self._thread and self._thread.is_alive():
            return

        def _run():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            async def _consume():
                # 기본 유효성 검사
                if not self.bootstrap_servers or not self.topic:
                    self.logger.warning("Kafka 서버 또는 토픽이 설정되지 않아 중지 리스너를 비활성화합니다.")
                    return
                try:
                    consumer = AIOKafkaConsumer(
                        self.topic,
                        bootstrap_servers=[s.strip() for s in self.bootstrap_servers.split(",") if s.strip()],
                        group_id=self.group_id,
                        enable_auto_commit=True,
                        auto_offset_reset="latest",
                        value_deserializer=lambda m: m.decode("utf-8", errors="ignore"),
                    )
                except Exception as e:
                    self.logger.warning(f"aiokafka Consumer 생성 중 경고: {e}")
                    return

                self._consumer = consumer
                self.logger.info(
                    f"Kafka 중지 리스너 시작 (topic={self.topic}, group_id={self.group_id}, job_id={self.job_id})"
                )
                try:
                    await consumer.start()
                    while not self._stop_event.is_set():
                        try:
                            msg = await consumer.getone()
                            if self._stop_event.is_set():
                                break
                            payload = msg.value
                            if not payload:
                                continue
                            matched = False
                            try:
                                data = json.loads(payload)
                                action = str(data.get("action", "")).lower()
                                msg_job_id = data.get("job_id")
                                if action == "stop" and (self.job_id is None or str(self.job_id) == str(msg_job_id)):
                                    matched = True
                            except Exception:
                                text = str(payload).lower()
                                if "stop" in text:
                                    if self.job_id is None or (self.job_id and str(self.job_id) in text):
                                        matched = True
                            if matched:
                                self.logger.info("Kafka로부터 중지 요청을 수신했습니다. 중지 플래그를 설정합니다.")
                                self._stop_requested.set()
                                break
                        except Exception as inner:
                            self.logger.warning(f"Kafka 폴링 중 경고: {inner}")
                            await asyncio.sleep(1.0)
                finally:
                    try:
                        await consumer.stop()
                    except Exception:
                        pass
                    self.logger.info("Kafka 중지 리스너를 종료했습니다.")

            loop.run_until_complete(_consume())

        self._thread = threading.Thread(target=_run, name="kafka-stop-listener", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        try:
            self._stop_event.set()
            if self._thread and self._thread.is_alive():
                self._thread.join(timeout=5)
        except Exception:
            pass

    def is_stop_requested(self) -> bool:
        return self._stop_requested.is_set()

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
    def get_target_modules(model, auto: bool = True):
        """LoRA 타겟 모듈을 반환 - auto=True이면 PEFT all-linear 자동 감지 사용"""
        if auto:
            return "all-linear"  # PEFT >= 0.13.0: 모든 Linear 레이어 자동 감지

        # auto=False: 아키텍처별 static map (하위 호환 fallback)
        model_name = model.__class__.__name__.lower()

        target_modules_map = {
            "gpt2":     ["c_attn", "c_proj"],
            "gptj":     ["c_attn", "c_proj"],
            "gpt_neo":  ["c_attn", "c_proj"],
            "gpt_neox": ["query_key_value", "dense"],
            "opt":      ["q_proj", "k_proj", "v_proj", "out_proj"],
            "bloom":    ["query_key_value", "dense"],
            "llama":    ["q_proj", "k_proj", "v_proj", "o_proj"],
            "llama2":   ["q_proj", "k_proj", "v_proj", "o_proj"],
            "qwen":     ["q_proj", "k_proj", "v_proj", "o_proj"],
            "deepseek-r1": ["q_proj", "k_proj", "v_proj", "o_proj"],
            "mpt":      ["q_proj", "k_proj", "v_proj", "o_proj"],
            "falcon":   ["q_proj", "k_proj", "v_proj", "out_proj"],
        }

        for keyword, modules in target_modules_map.items():
            if keyword in model_name:
                base_modules = modules.copy()
                break
        else:
            # 미지정 아키텍처 일반 규칙: 표준 프로젝션 레이어만 타겟
            base_modules = ["q_proj", "k_proj", "v_proj", "o_proj", "out_proj", "c_proj", "c_attn", "query_key_value", "dense"]

        # leaf Linear 모듈만 필터링 (컨테이너 제외)
        allowed = set()
        for name, module in model.named_modules():
            last = name.split(".")[-1]
            if last in base_modules and isinstance(module, nn.Linear):
                allowed.add(last)

        # 최소한의 보강: 아무것도 못 찾으면 Linear 중 proj 계열만
        if not allowed:
            for name, module in model.named_modules():
                if isinstance(module, nn.Linear):
                    last = name.split(".")[-1]
                    if any(tag in last for tag in ["q_proj", "k_proj", "v_proj", "o_proj", "out_proj", "c_proj", "query_key_value", "dense"]):
                        allowed.add(last)

        return sorted(allowed)


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
            DatasetManager.logger.info(f"[INFO] 디렉토리 기반 arrow 로드: {dataset_path}")
            return load_from_disk(dataset_path)

        ext = path.suffix.lower()
        loader_args = {"data_files": dataset_path}
        if split:
            loader_args["split"] = split

        if ext in [".json", ".jsonl"]:
            DatasetManager.logger.info(f"[INFO] JSON 파일 로드: {dataset_path}")
            return load_dataset("json", **loader_args)
        elif ext == ".csv":
            DatasetManager.logger.info(f"[INFO] CSV 파일 로드: {dataset_path}")
            return load_dataset("csv", **loader_args)
        else:
            raise ValueError(f"⚠️ 지원하지 않는 확장자: {ext}")

    @staticmethod
    def prepare_datasets(dataset_path: str, cutoff_length: int, tokenizer, dataset_format: str = "auto") -> Tuple[Dataset, Optional[Dataset]]:
        """데이터셋을 로드하고 전처리 - 토크나이징 및 train/validation 분할"""
        dataset = DatasetManager.load_dataset_by_path(dataset_path=dataset_path)

        # train/validation 분할 - validation이 있으면 validation 사용, 없으면 test 사용
        train_dataset = dataset['train']
        eval_dataset = dataset.get('validation', dataset.get('test'))

        # 데이터셋에 있는 split 종류 로그 출력
        available_splits = list(dataset.keys())
        DatasetManager.logger.info(f"📊 데이터셋에서 사용 가능한 split 종류: {available_splits}")
        DatasetManager.logger.info(f"📈 사용할 train split: train (샘플 수: {len(train_dataset)})")

        if eval_dataset is not None:
            eval_split_name = 'validation' if 'validation' in dataset else 'test'
            DatasetManager.logger.info(f"📉 사용할 evaluation split: {eval_split_name} (샘플 수: {len(eval_dataset)})")
        else:
            DatasetManager.logger.warning(f"⚠️ 경고: 데이터셋에 'validation' 또는 'test' 스플릿이 없습니다. "
                  f"현재 사용 가능한 스플릿: {available_splits}. "
                  f"평가 데이터셋 없이 학습을 진행합니다.")

        # 데이터셋 형식 자동 감지
        sample_columns = train_dataset.column_names
        if dataset_format == "auto":
            if "messages" in sample_columns or "conversations" in sample_columns:
                detected_format = "chat"
            elif "instruction" in sample_columns:
                detected_format = "instruction"
            else:
                detected_format = "text"
        else:
            detected_format = dataset_format
        DatasetManager.logger.info(f"📝 데이터셋 형식: {detected_format} (요청: {dataset_format})")

        # 토크나이징 함수 - 형식에 따라 분기
        def tokenize_function(examples):
            if detected_format == "chat":
                # messages/conversations 컬럼 → chat template 적용
                col = "messages" if "messages" in examples else "conversations"
                texts = [
                    tokenizer.apply_chat_template(msgs, tokenize=False, add_generation_prompt=False)
                    if hasattr(tokenizer, "apply_chat_template") and tokenizer.chat_template
                    else " ".join(m.get("content", "") for m in msgs)
                    for msgs in examples[col]
                ]
            elif detected_format == "instruction":
                # instruction/input/output 컬럼 → 프롬프트 조합
                instructions = examples.get("instruction", [""] * len(examples["instruction"]))
                inputs = examples.get("input", [""] * len(instructions))
                outputs = examples.get("output", [""] * len(instructions))
                texts = [
                    f"{inst}\n{inp}\n{out}".strip()
                    for inst, inp, out in zip(instructions, inputs, outputs)
                ]
            else:
                # 기본: text 컬럼
                texts = examples["text"]

            tok = tokenizer(
                texts,
                padding="max_length",
                truncation=True,
                max_length=cutoff_length,
                return_attention_mask=True
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
            "fp16", "bf16", "weight_decay", "overwrite_output_dir", "output_dir", "logging_dir",
            "remove_unused_columns", "save_total_limit", "save_strategy", "logging_strategy",
            "eval_strategy", "eval_steps", "logging_steps", "save_steps", "prediction_loss_only",
            "dataloader_pin_memory", "dataloader_num_workers"
        }

    @staticmethod
    def build_deepspeed_config(use_bf16: bool, zero_stage: int = 1) -> dict:
        """DeepSpeed 설정을 동적으로 생성 - precision과 ZeRO stage에 따라 fp16/bf16 자동 전환"""
        return {
            "train_batch_size": "auto",
            "train_micro_batch_size_per_gpu": "auto",
            "gradient_accumulation_steps": "auto",
            "gradient_clipping": "auto",
            "zero_allow_untested_optimizer": True,
            "fp16": {
                "enabled": not use_bf16,
                "loss_scale": 0,
                "loss_scale_window": 1000,
                "initial_scale_power": 16,
                "hysteresis": 2,
                "min_loss_scale": 1,
            },
            "bf16": {
                "enabled": use_bf16,
            },
            "zero_optimization": {
                "stage": zero_stage,
                "allgather_partitions": True,
                "allgather_bucket_size": 5e8,
                "overlap_comm": True,
                "reduce_scatter": True,
                "reduce_bucket_size": 5e8,
                "contiguous_gradients": True,
                "round_robin_gradients": True,
            },
        }

    def create_training_arguments(self, args: FineTuningArgs, remove_unused_columns: bool, use_bf16: bool = False) -> TrainingArguments:
        """TrainingArguments 생성 - 사용자 설정 파일 또는 동적 DeepSpeed 설정 사용"""
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
            # DeepSpeed config 동적 생성 (precision + ZeRO stage 반영)
            ds_config = TrainingManager.build_deepspeed_config(
                use_bf16=use_bf16, zero_stage=args.zero_stage
            )
            self.logger.info(f"DeepSpeed config 동적 생성: precision={'bf16' if use_bf16 else 'fp16'}, ZeRO stage={args.zero_stage}")
            return TrainingArguments(
                learning_rate=args.learning_rate,
                gradient_accumulation_steps=args.gradient_accumulation_steps,
                num_train_epochs=args.num_train_epochs,
                warmup_steps=args.warmup_steps,
                deepspeed=ds_config,
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
                   training_args: TrainingArguments, tokenizer, data_collator=None, stop_signal_manager: Optional[object] = None):
        """모델 학습 실행 - Trainer를 사용한 실제 학습 프로세스"""
        # transformers 4.52.4 호환성을 위한 설정 - DeepSpeed와의 호환성 문제 해결
        training_args.dataloader_pin_memory = False
        training_args.dataloader_num_workers = 0
        
        # eval_dataset이 None인 경우 평가 관련 설정 비활성화
        if eval_dataset is None:
            training_args.eval_strategy = "no"
            training_args.eval_steps = None
            self.logger.info("⚠️ 평가 데이터셋이 없어 평가를 비활성화합니다.")
        
        callbacks = [SavePeftAdapterCallback(save_directory=training_args.output_dir)]
        if stop_signal_manager is not None:
            callbacks.append(KafkaStopTrainingCallback(stop_signal_manager=stop_signal_manager, logger=self.logger))

        trainer = Trainer(
            model=model,
            args=training_args,
            train_dataset=train_dataset,
            eval_dataset=eval_dataset,
            tokenizer=tokenizer,
            optimizers=(None, None),  # DeepSpeed가 optimizer를 관리하므로 None
            data_collator=data_collator,
            callbacks=callbacks
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

    def _is_lora_checkpoint_dir(self, directory: Path) -> bool:
        """
        LoRA 체크포인트 디렉토리 여부를 판단합니다.

        - adapter_config.json이 존재하고,
        - adapter_model.bin 또는 adapter_model*.safetensors 가 존재하면 LoRA 체크포인트로 간주합니다.

        Args:
            directory (Path): 확인할 디렉토리 경로

        Returns:
            bool: LoRA 체크포인트 디렉토리이면 True, 아니면 False
        """
        try:
            if directory is None or not directory.exists() or not directory.is_dir():
                return False

            config_path = directory / "adapter_config.json"
            adapter_bin = directory / "adapter_model.bin"
            has_safetensors = any(directory.glob("adapter_model*.safetensors"))

            return config_path.exists() and (adapter_bin.exists() or has_safetensors)
        except Exception as e:
            self.logger.warning(f"LoRA 체크포인트 판별 중 오류 발생 (directory: {directory}): {e}")
            return False

    def _get_base_model_path_from_adapter(self, adapter_dir: Path) -> Optional[Path]:
        """
        어댑터 디렉토리의 adapter_config.json에서 base_model_name_or_path를 읽어
        로컬 경로가 유효하면 해당 경로를 반환합니다.

        Args:
            adapter_dir (Path): LoRA 어댑터가 위치한 디렉토리 경로

        Returns:
            Optional[Path]: 로컬에서 확인 가능한 base 모델 경로, 없으면 None
        """
        try:
            config_path = adapter_dir / "adapter_config.json"
            if not config_path.exists():
                return None

            with open(config_path, "r", encoding="utf-8") as fp:
                cfg = json.load(fp)

            base_model_str = cfg.get("base_model_name_or_path")
            if not base_model_str:
                return None

            base_path = Path(base_model_str)
            return base_path if base_path.exists() else None
        except Exception as e:
            self.logger.warning(f"adapter_config.json 파싱 중 오류 발생 (adapter_dir: {adapter_dir}): {e}")
            return None

    def load_tokenizer(self, model_path: Path):
        """토크나이저 로드 - pad_token이 없는 경우에만 EOS 토큰으로 설정"""
        try:
            tokenizer = AutoTokenizer.from_pretrained(str(model_path), trust_remote_code=True)
            if tokenizer.pad_token is None or tokenizer.pad_token_id is None:
                tokenizer.pad_token = tokenizer.eos_token
                tokenizer.pad_token_id = tokenizer.eos_token_id
                self.logger.info("pad_token 미정의 → eos_token으로 설정")
            else:
                self.logger.info(f"pad_token 사용: {tokenizer.pad_token}")
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
            # LoRA 체크포인트 디렉토리 판별 및 base 모델 경로로 치환
            # - 입력된 model_path가 어댑터만 포함하는 LoRA 체크포인트라면
            #   base 모델이 위치한 경로(/source_model)를 사용하도록 전환합니다.
            if self._is_lora_checkpoint_dir(model_path):
                # 1순위: 사전 마운트된 /source_model 사용
                if self.path_manager.lora_source_model_path.exists():
                    model_path = self.path_manager.lora_source_model_path
                    is_source_model_lora = True
                else:
                    # 2순위: adapter_config.json의 base_model_name_or_path가 로컬 경로이면 사용
                    resolved_base = self._get_base_model_path_from_adapter(model_path)
                    if resolved_base is not None:
                        model_path = resolved_base
                        is_source_model_lora = True
                    else:
                        # base 모델 경로를 찾지 못하면 안전하게 종료
                        raise FileNotFoundError(
                            "LoRA 체크포인트가 감지되었으나 base 모델 경로(/source_model 또는 adapter_config의 로컬 경로)를 찾지 못했습니다."
                        )

            # 기본 경로 결정 (위 LoRA 체크 결과를 우선 적용)
            # if not is_source_model_lora:
            #     if self.path_manager.lora_source_model_path.exists():
            #         model_path = self.path_manager.lora_source_model_path
            #         is_source_model_lora = True
            #     else:
            #         model_path = self.path_manager.model_path

            # 모델 로드 - 8비트 양자화 옵션 지원
            # torch_dtype="auto": 모델 config의 네이티브 dtype(fp16/bf16)으로 로딩하여 VRAM 절약
            if args.load_in_8bit:
                quantization_config = BitsAndBytesConfig(load_in_8bit=True)
                model = AutoModelForCausalLM.from_pretrained(
                    str(model_path),
                    quantization_config=quantization_config,
                    torch_dtype="auto",
                    trust_remote_code=True
                )
            else:
                model = AutoModelForCausalLM.from_pretrained(
                    str(model_path),
                    torch_dtype="auto",
                    trust_remote_code=True
                )

            # LoRA 설정 - 기존 LoRA 모델 병합 또는 새 LoRA 적용
            if args.used_lora or is_source_model_lora:
                if is_source_model_lora:
                    # 기존 LoRA 모델을 로드하고 병합
                    model = PeftModel.from_pretrained(model, str(self.path_manager.model_path))
                    model = model.merge_and_unload()  # LoRA 가중치를 원본 모델에 병합
                    # if self.pod_index == 0:
                    #     # 소스 모델을 출력 디렉토리로 복사
                    #     FileManager.copy_dir_contents(
                    #         self.path_manager.lora_source_model_path, 
                    #         self.path_manager.output_path / "source_model"
                    #     )
                    remove_unused_columns = False  # 병합된 모델은 컬럼 제거 불필요
                # else:
                    # if self.pod_index == 0:
                    #     # 원본 모델을 출력 디렉토리로 복사
                    #     FileManager.copy_dir_contents(
                    #         self.path_manager.model_path, 
                    #         self.path_manager.output_path / "source_model"
                    #     )
                

                # 모델 타입에 따른 LoRA 타겟 모듈 설정
                model_type = str(getattr(model.config, "model_type", "")).lower()
                if model_type == "gpt_oss" or "gptoss" in model.__class__.__name__.lower():
                    target_modules = ["q_proj", "k_proj", "v_proj", "o_proj"]
                else:
                    target_modules = ModelManager.get_target_modules(
                        model, auto=bool(args.auto_target_modules)
                    )
                lora_config = LoraConfig(
                    r=8,  # LoRA 랭크 (적응 가능한 파라미터 수)
                    lora_alpha=16,  # LoRA 스케일링 팩터
                    lora_dropout=0.05,  # LoRA 드롭아웃
                    target_modules=target_modules  # LoRA를 적용할 모듈들
                )
                model = get_peft_model(model, lora_config)
                # LoRA는 대부분 파라미터를 frozen → gradient checkpointing과 호환되려면 입력에 requires_grad 필요
                model.enable_input_require_grads()
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

            # Precision 자동 감지 및 TrainingConfig 업데이트
            if args.precision == "auto":
                model_dtype = getattr(model.config, "torch_dtype", None)
                use_bf16 = (model_dtype == torch.bfloat16)
            else:
                use_bf16 = (args.precision == "bf16")
            self.training_manager.training_config.bf16 = use_bf16
            self.training_manager.training_config.fp16 = not use_bf16
            self.logger.info(f"학습 정밀도: {'BF16' if use_bf16 else 'FP16'} (precision={args.precision}, model_dtype={getattr(model.config, 'torch_dtype', 'unknown')})")

            if args.config_path:
                # 사용자 정의 설정 파일 로드
                config_path = self.path_manager.config_path / args.config_path
                with open(config_path, "r", encoding="utf-8") as file:
                    config = json.load(file)
                args.cutoff_length = config.get("cutoff_length", args.cutoff_length)


            # 학습 인자 설정 (사용자 설정 또는 기본값)
            training_args = self.training_manager.create_training_arguments(args, remove_unused_columns, use_bf16=use_bf16)
            self.logger.info("TRAINING ARGUMENT LOAD SUCCESS")

            # 데이터셋 준비 (토크나이징 및 train/validation 분할)
            train_dataset, eval_dataset = DatasetManager.prepare_datasets(
                args.dataset_path, args.cutoff_length, tokenizer, dataset_format=args.dataset_format
            )
            self.logger.info("DATASET LOAD SUCCESS")

            # steps per epoch 계산 (분산 학습 고려)
            steps_per_epoch = self.training_manager.calculate_steps_per_epoch(training_args, train_dataset)
            # 오직 primary 프로세스(랭크0/로컬랭크0) && 첫 번째 파드에서만 DB 반영
            if (int(os.getenv("RANK", "0")) == 0) and (int(os.getenv("LOCAL_RANK", "0")) == 0) and (self.pod_index == 0):
                update_steps_per_epoch(steps_per_epoch=steps_per_epoch)

            self.logger.info("="*20)
            self.logger.info("TRAIN SETTING SUCCESS")
            self.logger.info("="*20)

            # 데이터 콜레이터 설정 (언어 모델링용)
            data_collator = DataCollatorForLanguageModeling(tokenizer=tokenizer, mlm=False)

            # Kafka 중지 리스너 시작 (환경 변수 기반)
            stop_manager = None
            try:
                env_enable = os.getenv("KAFKA_ENABLE_STOP_LISTENER")
                env_bootstrap = os.getenv("KAFKA_BOOTSTRAP_SERVERS")
                env_topic = os.getenv("KAFKA_TOPIC")
                env_group = os.getenv("KAFKA_GROUP_ID")
                env_job_id = os.getenv("STOP_JOB_ID") or os.getenv("JOB_ID")

                def _to_bool(s):
                    if s is None:
                        return False
                    v = str(s).strip().lower()
                    return v in ("1", "true", "yes", "y", "on")

                enable_listener = _to_bool(env_enable)
                if enable_listener:
                    stop_manager = StopSignalManager(
                        enable_listener=True,
                        bootstrap_servers=env_bootstrap,
                        topic=env_topic,
                        group_id=env_group,
                        job_id=env_job_id,
                        logger=self.logger,
                    )
            except Exception as e:
                self.logger.warning(f"중지 리스너 초기화 경고: {e}")

            if stop_manager is not None:
                stop_manager.start()

            # 모델 학습 실행 (중지 콜백 등록)
            trainer = self.training_manager.train_model(
                model, train_dataset, eval_dataset, training_args, tokenizer, data_collator, stop_signal_manager=stop_manager
            )

            # 결과 저장 (첫 번째 pod의 primary 프로세스만 실행)
            if self.pod_index == 0 and (int(os.getenv("RANK", "0")) == 0) and (int(os.getenv("LOCAL_RANK", "0")) == 0):
                trainer.save_model(training_args.output_dir)  # 최종 모델 저장
                # tokenizer.json 손상 방지를 위해 토크나이저를 명시적으로 저장
                tokenizer.save_pretrained(training_args.output_dir)
                FileManager.delete_checkpoint_dir(self.path_manager.output_path)  # 체크포인트 정리
                # FileManager.clear_dir_contents(self.path_manager.model_path)  # 기존 모델 정리
                # FileManager.copy_dir_contents(self.path_manager.output_path, self.path_manager.model_path)  # 새 모델 복사

            self.logger.info("="*20)
            self.logger.info("FINE TUNING SUCCESS AND MODEL SAVE SUCCESS")
            self.logger.info("="*20)

        except Exception as e:
            traceback.print_exc()
            self.logger.error(f"파인튜닝 중 오류 발생: {e}")
            # 오직 primary 프로세스(랭크0/로컬랭크0) && 첫 번째 파드에서만 오류 상태 업데이트
            if (int(os.getenv("RANK", "0")) == 0) and (int(os.getenv("LOCAL_RANK", "0")) == 0) and (self.pod_index == 0):
                update_finetuning_error_status()
            raise e
        finally:
            # Kafka 리스너 종료
            try:
                if 'stop_manager' in locals() and stop_manager is not None:
                    stop_manager.stop()
            except Exception:
                pass


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
    parser.add_argument("--precision", type=str, default="auto",
                       help="학습 정밀도: auto(모델 dtype 자동 감지) | fp16 | bf16")
    parser.add_argument("--auto_target_modules", type=int, default=1,
                       help="LoRA 타겟 모듈 자동 감지: 1=auto(all-linear), 0=static map")
    parser.add_argument("--dataset_format", type=str, default="auto",
                       help="데이터셋 형식: auto | text | chat | instruction")
    parser.add_argument("--zero_stage", type=int, default=1,
                       help="DeepSpeed ZeRO stage: 1, 2, 3 (기본값: 1)")
    # Kafka 관련 CLI 인자는 제거하고 환경 변수를 사용합니다.

    # args = parser.parse_args()
    # pod_index = int(os.getenv("POD_INDEX", 0))
    
    args = parser.parse_args()
    pod_index = int(os.getenv("POD_INDEX", 0))
    is_primary_proc = (int(os.getenv("RANK", "0")) == 0) and (int(os.getenv("LOCAL_RANK", str(args.local_rank))) == 0)
    
    # 오직 primary 프로세스(랭크0/로컬랭크0) && 첫 번째 파드에서만 초기화 작업 수행
    if pod_index == 0 and is_primary_proc:
        update_finetuning_running_status()  # 파인튜닝 상태 업데이트
        path_manager = PathManager()
        # FileManager.clear_dir_contents(path_manager.output_path)  # 출력 디렉토리 정리
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
        deepspeed=args.deepspeed,
        precision=args.precision,
        auto_target_modules=args.auto_target_modules,
        dataset_format=args.dataset_format,
        zero_stage=args.zero_stage,
    )

    # 파인튜닝 엔진 실행
    engine = FineTuningEngine()
    engine.logger.info(fine_tuning_args)
    
    try:
        engine.fine_tuning(fine_tuning_args)
    except Exception:
        if pod_index == 0 and is_primary_proc:
            update_finetuning_error_status()  # 오류 상태 업데이트


if __name__ == "__main__":
    main()


"""
================================================================================
📋 전체 파인튜닝 워크플로우 요약 (업데이트)
================================================================================

🎯 목적: Hugging Face 기반 언어 모델의 효율적인 파인튜닝 엔진

🔄 전체 프로세스:

1️⃣ 초기화 (main)
   ├── 명령행 인자 파싱 (분산, 데이터셋, LoRA, 8bit, DeepSpeed)
   ├── POD_INDEX 확인 (분산 환경 식별)
   └── 첫 번째 pod 전용 초기화
       ├── 파인튜닝 실행 상태 DB 업데이트
       └── 로그 디렉토리 정리 (/logs)

2️⃣ 경로/환경 (PathManager)
   ├── 모델 경로: /source_model 존재 시 우선, 없으면 /model
   └── 출력/로그 디렉토리 생성 (/model, /logs)

3️⃣ 토크나이저 (load_tokenizer)
   ├── AutoTokenizer.from_pretrained 로드
   └── pad_token 을 eos_token 으로 설정 (언어 모델링용)

4️⃣ 모델 로드/LoRA (load_model)
   ├── LoRA 체크포인트 디렉토리 입력 시 base 모델 경로 자동 치환
   │   └── /source_model 또는 adapter_config.json 의 로컬 경로 사용
   ├── 8bit 양자화 옵션 지원 (BitsAndBytes)
   ├── 기존 LoRA 병합 지원
   │   └── PeftModel.from_pretrained(..., /model) → merge_and_unload()
   └── 새 LoRA 적용 가능 (r=8, alpha=16, dropout=0.05, target_modules 자동 탐지)

5️⃣ 학습 인자 (create_training_arguments)
   ├── 사용자 JSON 제공 시 로드, 중복/불필요 키 제거
   └── 미제공 시 기본 DeepSpeed 설정 사용

6️⃣ 데이터셋 (prepare_datasets)
   ├── 디렉토리(arrow)/JSON(JSONL)/CSV 자동 로드
   ├── train 사용, validation 없으면 test 사용
   └── 평가 스플릿 없으면 경고 로그 후 평가 비활성화로 학습 진행

7️⃣ 스텝 계산 (calculate_steps_per_epoch)
   ├── world_size, per_device_batch_size, gradient_accumulation 고려
   └── steps_per_epoch 계산 후 DB 업데이트

8️⃣ 학습 실행 (train_model)
   ├── DeepSpeed 호환 설정 (pin_memory=False, num_workers=0)
   ├── DataCollatorForLanguageModeling(mlm=False)
   ├── SavePeftAdapterCallback 등록
   ├── KafkaStopTrainingCallback (환경 변수로 리스너 활성 시) 등록
   └── trainer.train()

9️⃣ 저장/정리 (첫 번째 pod)
   └── 최종 모델 저장 및 checkpoint-* 디렉토리 정리

🔧 특징
- 분산 학습(DeepSpeed), LoRA 자동 타겟 탐지/병합, 8bit 옵션
- 환경 변수 기반 Kafka 중지 리스너 지원: KAFKA_ENABLE_STOP_LISTENER, KAFKA_BOOTSTRAP_SERVERS,
  KAFKA_TOPIC, KAFKA_GROUP_ID, STOP_JOB_ID/JOB_ID
- 견고한 로깅과 단계별 예외 처리 및 DB 상태 업데이트

🧪 사용 시나리오
- 단일 GPU: used_dist=0, used_lora=1
- 다중 GPU: used_dist=1, num_gpus=N
- 기존 LoRA 연속 학습: base 모델 로드 후 어댑터 병합
- 메모리 제약: load_in_8bit=1, gradient_accumulation_steps=N

================================================================================
"""