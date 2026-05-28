import torch
import os, glob, csv, re
from PIL import Image
import torch.utils.data as d
import torch.nn.functional as F
from transformers import AutoProcessor
from overrides import overrides

class BaseDataset(d.Dataset):
    def __init__(self, base_data_path: str, model_id: str):
        super().__init__()
        
        self.processed_dataset = self._load_data(base_data_path)

        self.processor = AutoProcessor.from_pretrained(model_id, padding_side="left")
    
    def _load_data(self, base_data_path: str) -> list:
        def extract_number(name):
            match = re.search(r'\d+', name)
            return int(match.group()) if match else float('inf')
        datasets = []
        directories = sorted(os.listdir(base_data_path), key=extract_number)
        for loc in directories: # base_data_path는 '20250922'부터 시작
            if os.path.isdir(f'{base_data_path}/{loc}'):
                for f in glob.glob(f'{base_data_path}/{loc}/**/**.*', recursive=True):
                    if f.endswith('.csv'):
                        with open(f, 'r', encoding='utf-8-sig') as d:
                            if 'input' in f:
                                input_data = []
                                for r in csv.DictReader(d):
                                    input_data.append(r)
                            elif 'output' in f:
                                output_data = []
                                for r in csv.DictReader(d):
                                    output_data.append(r)
                    elif f.endswith('.png') and 'ImageWithBBox' in f:
                        bbox_full_path = f
                    elif f.endswith('.png'):
                        norm_full_path = f
                datasets.append({'input': input_data, 'output': output_data, 'bbox_image_path': bbox_full_path, 'image_path': norm_full_path})
        processed_dataset = self._processing_data(datasets)

        return processed_dataset

    def _processing_data(self, datasets: list) -> list:
        processed_dataset = []
        for idx, dataset in enumerate(datasets):
            input_csv = dataset['input']
            output_csv = dataset['output']
            for out in output_csv:
                sensor_data = []
                for inp in input_csv:
                    if out['file_name'] == inp['file_name']:
                        sensor_data.append(inp)
                processed_dataset.append({
                            'frame_id' : out['file_name'],
                            'dataset_id' : idx + 1,
                            'sensor_data': sensor_data, 
                            'pseudo_label': out['text'], 
                            'bbox_image_path': dataset['bbox_image_path'],
                            'image_path': dataset['image_path'],
                        })
        return processed_dataset

    def __len__(self):
        return len(self.processed_dataset)

    def collate_fn(self, batchs): # 수정 필요
        
        xs = [b['input_ids'] for b in batchs]
        ys = [b['labels'] for b in batchs]

        max_len = max(len(tokens) for tokens in xs + ys)

        attention_mask = torch.stack([torch.tensor([0 if i <= max_len - len(tokens) - 1 else 1 for i in range(max_len)]) for tokens in xs])
        xs = torch.stack([F.pad(tokens, (max_len - len(tokens), 0), value=self.tokenizer.pad_token_id) for tokens in xs])
        ys = torch.stack([F.pad(tokens, (max_len - len(tokens), 0), value=self.tokenizer.pad_token_id) for tokens in ys])

        return {'input_ids': xs, 'labels': ys, 'attention_mask': attention_mask}

class PromptingDataset(BaseDataset):
    def __getitem__(self, index: int):
        for s_data in self.processed_dataset[index]['sensor_data']:
            sensor_info = (
                f"- ship_id: {s_data['ship_id']}, my_ship: {s_data['my_ship']}, ship_type: {s_data['ship_type']}, "
                f"length: {s_data['length']}, width: {s_data['width']}, draft: {s_data['draft']}, "
                f"latitude: {s_data['latitude']}, longitude: {s_data['longitude']}, knot: {s_data['knot']}, "
                f"heading: {s_data['heading']}, bbox_x: {s_data['bbox_x']}, bbox_y: {s_data['bbox_y']}, "
                f"bbox_width: {s_data['bbox_width']}, bbox_height: {s_data['bbox_height']}\n"
            )
            if 'sensor_text' in locals():
                sensor_text += sensor_info
            else:
                sensor_text = sensor_info
        messages = [
            {
                'role': 'system',
                'content': [
                    {
                        'type': 'text',
                        'text': (
                            '당신은 해상 상황을 분석하는 전문가입니다.\n'
                            '주어진 이미지는 해상 위의 여러 선박을 포함하고 있으며, 각 선박에 대한 센서 데이터가 함께 제공됩니다.\n\n'
                            '센서 데이터 필드는 다음과 같습니다:\n'
                            '- ship_id: 선박 고유 ID\n'
                            '- my_ship: 자신의 선박 여부 (1이면 자신의 선박에 대한 센서 데이터, 0이면 다른 선박에 대한 센서 데이터)\n'
                            '- ship_type: 선박 종류\n'
                            '- length, width, draft: 선박의 크기 및 수면 아래 잠긴 깊이\n'
                            '- latitude, longitude: 선박의 위도 및 경도\n'
                            '- knot: 선박 속력 (노트 단위)\n'
                            '- heading: 해당 선박의 진행 방향 (방위각을 나타내며, True North를 기준으로 시계방향으로 측정한 각도)\n'
                            '- bbox_x, bbox_y, bbox_width, bbox_height: 이미지 상의 바운딩박스 좌표\n\n'
                            '---당신의 역할---\n\n'
                            '- 제공된 출력형식에 따라 제공된 해상 상황 묘사와 유사한 형태로 항해사가 사용하는 한국어 어휘를 사용하여 답변하세요.\n'
                            '- 최대한 불필요한 서술은 배제하고 항해사 입장에서 효과적으로 해상 컨텍스트를 이해할 수 있도록 항해 상황을 묘사하세요.\n'
                            '- 아래의 \"기존 묘사문\"을 검토하고 질문에 답을 하세요.\n'
                            '- 이미지 및 센서 데이터와 비교하여 잘못된 정보, 누락된 정보, 혹은 사실과 다른 표현을 찾으세요.\n'
                            '- 이미지 및 센서 데이터에 기반하여 정확한 해상 상황 묘사로 수정하세요.\n'
                            '- 센서에 감지된 선박들이 이미지에서 명확히 식별되는지 여부를 고려하세요.\n'
                            '- 주변 선박들의 위치 묘사는 자신의 선박을 기준으로 하여 Clock position을 통해 상대적으로 나타내세요.\n (예: \"12시 방향에 어선 한 척이 접근 중이다.\", \"2시 방향에 대형 선박이 정박해 있다.\")\n'
                            '- 수정된 문장은 객관적이고 이미지와 센서 데이터에 근거한 사실 중심 서술이어야 합니다. (예: \"11시 방향에 어선 한 척이 3.2 knot로 접근 중이다.\", \"역광으로 인해 선박 식별이 어렵다.\")\n\n'
                            '---*Reasoning Process: Use step-by-step Q&A reasoning*---\n\n'
                            'Q1: 주어진 묘사문에서 이미지 및 센서에서 식별되는 자신의 선박이 아닌, 주변 선박이나 해상 객체를 필요에 따라 적절하게 언급하고 있는가?\n'
                            'A1: yes or no, (이미지 및 센서에서 자신의 선박이 아닌 주변 선박 및 객체 식별, 예: 자신의 선박 이외에 주변에 선박 및 객체가 없는 경우 \"주변 선박 및 객체 감지되지 않음.\", 2시 방향에 어선이 이미지 및 센서에 감지된 경우 \"2시 방향에 어선 1척 식별됨.\")\n\n'
                            'Q2: 센서 데이터에 나타난 실제 선박에 대한 정보(자신의 선박인지 여부, 위치, 속도, 방향, 종류 등)와 묘사문이 일치하는가?\n'
                            'A2: yes or no, (센서 데이터를 기반으로 자신의 선박에 대한 묘사 또는 주변 선박에 대한 묘사가 일치하는지 분석. 단, 자신의 선박을 반드시 묘사할 필요는 없음. 예: "묘사에는 \'고속으로 이동 중\'이라 했으나 센서상 속도는 3 knot로 느림.")\n\n'
                            'Q3: 필요한 경우, 주어진 묘사문에서 주변 선박 및 객체와 자신의 선박과의 거리, 속도 등을 파악하여 상황을 정확히 묘사하였는가?\n'
                            'A3: yes or no, (거리 및 속도에 대한 묘사 정확성 분석, 예: 묘사문에는 주변 선박 및 객체에 대한 정보를 바탕으로 상황 묘사를 수행하지 않음.)\n\n'
                            'Q4: 필요한 경우, 이미지와 센서 데이터를 기반으로 식별된 주변 선박 및 개체와의 근접 또는 충돌 등의 위험 상황에서 위험 상황을 정확히 묘사하였는가?\n'
                            'A4: yes or no, (근접 상황에서 위험 상황 묘사 정확성 분석, 예: 묘사문에는 선박 간 충돌 위험성에 대해 언급하지 않았으나, 근접하고 있는 상황으로 경고가 필요한 상황이었음.)\n\n'
                            'Q5: 필요한 경우, Clock position을 통해 주변 선박 및 객체의 위치를 자신의 선박을 기준으로 상대적으로 정확히 묘사하였는가?\n'
                            'A5: yes or no, (Clock position을 통해 상대적 위치 묘사 정확성 분석, 예: 묘사문에는 \'2시 방향\'이라 했으나 실제로는 \'9시 방향\'이었음.)\n\n'
                            'Q6: 자신의 선박을 다른 선박 또는 다른 객체로 인식하여 묘사하지는 않았는가?\n'
                            'A6: yes or no, (자신의 선박을 다른 선박 또는 다른 객체로 인식하여 묘사함. 단, 자신의 선박을 반드시 묘사할 필요는 없음. 예: 센서 데이터 상 선박이 존재하여 다른 선박 또는 타선박이라고 묘사하였으나 자신의 선박이었음.)\n\n'
                            'Q7: 눈부심, 어두움, 역광, 야간, 안개 등의 이미지에서 확인되는 기상상황 또는 시야 조건을 묘사하였고, 이로 인한 시야 확보 및 거리 판단의 어려움이 있는 경우에 경고가 묘사문에 반영되었는가?\n'
                            'A7: yes or no, (이미지에 나타난 기상상황 또는 시야 조건이 묘사문과 일치하는지 분석, 예: 시야 확보가 양호하나 묘사문에서 \'역광으로 인해 시야 확보가 원활하지 않음.\'와 같이 묘사함.)\n\n'
                            'Q8: 이미지에서 시야 확보의 어려움이 확인되었을 때, 선박 식별 어려움에 대한 경고가 묘사문에 반영되었는가?\n'
                            'A8: yes or no, (제공된 두 이미지 중, *초록색 바운딩박스가 포함되지 않은* 두 번째 이미지인 *원본 이미지*를 바탕으로 주변 선박 및 객체 식별이 원활한지 분석, 예: *원본 이미지* 상 주변 선박 및 객체가 명확하게 식별되지 않으나, 선박 식별이 어렵다는 점이 묘사문에 반영되지 않았음.)\n\n'
                            #'Q9: 위의 질문들을 종합하여 기존 묘사문을 1차적으로 수정하시오.\n'
                            #'A9: (기존 묘사문을 바탕으로 이미지 및 센서 데이터와 일치하도록 수정한 1차 수정 묘사문 작성)\n\n'
                            'Q9: 위의 질문들에 대한 답변을 종합하여 기존 묘사문이 바운딩박스가 포함된 이미지, 원본 이미지, 센서 데이터에 기반하여 검토되고 수정되었는가?\n'
                            'A9: yes or no, (주의사항을 고려하면서 부여된 역할을 잘 반영하여 앞선 질문들에 대한 답변이 이미지 및 센서 데이터와 일치하는지 종합적으로 재검토 후 판단 및 요약)\n\n'
                            #'---*Reasoning Process: Use step-by-step verification*---\n\n'
                            #'R1: 위의 질문들을 종합하여 기존 묘사문을 1차적으로 수정하시오.\n'
                            #'A1: (기존 묘사문을 바탕으로 이미지 및 센서 데이터와 일치하도록 수정한 1차 수정 묘사문 작성)\n\n'
                            #'R2: 기존 묘사문이 적절하게 수정되었는지를 확인하기 위해 제공된 질문들에 대한 답변들이 이미지 및 센서 데이터를 확인하였을 때 적절한지 재검토하고 1차 수정문에 반영되었는지 검토 후, 추가 수정을 수행하시오.\n'
                            #'A2: (1차 수정 묘사문을 재검토하여 수정한 최종 묘사문 작성)\n\n'
                            '---*주의사항*---\n\n'
                            '- 별표(*)로 강조된 부분을 주의깊게 확인하여 올바르게 각 질문들에 답하세요.\n'
                            '- 이미지는 *자신의 선박 정면*을 기준으로 촬영된 것이며, 이를 기준으로 상대적으로 위치를 묘사하세요.\n'
                            '- 첫 번째 이미지는 선박에 대한 바운딩박스가 포함된 이미지이며, 두 번째 이미지는 원본 이미지입니다.\n'
                            '- 바운딩박스가 포함된 이미지에서는 시야조건과 무관하게 선박 식별이 명확히 되므로, 원본 이미지를 바탕으로 명확한 선박 식별 및 시야 확보가 가능한지 시야조건을 고려하여 기존 묘사문을 검토하세요.\n'
                            '- 선박간의 거리는 선박의 위도 및 경도를 나타내는 latitude, longitude 센서 데이터를 기반으로 위도와 경도의 차이를 통해 고려하세요.\n'
                            '- 센서 데이터의 \"heading\" 필드는 해당 선박이 향하고 있는 진행 방향을 나타내며, 위치를 나타내지 않기 때문에 선박의 상대적 위치 묘사에는 영향을 미치지 않아야 합니다.\n'
                            '- 자신의 선박은 이미지에 나타나지 않을 수 있으므로 \"ship_id\"와 \"my_ship\" 필드를 참고하여 자신의 선박 여부를 판단하여 기존 묘사문을 수정하세요.\n'
                            '- *자신의 선박에 대한 묘사는 묘사문에 반드시 포함되지 않아도 되며*, 묘사할 경우에 전지적 시점이 아닌 *1인칭 관점*에서 묘사하세요.\n'
                            '- 출력을 대시(-)와 띄어쓰기 및 콜론(:)을 포함하여 최종 출력 형식에 *반드시* 일치시키세요.\n\n'
                            '---*최종 출력 형식*---\n\n'
                            '- 기존 묘사문 : (수정 전의 원본 텍스트)\n'
                            '- 검토 요약 : (묘사와 실제 데이터 간의 일치 여부 요약)\n'
                            #'- 1차 수정 묘사문 : (기존 묘사문을 1차 수정한 묘사문)\n'
                            '- 수정된 묘사문 : (사실과 일치하도록 수정한 최종 묘사문)\n'
                            '- 신뢰도 점수 : (0~1 사이의 점수로 수정한 묘사에 대한 정확도 평가 예: 0.85)\n\n'
                        )
                    }
                ]
            },
            {
                'role': 'user',
                'content': [
                    {
                        'type': 'image',
                        'image': Image.open(self.processed_dataset[index]['bbox_image_path']).convert('RGB')
                    },
                    {
                        'type': 'image',
                        'image': Image.open(self.processed_dataset[index]['image_path']).convert('RGB')
                    },
                    {
                        'type': 'text',
                        'text': (
                            '------\n\n'
                            '센서 데이터:\n'
                            f'{sensor_text}\n'
                            '수정 전 항해 상황 묘사:\n'
                            f'{self.processed_dataset[index]["pseudo_label"]}\n\n'
                            '------\n\n'
                        )
                    }
                ]
            }
        ]
        #inputs = self.processor.apply_chat_template(
        #    messages,
        #    tokenize=True,
        #    add_generation_prompt=True,
        #    return_dict=True,
        #    return_tensors="pt"
        #)
#
        #return {'dataset_id': self.processed_dataset[index]['dataset_id'], 'frame_id': self.processed_dataset[index]['frame_id'], 'input_ids': inputs}
        return {'dataset_id': self.processed_dataset[index]['dataset_id'], 'frame_id': self.processed_dataset[index]['frame_id'], 'input_ids': messages}
    
    @overrides
    def collate_fn(self, batchs):
        messages = [b['input_ids'] for b in batchs]
        ids = [b['dataset_id'] for b in batchs]
        frame_ids = [b['frame_id'] for b in batchs]

        inputs = self.processor.apply_chat_template(
            messages,
            tokenize=True,
            padding=True,
            add_generation_prompt=True,
            return_dict=True,
            return_tensors="pt"
        )

        return {'dataset_id': ids, 'frame_id': frame_ids, 'messages': messages}, inputs

#class TrainDataset(BaseDataset):
#    def __getitem__(self, index):
#        prompt = ( # Intents와 Slots을 추출하도록 Instruction 수정 필요
#            '<|start_header_id|>system<|end_header_id|>\n\n'
#            'You are a translator. Please translate English to Deutsch.<|eot_id|><|start_header_id|>user<|end_header_id|>\n\n'
#        )
#        inputs = self.tokenizer(text=f'{prompt}{self.data_x[index]}<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n\n', return_tensors="pt", truncation=True)['input_ids'].squeeze()
#        target = self.tokenizer(text=f'{self.data_y[index]}<|eot_id|>', return_tensors="pt", truncation=True)['input_ids'].squeeze()
#
#        concatenated_tokens = torch.cat([inputs, target])
#        labels = concatenated_tokens.clone()
#        labels[:len(inputs)] = self.tokenizer.pad_token_id
#
#        return {'input_ids': concatenated_tokens, 'labels': labels}
#    
#class EvaluateDataset(BaseDataset):
#    def __getitem__(self, index):
#        prompt = ( # Intents와 Slots을 추출하도록 Instruction 수정 필요
#            '<|start_header_id|>system<|end_header_id|>\n\n'
#            'You are a translator. Please translate English to Deutsch.<|eot_id|><|start_header_id|>user<|end_header_id|>\n\n'
#        )
#        inputs = self.tokenizer(text=f'{prompt}{self.data_x[index]}<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n\n', return_tensors="pt", truncation=True)['input_ids'].squeeze()
#        target = self.tokenizer(text=f'{self.data_y[index]}<|eot_id|>', return_tensors="pt", truncation=True)['input_ids'].squeeze()
#
#        return {'input_ids': inputs, 'labels': target}