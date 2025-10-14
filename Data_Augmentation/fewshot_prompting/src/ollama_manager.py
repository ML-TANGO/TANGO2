import subprocess
import os
import signal
import time
import sys
import json
import urllib.request

def install_ollama():
    """Installs Ollama on macOS without user confirmation."""
    print("Ollama is not found. Automatically proceeding with installation...")

    install_command = "curl -fsSL https://ollama.com/install.sh | sh"
    print(f"Running installation command: {install_command}")
    try:
        process = subprocess.run(install_command, shell=True, check=True, text=True, capture_output=True)
        print("--- Installation Output ---")
        print(process.stdout)
        if process.stderr:
            print("--- Installation Errors ---")
            print(process.stderr)
        print("---------------------------")
        print("Ollama installed successfully.")
        print("Please restart the script for the changes to take effect.")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Ollama installation failed with exit code {e.returncode}.")
        print(f"Stdout: {e.stdout}")
        print(f"Stderr: {e.stderr}")
        return False
    except Exception as e:
        print(f"An unexpected error occurred during installation: {e}")
        return False

def start_ollama():
    """Checks if the Ollama system service is running and responsive."""
    print("Checking if Ollama system service is running and responsive...")
    try:
        # Check if the command exists first
        subprocess.run("command -v ollama", shell=True, check=True, capture_output=True)
    except subprocess.CalledProcessError:
        print("Error: 'ollama' command not found. Please ensure Ollama is installed correctly.")
        return None

    try:
        # Check if the server is responsive
        subprocess.run("ollama list", shell=True, check=True, capture_output=True)
        print("Ollama system service is running and responsive.")
        return "system_service" # Return a new indicator string
    except subprocess.CalledProcessError:
        print("\n---")
        print("Error: Ollama system service is not running or not responsive.")
        print("Please ensure the service is active by running: sudo systemctl start ollama")
        print("---\n")
        return None

def pull_model_if_needed(model_name):
    """Checks if the model exists locally and pulls it if it doesn't."""
    print(f"Checking if model '{model_name}' exists locally...")
    try:
        result = subprocess.run("ollama list", shell=True, check=True, capture_output=True, text=True)
        if model_name in result.stdout:
            print(f"Model '{model_name}' already exists.")
            return True
        else:
            print(f"Model '{model_name}' not found. Pulling from Ollama...")
            # This will use the system service and download to the system directory
            pull_command = f"ollama pull {model_name}"
            print(f"Running command: {pull_command}")
            pull_process = subprocess.run(pull_command, shell=True, check=True)
            print(f"Model '{model_name}' pulled successfully.")
            return True
    except subprocess.CalledProcessError as e:
        print(f"Error during model check/pull: {e.stderr}")
        return False
    except FileNotFoundError:
        print("Error: 'ollama' command not found.")
        return False

def stop_ollama(model_name):
    """
    Unloads the specified model from GPU memory using the Ollama API.
    """
    if not model_name:
        print("No model name provided to unload.")
        return
    
    print(f"Attempting to unload model '{model_name}' from memory via API...")
    try:
        url = "http://localhost:11434/api/generate"
        data = {
            "model": model_name,
            "prompt": "", # Prompt can be empty
            "keep_alive": 0,
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(data).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req) as response:
            if 200 <= response.status < 300:
                # The API streams a response, we can just read it to ensure completion
                response.read()
                print(f"Successfully sent request to unload model '{model_name}'.")
            else:
                print(f"API request to unload model failed with status: {response.status}")

    except urllib.error.URLError as e:
        print(f"Failed to connect to Ollama API to unload model. Is the server running? Error: {e.reason}")
    except Exception as e:
        print(f"An unexpected error occurred while trying to unload the model: {e}")
