from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "train"))

from prompt import make_training_chat_template
from util import patch_exaone_causal_mask_compat


def main() -> None:
    exaone_template = make_training_chat_template("LGAI-EXAONE/EXAONE-3.5-7.8B-Instruct")
    assert "[|assistant|]" in exaone_template
    assert "<|assistant|>" not in exaone_template
    assert "{% generation %}" in exaone_template

    generic_template = make_training_chat_template("Qwen/Qwen3-8B")
    assert "<|assistant|>" in generic_template

    import transformers.masking_utils as masking_utils

    original = masking_utils.create_causal_mask

    def fake_create_causal_mask(config, inputs_embeds, attention_mask, past_key_values, position_ids=None):
        return {
            "config": config,
            "inputs_embeds": inputs_embeds,
            "attention_mask": attention_mask,
            "past_key_values": past_key_values,
            "position_ids": position_ids,
        }

    try:
        masking_utils.create_causal_mask = fake_create_causal_mask
        patch_exaone_causal_mask_compat("LGAI-EXAONE/EXAONE-3.5-7.8B-Instruct")
        result = masking_utils.create_causal_mask(
            config="config",
            input_embeds="embeds",
            attention_mask="mask",
            cache_position="dropped",
            past_key_values="past",
            position_ids="positions",
        )
        assert result["inputs_embeds"] == "embeds"
        assert result["position_ids"] == "positions"
        assert getattr(masking_utils.create_causal_mask, "_logickor_exaone_compat", False)
    finally:
        masking_utils.create_causal_mask = original


if __name__ == "__main__":
    main()
