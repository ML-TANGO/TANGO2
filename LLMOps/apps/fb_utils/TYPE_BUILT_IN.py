# BUILT IN
"""
1.  텍스트 (Text)
텍스트 증강 (Text Augmentation)
텍스트 정제 (Text Cleaning)
토큰화 및 임베딩 생성 (Tokenization & Embedding Generation)
구문 재배열 (Syntactic Reordering)
규칙 기반 패러프레이즈 생성 (Rule-Based Paraphrase Generation)
의미 필터링 (Semantic Filtering)
2. 이미지 (Image)
이미지 증강 (Image Augmentation)
정규화 및 표준화 (Normalization & Standardization)
믹스업/CutMix (MixUp/CutMix)
아핀 및 원근 변환 (Affine & Perspective Transformation)
랜덤 지우기 (Random Erasing)
색상 및 조명 조정 (Color and Illumination Adjustment)
3. 테이블 (Tabular)
결측값 처리 (Missing Value Handling)
형식 변환 (Format Conversion - JSON to CSV)
스케일링 및 정규화 (Scaling & Normalization)
범주형 인코딩 (Categorical Encoding)
통계적 리샘플링 (Statistical Resampling)
특징 공학 및 변환 (Feature Engineering & Transformation)
4. 비디오 (Video)
스펙트럴 증강 (Spectral Augmentation)
프레임 추출 및 재구성 (Frame Extraction & Recomposition)
시공간 증강 (Spatio-Temporal Augmentation)
동적 프레임 보간 (Dynamic Frame Interpolation)
지역 수준 증강 (Region-Level Augmentation)
동적 색상 및 조명 조정 (Dynamic Color & Illumination Adjustment)
5. 오디오 (Audio)
시간-주파수 증강 (Time-Frequency Augmentation)
스펙트로그램 분석 및 변환 (Spectrogram Analysis & Transformation)
피치 및 시간 스케일링 (Pitch & Time Scaling)
고조파 왜곡 (Harmonic Distortion)
노이즈 주입 (Noise Injection)
다이나믹 레인지 압축 변형 (Dynamic Range Compression Variation)
"""
# DATA TYPES
# PREPROCESSING_BUILT_IN_TEXT_TYPE = "Text"
PREPROCESSING_BUILT_IN_IMAGE_TYPE = "Image"
PREPROCESSING_BUILT_IN_TABULAR_TYPE = "Tabular"
# PREPROCESSING_BUILT_IN_VIDEO_TYPE = "Video"
# PREPROCESSING_BUILT_IN_AUDIO_TYPE = "Audio"

PREPROCESSING_BUILT_IN_DATA_TYPES = [
    # PREPROCESSING_BUILT_IN_TEXT_TYPE,
    PREPROCESSING_BUILT_IN_IMAGE_TYPE,
    PREPROCESSING_BUILT_IN_TABULAR_TYPE,
    # PREPROCESSING_BUILT_IN_VIDEO_TYPE,
    # PREPROCESSING_BUILT_IN_AUDIO_TYPE
] 

# TFS
IMAGE_AUGMENT = "데이터셋 내 이미지 증강 (Image Augmentation in given dataset)"
MARKER_ANALYSIS = "Marker 라벨링 json 데이터 csv 변환(Marker result json to csv)"
TEXT_AUGMENT = "텍스트 증강 (Text Augmentation)"
TEXT_CLEANING = "텍스트 정제 (Text Cleaning)"
TOKENIZATION_EMBEDDING = "토큰화 및 임베딩 생성 (Tokenization & Embedding Generation)"
SYNTACTIC_REORDERING = "구문 재배열 (Syntactic Reordering)"
RULE_BASED_PARAPHRASE = "규칙 기반 패러프레이즈 생성 (Rule-Based Paraphrase Generation)"
SEMANTIC_FILTERING = "의미 필터링 (Semantic Filtering)"
NORMALIZATION_STANDARDIZATION = "정규화 및 표준화 (Normalization & Standardization)"
MIXUP_CUTMIX = "믹스업/CutMix (MixUp/CutMix)"
AFFINE_TRANSFORMATION = "아핀 및 원근 변환 (Affine & Perspective Transformation)"
RANDOM_ERASING = "랜덤 지우기 (Random Erasing)"
COLOR_ADJUSTMENT = "색상 및 조명 조정 (Color and Illumination Adjustment)"
MISSING_VALUE_HANDLING = "결측값 처리 (Missing Value Handling)"
SCALING_NORMALIZATION = "스케일링 및 정규화 (Scaling & Normalization)"
CATEGORICAL_ENCODING = "범주형 인코딩 (Categorical Encoding)"
STATISTICAL_RESAMPLING = "통계적 리샘플링 (Statistical Resampling)"
FEATURE_ENGINEERING = "특징 공학 및 변환 (Feature Engineering & Transformation)"
SPECTRAL_AUGMENTATION = "스펙트럴 증강 (Spectral Augmentation)"
FRAME_EXTRACTION = "프레임 추출 및 재구성 (Frame Extraction & Recomposition)"
SPATIO_TEMPORAL_AUGMENTATION = "시공간 증강 (Spatio-Temporal Augmentation)"
DYNAMIC_FRAME_INTERPOLATION = "동적 프레임 보간 (Dynamic Frame Interpolation)"
REGION_LEVEL_AUGMENTATION = "지역 수준 증강 (Region-Level Augmentation)"
DYNAMIC_COLOR_ADJUSTMENT = "동적 색상 및 조명 조정 (Dynamic Color & Illumination Adjustment)"
TIME_FREQUENCY_AUGMENTATION = "시간-주파수 증강 (Time-Frequency Augmentation)"
SPECTROGRAM_ANALYSIS = "스펙트로그램 분석 및 변환 (Spectrogram Analysis & Transformation)"
PITCH_TIME_SCALING = "피치 및 시간 스케일링 (Pitch & Time Scaling)"
HARMONIC_DISTORTION = "고조파 왜곡 (Harmonic Distortion)"
NOISE_INJECTION = "노이즈 주입 (Noise Injection)"
DYNAMIC_RANGE_COMPRESSION = "다이나믹 레인지 압축 변형 (Dynamic Range Compression Variation)"

# TFS PARAM

PREPROCESSING_TFS_PARAM = {
    IMAGE_AUGMENT : ["image_dir", "result_file_name","result_dir_name","target_answer"], # "input_csv",
    MARKER_ANALYSIS : ["result_file_name"],
    TEXT_AUGMENT: ["text_data", "augmentation_rules"],
    TEXT_CLEANING: ["text_data", "cleaning_rules"],
    TOKENIZATION_EMBEDDING: ["text_data", "tokenization_method"],
    SYNTACTIC_REORDERING: ["text_data", "reordering_rules"],
    RULE_BASED_PARAPHRASE: ["text_data", "paraphrase_rules"],
    SEMANTIC_FILTERING: ["text_data", "filtering_rules"],
    NORMALIZATION_STANDARDIZATION: ["image_data", "normalization_params"],
    MIXUP_CUTMIX: ["image_data", "mixup_cutmix_params"],
    AFFINE_TRANSFORMATION: ["image_data", "transformation_params"],
    RANDOM_ERASING: ["image_data", "erasing_params"],
    COLOR_ADJUSTMENT: ["image_data", "adjustment_params"],
    MISSING_VALUE_HANDLING: ["table_data", "handling_method"],
    SCALING_NORMALIZATION: ["table_data", "scaling_params"],
    CATEGORICAL_ENCODING: ["table_data", "encoding_method"],
    STATISTICAL_RESAMPLING: ["table_data", "resampling_params"],
    FEATURE_ENGINEERING: ["table_data", "engineering_params"],
    SPECTRAL_AUGMENTATION: ["video_data", "augmentation_params"],
    FRAME_EXTRACTION: ["video_data", "extraction_params"],
    SPATIO_TEMPORAL_AUGMENTATION: ["video_data", "augmentation_params"],
    DYNAMIC_FRAME_INTERPOLATION: ["video_data", "interpolation_params"],
    REGION_LEVEL_AUGMENTATION: ["video_data", "augmentation_params"],
    DYNAMIC_COLOR_ADJUSTMENT: ["video_data", "adjustment_params"],
    TIME_FREQUENCY_AUGMENTATION: ["audio_data", "augmentation_params"],
    SPECTROGRAM_ANALYSIS: ["audio_data", "analysis_params"],
    PITCH_TIME_SCALING: ["audio_data", "scaling_params"],
    HARMONIC_DISTORTION: ["audio_data", "distortion_params"],
    NOISE_INJECTION: ["audio_data", "noise_params"],
    DYNAMIC_RANGE_COMPRESSION: ["audio_data", "compression_params"]
}

# TFS SCRIPT
PREPROCESSING_TFS_SCRIPT = {
    IMAGE_AUGMENT : "preprocessing_augment.py",
    MARKER_ANALYSIS : "preprocess_marker_json.py",
    TEXT_AUGMENT: "text_augmentation.py",
    TEXT_CLEANING: "text_cleaning.py",
    TOKENIZATION_EMBEDDING: "tokenization_embedding.py",
    SYNTACTIC_REORDERING: "syntactic_reordering.py",
    RULE_BASED_PARAPHRASE: "rule_based_paraphrase.py",
    SEMANTIC_FILTERING: "semantic_filtering.py",
    NORMALIZATION_STANDARDIZATION: "image_normalization.py",
    MIXUP_CUTMIX: "mixup_cutmix.py",
    AFFINE_TRANSFORMATION: "affine_transformation.py",
    RANDOM_ERASING: "random_erasing.py",
    COLOR_ADJUSTMENT: "color_adjustment.py",
    MISSING_VALUE_HANDLING: "missing_value_handling.py",
    SCALING_NORMALIZATION: "scaling_normalization.py",
    CATEGORICAL_ENCODING: "categorical_encoding.py",
    STATISTICAL_RESAMPLING: "statistical_resampling.py",
    FEATURE_ENGINEERING: "feature_engineering.py",
    SPECTRAL_AUGMENTATION: "spectral_augmentation.py",
    FRAME_EXTRACTION: "frame_extraction.py",
    SPATIO_TEMPORAL_AUGMENTATION: "spatio_temporal_augmentation.py",
    DYNAMIC_FRAME_INTERPOLATION: "dynamic_frame_interpolation.py",
    REGION_LEVEL_AUGMENTATION: "region_level_augmentation.py",
    DYNAMIC_COLOR_ADJUSTMENT: "dynamic_color_adjustment.py",
    TIME_FREQUENCY_AUGMENTATION: "time_frequency_augmentation.py",
    SPECTROGRAM_ANALYSIS: "spectrogram_analysis.py",
    PITCH_TIME_SCALING: "pitch_time_scaling.py",
    HARMONIC_DISTORTION: "harmonic_distortion.py",
    NOISE_INJECTION: "noise_injection.py",
    DYNAMIC_RANGE_COMPRESSION: "dynamic_range_compression.py"
}

PREPROCESSING_BUILT_IN_DATA_TYPE_TFS = {
    # PREPROCESSING_BUILT_IN_TEXT_TYPE : [
    #     TEXT_AUGMENT,
    #     TEXT_CLEANING,
    #     TOKENIZATION_EMBEDDING,
    #     SYNTACTIC_REORDERING,
    #     RULE_BASED_PARAPHRASE,
    #     SEMANTIC_FILTERING
    # ],
    PREPROCESSING_BUILT_IN_IMAGE_TYPE : [
        IMAGE_AUGMENT,
        # NORMALIZATION_STANDARDIZATION,
        # MIXUP_CUTMIX,
        # AFFINE_TRANSFORMATION,
        # RANDOM_ERASING,
        # COLOR_ADJUSTMENT
    ],
    PREPROCESSING_BUILT_IN_TABULAR_TYPE : [
        MARKER_ANALYSIS,
        # MISSING_VALUE_HANDLING,
        # SCALING_NORMALIZATION,
        # CATEGORICAL_ENCODING,
        # STATISTICAL_RESAMPLING,
        # FEATURE_ENGINEERING
    ],
    # PREPROCESSING_BUILT_IN_VIDEO_TYPE : [
    #     SPECTRAL_AUGMENTATION,
    #     FRAME_EXTRACTION,
    #     SPATIO_TEMPORAL_AUGMENTATION,
    #     DYNAMIC_FRAME_INTERPOLATION,
    #     REGION_LEVEL_AUGMENTATION,
    #     DYNAMIC_COLOR_ADJUSTMENT
    # ],
    # PREPROCESSING_BUILT_IN_AUDIO_TYPE : [
    #     TIME_FREQUENCY_AUGMENTATION,
    #     SPECTROGRAM_ANALYSIS,
    #     PITCH_TIME_SCALING,
    #     HARMONIC_DISTORTION,
    #     NOISE_INJECTION,
    #     DYNAMIC_RANGE_COMPRESSION
    # ]
}




# =========================================================
# 학습
# =========================================================

"""
>의료 (Healthcare/Medical AI Solutions)
화상 심도 탐지
욕창 심도 예측
우울증 조기 진단  
전립선 증식증 감별 진단  <-SW1가 바뀐것
전립선 증식증 예후 예측  <-SW2가 바뀐것
전립선 초음파 영상 기반 세그멘테이션 <- SAM 이 바뀐것
 
>시각 (Object detection AI Solutions)
DNA+ 드론 균열 탐지
DNA+ 드론 녹 탐지
스마트 감시 객체 분석
CCTV 객체 탐지기
OX 플래카드 실시간 탐지기
손 제스쳐 탐지기
 
>대화 생성 (Dialogue Generation)
자율주행 상황 인식을 위한 LLM 기반 개체명 인식
다중 도메인 LLM 기반 대화 생성
고객 서비스 AI 대응
의료 상담 대화 생성
기계 번역 기반 대화
 
>자연어 이해 (Natural Language Understanding)
텍스트 개체명 인식 
SW 코드 결함 탐지
의료 기록 개체명 인식 
법률 문서 분석
기술 문서 내용 추출
 
>감성 (Sentiment Analysis)
복합 감성 분석
텍스트 기반 감정 변화 추적
고객 피드백 감정 분석
사용자 의도 기반 감성 분류
멀티모달 감성 추론
 
>공감 (Emphathy Analysis)
대화 맥락 공감 분석
감정 기반 공감 피드백 생성
정신 건강 대화 공감
사용자 반응 공감 추론
감정 연관 대화 공감기
"""
 
MEDICAL = "의료 (Healthcare/Medical AI Solutions)"
EMPATHY_SENTIMENT_ANALYSIS = "공감감성지능  (Emphathy Sentiment Analysis)"
NATURAL_LANGUAGE_UNDERSTANDING = "자연어 이해 (Natural Language Understanding)"
VISION = "시각 (Object detection AI Solutions)"
DIALOGUE_GENERATION = "대화 생성 (Dialogue Generation)"

BUILT_IN_MODEL_CATEGORY = [
    MEDICAL,
    EMPATHY_SENTIMENT_ANALYSIS,
    NATURAL_LANGUAGE_UNDERSTANDING,
    VISION,
    DIALOGUE_GENERATION,
]

BUILT_IN_MODELS_BY_CATEGORY = {
    MEDICAL: [
        {
            "name": "화상 심도 탐지",
            "huggingface_model_id": "Acryl-aLLM/BurnDepthAnalysisIntelligence",
            "target_metric" : "Val_loss",
            "readme" : "",
            "deploy_params" : [],
            "system_params" : [
                {
                    "name" : "dataset_csv_file",
                    "type" : "str",
                    "format" : "{data_path}/meta.csv",
                },
                {
                    "name" : "image_dir",
                    "type" : "str",
                    "format" : "{data_path}/meta.csv",
                },
                {
                    "name" : "final_checkpoint_file",
                    "type" : "str",
                    "format" : "{checkpoint_file}",
                },
                ],
            "user_params" : [
                {
                "name" : "batch", 
                "default_value" : 32,
                "description" : "",
                "type" : "int"
                },
                {
                "name" : "num_workers", 
                "default_value" : 16,
                "description" : "",
                "type" : "int"
                },
                {
                "name" : "max_epoch", 
                "default_value" : 20,
                "description" : "",
                "type" : "int"
                },
                {
                "name" : "lr", 
                "default_value" : 1e-5,
                "description" : "",
                "type" : "float"
                },
            ]
        },
        {"name": "욕창 심도 예측", "huggingface_model_id": ""},
        {"name": "SAM", "huggingface_model_id": ""},
        {"name": "우울증 조기 진단", "huggingface_model_id": ""},
        {"name": "전립선 증식증 감별 진단", "huggingface_model_id": ""},
        {"name": "전립선 증식증 예후 예측", "huggingface_model_id": ""},
    ],
    EMPATHY_SENTIMENT_ANALYSIS: [
        {
            "name": "대화 맥락 공감 분석",
            "huggingface_model_id": "Acryl-aLLM/Text-Empathy",
        }
    ],
    NATURAL_LANGUAGE_UNDERSTANDING: [
        {
            "name": "개체명 인식 모델",
            "huggingface_model_id": "Acryl-aLLM/Named-Entity-Recognition",
        },
        {
            "name": "sw 오류수정 모델 v0.1",
            "huggingface_model_id": "Acryl-Jonathan/coder-0.1",
        },
        {
            "name": "sw 오류수정 모델 v0.2",
            "huggingface_model_id": "Acryl-Jonathan/coder-0.2",
        },
    ],
    VISION: [
        {
            "name": "DNA+ 드론 균열 탐지 모델",
            "huggingface_model_id": "Acryl-aLLM/dna_pothole_crack",
        },
        {
            "name": "DNA+ 드론 녹 탐지 모델",
            "huggingface_model_id": "Acryl-aLLM/dna_rust",
        },
        {"name": "DNA+ 드론 도로 결함 탐지 모델", "huggingface_model_id": ""},
    ],
    # RECOMMENDATION: [
    #     {"name": "기입 예정(조나단)", "huggingface_model_id": ""},
    #     {"name": "기입 예정(조나단)", "huggingface_model_id": ""},
    # ],
    DIALOGUE_GENERATION: [
        {"name": "대화모델", "huggingface_model_id": ""},
        {
            "name": "자율주행 LLM-NER 모델",
            "huggingface_model_id": "Acryl-Jonathan-2/autodrive-ner",
        },
    ],
}


BUILT_IN_MODEL_LOOKUP_BY_HF = {
    category: {model["huggingface_model_id"]: model["name"] for model in models if model["huggingface_model_id"]}
    for category, models in BUILT_IN_MODELS_BY_CATEGORY.items()
}

# =========================================================
# 파이프라인
# =========================================================

PIPELINE_BUILT_IN_HEALTHCARE_TYPE =  "헬스케어"
PIPELINE_BUILT_IN_MANUFACTURING_TYPE = "제조"

PIPELINE_BUILT_IN_TYPES = [PIPELINE_BUILT_IN_HEALTHCARE_TYPE, PIPELINE_BUILT_IN_MANUFACTURING_TYPE]




PIPELINE_BUILT_IN_HEALTHCARE_LIST =  [
    "피부질환", "정신질환", "비뇨기질환"
]

PIPELINE_BUILT_IN_MANUFACTURING_LIST = [
    "불량 판별", "품질 분석", "품질 예측"
]

PIPELINE_BUILT_IN = {
    PIPELINE_BUILT_IN_HEALTHCARE_TYPE : PIPELINE_BUILT_IN_HEALTHCARE_LIST,
    PIPELINE_BUILT_IN_MANUFACTURING_TYPE : PIPELINE_BUILT_IN_MANUFACTURING_LIST
}