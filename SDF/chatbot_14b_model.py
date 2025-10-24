from transformers import (
    AutoTokenizer, 
    AutoModelForCausalLM, 
    BitsAndBytesConfig,
    StoppingCriteria, 
    StoppingCriteriaList
)
class StopOnTokens(StoppingCriteria):
    def __init__(self, stop_sequences, device):
        self.stop_sequences = [
            tokenizer(seq, 
                      return_tensors='pt', 
                      add_special_tokens=False)['input_ids'].to(device) 
            for seq in stop_sequences
        ]

    def __call__(self, input_ids: torch.LongTensor, scores: torch.FloatTensor, **kwargs) -> bool:
        # input_ids: (batch_size, sequence_length)
        # 현재까지 생성된 모든 토큰을 확인
        for stop_ids in self.stop_sequences:
            # input_ids의 끝 부분이 stop_ids와 일치하는지 확인
            # (stop_ids의 shape는 (1, stop_seq_len)이므로 [0]으로 접근)
            stop_len = stop_ids.shape[1]
            if input_ids.shape[1] >= stop_len:
                if torch.all(input_ids[0, -stop_len:] == stop_ids[0]):
                    return True
        return False

stop_sequences = [tokenizer.eos_token, "```", "\nUser:"]
stop_criteria = StopOnTokens(stop_sequences, model.device)
stopping_criteria_list = StoppingCriteriaList([stop_criteria])

# 7. 간단한 챗봇 루프
while True:
    # 7-1. 사용자 입력
    user_input = input("You: ")
    if user_input.lower() == 'exit':
        print("챗봇을 종료합니다.")
        break

    # 7-2. 프롬프트 생성
    prompt = f"User: {user_input}\nAssistant: ```json\n"

    # 7-3. 입력 토큰화
    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
    input_len = inputs['input_ids'].shape[1]

    # ❗ [수정 2]
    # 루프 안에서 매번 객체를 생성할 필요가 없습니다.
    # stop_sequences = [tokenizer.eos_token, "}\n```"]
    # stop_criteria = StopOnTokens(stop_sequences, model.device)
    # stopping_criteria_list = StoppingCriteriaList([stop_criteria])
    
    # 7-4. 모델 생성 (generate)
    outputs = model.generate(
        **inputs,
        max_new_tokens=2048,
        
        # ❗ [수정 3]
        # 'eos_token_id=stop_sequences' 대신 'stopping_criteria'를 사용합니다.
        stopping_criteria=stopping_criteria_list,
        
        # 'eos_token_id'에는 실제 정수 ID를 전달하는 것이 좋습니다.
        eos_token_id=tokenizer.eos_token_id, 
        pad_token_id=tokenizer.pad_token_id, # 경고 방지를 위해 추가
        
        do_sample=True,
        temperature=0.3,
        top_p=0.9
    )

    # 7-5. 응답 디코딩 (입력 프롬프트 부분 제외)
    response_tokens = outputs[0][input_len:]
    response = tokenizer.decode(response_tokens, skip_special_tokens=True)

    print(f"Bot: {response}")