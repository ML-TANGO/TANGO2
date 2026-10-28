#!/bin/bash
# 공유 HuggingFace 캐시(hf-model-cache-pvc)에 모델 가중치를 미리 받아 두는 운영 도구.
#
# 왜 필요한가: 외부 컨테이너 잡의 `/hf-cache` 는 **RO 마운트**이고 manifest env 가
# HF_HUB_OFFLINE=1(폐쇄망 전제)이라, 파드 안에서는 가중치를 받을 수 없다.
# external_container/templates/pod.yaml 주석이 "operator 가 미리 받아 둔다"를 계약으로
# 못박고 있는데 그 단계가 리포에 없어서 사람 기억에 의존했고, 실제로 누락되어
# eva-vlm-train 이 model_loaded=false → /health 503 으로 교착했다. 그 단계를 여기 고정한다.
#
# 사용:
#   ./run.sh <workspace-namespace> [모델...]
#   ./run.sh tango-dev-2                       # 기본 목록(SDS VLM 학습용 2종)
#   ./run.sh jonathan-system-2 openai/clip-vit-large-patch14-336
#
# 전제: 대상 ns 에 hf-model-cache-pvc 가 있고, 플랫폼 ns 의 jfb-settings 에
#       HUGGINGFACE_TOKEN 이 있다(gated repo 인 meta-llama 는 토큰 필수).
set -euo pipefail

NS="${1:?usage: run.sh <workspace-namespace> [models...]}"; shift || true
MODELS=("$@")
if [ ${#MODELS[@]} -eq 0 ]; then
  # SDS VLM(eva-vlm-train) 이 요구하는 2종. 다른 파트너 컨테이너가 늘면 여기 추가.
  MODELS=("openai/clip-vit-large-patch14-336" "meta-llama/Llama-3.1-8B-Instruct")
fi

# 플랫폼 ns = 워크스페이스 ns 에서 마지막 `-<id>` 를 뗀 것 (tango-dev-2 → tango-dev).
PLATFORM_NS="${NS%-*}"
TOKEN="$(kubectl get cm -n "$PLATFORM_NS" jfb-settings -o jsonpath='{.data.HUGGINGFACE_TOKEN}' 2>/dev/null || true)"
[ -n "$TOKEN" ] || echo "[warn] HUGGINGFACE_TOKEN 없음 — gated repo(meta-llama)는 실패한다" >&2

# 토큰은 리포/Job 스펙에 남기지 않는다 — 대상 ns 에 Secret 으로만 넣는다.
kubectl create secret generic hf-prefetch-token -n "$NS" \
  --from-literal=HF_TOKEN="$TOKEN" --dry-run=client -o yaml | kubectl apply -f -

JOB="hf-prefetch-$(date +%s)"
echo "[job] $JOB (ns=$NS) models: ${MODELS[*]}"

kubectl apply -f - <<YAML
apiVersion: batch/v1
kind: Job
metadata:
  name: $JOB
  namespace: $NS
spec:
  backoffLimit: 1
  template:
    spec:
      restartPolicy: Never
      containers:
      - name: prefetch
        image: python:3.11-slim
        env:
        - name: HF_HOME
          value: /hf-cache
        - name: MODELS
          value: "${MODELS[*]}"
        - name: HF_TOKEN
          valueFrom:
            secretKeyRef: { name: hf-prefetch-token, key: HF_TOKEN }
        command: ["/bin/sh","-c"]
        args:
        - |
          set -e
          pip install --no-cache-dir 'huggingface_hub>=0.24' >/dev/null
          python3 - <<'PY'
          import os
          from huggingface_hub import snapshot_download
          for repo in os.environ["MODELS"].split():
              print(f"[prefetch] {repo}", flush=True)
              # original/*.pth 는 safetensors 와 중복인 원본 체크포인트다(Llama 계열에서
              # 16GB 가량). 플랫폼은 torch.load 를 쓰지 않으므로 받지 않는다.
              p = snapshot_download(
                  repo_id=repo,
                  token=os.environ.get("HF_TOKEN") or None,
                  ignore_patterns=["original/*", "*.pth", "*.msgpack", "*.h5"],
              )
              print(f"[prefetch] done → {p}", flush=True)
          PY
          # ── safetensors 보정 ──────────────────────────────────────────────
          # 일부 상위 저장소는 safetensors 를 아예 게시하지 않는다(예:
          # openai/clip-vit-large-patch14-336 = pytorch_model.bin + tf_model.h5 뿐).
          # 그런데 파트너 컨테이너는 `from_pretrained(..., use_safetensors=True)` 로
          # 부르기 때문에(eva-vlm 은 v11·1.1.0 모두 동일) 그대로 두면
          # "does not appear to have a file named model.safetensors" 로 학습이 죽는다.
          # 플랫폼 방침(.bin 직접 로드 금지)과도 맞으므로 스테이징 시점에 변환해 둔다.
          # torch 는 변환이 필요할 때만 설치한다(CPU 휠) — 없는 경우가 대부분이라
          # 공통 경로를 무겁게 만들지 않는다.
          python3 - <<'PY' > /tmp/need_convert.txt
          import os, glob
          need = []
          for repo in os.environ["MODELS"].split():
              d = os.path.join("/hf-cache/hub", "models--" + repo.replace("/", "--"), "snapshots")
              for snap in glob.glob(os.path.join(d, "*")):
                  if glob.glob(os.path.join(snap, "*.safetensors")):
                      continue
                  if os.path.exists(os.path.join(snap, "pytorch_model.bin")):
                      need.append(snap)
          print("\n".join(need))
          PY
          if [ -s /tmp/need_convert.txt ]; then
            echo "[convert] safetensors 없는 스냅샷 발견 — torch(CPU) 설치 후 변환"
            pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu >/dev/null
            # numpy 는 safetensors 가 텐서를 직렬화할 때 내부적으로 쓴다
            # (없으면 save_file 이 ModuleNotFoundError 로 죽는다).
            pip install --no-cache-dir safetensors numpy >/dev/null
            python3 - <<'PY'
          import torch, os
          from safetensors.torch import save_file
          for snap in open("/tmp/need_convert.txt").read().split():
              src = os.path.join(snap, "pytorch_model.bin")
              dst = os.path.join(snap, "model.safetensors")
              print(f"[convert] {src} → {dst}", flush=True)
              # weights_only=True = pickle 임의코드 실행 차단(플랫폼 torch CVE 방침).
              sd = torch.load(src, map_location="cpu", weights_only=True)
              # 공유 스토리지를 가진 텐서는 safetensors 가 거부한다 → clone 으로 분리.
              sd = {k: v.detach().clone().contiguous() for k, v in sd.items()
                    if hasattr(v, "detach")}
              # metadata format=pt 가 없으면 transformers 가 프레임워크를 못 정한다.
              save_file(sd, dst, metadata={"format": "pt"})
              # save_file 은 0600 으로 만든다. 파트너 잡 파드는 차트 기본값이
              # 비-root(runAsNonRoot/runAsUser=1000, SP-1 v2 §7.1)라 그대로 두면
              # 읽지 못하고, safetensors 는 그 권한 오류를 FileNotFoundError 로
              # 표면화해 원인 추적이 어렵다. 캐시는 공유 RO 자산이므로 0644.
              os.chmod(dst, 0o644)
              print(f"[convert] done ({os.path.getsize(dst)/1e9:.2f} GB)", flush=True)
          PY
          else
            echo "[convert] 변환 필요 없음"
          fi
          # 다운로드/변환 산출물을 비-root 잡 파드가 읽을 수 있게 마무리 보정.
          # (huggingface_hub 는 0644 로 받지만 umask·도구에 따라 예외가 생긴다.)
          chmod -R a+rX /hf-cache/hub 2>/dev/null || true
        # 워크스페이스 ns 에는 ResourceQuota 가 걸려 있어 limits 를 명시하지 않으면
        # 파드 생성 자체가 거부된다(FailedCreate: must specify limits.cpu/memory).
        # 다운로드는 네트워크·디스크 바운드라 작게 잡는다.
        resources:
          requests: { cpu: "500m", memory: "1Gi" }
          limits: { cpu: "2", memory: "4Gi" }
        volumeMounts:
        - name: hf-model-cache
          mountPath: /hf-cache
      volumes:
      - name: hf-model-cache
        persistentVolumeClaim:
          claimName: hf-model-cache-pvc
YAML

echo "[wait] kubectl -n $NS logs -f job/$JOB"
# 끝나면 정리(토큰 Secret 을 워크스페이스 ns 에 남기지 않는다 — 다음 실행 때 다시 만든다):
echo "[cleanup] kubectl -n $NS delete job/$JOB secret/hf-prefetch-token"
