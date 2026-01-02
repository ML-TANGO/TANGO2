import sys
from langchain_ollama import OllamaLLM
from langchain_core.prompts import PromptTemplate, FewShotPromptTemplate, ChatPromptTemplate, MessagesPlaceholder
from langchain_classic.chains import LLMChain
from langchain_classic.memory import ConversationBufferMemory

# 모듈화된 함수들 임포트
from src.config import read_config
from src.ollama_manager import start_ollama, stop_ollama, pull_model_if_needed
from src.data_loader import load_examples
from src.prompt_loader import load_prompt_config, load_prompt_components
from src.app_ui import run_cli, run_web

def main():
    """Main function to run the application."""
    ollama_status = None
    ollama_process = None
    model_name = None
    try:
        # 1. 설정 읽기
        config = read_config()
        ui_mode = config.get('app', 'UI_MODE', fallback='cli')
        interaction_mode = config.get('app', 'INTERACTION_MODE', fallback='single_shot')
        model_name = config.get('app', 'MODEL_NAME', fallback='gemma3')
        web_host = config.get('web', 'HOST', fallback='127.0.0.1')
        web_port = config.getint('web', 'PORT', fallback=5000)

        # DSPy Configure
        dspy_optimizer = config.get('DSPY', 'OPTIMIZER', fallback='BootstrapFewShot')
        use_dspy = config.getboolean('DSPY', 'USE_DSPY', fallback=False)
        dspy_metric = config.get('DSPY', 'METRIC', fallback='bert_score')

        print(f"--- Mode: {ui_mode.upper()} | Interaction: {interaction_mode.upper()} ---")
        if use_dspy and interaction_mode == 'single_shot':
            print(f"--- DSPy Optimizer: {dspy_optimizer} ---")

        # 2. Ollama 서버 및 모델 준비
        ollama_status, ollama_process = start_ollama()
        if ollama_status is None:
            return

        if not pull_model_if_needed(model_name):
            print(f"'{model_name}' 모델을 준비할 수 없어 프로그램을 종료합니다.")
            return

        # 3. Few-Shot 예시 로드
        examples = []
        load_examples_needed = True #TODO: 항상 필요한지 고민
        if load_examples_needed:
            print("="*50)
            print("🤖 Few-Shot 예시로 사용할 CSV 파일 경로를 입력해주세요.")
            print("   - 경로 입력을 마치려면 그냥 Enter를 누르세요.")
            print("="*50)
            input_csv_paths, output_csv_paths = [], []
            while True:
                path = input(f"입력(Input) CSV 파일 경로 #{len(input_csv_paths) + 1}: ")
                if not path: break
                input_csv_paths.append(path)
            if input_csv_paths:
                while len(output_csv_paths) < len(input_csv_paths):
                    path = input(f"출력(Output) CSV 파일 경로 #{len(output_csv_paths) + 1}: ")
                    if not path: break
                    output_csv_paths.append(path)

            if input_csv_paths and output_csv_paths:
                shuffle_choice = input("🔀 예제를 셔플하시겠습니까? (y/n, 기본값 n): ").lower().strip()
                do_shuffle = shuffle_choice == 'y'

                examples = load_examples(input_csv_paths, output_csv_paths, shuffle=do_shuffle)

                if examples:
                    print(f"✅ 총 {len(examples)}개의 Few-Shot 예시를 성공적으로 불러왔습니다.")
                else:
                    print("⚠️  불러온 예시가 없습니다.")
            else:
                print("💡 입력된 Few-Shot 예시 파일이 없습니다.")

        # 4. LLM 및 실행 컨텍스트 설정
        llm = OllamaLLM(model=model_name)
        context = {}

        if interaction_mode == 'conversational': # conversational 모드 프롬프트 설정
            conv_templates = load_prompt_config("prompts/conversational.yml")
            system_message = conv_templates['system_message_prefix'] + "\n\n"

            example_template_str = conv_templates['example_template']
            for ex in examples:
                system_message += f"Query: {ex['query']}\nResponse: {ex['response']}\n\n"

            memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)
            prompt = ChatPromptTemplate.from_messages([
                ("system", system_message),
                MessagesPlaceholder(variable_name="chat_history"),
                ("human", "{user_query}"),
            ])
            chain = LLMChain(llm=llm, prompt=prompt, memory=memory, verbose=True)
            context = {"mode": "conversational", "chain": chain}

        else: # single_shot 모드
            if use_dspy and examples: # DSPy 사용 로직
                print("\n🚀 DSPy 옵티마이저를 사용하여 프롬프트를 컴파일합니다...")
                print("   (MIPROv2와 같은 일부 옵티마이저는 시간이 오래 걸릴 수 있습니다.)")
                try:
                    from src.dspy_handler import compile_program, print_program_details
                    compiled_program = compile_program(model_name, dspy_optimizer, examples, metric_name=dspy_metric)
                    print("✅ DSPy 프로그램 컴파일 완료!")

                    # 컴파일된 프로그램의 상세 내용(지시문, 예제) 출력
                    print_program_details(compiled_program)

                    context = {
                        "mode": "dspy_single_shot",
                        "dspy_program": compiled_program,
                    }
                except ImportError as e:
                    print(f"\n[에러] DSPy 관련 모듈을 임포트하는 데 실패했습니다: {e}")
                    print("   'pip install dspy-ai'를 실행하여 라이브러리를 설치해주세요.")
                    return
                except Exception as e:
                    print(f"\n[에러] DSPy 프로그램 컴파일 중 오류가 발생했습니다: {e}")
                    return
            else: # 기존 LangChain single_shot 로직
                if use_dspy and not examples:
                    print("\nDSPy를 사용하도록 설정되었지만, Few-shot 예제가 제공되지 않아 기존 방식으로 실행합니다.")

                prompt_components = load_prompt_components()
                context = {
                    "mode": "single_shot",
                    "llm": llm,
                    "prompt_components": prompt_components,
                    "examples": examples
                }

        # 5. UI 실행
        if ui_mode == 'web':
            run_web(context, web_host, web_port)
        else:
            run_cli(context)

    except FileNotFoundError as e:
        print(f"\n오류: {e}. 설정 파일을 확인해주세요.")
    except KeyboardInterrupt:
        print("\n사용자에 의해 프로그램이 중단되었습니다.")
    finally:
        # Unload the model and/or stop the server
        if ollama_status:
            stop_ollama(ollama_status, ollama_process, model_name)
        print("Application shut down.")

if __name__ == "__main__":
    main()
