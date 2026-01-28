# GenAI Platform

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Kubernetes](https://img.shields.io/badge/Kubernetes-1.24+-blue.svg)](https://kubernetes.io/)
[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)

GenAI Platform은 기업용 대규모 언어 모델 개발을 위한 완전한 LLMOps 플랫폼입니다. 현재 초기 버전으로 핵심 서비스들이 포함되어 있으며, 향후 추가 기능들이 개발될 예정입니다.

## 🎯 현재 포함된 구성요소

### ✅ 쿠버네티스 인프라 계층 (`devops/`)
쿠버네티스 기반 운영/배포를 위한 Helm 차트 및 실행 스크립트가 포함되어 있습니다.

- **주요 인프라 차트(예시)**
  - **NFS Provisioner**: `devops/gaip_nfs_provisioner/`
  - **(Optional) MetalLB**: `devops/gaip_metallb/`
  - **Kong(Ingress)**: `devops/gaip_kong/`
  - **Registry**: `devops/gaip_registry/`
  - **MariaDB**: `devops/gaip_maraidb/`
  - **Kafka**: `devops/gaip_kafka/`
  - **Redis**: `devops/gaip_redis/`
  - **MongoDB**: `devops/gaip_mongodb/`
  - **Prometheus/Grafana**: `devops/gaip_prometheus/`
  - **EFK**: `devops/gaip_efk/`
  - **GPU Operators**: `devops/gaip_gpu_operators/`

> 설치 순서/값 설정/주의사항은 `devops/INSTALL.md`에 정리되어 있습니다.

### ✅ 핵심 마이크로서비스 (`apps/`)
현재 포함된 서비스(디렉토리 기준):

#### 데이터 관리 서비스
- **`fb_dashboard`** - 웹 기반 관리 인터페이스
- **`fb_dataset`** - 데이터셋 생명주기 관리
- **`fb_image`** - 이미지 처리 및 관리

#### 모니터링 및 운영 서비스
- **`fb_log_middleware`** - 로그 수집 미들웨어
- **`fb_logger`** - 중앙화 로깅 시스템
- **`fb_monitoring`** - 시스템 헬스 모니터링
- **`fb_notification`** - 알림 시스템
- **`fb_resource`** - 쿠버네티스 리소스/스토리지 관리

#### 사용자 및 작업 관리 서비스
- **`fb_scheduler`** - 작업 스케줄링 및 리소스 할당
- **`fb_user`** - 사용자 인증 및 권한 관리
- **`fb_utils`** - 공통 유틸리티 라이브러리
- **`fb_workspace`** - 멀티테넌트 워크스페이스

#### LLM 서비스
- **`llm_model`** - LLM 모델 다운로드/관리 및 서빙 관련 기능
- **`llm_playground`** - 대화형 LLM 실험 환경(프롬프트/RAG/테스트)
- **`llm_rag`** - RAG API 서비스

### ✅ 공유 라이브러리 (`libs/`)
- **공통 ML 프레임워크**
  - 분산 훈련 지원
  - 모델 관리 유틸리티
  - 데이터 처리 라이브러리

## 🔧 빠른 시작

### 전제 조건
- **Kubernetes 클러스터**: v1.24+ (최소 3노드)
- **리소스 요구사항**:
  - CPU: 노드당 8+ 코어 권장
  - 메모리: 노드당 16GB+ 권장

### 설치 및 배포
이 저장소의 쿠버네티스 배포는 `devops/` 아래 Helm 차트와 실행 스크립트를 기준으로 동작합니다.

```bash
# 1) (필수) devops 스크립트가 참조하는 kubeconfig 준비
cp ~/.kube/config GenAI_Platform/devops/fb_common_app/helm/file/kube/config

# 2) values 파일 준비 (템플릿에서 복사하여 환경에 맞게 수정)
cd GenAI_Platform/devops
cp values.yaml.template values_<서버명>.yaml
# TODO 주석을 확인하며 실제 환경에 맞게 수정

# 3) 인프라(스토리지/DB/ingress/registry 등) 설치
# - 자세한 순서/명령은 devops/INSTALL.md 참고

# 4) 앱(Flightbase) 차트 설치
./run.sh install -f ./values_<서버명>.yaml

# 5) LLM 관련 차트 설치(선택)
./run_llm.sh install -f ./values_<서버명>.yaml

# 6) 서비스 확인
kubectl get pods -A
```

## 📁 디렉토리 구조

```
GenAI_Platform/
├── devops/                        # 쿠버네티스 인프라 구성요소
│   ├── gaip_efk/                  # 로그 수집 및 분석
│   ├── gaip_prometheus/           # 모니터링 스택
│   ├── gaip_kong/                 # ingress (kong)
│   ├── gaip_registry/             # private registry
│   ├── gaip_maraidb/              # mariadb
│   └── ...                        # 기타 인프라 구성요소
│
├── apps/                          # 마이크로서비스
│   ├── fb_dashboard/              # 웹 관리 인터페이스
│   ├── fb_dataset/                # 데이터셋 관리
│   ├── fb_image/                  # 이미지 처리
│   ├── fb_log_middleware/         # 로그 미들웨어
│   ├── fb_logger/                 # 중앙 로깅
│   ├── fb_monitoring/             # 시스템 모니터링
│   ├── fb_notification/           # 알림 시스템
│   ├── fb_resource/               # 리소스/스토리지 관리
│   ├── fb_scheduler/              # 작업 스케줄링
│   ├── fb_user/                   # 사용자 관리
│   ├── fb_utils/                  # 공통 유틸리티
│   ├── fb_workspace/              # 워크스페이스
│   ├── llm_model/                 # LLM 모델/서빙
│   ├── llm_playground/            # LLM 실험/플레이그라운드
│   └── llm_rag/                   # RAG API
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

**참고**: 인프라/앱/LLM 설치 방법은 `devops/INSTALL.md`에 최신 기준으로 정리되어 있습니다.