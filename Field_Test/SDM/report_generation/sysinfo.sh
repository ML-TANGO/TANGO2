#!/usr/bin/env bash
# Hardware and software configuration of the system under test, for the reviewers.
#
#   ./sysinfo.sh                  host + the gpt-6-luna image
#   LABELER=gemini ./sysinfo.sh   host + the gemini-3.5-flash-lite image
#   GPU=1 ./sysinfo.sh            report a different GPU as the one exposed (default 5)
#
# Prints to the screen and saves the same text to out/sysinfo_<date_time>.txt.
# Read-only: nothing is installed or changed.
set -uo pipefail
cd "$(dirname "$(readlink -f "$0")")"

GPU=${GPU:-5}
case "${LABELER:-luna}" in
  luna)   IMAGE=chest-ct-foundation:tc1;        ID_FILE=IMAGE_ID;        LABEL_MODEL=gpt-6-luna ;;
  gemini) IMAGE=chest-ct-foundation:tc1-gemini; ID_FILE=IMAGE_ID_GEMINI; LABEL_MODEL=gemini-3.5-flash-lite ;;
  *) echo "LABELER must be luna or gemini" >&2; exit 2 ;;
esac

mkdir -p out
LOG=out/sysinfo_$(date +%Y%m%d_%H%M%S).txt
exec > >(tee >(sed 's/\x1b\[[0-9;]*m//g' > "$LOG")) 2>&1

section() { printf '\n\033[1;36m== %s\033[0m\n' "$1"; }
kv()      { printf '  %-27s %s\n' "$1" "$2"; }

printf '\033[1mSystem under test — hardware and software configuration\033[0m\n'
kv "collected" "$(date '+%Y-%m-%d %H:%M:%S %Z')"
kv "host" "$(hostname)"

section "Hardware"
kv "system" "$(cat /sys/class/dmi/id/sys_vendor 2>/dev/null) $(cat /sys/class/dmi/id/board_name 2>/dev/null)"
cpu=$(lscpu | sed -n 's/^Model name: *//p' | head -1)
sockets=$(lscpu | sed -n 's/^Socket(s): *//p')
cores=$(lscpu | sed -n 's/^Core(s) per socket: *//p')
threads=$(nproc --all)
kv "CPU" "$sockets x $cpu"
kv "CPU cores / threads" "$((sockets * cores)) cores / $threads threads"
kv "memory (RAM)" "$(free -g | awk '/^Mem:/ {print $2}') GiB"
ngpu=$(nvidia-smi -L | wc -l)
kv "GPU" "$ngpu x $(nvidia-smi --query-gpu=name,memory.total --format=csv,noheader -i 0)"
kv "GPU exposed to the test" "1 (GPU $GPU, $(nvidia-smi --query-gpu=name,pci.bus_id --format=csv,noheader -i "$GPU"))"
echo "  disks"
lsblk -d -n -o NAME,SIZE,ROTA,TRAN,MODEL -e 7 | awk '{t = ($3 == 1) ? "HDD" : "SSD"; m = $5; for (i = 6; i <= NF; i++) m = m " " $i; printf "    %-9s %7s  %s  %-5s %s\n", $1, $2, t, toupper($4), m}'
kv "disk holding the bundle" "$(df -h --output=source,size,avail . | tail -1 | awk '{print $1", "$2" total, "$3" free"}')"

section "GPUs (nvidia-smi)"
nvidia-smi --query-gpu=index,name,memory.total,memory.used,driver_version --format=csv | sed 's/^/  /'

section "Operating system and drivers"
kv "OS" "$(. /etc/os-release; echo "$PRETTY_NAME")"
kv "kernel" "$(uname -r) ($(uname -m))"
kv "NVIDIA driver" "$(nvidia-smi --query-gpu=driver_version --format=csv,noheader -i 0)"
kv "CUDA (driver supports)" "$(nvidia-smi | grep -o 'CUDA Version: [0-9.]*' | cut -d' ' -f3)"

section "Container runtime"
kv "Docker Engine" "$(docker version --format '{{.Server.Version}}' 2>/dev/null)"
kv "Docker client" "$(docker version --format '{{.Client.Version}}' 2>/dev/null)"
kv "containerd" "$(docker version --format '{{range .Server.Components}}{{if eq .Name "containerd"}}{{.Version}}{{end}}{{end}}' 2>/dev/null)"
kv "NVIDIA Container Toolkit" "$(nvidia-ctk --version 2>/dev/null | head -1 | grep -o '[0-9][0-9.]*$')"

section "Test image"
kv "image" "$IMAGE"
kv "image ID" "$(docker inspect --format '{{.Id}}' "$IMAGE" 2>/dev/null || echo 'not found')"
kv "expected ($ID_FILE)" "$(cat "$ID_FILE")"
kv "created" "$(docker inspect --format '{{.Created}}' "$IMAGE" 2>/dev/null | cut -c1-19)"
kv "size" "$(docker image ls --format '{{.Size}}' "$IMAGE")"
kv "base image" "pytorch/pytorch:2.5.1-cuda12.4-cudnn9-runtime"

section "Software inside the test container"
docker run --rm --gpus "\"device=$GPU\"" --entrypoint python3 -e LABEL_MODEL="$LABEL_MODEL" "$IMAGE" -c '
import importlib.metadata as md, os, platform, sys
import torch
def kv(k, v): print(f"  {k:<27} {v}")
kv("OS (container)", next(l.split("=", 1)[1].strip().strip(chr(34)) for l in open("/etc/os-release") if l.startswith("PRETTY_NAME")))
kv("Python", platform.python_version())
kv("PyTorch", torch.__version__)
kv("CUDA runtime", torch.version.cuda)
v = torch.backends.cudnn.version(); kv("cuDNN", f"{v // 10000}.{v // 100 % 100}.{v % 100}")
kv("GPU visible", f"{torch.cuda.device_count()} x {torch.cuda.get_device_name(0)}" if torch.cuda.is_available() else "none")
pkgs = ["transformers", "peft", "accelerate", "safetensors", "monai", "nibabel", "numpy", "pandas", "rich"]
pkgs += ["google-genai"] if os.environ["LABEL_MODEL"].startswith("gemini") else ["openai"]
for p in pkgs:
    try:
        kv(p, md.version(p))
    except md.PackageNotFoundError:
        pass
' 2>&1 | grep -v -i warning

section "Models"
kv "report generation" "JECT_Generator (MedGemma 1.5 4B + LoRA, JECT encoder), local, offline"
kv "decoding" "greedy, seed 42, batch size 4"
kv "labeler" "$LABEL_MODEL (external API; report text only)"

printf '\n  \033[2msaved to %s\033[0m\n' "$PWD/$LOG"
