import subprocess
from utils.msa_db import db_node as node_db
import os
import traceback

def get_cuda_cores_per_sm(major):
    if major == 2:
        return "Fermi",32  # Fermi
    elif major == 3:
        return "kepler",192  # Kepler
    elif major == 5:
        return "Maxwell",128  # Maxwell
    elif major == 6:
        return "Pascal",64  # Pascal
    elif major == 7:
        return "Turing",64  # Volta/Turing
    elif major == 8:
        return "Ampere",128  # Ampere
    else:
        return "unkown",64  # Default value

def init_gpu_cuda_info():
    import cupy as cp
    num_gpus = cp.cuda.runtime.getDeviceCount()
    for device_id in range(num_gpus):
        device = cp.cuda.Device(device_id)
        properties = cp.cuda.runtime.getDeviceProperties(device_id)
        architecture, cores_per_sm = get_cuda_cores_per_sm(properties['major'])
        cuda_cores = device.attributes['MultiProcessorCount'] * cores_per_sm
        model_name = properties['name'].decode('utf-8')
        if node_db.get_gpu_cuda_info(model=model_name) is None:
            node_db.insert_gpu_cuda_info(model=model_name, cuda_core=cuda_cores, architecture=architecture)


def run_dmidecode():
    # dmidecode --type memory 명령을 실행하고 결과를 캡처
    output = subprocess.run(['dmidecode', '--type', 'memory'], capture_output=True, text=True).stdout.split('Memory Device')
    memory_list=[]
    # print(output)
    for info in output:
        # print(info)
        memory_info={}
        for line in info.split('\n'):
            try:
                if ":" in line:
                    key, value = line.split(":")
                    key = key.strip().replace(' ','_')
                    value = value.strip()
                    memory_info[key] = value
            except:
                pass
        memory_list.append(memory_info)

    return memory_list

def init_memory_info():
    try:
        memory_list = run_dmidecode()
        memory_info_list ={}
        for memory in memory_list:
            if "Part_Number" not in memory or memory['Part_Number'] == "NO DIMM":
                continue
            if memory_info_list.get(memory['Part_Number']):
                memory_info_list[memory['Part_Number']]['count'] +=1
            else:

                if memory['Size'] != "No Module Installed":
                    memory_info_list[memory['Part_Number']]={
                            'type' : memory['Type'],
                            'size' : int(memory['Size'].split(' ')[0])*1024*1024*1024,
                            'speed': memory['Speed'],
                            'manufacturer' : memory['Manufacturer'],
                            'count' : 1
                            }
        node_id = os.getenv("NODE_ID")
        for model, mem_info in memory_info_list.items():
            node_db.insert_node_ram(
                node_id=node_id,
                size=mem_info['size'],
                type=mem_info['type'],
                model=model,
                speed=mem_info['speed'],
                manufacturer=mem_info['manufacturer'],
                count=mem_info['count']
            )
    except:
        traceback.print_exc()


if __name__ == "__main__":
    try:
        init_memory_info()
    except:
        print("get Memory info fail")
    try:
        init_gpu_cuda_info()
    except:
        print("get CUDA cores info fail")




