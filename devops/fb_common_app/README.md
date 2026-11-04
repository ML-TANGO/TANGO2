# fb_common_app

플랫폼의 모든 앱(`fb_*`) Helm 차트가 공통으로 의존하는 **공통 app 차트**입니다. 차트 이름은 `jfb-commonapp` 이며, `fb_common_lib`(`commonlib`)을 dependency 로 끌어오면서, 앱 Pod 안으로 마운트되는 공통 리소스(특히 **kubeconfig**)를 차트의 `helm/file/` 아래에 모아둡니다.

## 역할

- `fb_common_lib`(commonlib)의 Helm dependency 진입점
- 앱 컨테이너에서 K8s API 를 호출할 수 있도록 **kubeconfig 를 ConfigMap/Secret 으로 패키징**
- `devops/run.sh` 가 다른 앱 차트들을 설치하기 전에 가장 먼저 dependency build 되는 차트

## 사전 준비 — kubeconfig 복사 (필수)

이 차트(또는 이 차트를 dependency 로 가지는 다른 차트)를 빌드하기 전에 **반드시** 클러스터의 kubeconfig 를 차트가 읽는 위치로 복사해야 합니다. 이 과정 없이 `helm dependency build` 또는 `devops/run.sh install` 을 실행하면 실패합니다.

```bash
# 단순 복사 예시
cp ~/.kube/config GenAI_Platform/devops/fb_common_app/helm/file/kube/config
```

> 자동화된 빌드 스크립트(예: bundle/CICD)에서는 `helm_dependency.sh` 가 `${CONFIGURATION_DIR}/${DEPLOY_TARGET}/kube` 경로의 kube 디렉터리를 `helm/file/` 아래에 복사한 뒤 `helm dependency build` 를 수행하도록 되어 있습니다. 로컬 수동 설치 시에는 위와 같이 직접 한 번 복사해 두면 됩니다.

## 디렉터리 구조

```
devops/fb_common_app/
├── ci.yml
├── helm/
│   ├── Chart.yaml         # name: jfb-commonapp, dependency: commonlib
│   └── file/
│       └── kube/
│           └── config     # ← 위 사전 준비 단계에서 복사하는 kubeconfig
├── helm_dependency.sh     # CICD 용 dependency 준비 스크립트
└── README.md
```

## 함께 보면 좋은 문서

- 전체 설치 흐름: [`../INSTALL.md`](../INSTALL.md)
- 정식 설치 매뉴얼: [`../Tango GenAI Platform 설치 매뉴얼.md`](../Tango%20GenAI%20Platform%20설치%20매뉴얼.md)
