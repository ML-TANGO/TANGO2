from dataclasses import dataclass, field
from typing import Optional
import torch
import os
from peft import PeftModel
from transformers import LlamaForCausalLM, LlamaTokenizer, HfArgumentParser, LlamaConfig

@dataclass
class ScriptArguments:
    adapter_model_name: Optional[str] = field(default=None, metadata={"help": "the model name"})
    base_model_name: Optional[str] = field(default=None, metadata={"help": "the model name"})
    output_name: Optional[str] = field(default=None, metadata={"help": "the model name"})

def translate_state_dict_key(k):
    return k.replace("base_model.model.base_model.model.model.layers", "base_model.model.model.layers")

def main():
    parser = HfArgumentParser((ScriptArguments))
    script_args = parser.parse_args_into_dataclasses()[0]

    # load config and tokenziers
    config = LlamaConfig.from_pretrained(script_args.base_model_name)
    config.use_cache = False
    # use truncation_side='left' to preserve linking between end of prompt and target labels
    tokenizer = LlamaTokenizer.from_pretrained(script_args.base_model_name, truncation_side='left')
    # initialize modules
    model = LlamaForCausalLM.from_pretrained(script_args.base_model_name, config=config)

     # add pad token in tokenizer if needed
    if tokenizer.pad_token is None:
        tokenizer.add_special_tokens({"pad_token":"<pad>"})
        tokenizer.pad_token_id = 0

    embedding_size = model.get_input_embeddings().weight.shape[0]
    if len(tokenizer) > embedding_size:
        model.resize_token_embeddings(len(tokenizer))

    print("-" * 20 + "Weight before merge" + "-" * 20)
    old_weight = model.get_output_embeddings().weight.clone()
    print(old_weight)

    # check Lora weights before merge
    print("-" * 20 + "Check Lora Weights before merge" + "-" * 20)
    lora_weights = torch.load(os.path.join(script_args.adapter_model_name, "adapter_model.bin"))
    for k, v in lora_weights.items():
        if "lora_B" in k:
            print(k)
            print(v)
            break
    new_lora_dict = {}
    for k, v in lora_weights.items():
        new_lora_dict[translate_state_dict_key(k)] = v
    torch.save(new_lora_dict, os.path.join(script_args.adapter_model_name, "adapter_model.bin"))

    # Load the Lora model
    model = PeftModel.from_pretrained(model, script_args.adapter_model_name)
    model.eval()

    # check Lora weights during merge
    print("-" * 20 + "Check Lora Weights during merge" + "-" * 20)
    for k, v in model.state_dict().items():
        if "lora_B" in k:
            print(k)
            print(v)
            break

    # merge lora weight and base model
    model = model.merge_and_unload()

    print("-" * 20 + "Weight after merge" + "-" * 20)
    new_weight = model.get_output_embeddings().weight.clone()
    print(new_weight)

    print("-" * 20 + "Weight difference" + "-" * 20)
    print((new_weight - old_weight).sum())

    model.half().save_pretrained(f"{script_args.output_name}")
    tokenizer.save_pretrained(f"{script_args.output_name}")

    # remove possible lora modules
    # os.system("rm -f {} {} {}".format(
    #     os.path.join(script_args.output_name, "adapter_model.bin"),
    #     os.path.join(script_args.output_name, "adapter_config.json"),
    #     os.path.join(script_args.output_name, "README.md")
    # ))

if __name__ == "__main__":
    main()
