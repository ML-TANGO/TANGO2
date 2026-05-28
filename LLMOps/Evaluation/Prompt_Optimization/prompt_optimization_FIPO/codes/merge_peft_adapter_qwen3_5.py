from dataclasses import dataclass, field
from typing import Optional

from peft import PeftModel
from transformers import AutoConfig, AutoModelForCausalLM, AutoTokenizer, HfArgumentParser


@dataclass
class ScriptArguments:
    adapter_model_name: Optional[str] = field(default=None)
    base_model_name: Optional[str] = field(default=None)
    output_name: Optional[str] = field(default=None)
    trust_remote_code: bool = field(default=True)


def main():
    parser = HfArgumentParser((ScriptArguments,))
    script_args = parser.parse_args_into_dataclasses()[0]

    config = AutoConfig.from_pretrained(script_args.base_model_name, trust_remote_code=script_args.trust_remote_code)
    config.use_cache = False
    tokenizer = AutoTokenizer.from_pretrained(script_args.base_model_name, trust_remote_code=script_args.trust_remote_code, use_fast=False)
    model = AutoModelForCausalLM.from_pretrained(script_args.base_model_name, config=config, trust_remote_code=script_args.trust_remote_code)

    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token or tokenizer.unk_token
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token_id = tokenizer.convert_tokens_to_ids(tokenizer.pad_token)
    model.config.pad_token_id = tokenizer.pad_token_id

    model = PeftModel.from_pretrained(model, script_args.adapter_model_name)
    model = model.merge_and_unload()

    model.save_pretrained(script_args.output_name)
    tokenizer.save_pretrained(script_args.output_name)


if __name__ == "__main__":
    main()
