"""Local Hugging Face Transformers provider for the v2 runner."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from ..core.types import Usage
from .base import Completion
from .registry import register_provider

if TYPE_CHECKING:
    from ..config.schema import ModelConfig


@dataclass(slots=True)
class TransformersProvider:
    id: str
    request_model: str
    processor: Any
    model: Any
    device: str
    max_tokens: int
    do_sample: bool

    async def complete(self, system: str, user: str) -> Completion:
        import torch

        tokenizer = getattr(self.processor, "tokenizer", self.processor)
        content = f"{system}\n\n{user}" if system else user
        encoded = tokenizer.apply_chat_template(
            [{"role": "user", "content": content}],
            add_generation_prompt=True,
            tokenize=True,
            return_tensors="pt",
            return_dict=True,
        )
        if hasattr(encoded, "keys") and "input_ids" in encoded:
            input_ids = encoded["input_ids"].to(self.device)
            attention_mask = encoded.get("attention_mask")
            attention_mask = attention_mask.to(self.device) if attention_mask is not None else None
        else:
            input_ids = encoded.to(self.device)
            attention_mask = None

        input_tokens = int(input_ids.shape[-1])
        try:
            with torch.inference_mode():
                output = self.model.generate(
                    input_ids=input_ids,
                    attention_mask=attention_mask,
                    max_new_tokens=self.max_tokens,
                    do_sample=self.do_sample,
                    use_cache=True,
                )
        except RuntimeError:
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            raise

        generated = output[:, input_tokens:]
        text = tokenizer.decode(generated[0], skip_special_tokens=True)
        return Completion(
            text=text,
            usage=Usage(input_tokens=input_tokens, output_tokens=int(generated.shape[-1])),
        )


def _build_transformers(config: ModelConfig) -> TransformersProvider:
    import torch
    from transformers import AutoModelForImageTextToText, AutoProcessor

    extras = config.request.model_dump(exclude={"model", "max_tokens", "temperature", "stream"})
    device = str(extras.get("device", "cuda"))
    dtype = _dtype(str(extras.get("dtype", "bfloat16")), torch)
    trust_remote_code = bool(extras.get("trust_remote_code", True))
    processor = AutoProcessor.from_pretrained(config.request.model, trust_remote_code=trust_remote_code)
    model = AutoModelForImageTextToText.from_pretrained(
        config.request.model,
        dtype=dtype,
        trust_remote_code=trust_remote_code,
    ).to(device)
    model.eval()
    return TransformersProvider(
        id=config.id,
        request_model=config.request.model,
        processor=processor,
        model=model,
        device=device,
        max_tokens=config.request.max_tokens or 128,
        do_sample=bool(extras.get("do_sample", False)),
    )


def _dtype(name: str, torch: Any) -> Any:
    return {
        "bfloat16": torch.bfloat16,
        "float16": torch.float16,
        "float32": torch.float32,
        "auto": "auto",
    }.get(name, torch.bfloat16)


register_provider("transformers", "generate", _build_transformers)
