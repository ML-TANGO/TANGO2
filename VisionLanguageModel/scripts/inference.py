import os
import argparse
import torch
from PIL import Image
from transformers import AutoTokenizer, CLIPImageProcessor
from llava_custom.model.language_model.llava_llama import LlavaLlamaForCausalLM
from llava_custom.constants import DEFAULT_IMAGE_TOKEN

def infer(args):
    """
    - 저장된 체크포인트를 불러들어와 이미지 기반 추론을 수행
    - 프로젝터 단일 경로 입력 시 명시적인 dtype 선언을 통해 NaN 텐서 오류 최소화
    """
    try:
        # - 모델 로드
        tokenizer = AutoTokenizer.from_pretrained(args.model_path, use_fast=False)
        model = LlavaLlamaForCausalLM.from_pretrained(args.model_path, torch_dtype=torch.float16, device_map="auto")
        
        # - 비전 타워 및 프로젝터 초기화
        class MockArgs:
            mm_vision_tower = "openai/clip-vit-large-patch14-336"
            mm_projector_type = "mlp2x_gelu"
            mm_vision_select_layer = -2
            mm_vision_select_feature = "patch"
        
        model.get_model().initialize_vision_modules(MockArgs())
        
        # - 프로젝터 가중치 로드
        if args.projector_path and os.path.exists(args.projector_path):
            projector_weights = torch.load(args.projector_path, map_location='cpu')
            
            def get_w(weights, keyword):
                """
                - Multi-GPU Zero-3 환경에서 저장된 가중치를 불러올 때 발생하는 dtype 불일치(NaN 방지)
                - 무조건 float16 으로 캐스팅 후 모델에 로드
                """
                try:
                    return {k.replace('model.mm_projector.', '').replace('mm_projector.', ''): v.to(torch.float16) for k, v in weights.items() if keyword in k}
                except Exception as e:
                    raise RuntimeError(f"가중치 변환 중 에러: {e}")
                
            filtered_weights = get_w(projector_weights, 'mm_projector')
            if len(filtered_weights) > 0:
                model.get_model().mm_projector.load_state_dict(filtered_weights)
                print("프로젝터 가중치(mm_projector.bin) 를 성공적으로 로드했습니다.")
            else:
                print("프로젝터 가중치를 찾을 수 없습니다. (키 불일치 혹은 모델 내장)")
            
        vision_tower = model.get_model().get_vision_tower()
        vision_tower.to(dtype=torch.float16, device=model.device)
        model.get_model().mm_projector.to(dtype=torch.float16, device=model.device)

        # - 이미지 전처리
        image_processor = CLIPImageProcessor.from_pretrained(MockArgs.mm_vision_tower)
        image = Image.open(args.image_file).convert('RGB')
        image_tensor = image_processor.preprocess(image, return_tensors='pt')['pixel_values'][0].unsqueeze(0).to(model.device, dtype=torch.float16)
        
        # - 추론용 프롬프트 생성 (Llama-3.1 포맷)
        # - <image> 토큰을 명시적으로 IMAGE_TOKEN_INDEX(-200)로 변환
        from llava_custom.constants import IMAGE_TOKEN_INDEX
        
        prompt = "<|begin_of_text|><|start_header_id|>user<|end_header_id|>\n\n" + DEFAULT_IMAGE_TOKEN + "\n" + args.query + "<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n\n"
        
        # - <image> 토큰 기준으로 분리하여 토큰화
        parts = prompt.split(DEFAULT_IMAGE_TOKEN)
        input_ids = []
        for i, part in enumerate(parts):
            if part:
                tokens = tokenizer.encode(part, add_special_tokens=False)
                input_ids.extend(tokens)
            if i < len(parts) - 1:
                input_ids.append(IMAGE_TOKEN_INDEX)
        
        input_ids = torch.tensor(input_ids, dtype=torch.long).unsqueeze(0).to(model.device)
        attention_mask = torch.ones_like(input_ids).to(model.device)
        
        # - 텍스트 생성
        if tokenizer.pad_token_id is None:
            tokenizer.pad_token_id = tokenizer.eos_token_id
            
        with torch.inference_mode():
            output_ids = model.generate(
                input_ids=input_ids,
                attention_mask=attention_mask,
                images=image_tensor,
                max_new_tokens=1024,
                use_cache=True,
                temperature=0.2,
                do_sample=True,
                pad_token_id=tokenizer.pad_token_id,
                eos_token_id=tokenizer.eos_token_id,
            )
        
        outputs = tokenizer.decode(output_ids[0, input_ids.shape[1]:], skip_special_tokens=True)
        print("======== 추론 결과 ========")
        print(outputs)

    except Exception as e:
        print(f"추론 실패: {e}")
        raise

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-path", type=str, required=True, help="Base LLM 모델 경로")
    parser.add_argument("--projector-path", type=str, default=None, help="학습된 mm_projector.bin 경로")
    parser.add_argument("--image-file", type=str, required=True, help="테스트 이미지 파일 경로")
    parser.add_argument("--query", type=str, default="Describe this image in detail.", help="질의응답 내용")
    args = parser.parse_args()
    infer(args)
