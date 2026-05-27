import torch
import torchvision.models as models
import torch.nn as nn

from split_onnx_utils import split_feature_backbone_model, export_split_onnx

# 1. 전체 모델 로드
full_model = models.mobilenet_v3_large(pretrained=True)
full_model.eval()

# 2. 분할 (features[0:3] / features[3:]+avgpool+flatten+classifier)
client_model, server_model = split_feature_backbone_model(
    full_model,
    feature_attr="features",   # full_model.features 사용
    split_index=3,             # 0,1,2 → client / 3~ → server
    head_modules=[
        full_model.avgpool,
        nn.Flatten(1),
        full_model.classifier,
    ],
)

# 3. ONNX export
export_split_onnx(
    client_model=client_model,
    server_model=server_model,
    input_shape=(1, 3, 224, 224),
    client_onnx_path="mobilenetv3_client.onnx",
    server_onnx_path="mobilenetv3_server.onnx",
    opset=11,
)
