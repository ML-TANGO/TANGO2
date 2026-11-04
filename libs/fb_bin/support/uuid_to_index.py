import os
import re
import subprocess

def get_gpu_index_by_uuid(target_uuids):
    try:
        # Run nvidia-smi to get GPU information
        result = subprocess.run(['nvidia-smi', '-L'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        if result.returncode != 0:
            print("Failed to run nvidia-smi. Make sure NVIDIA drivers are installed and nvidia-smi is available.")
            return None
        
        # Parse the output to get GPU index and UUID
        gpus = result.stdout.strip().split('\n')
        uuid_pattern = re.compile(r'UUID: GPU-([a-f0-9\-]+)', re.IGNORECASE)
        gpu_indices = []
        
        for uuid in target_uuids:
            uuid = uuid.strip()  # Remove any extra whitespace
            found = False
            for gpu in gpus:
                match = uuid_pattern.search(gpu)
                if match:
                    gpu_uuid = f"GPU-{match.group(1).strip()}"
                    index = int(gpu.split()[1][:-1])  # Extract the GPU index from the output
                    if uuid.lower() == gpu_uuid.lower():
                        gpu_indices.append(index)
                        found = True
                        break
            if not found:
                print(f"Unable to find GPU index for the given UUID: {uuid}")
        
        return gpu_indices if gpu_indices else None
    except Exception as e:
        print(f"An error occurred: {e}")
        return None

# Example usage
if 'CUDA_VISIBLE_DEVICES' in os.environ:
    target_uuids = os.environ['CUDA_VISIBLE_DEVICES'].split(',')
elif 'NVIDIA_VISIBLE_DEVICES' in os.environ:
    target_uuids = os.environ['NVIDIA_VISIBLE_DEVICES'].split(',')
else:
    print("No existing GPU UUIDs found in CUDA_VISIBLE_DEVICES or NVIDIA_VISIBLE_DEVICES.")
    target_uuids = []

gpu_indices = get_gpu_index_by_uuid(target_uuids)

if gpu_indices is not None:
    # Update environment variable
    cuda_visible_devices = ','.join(map(str, gpu_indices))
    print(f"export CUDA_VISIBLE_DEVICES={cuda_visible_devices}")
else:
    print("No valid GPU indices found. CUDA_VISIBLE_DEVICES not updated.")
