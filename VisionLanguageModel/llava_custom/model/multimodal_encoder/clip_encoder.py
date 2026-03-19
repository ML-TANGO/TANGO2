import torch
import torch.nn as nn
from transformers import CLIPVisionModel, CLIPImageProcessor, CLIPVisionConfig

class CLIPVisionTower(nn.Module):
    def __init__(self, vision_tower, args, delay_load=False):
        """
        - CLIP 비전 코더 초기화
        - vision_tower: 모델 경로 또는 이름
        - args: 인자 객체
        - delay_load: 지연 로딩 여부
        """
        super().__init__()
        try:
            self.is_loaded = False
            self.vision_tower_name = vision_tower
            self.select_layer = args.mm_vision_select_layer
            self.select_feature = getattr(args, 'mm_vision_select_feature', 'patch')

            if not delay_load:
                self.load_model()
            else:
                self.cfg_only = CLIPVisionConfig.from_pretrained(self.vision_tower_name)
        except Exception as e:
            raise RuntimeError(f"CLIPVisionTower 초기화 에러 발생: {e}")

    def load_model(self):
        """
        - CLIP 모델과 프로세서 로드
        - 예외 발생 시 빈 에러를 띄움
        """
        try:
            self.image_processor = CLIPImageProcessor.from_pretrained(self.vision_tower_name)
            self.vision_tower = CLIPVisionModel.from_pretrained(self.vision_tower_name)
            self.vision_tower.requires_grad_(False)
            self.is_loaded = True
        except Exception as e:
            raise RuntimeError(f"Vision model 로드 실패: {e}")

    def feature_select(self, image_forward_outs):
        """
        - 선택한 레이어의 특징 추출
        """
        try:
            image_features = image_forward_outs.hidden_states[self.select_layer]
            if self.select_feature == 'patch':
                image_features = image_features[:, 1:]
            elif self.select_feature == 'cls_patch':
                image_features = image_features
            else:
                raise ValueError(f"지원하지 않는 select_feature: {self.select_feature}")
            return image_features
        except Exception as e:
            raise RuntimeError(f"Feature select 중 에러 발생: {e}")

    @torch.no_grad()
    def forward(self, images):
        """
        - 이미지 텐서를 특징 벡터로 인코딩
        """
        try:
            if type(images) is list:
                image_features = []
                for image in images:
                    image_forward_out = self.vision_tower(image.to(device=self.device, dtype=self.dtype).unsqueeze(0), output_hidden_states=True)
                    image_feature = self.feature_select(image_forward_out).to(image.dtype)
                    image_features.append(image_feature)
            else:
                image_forward_outs = self.vision_tower(images.to(device=self.device, dtype=self.dtype), output_hidden_states=True)
                image_features = self.feature_select(image_forward_outs).to(images.dtype)

            return image_features
        except Exception as e:
            raise RuntimeError(f"비전 인코더 forward 작동 불가: {e}")

    @property
    def dummy_feature(self):
        """
        - 더미 특징 벡터 반환
        """
        try:
            return torch.zeros(1, self.hidden_size, device=self.device, dtype=self.dtype)
        except Exception as e:
            raise RuntimeError(f"dummy_feature 반환 실패: {e}")

    @property
    def dtype(self):
        """
        - 데이터 타입 반환
        """
        try:
            return self.vision_tower.dtype
        except Exception as e:
            try:
                return next(self.vision_tower.parameters()).dtype
            except StopIteration:
                return torch.float32

    @property
    def device(self):
        """
        - 디바이스 반환
        """
        try:
            return self.vision_tower.device
        except Exception as e:
            try:
                return next(self.vision_tower.parameters()).device
            except StopIteration:
                return torch.device('cpu')

    @property
    def config(self):
        """
        - 설정 객체 반환
        """
        try:
            if self.is_loaded:
                return self.vision_tower.config
            else:
                return self.cfg_only
        except Exception as e:
            raise RuntimeError(f"Config 접근 중 에러 발생: {e}")

    @property
    def hidden_size(self):
        """
        - 은닉층 크기 반환
        """
        try:
            return self.config.hidden_size
        except Exception as e:
            raise RuntimeError(f"hidden_size 반환 실패: {e}")

    @property
    def num_patches(self):
        """
        - 패치 개수 반환
        """
        try:
            return (self.config.image_size // self.config.patch_size) ** 2
        except Exception as e:
            raise RuntimeError(f"num_patches 반환 실패: {e}")
