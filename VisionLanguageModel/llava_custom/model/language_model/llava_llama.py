import torch
import torch.nn as nn
from transformers import LlamaConfig, LlamaModel, LlamaForCausalLM
from llava_custom.model.multimodal_encoder.clip_encoder import CLIPVisionTower
from llava_custom.model.multimodal_projector.projector import build_vision_projector
from llava_custom.constants import IGNORE_INDEX, IMAGE_TOKEN_INDEX

class LlavaConfig(LlamaConfig):
    model_type = "llava_llama"

class LlavaMetaModel:
    def __init__(self, config):
        """
        - LLaVA 메타 모델 초기화
        """
        super(LlavaMetaModel, self).__init__(config)
        self.vision_tower = None
        self.mm_projector = None

    def get_vision_tower(self):
        """
        - 비전 인코더 반환
        """
        return self.vision_tower

    def initialize_vision_modules(self, model_args):
        """
        - 비전 인코더 및 프로젝터 모듈 초기화
        """
        try:
            self.config.mm_vision_tower = model_args.mm_vision_tower
            self.config.mm_projector_type = getattr(model_args, 'mm_projector_type', 'linear')
            self.config.mm_vision_select_layer = model_args.mm_vision_select_layer
            self.config.mm_vision_select_feature = getattr(model_args, 'mm_vision_select_feature', 'patch')

            if self.vision_tower is None:
                self.vision_tower = CLIPVisionTower(model_args.mm_vision_tower, model_args)

            self.config.mm_hidden_size = self.vision_tower.hidden_size

            if self.mm_projector is None:
                self.mm_projector = build_vision_projector(self.config)
        except Exception as e:
            raise RuntimeError(f"Vision Modules 초기화 실패: {e}")

class LlavaLlamaModel(LlavaMetaModel, LlamaModel):
    config_class = LlavaConfig

    def __init__(self, config: LlamaConfig):
        """
        - LLaVA Llama 하위 모델 초기화
        """
        super(LlavaLlamaModel, self).__init__(config)

class LlavaLlamaForCausalLM(LlamaForCausalLM, LlavaMetaModel):
    config_class = LlavaConfig

    def __init__(self, config):
        """
        - LLaVA Llama Causal LM 모델 초기화
        """
        LlamaForCausalLM.__init__(self, config)
        self.model = LlavaLlamaModel(config)
        self.lm_head = nn.Linear(config.hidden_size, config.vocab_size, bias=False)
        self.post_init()

    def get_model(self):
        """
        - 내부 모델 반환
        """
        return self.model

    def forward(
        self,
        input_ids=None,
        attention_mask=None,
        position_ids=None,
        past_key_values=None,
        inputs_embeds=None,
        labels=None,
        use_cache=None,
        output_attentions=None,
        output_hidden_states=None,
        images=None,
        return_dict=None,
        **kwargs
    ):
        """
        - 멀티모달 포워드 패스 실행
        - 이미지 텐서가 존재 시, 토큰 임베딩 시퀀스 안에 이미지 특징 벡터를 병합
        """
        try:
            # - input_ids가 존재할 경우 IMAGE_TOKEN_INDEX(-200) 및 기타 음수값을 먼저 클램핑
            # - images 유무와 무관하게 embed_tokens에 음수 인덱스가 전달되는 것을 방지
            if input_ids is not None and inputs_embeds is None:
                has_image_token = (input_ids == IMAGE_TOKEN_INDEX).any()
                if has_image_token and images is None:
                    # - 이미지가 없는 배치인데 IMAGE_TOKEN_INDEX가 존재하는 비정상 케이스 처리
                    # - 해당 위치를 pad_token_id(0)으로 치환하여 embed_tokens 에러 방지
                    input_ids = input_ids.clone()
                    input_ids[input_ids == IMAGE_TOKEN_INDEX] = 0
                    if labels is not None:
                        labels = labels.clone()
                        labels[labels == IMAGE_TOKEN_INDEX] = IGNORE_INDEX

            if inputs_embeds is None and images is not None and getattr(self.config, 'mm_vision_tower', None) is not None:
                # - IMAGE_TOKEN_INDEX(-200)가 포함된 input_ids를 그대로 embed_tokens에 넣으면 에러 발생
                # - 임시로 0으로 치환하여 임베딩을 얻은 후 이미지 특징으로 덮어씌움
                input_ids_for_embed = input_ids.clone()
                input_ids_for_embed[input_ids_for_embed == IMAGE_TOKEN_INDEX] = 0

                # - 다른 음수값이 있는지 체크
                if (input_ids_for_embed < 0).any():
                    neg_vals = input_ids_for_embed[input_ids_for_embed < 0].unique()
                    raise RuntimeError(f"input_ids에 예상치 못한 음수값이 포함되어 있습니다: {neg_vals}")

                inputs_embeds = self.get_model().embed_tokens(input_ids_for_embed)

                vision_tower = self.get_model().get_vision_tower()
                image_features = vision_tower(images)
                image_features = self.get_model().mm_projector(image_features)

                new_input_embeds = []
                new_labels = [] if labels is not None else None
                new_attention_mask = [] if attention_mask is not None else None

                for batch_idx, cur_input_ids in enumerate(input_ids):
                    num_images = (cur_input_ids == IMAGE_TOKEN_INDEX).sum()
                    if num_images == 0:
                        new_input_embeds.append(inputs_embeds[batch_idx])
                        if labels is not None:
                            new_labels.append(labels[batch_idx])
                        if attention_mask is not None:
                            new_attention_mask.append(attention_mask[batch_idx])
                        continue

                    cur_image_features = image_features[batch_idx]
                    cur_new_input_embeds = []
                    cur_new_labels = [] if labels is not None else None
                    cur_new_attention_mask = [] if attention_mask is not None else None

                    split_idx = torch.where(cur_input_ids == IMAGE_TOKEN_INDEX)[0]
                    start = 0
                    for split in split_idx:
                        if split > start:
                            cur_new_input_embeds.append(inputs_embeds[batch_idx][start:split])
                            if labels is not None:
                                cur_new_labels.append(labels[batch_idx][start:split])
                            if attention_mask is not None:
                                cur_new_attention_mask.append(attention_mask[batch_idx][start:split])

                        cur_new_input_embeds.append(cur_image_features)
                        if labels is not None:
                            cur_new_labels.append(torch.full((cur_image_features.shape[0],), IGNORE_INDEX, device=labels.device, dtype=labels.dtype))
                        if attention_mask is not None:
                            cur_new_attention_mask.append(torch.full((cur_image_features.shape[0],), 1, device=attention_mask.device, dtype=attention_mask.dtype))

                        start = split + 1

                    if start < cur_input_ids.shape[0]:
                        cur_new_input_embeds.append(inputs_embeds[batch_idx][start:])
                        if labels is not None:
                            cur_new_labels.append(labels[batch_idx][start:])
                        if attention_mask is not None:
                            cur_new_attention_mask.append(attention_mask[batch_idx][start:])

                    new_input_embeds.append(torch.cat(cur_new_input_embeds))
                    if labels is not None:
                        new_labels.append(torch.cat(cur_new_labels))
                    if attention_mask is not None:
                        new_attention_mask.append(torch.cat(cur_new_attention_mask))

                # print(f"[DEBUG] new_input_embeds lengths: {[x.shape for x in new_input_embeds]}")
                inputs_embeds = torch.stack(new_input_embeds)
                if labels is not None:
                    labels = torch.stack(new_labels)
                if attention_mask is not None:
                    attention_mask = torch.stack(new_attention_mask)

                # - NaN 검사
                if torch.isnan(inputs_embeds).any():
                    raise RuntimeError("inputs_embeds에 NaN이 포함되어 있습니다.")

                if labels is not None:
                    valid_labels = labels[labels != IGNORE_INDEX]
                    if valid_labels.numel() > 0:
                        l_min, l_max = valid_labels.min(), valid_labels.max()
                        vocab_size = self.config.vocab_size
                        if l_min < 0 or l_max >= vocab_size:
                            raise RuntimeError(f"labels에 범위를 벗어난 값이 포함되어 있습니다. (min: {l_min}, max: {l_max}, vocab_size: {vocab_size})")

                # - inputs_embeds가 준비되었으므로 input_ids 및 position_ids는 None으로 설정
                # - LlamaModel.forward 에서 inputs_embeds 와 attention_mask 에 맞춰 자동 재설정 유도
                input_ids = None
                position_ids = None

            return super().forward(
                input_ids=input_ids,
                attention_mask=attention_mask,
                position_ids=position_ids,
                past_key_values=past_key_values,
                inputs_embeds=inputs_embeds,
                labels=labels,
                use_cache=use_cache,
                output_attentions=output_attentions,
                output_hidden_states=output_hidden_states,
                return_dict=return_dict
            )
        except Exception as e:
            # CUDA 에러 발생 시 동기화하여 정확한 위치 파악 시도
            torch.cuda.synchronize()
            raise RuntimeError(f"LlavaLlamaForCausalLM forward 중 에러 발생: {e}")

    def prepare_inputs_for_generation(self, input_ids, past_key_values=None, inputs_embeds=None, **kwargs):
        """
        - 추론을 위한 입력 준비 기능
        - images 인자를 그대로 넘겨주도록 처리
        """
        try:
            images = kwargs.pop("images", None)
            _inputs = super().prepare_inputs_for_generation(
                input_ids, past_key_values=past_key_values, inputs_embeds=inputs_embeds, **kwargs
            )
            if images is not None:
                _inputs['images'] = images
            return _inputs
        except Exception as e:
            raise RuntimeError(f"prepare_inputs_for_generation 중 에러: {e}")
