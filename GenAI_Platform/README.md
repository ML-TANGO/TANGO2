# GenAI Platform

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Kubernetes](https://img.shields.io/badge/Kubernetes-1.24+-blue.svg)](https://kubernetes.io/)
[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)

GenAI Platform은 기업용 대규모 언어 모델 개발을 위한 완전한 LLMOps 플랫폼입니다. 현재 초기 버전으로 핵심 서비스들이 포함되어 있으며, 향후 추가 기능들이 개발될 예정입니다.

## 🎯 현재 포함된 구성요소

### ✅ 쿠버네티스 인프라 계층 (`devops/`)
완전한 MLOps 인프라 스택을 위한 핵심 구성요소들:

- **Storage & Database**
  - 분산 스토리지 및 데이터베이스 솔루션
  - 고가용성 클러스터 구성

- **Monitoring & Observability**
  - 메트릭 수집 및 모니터링 시스템
  - 중앙화된 로그 관리

- **DevOps & CI/CD**
  - GitOps 기반 배포 자동화
  - 소스 코드 관리 및 파이프라인

- **GPU & ML Infrastructure**
  - NVIDIA GPU 오퍼레이터
  - 분산 컴퓨팅 지원

### ✅ 핵심 마이크로서비스 (`apps/`)
현재 15개의 핵심 서비스가 포함되어 있습니다:

#### 데이터 관리 서비스
- **`fb_dashboard`** - 웹 기반 관리 인터페이스
- **`fb_dataset`** - 데이터셋 생명주기 관리
- **`fb_db`** - 데이터베이스 관리 서비스
- **`fb_image`** - 이미지 처리 및 관리

#### 모니터링 및 운영 서비스
- **`fb_log_middleware`** - 로그 수집 미들웨어
- **`fb_logger`** - 중앙화 로깅 시스템
- **`fb_monitoring`** - 시스템 헬스 모니터링
- **`fb_notification`** - 알림 시스템
- **`fb_resource_kube`** - 쿠버네티스 리소스 관리

#### 사용자 및 작업 관리 서비스
- **`fb_scheduler`** - 작업 스케줄링 및 리소스 할당
- **`fb_user`** - 사용자 인증 및 권한 관리
- **`fb_utils`** - 공통 유틸리티 라이브러리
- **`fb_workspace`** - 멀티테넌트 워크스페이스

#### 개발 지원 서비스
- **`walking_skeleton_python`** - Python 서비스 템플릿

### ✅ 공유 라이브러리 (`libs/`)
- **공통 ML 프레임워크**
  - 분산 훈련 지원
  - 모델 관리 유틸리티
  - 데이터 처리 라이브러리

## 🚧 향후 개발 예정

다음 서비스들이 현재 개발 중이며 향후 릴리스에 포함될 예정입니다:

### LLM 특화 서비스
- **`llm_model`** - LLM 모델 관리 및 서빙 서비스
- **`llm_playground`** - 대화형 LLM 실험 환경 (RAG, 프롬프트 엔지니어링, 테스트 배포 기능 포함)

## 🔧 빠른 시작

### 전제 조건
- **Kubernetes 클러스터**: v1.24+ (최소 3노드)
- **리소스 요구사항**:
  - CPU: 노드당 8+ 코어 권장
  - 메모리: 노드당 16GB+ 권장

### 설치 및 배포

```bash
# 1. 인프라 구성요소 배포
kubectl apply -k devops/

# 2. 마이크로서비스 배포
kubectl apply -k apps/

# 3. 서비스 확인
kubectl get pods -A
```

## 📁 디렉토리 구조

```
GenAI_Platform/
├── devops/                        # 쿠버네티스 인프라 구성요소
│   ├── aaai_efk/                  # 로그 수집 및 분석
│   ├── aaai_prometheus/           # 모니터링 스택
│   ├── aaai_argo/                 # GitOps 배포 자동화
│   └── ...                        # 기타 인프라 구성요소
│
├── apps/                          # 마이크로서비스
│   ├── fb_dashboard/              # 웹 관리 인터페이스
│   ├── fb_dataset/                # 데이터셋 관리
│   ├── fb_db/                     # 데이터베이스 관리
│   ├── fb_image/                  # 이미지 처리
│   ├── fb_log_middleware/         # 로그 미들웨어
│   ├── fb_logger/                 # 중앙 로깅
│   ├── fb_monitoring/             # 시스템 모니터링
│   ├── fb_notification/           # 알림 시스템
│   ├── fb_resource_kube/          # 리소스 관리
│   ├── fb_scheduler/              # 작업 스케줄링
│   ├── fb_user/                   # 사용자 관리
│   ├── fb_utils/                  # 공통 유틸리티
│   ├── fb_workspace/              # 워크스페이스
│   └── walking_skeleton_python/   # 서비스 템플릿
│
├── libs/                          # 공유 라이브러리
│   └── fb_bin/                    # ML 프레임워크
│
└── tools/                         # 개발 도구
```

## 💻 개발 가이드

### 로컬 개발 환경

```bash
# 서비스 개발
cd apps/fb_dashboard
pip install -r requirements.txt
./run.sh

# 또는 다른 서비스들
cd apps/fb_user
pip install -r requirements.txt
./run.sh
```

## 🤝 기여하기

현재 초기 버전으로, 플랫폼 완성을 위한 기여를 환영합니다:

1. **서비스 개선**: 기존 마이크로서비스 기능 강화
2. **새 서비스 추가**: 새로운 기능의 마이크로서비스 구현
3. **인프라 최적화**: 쿠버네티스 매니페스트 개선
4. **문서화**: 설치 가이드 및 API 문서 작성

## 📄 라이선스

이 프로젝트는 Apache License 2.0 하에 배포됩니다.

---

**참고**: 향후 `llm_model`과 `llm_playground` 서비스 추가를 통해 LLM 특화 기능을 강화할 예정입니다.