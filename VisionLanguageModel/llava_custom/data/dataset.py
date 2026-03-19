import os
import copy
import json
import torch
from torch.utils.data import Dataset
from PIL import Image
from llava_custom.constants import IGNORE_INDEX, IMAGE_TOKEN_INDEX, DEFAULT_IMAGE_TOKEN

def preprocess_llama3(sources, tokenizer):
    """
    - Llama-3.1 Instruct 템플릿에 맞추어 대화를 토크나이징하고 라벨 생성
    """
    try:
        # Llama-3 특수 토큰
        BOS = "<|begin_of_text|>"
        USER_HEADER = "<|start_header_id|>user<|end_header_id|>\n\n"
        ASSISTANT_HEADER = "<|start_header_id|>assistant<|end_header_id|>\n\n"
        EOT = "<|eot_id|>"

        input_ids_list = []
        labels_list = []

        # Llama-3 특수 토큰 인코딩
        def _encode(text):
            try:
                return tokenizer.encode(text, add_special_tokens=False, allowed_special="all")
            except:
                return tokenizer.encode(text, add_special_tokens=False)

        for source in sources:
            input_ids = _encode(BOS) if getattr(tokenizer, 'bos_token', None) else []
            labels = [IGNORE_INDEX] * len(input_ids)

            for sentence in source:
                role = sentence["from"]
                value = sentence["value"]

                if role == "human":
                    text = USER_HEADER + value + EOT
                    parts = text.split(DEFAULT_IMAGE_TOKEN)
                    for i, part in enumerate(parts):
                        if part:
                            tokens = _encode(part)
                            input_ids.extend(tokens)
                            labels.extend([IGNORE_INDEX] * len(tokens))
                        if i < len(parts) - 1:
                            input_ids.append(IMAGE_TOKEN_INDEX)
                            labels.append(IGNORE_INDEX)
                elif role == "gpt":
                    text = ASSISTANT_HEADER + value + EOT
                    tokens = _encode(text)
                    header_tokens = _encode(ASSISTANT_HEADER)
                    
                    input_ids.extend(tokens)
                    labels.extend([IGNORE_INDEX] * len(header_tokens) + tokens[len(header_tokens):])
                else:
                    raise ValueError(f"알 수 없는 역할: {role}")

            input_ids_list.append(torch.tensor(input_ids, dtype=torch.long))
            labels_list.append(torch.tensor(labels, dtype=torch.long))

        return dict(
            input_ids=input_ids_list,
            labels=labels_list,
        )
    except Exception as e:
        raise RuntimeError(f"데이터 전처리 실패: {e}")


class LazySupervisedDataset(Dataset):
    """
    - 메모리 효율성을 위한 지연 로딩 기반 학습 데이터셋
    """
    def __init__(self, data_path, tokenizer, data_args):
        super(LazySupervisedDataset, self).__init__()
        try:
            self.tokenizer = tokenizer
            self.data_args = data_args
            self.list_data_dict = json.load(open(data_path, "r"))
        except Exception as e:
            raise RuntimeError(f"데이터셋 로드 실패: {e}")

    def __len__(self):
        return len(self.list_data_dict)

    def __getitem__(self, i):
        """
        - 단일 데이터 샘플과 이미지를 반환
        """
        try:
            sources = self.list_data_dict[i]
            if isinstance(i, int):
                sources = [sources]

            conversations = [copy.deepcopy(s["conversations"]) for s in sources]
            data_dict = preprocess_llama3(conversations, self.tokenizer)

            data_dict = dict(input_ids=data_dict["input_ids"][0], labels=data_dict["labels"][0])
            
            # - 이미지 처리
            image_file = self.list_data_dict[i].get("image")
            if image_file and hasattr(self.data_args, 'image_folder'):
                image_folder = self.data_args.image_folder
                processor = getattr(self.data_args, 'image_processor', None)
                if processor is None:
                    raise ValueError("image_processor 가 정의되지 않았습니다.")
                
                image_path = os.path.join(image_folder, image_file)
                image = Image.open(image_path).convert('RGB')
                
                image_tensor = processor.preprocess(image, return_tensors='pt')['pixel_values'][0]
                data_dict['image'] = image_tensor
            
            return data_dict
        except Exception as e:
            raise RuntimeError(f"__getitem__ 실행 중 에러: {e}")


class DataCollatorForSupervisedDataset(object):
    """
    - 미니배치 구성을 위한 데이터 콜레이터
    - 패딩 토큰을 추가하여 시퀀스 길이 일치
    """
    def __init__(self, tokenizer):
        self.tokenizer = tokenizer

    def __call__(self, instances):
        try:
            input_ids = [instance['input_ids'] for instance in instances]
            labels = [instance['labels'] for instance in instances]
            
            input_ids = torch.nn.utils.rnn.pad_sequence(
                input_ids,
                batch_first=True,
                padding_value=self.tokenizer.pad_token_id
            )
            labels = torch.nn.utils.rnn.pad_sequence(
                labels,
                batch_first=True,
                padding_value=IGNORE_INDEX
            )
            
            batch = dict(
                input_ids=input_ids,
                labels=labels,
                attention_mask=input_ids.ne(self.tokenizer.pad_token_id),
            )
            
            if 'image' in instances[0]:
                images = [instance['image'] for instance in instances]
                batch['images'] = torch.stack(images)
                
            return batch
        except Exception as e:
            raise RuntimeError(f"Data collator 에러: {e}")

def make_supervised_data_module(tokenizer, data_args):
    """
    - 학습용 데이터 모듈 생성
    """
    try:
        train_dataset = LazySupervisedDataset(tokenizer=tokenizer, data_path=data_args.data_path, data_args=data_args)
        data_collator = DataCollatorForSupervisedDataset(tokenizer=tokenizer)
        return dict(train_dataset=train_dataset, eval_dataset=None, data_collator=data_collator)
    except Exception as e:
        raise RuntimeError(f"데이터 모듈 생성 실패: {e}")
