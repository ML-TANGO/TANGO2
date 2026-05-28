#!/usr/bin/env python
import argparse
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base_model", required=True)
    parser.add_argument("--adapter_model", required=True)
    parser.add_argument("--output_dir", required=True)
    parser.add_argument("--trust_remote_code", action="store_true")
    args = parser.parse_args()

    tokenizer = AutoTokenizer.from_pretrained(
        args.base_model,
        trust_remote_code=args.trust_remote_code,
    )
    model = AutoModelForCausalLM.from_pretrained(
        args.base_model,
        trust_remote_code=args.trust_remote_code,
        torch_dtype="auto",
    )
    model = PeftModel.from_pretrained(model, args.adapter_model)
    model = model.merge_and_unload()
    model.save_pretrained(args.output_dir)
    tokenizer.save_pretrained(args.output_dir)

if __name__ == "__main__":
    main()