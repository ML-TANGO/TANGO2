import sys
from langchain_ollama import OllamaLLM
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate, FewShotPromptTemplate, ChatPromptTemplate, MessagesPlaceholder
from langchain_classic.chains import LLMChain
from langchain_classic.memory import ConversationBufferMemory

# 모듈화된 함수들 임포트
from src.config import read_config, get_few_shot_files
from src.ollama_manager import start_ollama, stop_ollama, pull_model_if_needed
from src.vllm_manager import start_vllm, stop_vllm
from src.data_loader import load_examples
from src.prompt_loader import load_prompt_config, load_prompt_components
from src.app_ui import run_cli, run_web

def main():
    """Main function to run the application."""
    ollama_status, ollama_process = None, None
    vllm_status, vllm_process = None, None
    model_name = None
    backend = None
    try:
        # 1. 설정 읽기
        config = read_config()
        ui_mode = config.get('app', 'UI_MODE', fallback='cli')
        interaction_mode = config.get('app', 'INTERACTION_MODE', fallback='single_shot')
        do_shuffle = config.getboolean('app', 'SHUFFLE_EXAMPLES', fallback=False)
        fallback_to_interactive = config.getboolean('FEW_SHOT_DATA', 'FALLBACK_TO_INTERACTIVE', fallback=True)
        backend = config.get('app', 'BACKEND', fallback='ollama').lower()
        model_name = config.get('app', 'MODEL_NAME', fallback='gemma3')

        web_host = config.get('web', 'HOST', fallback='127.0.0.1')
        web_port = config.getint('web', 'PORT', fallback=5000)

        # DSPy Configure
        dspy_optimizer = config.get('DSPY', 'OPTIMIZER', fallback='BootstrapFewShot')
        use_dspy = config.getboolean('DSPY', 'USE_DSPY', fallback=False)
        dspy_metric = config.get('DSPY', 'METRIC', fallback='bert_score')
        dspy_mipro_auto_level = config.get('DSPY', 'MIPRO_AUTO_LEVEL', fallback='light')

        print(f"--- Backend: {backend.upper()} | Mode: {ui_mode.upper()} | Interaction: {interaction_mode.upper()} ---")
        if use_dspy:
            print(f"--- DSPy Optimizer: {dspy_optimizer} | Metric: {dspy_metric} ---")
            if dspy_optimizer == 'MIPROv2':
                print(f"--- DSPy MIPRO Auto Level: {dspy_mipro_auto_level.upper()} ---")

        # 2. 백엔드 및 모델 준비
        if backend == 'ollama':
            ollama_status, ollama_process = start_ollama()
            if ollama_status is None:
                return

            if not pull_model_if_needed(model_name):
                print(f"'{model_name}' 모델을 준비할 수 없어 프로그램을 종료합니다.")
                return

            llm = OllamaLLM(model=model_name)
            backend_url = config.get('ollama', 'OLLAMA_URL', fallback='http://localhost:11434')

        elif backend == 'vllm':
            vllm_url = config.get('vllm', 'VLLM_URL', fallback='http://localhost:8000/v1')
            vllm_model_path = config.get('vllm', 'MODEL_PATH', fallback=None)

            vllm_status, vllm_process = start_vllm(vllm_url, model_name, model_path=vllm_model_path)
            if vllm_status is None:
                print(f"vLLM 서버를 시작할 수 없어 프로그램을 종료합니다.")
                return

            # 클라이언트가 사용할 모델 식별자를 결정합니다. (로컬 경로 우선)
            model_name = vllm_model_path if vllm_model_path and vllm_model_path.strip() else model_name

            # vLLM (OpenAI-compatible) LLM setup
            llm = ChatOpenAI(
                model=model_name,
                openai_api_base=vllm_url,
                openai_api_key="none" # vLLM typically doesn't need a key
            )
            backend_url = vllm_url
        else:
            print(f"지원하지 않는 백엔드입니다: {backend}")
            return

        # 3. Few-Shot 예시 로드
        examples = []

        # config.ini에서 로드 시도
        input_csv_paths, output_csv_paths = get_few_shot_files(config)

        if input_csv_paths and output_csv_paths:
            print(f"config.ini에서 Few-shot 파일 경로를 불러왔습니다: {len(input_csv_paths)} 쌍")
            if len(input_csv_paths) != len(output_csv_paths):
                print("입력 CSV 파일과 출력 CSV 파일의 개수가 일치하지 않습니다.")
            else:
                examples = load_examples(input_csv_paths, output_csv_paths, shuffle=do_shuffle)
                if examples:
                    print(f"총 {len(examples)}개의 Few-Shot 예시를 성공적으로 불러왔습니다.")
                else:
                    print("config.ini에 지정된 파일에서 예시를 불러오지 못했습니다.")

        # config.ini에서 예제를 불러오지 못한 경우, 사용자에게 입력 요청
        if not examples and fallback_to_interactive:
            if input_csv_paths: # 경로는 있었지만 로딩에 실패한 경우
                 print("사용자 입력을 통해 Few-shot 예제를 다시 설정합니다.")

            if ui_mode == 'web' and not input_csv_paths:
                print("\n[Web UI 모드] 웹 세션에서 사용할 Few-shot 예제를 미리 설정합니다.")
            print("="*50)
            print("Few-Shot 예시로 사용할 CSV 파일 경로를 입력해주세요.")
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
                examples = load_examples(input_csv_paths, output_csv_paths, shuffle=do_shuffle)

                if examples:
                    print(f"총 {len(examples)}개의 Few-Shot 예시를 성공적으로 불러왔습니다.")
                else:
                    print("⚠️  불러온 예시가 없습니다.")
            else:
                print("입력된 Few-Shot 예시 파일이 없습니다.")

        if not examples:
             print("로딩된 Few-Shot 예시가 없습니다. Zero-shot 모드로 실행됩니다.")

        # 4. LLM 및 실행 컨텍스트 설정
        context = {}

        if interaction_mode == 'conversational': # conversational 모드 프롬프트 설정
            if use_dspy and examples:
                print("\nDSPy 옵티마이저를 사용하여 대화형 프롬프트를 컴파일합니다...")
                print("   (MIPROv2와 같은 일부 옵티마이저는 시간이 오래 걸릴 수 있습니다.)")
                try:
                    from src.dspy_handler import compile_program, print_program_details
                    compiled_program = compile_program(
                        model_name, dspy_optimizer, examples,
                        metric_name=dspy_metric,
                        backend=backend,
                        backend_url=backend_url,
                        is_conversational=True,
                        mipro_auto_level=dspy_mipro_auto_level
                    )
                    print("DSPy 대화형 프로그램 컴파일 완료!")
                    print_program_details(compiled_program)

                    memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)
                    context = {
                        "mode": "dspy_conversational",
                        "dspy_program": compiled_program,
                        "memory": memory,
                    }
                except ImportError as e:
                    print(f"\n[에러] DSPy 관련 모듈을 임포트하는 데 실패했습니다: {e}")
                    print("   'pip install dspy-ai'를 실행하여 라이브러리를 설치해주세요.")
                    return
                except Exception as e:
                    print(f"\n[에러] DSPy 대화형 프로그램 컴파일 중 오류가 발생했습니다: {e}")
                    return
            else:
                if use_dspy and not examples:
                    print("\nDSPy를 사용하도록 설정되었지만, Few-shot 예제가 제공되지 않아 기존 대화형 방식으로 실행합니다.")

                conv_templates = load_prompt_config("prompts/conversational.yml")
                system_message = conv_templates['system_message_prefix'] + "\n\n"

                example_template_str = conv_templates['example_template']
                for ex in examples:
                    if example_template_str:
                         system_message += example_template_str.format(query=ex['query'], response=ex['response']) + "\n\n"
                    else:
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
                print("\nDSPy 옵티마이저를 사용하여 프롬프트를 컴파일합니다...")
                print("   (MIPROv2와 같은 일부 옵티마이저는 시간이 오래 걸릴 수 있습니다.)")
                try:
                    from src.dspy_handler import compile_program, print_program_details
                    compiled_program = compile_program(
                        model_name, dspy_optimizer, examples,
                        metric_name=dspy_metric,
                        backend=backend,
                        backend_url=backend_url,
                        mipro_auto_level=dspy_mipro_auto_level
                    )
                    print("DSPy 프로그램 컴파일 완료!")

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
        if backend == 'ollama' and (ollama_status or ollama_process):
            stop_ollama(ollama_status, ollama_process, model_name)
        elif backend == 'vllm' and vllm_process:
            stop_vllm(vllm_status, vllm_process)
        print("Application shut down.")

if __name__ == "__main__":
    main()
