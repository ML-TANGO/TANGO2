# FastAPI Pod 자동 확장(HPA) 구성 및 평가

FastAPI 서비스(`docker-conn` 네임스페이스, `fastapi-deploy`)를 CPU, 메모리, API 요청률 세 가지 지표로 자동 확장하는 환경의 구성 방법, 동작 원리, 평가 절차를 정리한 문서이다.

- 클러스터: Kubernetes v1.30.14, control-plane `ketis`, worker `ubuntu2204-worker`(16 core), `jetson-2204-arm`(8 core, arm64)
- 관련 파일: `docker-repo/` 디렉토리
  - `fastapi-repo.yaml` : Deployment + Service (확장 대상)
  - `fastapi-monitor.yaml` : ServiceMonitor (Prometheus 수집 설정)
  - `fastapi-hpa-custom-metrics.yaml` : prometheus-adapter 규칙 (custom metric 정의)
  - `fastapi-hpa.yaml` : HorizontalPodAutoscaler (확장 정책)

## 목차

- [1. 전체 구조](#1-전체-구조)
- [2. 환경 구성](#2-환경-구성)
  - [2-1. metrics-server (CPU / 메모리 지표)](#2-1-metrics-server-cpu--메모리-지표)
  - [2-2. Prometheus + Grafana (kube-prometheus-stack)](#2-2-prometheus--grafana-kube-prometheus-stack)
  - [2-3. prometheus-adapter 설치 (custom metric API)](#2-3-prometheus-adapter-설치-custom-metric-api)
  - [2-4. 확장 대상 Deployment (fastapi-repo.yaml)](#2-4-확장-대상-deployment-fastapi-repoyaml)
  - [2-5. ServiceMonitor (fastapi-monitor.yaml)](#2-5-servicemonitor-fastapi-monitoryaml)
  - [2-6. prometheus-adapter 규칙 (fastapi-hpa-custom-metrics.yaml)](#2-6-prometheus-adapter-규칙-fastapi-hpa-custom-metricsyaml)
  - [2-7. HPA (fastapi-hpa.yaml)](#2-7-hpa-fastapi-hpayaml)
- [3. 동작 원리](#3-동작-원리)
  - [3-1. 목표 개수 계산식](#3-1-목표-개수-계산식)
  - [3-2. 계산 예시 (pod 2개, CPU 기준)](#3-2-계산-예시-pod-2개-cpu-기준)
  - [3-3. behavior에 의한 속도 제한](#3-3-behavior에-의한-속도-제한)
  - [3-4. 주의할 점](#3-4-주의할-점)
- [4. 평가 방법](#4-평가-방법)
  - [4-1. 사전 정리](#4-1-사전-정리)
  - [4-2. 초기 상태 기록](#4-2-초기-상태-기록)
  - [4-3. 모니터링 창 열기](#4-3-모니터링-창-열기)
  - [4-4. 시험 1: CPU 부하](#4-4-시험-1-cpu-부하)
  - [4-5. 시험 2: 메모리 부하](#4-5-시험-2-메모리-부하)
  - [4-6. 시험 3: API 요청 부하](#4-6-시험-3-api-요청-부하)
  - [4-7. 판정 기준](#4-7-판정-기준)
- [5. 트러블슈팅](#5-트러블슈팅)
  - [custom metric이 NotFound](#custom-metric이-notfound)
  - [ContainerCreating 중 Terminating](#containercreating-중-terminating)
  - [노드를 껐는데 pod가 Running으로 남음](#노드를-껐는데-pod가-running으로-남음)

---

---

## 1. 전체 구조

```
                    ┌──────────────────────────────────────────────────────┐
                    │  HPA controller (fastapi-hpa, 15초마다 계산)           │
                    │   CPU 50%  ·  Memory 60%  ·  fastapi_requests_per_second 5 │
                    └───────┬──────────────────────────┬───────────────────┘
                            │ metrics.k8s.io            │ custom.metrics.k8s.io
                            ▼                           ▼
                    ┌───────────────┐          ┌──────────────────────┐
                    │ metrics-server│          │  prometheus-adapter  │
                    │ (kubelet 수집)│          │  (PromQL → metric API)│
                    └───────────────┘          └──────────┬───────────┘
                                                          │ PromQL
                                                          ▼
                                               ┌──────────────────────┐
                                               │ Prometheus (ketis)   │
                                               │  ServiceMonitor 로    │
                                               │  fastapi /metrics 5초 수집│
                                               └──────────┬───────────┘
                                                          │ scrape
                                                          ▼
                                               fastapi-deploy pods (:8100/metrics)
```

- CPU, 메모리 지표는 **metrics-server**가 kubelet에서 받아 HPA에 제공한다.
- 요청률 지표는 FastAPI가 노출하는 `http_requests_total` 카운터를 **Prometheus**가 수집하고, **prometheus-adapter**가 PromQL로 가공해 `fastapi_requests_per_second`라는 이름으로 HPA에 제공한다.

---

## 2. 환경 구성

### 2-1. metrics-server (CPU / 메모리 지표)

[`README.md` 3-2](README.md#3-2-kubernetes-dashboard--metrics-server-설치)의 `dashboard_k8s/metrics.yaml`로 설치되어 있으며 `--metric-resolution=15s`로 동작한다.

```bash
kubectl get pods -n kube-system | grep metrics-server
kubectl top nodes
kubectl top pods -n docker-conn
```

`kubectl top`이 값을 보여주면 HPA의 CPU, 메모리 지표는 준비된 것이다.

### 2-2. Prometheus + Grafana (kube-prometheus-stack)

helm 릴리즈 `prometheus`(차트 81.4.3)가 `monitoring` 네임스페이스에 설치되어 있다. 설정은 `prometheus/monitoring-config.yaml` 한 파일로 관리한다.

```bash
set -a; source .env; set +a   # GRAFANA_ADMIN_PASSWORD 로드 (.env는 git에 올리지 않음)
helm upgrade prometheus prometheus-community/kube-prometheus-stack \
  -n monitoring --version 81.4.3 -f prometheus/monitoring-config.yaml \
  --set-string grafana.adminPassword="$GRAFANA_ADMIN_PASSWORD"
```

| 구성요소 | 접근 | 비고 |
|---|---|---|
| Grafana | `http://<노드IP>:30300` | 계정 `admin`, 비밀번호는 환경변수 `GRAFANA_ADMIN_PASSWORD` |
| Prometheus | `http://<노드IP>:30090` | |

모든 구성요소는 control-plane 노드 `ketis`에 고정되어 있어 worker 노드를 꺼도 모니터링이 유지된다.

### 2-3. prometheus-adapter 설치 (custom metric API)

```bash
helm install prometheus-adapter prometheus-community/prometheus-adapter \
  --namespace monitoring \
  --set prometheus.url=http://prometheus-kube-prometheus-prometheus.monitoring.svc \
  --set prometheus.port=9090
```

설치 확인:

```bash
helm list -n monitoring
kubectl get apiservices | grep custom.metrics
kubectl get --raw "/apis/custom.metrics.k8s.io/v1beta1" | jq .
```

### 2-4. 확장 대상 Deployment (`fastapi-repo.yaml`)

HPA 관점에서 중요한 항목만 발췌한다.

```yaml
spec:
  # replicas 는 지정하지 않는다. HPA 가 개수를 관리하므로 함께 두면 충돌한다.
  template:
    spec:
      priorityClassName: critical-service
      containers:
        - name: fastapi
          image: 203.254.171.40:5003/fastapi:external
          ports:
            - containerPort: 8100
          resources:
            requests:
              cpu: "100m"      # CPU 사용률(%)의 분모
              memory: "512Mi"  # 메모리 사용률(%)의 분모
            limits:
              cpu: "500m"
              memory: "1024Mi"
      imagePullSecrets:
        - name: regcred
```

- **`resources.requests`는 필수**다. HPA의 Utilization 타입 지표는 "사용량 ÷ request"로 계산하므로 request가 없으면 CPU, 메모리 지표가 동작하지 않는다.
- Service는 NodePort 30810으로 노출되며, 포트 이름 `http-metrics`가 ServiceMonitor에서 참조된다.
- 이미지는 사설 레지스트리에서 받는다. 노드의 containerd 설정과 `regcred` Secret이 선행되어야 하며, 절차는 [`README.md`의 준비사항 장](README.md#3-1-사설-docker-registry-연동)을 참조한다.

```bash
kubectl apply -f docker-repo/fastapi-repo.yaml
kubectl get pods -n docker-conn -l app=fastapi
```

### 2-5. ServiceMonitor (`fastapi-monitor.yaml`)

Prometheus가 FastAPI의 `/metrics`를 5초마다 수집하도록 등록한다. Prometheus와 FastAPI의 네임스페이스가 다르므로 `namespaceSelector`를 지정해야 한다.

```yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: fastapi-svc-monitor
  namespace: monitoring          # Prometheus 가 설치된 네임스페이스
  labels:
    release: prometheus          # 이 label 이 있어야 Prometheus 가 인식한다
spec:
  namespaceSelector:
    matchNames: [docker-conn]
  selector:
    matchLabels:
      app: fastapi               # Service 의 label
  endpoints:
    - port: http-metrics         # Service 의 포트 이름
      path: /metrics
      interval: 5s
```

```bash
kubectl apply -f docker-repo/fastapi-monitor.yaml
kubectl get servicemonitor -n monitoring
```

수집 확인: Prometheus UI(30090) → Status → Targets에서 `fastapi-svc` job이 UP이면 된다. 명령으로는 다음과 같다.

```bash
curl -s "http://<노드IP>:30090/api/v1/targets" \
  | jq '.data.activeTargets[] | select(.labels.job=="fastapi-svc") | {pod:.labels.pod, health}'
```

### 2-6. prometheus-adapter 규칙 (`fastapi-hpa-custom-metrics.yaml`)

```yaml
prometheus:
  url: http://prometheus-kube-prometheus-prometheus.monitoring.svc
  port: 9090

rules:
  default: false        # 기본 규칙은 끄고 필요한 metric 만 정의
  custom:
    - seriesQuery: 'http_requests_total{container="fastapi", namespace="docker-conn", handler!="/metrics"}'
      resources:
        overrides:
          namespace: {resource: "namespace"}
          pod: {resource: "pod"}
      name:
        matches: "http_requests_total"
        as: "fastapi_requests_per_second"
      metricsQuery: 'sum(rate(<<.Series>>{<<.LabelMatchers>>}[1m])) by (<<.GroupBy>>)'
```

| 항목 | 의미 |
|---|---|
| `seriesQuery` | 어떤 시계열을 쓸지. `/metrics` 자체 수집 요청은 제외한다 |
| `resources.overrides` | Prometheus label(namespace, pod)을 Kubernetes 리소스와 연결 |
| `name.as` | HPA에서 참조할 metric 이름 |
| `metricsQuery` | 최근 1분간 초당 요청 수를 pod별로 합산 |

적용:

```bash
helm upgrade prometheus-adapter prometheus-community/prometheus-adapter \
  --namespace monitoring --reuse-values \
  -f docker-repo/fastapi-hpa-custom-metrics.yaml
```

확인:

```bash
kubectl get --raw "/apis/custom.metrics.k8s.io/v1beta1/namespaces/docker-conn/pods/*/fastapi_requests_per_second" | jq .
```

pod별로 `value`가 나오면 성공이다. `NotFound`가 나오는 경우는 [5장 트러블슈팅](#5-트러블슈팅)을 참고한다.

### 2-7. HPA (`fastapi-hpa.yaml`)

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: fastapi-hpa
  namespace: docker-conn
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: fastapi-deploy
  minReplicas: 2
  maxReplicas: 10
  metrics:
    - type: Resource                      # 1. CPU: request(100m) 대비 평균 50%
      resource:
        name: cpu
        target: {type: Utilization, averageUtilization: 50}
    - type: Resource                      # 2. 메모리: request(512Mi) 대비 평균 60%
      resource:
        name: memory
        target: {type: Utilization, averageUtilization: 60}
    - type: Pods                          # 3. 요청률: pod 당 평균 5 req/s
      pods:
        metric: {name: fastapi_requests_per_second}
        target: {type: AverageValue, averageValue: 5}
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 30
      selectPolicy: Max                   # 아래 두 정책 중 더 많이 늘리는 쪽
      policies:
        - {type: Pods,    value: 2,  periodSeconds: 30}   # 30초당 최대 2개
        - {type: Percent, value: 50, periodSeconds: 30}   # 30초당 현재의 50%
    scaleDown:
      stabilizationWindowSeconds: 30      # 기본값 300초 → 시험 편의상 30초
      policies:
        - {type: Pods, value: 2, periodSeconds: 15}       # 15초당 최대 2개 축소
```

```bash
kubectl apply -f docker-repo/fastapi-hpa.yaml
kubectl get hpa -n docker-conn
```

정상 상태 예시:

```
NAME          REFERENCE                   TARGETS                                    MINPODS   MAXPODS   REPLICAS
fastapi-hpa   Deployment/fastapi-deploy   cpu: 3%/50%, memory: 40%/60% + 1 more...   2         10        2
```

---

## 3. 동작 원리

### 3-1. 목표 개수 계산식

HPA는 15초마다 지표별로 아래 식을 계산한다.

```
목표 pod 수 = ceil( 현재 pod 수 × 현재 평균값 ÷ 목표값 )
```

1. 세 지표를 각각 계산한다.
2. 그중 **가장 큰 값**을 채택한다. 하나라도 초과하면 확장되고, 축소되려면 세 지표 모두 목표 아래여야 한다.
3. `minReplicas` ~ `maxReplicas` 범위로 자른다.
4. `behavior` 정책으로 한 번에 바뀌는 개수를 제한한다.

목표 대비 ±10% 이내(CPU 기준 45~55%)의 차이는 무시하므로 그 구간에서는 개수가 바뀌지 않는다. 이 허용 오차는 kube-controller-manager의 `--horizontal-pod-autoscaler-tolerance` 플래그(기본값 0.1)로 정해지며, 이 클러스터는 기본값을 쓴다. 정확히는 "현재값 ÷ 목표값"이 0.9~1.1 사이면 계산 결과와 무관하게 현재 개수를 유지한다.

### 3-2. 계산 예시 (pod 2개, CPU 기준)

| 평균 사용률 | 계산 | 목표 |
|---|---|---|
| 55% | 2 × 55/50 = 2.2 → 오차 범위라 무시 | 2 |
| 60% | 2 × 60/50 = 2.4 | 3 |
| 78% | 2 × 78/50 = 3.12 | 4 |
| 100% | 2 × 100/50 = 4.0 | 4 |
| 120% | 2 × 120/50 = 4.8 | 5 |
| 200% | 2 × 200/50 = 8.0 | 8 |
| 300% | 2 × 300/50 = 12 → 최대값 초과 | 10 |

총량으로 생각하면 더 직관적이다. 부하 총량을 pod당 목표(50m)로 나눈 값을 올림한 것이 균형점이다. 예를 들어 한 pod에 180m 부하를 주면 180 ÷ 50 = 3.6 → 4개에서 안정된다.

| pod 수 | 평균 사용률 | 재계산 | 결과 |
|---|---|---|---|
| 3 | (180 + 6) ÷ 3 ≈ 62% | ceil(3 × 62/50) = 4 | 확장 |
| 4 | (180 + 9) ÷ 4 ≈ 47% | ceil(4 × 47/50) = 4 | 유지 |
| 5 | (180 + 12) ÷ 5 ≈ 38% | ceil(5 × 38/50) = 4 | 축소 |

### 3-3. behavior에 의한 속도 제한

- **확장**: 30초마다 "2개" 또는 "현재의 50%" 중 큰 쪽까지만 늘어난다. 2개에서 시작하면 2 → 4 → 6 → 9 → 10 순으로 올라간다.
- **축소**: 지표가 30초 동안 계속 낮아야 하며, 15초마다 최대 2개씩 줄인다. 부하가 끊기면 1분 안에 최소값으로 돌아온다.
- 축소 시 Deployment는 **아직 Ready가 아닌 pod부터** 지운다. 이미지 pull이 오래 걸리는 노드에 배정된 pod는 부하가 짧으면 Running을 보기 전에 삭제될 수 있다.

### 3-4. 주의할 점

- 사용률은 limit이 아니라 **request 기준**이다. CPU request가 100m이므로 pod가 120m을 쓰면 120%가 된다.
- 사용률은 모든 Ready pod의 **평균**이다. 한 pod만 바쁘고 나머지가 놀면 평균이 희석된다.
- Ready가 아닌 pod는 확장 판단 시 사용량 0으로 가정해 분모에 포함되므로, pod가 뜨는 동안에는 추가 확장이 보수적으로 억제된다.
- 메모리는 부하가 끝나도 바로 떨어지지 않는 지표라, 축소가 CPU보다 늦게 단계적으로 일어날 수 있다.

---

## 4. 평가 방법

### 4-1. 사전 정리

이전 시험에서 남은 비정상 pod를 정리한다.

```bash
kubectl delete pods -n docker-conn --field-selector=status.phase==Failed
kubectl delete pods -n docker-conn --field-selector=status.phase==Succeeded
kubectl get pods -n docker-conn | grep Terminating | awk '{print $1}' \
  | xargs -r kubectl delete pod -n docker-conn --force --grace-period=0
```

### 4-2. 초기 상태 기록

```bash
kubectl top pods -n docker-conn -l app=fastapi
kubectl describe hpa fastapi-hpa -n docker-conn
```

평상시 값 (실측):

| 지표 | 현재 | 목표 |
|---|---|---|
| CPU | 3~4% (3~4m / 100m) | 50% |
| 메모리 | 30~43% (155~218Mi / 512Mi) | 60% |
| fastapi_requests_per_second | 0.2 (199m) | 5 |

### 4-3. 모니터링 창 열기

별도 터미널에서 다음 중 하나를 띄워 두고 시험한다.

```bash
# 요약
kubectl get hpa -n docker-conn -w

# 세 지표와 replica 수를 1초마다
watch -n 1 'kubectl describe hpa fastapi-hpa -n docker-conn \
  | grep -E "Reference|resource cpu|resource memory|fastapi_requests_per_second|Deployment pods"'

# 어느 노드에 뜨는지
kubectl get pods -n docker-conn -l app=fastapi -o wide -w
```

HPA 결정 이력은 이벤트로 남는다.

```bash
kubectl get events -n docker-conn --field-selector involvedObject.name=fastapi-hpa \
  --sort-by=.lastTimestamp | tail
```

Grafana(30300)의 "The number of pods" 대시보드에서도 네임스페이스별 pod 수 변화를 볼 수 있다.

### 4-4. 시험 1: CPU 부하

pod 내부에서 stress-ng로 부하를 건다.

```bash
kubectl exec -it <fastapi-pod> -n docker-conn -- /bin/bash
apt-get update && apt-get install -y stress-ng      # 최초 1회
stress-ng --cpu 1 --cpu-load 15 --cpu-method ackermann --timeout 120s
```

- 코어 1개의 15% = 약 150m 부하를 120초 동안 생성한다. 실측으로는 약 180m까지 올라간다.
- **예상**: 평균 (180 + 3) ÷ 2 ≈ 90% → ceil(2 × 90/50) = 4개. 확장 정책상 2 → 4로 한 번에 도달한다.
- **실측**: 부하 시작 후 약 1분 뒤 `New size: 4; reason: cpu resource utilization above target`, 부하 종료 후 약 1분 뒤 4 → 3 → 2로 축소.

### 4-5. 시험 2: 메모리 부하

```bash
stress-ng --vm 1 --vm-bytes 384M --vm-hang 120 --timeout 120s
```

- 384MB를 할당해 120초 유지한다. 기본 사용량 ~160Mi와 합쳐 약 540Mi가 된다.
- **예상**: 한 pod 540Mi, 다른 pod 160Mi → 평균 350Mi ≈ 68% → ceil(2 × 68/60) = 3개.
- limit이 1024Mi이므로 OOM은 발생하지 않는다.

### 4-6. 시험 3: API 요청 부하

외부에서 NodePort로 실제 HTTP 요청을 넣는다. 이 방식만 새로 뜬 pod에도 부하가 분산된다.

```bash
# hey 사용
sudo apt-get install -y hey
hey -z 120s -c 3 -q 50 http://<노드IP>:30810/

# apache bench 사용
sudo apt-get install -y apache2-utils
ab -n 20000 -c 50 http://<노드IP>:30810/
```

hey 옵션: `-c 3`(클라이언트 3개) × `-q 50`(클라이언트당 초당 50회) = **초당 150 요청**, `-z 120s` 동안 유지.

- **예상**: pod 2개일 때 pod당 평균 75 req/s → ceil(2 × 75/5) = 30 → 최대값 10개. 확장 정책에 따라 2 → 4 → 6 → 9 → 10으로 30초 간격으로 올라간다.
- 인증이 필요한 엔드포인트는 `-H "Token: <값>"` 식으로 헤더를 추가한다.

### 4-7. 판정 기준

| 항목 | 기준 |
|---|---|
| 확장 | 부하 후 60초 이내에 예상 개수로 증가 (behavior 제한 고려) |
| 분산 | 새 pod가 여러 노드에 배치됨 (`-o wide`) |
| 축소 | 부하 종료 후 60~90초 이내에 minReplicas(2)로 복귀 |
| 지표 | describe hpa의 세 지표가 모두 `<unknown>` 없이 값으로 표시 |

---

## 5. 트러블슈팅

### custom metric이 `NotFound`

```
Error from server (NotFound): the server could not find the metric fastapi_requests_per_second for pods
```

- 원인 1: Prometheus가 재시작되어 데이터가 비었고, 이후 FastAPI가 `/metrics` 외의 요청을 한 번도 받지 않아 `http_requests_total{handler!="/metrics"}` 시계열이 없음.
- 조치: `curl http://<노드IP>:30810/` 로 요청을 몇 번 보내고 1분 정도 기다린다.
- 원인 2: ServiceMonitor의 `release: prometheus` label 누락 또는 Service 포트 이름 불일치. Prometheus Targets에서 `fastapi-svc`가 보이는지 확인한다.

### ContainerCreating 중 Terminating

HPA가 축소될 때 Ready가 아닌 pod를 먼저 지우기 때문이다. 디스크 문제가 아니라 부하가 이미지 pull 시간보다 짧았던 것이므로, 부하를 더 오래 주거나 이미지를 미리 받아 둔다.

### 노드를 껐는데 pod가 Running으로 남음

kubelet이 사라져 상태가 갱신되지 않는 것이다. 일반 Deployment pod는 약 5분 뒤 다른 노드로 옮겨지고, DaemonSet pod는 노드가 돌아올 때까지 남는다. 실제 Ready 여부는 다음으로 확인한다.

```bash
kubectl get pods -n docker-conn -o custom-columns='NAME:.metadata.name,NODE:.spec.nodeName,READY:.status.conditions[?(@.type=="Ready")].status'
```
