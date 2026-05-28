from utils.msa_db import db_node as node_db
import cupy as cp
import traceback


def get_cuda_cores_per_sm(major):
    if major == 2:
        return "Fermi", 32  # Fermi
    elif major == 3:
        return "kepler", 192  # Kepler
    elif major == 5:
        return "Maxwell", 128  # Maxwell
    elif major == 6:
        return "Pascal", 64  # Pascal
    elif major == 7:
        return "Turing", 64  # Volta/Turing
    elif major == 8:
        return "Ampere", 128  # Ampere
    else:
        return "unknown", 64  # Default value


def init_gpu_cuda_info():
    try:
        num_gpus = cp.cuda.runtime.getDeviceCount()
        for device_id in range(num_gpus):
            device = cp.cuda.Device(device_id)
            properties = cp.cuda.runtime.getDeviceProperties(device_id)
            architecture, cores_per_sm = get_cuda_cores_per_sm(properties["major"])
            cuda_cores = device.attributes["MultiProcessorCount"] * cores_per_sm
            model_name = properties["name"].decode("utf-8")
            if node_db.get_gpu_cuda_info(model=model_name) is None:
                node_db.insert_gpu_cuda_info(
                    model=model_name, cuda_core=cuda_cores, architecture=architecture
                )
    except:
        traceback.print_exc()


if __name__ == "__main__":
    try:
        init_gpu_cuda_info()
    except:
        print("get CUDA cores info fail")
