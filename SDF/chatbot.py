# 필요한 라이브러리 임포트
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from peft import PeftModel
import json
import re

# 모델과 토크나이저 로드
print("모델과 토크나이저를 로딩 중...")

# 기본 모델과 토크나이저 로드
base_model_name = "Salesforce/xLAM-1b-fc-r"
tokenizer = AutoTokenizer.from_pretrained(base_model_name)
base_model = AutoModelForCausalLM.from_pretrained(
    base_model_name,
    device_map="auto",
    torch_dtype=torch.float16
)

# LoRA 어댑터 로드
model = PeftModel.from_pretrained(base_model, "./fine_tuned_xlm_lora")

print("모델 로딩 완료!")
print(f"사용 가능한 도구: {len(model.peft_config)} 개의 LoRA 어댑터가 로드됨")

# 스마트홈 도구 정보 정의
SMART_HOME_TOOLS = [
    {
        "name": "open_left_window",
        "description": "왼쪽 창문을 주어진 퍼센트(%)만큼 엽니다. 온도를 낮추거나 환기시킬 때 사용합니다.",
        "parameters": {"persent": {"type": "int", "description": "열고자 하는 창문의 개방 정도(0-100%)"}}
    },
    {
        "name": "open_right_window",
        "description": "오른쪽 창문을 주어진 퍼센트(%)만큼 엽니다. 온도를 낮추거나 환기시킬 때 사용합니다.",
        "parameters": {"persent": {"type": "int", "description": "열고자 하는 창문의 개방 정도(0-100%)"}}
    },
    {
        "name": "supply_water",
        "description": "식물에게 지정된 양만큼의 물을 공급합니다. 토양이 건조하거나 습도를 높여야 할 때 사용합니다.",
        "parameters": {"Liter": {"type": "float", "description": "공급할 물의 양 (리터 단위)"}}
    },
    {
        "name": "light_on",
        "description": "하우스 내부의 생장등을 켭니다. 일조량이 부족할 때 사용합니다.",
        "parameters": {}
    },
    {
        "name": "light_off",
        "description": "하우스 내부의 생장등을 끕니다. 야간이거나 일조량이 충분할 때 사용합니다.",
        "parameters": {}
    }
]

print("스마트홈 도구 정보:")
for tool in SMART_HOME_TOOLS:
    print(f"- {tool['name']}: {tool['description']}")

# 응답 생성 함수
def generate_response(prompt, max_new_tokens=200):
    """프롬프트에 대한 응답을 생성하는 함수"""
    try:
        # 입력 텍스트 토크나이징
        inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=512)

        # 디바이스 설정 - MPS 대신 CPU 사용으로 안정성 확보
        device = "cpu"  # MPS 대신 CPU 사용
        inputs = {k: v.to(device) for k, v in inputs.items()}
        model.to(device)
        
        # 응답 생성
        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                num_return_sequences=1,
                temperature=0.2,
                do_sample=True,
                pad_token_id=tokenizer.eos_token_id,
                eos_token_id=tokenizer.eos_token_id,
                repetition_penalty=1.1
            )
        
        # 토큰을 텍스트로 디코딩
        response = tokenizer.decode(outputs[0], skip_special_tokens=True)
        
        # 입력 프롬프트 제거하고 응답만 반환
        response = response.replace(prompt, "").strip()
        return response
        
    except Exception as e:
        return f"응답 생성 중 오류 발생: {e}"
    
# JSON 응답 파싱 함수
def parse_json_response(response):
    """AI 응답에서 JSON 형식의 액션을 추출하는 함수"""
    try:
        # JSON 배열 패턴 찾기
        json_pattern = r'\[\s*\{[^\]]*\}\]'
        json_match = re.search(json_pattern, response)
        
        if json_match:
            json_str = json_match.group()
            actions = json.loads(json_str)
            return actions
        
        return None
    except Exception as e:
        print(f"JSON 파싱 오류: {e}")
        return None

# 액션 실행 시뮬레이션 함수
def simulate_action(action):
    """AI가 제안한 액션을 시뮬레이션하는 함수"""
    try:
        action_name = action.get('name', 'unknown')
        arguments = action.get('arguments', {})
        
        print(f"\n🔧 액션 실행: {action_name}")
        
        if action_name == "open_left_window":
            percent = arguments.get('persent', 0)
            print(f"   왼쪽 창문을 {percent}% 열었습니다.")
        elif action_name == "open_right_window":
            percent = arguments.get('persent', 0)
            print(f"   오른쪽 창문을 {percent}% 열었습니다.")
        elif action_name == "supply_water":
            liters = arguments.get('Liter', 0)
            print(f"   {liters}L의 물을 공급했습니다.")
        elif action_name == "light_on":
            print(f"   생장등을 켰습니다.")
        elif action_name == "light_off":
            print(f"   생장등을 껐습니다.")
        else:
            print(f"   알 수 없는 액션: {action_name}")
            
    except Exception as e:
        print(f"액션 실행 오류: {e}")

# 대화형 챗봇 인터페이스
def chat():
    """대화형 챗봇 인터페이스"""
    print("\n" + "="*60)
    print("🏠 스마트홈 AI 챗봇에 오신 것을 환영합니다!")
    print("="*60)
    print("\n사용 가능한 명령:")
    print("- 'quit', 'exit', '종료': 챗봇 종료")
    print("- 'tools': 사용 가능한 도구 목록 보기")
    print("- 'help': 도움말 보기")
    print("\n예시 질문:")
    print("- \"온도가 너무 높아요\"")
    print("- \"식물에게 물을 주고 싶어요\"")
    print("- \"일조량이 부족해요\"")
    print("="*60)
    
    while True:
        try:
            # 사용자 입력
            user_input = input("\n🏠 사용자: ").strip()
            
            if user_input.lower() in ['quit', 'exit', '종료']:
                print("\n�� 스마트홈 AI 챗봇을 종료합니다. 안녕히 가세요!")
                break
            
            if user_input.lower() == 'tools':
                print("\n�� 사용 가능한 스마트홈 도구:")
                for tool in SMART_HOME_TOOLS:
                    print(f"  • {tool['name']}: {tool['description']}")
                continue
            
            if user_input.lower() == 'help':
                print("\n📖 도움말:")
                print("  • 자연어로 스마트홈 제어 요청을 입력하세요")
                print("  • AI가 상황에 맞는 적절한 액션을 제안합니다")
                print("  • 'tools' 명령으로 사용 가능한 도구를 확인할 수 있습니다")
                continue
            
            if not user_input:
                continue
            
            # 프롬프트 구성 (훈련 데이터 형식과 일치)
            tools_json = json.dumps(SMART_HOME_TOOLS, ensure_ascii=False)
            prompt = f"Query: {user_input}\nTools: {tools_json}\nAnswer:"
            
            print("\n�� AI가 응답을 생성 중입니다...")
            
            # 응답 생성
            response = generate_response(prompt)
            
            print(f"\n🤖 AI: {response}")
            
            # JSON 응답 파싱 및 액션 실행
            actions = parse_json_response(response)
            if actions:
                print("\n📋 제안된 액션:")
                for action in actions:
                    simulate_action(action)
            
        except KeyboardInterrupt:
            print("\n\n�� 스마트홈 AI 챗봇을 종료합니다. 안녕히 가세요!")
            break
        except Exception as e:
            print(f"\n❌ 오류 발생: {e}")

# 메인 실행
if __name__ == "__main__":
    chat()