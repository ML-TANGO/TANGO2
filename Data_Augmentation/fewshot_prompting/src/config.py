import configparser
import os

def read_config():
    """Reads the config.ini file and returns the configuration."""
    config = configparser.ConfigParser()
    if not os.path.exists('config.ini'):
        raise FileNotFoundError("config.ini not found. Please create it.")
    config.read('config.ini')
    return config

def get_few_shot_files(config):
    """
    Reads few-shot file paths from the config file.
    Returns a tuple of (input_files, output_files).
    """
    input_files, output_files = [], []
    if config.has_section('FEW_SHOT_DATA'):
        input_str = config.get('FEW_SHOT_DATA', 'INPUT_FILES', fallback='')
        output_str = config.get('FEW_SHOT_DATA', 'OUTPUT_FILES', fallback='')

        if input_str:
            input_files = [path.strip() for path in input_str.split(',')]
        if output_str:
            output_files = [path.strip() for path in output_str.split(',')]

    return input_files, output_files
