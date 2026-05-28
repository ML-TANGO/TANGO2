from transformers import Qwen3VLMoeForConditionalGeneration, AutoProcessor
import torch
import os, json, logging, argparse, csv
from datetime import datetime
from pytz import timezone
from torch.utils.data import DataLoader
from tqdm.auto import tqdm

from dataset import PromptingDataset

class DataRevisor():
    def __init__(self, dataloader, model_id):
        self.dataloader = dataloader
        self.model = Qwen3VLMoeForConditionalGeneration.from_pretrained(
            model_id,
            dtype=torch.bfloat16,
            attn_implementation="flash_attention_2",
            device_map="auto",
        )
        self.model.to(device)
        self.processor = AutoProcessor.from_pretrained(model_id)
        self.outputs = {}
        self.reasoning = {}
    
    def __call__(self):
        progress_bar = tqdm(total=len(self.dataloader), desc="Augmenting Data")

        self.model.eval()
        for meta, batch in self.dataloader:
            batch = {k: v.to(device) for k, v in batch.items()}
            with torch.inference_mode():
                generation = self.model.generate(
                    **batch,
                    max_new_tokens=8192,
                )

            generated_ids_trimmed = [
                out_ids[len(in_ids):] for in_ids, out_ids in zip(batch['input_ids'], generation)
            ]
            output_text = self.processor.batch_decode(
                generated_ids_trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False
            )

            #for i, o in enumerate(output_text):
            #    self.outputs.setdefault(meta['dataset_id'][i], []).append({
            #        'file_name' : meta['frame_id'][i],
            #        'input' : meta['messages'][i][1]['content'][2]['text'],
            #        'output' : o.strip(),
            #    })

            for i, o in enumerate(output_text):
                self.outputs.setdefault(meta['dataset_id'][i], []).append({
                    'file_name' : meta['frame_id'][i],
                    'input' : o.split('- 기존 묘사문 : ')[1].split('- 검토 요약 : ')[0],
                    'output' : o.split('- 수정된 묘사문 : ')[1].split('- 신뢰도 점수 : ')[0],
                })
                self.reasoning.setdefault(meta['dataset_id'][i], []).append({
                    'file_name' : meta['frame_id'][i],
                    'input' : meta['messages'][i][1]['content'][2]['text'],
                    'reasoning' : o.strip()
                })
            
            progress_bar.update(1)

        return self.outputs, self.reasoning

    def save_result(self, save_path):
        os.makedirs(save_path, exist_ok=True)
        for k in self.outputs.keys():
            with open(os.path.join(save_path, f'dataset{k}.csv'), 'wt') as f:
                writer = csv.DictWriter(f, fieldnames=['file_name', 'input', 'output'])
                writer.writeheader()
                writer.writerows(self.outputs[k])
        for k in self.reasoning.keys():
            with open(os.path.join(save_path, f'reasoning_dataset{k}.csv'), 'wt') as f:
                writer = csv.DictWriter(f, fieldnames=['file_name', 'input', 'reasoning'])
                writer.writeheader()
                writer.writerows(self.reasoning[k])
        print(f'data saved as {save_path}')

def main():
    # (0) argument parsing
    parser = argparse.ArgumentParser(description='Generated Data Revision')
    parser.add_argument('--model_id', type=str, default="Qwen/Qwen3-VL-30B-A3B-Instruct", help='model id/location of LLM')
    parser.add_argument('--batch_size', type=int, default=4, help='batch size for dataloader')
    parser.add_argument('--base_data_path', type=str, default='../dataset/20250922', help='base data path')
    parser.add_argument('--save_path', type=str, default='./result', help='output directory path')
    args = parser.parse_args()

    # (1) data loading
    now_time = datetime.now(KST).strftime('%Y/%m/%d %H:%M:%S')
    _LOGGER.info(f'[INFO] ({now_time}) Starting Revision Process..\n  target data: {args.base_data_path}\n  batch size: {args.batch_size}')
    dataset = PromptingDataset(args.base_data_path, args.model_id)
    dataloader = DataLoader(dataset, batch_size=args.batch_size, shuffle=False, collate_fn=dataset.collate_fn)
    revisor = DataRevisor(dataloader, args.model_id)

    # (2) data augmentation
    now_time = datetime.now(KST).strftime('%Y/%m/%d %H:%M:%S')
    _LOGGER.info(f'[INFO] ({now_time}) Starting Augmentation Process..\n  saving path: {args.save_path}\n  model: {args.model_id}')
    outputs, reasoning = revisor()

    # (3) save json
    now_time = datetime.now(KST).strftime('%Y/%m/%d %H:%M:%S')
    _LOGGER.info(f'[INFO] ({now_time}) Success!!\n  saving path: {args.save_path}\n')
    revisor.save_result(args.save_path)

if __name__ == '__main__':
    KST = timezone('Asia/Seoul')
    stream_handler = logging.StreamHandler()
    _LOGGER = logging.getLogger("__name__")
    _LOGGER.setLevel(level=logging.INFO)
    _LOGGER.addHandler(stream_handler)
    date = datetime.now(KST).strftime('%m%d%H%M')
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    main()