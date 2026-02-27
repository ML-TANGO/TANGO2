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

def prepare_model(model_name):
    """
    Ensures a model is ready for use, with a fallback mechanism.
    It tries the specified model_name first, then a default model.
    Returns the name of the model that is ready, or None if all attempts fail.
    """
    candidates = []
    if model_name and model_name.strip():
        candidates.append(model_name)

    default_model = "gemma3:4b"
    if default_model not in candidates:
        candidates.append(default_model)

    print(f"--> Model preparation priority: {', '.join(f'"{c}"' for c in candidates)}")

    try:
        # Get the list of models once to avoid multiple shell calls
        result = subprocess.run("ollama list", shell=True, check=True, capture_output=True, text=True)
        local_models = result.stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("Error: 'ollama' command not found or failed to run. Please ensure Ollama is installed and running.")
        return None

    for candidate in candidates:
        print(f"--- Checking for model: '{candidate}' ---")
        # Check if the model (and tag) is in the list output
        if f"{candidate}" in local_models:
            print(f"--> Model '{candidate}' found locally.")
            return candidate
        else:
            print(f"Model '{candidate}' not found locally. Attempting to pull...")
            try:
                # Use Popen for real-time output, but Run is simpler if we wait anyway
                pull_command = f"ollama pull {candidate}"
                print(f"    Running command: {pull_command}")
                # Using check=True will raise CalledProcessError on failure (e.g., model not found)
                subprocess.run(pull_command, shell=True, check=True, text=True, capture_output=True)
                print(f"--> Model '{candidate}' pulled successfully.")
                return candidate
            except subprocess.CalledProcessError as e:
                print(f"    - Failed to pull '{candidate}'. Reason:")
                # Show a snippet of stderr, which usually has the "not found" message
                stderr_snippet = (e.stderr or e.stdout or "No output from command.").strip().split('\n')[-1]
                print(f"    - {stderr_snippet}")
                print(f"    - Trying next candidate...")

    print("\nError: All model candidates failed. Could not prepare a model for Ollama.")
    return None
