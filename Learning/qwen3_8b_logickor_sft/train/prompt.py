from typing import Any


def make_training_chat_template() -> str:
    # TRL assistant-only loss expects {% generation %} markers in assistant spans.
    return (
        "{% for message in messages %}"
        "{% if message['role'] == 'system' %}"
        "<|system|>\n{{ message['content'] }}{{ eos_token }}\n"
        "{% elif message['role'] == 'user' %}"
        "<|user|>\n{{ message['content'] }}{{ eos_token }}\n"
        "{% elif message['role'] == 'assistant' %}"
        "<|assistant|>\n{% generation %}{{ message['content'] }}{% endgeneration %}{{ eos_token }}\n"
        "{% endif %}"
        "{% endfor %}"
        "{% if add_generation_prompt %}<|assistant|>\n{% endif %}"
    )


def ensure_training_chat_template(tokenizer: Any) -> None:
    # Replace non-training-compatible templates with a stable training template.
    tokenizer.chat_template = make_training_chat_template()
