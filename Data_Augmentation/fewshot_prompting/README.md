# Ollama & LangChain 기반 Few-Shot Prompting 

사용자가 제시하는 Few-Shot 예시를 통해 LLM이 유사하게 동작할 수 있도록 유도합니다. LLM과 상호작용할 수 있는 CLI 및 웹 GUI 인터페이스를 제공합니다.

## 주요 기능

- **Ollama 자동 연동**: 애플리케이션 실행 시 Ollama 서버 프로세스를 자동으로 시작하고, 종료 시 함께 중단합니다.
- **Few-Shot 예시 구성**: 여러 쌍의 `input.csv`와 `output.csv` 파일을 예시로 제공할 수 있습니다.
- **CLI & 웹 GUI 지원**: `config.ini` 파일의 `UI_MODE` 설정(`cli` 또는 `web`)에 따라 인터페이스를 선택할 수 있습니다.
- **상호작용 모드 선택**: `INTERACTION_MODE` 설정을 통해, 단일 응답 모드(`single_shot`)와 대화 기록을 기억하는 대화 모드(`conversational`)를 선택할 수 있습니다.
- **중앙 설정 관리**: `config.ini` 파일을 통해 Ollama 모델, UI 모드, 웹 서버 주소, 상호작용 방식 등 주요 설정을 변경할 수 있습니다.
- **대화 내용 로깅**: 사용자와 LLM 간의 모든 상호작용은 `conversation_log.txt` 파일에 자동으로 기록됩니다.

## 기술 스택

- **LLM**: Ollama (로컬 환경에서 모델 실행)
- **Framework**: LangChain (`langchain_ollama`, `langchain`), Flask (웹 GUI)
- **Language**: Python
- **Data Handling**: `pandas` (CSV 파일 처리)

## 설치 및 설정

1.  **설정 파일(`config.ini`) 수정**
    실행 전 `config.ini` 파일을 열어 원하는 설정을 구성합니다.

    ```ini
    [ollama]
    MODEL_NAME = gemma:2b      ; 사용할 Ollama 모델 이름
    
    [ui]
    UI_MODE = cli              ; 인터페이스 선택 (cli 또는 web)
    
    [web_server]
    HOST = 0.0.0.0             ; 웹 서버 호스트
    PORT = 7860                ; 웹 서버 포트
    
    [interaction]
    INTERACTION_MODE = conversational ; single_shot 또는 conversational
    ```
    - `setup.sh` 실행 시 `MODEL_NAME`에 지정된 모델을 자동으로 `pull` 합니다.

2.  **자동 설치 스크립트 실행**
    `setup.sh` 스크립트는 OS를 감지하여 Ollama를 설치하고, `requirements.txt`에 명시된 Python 라이브러리를 설치합니다.

    ```bash
    bash setup.sh
    ```

## 실행 방법

1.  **Few-Shot 데이터 준비 (선택 사항)**
    - Few-shot 예시를 사용하려면 `input.csv`와 `output.csv` 같은 형식의 파일을 준비합니다.

2.  **애플리케이션 실행 및 Few-Shot 데이터 지정**
    
    애플리케이션을 실행하고 Few-shot 예시를 지정하는 방법은 다음과 같습니다.

    a. 터미널에서 아래 명령어로 애플리케이션을 시작합니다.
    ```bash
    python main.py
    ```

    b. **입력(Input) CSV 파일 경로**를 입력하라는 메시지가 나타납니다. 첫 번째 입력 파일의 경로를 쓰고 Enter를 누릅니다. 이어서 다음 입력 파일 경로를 입력하는 과정을 반복합니다.
    ```
    🤖 Few-Shot 예시로 사용할 CSV 파일 경로를 입력해주세요.
       - 경로 입력을 마치려면 그냥 Enter를 누르세요.
    ==================================================
    입력(Input) CSV 파일 경로 #1: input.csv
    입력(Input) CSV 파일 경로 #2: 
    ```
    > **Note:** Few-shot 예시를 사용하지 않으려면 이 단계에서 아무것도 입력하지 않고 Enter를 누르면 됩니다.

    c. 모든 입력 파일 경로를 입력했다면, 이어서 **출력(Output) CSV 파일 경로**를 입력하라는 메시지가 나타납니다. 각 입력 파일에 대응하는 출력 파일의 경로를 순서대로 입력합니다.
    ```
    출력(Output) CSV 파일 경로 #1: output.csv
    ```

    d. 입력한 파일의 개수가 맞으면 예시 로딩이 완료되고 다음 단계로 진행됩니다.

## 사용 방법

### CLI 모드

- 터미널에 직접 질문을 입력하여 LLM과 대화할 수 있습니다.
- `quit` 또는 `exit`를 입력하여 프로그램을 종료합니다.

### 웹 GUI 모드

- `UI_MODE`를 `web`으로 설정하고 실행하면, 자동으로 웹 브라우저가 열리며 채팅 인터페이스가 나타납니다.
- (만약 자동으로 열리지 않으면 http://[HOST]:[PORT] 주소로 접속)
- 웹 페이지의 입력창을 통해 LLM과 실시간으로 대화할 수 있습니다.
