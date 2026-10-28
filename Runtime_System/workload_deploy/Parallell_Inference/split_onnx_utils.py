import torch
import torch.nn as nn
from typing import Sequence, Tuple, Optional


def _seq_from_modules(mods: Sequence[nn.Module]) -> nn.Sequential:
    """모듈 리스트를 nn.Sequential로 묶는 헬퍼."""
    return nn.Sequential(*mods)


def split_sequential_model(
    model: nn.Sequential,
    split_index: int,
) -> Tuple[nn.Sequential, nn.Sequential]:
    """
    순수 nn.Sequential 모델을 앞/뒤로 나누기.
    - split_index 이전까지: client
    - split_index 이후: server
    """
    children = list(model.children())
    assert 0 < split_index < len(children), "split_index 범위 확인"
    client = _seq_from_modules(children[:split_index])
    server = _seq_from_modules(children[split_index:])
    return client, server


def split_feature_backbone_model(
    full_model: nn.Module,
    feature_attr: str,
    split_index: int,
    head_modules: Sequence[nn.Module],
) -> Tuple[nn.Sequential, nn.Sequential]:
    """
    torchvision 계열처럼
      - full_model.features (Sequential)
      - + head 모듈들 (avgpool, flatten, classifier 등)
    구조인 모델을 분할하는 함수.

    예:
        client, server = split_feature_backbone_model(
            full_model,
            feature_attr="features",
            split_index=3,
            head_modules=[full_model.avgpool, nn.Flatten(1), full_model.classifier],
        )
    """
    features: nn.Sequential = getattr(full_model, feature_attr)
    feat_children = list(features.children())
    assert 0 < split_index <= len(feat_children), "split_index 범위 확인"

    client_feats = _seq_from_modules(feat_children[:split_index])
    server_feats = _seq_from_modules(feat_children[split_index:])

    client = client_feats
    server = nn.Sequential(
        server_feats,
        *head_modules,
    )
    return client, server


def export_split_onnx(
    client_model: nn.Module,
    server_model: nn.Module,
    input_shape: Tuple[int, int, int, int],
    client_onnx_path: str,
    server_onnx_path: str,
    opset: int = 11,
    device: Optional[torch.device] = None,
):
    """
    분할된 client_model / server_model 을 ONNX 두 개로 export.

    - client 입력: 원본 입력 (예: [B,3,224,224])
    - client 출력: mid_feat
    - server 입력: mid_feat
    - server 출력: 최종 logits
    """
    if device is None:
        device = torch.device("cpu")

    client_model = client_model.to(device).eval()
    server_model = server_model.to(device).eval()

    # 1) dummy 입력
    dummy_input = torch.randn(*input_shape, device=device)

    # 2) client ONNX export
    torch.onnx.export(
        client_model,
        dummy_input,
        client_onnx_path,
        input_names=["input"],
        output_names=["mid_feat"],
        dynamic_axes={"input": {0: "batch_size"}, "mid_feat": {0: "batch_size"}},
        opset_version=opset,
    )

    # 3) mid_feat 생성
    with torch.no_grad():
        mid_feat = client_model(dummy_input)

    # 4) server ONNX export
    torch.onnx.export(
        server_model,
        mid_feat,
        server_onnx_path,
        input_names=["mid_feat"],
        output_names=["output"],
        dynamic_axes={"mid_feat": {0: "batch_size"}, "output": {0: "batch_size"}},
        opset_version=opset,
    )

    print(f"ONNX export 완료\n  - client: {client_onnx_path}\n  - server: {server_onnx_path}")
