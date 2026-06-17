# Jetson Orin (`tg-orin`) Calico CNI & BGP Peering 장애 조치 보고서

본 보고서는 Kubernetes 기반 GenAI 플랫폼의 신규 ARM64 젯슨 오린 노드(`tg-orin`) 연동 중 발생한 Calico CNI의 초기화 오류 및 BGP 피어링 연결 실패 현상에 대한 원인 분석과 **재현 가능(Reproducible)한 해결 조치 명령어 및 코드**를 정리한 기술 문서입니다.

---

## 1. 장애 현상 및 최초 상태
- **Calico Pod 상태**: `tg-orin` 노드의 `calico-node` DaemonSet Pod가 계속 `0/1 Running` 상태에 머무름.
- **오류 분석**:
  - `felix/table.go`에서 `iptables` 규칙 커밋 시 실패 발생 (raw table).
  - BIRD 데몬(BGP) 로그에서 타 노드들과 BGP 피어링이 성립되지 않고 `Connect` 상태에서 무한 대기함.
  - 원인은 젯슨 오린 커널(`5.15.185-tegra`)에 필수 Netfilter 모듈(`ipt_rpfilter`, `ip6t_rpfilter`, `xt_CT`)이 누락되었기 때문이며, 추가로 CNI IP 감지 명칭의 오기로 인해 잘못된 IP(`192.168.55.1`)를 인식하고 있었습니다.

---

## 2. 재현 가능한 단계별 조치 및 소스 코드

### [1단계] `rpfilter` 커널 모듈 빌드 및 로드 (`tg-orin` 호스트 셸)
Tegra 커널 환경에서 사용할 `ipt_rpfilter.ko` 및 `ip6t_rpfilter.ko` 모듈을 소스코드 단독 다운로드 방식으로 컴파일하여 설치합니다.

```bash
# 1. 빌드 작업 임시 디렉터리 생성 및 이동
mkdir -p /tmp/build_rpfilter
cd /tmp/build_rpfilter

# 2. 공식 리눅스 커널 저장소에서 IPv4/IPv6용 rpfilter 소스코드 다운로드
wget -O ipt_rpfilter.c "https://raw.githubusercontent.com/torvalds/linux/refs/tags/v5.15/net/ipv4/netfilter/ipt_rpfilter.c"
wget -O ip6t_rpfilter.c "https://raw.githubusercontent.com/torvalds/linux/refs/tags/v5.15/net/ipv6/netfilter/ip6t_rpfilter.c"

# 3. 모듈 빌드를 위한 Makefile 생성
cat << 'EOF' > Makefile
obj-m += ipt_rpfilter.o
obj-m += ip6t_rpfilter.o
EOF

# 4. Tegra 커널 헤더 디렉터리를 타겟으로 Out-of-tree 컴파일 실행
sudo make -C /lib/modules/$(uname -r)/build M=/tmp/build_rpfilter modules

# 5. 빌드 완료된 커널 모듈(.ko)을 시스템 커널 모듈 디렉터리로 복사
sudo cp ipt_rpfilter.ko /lib/modules/$(uname -r)/kernel/net/ipv4/netfilter/
sudo cp ip6t_rpfilter.ko /lib/modules/$(uname -r)/kernel/net/ipv6/netfilter/

# 6. 커널 모듈 의존성 갱신 및 활성화(로드)
sudo depmod -a
sudo modprobe ipt_rpfilter
sudo modprobe ip6t_rpfilter

# 7. 모듈 활성화 여부 확인
lsmod | grep rpfilter
```

---

### [2단계] `xt_CT` 커널 모듈 빌드 및 소스 코드 패치 (`tg-orin` 호스트 셸)
Tegra 커널 헤더의 구조체 포인터 타입 불일치(`atomic_t` 대신 conntrack 참조 카운트가 `refcount_t`로 정의됨)를 대응하기 위해 소스코드 패치 후 빌드합니다.

```bash
# 1. 빌드 작업 임시 디렉터리 생성 및 이동
mkdir -p /tmp/build_ct
cd /tmp/build_ct

# 2. 공식 리눅스 커널 저장소에서 xt_CT 소스코드 다운로드
wget -O xt_CT.c "https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/plain/net/netfilter/xt_CT.c?h=v5.15.185"

# 3. 소스코드 내 참조 카운터 처리 함수 수정 (refcount_t 대응 패치)
# - 원본: atomic_inc(&ct->ct_general.use);
# - 변경: refcount_inc(&ct->ct_general.use);
sed -i 's/atomic_inc(&ct->ct_general.use);/refcount_inc(\&ct->ct_general.use);/g' xt_CT.c

# 4. 모듈 빌드를 위한 Makefile 생성
echo "obj-m += xt_CT.o" > Makefile

# 5. Out-of-tree 컴파일 실행
sudo make -C /lib/modules/$(uname -r)/build M=/tmp/build_ct modules

# 6. 빌드 완료된 xt_CT.ko 모듈 복사 및 적재
sudo cp xt_CT.ko /lib/modules/$(uname -r)/kernel/net/netfilter/
sudo depmod -a
sudo modprobe xt_CT

# 7. 모듈 로드 상태 확인 (성공 시 리스트에 출력됨)
lsmod | grep xt_CT
```

---

### [3단계] Calico DaemonSet 환경변수 수정 (`tg-mst` 마스터 노드 셸)
CNI가 젯슨 노드의 가상 USB 브릿지 IP(`192.168.55.1`)를 잘못 감지하지 않고, 노드의 공식 `InternalIP`(`129.254.222.149`)를 사용하도록 변경합니다. 

또한 Tegra 커널의 기술 한계를 우회하기 위한 튜닝 파라미터를 통합하여 수정합니다.

```bash
# 1. Calico의 IP 자동 감지 방식을 노드 객체의 InternalIP로 고정 설정
# (초기화 컨테이너를 포함한 DaemonSet 전체 컨테이너에 대해 동시 변경)
kubectl set env daemonset/calico-node -n kube-system --containers="*" IP_AUTODETECTION_METHOD=kubernetes-internal-ip
kubectl set env daemonset/calico-node -n kube-system --containers="*" IP_AUTODETECT_METHOD=kubernetes-internal-ip

# 2. Tegra 노드 및 클러스터 우회 환경변수 최종 검증 확인 (필요 시 아래 명령으로 세팅)
# - VXLAN 오버레이 고정 및 IPIP 비활성화
kubectl set env daemonset/calico-node -n kube-system --containers="calico-node,upgrade-ipam,install-cni" CALICO_IPV4POOL_VXLAN=Always
kubectl set env daemonset/calico-node -n kube-system --containers="calico-node,upgrade-ipam,install-cni" CALICO_IPV4POOL_IPIP=Never
# - ipset 및 nftables 바이패스 설정
kubectl set env daemonset/calico-node -n kube-system --containers="*" FELIX_IPSETSUPPORTED=false
kubectl set env daemonset/calico-node -n kube-system --containers="*" FELIX_IPTABLESBACKEND=Legacy
```

---

### [4단계] Kubernetes 노드 메타데이터 패치 및 재기동 (`tg-mst` 마스터 노드 셸)
기존에 오인되어 등록되었던 Calico 노드 통신 주소를 실제 노드의 물리 IP 대역으로 변경하여 BGP Peering을 정상화합니다.

```bash
# 1. 오린 노드의 Calico 주소 어노테이션을 물리망 대역인 129.254.222.149/24 로 강제 갱신
kubectl patch node tg-orin -p '{"metadata":{"annotations":{"projectcalico.org/IPv4Address":"129.254.222.149/24"}}}'

# 2. DaemonSet 롤아웃 현황 확인
kubectl rollout status ds/calico-node -n kube-system
```

---

## 3. 최종 상태 검증 명령어 및 결과 확인

조치가 정상적으로 재현/완료되었는지 검증하기 위한 명령어 모음입니다.

### 1) Calico Pod의 기동 상태 조회
```bash
kubectl get pods -n kube-system -o wide | grep -E "calico|orin"
```
* **결과 확인**: `calico-node-xxxxx` (tg-orin 배포 파드)의 상태가 `1/1 Running`으로 표시되어야 함.

### 2) BGP Mesh 피어링 상태 최종 검증
`tg-orin` 노드의 BIRD 라우터 컨트롤 셸로 강제 접속하여 다른 4개 노드와의 피어링 상황을 확인합니다.
```bash
# tg-orin에 배포된 calico-node 파드명을 확인하여 실행합니다.
kubectl exec -n kube-system <calico-node-orin-pod-name> -c calico-node -- /usr/bin/birdcl -s /var/run/calico/bird.ctl show protocols
```
* **기대 결과**: 아래와 같이 마스터 노드(`129.254.222.150`)를 포함한 모든 타 노드들에 대하여 상태가 **`Established`**로 연결되어 있어야 합니다.
  ```text
  BIRD v0.3.3+birdv1.6.8 ready.
  name     proto    table    state  since       info
  static1  Static   master   up     07:17:15    
  kernel1  Kernel   master   up     07:17:15    
  device1  Device   master   up     07:17:15    
  direct1  Direct   master   up     07:17:15    
  Mesh_129_254_222_148 BGP      master   up     07:17:24    Established   
  Mesh_129_254_222_147 BGP      master   up     07:17:45    Established   
  Mesh_129_254_222_146 BGP      master   up     07:17:56    Established   
  Mesh_129_254_222_150 BGP      master   up     07:17:36    Established   
  ```
