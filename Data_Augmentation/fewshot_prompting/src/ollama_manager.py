import subprocess
import os
import signal
import time
import sys
import json
import urllib.request
import platform

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
    """
    Checks for a running Ollama service. If not found, starts a temporary one as a fallback.
    Returns a tuple: (status, process_object)
    status: "system_service", "temp_server", or None
    process_object: The subprocess.Popen object if a temp server was started, else None.
    """
    print("Checking for existing Ollama service...")
    try:
        # Check if the server is responsive
        subprocess.run("ollama list", shell=True, check=True, capture_output=True, text=True)
        print("--> Found running Ollama system service.")
        return "system_service", None
    except (subprocess.CalledProcessError, FileNotFoundError):
        # System service not found or 'ollama' command doesn't exist yet.
        # Proceed to fallback.
        pass

    print("--> No running Ollama service found. Attempting to start a temporary server...")
    print("    WARNING: This is a fallback mechanism. For best performance and stability,")
    print("    it is recommended to install and run the main Ollama application.")

    try:
        # Start the temporary server
        temp_server_process = subprocess.Popen(
            "ollama serve", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, preexec_fn=os.setsid
        )
        
        # Wait for the temp server to become responsive
        print("    Waiting for temporary server to initialize...")
        max_wait_time = 30
        wait_interval = 2
        waited_time = 0
        
        while waited_time < max_wait_time:
            time.sleep(wait_interval)
            waited_time += wait_interval
            try:
                # Check responsiveness via API, as 'ollama list' might not work immediately
                with urllib.request.urlopen("http://localhost:11434", timeout=1) as response:
                    if response.status == 200:
                        print("--> Temporary server started successfully.")
                        return "temp_server", temp_server_process
            except Exception:
                print(f"    Still waiting... ({waited_time}s / {max_wait_time}s)")

        # If loop finishes, server did not start in time
        if temp_server_process:
            os.killpg(os.getpgid(temp_server_process.pid), signal.SIGTERM) # Clean up the zombie process
        print("Error: Failed to start temporary Ollama server in time.")
        return None, None

    except Exception as e:
        print(f"Error: Failed to execute 'ollama serve': {e}")
        return None, None

def stop_ollama(status, process, model_name):
    """
    Unloads the model from memory. If it's a temporary server, it also stops the server.
    """
    if status == "system_service":
        if not model_name:
            return
        print(f"--> Requesting Ollama system service to unload model '{model_name}'...")
        # Just unload the model via API
        try:
            url = "http://localhost:11434/api/generate"
            data = {"model": model_name, "prompt": "", "keep_alive": 0}
            req = urllib.request.Request(
                url, data=json.dumps(data).encode("utf-8"),
                headers={"Content-Type": "application/json"}, method="POST"
            )
            with urllib.request.urlopen(req) as response:
                response.read()
            print(f"    Successfully sent unload request for model '{model_name}'.")
        except Exception as e:
            print(f"    Warning: Failed to send unload request to Ollama API: {e}")

    elif status == "temp_server" and process:
        print(f"--> Stopping temporary Ollama server and unloading model '{model_name}'...")
        # 1. Send unload request (best effort)
        if model_name:
            try:
                url = "http://localhost:11434/api/generate"
                data = {"model": model_name, "prompt": "", "keep_alive": 0}
                req = urllib.request.Request(
                    url, data=json.dumps(data).encode("utf-8"),
                    headers={"Content-Type": "application/json"}, method="POST"
                )
                with urllib.request.urlopen(req, timeout=5) as response:
                    response.read()
                print("    - Sent unload request to temporary server.")
            except Exception as e:
                print(f"    - Warning: Failed to send unload request to temporary server: {e}")

        # 2. Give a grace period
        print("    - Waiting 2s for graceful shutdown...")
        time.sleep(2)

        # 3. Terminate the process group
        print(f"    - Terminating temporary server process group (PGID: {process.pid}).")
        try:
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
            process.wait(timeout=5)
            print("    - Temporary server stopped.")
        except (ProcessLookupError, subprocess.TimeoutExpired):
            try:
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                print("    - Temporary server killed.")
            except ProcessLookupError:
                print("    - Process already gone.") # Already terminated
        except Exception as e:
            print(f"    - Error while stopping server: {e}")

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
