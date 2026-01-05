import yaml

def load_prompt_config(file_path):
    """Loads a prompt configuration from a YAML file."""
    with open(file_path, 'r') as f:
        return yaml.safe_load(f)

def load_prompt_components(file_path="prompts/prompt_versions.yml"):
    """
    Loads an ordered list of prompt component definitions based on the active strategy.
    Each component definition is a dictionary containing its type, instruction, and/or template.
    """
    config = load_prompt_config(file_path)

    active_strategy_name = config.get("active_strategy")
    if not active_strategy_name:
        raise ValueError(f"'active_strategy' not found in {file_path}")

    strategy_component_names = config.get("prompt_strategies", {}).get(active_strategy_name)
    if not strategy_component_names:
        raise ValueError(f"Strategy '{active_strategy_name}' not found or empty in {file_path}")

    all_prompt_components = config.get("prompt_components", {})

    loaded_components = []
    for comp_name in strategy_component_names:
        component_def = all_prompt_components.get(comp_name)
        if not component_def:
            raise ValueError(f"Component '{comp_name}' not found in 'prompt_components' section of {file_path}")

        component_def['name'] = comp_name
        loaded_components.append(component_def)

    return loaded_components
