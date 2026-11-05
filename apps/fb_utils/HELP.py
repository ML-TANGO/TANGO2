from utils.TYPE import *

PORT_LIST="""Port List [{"name":"SSH", "target_port":22, "protocol":"TCP", "description":"", "node_port": null | 33333, "status": 0 | 1, "service_type": NodePort, "id": 100 | None(newCase)},...]
    ex) [
            {"name":"SSH", "target_port":22, "protocol":"TCP", "description":"rer", "node_port": 33333, "status": 1, "service_type": "NodePort", "system_definition":1 },
            {"name":"myport", "target_port":122, "protocol":"TCP", "description":"my port", "node_port": 32222, "status": 1, "service_type": "NodePort", "system_definition": 0 }
        ]
"""
GPU_MODEL_EX = """{"NVIDIA-GeForce-GTX-1080-Ti":["jf-node-03"], "TEST-GPU":["node1","node2"]}"""
GPU_MODEL="""GPU MODEL DEFINE
    ex) @GPU_MODEL_EX
""".replace("@GPU_MODEL_EX", GPU_MODEL_EX)

NODE_MODE="""Node Mode ((0) Single, (1) Multiple)"""

# NODE_NAME="""
#     gpu_model_status/cpu_model_status 에서 선택 한 아이템들의 node_name을 cpu/ram 제한 값과 함께 담음
#     ex) {{"jf-node-02": {{ "{CPU_CORES_PER_GPU}": 1, "{MEMORY_PER_GPU}" : 1, "{CPU_CORES_PER_POD}" : 1, "{MEMORY_PER_POD}" : 1}} }}
# """.format(
#     CPU_CORES_PER_GPU=NODE_CPU_LIMIT_PER_GPU_DB_KEY,
#     MEMORY_PER_GPU=NODE_MEMORY_LIMIT_PER_GPU_DB_KEY,
#     CPU_CORES_PER_POD=NODE_CPU_LIMIT_PER_POD_DB_KEY,
#     MEMORY_PER_POD=NODE_MEMORY_LIMIT_PER_POD_DB_KEY
# )


JOBS="""JOBS
    ex) {
        "training_id": 32,
        "job_name": "qweqwe",
        "dataset_id": "/",
        "docker_image_id": 1,
        "gpu_acceleration": 0 | 1,
        "rdma": 0 | 1,
        "unified_memory": 0 | 1,
        "run_code": "/examples/hps_fast_test.py",
        "parameter": "--test 1 --test 2",
        "gpu_model": @GPU_MODEL_EX ,
        "gpu_count": 0 ~ n
    }
""".replace("@GPU_MODEL_EX", GPU_MODEL_EX)

HPS_OPTION="""HPS OPTION 
{
    gpu_acceleration : 0, (True | False)
    unified_memory: 0,
    rdma: 0,
    gpu_count: (int) (optional)
    gpu_model: (dict) @GPU_MODEL_EX (optional)
    training_params (str || dict): str --batch_size 10 --lr 5 || dict {'batch_size': 10, 'lr': 5} (optional)
    search_params (str): {'x': (1,10) , 'y': (12,15)}  {param : (min,max)} (required)
    search_count (int): 1 ~ n (int) number of searches (required)
    search_interval (float): 0.0 ~ float (float) Grid search interval (optional)
    method (int || str):  Search method 0 = bayesian , 1 = random , 2 = grid , 3 = user_custom (not yet)  (required)
    load_file_name (str): load data file name (ex logs.json). Load saved data (optional)
    save_file_name (str): save data file name. (optional)
    save_file_reset (bool (0,1)): if already exist save data, then remove and create new one (optional)
    init_points (int): Bayesian search Base point. (1~n) (optional)
    int_params : (str) ex) batch_size,epoch
}
""".replace("@GPU_MODEL_EX", GPU_MODEL_EX)