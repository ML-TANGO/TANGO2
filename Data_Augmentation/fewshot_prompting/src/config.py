import configparser
import os

def read_config():
    """Reads the config.ini file and returns the configuration."""
    config = configparser.ConfigParser()
    if not os.path.exists('config.ini'):
        raise FileNotFoundError("config.ini not found. Please create it.")
    config.read('config.ini')
    return config
