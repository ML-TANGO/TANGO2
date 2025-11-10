import os
import torch
from datasets import load_dataset
from transformers import (
    AutoModelForSequenceClassification,
    AutoModelForImageClassification,
    AutoTokenizer,
    AutoFeatureExtractor,
    TrainingArguments,
    Trainer,
    YolosFeatureExtractor, 
    YolosForObjectDetection
)
from accelerate import Accelerator
from huggingface_hub import login, snapshot_download
# Hugging Face 로그인 (토큰 기반)


def train_model(model_name: str, data_path: str, output_dir: str = "./output", task_type: str = "text-classification"):
    """
    Hugging Face 모델 레포 이름과 데이터 경로를 입력받아 자동으로 모델 학습을 진행합니다.
    - model_name: Hugging Face 모델 레포 이름 (예: bert-base-uncased, google/vit-base-patch16-224 등)
    - data_path: 데이터 경로 (CSV, JSON 또는 Hugging Face dataset 이름)
    - output_dir: 모델 학습 결과가 저장될 디렉토리
    - task_type: 'text-classification' 또는 'image-classification' 등 작업 유형
    """
    # 1. Accelerator 초기화
    accelerator = Accelerator()
    print("Accelerator initialized with device:", accelerator.device)
    
    # 2. 모델 불러오기 (Text 또는 Vision 자동 감지)
    login(token=token, add_to_git_credential=True)
    if task_type == "text-classification":
        print("Loading a text classification model...")
        model = AutoModelForSequenceClassification.from_pretrained(model_name, num_labels=2)
        tokenizer = AutoTokenizer.from_pretrained(model_name)
    elif task_type == "image-classification":
        print("Loading an image classification model...")
        model = AutoModelForImageClassification.from_pretrained(model_name)
        feature_extractor = AutoFeatureExtractor.from_pretrained(model_name)
    else:
        raise ValueError("Unsupported task type. Use 'text-classification' or 'image-classification'.")

    # 3. 데이터셋 불러오기
    if os.path.exists(data_path):  # 로컬 파일 (CSV or JSON)
        print("Loading local dataset from:", data_path)
        dataset = load_dataset("csv", data_files={"train": data_path})
    else:  # Hugging Face 데이터셋
        print("Loading Hugging Face dataset:", data_path)
        dataset = load_dataset(data_path)

    # 데이터 전처리
    def preprocess_text(examples):
        return tokenizer(examples['text'], truncation=True, padding='max_length')

    def preprocess_image(examples):
        return feature_extractor(examples['image'], return_tensors="pt")

    if task_type == "text-classification":
        dataset = dataset.map(preprocess_text, batched=True)
    elif task_type == "image-classification":
        dataset = dataset.map(preprocess_image)

    # 4. TrainingArguments 설정
    training_args = TrainingArguments(
        output_dir=output_dir,
        per_device_train_batch_size=8,
        num_train_epochs=3,
        evaluation_strategy="no",
        save_strategy="epoch",
        logging_dir=f"{output_dir}/logs",
        report_to="none",
        deepspeed="ds_config.json"  # DeepSpeed 설정 JSON 파일 경로
    )

    # 5. Trainer 설정 및 학습 시작
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=dataset["train"],
        tokenizer=tokenizer if task_type == "text-classification" else None,
    )

    # Accelerator와 함께 학습 실행
    model, trainer = accelerator.prepare(model, trainer)
    print("Training started...")
    trainer.train()

    print("Training completed. Model saved to:", output_dir)

# 사용 예시
if __name__ == "__main__":
    train_model(
        model_name="hustvl/yolos-small",           # NLP 모델 예시
        data_path="./data/text_dataset.csv",     # 로컬 CSV 데이터 경로
        output_dir="./output",
        task_type="text-classification"          # 작업 유형 ('text-classification' or 'image-classification')
    )
