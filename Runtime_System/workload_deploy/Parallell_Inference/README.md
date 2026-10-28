# split_onnx_utils

PyTorch 모델을 클라이언트 / 서버로 분할하여 각각 ONNX로 내보내기 위한 간단한 유틸 모듈입니다.  
특히 `torchvision`의 CNN 분류 모델(`features + classifier` 구조)에 최적화되어 있으며,  
분산 추론(split inference) 실험에 바로 사용할 수 있습니다.

---

## 🔧 주요 기능

- **Sequential 모델 분할:**  
  `split_sequential_model(model, split_index)`
- **백본(feature) + 헤드(head) 구조 모델 분할:**  
  `split_feature_backbone_model(full_model, feature_attr, split_index, head_modules)`
- **분할된 모델 ONNX export:**  
  `export_split_onnx(client_model, server_model, input_shape, client_onnx_path, server_onnx_path)`

---

## 🚀 사용 예시

### MobileNetV3 분할 예시

```python
import torch
import torchvision.models as models
import torch.nn as nn
from split_onnx_utils import split_feature_backbone_model, export_split_onnx

# 전체 모델 로드
full_model = models.mobilenet_v3_large(pretrained=True).eval()

# features[0:3] → client / 나머지 + head → server
client_model, server_model = split_feature_backbone_model(
    full_model,
    feature_attr="features",
    split_index=3,
    head_modules=[
        full_model.avgpool,
        nn.Flatten(1),
        full_model.classifier,
    ],
)

# ONNX export
export_split_onnx(
    client_model,
    server_model,
    input_shape=(1, 3, 224, 224),
    client_onnx_path="mobilenetv3_client.onnx",
    server_onnx_path="mobilenetv3_server.onnx",
)