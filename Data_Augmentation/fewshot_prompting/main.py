import sys
from langchain_community.llms import Ollama
from langchain.prompts import PromptTemplate, FewShotPromptTemplate, ChatPromptTemplate, MessagesPlaceholder
from langchain.chains import LLMChain
from langchain.memory import ConversationBufferMemory

from src.config import read_config
from src.ollama_manager import start_ollama, stop_ollama, pull_model_if_needed
from src.data_loader import load_examples
from src.app_ui import run_cli, run_web

def main():
    """Main function to run the application."""
    ollama_status = None
    model_name = None
    try:
        # 1. 설정 읽기
        config = read_config()
        ui_mode = config.get('app', 'UI_MODE', fallback='cli')
        interaction_mode = config.get('app', 'INTERACTION_MODE', fallback='single_shot')
        model_name = config.get('app', 'MODEL_NAME', fallback='gemma3')
        web_host = config.get('web', 'HOST', fallback='127.0.0.1')
        web_port = config.getint('web', 'PORT', fallback=5000)

        print(f"--- Mode: {ui_mode.upper()} | Interaction: {interaction_mode.upper()} ---")

        # 2. Ollama 서버 및 모델 준비
        ollama_status = start_ollama()
        if ollama_status is None:
            # start_ollama now prints a detailed error message
            return

        if not pull_model_if_needed(model_name):
            print(f"'{model_name}' 모델을 준비할 수 없어 프로그램을 종료합니다.")
            return

        # 3. Few-Shot 예시 로드
        examples = []
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
            examples = load_examples(input_csv_paths, output_csv_paths)
            if examples: print(f"✅ 총 {len(examples)}개의 Few-Shot 예시를 성공적으로 불러왔습니다.")
            else: print("⚠️  불러온 예시가 없습니다.")
        else:
            print("💡 입력된 Few-Shot 예시 파일이 없습니다.")

        # 4. LLM 및 체인 설정
        llm = Ollama(model=model_name)
        chain = None

        if interaction_mode == 'conversational':
            system_message = "You are a helpful assistant. Based on the following examples, have a conversation.\n\n"
            for ex in examples:
                system_message += f"Query: {ex['query']}\nResponse: {ex['response']}\n\n"
            
            memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)
            prompt = ChatPromptTemplate.from_messages([
                ("system", system_message),
                MessagesPlaceholder(variable_name="chat_history"),
                ("human", "{user_query}"),
            ])
            chain = LLMChain(llm=llm, prompt=prompt, memory=memory, verbose=True)
        else: # single_shot 모드
            example_prompt = PromptTemplate.from_template("Query: {query}\nResponse: {response}")
            prompt = FewShotPromptTemplate(
                examples=examples,
                example_prompt=example_prompt,
                prefix="Here are some examples. Please follow this format.",
                suffix="Now, answer the following query:\nQuery: {user_query}",
                input_variables=["user_query"],
                example_separator="\n\n"
            )
            chain = LLMChain(llm=llm, prompt=prompt, verbose=True)

        # 5. UI 실행
        if ui_mode == 'web':
            run_web(chain, interaction_mode, web_host, web_port)
        else:
            run_cli(chain, interaction_mode)

    except FileNotFoundError as e:
        print(f"\n오류: {e}. 설정 파일을 확인해주세요.")
    except KeyboardInterrupt:
        print("\n사용자에 의해 프로그램이 중단되었습니다.")
    finally:
        # Unload the model from memory via API
        if ollama_status:
            stop_ollama(model_name)
        print("Application shut down.")

if __name__ == "__main__":
    main()
