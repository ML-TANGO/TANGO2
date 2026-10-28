"""GPU 접근 방식 선택 회귀 테스트 (실장비 없이 검증 가능한 부분).

실행: cd apps/edge_remote_manager && python3 -m pytest test_gpu_selection.py -v

Jetson(Orin) 실장비가 없어 실제 기동은 검증할 수 없지만, **우리가 어떤 docker 인자를
내보내는지**는 여기서 고정한다. 이전 판본은 `nvidia-smi` 유무만 봤고 Jetson 은 그 도구를
제공하지 않아, GPU=auto 가 조용히 CPU 로 컨테이너를 띄웠다(오류 없이 느려지기만 함).
"""
import importlib.util

import pytest

SPEC = importlib.util.spec_from_file_location("agent", "remote_manager_agent.py")


def load(gpu="auto"):
    import os
    os.environ["GPU"] = gpu
    m = importlib.util.module_from_spec(SPEC)
    SPEC.loader.exec_module(m)
    return m


def _as(m, tegra, runtimes=(), has_smi=False):
    m._is_tegra = lambda: tegra
    m._docker_runtimes = lambda: set(runtimes)
    m.shutil.which = lambda x: "/usr/bin/nvidia-smi" if (has_smi and x == "nvidia-smi") else None
    return m


def test_desktop_nvidia_uses_gpus_flag():
    m = _as(load(), tegra=False, has_smi=True)
    assert m._gpu_flags() == ["--gpus", "all"]


def test_jetson_prefers_nvidia_runtime():
    """JetPack/L4T 의 표준 경로. nvidia 런타임이 등록돼 있으면 그쪽이 가장 넓게 동작한다."""
    m = _as(load(), tegra=True, runtimes=("runc", "nvidia"))
    assert m._gpu_flags() == ["--runtime", "nvidia"]


def test_jetson_without_registered_runtime_falls_back_to_gpus():
    """최신 toolkit 이 깔린 JetPack 6 은 --gpus 로도 동작한다."""
    m = _as(load(), tegra=True, runtimes=("runc",))
    assert m._gpu_flags() == ["--gpus", "all"]


def test_jetson_is_never_treated_as_cpu_only():
    """회귀 방지 — nvidia-smi 가 없다는 이유로 GPU 를 포기하면 안 된다."""
    m = _as(load(), tegra=True, runtimes=("runc",), has_smi=False)
    assert m._gpu_available() is True
    assert m._gpu_flags() != []


def test_cpu_only_host_emits_no_gpu_flags():
    m = _as(load(), tegra=False, has_smi=False)
    assert m._gpu_flags() == []
    assert m._gpu_info() == "none"


@pytest.mark.parametrize("mode,expected", [
    ("runtime", ["--runtime", "nvidia"]),
    ("gpus", ["--gpus", "all"]),
    ("off", []),
])
def test_operator_can_force_mode(mode, expected):
    """대상 JetPack 이 확정되면 자동 판별에 의존하지 않고 못박을 수 있어야 한다."""
    m = _as(load(mode), tegra=True, runtimes=("runc",))
    assert m._gpu_flags() == expected
