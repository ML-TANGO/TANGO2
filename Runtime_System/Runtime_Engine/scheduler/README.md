# RTST Orin 스케줄러

Linux 6.12/PREEMPT_RT의 `sched_ext`를 이용해 cgroup의 실행 등급과
CPU 역할을 제어하는 S1b 스케줄러입니다.

## 포함 파일

| 파일 | 역할 |
|---|---|
| `scx_rtst_orin.bpf.c` | 등급별 큐와 CPU별 dispatch를 구현하는 BPF 소스 |
| `scx_rtst_orin.c` | scheduler 연결·해제, cgroup 등급 제어와 진단 |
| `admit-pod.sh` | Pod → 컨테이너 → cgroup을 식별하는 일회성 제어 도구 |
| `test-run-config.sh` | CPU mask 인자 검사 |
| `build.sh` | 외부 Linux SDK를 참조하는 독립 빌드 스크립트 |

다른 scx 스케줄러, Rust workspace와 전체 커널 소스는 포함하지 않습니다.
`SOURCE.json`과 `MANIFEST.sha256`은 소스 신원을 기록합니다. 두 C 소스의
기존 `GPL-2.0` SPDX 표기를 유지합니다.

## 빌드

Linux 교차 빌드 호스트에서 이 폴더를 현재 디렉터리로 두고 실행합니다.
Git checkout과 상위 디렉터리 구조에 의존하지 않으므로 압축을 푼 폴더에서도
빌드할 수 있습니다. 경로는 실제 입력의 절대경로로 바꿉니다.

```bash
KSRC=/path/to/kernel-6.12 \
KOUT=/path/to/target-kernel-build \
SYSROOT=/path/to/aarch64-sysroot \
BPFTOOL=/path/to/bpftool \
  bash ./build.sh
```

`KSRC`에는 대상 커널과 같은 버전의 `tools/sched_ext`·공용 헤더·libbpf
빌드 자산이, `KOUT/vmlinux`에는 해당 커널의 BTF가 있어야 합니다.
ARM64 libelf·zlib·zstd가 있는 sysroot, AArch64 GCC, BPF를 지원하는 Clang,
호스트용 bpftool과 make도 필요합니다. 커널 헤더의 sched_ext ABI가 달라지면
빌드를 지원한다고 가정하지 않습니다.

빌드 스크립트는 외부 SDK의 지원 디렉터리만 임시 연결하고, 우리 두 C 파일만
컴파일 대상으로 지정합니다. 외부 커널 소스를 수정하지 않습니다.
출력은 `build/build/bin/scx_rtst_orin`, 신원 기록은 `build/BUILD.sha256`입니다.
`BUILD`로 별도 출력 경로, `JOBS`로 병렬도를 지정할 수 있습니다.

## 실행과 제어

대상 Orin은 cgroup v2·bpffs와 sched_ext가 활성화된 커널을 사용해야 합니다.
실행 중인 다른 sched_ext 스케줄러와 기존 intent map pin이 없는 상태에서
대상 커널의 BTF로 만든 바이너리를 사용합니다.

12개 CPU가 online인 AGX의 예입니다.

```bash
sudo ./scx_rtst_orin run \
  --rt-cpu 4 --online-mask 0xfff \
  --shared-mask 0xfef --background-mask 0xfe0
```

8개 CPU가 online인 NX의 대응 mask는 `0xff`, `0xef`, `0xe0`입니다.
무인자 기본값은 NX 기준입니다. CPU4는 CPU4-only fair-class 작업의 전용
helper 경로이며 일반·background 작업에서 제외합니다. CPU Manager가
관리하는 Pod cpuset은 변경하지 않습니다.

별도 터미널에서 살아 있는 cgroup v2 경로에 등급을 지정합니다.

```bash
sudo ./scx_rtst_orin set background /sys/fs/cgroup/path/to/container
sudo ./scx_rtst_orin list
sudo ./scx_rtst_orin delete /sys/fs/cgroup/path/to/container
```

`critical`은 공유 CPU에서 먼저 소비하는 큐, `normal`은 기본 큐,
`background`는 background CPU가 소비하는 큐입니다. `set`의 ACK는
map 갱신과 read-back 확인이며 실행 중 모든 스레드의 배치 전환 완료를
보증하지 않습니다. background 첫 배치와 live class 전환은 운영 수용조건을
별도로 검증해야 합니다. 마감·예산 집행과 동적 CPU 배분은 이 S1b의 기능에
포함하지 않습니다.

Pod 제어에는 kubectl·crictl·jq와 필요한 권한을 준비한 뒤 다음을 사용합니다.

```bash
./admit-pod.sh admit NAMESPACE POD_NAME ./scx_rtst_orin
./admit-pod.sh revoke-id SAVED_CGROUP_ID ./scx_rtst_orin
```

일회성 어댑터이므로 Pod 재시작·삭제를 자동 추적하지 않습니다.
연결 종료는 Ctrl+C 또는 SIGTERM을 사용합니다. 정상 종료 시 자신이 만든
intent pin을 제거합니다. 인자 검사만 수행할 때는 대상 AArch64 장비에서
`bash test-run-config.sh /path/to/scx_rtst_orin`을 사용합니다.
