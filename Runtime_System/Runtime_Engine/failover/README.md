# 컨테이너 서비스 장애복구

active의 응답 실패를 감지하고 실행 차단을 확인한 뒤, 요청 경로를
이미 실행 중인 backup으로 전환합니다. 이후 Kubernetes Service 경로를
backup으로 수렴시키고 전환용 규칙을 정리합니다.

## 구성

- `service_agent.py`: 장애 감지와 전환 제어
- `service_chain.py`, `prepared_restore.py`: DNAT 규칙 전환
- `service_controller.py`: 컨테이너 식별·실행·결과 수집
- `service_server.py`, `service_probe.py`, `service.yaml`: 실행 예제와 관측
- `tests/`: 단위·회귀 검사

## 실행

Orin에 Kubernetes·containerd·iptables-nft·Python 3.12의 pidfd 지원,
kubectl·crictl·비대화형 sudo와 `rtst-rttools:orin-k1` 이미지를 준비합니다.
이미지는 별도 입력이며 로컬에 있어야 합니다.

`service.yaml`의 모든 `nodeName`과 아래 변수를 실제 노드에 맞춥니다.
다른 manifest는 `TC2_SERVICE_MANIFEST`로 지정할 수 있습니다.
변수 이름과 서비스 이름은 기존 구현과의 호환을 위해 유지합니다.

```bash
export KUBECONFIG="$HOME/.kube/config"
TC2_NODE_NAME=mic711-rt TC2_NODE_IP=10.2.58.155 \
  ./run-service-integration.sh "$HOME/tango2-evidence/UNIQUE_ID" demo hang
```

결과 경로는 새 디렉터리여야 합니다. 실행기는 전용 namespace와 Pod,
Service·EndpointSlice·DNAT 규칙을 만들고 종료 시 정리를 확인합니다.
개발용 단일 노드에서 실행합니다. 상태 복제나 다른 노드로의 이동은
이 구현에 포함하지 않습니다.

## 검사

```bash
python3 -m unittest discover -s tests -v
bash -n run-service-integration.sh
```

Linux 전용 검사는 Linux에서 수행합니다. 실제 장애복구 확인은 대상 Orin에서
수집한 응답·환경 기록을 기준으로 합니다.
