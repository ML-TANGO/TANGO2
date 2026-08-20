from typing import Any


def make_training_chat_template(model_name: str | None = None) -> str:
    # TRL assistant-only loss expects {% generation %} markers in assistant spans.
    if model_name and "EXAONE" in model_name.upper():
        return (
            "{% for message in messages %}"
            "{% if loop.first and message['role'] != 'system' %}"
            "{{ '[|system|][|endofturn|]\n' }}"
            "{% endif %}"
            "{% if message['role'] == 'system' %}"
            "{{ '[|system|]' + message['content'] }}{{ eos_token }}\n"
            "{% elif message['role'] == 'user' %}"
            "{{ '[|user|]' + message['content'] }}\n"
            "{% elif message['role'] == 'assistant' %}"
            "{{ '[|assistant|]' }}{% generation %}{{ message['content'] }}{% endgeneration %}{{ eos_token }}\n"
            "{% endif %}"
            "{% endfor %}"
            "{% if add_generation_prompt %}{{ '[|assistant|]' }}{% endif %}"
        )
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


def ensure_training_chat_template(tokenizer: Any, model_name: str | None = None) -> None:
    # Replace non-training-compatible templates with a stable training template.
    tokenizer.chat_template = make_training_chat_template(model_name)
