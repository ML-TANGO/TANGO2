#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
imagebuild.py — 배포 아티팩트 생성기

pipeline.py 의 image_build 단계가 호출한다. codegen 이 만든 서비스 코드를
실제 배포 대상에 올릴 수 있는 형태로 포장한다.

deploy_method 별 생성물:
    docker    Dockerfile, docker-compose.yaml, .dockerignore, build.sh
    k8s/k3s   Dockerfile, deployment.yaml, service.yaml, (pvc.yaml), build.sh, deploy.sh
    raw       run.sh, <app>.service(systemd), install.sh

모델 파일은 이미지에 굽지 않고 볼륨으로 마운트하는 것을 기본으로 한다.
    - 모델은 보통 수 GB 라 이미지에 넣으면 빌드·푸시·롤아웃이 모두 느려진다
    - 같은 이미지로 모델만 바꿔 띄우는 운용이 쉬워진다
    - 이미지에 굽고 싶으면 생성된 Dockerfile 하단의 주석 처리된 COPY 를 켜면 된다

생성된 코드는 MODEL_DIR 환경변수로 모델 위치를 덮어쓸 수 있으므로,
컨테이너 안에서는 항상 /models 를 가리키게 해 두었다.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

# 저장소 루트를 검색 경로에 추가 — 이 파일을 개별 CLI 로 실행할 때
# 루트의 yaml_parser 를 찾기 위함이다.
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


try:
    import yaml
except ImportError:  # pragma: no cover
    sys.exit("PyYAML이 필요합니다: pip install pyyaml")


# ---------------------------------------------------------------------------
# 엔진별 베이스 이미지 / 설치 방식
# ---------------------------------------------------------------------------
#   vllm      : vLLM 공식 이미지를 베이스로 쓴다(CUDA + vllm 이 이미 들어 있다)
#   llama.cpp : llama-cpp-python 을 빌드해야 해서 컴파일러가 필요하다
#   pytorch   : CPU 휠 인덱스로 CUDA 의존을 피한다
#   tensorrt  : 현재는 onnxruntime 실행이므로 슬림 이미지로 충분하다
ENGINE_BASE = {
    "vllm": {
        "image": "vllm/vllm-openai:latest",
        "apt": [],
        "pip_pre": [],
        "gpu": True,
        "note": "vLLM 공식 이미지(CUDA 포함). GPU 런타임이 필요합니다.",
    },
    "trtllm": {
        "image": "nvcr.io/nvidia/tensorrt-llm/release:latest",
        "apt": [],
        "pip_pre": [],
        "gpu": True,
        "note": "TensorRT-LLM 공식 이미지(CUDA 포함). GPU 런타임이 필요합니다.",
    },
    "llama.cpp": {
        "image": "python:3.11-slim",
        "apt": ["build-essential", "cmake"],
        "pip_pre": [],
        "gpu": False,
        "note": "llama-cpp-python 을 소스 빌드하므로 컴파일러가 들어갑니다.",
    },
    "pytorch": {
        "image": "python:3.11-slim",
        "apt": [],
        "pip_pre": ["torch --index-url https://download.pytorch.org/whl/cpu"],
        "gpu": False,
        "note": "CPU torch 기준입니다. GPU 로 돌리려면 베이스를 CUDA 이미지로 바꾸세요.",
    },
    "tensorrt": {
        "image": "python:3.11-slim",
        "apt": [],
        "pip_pre": [],
        "gpu": False,
        "note": "현재는 onnxruntime 실행입니다. TensorRT engine 빌드는 미구현입니다.",
    },
}

ARCH_PLATFORM = {"x86": "linux/amd64", "arm": "linux/arm64"}

# storage_class → 쿠버네티스 볼륨 처리 방식
STORAGE_CLASS_MAP = {
    "local": {"pvc": True, "storageClassName": "local-path"},
    "nfs": {"pvc": True, "storageClassName": "nfs"},
    "aws": {"pvc": True, "storageClassName": "gp3"},
    "minio": {"pvc": False, "storageClassName": None},
}

MODEL_MOUNT = "/models"
APP_DIR = "/app"


# ---------------------------------------------------------------------------
# Dockerfile
# ---------------------------------------------------------------------------
def _dockerfile(app_name: str, engine: str, invoke_time: str,
                port: int | None, arch: str,
                has_requirements: bool = True) -> str:
    base = ENGINE_BASE[engine]
    lines = [
        "# ============================================================================",
        f"# {app_name} — {engine} 서비스 이미지 (imagebuild 자동 생성)",
        f"#   {base['note']}",
        "#",
        "# 모델은 이미지에 굽지 않고 볼륨으로 마운트한다(기본).",
        f"#   컨테이너 안 모델 경로: {MODEL_MOUNT}  (MODEL_DIR 환경변수로 코드에 전달)",
        "# ============================================================================",
        f"FROM {base['image']}",
        "",
        f"WORKDIR {APP_DIR}",
        "",
    ]

    if base["apt"]:
        lines += [
            "# 빌드에 필요한 패키지",
            "RUN apt-get update && apt-get install -y --no-install-recommends \\",
            "        " + " ".join(base["apt"]) + " \\",
            "    && rm -rf /var/lib/apt/lists/*",
            "",
        ]

    for spec in base["pip_pre"]:
        lines += [f"RUN pip install --no-cache-dir {spec}", ""]

    lines += [
    ]

    if has_requirements:
        lines += [
            "# 서비스 의존성 (코드보다 먼저 복사해 레이어 캐시를 활용)",
            "COPY requirements.txt .",
            "RUN pip install --no-cache-dir -r requirements.txt",
            "",
        ]
    else:
        lines += [
            "# requirements.txt 가 없는 서비스다. 의존성 설치가 필요하면",
            "# 아래 두 줄을 켜거나 서비스의 설치 스크립트를 호출하세요.",
            "# COPY requirements.txt .",
            "# RUN pip install --no-cache-dir -r requirements.txt",
            "",
        ]

    lines += [
        "# 서비스 코드",
        "COPY . .",
        "",
        f"ENV MODEL_DIR={MODEL_MOUNT}",
        "ENV PYTHONUNBUFFERED=1",
        "",
    ]

    if invoke_time == "user" and port:
        lines += [f"EXPOSE {port}", ""]

    lines += [
        'CMD ["python", "app.py"]',
        "",
        "# ── 모델을 이미지에 구우려면 ────────────────────────────────────────",
        "# 아래 두 줄을 켜고 빌드 컨텍스트에 모델 폴더를 두세요.",
        "# 이미지가 수 GB 커지는 대신 볼륨 마운트가 필요 없어집니다.",
        f"# COPY model/ {MODEL_MOUNT}/",
        f"# ENV MODEL_DIR={MODEL_MOUNT}",
        "",
    ]
    if arch == "arm":
        lines += [
            "# ── ARM 타깃 ────────────────────────────────────────────────────────",
            "# x86 머신에서 빌드한다면 buildx 로 크로스 빌드하세요:",
            f"#   docker buildx build --platform {ARCH_PLATFORM['arm']} -t {app_name} .",
            "",
        ]
    return "\n".join(lines)


def _dockerignore() -> str:
    return "\n".join([
        "# 이미지에 들어갈 필요 없는 것들",
        "__pycache__/",
        "*.pyc",
        "*.log",
        ".git/",
        "README.md",
        "",
        "# 모델은 볼륨으로 마운트한다(이미지에 굽는 경우에만 이 줄을 지우세요)",
        "model/",
        "*.safetensors",
        "*.gguf",
        "*.onnx",
        "*.bin",
        "",
    ])


# ---------------------------------------------------------------------------
# docker compose
# ---------------------------------------------------------------------------
def _compose(app_name: str, image: str, engine: str, invoke_time: str,
             port: int | None, arch: str, mount_volume: str | None,
             model_host_path: str, shared_folder: str | None) -> str:
    svc: dict = {
        "build": {"context": ".", "dockerfile": "Dockerfile"},
        "image": image,
        "restart": "unless-stopped",
        "environment": [f"MODEL_DIR={MODEL_MOUNT}"],
        "volumes": [f"{model_host_path}:{MODEL_MOUNT}:ro"],
    }
    if arch in ARCH_PLATFORM:
        svc["platform"] = ARCH_PLATFORM[arch]
    if invoke_time == "user" and port:
        svc["ports"] = [f"{port}:{port}"]
    if invoke_time in ("period", "event") and shared_folder:
        # 워커는 공유 폴더를 읽고 쓰므로 read-only 로 걸면 안 된다
        svc["volumes"].append(f"{mount_volume or './data'}:{shared_folder}")

    doc = {"services": {app_name: svc}}
    if ENGINE_BASE[engine]["gpu"]:
        svc["deploy"] = {"resources": {"reservations": {"devices": [
            {"driver": "nvidia", "count": "all", "capabilities": ["gpu"]}]}}}

    header = [
        f"# {app_name} 실행 정의 (imagebuild 자동 생성)",
        "#",
        "#   docker compose up -d --build",
        "#   docker compose logs -f",
        "#",
        f"# 모델 경로는 호스트의 {model_host_path} 를 {MODEL_MOUNT} 로 마운트합니다.",
        "# 다른 위치에 있다면 volumes 의 왼쪽 경로를 바꾸세요.",
        "",
    ]
    if ENGINE_BASE[engine]["gpu"]:
        header.insert(-1, "# GPU 가 필요합니다 (nvidia-container-toolkit).")
    return "\n".join(header) + yaml.safe_dump(doc, allow_unicode=True,
                                              sort_keys=False, default_flow_style=False)


# ---------------------------------------------------------------------------
# 쿠버네티스 매니페스트
# ---------------------------------------------------------------------------
def _k8s_manifests(app_name: str, image: str, engine: str, invoke_time: str,
                   port: int | None, replicas: int, storage_class: str | None,
                   mount_volume: str | None, shared_folder: str | None) -> dict:
    """deployment / service / pvc 매니페스트를 dict 로 만들어 반환."""
    labels = {"app": app_name}
    storage = STORAGE_CLASS_MAP.get((storage_class or "local").lower(),
                                    STORAGE_CLASS_MAP["local"])

    container: dict = {
        "name": app_name,
        "image": image,
        "imagePullPolicy": "IfNotPresent",
        "env": [{"name": "MODEL_DIR", "value": MODEL_MOUNT}],
        "volumeMounts": [{"name": "model", "mountPath": MODEL_MOUNT,
                          "readOnly": True}],
        "resources": {
            "requests": {"cpu": "500m", "memory": "2Gi"},
            "limits": {"cpu": "2", "memory": "8Gi"},
        },
    }
    if ENGINE_BASE[engine]["gpu"]:
        container["resources"]["limits"]["nvidia.com/gpu"] = 1

    if invoke_time == "user" and port:
        container["ports"] = [{"containerPort": port, "name": "http"}]
        # 모델 로드가 오래 걸릴 수 있어 startupProbe 로 여유를 준다
        container["startupProbe"] = {
            "httpGet": {"path": "/health", "port": port},
            "periodSeconds": 10, "failureThreshold": 60,
        }
        container["readinessProbe"] = {
            "httpGet": {"path": "/health", "port": port},
            "periodSeconds": 10,
        }

    volumes: list = []
    if storage["pvc"]:
        volumes.append({"name": "model",
                        "persistentVolumeClaim": {"claimName": f"{app_name}-model"}})
    else:
        # minio 등 오브젝트 스토리지는 PVC 가 아니라 초기화 단계에서 내려받는다
        volumes.append({"name": "model", "emptyDir": {}})

    if invoke_time in ("period", "event") and shared_folder:
        container["volumeMounts"].append({"name": "shared",
                                          "mountPath": shared_folder})
        volumes.append({"name": "shared",
                        "persistentVolumeClaim": {"claimName": f"{app_name}-shared"}}
                       if storage["pvc"] else {"name": "shared", "emptyDir": {}})

    deployment = {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": {"name": app_name, "labels": dict(labels)},
        "spec": {
            "replicas": replicas,
            "selector": {"matchLabels": dict(labels)},
            "template": {
                "metadata": {"labels": dict(labels)},
                "spec": {"containers": [container], "volumes": volumes},
            },
        },
    }

    out = {"deployment.yaml": deployment}

    if invoke_time == "user" and port:
        out["service.yaml"] = {
            "apiVersion": "v1",
            "kind": "Service",
            "metadata": {"name": app_name, "labels": dict(labels)},
            "spec": {
                "type": "ClusterIP",
                "selector": dict(labels),
                "ports": [{"port": port, "targetPort": port,
                           "protocol": "TCP", "name": "http"}],
            },
        }

    if storage["pvc"]:
        claims = [("model", "20Gi")]
        if invoke_time in ("period", "event") and shared_folder:
            claims.append(("shared", "5Gi"))
        pvcs = []
        for suffix, size in claims:
            pvcs.append({
                "apiVersion": "v1",
                "kind": "PersistentVolumeClaim",
                "metadata": {"name": f"{app_name}-{suffix}"},
                "spec": {
                    "accessModes": ["ReadWriteOnce" if suffix == "model"
                                    else "ReadWriteMany"],
                    "storageClassName": storage["storageClassName"],
                    "resources": {"requests": {"storage": size}},
                },
            })
        out["pvc.yaml"] = pvcs

    return out


def _dump_manifest(obj) -> str:
    if isinstance(obj, list):
        return "---\n".join(
            yaml.safe_dump(o, allow_unicode=True, sort_keys=False) for o in obj)
    return yaml.safe_dump(obj, allow_unicode=True, sort_keys=False)


# ---------------------------------------------------------------------------
# 스크립트
# ---------------------------------------------------------------------------
def _build_sh(image: str, arch: str) -> str:
    platform = ARCH_PLATFORM.get(arch, ARCH_PLATFORM["x86"])
    return "\n".join([
        "#!/usr/bin/env bash",
        "# 이미지 빌드 (imagebuild 자동 생성)",
        "set -euo pipefail",
        "cd \"$(dirname \"$0\")\"",
        "",
        f'IMAGE="${{IMAGE:-{image}}}"',
        f'PLATFORM="${{PLATFORM:-{platform}}}"',
        "",
        'echo "[build] $IMAGE ($PLATFORM)"',
        "if docker buildx version >/dev/null 2>&1; then",
        '    docker buildx build --platform "$PLATFORM" -t "$IMAGE" --load .',
        "else",
        '    echo "[warn] buildx 가 없어 호스트 아키텍처로 빌드합니다."',
        '    docker build -t "$IMAGE" .',
        "fi",
        'echo "[done] $IMAGE"',
        "",
    ])


def _deploy_sh(app_name: str, deploy_method: str, has_service: bool,
               has_pvc: bool) -> str:
    kubectl = "kubectl" if deploy_method == "k8s" else "sudo k3s kubectl"
    order = (["pvc.yaml"] if has_pvc else []) + ["deployment.yaml"] + \
            (["service.yaml"] if has_service else [])
    lines = [
        "#!/usr/bin/env bash",
        f"# {deploy_method} 배포 (imagebuild 자동 생성)",
        "set -euo pipefail",
        "cd \"$(dirname \"$0\")\"",
        "",
        f'KUBECTL="${{KUBECTL:-{kubectl}}}"',
        f'NAMESPACE="${{NAMESPACE:-default}}"',
        "",
    ]
    for f in order:
        lines.append(f'$KUBECTL -n "$NAMESPACE" apply -f {f}')
    lines += [
        "",
        f'$KUBECTL -n "$NAMESPACE" rollout status deployment/{app_name} --timeout=10m',
        f'$KUBECTL -n "$NAMESPACE" get pods -l app={app_name}',
        "",
    ]
    if not has_pvc:
        lines += [
            '# storage_class=minio — PVC 대신 emptyDir 를 씁니다.',
            '# 파드 기동 후 모델을 내려받는 initContainer 를 deployment.yaml 에 추가하세요.',
            "",
        ]
    return "\n".join(lines)


def _systemd_unit(app_name: str, workdir: str, model_dir: str,
                  invoke_time: str) -> str:
    return "\n".join([
        "# systemd 유닛 (imagebuild 자동 생성)",
        f"#   sudo cp {app_name}.service /etc/systemd/system/",
        "#   sudo systemctl daemon-reload",
        f"#   sudo systemctl enable --now {app_name}",
        "",
        "[Unit]",
        f"Description={app_name} 추론 서비스",
        "After=network-online.target",
        "Wants=network-online.target",
        "",
        "[Service]",
        "Type=simple",
        f"WorkingDirectory={workdir}",
        f"Environment=MODEL_DIR={model_dir}",
        "Environment=PYTHONUNBUFFERED=1",
        f"ExecStart={workdir}/venv/bin/python {workdir}/app.py",
        "Restart=on-failure",
        "RestartSec=10",
        # 모델 로딩이 길어질 수 있어 기동 타임아웃을 늘려 둔다
        "TimeoutStartSec=600",
        "",
        "[Install]",
        "WantedBy=multi-user.target",
        "",
    ])


def _install_sh(app_name: str) -> str:
    return "\n".join([
        "#!/usr/bin/env bash",
        "# 베어메탈 설치 (imagebuild 자동 생성)",
        "#   가상환경을 만들고 의존성을 설치한 뒤 systemd 유닛을 등록한다.",
        "set -euo pipefail",
        'cd "$(dirname "$0")"',
        "",
        'WORKDIR="$(pwd)"',
        "",
        'echo "[install] 가상환경 생성"',
        "python3 -m venv venv",
        "./venv/bin/pip install --upgrade pip",
        "./venv/bin/pip install -r requirements.txt",
        "",
        'echo "[install] systemd 유닛 등록"',
        f"sed -i \"s|^WorkingDirectory=.*|WorkingDirectory=$WORKDIR|\" {app_name}.service",
        f"sed -i \"s|^ExecStart=.*|ExecStart=$WORKDIR/venv/bin/python $WORKDIR/app.py|\" {app_name}.service",
        f"sudo cp {app_name}.service /etc/systemd/system/",
        "sudo systemctl daemon-reload",
        f"sudo systemctl enable --now {app_name}",
        "",
        f'echo "[done] systemctl status {app_name}"',
        "",
    ])


def _run_sh(app_name: str, model_dir: str) -> str:
    return "\n".join([
        "#!/usr/bin/env bash",
        "# 전경 실행 (systemd 없이 바로 띄워 볼 때)",
        "set -euo pipefail",
        'cd "$(dirname "$0")"',
        "",
        f'export MODEL_DIR="${{MODEL_DIR:-{model_dir}}}"',
        "export PYTHONUNBUFFERED=1",
        "",
        'if [ -x ./venv/bin/python ]; then',
        '    exec ./venv/bin/python app.py',
        "else",
        '    exec python3 app.py',
        "fi",
        "",
    ])


# ---------------------------------------------------------------------------
# README
# ---------------------------------------------------------------------------
def _readme(app_name: str, deploy_method: str, engine: str, arch: str,
            image: str, invoke_time: str, port: int | None,
            storage_class: str | None, files: list[str]) -> str:
    lines = [
        f"# {app_name} 배포 아티팩트",
        "",
        "`imagebuild` 가 자동 생성했습니다. codegen 이 만든 서비스 코드와 같은 폴더에",
        "두고 사용하는 것을 전제로 합니다.",
        "",
        "## 구성",
        "",
        f"- 배포 방식: `{deploy_method}`",
        f"- 엔진: `{engine}` / 타깃 아키텍처: `{arch}`",
        f"- 이미지: `{image}`" if deploy_method != "raw" else "- 컨테이너 없이 직접 실행",
        f"- 구동 방식: `{invoke_time}`",
        "",
        "모델은 이미지에 굽지 않고 마운트합니다. 컨테이너 안 경로는",
        f"`{MODEL_MOUNT}` 이고, 코드에는 `MODEL_DIR` 환경변수로 전달됩니다.",
        "",
    ]

    if deploy_method == "docker":
        lines += [
            "## 실행",
            "",
            "```bash",
            "./build.sh                    # 이미지 빌드",
            "docker compose up -d          # 기동",
            "docker compose logs -f",
            "```",
            "",
            "`docker-compose.yaml` 의 volumes 왼쪽 경로가 호스트의 모델 위치입니다.",
            "",
        ]
    elif deploy_method in ("k8s", "k3s"):
        lines += [
            "## 실행",
            "",
            "```bash",
            "./build.sh                    # 이미지 빌드",
            "# 레지스트리를 쓴다면 여기서 push",
            "./deploy.sh                   # 매니페스트 적용",
            "```",
            "",
            f"`storage_class={storage_class}` 기준으로 볼륨을 구성했습니다.",
        ]
        if (storage_class or "").lower() == "minio":
            lines += [
                "",
                "> minio 는 PVC 대상이 아니라 `emptyDir` 로 잡혀 있습니다.",
                "> 파드 기동 시 모델을 내려받는 initContainer 를 `deployment.yaml` 에",
                "> 추가해야 실제로 동작합니다.",
            ]
        lines += [
            "",
            "모델 로딩이 길어질 수 있어 `startupProbe` 를 넉넉히(최대 10분) 잡아 두었습니다.",
            "",
        ]
    else:  # raw
        lines += [
            "## 실행",
            "",
            "```bash",
            "./install.sh                  # venv 생성 + systemd 등록",
            f"systemctl status {app_name}",
            "```",
            "",
            "systemd 없이 바로 띄워 보려면 `./run.sh` 를 쓰세요.",
            "",
        ]

    if invoke_time == "user" and port:
        lines += [f"서비스 포트는 `{port}` 입니다.", ""]

    lines += ["## 생성된 파일", ""]
    lines += [f"- `{f}`" for f in files]
    lines += ["", "> 생성물입니다. 파이프라인을 다시 돌리면 덮어쓰입니다.", ""]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 공개 API
# ---------------------------------------------------------------------------
def build_artifacts(plan, cfg, out_dir, service_dir=None, model_dir=None):
    """배포 아티팩트를 생성한다.

    인자:
        plan        : yaml_parser.Plan
        cfg         : yaml_parser.DeployConfig
        out_dir     : 생성 위치
        service_dir : codegen 산출물 폴더 (상대경로 안내용)
        model_dir   : 변환된 모델 폴더 (호스트 마운트 경로 안내용)

    반환값:
        (0, "success 메시지") 또는 (-1, "<오류 메시지>")
    """
    try:
        ib = cfg.image_build
        bi = ib.build_info
        deploy_method = (ib.deploy_method or "docker").lower()
        if deploy_method not in ("docker", "k8s", "k3s", "raw"):
            return (-1, f"알 수 없는 deploy_method 입니다: {deploy_method}")

        engine = plan.target_engine
        if engine not in ENGINE_BASE:
            return (-1, f"배포를 지원하지 않는 엔진입니다: {engine}")

        app_name = bi.app_name or "model-service"
        image = bi.image_file or f"{app_name}:latest"
        arch = (bi.target_arch or "x86").lower()
        if arch not in ARCH_PLATFORM:
            return (-1, f"target_arch 는 x86 또는 arm 이어야 합니다 (받은 값: {arch})")
        replicas = bi.replicas_num or 1

        spec = cfg.code_generation.service_info.spec
        invoke_time = (spec.invoke_time or "user").lower()
        port = bi.target_port or spec.service_port
        shared_folder = spec.service_shared_folder
        storage_class = (bi.storage_class or "local").lower()

        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        written: list[str] = []

        def write(name: str, content: str, executable: bool = False):
            p = out / name
            p.write_text(content, encoding="utf-8")
            if executable:
                p.chmod(0o755)
            written.append(name)

        # 서비스 코드를 같은 폴더로 복사해 '그 자리에서 바로 빌드되는' 컨텍스트를 만든다.
        #   Dockerfile 의 COPY . . 가 app.py/engine.py/requirements.txt 를 찾으려면
        #   이들이 빌드 컨텍스트 안에 있어야 한다.
        copied: list[str] = []
        if service_dir:
            svc_path = Path(service_dir)
            if svc_path.is_dir():
                for entry in sorted(svc_path.iterdir()):
                    if entry.is_dir():
                        # 템플릿 기반 서비스는 코드가 폴더 구조로 들어온다
                        shutil.copytree(entry, out / entry.name,
                                        dirs_exist_ok=True)
                        copied.append(entry.name + "/")
                        continue
                    if not entry.is_file():
                        continue
                    # 서비스 README 는 배포 README 와 이름이 겹치므로 옮겨 둔다
                    target = out / ("SERVICE.md" if entry.name == "README.md"
                                    else entry.name)
                    shutil.copy2(entry, target)
                    copied.append(target.name)
            else:
                return (-1, f"서비스 코드 폴더를 찾을 수 없습니다: {svc_path}. "
                            "codegen 단계를 먼저 실행하세요.")
        has_requirements = bool(service_dir) and \
            (Path(service_dir) / "requirements.txt").is_file()

        host_model = model_dir or "../30_converted"

        if deploy_method == "raw":
            write("run.sh", _run_sh(app_name, host_model), executable=True)
            write(f"{app_name}.service",
                  _systemd_unit(app_name, "/opt/" + app_name, host_model, invoke_time))
            write("install.sh", _install_sh(app_name), executable=True)
        else:
            write("Dockerfile", _dockerfile(app_name, engine, invoke_time, port,
                                            arch, has_requirements))
            write(".dockerignore", _dockerignore())
            write("build.sh", _build_sh(image, arch), executable=True)

            if deploy_method == "docker":
                write("docker-compose.yaml",
                      _compose(app_name, image, engine, invoke_time, port, arch,
                               bi.mount_volume, host_model, shared_folder))
            else:
                manifests = _k8s_manifests(
                    app_name, image, engine, invoke_time, port, replicas,
                    storage_class, bi.mount_volume, shared_folder)
                for name, obj in manifests.items():
                    write(name, _dump_manifest(obj))
                write("deploy.sh",
                      _deploy_sh(app_name, deploy_method,
                                 has_service="service.yaml" in manifests,
                                 has_pvc="pvc.yaml" in manifests),
                      executable=True)

        write("README.md",
              _readme(app_name, deploy_method, engine, arch, image, invoke_time,
                      port, storage_class, written + ["README.md"]))

        hint = f", 서비스 코드 {len(copied)}개 동봉" if copied else ""
        return (0, f"{deploy_method} / {engine} / {arch} 아티팩트 생성 "
                   f"({len(written)}개 파일{hint})")

    except Exception as e:
        return (-1, f"{type(e).__name__}: {e}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> int:
    import argparse
    from yaml_parser import DeployConfig

    ap = argparse.ArgumentParser(description="배포 아티팩트 생성기")
    ap.add_argument("config", help="deploy.yaml 경로")
    ap.add_argument("-o", "--output", default="./image", help="생성 위치")
    ap.add_argument("--model-dir", default=None,
                    help="모델 폴더 경로 (기본: ../30_converted)")
    args = ap.parse_args()

    cfg = DeployConfig.from_yaml(args.config)
    errors, warnings = cfg.validate()
    for w in warnings:
        print(f"[WARN ] {w}", file=sys.stderr)
    if errors:
        for e in errors:
            print(f"[ERROR] {e}", file=sys.stderr)
        return 2

    code, msg = build_artifacts(cfg.resolve_plan(), cfg, args.output,
                                model_dir=args.model_dir)
    if code == 0:
        print(f"[done] {args.output} — {msg}")
        return 0
    print(f"오류: {msg}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
