# workload_deploy

워크로드 배포 관련 프로젝트 모음입니다. 분산 추론 모델 분할, Kubernetes 자동 확장·우선순위 스케줄링, 원격 노드 컨테이너 관리 도구를 포함합니다.

## 폴더 구조

```
workload_deploy/
├── Parallell_Inference/   # PyTorch 모델 분할 및 ONNX 내보내기 유틸
│   ├── split_onnx_utils.py
│   ├── example.py
│   └── README.md
├── k8s_autoscaling/       # Kubernetes HPA 및 PriorityClass 운영 가이드
│   ├── Autoscaling.md
│   ├── Priority_Scheduling.md
│   ├── docker-repo/
│   ├── dashboard_k8s/
│   ├── prometheus/
│   ├── scheduler/
│   └── README.md
└── remoteManager/         # 원격 노드 컨테이너 관리 (Go, Control Plane + CLI)
    ├── cmd/cli/           # CLI 클라이언트
    ├── cmd/centralagent/  # Control Plane 서버
    ├── examples/
    ├── inventory.yaml
    ├── nodes.txt
    └── README.md
```

## 프로젝트 요약

| 프로젝트 | 설명 |
|---|---|
| **Parallell_Inference** | PyTorch 모델(주로 torchvision CNN)을 클라이언트/서버 두 부분으로 나누고 각각 ONNX로 내보내는 유틸리티입니다. 분산 추론 실험에 사용합니다. |
| **k8s_autoscaling** | 사설 레지스트리의 컨테이너(FastAPI, Ubuntu)를 Kubernetes에 배포하고, CPU·메모리·API 요청률 기반 자동 확장(HPA)과 우선순위 기반 스케줄링(PriorityClass, 선점)을 구성·평가한 자료입니다. |
| **remoteManager** | 여러 원격 노드의 Docker 컨테이너를 중앙에서 pull, create, start, stop, delete 하는 Go 기반 관리 도구입니다. 이미지 빌드(build.yaml 기반 Dockerfile 생성, Harbor push, 노드 배포) 기능을 포함합니다. |

## 상세 문서

- Parallell_Inference: [Parallell_Inference/README.md](Parallell_Inference/README.md)
- k8s_autoscaling: [k8s_autoscaling/README.md](k8s_autoscaling/README.md)
- remoteManager: [remoteManager/README.md](remoteManager/README.md)

---

**작성 기관:** 한국전자기술연구원 (KETI)

**최종 작업 날짜:** 2026-10-28
