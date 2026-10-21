# 우선순위 기반 스케줄링(PriorityClass) 구성 및 평가

서비스별 중요도에 따라 Pod에 우선순위를 부여하고, 자원이 부족할 때 낮은 우선순위 Pod를 선점(Preemption)해 중요한 서비스를 먼저 배치하는 구성의 방법, 동작 원리, 평가 절차를 정리한 문서이다.

- 클러스터: Kubernetes v1.30.14, control-plane `ketis`(28 core), worker `ubuntu2204-worker`(16 core), `jetson-2204-arm`(8 core)
- 관련 파일: `scheduler/` 디렉토리
  - `priority.yaml` : PriorityClass 3종 정의
  - `priority-test.yaml` : 선점 시험용 저우선순위 filler
  - `priority-test-high.yaml` : 선점 시험용 고우선순위 pod
  - `priority-test-never.yaml` : `preemptionPolicy: Never` 비교용
- 적용 대상: `docker-repo/fastapi-repo.yaml` (`priorityClassName: critical-service`)

## 목차

- [1. 개념](#1-개념)
- [2. 환경 구성](#2-환경-구성)
  - [2-1. PriorityClass 정의 (priority.yaml)](#2-1-priorityclass-정의-priorityyaml)
  - [2-2. Deployment에 적용 (docker-repo/fastapi-repo.yaml)](#2-2-deployment에-적용-docker-repofastapi-repoyaml)
  - [2-3. 적용 확인](#2-3-적용-확인)
- [3. 동작 원리](#3-동작-원리)
  - [3-1. 스케줄링 순서](#3-1-스케줄링-순서)
  - [3-2. 선점(Preemption) 절차](#3-2-선점preemption-절차)
  - [3-3. 선점 외의 효과](#3-3-선점-외의-효과)
  - [3-4. HPA와의 관계](#3-4-hpa와의-관계)
- [4. 평가 방법](#4-평가-방법)
  - [4-1. 시험 설계](#4-1-시험-설계)
  - [4-2. 1단계: 노드 채우기](#4-2-1단계-노드-채우기)
  - [4-3. 2단계: 모니터링 창 열기](#4-3-2단계-모니터링-창-열기)
  - [4-4. 3단계: 고우선순위 pod 투입](#4-4-3단계-고우선순위-pod-투입)
  - [4-5. 4단계: 결과 확인](#4-5-4단계-결과-확인)
  - [4-6. 5단계: preemptionPolicy: Never 비교](#4-6-5단계-preemptionpolicy-never-비교)
  - [4-7. 정리](#4-7-정리)
  - [4-8. 판정 기준](#4-8-판정-기준)
  - [4-9. 실측 결과](#4-9-실측-결과)
- [5. 운영 시 주의사항](#5-운영-시-주의사항)

---

---

## 1. 개념

kube-scheduler는 Pending 상태의 Pod를 **우선순위 값이 큰 순서**로 꺼내 배치한다. 배치할 노드가 없으면 `preemptionPolicy`에 따라 자신보다 낮은 우선순위의 Pod를 퇴거시켜 자리를 만든다.

```
  스케줄링 큐 (높은 값부터)                       노드 (자원 부족)
  ┌──────────────────────┐                     ┌──────────────────────────┐
  │ db-service      20000│ ─── 먼저 배치 ────▶  │  ... 가득 참              │
  │ critical-service 10000│ ─── 자리 없음 ──┐   │  low pod (1000)  ◀─ 퇴거  │
  │ algorithm-service 1000│                 └──▶│  high pod (10000) 배치    │
  │ (미지정)            0│                     └──────────────────────────┘
  └──────────────────────┘
```

| 용어 | 의미 |
|---|---|
| PriorityClass | 우선순위 값(value)과 선점 정책을 묶은 클러스터 단위 객체 |
| `value` | 정수. 클수록 우선. 사용자 정의는 10억 미만 |
| `globalDefault` | true면 priorityClassName을 지정하지 않은 pod에 자동 적용. 클러스터에 하나만 가능 |
| `preemptionPolicy` | `PreemptLowerPriority`(기본): 자리가 없으면 낮은 pod를 퇴거 / `Never`: 퇴거하지 않고 대기 |
| 선점(Preemption) | 높은 우선순위 pod를 위해 낮은 pod를 graceful 종료시키는 동작 |

시스템 예약 클래스로 `system-node-critical`(2000001000), `system-cluster-critical`(2000000000)이 있으며 kube-system 구성요소가 사용한다. 사용자 서비스는 이 값보다 작게 둔다.

---

## 2. 환경 구성

### 2-1. PriorityClass 정의 (`priority.yaml`)

```yaml
apiVersion: scheduling.k8s.io/v1
kind: PriorityClass
metadata:
  name: db-service                      # SQL / NoSQL DB
value: 20000
globalDefault: false
preemptionPolicy: PreemptLowerPriority
description: "DB service - Must be activated first"
---
apiVersion: scheduling.k8s.io/v1
kind: PriorityClass
metadata:
  name: critical-service                # 메인 API 서버 (FastAPI)
value: 10000
globalDefault: false
preemptionPolicy: PreemptLowerPriority
description: "Super-high priority service"
---
apiVersion: scheduling.k8s.io/v1
kind: PriorityClass
metadata:
  name: algorithm-service               # 시뮬레이션 알고리즘 등 후순위 작업
value: 1000
globalDefault: false
preemptionPolicy: PreemptLowerPriority
description: "Simulation algorithm marginal priority service"
```

설계 의도:

| 클래스 | 값 | 대상 | 자원 부족 시 |
|---|---|---|---|
| db-service | 20000 | DB | 아래 두 클래스를 선점 |
| critical-service | 10000 | API 서버 | algorithm-service와 미지정 pod를 선점 |
| algorithm-service | 1000 | 배치, 시뮬레이션 | 미지정 pod(0)만 선점, 위 두 클래스에 밀림 |
| (미지정) | 0 | 그 외 | 가장 먼저 밀림 |

값 사이 간격을 10배로 두어 나중에 중간 등급을 추가할 여지를 남겼다.

```bash
kubectl apply -f scheduler/priority.yaml
kubectl get priorityclass        # 또는 kubectl get pc
```

```
NAME                      VALUE        GLOBAL-DEFAULT   AGE
algorithm-service         1000         false            214d
critical-service          10000        false            214d
db-service                20000        false            123d
system-cluster-critical   2000000000   false            242d
system-node-critical      2000001000   false            242d
```

### 2-2. Deployment에 적용 (`docker-repo/fastapi-repo.yaml`)

Pod 템플릿의 `spec`에 `priorityClassName`을 한 줄 추가한다.

```yaml
spec:
  template:
    spec:
      priorityClassName: critical-service
      containers:
        - name: fastapi
          ...
```

```bash
kubectl apply -f docker-repo/fastapi-repo.yaml
```

- 이미 떠 있는 pod에는 소급 적용되지 않는다. 템플릿이 바뀌므로 Deployment가 rolling update로 pod를 새로 만든다.
- 존재하지 않는 PriorityClass 이름을 쓰면 pod 생성 자체가 거부된다. PriorityClass를 먼저 만들어야 한다.

### 2-3. 적용 확인

```bash
kubectl get pods -n docker-conn -o custom-columns='NAME:.metadata.name,CLASS:.spec.priorityClassName,PRIORITY:.spec.priority'
```

```
NAME                              CLASS              PRIORITY
fastapi-deploy-54f7bdd6fc-55xch   critical-service   10000
fastapi-deploy-54f7bdd6fc-bm488   critical-service   10000
```

`spec.priority`는 admission 시점에 PriorityClass의 value가 복사된 값이다. `kubectl describe pod`의 `Priority:`, `Priority Class Name:` 항목으로도 볼 수 있다.

---

## 3. 동작 원리

### 3-1. 스케줄링 순서

1. 새 pod가 Pending 큐에 들어오면 `spec.priority` 내림차순으로 정렬된다. 같은 값이면 먼저 들어온 순서다.
2. 스케줄러는 큐 맨 앞 pod부터 배치 가능한 노드를 찾는다 (nodeSelector, 자원 request, taint 등 필터 → 점수).
3. 노드가 있으면 배치하고 끝난다. **자원이 충분하면 우선순위는 배치 순서에만 영향을 주고 아무도 퇴거되지 않는다.**

### 3-2. 선점(Preemption) 절차

배치 가능한 노드가 없고 `preemptionPolicy: PreemptLowerPriority`이면:

1. 각 노드에 대해 "이 노드의 자신보다 낮은 우선순위 pod들을 제거하면 들어갈 수 있는가"를 계산한다.
2. 조건을 만족하는 노드 중 **퇴거되는 pod의 우선순위 합이 가장 낮고, 개수가 가장 적은** 노드를 고른다. PodDisruptionBudget 위반이 적은 노드를 우선한다.
3. 선택된 희생 pod를 graceful 종료시킨다 (`terminationGracePeriodSeconds` 적용, 기본 30초).
4. 새 pod의 `status.nominatedNodeName`에 그 노드를 기록하고, 자리가 비면 배치한다.

선점은 **같은 우선순위나 더 높은 우선순위 pod는 절대 퇴거하지 않는다.** 또 kube-system의 system-* 클래스는 사용자 클래스보다 항상 높으므로 사용자 pod가 시스템 pod를 밀어내는 일은 없다.

### 3-3. 선점 외의 효과

- **kubelet 자원 부족 퇴거**: 노드가 MemoryPressure, DiskPressure 상태가 되면 kubelet도 pod를 퇴거하는데, 이때 request를 초과해 쓰는 pod 중 **우선순위가 낮은 것부터** 고른다. PriorityClass는 스케줄링뿐 아니라 노드 단위 퇴거 순서에도 영향을 준다.
- **ResourceQuota**: 네임스페이스 쿼터에 `scopeSelector`로 특정 PriorityClass만 허용하거나 제한할 수 있다 (이 클러스터에서는 미사용).

### 3-4. HPA와의 관계

fastapi-deploy는 HPA([`Autoscaling.md`](Autoscaling.md))로 2~10개까지 늘어나며 모두 `critical-service`다. 확장 시 노드 자원이 부족하면 algorithm-service 이하 pod를 밀어내고 자리를 확보하므로, 부하 상황에서 API 서버의 확장이 후순위 작업에 막히지 않는다. 반대로 algorithm-service 작업은 API 서버가 한가할 때 남는 자원을 쓰는 구조가 된다.

---

## 4. 평가 방법

현재 클러스터는 자원이 넉넉해(allocatable 총 52 core 중 request 합계 약 1.7 core) 평상시에는 선점이 일어나지 않는다. 따라서 **노드 하나를 의도적으로 채운 뒤** 고우선순위 pod를 넣어 선점을 관찰한다. 시험은 별도 네임스페이스 `priority-test`에서 수행하며, 운영 pod에는 영향이 없다.

### 4-1. 시험 설계

- 대상 노드: `ubuntu2204-worker` (allocatable 16 core, 평시 request 약 200m)
- filler: `algorithm-service`(1000), CPU request 3000m × 5개 = 15 core → 노드 포화 (여유 약 0.8 core)
- high-pod: `critical-service`(10000), CPU request 2000m → 여유 부족 → filler 1개 선점 필요
- 이미지는 모든 노드에 있는 `registry.k8s.io/pause:3.8`을 써서 pull 시간을 없앤다.

### 4-2. 1단계: 노드 채우기

```bash
kubectl apply -f scheduler/priority-test.yaml
kubectl rollout status deploy/low-filler -n priority-test
kubectl get pods -n priority-test -o wide
kubectl describe node ubuntu2204-worker | grep -A3 "Allocated resources" | grep cpu
```

기대: low-filler 5개 모두 ubuntu2204-worker에서 Running, 노드 CPU request가 약 15200m(95%)로 표시.

### 4-3. 2단계: 모니터링 창 열기

별도 터미널에서:

```bash
kubectl get pods -n priority-test -o wide -w
```

```bash
kubectl get events -n priority-test --sort-by=.lastTimestamp -w
```

### 4-4. 3단계: 고우선순위 pod 투입

```bash
kubectl apply -f scheduler/priority-test-high.yaml
```

기대 동작 (수십 초 이내):

1. high-pod가 Pending이 되고 `nominatedNodeName: ubuntu2204-worker`가 기록된다.
2. low-filler 중 1개가 Terminating으로 바뀐다 (graceful 종료 30초).
3. 그 pod가 사라지면 high-pod가 Running이 된다.
4. Deployment가 low-filler를 다시 5개로 맞추려 하지만, 자리가 없어 새 filler 1개는 Pending으로 남는다.

### 4-5. 4단계: 결과 확인

```bash
# 선점 이벤트
kubectl get events -n priority-test --field-selector reason=Preempted
kubectl get events -n priority-test | grep -iE "preempt|nominated"

# high-pod 상태
kubectl get pod high-pod -n priority-test -o wide
kubectl get pod high-pod -n priority-test -o jsonpath='{.status.nominatedNodeName}{"\n"}'

# 최종 배치
kubectl get pods -n priority-test -o custom-columns='NAME:.metadata.name,PRIORITY:.spec.priority,STATUS:.status.phase,NODE:.spec.nodeName'
```

기대 결과:

```
NAME                          PRIORITY   STATUS    NODE
high-pod                      10000      Running   ubuntu2204-worker
low-filler-xxxxx-aaaaa        1000       Running   ubuntu2204-worker
low-filler-xxxxx-bbbbb        1000       Running   ubuntu2204-worker
low-filler-xxxxx-ccccc        1000       Running   ubuntu2204-worker
low-filler-xxxxx-ddddd        1000       Running   ubuntu2204-worker
low-filler-xxxxx-eeeee        1000       Pending   <none>
```

이벤트에는 희생 pod에 대해 `Preempted by a pod on node ubuntu2204-worker` 메시지가, high-pod에 대해 `Scheduled` 메시지가 남는다.

### 4-6. 5단계: `preemptionPolicy: Never` 비교

같은 값(10000)이지만 선점하지 않는 클래스로 비교한다. 4단계 상태(노드 포화)에서 수행한다.

```bash
kubectl apply -f scheduler/priority-test-never.yaml
kubectl get pod high-pod-never -n priority-test
kubectl describe pod high-pod-never -n priority-test | tail -5
```

기대: `Pending` 상태로 남고, 이벤트에 `0/4 nodes are available: ... Insufficient cpu` 와 함께 `preemption: not eligible due to preemptionPolicy=Never` 가 표시된다. 아무 pod도 퇴거되지 않는다.

### 4-7. 정리

```bash
kubectl delete namespace priority-test
kubectl delete priorityclass critical-no-preempt
```

### 4-8. 판정 기준

| 항목 | 기준 |
|---|---|
| 선점 발생 | high-pod 투입 후 60초 이내 low-filler 1개 Terminating → high-pod Running |
| 희생 선택 | 퇴거된 pod가 algorithm-service(1000)이며, 다른 네임스페이스의 pod는 영향 없음 |
| 이벤트 | `Preempted` 이벤트와 `nominatedNodeName` 기록 확인 |
| Never 정책 | high-pod-never는 Pending 유지, 퇴거 없음 |
| 운영 영향 | docker-conn, monitoring의 pod 상태 변화 없음 |

### 4-9. 실측 결과

위 절차를 그대로 수행한 결과이며, 모든 판정 기준을 만족했다.

**1단계 (노드 채우기)**: low-filler 5개가 ubuntu2204-worker에 모두 Running. 노드 CPU request 15200m (95%).

**3단계 (high-pod 투입)**: 투입 **5초 만에** high-pod가 Running이 되었다. pause 컨테이너는 종료가 즉시 끝나 graceful 30초를 기다리지 않았다.

```
NAME                         PRIORITY   STATUS    NODE
high-pod                     10000      Running   ubuntu2204-worker
low-filler-987c8fcc8-944qq   1000       Pending   <none>              ← 선점으로 밀려난 자리의 대체 pod
low-filler-987c8fcc8-hq95g   1000       Running   ubuntu2204-worker
low-filler-987c8fcc8-k5ms5   1000       Running   ubuntu2204-worker
low-filler-987c8fcc8-r74gg   1000       Running   ubuntu2204-worker
low-filler-987c8fcc8-xh8mw   1000       Running   ubuntu2204-worker
```

이벤트 (요약):

```
high-pod                     FailedScheduling  0/4 nodes are available: 1 Insufficient cpu, 1 node(s) had untolerated taint {node.kubernetes.io/unreachable: }, 2 node(s) didn't match Pod's node affinity/selector.
low-filler-987c8fcc8-6l4vw   Preempted         Preempted by pod 00c87ff2-... on node ubuntu2204-worker
high-pod                     Scheduled         Successfully assigned priority-test/high-pod to ubuntu2204-worker
low-filler-987c8fcc8-944qq   FailedScheduling  ... 1 Insufficient cpu ... preemption: 0/4 nodes are available: 1 Insufficient cpu, 3 Preemption is not helpful for scheduling.
```

- high-pod는 처음엔 자리가 없어 FailedScheduling이 한 번 기록되고, 곧바로 low-filler 1개(6l4vw)가 `Preempted`되어 배치되었다.
- Deployment가 만든 대체 filler(944qq)는 같은 1000 우선순위라 아무도 선점할 수 없어 `Preemption is not helpful` 메시지와 함께 Pending으로 남았다. 낮은 우선순위는 같은 등급 이상을 밀어내지 못한다는 점이 확인된다.

**5단계 (preemptionPolicy: Never 비교)**: 같은 값 10000이지만 `Never`인 high-pod-never는 25초 뒤에도 Pending이었고, 추가 선점은 발생하지 않았다.

```
high-pod-never   10000   Never   Pending
FailedScheduling: 0/4 nodes are available: 1 Insufficient cpu, ... preemption: not eligible due to preemptionPolicy=Never.
```

**운영 영향**: 시험 동안 docker-conn(fastapi-deploy 2개, ubuntu-deploy 3개)과 monitoring의 pod는 모두 Running을 유지했다.

**정리**: `priority-test` 네임스페이스와 `critical-no-preempt` PriorityClass를 삭제한 뒤 ubuntu2204-worker의 CPU request가 평시 수준(200m)으로 돌아온 것을 확인했다.

---

## 5. 운영 시 주의사항

- **globalDefault**: 현재 모두 false라 미지정 pod는 0이다. 특정 클래스를 기본값으로 두고 싶으면 하나만 true로 바꾼다. 이미 떠 있는 pod에는 적용되지 않는다.
- **PodDisruptionBudget**: 선점은 PDB를 "가능하면" 존중하지만 보장하지는 않는다. 꼭 지켜야 하는 서비스는 우선순위를 충분히 높게 둔다.
- **graceful 종료 시간**: 희생 pod는 `terminationGracePeriodSeconds`(기본 30초)만큼 기다린 뒤 종료되므로, 고우선순위 pod의 배치도 그만큼 늦어진다. 빠른 선점이 필요하면 후순위 워크로드의 이 값을 줄인다.
- **DaemonSet**: DaemonSet pod는 노드마다 1개가 필요하므로 보통 높은 우선순위(예: system-node-critical)를 준다. 그렇지 않으면 사용자 pod에 밀려 노드 기능(네트워크, 모니터링)이 빠질 수 있다.
- **request 없는 pod**: 자원 request가 없는 pod는 스케줄러가 0으로 계산하므로 선점의 희생자로 선택되어도 실제 자원이 확보되지 않을 수 있다. 우선순위를 쓰는 워크로드에는 request를 함께 지정한다.
- **값 변경**: PriorityClass의 `value`는 생성 후 변경할 수 없다. 바꾸려면 삭제 후 재생성해야 하며, 기존 pod의 `spec.priority`는 그대로 남는다.
