import torch
import torch.nn as nn
import re

def build_vision_projector(config, delay_load=False, **kwargs):
    """
    - 비전 특징을 텍스트 공간으로 변환하는 프로젝터 생성
    - config: 멀티모달 모델 설정
    - delay_load: 지연 로딩 여부
    """
    try:
        projector_type = getattr(config, 'mm_projector_type', 'linear')

        if projector_type == 'linear':
            return nn.Linear(config.mm_hidden_size, config.hidden_size)

        mlp_gelu_match = re.match(r'^mlp(\d+)x_gelu$', projector_type)
        if mlp_gelu_match:
            mlp_depth = int(mlp_gelu_match.group(1))
            modules = [nn.Linear(config.mm_hidden_size, config.hidden_size)]
            for _ in range(1, mlp_depth):
                modules.append(nn.GELU())
                modules.append(nn.Linear(config.hidden_size, config.hidden_size))
            return nn.Sequential(*modules)

        if projector_type == 'identity':
            return nn.Identity()

        raise ValueError(f"알 수 없는 프로젝터 형식: {projector_type}")
    except Exception as e:
        raise RuntimeError(f"비전 프로젝터 빌드 중 에러 발생: {e}")
