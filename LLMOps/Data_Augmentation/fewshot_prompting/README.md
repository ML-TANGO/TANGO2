# Ollama & LangChain 기반 Few-Shot Prompting 

사용자가 제시하는 Few-Shot 예시를 통해 LLM이 유사하게 동작할 수 있도록 유도합니다. LangChain과 DSPy를 활용한 프롬프트 엔지니어링이 지원되며, LLM과 상호작용할 수 있는 CLI 및 웹 GUI 인터페이스를 제공합니다.

## 주요 기능

- **Ollama 자동 연동**: 사용자 시스템에서 서비스 중인 Ollama 서버에 접근하여 LLM 애플리케이션을 구동시킵니다. API를 통해 모델을 효율적으로 관리하며, 애플리케이션 종료 시 모델을 메모리에서 해제하여 시스템 리소스를 정리합니다.
- **DSPy 프롬프트 최적화**: DSPy 프레임워크를 통합하여, 데이터에 가장 적합한 **지시문(Instructions)**과 **Few-Shot 예제 세트**를 자동으로 학습하고 최적화합니다. (`BootstrapFewShot`, `MIPROv2` 등 지원)
- **프롬프트 관리**: YAML 파일을 통해 다양한 버전의 프롬프트를 정의하고 관리합니다. `active_version` 설정으로 ReFlexion, CoT 등 다양한 프롬프트 전략을 즉시 교체하여 테스트할 수 있습니다.
- **Few-Shot 예시 구성**: 여러 쌍의 `input.csv`와 `output.csv` 파일을 예시로 제공할 수 있습니다.
- **CLI & 웹 GUI 지원**: `config.ini` 파일의 `UI_MODE` 설정(`cli` 또는 `web`)에 따라 인터페이스를 선택할 수 있습니다.
- **상호작용 모드 선택**: `INTERACTION_MODE` 설정을 통해, 단일 응답 모드(`single_shot`)와 대화 기록을 기억하는 대화 모드(`conversational`)를 선택할 수 있습니다.
- **중앙 설정 관리**: `config.ini` 파일을 통해 Ollama 모델, UI 모드, 웹 서버 주소, 상호작용 방식 등 주요 설정을 변경할 수 있습니다.
- **대화 내용 로깅**: 사용자와 LLM 간의 모든 상호작용은 `conversation_log.txt` 파일에 기록되며, 배치 처리 결과는 `csv_query_responses.log`에 별도로 저장됩니다.

## 기술 스택

- **LLM**: Ollama (로컬 환경에서 모델 실행)
- **Framework**: LangChain (`langchain_ollama`, `langchain`), Flask (웹 GUI)
- **Prompt Optimization**: DSPy
- **Language**: Python
- **Data & Config**: `pandas` (CSV), `PyYAML` (프롬프트 설정)

## 설치 및 설정

1.  **설정 파일(`config.ini`) 수정**
    실행 전 `config.ini` 파일을 열어 원하는 설정을 구성합니다.

    ```ini
    [ollama]
    MODEL_NAME = gemma:4b      ; 사용할 Ollama 모델 이름
    
    [ui]
    UI_MODE = cli              ; 인터페이스 선택 (cli 또는 web)
    
    [web_server]
    HOST = 0.0.0.0             ; 웹 서버 호스트
    PORT = 7860                ; 웹 서버 포트
    
    [interaction]
    INTERACTION_MODE = single_shot ; conversational / single_shot

    [DSPY]
    USE_DSPY = yes             ; DSPy 최적화 사용 여부 (yes/no)
    OPTIMIZER = MIPROv2        ; 최적화 알고리즘 (BootstrapFewShot, MIPROv2 등)
    METRIC = bert_score        ; 평가 지표 (bert_score 또는 jaccard)
    ```
    - `setup.sh` 실행 시 `MODEL_NAME`에 지정된 모델을 자동으로 `pull` 합니다.

2.  **자동 설치 스크립트 실행**
    `setup.sh` 스크립트는 OS를 감지하여 Ollama를 설치하고, `requirements.txt`에 명시된 Python 라이브러리를 설치합니다.

    ```bash
    bash setup.sh
    ```

## 프롬프트 시스템 (Advanced)

### 1. DSPy 프롬프트 최적화
- **자동 학습**: `USE_DSPY = yes` 설정 시, 입력된 데이터를 기반으로 최적의 프롬프트를 자동으로 컴파일합니다. 특히 `MIPROv2` 옵티마이저는 모델의 지시문까지 직접 수정하여 성능을 극대화합니다.
- **결과 확인**: 최적화가 완료되면 터미널 로그에 **[Optimized Program Details]**가 출력됩니다. 여기서 DSPy가 생성한 최종 지시문과 선택된 핵심 예제들을 직접 확인할 수 있습니다.
- **정량적 평가**: BERTScore 또는 Jaccard 유사도를 지표로 사용하여 응답의 품질을 객관적으로 검증합니다.

### 2. 프롬프트 버전 관리 (Prompt Versioning)
이 프로젝트는 `prompts/prompt_versions.yml` 파일을 통해 강력한 버전 관리 기능을 제공합니다.
- **버전 정의**: `versions` 섹션에 기본형, ReFlexion(자기비평), CoT(단계별 추론) 등 다양한 전략을 정의합니다.
- **버전 선택**: `active_version` 값을 변경하는 것만으로 실행 중인 전략을 즉시 교체할 수 있습니다.

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
    Few-Shot 예시로 사용할 CSV 파일 경로를 입력해주세요.
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

    d. Few-shot 예시들을 랜덤 셔플할지 결정합니다.

    e. 입력한 파일의 개수가 맞으면 예시 로딩이 완료되고 다음 단계로 진행됩니다.

## 사용 방법

### CLI 모드

- **대화 모드**: 터미널에 직접 질문을 입력하여 LLM과 실시간으로 대화할 수 있습니다. `quit` 또는 `exit`를 입력하여 종료합니다.
- **배치 처리 모드 (`csv_query`)**:
    - 프롬프트에서 `csv_query`를 입력하여 배치 모드를 시작할 수 있습니다.
    - 이 모드에서는 터미널에 직접 CSV 형식의 데이터를 붙여넣고, 마지막 줄에 `END_CSV`를 입력하여 여러 쿼리를 한 번에 처리할 수 있습니다.
    - `file_name` 컬럼을 기준으로 쿼리가 그룹화되어 처리됩니다.
    - **결과 저장**: 화면 출력 외에 `csv_query_responses.log` 파일에 결과가 별도로 기록됩니다.

### 웹 GUI 모드

- `UI_MODE`를 `web`으로 설정하고 실행하면, 자동으로 웹 브라우저가 열리며 채팅 인터페이스가 나타납니다.
- (만약 자동으로 열리지 않으면 http://[HOST]:[PORT] 주소로 접속)
- 웹 페이지의 입력창을 통해 LLM과 실시간으로 대화할 수 있습니다.
