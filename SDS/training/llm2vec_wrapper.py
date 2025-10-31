from llm2vec import LLM2Vec
from peft import PeftModel
from transformers import (
    AutoConfig,
    PretrainedConfig,
    AutoTokenizer,

)
import logging
import json
import os
logger = logging.getLogger(__name__)
class LLM2VecWrapper(LLM2Vec):
    def __init__(self, *args, **kwargs):
        super(LLM2VecWrapper, self).__init__(*args, **kwargs)

    def prepare_for_tokenization(self, text):
        text = (
            "<|start_header_id|>user<|end_header_id|>\n\n"
            + text.strip()
            + "<|eot_id|>"
        )
        return text

    @classmethod
    def from_pretrained(
        cls,
        base_model_name_or_path,
        peft_model_name_or_path=None,
        merge_peft=False,
        enable_bidirectional=True,
        extra_model_name_or_path=None,
        **kwargs,
    ):
        # pop out encoder args
        keys = ["pooling_mode", "max_length", "doc_max_length", "skip_instruction"]
        encoder_args = {
            key: kwargs.pop(key, None) for key in keys if kwargs.get(key) is not None
        }

        tokenizer = AutoTokenizer.from_pretrained(base_model_name_or_path)
        tokenizer.pad_token = tokenizer.eos_token
        tokenizer.padding_side = "left"

        config = AutoConfig.from_pretrained(base_model_name_or_path)
        config_class_name = config.__class__.__name__

        model_class = cls._get_model_class(
            config_class_name, enable_bidirectional=enable_bidirectional
        )
        model = model_class.from_pretrained(base_model_name_or_path, **kwargs)

        if os.path.isdir(base_model_name_or_path) and os.path.exists(
            f"{base_model_name_or_path}/config.json"
        ):
            with open(f"{base_model_name_or_path}/config.json", "r") as fIn:
                config_dict = json.load(fIn)
            config = PretrainedConfig.from_dict(config_dict)
            model.config._name_or_path = config._name_or_path

        # For special case where config.json and adapter weights are in the same directory
        if hasattr(model, "peft_config"):
            model = PeftModel.from_pretrained(
                model,
                base_model_name_or_path,
            )
            model = model.merge_and_unload()

        if peft_model_name_or_path is not None:
            model = PeftModel.from_pretrained(
                model,
                peft_model_name_or_path,
            )
            if merge_peft:
                model = model.merge_and_unload()
        if extra_model_name_or_path is not None:
            logger.info(f"Loading extra model from {extra_model_name_or_path}")
            if not merge_peft:
                model = model.merge_and_unload()
            if isinstance(extra_model_name_or_path, str):
                model = PeftModel.from_pretrained(
                    model,
                    extra_model_name_or_path,
                )
                model = model.merge_and_unload()
            elif isinstance(extra_model_name_or_path, list):
                for extra_model in extra_model_name_or_path:
                    model = PeftModel.from_pretrained(
                        model,
                        extra_model,
                    )
                    peft_model_name_or_path = extra_model
                    model = model.merge_and_unload()
            else:
                raise ValueError(
                    f"extra_model_name_or_path should be a string or a list of strings."
                )
        config = {}
        config_addr = (
            peft_model_name_or_path
            if peft_model_name_or_path is not None
            else base_model_name_or_path
        )
        if os.path.exists(f"{config_addr}/llm2vec_config.json"):
            with open(f"{config_addr}/llm2vec_config.json", "r") as fIn:
                llm2vec_config = json.load(fIn)
            config.update(llm2vec_config)

        for key, value in encoder_args.items():
            config[key] = value

        return cls(model=model, tokenizer=tokenizer, **config)