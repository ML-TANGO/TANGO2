import urllib.request
import json
import subprocess
import os
import signal
import time
import threading
from collections import deque
from urllib.parse import urlparse

# This function will run in a background thread to consume pipe output
def _drain_pipe_to_deque(pipe, deque_buffer):
    """Reads from a pipe and appends lines to a deque."""
    try:
        with pipe:
            for line in iter(pipe.readline, ''):
                deque_buffer.append(line)
    except Exception:
        # Pipe was closed or another error occurred
        pass

def _attempt_start_server(vllm_url, model_to_load, host, port):
    """Helper function to attempt starting the vLLM server with a specific model."""
    print(f"--> Attempting to start vLLM with model: '{model_to_load}'...")

    try:
        command = [
            "python", "-m", "vllm.entrypoints.openai.api_server",
            "--host", host,
            "--port", str(port),
            "--model", model_to_load
        ]

        print(f"    Running command: {' '.join(command)}")

        temp_server_process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            preexec_fn=os.setsid
        )

        stdout_deque = deque(maxlen=100)
        stderr_deque = deque(maxlen=100)

        temp_server_process.stdout_deque = stdout_deque
        temp_server_process.stderr_deque = stderr_deque

        stdout_thread = threading.Thread(target=_drain_pipe_to_deque, args=(temp_server_process.stdout, stdout_deque), daemon=True)
        stderr_thread = threading.Thread(target=_drain_pipe_to_deque, args=(temp_server_process.stderr, stderr_deque), daemon=True)
        stdout_thread.start()
        stderr_thread.start()

        print("    Waiting for temporary vLLM server to initialize...")
        max_wait_time = 180 # Increased timeout for model downloads
        wait_interval = 5
        waited_time = 0

        while waited_time < max_wait_time:
            time.sleep(wait_interval)
            waited_time += wait_interval
            # Use silent=True to avoid flooding the console during checks
            if check_vllm_ready(vllm_url, silent=True):
                print(f"--> Temporary vLLM server started successfully with model '{model_to_load}'.")
                return temp_server_process
            #else:
            #    print(f"    Still waiting... ({waited_time}s / {max_wait_time}s)")

        # Server did not start in time, now we print the logs.
        print(f"\nError: Failed to start server with model '{model_to_load}' in the allotted time ({max_wait_time}s).")

        # Ensure the process is terminated before printing logs
        try:
            os.killpg(os.getpgid(temp_server_process.pid), signal.SIGTERM)
            time.sleep(0.5)
        except ProcessLookupError:
            pass # Process already terminated

        print(f"--- vLLM Server STDOUT for '{model_to_load}' (last 100 lines) ---")
        for line in list(stdout_deque):
            print(line, end='')
        print(f"--- vLLM Server STDERR for '{model_to_load}' (last 100 lines) ---")
        for line in list(stderr_deque):
            print(line, end='')

        return None

    except Exception as e:
        print(f"Error: Exception while trying to start vLLM with model '{model_to_load}': {e}")
        return None


def start_vllm(vllm_url, model_name, model_path=None):
    """
    Checks for a running vLLM server. If not found, starts a temporary one
    with a fallback mechanism for loading models.
    """
    # Check with silent=False for the initial check to inform the user.
    if check_vllm_ready(vllm_url, silent=False):
        return "existing_service", None

    print("--> No running vLLM service found. Attempting to start a temporary server with fallback...")

    # 1. Define model candidates in order of priority
    candidates = []
    # Priority 1: Local path from config
    if model_path and model_path.strip():
        if os.path.isdir(model_path):
            candidates.append(model_path)
            print(f"    - Priority 1: Found local path '{model_path}'.")
        else:
            print(f"    - Warning: Provided model_path '{model_path}' is not a valid directory. Skipping.")

    # Priority 2: Model name from config
    if model_name and model_name.strip():
        if model_name not in candidates:
            candidates.append(model_name)

    # Priority 3: Default fallback model
    default_model = "google/gemma-3-4b-it"
    if default_model not in candidates:
        candidates.append(default_model)

    # print(f"--> Model loading priority: {', '.join(f'"{c}"' for c in candidates)}")

    try:
        parsed_url = urlparse(vllm_url)
        host = parsed_url.hostname
        port = parsed_url.port

        # 2. Loop through candidates and attempt to start the server
        for candidate in candidates:
            process = _attempt_start_server(vllm_url, candidate, host, port)
            if process:
                # Success!
                return "temp_server", process
            else:
                # Failure, try next candidate
                print(f"    - Failed to start server with '{candidate}'. Trying next option...\n")

        # 3. If all candidates fail
        print("Error: All model candidates failed. Could not start vLLM server.")
        return None, None

    except Exception as e:
        print(f"Error: A critical error occurred in start_vllm: {e}")
        return None, None


def stop_vllm(status, process):
    """
    Stops the temporary vLLM server if it was started by this script.
    """
    if status == "temp_server" and process:
        print(f"--> Stopping temporary vLLM server (PGID: {process.pid})...")
        try:
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
            process.wait(timeout=10)
            print("    - Temporary server stopped.")
        except (ProcessLookupError, subprocess.TimeoutExpired):
            try:
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                print("    - Temporary server killed.")
            except ProcessLookupError:
                print("    - Process already gone.")
        except Exception as e:
            print(f"    - Error while stopping server: {e}")


def check_vllm_ready(vllm_url, silent=False):
    """
    Checks if the vLLM server is responsive.
    vllm_url: The base URL of the vLLM server (e.g., http://localhost:8000/v1)
    silent: If True, suppresses output on connection errors.
    """
    if not silent:
        print(f"Checking if vLLM server is ready at {vllm_url}...")
    try:
        # Check /models endpoint as a health check
        # The health endpoint is at the root, not /v1
        base_url = vllm_url.replace('/v1', '')
        health_url = f"{base_url}/health"

        with urllib.request.urlopen(health_url, timeout=3) as response:
            if response.status == 200:
                if not silent:
                    print("--> vLLM server is ready.")
                return True
    except Exception as e:
        if not silent:
            print(f"--> vLLM server check failed: {e}")

    return False

def get_vllm_model(vllm_url):
    """
    Retrieves the first available model name from the vLLM server.
    """
    try:
        models_url = f"{vllm_url}/models"
        with urllib.request.urlopen(models_url, timeout=5) as response:
            data = json.loads(response.read().decode())
            if data['data']:
                return data['data'][0]['id']
    except Exception:
        pass
    return None
