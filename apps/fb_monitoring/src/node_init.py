import subprocess
from utils.msa_db import db_node as node_db
import os
import traceback
import re


def parse_nvidia_smi_uuids():
    try:
        # Run the `nvidia-smi -L` command and capture its output
        result = subprocess.run(
            ["nvidia-smi", "-L"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        # Check for errors
        if result.returncode != 0:
            raise RuntimeError(f"Error running nvidia-smi: {result.stderr.strip()}")

        # Parse UUIDs using regex
        uuids = re.findall(r"UUID: ([0-9a-zA-Z\-]+)", result.stdout)

        return uuids

    except Exception as e:
        print(f"An error occurred while getting nvidia uuids: {e}")
        return []


def call_init_gpu():
    uuids = parse_nvidia_smi_uuids()
    original_cuda_visible_devices = os.environ.get("CUDA_VISIBLE_DEVICES")
    file_path = os.path.abspath(__file__)
    target_path = os.path.join(os.path.dirname(file_path), "node_init_gpu.py")
    for uuid in uuids:
        os.environ["CUDA_VISIBLE_DEVICES"] = uuid
        subprocess.call(["python3", target_path])
    if original_cuda_visible_devices:
        os.environ["CUDA_VISIBLE_DEVICES"] = original_cuda_visible_devices
    else:
        del os.environ["CUDA_VISIBLE_DEVICES"]
    return


def run_dmidecode():
    # dmidecode --type memory 명령을 실행하고 결과를 캡처
    output = subprocess.run(
        ["dmidecode", "--type", "memory"], capture_output=True, text=True
    ).stdout.split("Memory Device")
    memory_list = []
    # print(output)
    for info in output:
        # print(info)
        memory_info = {}
        for line in info.split("\n"):
            try:
                if ":" in line:
                    key, value = line.split(":")
                    key = key.strip().replace(" ", "_")
                    value = value.strip()
                    memory_info[key] = value
            except:
                pass
        memory_list.append(memory_info)

    return memory_list


def init_memory_info():
    try:
        memory_list = run_dmidecode()
        memory_info_list = {}
        for memory in memory_list:
            if "Part_Number" not in memory or memory["Part_Number"] == "NO DIMM":
                continue
            if memory_info_list.get(memory["Part_Number"]):
                memory_info_list[memory["Part_Number"]]["count"] += 1
            else:

                if memory["Size"] != "No Module Installed":
                    memory_info_list[memory["Part_Number"]] = {
                        "type": memory["Type"],
                        "size": int(memory["Size"].split(" ")[0]) * 1024 * 1024 * 1024,
                        "speed": memory["Speed"],
                        "manufacturer": memory["Manufacturer"],
                        "count": 1,
                    }
        node_id = os.getenv("NODE_ID")
        for model, mem_info in memory_info_list.items():
            node_db.insert_node_ram(
                node_id=node_id,
                size=mem_info["size"],
                type=mem_info["type"],
                model=model,
                speed=mem_info["speed"],
                manufacturer=mem_info["manufacturer"],
                count=mem_info["count"],
            )
    except:
        traceback.print_exc()


if __name__ == "__main__":
    try:
        init_memory_info()
    except:
        print("get Memory info fail")
    try:
        call_init_gpu()
    except:
        print("get CUDA cores info fail")
