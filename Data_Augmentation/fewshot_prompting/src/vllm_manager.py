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

def start_vllm(vllm_url, model_name, model_path=None):
    """
    Checks for a running vLLM server. If not found, starts a temporary one.
    This version uses background threads to drain stdout/stderr, preventing hangs
    while keeping recent logs in memory for debugging.
    """
    if check_vllm_ready(vllm_url):
        return "existing_service", None

    print("--> No running vLLM service found. Attempting to start a temporary server...")
    
    try:
        parsed_url = urlparse(vllm_url)
        host = parsed_url.hostname
        port = parsed_url.port
        
        model_to_load = model_path if model_path and model_path.strip() else model_name
        if model_path and model_path.strip():
            print(f"    Using local model path: {model_to_load}")
        else:
            print(f"    Using model name from config: {model_to_load}")

        command = [
            "python", "-m", "vllm.entrypoints.openai.api_server",
            "--host", host,
            "--port", str(port),
            "--model", model_to_load
        ]
        
        print(f"    Running command: {' '.join(command)}")

        # Start the temporary server
        temp_server_process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            preexec_fn=os.setsid
        )
        
        # Create in-memory buffers for recent logs
        stdout_deque = deque(maxlen=100)
        stderr_deque = deque(maxlen=100)
        
        # Attach deques to process object for access in error handling
        temp_server_process.stdout_deque = stdout_deque
        temp_server_process.stderr_deque = stderr_deque

        # Start background threads to drain the pipes
        stdout_thread = threading.Thread(target=_drain_pipe_to_deque, args=(temp_server_process.stdout, stdout_deque), daemon=True)
        stderr_thread = threading.Thread(target=_drain_pipe_to_deque, args=(temp_server_process.stderr, stderr_deque), daemon=True)
        stdout_thread.start()
        stderr_thread.start()

        # Wait for the temp server to become responsive
        print("    Waiting for temporary vLLM server to initialize...")
        max_wait_time = 60
        wait_interval = 5
        waited_time = 0
        
        while waited_time < max_wait_time:
            time.sleep(wait_interval)
            waited_time += wait_interval
            if check_vllm_ready(vllm_url):
                print("--> Temporary vLLM server started successfully.")
                return "temp_server", temp_server_process
            else:
                print(f"    Still waiting... ({waited_time}s / {max_wait_time}s)")

        # If loop finishes, server did not start in time
        if temp_server_process:
            print("Error: Failed to start temporary vLLM server in time. Terminating process.")
            os.killpg(os.getpgid(temp_server_process.pid), signal.SIGTERM)
            
            # Give threads a moment to catch final output
            time.sleep(0.5) 
            
            print("--- vLLM Server STDOUT (last 100 lines) ---")
            for line in list(stdout_deque):
                print(line, end='')
            print("--- vLLM Server STDERR (last 100 lines) ---")
            for line in list(stderr_deque):
                print(line, end='')
                
        return None, None

    except FileNotFoundError:
        print("Error: 'python' command not found. Make sure Python and vLLM are installed correctly.")
        return None, None
    except Exception as e:
        print(f"Error: Failed to execute vLLM server command: {e}")
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


def check_vllm_ready(vllm_url):
    """
    Checks if the vLLM server is responsive.
    vllm_url: The base URL of the vLLM server (e.g., http://localhost:8000/v1)
    """
    print(f"Checking if vLLM server is ready at {vllm_url}...")
    try:
        # Check /models endpoint as a health check
        # The health endpoint is at the root, not /v1
        base_url = vllm_url.replace('/v1', '')
        health_url = f"{base_url}/health"
        
        with urllib.request.urlopen(health_url, timeout=3) as response:
            if response.status == 200:
                print("--> vLLM server is ready.")
                return True
    except Exception as e:
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
