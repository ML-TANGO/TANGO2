# 온실 자율 제어 시스템 (SDF/train)

## 프로젝트 개요
온실 자율 제어 시스템은 기상 데이터와 센서 데이터를 수집하여 **거시 계획 모델(xLAM2)**이 하루 온도 계획을 수립하고, **미시 제어 모델(LightGBM)**이 1분 단위로 모터를 제어하는 분리형 아키텍처를 기반으로 합니다.

## 프로젝트 구조

```
train(프로젝트 루트)/
├── src/
│   ├── __init__.py
│   ├── data_collection/          # 데이터 수집 및 적재
│   │   ├── __init__.py
│   │   ├── weather_api.py        # 기상청 API 호출
│   │   ├── query_builder.py      # DB 쿼리 생성 (센서별/채널별)
│   │   └── db_client.py          # PostgreSQL 연결 및 쿼리 실행
│   ├── processing/               # 데이터 전처리 및 가공
│   │   ├── __init__.py
│   │   ├── time_sync.py          # 시계열 동기화 (리샘플링, merge_asof)
│   │   └── feature_gen.py        # 피처 생성 (diff, rolling, time)
│   ├── pipeline.py               # 전체 파이프라인 제어
│   ├── pipeline_preprocessing.py # 전처리 전용 함수
│   └── utils.py                  # 상수 및 유틸리티
├── config/                       # 설정 파일
│   ├── settings.yaml             # DB/API 환경 설정
│   └── *.yaml                    # 쿼리 설정 파일
├── tests/                        # 단위 테스트
│   ├── conftest.py               # 공통 테스트 설정
│   ├── test_data_collection/
│   ├── test_processing/
│   └── test_pipeline.py
├── SKILLS/                       # 개발 가이드
│   └── 개발방법론.md
├── notebook/                     # Jupyter 노트북
├── plots/                        # 시각화 결과
├── primitive_data/               # 원시 데이터 저장 (날짜별 폴더)
├── data_inspect/                 # 데이터 검증 및 분석
│   ├── scripts/                  # 분석 스크립트
│   └── output/                   # 분석 결과
├── main.py                       # 진입점
├── requirements.txt              # 의존성 패키지
└── README.md
```


## 실행 방법

### 1. 환경 설정
```bash
conda activate llm_env
pip install -r requirements.txt
```

### 2. 데이터 수집
```bash
# 파일 입력 모드 (config 파일 사용)
python main.py --config config/260526_query.yaml

# 데이터는 primitive_data/YYYYMMDD_HHMMSS/ 폴더에 저장됨
```

### 3. 테스트 실행
```bash
pytest tests/
```

## 주요 파일 설명

### main.py
- 진입점 (메뉴: 1=DB수집, 2=기상청API, 3=전처리)
- KST → UTC 시간대 변환 처리
- 날짜별 폴더 생성 로직

### src/pipeline.py
- DataPipeline 클래스 (수집→전처리→저장 총괄)
- `run_db_load()`: DB 데이터 수집
- `save_results_to_files()`: 센서별 파일 저장
- `tideup_collect_data()`: 센서별 폴더 정리

### src/pipeline_preprocessing.py
- 전처리 전용 함수
- 메타데이터 로드
- 프레임 구축
- 시간 동기화

### src/utils.py
- COLUMN_LIST, COLUMN_CONDITION 상수
- SENSOR_THRESHOLD 상수

## Git 관리
- 데이터 파일은 `.gitignore`로 제외
- 폴더 구조 유지를 위해 `.gitkeep` 파일 사용
- 백업 파일은 제외
