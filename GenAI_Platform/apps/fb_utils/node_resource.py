import utils.kube as kube
import utils.kube_parser as kube_parser
import utils.common as common
# import utils.db as db

import os
import sys
sys.path.insert(0, os.path.abspath('..'))
from utils.TYPE import *


# 단일 노드에서도 MPI 설정은 이뤄짐
# mpirun --allow-run-as-root -np 2 -H 192.168.1.16:2         -bind-to none -map-by slot         -x MASTER_ADDR=$MASTER_ADDR         -x MASTER_PORT=$MASTER_PORT             -x MPI_MODE=default         -x NCCL_DEBUG=INFO         -x NCCL_IB_DISABLE=1         -x NCCL_IB_CUDA_SUPPORT=0         -x NCCL_SOCKET_IFNAME=lo         -x NCCL_P2P_DISABLE=1         -x NCCL_SHM_DISABLE=1         -x LD_LIBRARY_PATH -x PATH         -mca pml ob1 -mca btl ^openib         -mca plm_rsh_args '-p 29000'         -mca btl_tcp_if_exclude vethwepl7b2ed87,vethweplfb266cd,vethwepl0972f5c,docker0,vetha55f704,vxlan-6784,veth29ed38b,vethwepl894adef,vethwepl1061dd4,vethwe-bridge,datapath,enp2s0f0,vethwepl1d82420,vethwepl1d5c542,vethwepl2380ef5,weave,vethwepl7e59ed2,vethwe-datapath,veth87260bd,vethwepl573c591,enp2s0f1             python -u /examples/pytorch_synthetic_benchmark.py           > /job_logs/952.jflog 2>> /job_logs/952.jflog
SINGLE_NODE_NETWORK_GROUP_ID = -1
SINGLE_NODE_NETWORK_GROUP_NAME = "Local"
SINGLE_NODE_NETWORK_GROUP_INTERFACE = "lo"

# TODO IB 남아 있는가 확인하는 로직 필요
#   - JOB / HPS 에서는 네트워크 자원이 남아 있지 않으면 다른 network group을 쓰도록 해야함 -
#   - 다른 Tool / Deployment 에서는 IB 자원을 할당하지 않도록 해야함
#   - 남아있는 자원 정보를 어디에 저장할것인가 ?
#       1. NetworkGroupInfo
#       2. NodeNetworkInfo
#       3. 별도 생성

class NodeGPUInfo():
    def __init__(self, gpu_model, total_gpu_count, used_gpu_count, gpu_mode, node_label):
        """
            Args :
                node (object) : k8s를 통해 가져온 node object
        """
        self._gpu_model = gpu_model
        self._total_gpu_count = total_gpu_count
        self._used_gpu_count = used_gpu_count
        self._avaliable_gpu_count = total_gpu_count - used_gpu_count
        self._gpu_mode = gpu_mode # MIG / General
        self._node_label = None # node_label

    @property
    def gpu_model(self):
        return self._gpu_model

    @property
    def total_gpu_count(self):
        return self._total_gpu_count

    @property
    def used_gpu_count(self):
        return self._used_gpu_count

    @property
    def avaliable_gpu_count(self):
        return self._avaliable_gpu_count

    @property
    def gpu_mode(self):
        return self._gpu_mode

    @property
    def node_label(self):
        return self._node_label

class NodeCPUMemoryInfo():
    def __init__(self, cpu_model, cpu_cores, allocated_cpu_cores, cpu_lock_per_pod, cpu_lock_per_gpu,
                    logical_cpu_cores_per_pod, logical_cpu_cores_per_gpu,
                    memory_size, allocated_memory_size, memory_lock_per_pod, memory_lock_per_gpu,
                    logical_memory_size_per_pod, logical_memory_size_per_gpu):
        # logical 크기의 경우 실제 물리적 크기 보다 적을 수 있음

        self._cpu_model = cpu_model # CPU 모델명
        self._cpu_cores = cpu_cores # 물리적 CPU cores 개수
        self._allocated_cpu_cores = allocated_cpu_cores # Pod에 할당되어 있는 CPU Cores 개수

        self._allocated_cpu_cores_ratio = round(allocated_cpu_cores / cpu_cores, 2) # Pod에 할당되어 있는 CPU Cores 개수 비율 (물리적 CPU Cores 대비)
        self._physical_avaliable_cpu_cores = cpu_cores - allocated_cpu_cores # 물리적 CPU Cores 개수 - Pod에 할당되어 있는 CPU Cores 개수

        self._cpu_lock_per_pod = cpu_lock_per_pod
        self._cpu_lock_per_gpu = cpu_lock_per_gpu
        self._logical_cpu_cores_per_pod = logical_cpu_cores_per_pod # CPU 용 Pod에서 총 사용할 수 있는 논리적 CPU Cores 개수
        self._logical_avaliable_cpu_cores_per_pod = logical_cpu_cores_per_pod - allocated_cpu_cores
        self._logical_cpu_cores_per_gpu = logical_cpu_cores_per_gpu # GPU 용 Pod에서 총 사용할 수 있는 논리적 CPU Cores 개수
        self._logical_avaliable_cpu_cores_per_gpu = logical_cpu_cores_per_gpu - allocated_cpu_cores

        # 관리하는 메모리 관련 단위는 Gi
        self._memory_size = memory_size # 물리적 Memory 크기
        self._allocated_memory_size = allocated_memory_size   # Pod에 할당되어 있는 Memory 크기
        self._allocated_memory_ratio = round(allocated_memory_size / memory_size, 2) # Pod에 할당되어 있는 Memory 비율
        self._physical_avaliable_memory_size = memory_size - allocated_memory_size # 물리적 Memory 크기 - Pod에 할당되어 있는 Memory 크기

        self._memory_lock_per_pod = memory_lock_per_pod
        self._memory_lock_per_gpu = memory_lock_per_gpu
        self._logical_memory_size_per_pod = logical_memory_size_per_pod # CPU 용 Pod에서 총 사용할 수 있는 논리적 Memory 크기
        self._logical_avaliable_memory_size_per_pod = logical_memory_size_per_pod - allocated_memory_size #
        self._logical_memory_size_per_gpu = logical_memory_size_per_gpu # GPU 용 Pod에서 총 사용할 수 있는 논리적 Memory 크기
        self._logical_avaliable_memory_size_per_gpu = logical_memory_size_per_gpu - allocated_memory_size


    @property
    def cpu_model(self):
        return self._cpu_model

    @property
    def cpu_cores(self):
        return self._cpu_cores

    @property
    def allocated_cpu_cores(self):
        return self._allocated_cpu_cores

    @property
    def physical_avaliable_cpu_cores(self):
        return self._physical_avaliable_cpu_cores

    @property
    def cpu_lock_per_cpu(self):
        return self._cpu_lock_per_pod

    @property
    def logical_cpu_cores_per_pod(self):
        return self._logical_cpu_cores_per_pod

    @property
    def logical_avaliable_cpu_cores_per_pod(self):
        return self._logical_avaliable_cpu_cores_per_pod

    @property
    def memory_size(self):
        return self._memory_size

    @property
    def allocated_memory_size(self):
        return self._allocated_memory_size

    @property
    def physical_avaliable_memory_size(self):
        return self._physical_avaliable_memory_size

    @property
    def memory_lock_per_pod(self):
        return self._memory_lock_per_pod

    @property
    def logical_avaliable_memory_size_per_pod(self):
        return self._logical_avaliable_memory_size_per_pod

    ## 요청 자원을 할당 시켰을 경우의 정보
    def get_allocated_cpu_cores_ratio_by_requested(self, requested_cpu_cores: float):
        """
            Description : 요청한 CPU Cores를 할당 했을 때 남아 있을 CPU Cores 비율 값 예상치

            Args:
                requested_cpu_cores (float): 요청한 cpu cores -  개수

            Return:
                (float) - 비율값
        """
        temp_allocated_cpu_cores = self.allocated_cpu_cores + requested_cpu_cores
        return round(temp_allocated_cpu_cores / self.cpu_cores, 2)

    def get_allocated_memory_size_ratio_by_requested(self, requested_memory_size: float):
        """
            Description : 요청한 Memory size를 할당 했을 때 남아 있을 Memory size 비율 값 예상치

            Args:
                requested_memory_size (float): 요청한 memory  -  크기 (단위 Gi)

            Return:
                (float) - 비율값
        """
        temp_allocated_memory_size = self.allocated_memory_size + requested_memory_size
        return round(temp_allocated_memory_size / self.memory_size, 2)

    def get_physical_avaliable_cpu_cores_by_requested(self, requested_cpu_cores: float):
        """
            Description : 요청한 CPU Cores를 할당 했을 때 남아 있을 CPU Cores 수

            Args:
                requested_cpu_cores (float): 요청한 cpu cores -  개수

            Return:
                (float) - 개수 (소수점 있을 수 있음)
        """
        temp_physical_avaliable_cpu_cores = self._physical_avaliable_cpu_cores - requested_cpu_cores
        return temp_physical_avaliable_cpu_cores

    def get_physical_physical_avaliable_memory_size_by_requested(self, requested_memory_size: float):
        """
            Description : 요청한 Memory를 할당 했을 때 남아 있을 Memory 크기

            Args:
                requested_memory_size (float): 요청한 메모리 - 크기 (단위 Gi)

            Return:
                (float) - XX(Gi)
        """
        temp_physical_avaliable_memory_size = self.physical_avaliable_memory_size - requested_memory_size
        return temp_physical_avaliable_memory_size

    ## Check 함수
    def is_cpu_cores_lock_per_pod(self):
        return self.cpu_lock_per_cpu == 1

    def is_cpu_cores_lock_per_gpu(self):
        return self.cpu_lock_per_gpu == 1

    def is_cpu_cores_allocatable_for_pod(self, requested_cpu_cores: float):
        if self.is_cpu_cores_lock_per_pod():
            return self.logical_avaliable_cpu_cores_per_pod >= requested_cpu_cores
        return True

    def is_memory_lock_per_pod(self):
        return self.memory_lock_per_pod == 1

    def is_memory_allocatable_for_pod(self, requested_memory_size: float):
        if self.is_memory_lock_per_pod():
            return self.logical_avaliable_memory_size_per_pod >= requested_memory_size
        return True

    # def get_allocated_memory_size_ratio_by_requested(self, requested_memory_size: float):
    #     """
    #     """

class NetworkGroupInfo():
    def __init__(self, network_group_id, network_group_name, speed, category, container_interface, node_interface):
        self._network_group_id = network_group_id
        self._network_group_name = network_group_name
        self._speed = speed # 속도가 빠른 순으로 정렬하기 위함
        self._category = category
        self._container_interface = container_interface # Pod에서 보이는 interface
        self._node_interface = node_interface # Node에서 사용해야 할 interface

    @property
    def network_group_id(self):
        return self._network_group_id

    @property
    def network_group_name(self):
        return self._network_group_name

    @property
    def speed(self):
        return self._speed

    @property
    def category(self):
        return self._category

    @property
    def container_interface(self):
        return self._container_interface

    @property
    def node_interface(self):
        return self._node_interface

    def is_infiniband_network_group(self):
        return self.category == NETWORK_GROUP_CATEGORY_INFINIBAND

    def is_ethernet_network_group(self):
        return self.category == NETWORK_GROUP_CATEGORY_ETHERNET

class NodeNetworkInfo():
    def __init__(self, network_group_info_list, node_interface_list):
        # 해당 Node가 가지고 있는 노드 그룹 정보 리스트
        # 전체 Interface 정보 - net=host 제거 시 불필요해질 수 있음
        self._network_group_info_list = network_group_info_list
        self._node_interface_list = node_interface_list

    @property
    def network_group_info_list(self):
        return self._network_group_info_list

    @property
    def node_interface_list(self):
        return self._node_interface_list

    def is_my_network_group(self, network_group_id):
        """
            Description : 확인하려는 network_group_id가 Node가 속해있는 Network Group 중 하나인지 내려주는 함수

            Args:
                network_group_id (int):

            Return:
                (bool)
        """

        if self.get_network_group_info(network_group_id=network_group_id) is not None:
            return True
        return False

    def get_infiniband_network_group_node_interface_list(self):
        node_interface_list = []
        for network_group_info in self.network_group_info_list:
            if network_group_info.is_infiniband_network_group():
                node_interface_list.append(network_group_info.node_interface)
        return node_interface_list

    def get_network_group_info(self, network_group_id):
        """
            Description : 동일한 network_group_id 를 가지는 경우가 존재 -> 멀티 포트
                        host_interface, container_interface가 다를 수 있음 (나머지는 동일)
                        이 함수에서는 1개의 network_group_info만 내려줌 (공통 정보 활용을 위함)

            Return :
                (NetworkGroupInfo)
        """
        for network_group_info in self.network_group_info_list:
            if network_group_info.network_group_id == network_group_id:
                return network_group_info
        return None

    def get_network_group_info_list(self, network_group_id):
        """
            Description : 동일한 network_group_id 를 가지는 경우가 존재 -> 멀티 포트
                        host_interface, container_interface가 다를 수 있음 (나머지는 동일)

            Return :
                (list (NetworkGroupInfo))
        """
        select_network_group_info_list = []
        for network_group_info in self.network_group_info_list:
            if network_group_info.network_group_id == network_group_id:
                select_network_group_info_list.append(network_group_info)
        return select_network_group_info_list

    def get_network_group_info_list_infiniband_only(self):
        """
            Description : 해당 노드가 등록되어 있는 network group 중 category가 infiniband인 network group만 가져오는 함수

            Return :
                (list (NetworkGroupInfo))
        """
        infiniband_network_group_info_list = []
        for network_group_info in self.network_group_info_list:
            if network_group_info.is_infiniband_network_group():
                infiniband_network_group_info_list.append(network_group_info)

        return infiniband_network_group_info_list

class NodeResourceAvaliableInfo():
    """
        k8s 기준으로 해당 노드에 Pod에서 사용중인거 빼고 남아있는 자원량
    """
    def __init__(self, resource_dict):
        """
            {
                'cpu': 41,
                'ephemeral-storage': 214606806561,
                'hugepages-1Gi': 0,
                'hugepages-2Mi': 0,
                'jf.device.rdma.ib/ib0': 0,
                'jf.device.rdma.ib/ib1': 0,
                'jf.device.rdma.ib/ibs9': 1000,
                'jf.network.ib/ibs9': 1,
                'memory': -212166967296,
                'nvidia.com/mig-1g.5gb': 6,
                'pods': 79
            }
        """
        self._resource_dict = resource_dict

    @property
    def resource_dict(self):
        return self._resource_dict

    def get_value(self, key):
        # TODO Key의 존재 유무를 확인이 필요한가?
        return self.resource_dict.get(key)

class NodeResourceLimitInfo():
    ## CPU / RAM / 임시 스토리지 정도의 정보 관리
    def __init__(self, max_cpu_limit, max_memory_limit, cpu_limit_per_pod, cpu_limit_per_gpu, memory_limit_per_pod, memory_limit_per_gpu,
                        ephemeral_storage_limit):
        """
            Description :
            Args :
                memory (str): k8s에서 내려주는 node 크기 값 상황에 따라 단위가 다양할 수 있음 10Gi, 100000K, 1Ti ...

        """
        self._max_cpu_limit = max_cpu_limit # 제한 값이 없을 때 혹은 GPU 개수 만큼 곱했을 때 물리적 개수를 넘어가는 경우 노드 자원의 최대 값을 주는 용도
        self._max_memory_limit = max_memory_limit # 제한 값이 없을 때 혹은 GPU 개수 만큼 곱했을 때 물리적 개수를 넘어가는 경우 노드 자원의 최대 값을 주는 용도 (단위는 Gi)
        self._cpu_limit_per_pod = cpu_limit_per_pod # CPU 쓸 때 CPU Core 개수 ex) 3, 10
        self._cpu_limit_per_gpu = cpu_limit_per_gpu # GPU 쓸 때 CPU Core 개수 ex) 3, 10
        self._memory_limit_per_pod = memory_limit_per_pod # CPU 쓸 때 Memory(ram) 크기 ex) 10, 30 (단위는 Gi)
        self._memory_limit_per_gpu = memory_limit_per_gpu # GPU 쓸 때 Memory(ram) 크기 ex) 10, 30 (단위는 Gi)
        self._ephemeral_storage_limit = ephemeral_storage_limit # 임시 메모리 크기 ex) 10 (단위는 Gi) 노드 초기화 후 자동 추가 시 None값 발생

        self._node_requested_info = None # 요청 자원 정보 관리용

    @property
    def max_cpu_limit(self):
        return self._max_cpu_limit

    @property
    def max_memory_limit(self):
        return self._max_memory_limit

    @property
    def cpu_limit_per_pod(self):
        return self._cpu_limit_per_pod

    @property
    def cpu_limit_per_gpu(self):
        return self._cpu_limit_per_gpu

    @property
    def memory_limit_per_pod(self):
        return self._memory_limit_per_pod

    @property
    def memory_limit_per_gpu(self):
        return self._memory_limit_per_gpu

    @property
    def ephemeral_storage_limit(self):
        return self._ephemeral_storage_limit

    @property
    def node_requested_info(self):
        return self._node_requested_info

    @node_requested_info.setter
    def node_requested_info(self, node_requested_info):
        self._node_requested_info = node_requested_info

    @property
    def requested_cpu_cores_per_pod(self):
        if self.node_requested_info.requested_cpu_cores_per_pod is None:
            return self.cpu_limit_per_pod
        else :
            return self.node_requested_info.requested_cpu_cores_per_pod

    @property
    def requested_cpu_cores_per_gpu(self):
        if self.node_requested_info.requested_cpu_cores_per_gpu is None:
            return self.cpu_limit_per_gpu
        else :
            return self.node_requested_info.requested_cpu_cores_per_gpu

    @property
    def requested_memory_size_per_pod(self):
        if self.node_requested_info.requested_memory_size_per_pod is None:
            return self.memory_limit_per_pod
        else :
            return self.node_requested_info.requested_memory_size_per_pod

    @property
    def requested_memory_size_per_gpu(self):
        if self.node_requested_info.requested_memory_size_per_gpu is None:
            return self.memory_limit_per_gpu
        else :
            return self.node_requested_info.requested_memory_size_per_gpu

    def _get_basic_resource_limit_form(self, cpu, memory, ephemeral_storage):
        form = {
            K8S_RESOURCE_CPU_KEY : cpu,
            K8S_RESOURCE_MEMORY_KEY : str(memory) + MEMORY_DEFAULT_UNIT,
            K8S_RESOURCE_EPHEMERAL_STORAGE_KEY : str(ephemeral_storage) + STORAGE_DEFAULT_UNIT
        }
        if ephemeral_storage is None:
            del form[K8S_RESOURCE_EPHEMERAL_STORAGE_KEY] # None 값일때는 특정 default 값 지정이 아닌 제거

        return form

    def get_basic_resource_limit_for_cpu(self):
        # CPU사용할 때 Pod의 CPU / RAM / 임시저장소 값
        return self._get_basic_resource_limit_form(cpu=self.requested_cpu_cores_per_pod, memory=self.requested_memory_size_per_pod, ephemeral_storage=self.ephemeral_storage_limit)

    def get_basic_resource_limit_for_gpu(self, requested_gpu_count):
        # GPU사용할 때 Pod의 CPU / RAM / 임시저장소 값
        # per gpu당 할당하는 값이기 때문에 GPU 개수만큼 곱하여 할당해주며 이 곱한 값이 물리적 개수를 넘어가는 경우 물리적 개수 값을 사용
        cpu = min(self.requested_cpu_cores_per_gpu * requested_gpu_count, self.max_cpu_limit)
        memory = min(self.requested_memory_size_per_gpu * requested_gpu_count, self.max_memory_limit)
        ephemeral_storage = self.ephemeral_storage_limit
        return self._get_basic_resource_limit_form(cpu=cpu, memory=memory, ephemeral_storage=ephemeral_storage)

    def get_basic_resource_limit(self, requested_gpu_count):
        if requested_gpu_count == 0:
            return self.get_basic_resource_limit_for_cpu()
        else:
            return self.get_basic_resource_limit_for_gpu(requested_gpu_count=requested_gpu_count)

    def get_resource_limit(self, requested_gpu_count):
        resource_limit = self.get_basic_resource_limit(requested_gpu_count=requested_gpu_count)
        return resource_limit

class NodeSpecificResourceLimitInfo():
    def __init__(self, gpu_resource_key, node_interface_list):
        """
            Description : GPU / RDMA / Infiniband 장치등을 할당하는 경우에 대해 각 노드에서 사용할 수 있는 Key 관리

            Args:
                gpu_resource_key (str) : GPU 사용 관련 resource key - nvidia.com/gpu, nvidia.com/mig-XXX
                node_interface_list (list): [ ib0, ib1, ibs9, ... ]
                                            - 이 변수를 받아서 아래 변수들을 생성
                                            network_ib_resource_key_list (list) : IB network 사용관련 resource key 여러개를 사용할 수 있음 -
                                            device_rdma_ib_resource_key_list (str) : RDMA (/dev/infiniband) 사용관련 resource key -
        """
        self._gpu_resource_key = gpu_resource_key
        self._network_ib_resource_key_list = [ K8S_RESOURCE_NETWORK_IB_LABEL_KEY.format(ib_interface=node_interface)  for node_interface in node_interface_list ]
        self._device_rdma_ib_resource_key_list = [ K8S_RESOURCE_DEVICE_RDMA_IB_LABEL_KEY.format(ib_interface=node_interface)  for node_interface in node_interface_list ]

        self._node_requested_info = None # 요청 자원 정보 관리용

    @property
    def gpu_resource_key(self):
        return self._gpu_resource_key

    @property
    def network_ib_resource_key_list(self):
        return self._network_ib_resource_key_list

    @property
    def device_rdma_ib_resource_key_list(self):
        return self._device_rdma_ib_resource_key_list

    @property
    def node_requested_info(self):
        return self._node_requested_info

    @node_requested_info.setter
    def node_requested_info(self, node_requested_info):
        self._node_requested_info = node_requested_info


    @property
    def requested_gpu_count(self):
        return self.node_requested_info.requested_gpu_count

    def get_ib_rdma_resource_limit(self, requested_gpu_count):
        # TODO Network interface를 무엇을 선택했느냐에 따라서 할당을 아예 안할 수 있음
        resource_limit = {}
        if len(self.network_ib_resource_key_list) == 0 or requested_gpu_count == 0:
            return resource_limit

        else:
            for ib_resource_key in self.network_ib_resource_key_list:
                resource_limit[ib_resource_key] = 1 # 경우에 따라서는 GPU 개수만큼 가져가야 할 수

            for ib_resource_key in self.device_rdma_ib_resource_key_list:
                resource_limit[ib_resource_key] = 1

        return resource_limit

    def get_ib_resource_limit(self, ib_interface_list):
        resource_limit = {}

        for ib_interface in ib_interface_list:
            network_ib = K8S_RESOURCE_NETWORK_IB_LABEL_KEY.format(ib_interface=ib_interface)
            device_rdma_ib = K8S_RESOURCE_DEVICE_RDMA_IB_LABEL_KEY.format(ib_interface=ib_interface)
            if network_ib in self.network_ib_resource_key_list and device_rdma_ib in self.device_rdma_ib_resource_key_list:
                resource_limit[network_ib] = 1
                resource_limit[device_rdma_ib] = 1
            else :
                raise Exception("ib_interface_list item invalid. Not exist.")

        return resource_limit

    def get_gpu_resource_limit(self, requested_gpu_count):
        resource_limit = {
            self.gpu_resource_key: requested_gpu_count
        }
        return resource_limit

    def get_resource_limit(self, requested_gpu_count, ib_interface_list):
        resource_limit = self.get_ib_resource_limit(ib_interface_list=ib_interface_list)
        resource_limit.update(self.get_gpu_resource_limit(requested_gpu_count=requested_gpu_count))
        return resource_limit

class NodeRequestedInfo():
    def __init__(self):
        # 현재 GPU, CPU, MEMORY는 NodeResourceLimitInfo, NodeSpecificResourceLimitInfo에 담고 있음

        self._requested_cpu_cores_per_pod = None
        self._requested_cpu_cores_per_gpu = None
        self._requested_memory_size_per_pod = None
        self._requested_memory_size_per_gpu = None

        self._requested_gpu_count = 0 # Scheduler에 의해서 할당 받을 GPU 개수를 전달 받았을 때

        self._requested_network_group_id = None # Multiple Node 실행 시 어떤 interface로 통신할거냐를 알려주기 위해서 필요함

    @property
    def requested_cpu_cores_per_pod(self):
        return self._requested_cpu_cores_per_pod

    @requested_cpu_cores_per_pod.setter
    def requested_cpu_cores_per_pod(self, requested_cpu_cores_per_pod):
        if requested_cpu_cores_per_pod is None:
            raise Exception("Not Allow None value.")
        self._requested_cpu_cores_per_pod = requested_cpu_cores_per_pod

    @property
    def requested_cpu_cores_per_gpu(self):
        return self._requested_cpu_cores_per_gpu

    @requested_cpu_cores_per_gpu.setter
    def requested_cpu_cores_per_gpu(self, requested_cpu_cores_per_gpu):
        if requested_cpu_cores_per_gpu is None:
            raise Exception("Not Allow None value.")
        self._requested_cpu_cores_per_gpu = requested_cpu_cores_per_gpu

    @property
    def requested_memory_size_per_pod(self):
        return self._requested_memory_size_per_pod

    @requested_memory_size_per_pod.setter
    def requested_memory_size_per_pod(self, requested_memory_size_per_pod):
        if requested_memory_size_per_pod is None:
            raise Exception("Not Allow None value.")
        self._requested_memory_size_per_pod = requested_memory_size_per_pod

    @property
    def requested_memory_size_per_gpu(self):
        return self._requested_memory_size_per_gpu

    @requested_memory_size_per_gpu.setter
    def requested_memory_size_per_gpu(self, requested_memory_size_per_gpu):
        if requested_memory_size_per_gpu is None:
            raise Exception("Not Allow None value.")
        self._requested_memory_size_per_gpu = requested_memory_size_per_gpu

    @property
    def requested_gpu_count(self):
        return self._requested_gpu_count

    @requested_gpu_count.setter
    def requested_gpu_count(self, requested_gpu_count):
        self._requested_gpu_count = requested_gpu_count

    @property
    def requested_network_group_id(self):
        return self._requested_network_group_id

    @requested_network_group_id.setter
    def requested_network_group_id(self, requested_network_group_id):
        self._requested_network_group_id = requested_network_group_id

# TODO Pod 실행 시 NAD Annotations 와 Pod에 Annotations 붙여주는 부분 여기서 관리 할 수 있도록
class NodeAnnotationInfo():
    def __init__(self):
        self._network_annotaion_key = ""
        self._network_annotaion_value = "" #

class NodeBasicInfo():
    def __init__(self, node_id, node_name, node_ip, is_gpu_server, is_cpu_server):
        """
            Description : Node를 설명하는 기본 정보 - DB 정보가 대부분
            Args:
                node_id (int)
                node_name (str)
                node_ip (str)
                is_gpu_server (int) : 1 (True) 0 (False)
                is_cpu_server (int) : 1 (True) 0 (False)

        """

        self._node_id = node_id
        self._node_name = node_name
        self._node_ip = node_ip

        self._is_gpu_server = is_gpu_server  # GPU 서버로 등록 되어 있는가
        self._is_cpu_server = is_cpu_server  # CPU 서버로 등록 되어 있는가

    @property
    def node_name(self):
        return self._node_name

    @property
    def node_ip(self):
        return self._node_ip

    @property
    def is_gpu_server(self):
        return self._is_gpu_server

    @property
    def is_cpu_server(self):
        return self._is_cpu_server



class NodeInfo():
    def __init__(self, node_gpu_info, node_cpu_memory_info, node_network_info, node_avaliable_resource_info,
                    node_resource_limit_info, node_basic_info, node_specific_resource_limit_info, node_requested_info):
        self._node_gpu_info = node_gpu_info # NodeGPUInfo - GPU 선택과 관련된 정보 - node를 특정하는 정보 필요 (gpu_model and node_name)
        self._node_cpu_memory_info = node_cpu_memory_info # NodeCPUInfo - CPU 선택과 관련된 정보 - node를 특정하는 정보 필요 (node_name == cpu_model)
        self._node_network_info = node_network_info # NodeNetworkInfo - Network 선택과 관련된 정보 - node_id 필요
        self._node_avaliable_resource_info = node_avaliable_resource_info # Node에 남아있는 k8s 자원 정보
        self._node_resource_limit_info = node_resource_limit_info # CPU / RAM / 임시저장소 등 Pod에서 기본적으로 사용될 수 있는 resource 정보
        self._node_basic_info = node_basic_info

        self._node_specific_resource_limit_info = node_specific_resource_limit_info # 특별한 장치 (gpu, network device, rdma device) 관리하는 resource 정보

        self._node_requested_info = node_requested_info # 노드 자원 중 요청한 정보들을 보관

        self._node_resource_limit_info.node_requested_info = node_requested_info
        self._node_specific_resource_limit_info.node_requested_info = node_requested_info

    @property
    def node_gpu_info(self):
        return self._node_gpu_info

    @property
    def node_cpu_memory_info(self):
        return self._node_cpu_memory_info

    @property
    def node_network_info(self):
        return self._node_network_info

    @property
    def node_avaliable_resource_info(self):
        return self._node_avaliable_resource_info

    @property
    def node_resource_limit_info(self):
        return self._node_resource_limit_info

    @property
    def node_specific_resource_limit_info(self):
        return self._node_specific_resource_limit_info

    @property
    def node_basic_info(self):
        return self._node_basic_info

    @property
    def node_requested_info(self):
        return self._node_requested_info

    # FROM GPU INFO
    def get_gpu_model(self):
        return self.node_gpu_info.gpu_model

    def get_avaliable_gpu_count(self):
        return self.node_gpu_info.avaliable_gpu_count

    def get_total_gpu_count(self):
        return self.node_gpu_info.total_gpu_count

    def get_used_gpu_count(self):
        return self.node_gpu_info.used_gpu_count

    # FROM CPU RAM INFO
    def get_cpu_model(self):
        return self.node_cpu_memory_info.cpu_model

    # FROM RESOURCE LIMIT INFO
    def get_resource_limits(self, requested_network_group_only=False):
        requested_gpu_count = self.node_requested_info.requested_gpu_count
        resource_limits = self.node_resource_limit_info.get_resource_limit(requested_gpu_count=requested_gpu_count) # CPU, Memory, 임시 저장소 관련 자원

        ib_interface_list = []
        if requested_gpu_count > 0:
            # GPU를 사용할때만 IB 자원 가능한 정책으로 진행.
            if requested_network_group_only == True:
                # 자원할당하면서 사용하기로 정의된 network group interface만 container에 등록하도록 - JOB | HPS 에 대응
                # 선택한 network group이 IB가 아니라면 IB 자원은 유한하기 때문에 제외함 (Ethernet은 별도로 제한하지 않음)

                network_group_info_list = self.get_requested_network_group_info_list()
                for network_group_info in network_group_info_list:
                    if network_group_info.is_infiniband_network_group():
                        if self.is_network_resource_enough(network_group_id=network_group_info.network_group_id):
                            ib_interface_list.append(network_group_info.node_interface)

            else :
                # 정의된 Network Group 과 관계 없이 모든 Interface를 사용하는 케이스 - Tool (JOB | HPS 제외) 와 Deployment Worker에 대응
                # 등록되어 있는 IB 자원을 모두 사용하려고 시도하며 IB 자원이 부족한 경우 해당 IB 자원은 제외시킴
                # 1. 해당 노드가 들어가있는 network group을 전부 가져옴
                # 2. network group 중 infiniband인 경우 자원이 남아있는지 확인
                # 3. 남아 있는 IB Interface만 resource limits form으로 받아옴
                ib_interface_list = []
                for infiniband_network_group_info in self.node_network_info.get_network_group_info_list_infiniband_only():
                    network_group_id = infiniband_network_group_info.network_group_id
                    if self.is_network_resource_enough(network_group_id=network_group_id):
                        ib_interface_list.append(infiniband_network_group_info.node_interface)


        resource_limits.update(self.node_specific_resource_limit_info.get_resource_limit(requested_gpu_count=requested_gpu_count, ib_interface_list=ib_interface_list)) # GPU, Network 관련 자원

        return resource_limits


    # FROM NETWORK INFO
    def get_requested_include_exclude_interfaces(self):
        """
            Description: Job, HPS 와 같이 멀티 노드 + mpirun을 하게 되는 경우 통신할 interface 지정 및 통신에 강제로 제외할 interface 지정을 위해 값을 내려주는 함수
                            - Pod 내부 interface로 처리하게 되면 해당 함수를 사용하지 않게 될 수 있음
                            - NCCL_SOCKET_IFNAME 을 지정하는것 외에 exclude를 지정하는 이유
                                - 노드간 interface 이름이 서로 다른 경우 의도하지 않은 interface로 통신이 발생하여 진행을 안하는 경우 발생
                                - NCCL_SOCKET_IFNAME 을 사용한다 하더라도 지정한 interface가 아닌 다른 interface를 사용하는 경우가 있음 (정확한 테스트 필요함)


            Return:
                (list), (list) - include_interfaces, exclude_interfaces
        """
        # TODO net=host 를 사용하지않는 구조로 변경 시 전체적으로 수정 필요함
        network_group_id = self.node_requested_info.requested_network_group_id
        if network_group_id is None:
            raise Exception("Network Group Empty")

        node_interface_list = self.node_network_info.node_interface_list
        network_group_info_list = self.node_network_info.get_network_group_info_list(network_group_id=network_group_id)
        if len(network_group_info_list) == 0:
            raise Exception("Network Group Not exist.")

        # node_interface = network_group_info.node_interface # 현재 net=host 를 사용하기 때문에 node_interface를 사용함
        # network_group_info.container_interface

        include_interfaces = [ network_group_info.node_interface for network_group_info in network_group_info_list ]
        exclude_interfaces = set(node_interface_list) - set(include_interfaces)


        return include_interfaces, exclude_interfaces

    def is_network_resource_enough(self, network_group_id):
        """
            Description : Infiniband를 활용하기 위해서는 GPU 자원 이외에 rdma device, network ib device 가 충분해야한다.
                            - rdma device는 자원을 복사해가는 형식이므로 개수를 조절해서 무한하게 유지가 가능함
                            - network ib device의 경우 생성되어 있는 자원을 아예 가져가는 구조이므로 무한하게 유지 불가
                            - GPU 개수 이상으로 생성해두긴 하겠지만 여러 이유로 (ex CPU Pod에서도 허용, GPU 개수만 증가 등) 개수의 괴리가 발생할 수 있음
                        해당 network_group_id 기준으로 충분한 자원이 있는지 확인하는 로직
                            - Infiniband가 아닌 자원은 무한하므로 자동 통과

            Return:
                (bool)
        """
        network_group_info_list = self.node_network_info.get_network_group_info_list(network_group_id=network_group_id)

        if len(network_group_info_list) == 0:
            raise Exception("Unknown Network Group")

        if network_group_info_list[0].is_ethernet_network_group():
            return True

        elif network_group_info_list[0].is_infiniband_network_group():
            for network_group_info in network_group_info_list:
                network_ib = K8S_RESOURCE_NETWORK_IB_LABEL_KEY.format(ib_interface=network_group_info.node_interface)
                rdma_ib = K8S_RESOURCE_DEVICE_RDMA_IB_LABEL_KEY.format(ib_interface=network_group_info.node_interface)
                network_ib_value = self.node_avaliable_resource_info.get_value(key=network_ib)
                rdma_ib_value = self.node_avaliable_resource_info.get_value(key=rdma_ib)
                if network_ib_value != None and network_ib_value > 0:
                    pass
                else:
                    return False

                if rdma_ib_value != None and rdma_ib_value > 0:
                    pass
                else:
                    return False
        else :
            raise Exception("Unknown Network Group category")

        return True

    # FROM BASIC INFO
    def get_node_name(self):
        return self.node_basic_info.node_name


    # FROM REQUESTED Info
    def get_requested_gpu_count(self):
        return self.node_requested_info.requested_gpu_count

    def get_requested_network_group_name(self):
        network_group_id = self.node_requested_info.requested_network_group_id
        network_group_name = self.node_network_info.get_network_group_info(network_group_id=network_group_id).network_group_name
        return network_group_name

    def get_requested_network_group_info(self):
        network_group_id = self.node_requested_info.requested_network_group_id
        network_group_info = self.node_network_info.get_network_group_info(network_group_id=network_group_id)
        return network_group_info

    def get_requested_network_group_info_list(self):
        network_group_id = self.node_requested_info.requested_network_group_id
        network_group_info_list = self.node_network_info.get_network_group_info_list(network_group_id=network_group_id)
        return network_group_info_list


    # Requested Set
    def set_resource_requested_gpu_count(self, requested_gpu_count):
        self.node_requested_info.requested_gpu_count = requested_gpu_count

    def set_requested_network_group_id(self, requested_network_group_id):
        self.node_requested_info.requested_network_group_id = requested_network_group_id

    def set_requested_cpu_memory_resource_limit_for_cpu(self, cpu_limit, memory_limit):
        if cpu_limit is None:
            cpu_limit = self.node_resource_limit_info.cpu_limit_per_pod

        if memory_limit is None:
            memory_limit = self.node_resource_limit_info.memory_limit_per_pod

        self.node_requested_info.requested_cpu_cores_per_pod = min(cpu_limit, self.node_resource_limit_info.cpu_limit_per_pod)
        self.node_requested_info.requested_memory_size_per_pod = min(memory_limit, self.node_resource_limit_info.memory_limit_per_pod)

    def set_requested_cpu_memory_resource_limit_for_gpu(self, cpu_limit, memory_limit):
        if cpu_limit is None:
            cpu_limit = self.node_resource_limit_info.cpu_limit_per_gpu

        if memory_limit is None:
            memory_limit = self.node_resource_limit_info.memory_limit_per_gpu

        self.node_requested_info.requested_cpu_cores_per_gpu = min(cpu_limit, self.node_resource_limit_info.cpu_limit_per_gpu)
        self.node_requested_info.requested_memory_size_per_gpu = min(memory_limit, self.node_resource_limit_info.memory_limit_per_gpu)

    # gpu_info | cpu_info -> node_network_info       특정할 수 있음
    # node_network_info -> gpu_info | cpu_info       특정할 수 없음 ( MIG를 선택한 경우에는 노드 id가 같은 gpu_info가 여러개일 수 있음  )

    # cpu_cores, memory 할당 만큼의

class NodeInfoManager():

    def __init__(self, node_info_list=None, pod_list=None, node_list=None, db_node_list=None):
        if node_info_list is None:
            self._node_info_list = [] # [ NodeInfo(), ... ]
            self._init(pod_list=pod_list, node_list=node_list, db_node_list=db_node_list)
        else:
            self._node_info_list = node_info_list

    def _init(self, pod_list=None, node_list=None, db_node_list=None):
        if pod_list is None:
            pod_list = kube.kube_data.get_pod_list()
        if node_list is None:
            node_list = kube.kube_data.get_node_list()
        if db_node_list is None:
            db_node_list = db.get_node_list()

        nodes_avaliable_resource_dict = kube.get_nodes_avaliable_resource_dict(pod_list=pod_list, node_list=node_list)

        for db_node in db_node_list:
            node_id = db_node["id"]
            node_name = db_node["name"].lower()

            item_list = kube.find_kuber_item_name_and_item(item_list=node_list, **{ KUBE_NODE_NAME_LABEL_KEY: node_name })
            if len(item_list) > 0:
                node = item_list[0]["item"]
            else:
                continue

            # node_gpu_info 생성, kube node 정보 필요 (n개가 생성 될 수 있음)
            node_gpu_info_list = self._get_node_gpu_info(node=node, pod_list=pod_list)
            # node_cpu_info 생성, kube node 정보 + db node 정보 필요

            # node_network_info 생성, db node 정보 필요
            for node_gpu_info in node_gpu_info_list:
                node_resource_limit_info = self._get_node_resource_limit_info(node=node, db_node=db_node)
                node_cpu_memory_info = self._get_node_cpu_memory_info(node=node, db_node=db_node, pod_list=pod_list)
                node_network_info = self._get_node_network_info(node_id=node_id)
                node_basic_info = self._get_node_basic_info(db_node=db_node)
                node_requested_info = self._get_node_requested_info()
                node_avaliable_resource_info = self._get_node_avaliable_resource_info(resource_dict=nodes_avaliable_resource_dict.get(node_name))
                node_specific_resource_limit_info = self._get_node_specific_resource_limit_info(node_network_info=node_network_info, node_gpu_info=node_gpu_info)
                self._node_info_list.append(NodeInfo(node_gpu_info=node_gpu_info, node_cpu_memory_info=node_cpu_memory_info,
                                                    node_network_info=node_network_info, node_avaliable_resource_info=node_avaliable_resource_info,
                                                    node_resource_limit_info=node_resource_limit_info,
                                                    node_basic_info=node_basic_info, node_specific_resource_limit_info=node_specific_resource_limit_info,
                                                    node_requested_info=node_requested_info))

    @property
    def node_info_list(self):
        return self._node_info_list

    ### OBJECT 획득 관련 함수
    def _get_node_gpu_info(self, node, pod_list):
        """
            Description : K8s Node 로부터 가져올 수 있는 정보 획득

            Args:
                node (object) : k8s를 통해 가져온 node object

            Return :
                (list) : [KubeGPUNodeInfo (object)] # MIG를 포함하는 경우 MIG 마다 1개의 Object가 되기 때문에 여러개가 존재할 수 있음
        """
        # MIG Case에 대한 고려가 필요
        # 노드에 A100 + Mig type a + Mig type b 가 있는 경우라면 ?
        # 기존 방법에서는 동일한 dict안에서 mig만 따로 묶어서 (mig_detail)로 관리 했었음
        # GPU 종류 1개 기준으로 Object를 하나씩 생성 ? -> 그러면 해당 함수에서 return 이 1 ~ n개가 될 수 있음
        # + 자원 사용 중 / 남은 정보는 pod_list에서 계산해서 업데이트를 해야함
        # 이 함수 내부에서 node, pod_list 를 받아서 계산을 할것인지 pod_list를 입력하여 별도로 계산할것인지 ?..


        # 잔존 GPU 정보들을 취합해서 보는 용도기 때문에 명칭이 GPU 기준에서 보여진다면 ?
        def update_mig_detail(total, used):
            new_mig_detail = {}

            for k, v in total.items():
                new_mig_detail[k] = {
                    "total": int(v),
                    "used": 0
                }
                if used.get(k) is not None:
                    new_mig_detail[k]["used"] += int(used.get(k))
            return new_mig_detail

        def combine_mig_used_detail(mig_used_detail_list):
            combine_mig_detail = {

            }
            for mig_detail in mig_used_detail_list:
                for k, v in mig_detail.items():
                    if combine_mig_detail.get(k) is None:
                        combine_mig_detail[k] = int(v)
                    else :
                        combine_mig_detail[k] += int(v)
            return combine_mig_detail

        def get_pod_gpu_usage_per_node(pod_list, node_name):

            general_used = 0
            mig_used = 0
            mig_used_detail_list = []
            for pod in pod_list.items:
                if kube_parser.parsing_pod_node_name(pod=pod) == node_name:
                    pod_gpu_resource = kube_parser.parsing_pod_gpu_resource(pod)
                    general_used += pod_gpu_resource["general_gpu"]
                    mig_used += pod_gpu_resource["mig_gpu"]
                    mig_used_detail_list.append(pod_gpu_resource["mig_detail"])
            mig_used_detail = combine_mig_used_detail(mig_used_detail_list)

            return general_used, mig_used, mig_used_detail


        node_is_ready = kube_parser.parsing_node_is_ready(node=node)
        node_ip, node_name = kube_parser.parsing_node_ip_and_hostname(node)
        node_gpu_resource = kube_parser.parsing_node_gpu_resource(node)
        gpu_model = kube_parser.parsing_node_gpu_model(node)
        node_label = kube_parser.parsing_item_labels(item=node)

        general_used, mig_used, mig_used_detail = get_pod_gpu_usage_per_node(pod_list=pod_list, node_name=node_name)

        if node_is_ready:
            node_gpu_resource = kube_parser.parsing_node_gpu_resource(node)
            general_total = node_gpu_resource["general_gpu"]
            mig_total = node_gpu_resource["mig_gpu"]
            mig_total_detail = node_gpu_resource["mig_detail"]
            new_mig_total_detail = update_mig_detail(mig_total_detail, mig_used_detail)
        else :
            # 서버가 정상이 아닌 경우에 처리
            return []

        node_gpu_info_list = []
        node_general_gpu_info = NodeGPUInfo(gpu_model=gpu_model,
                                                    total_gpu_count=general_total, used_gpu_count=general_used, gpu_mode=GPU_GENERAL_MODE, node_label=node_label)
        node_gpu_info_list.append(node_general_gpu_info)

        for key, value in new_mig_total_detail.items():
            mig_total = value["total"]
            mig_used = value["used"]
            mig_gpu_model = common.convert_mig_model_to_gpu_model_form(gpu_model=gpu_model, mig_model=key)
            node_mig_gpu_info = NodeGPUInfo(gpu_model=mig_gpu_model,
                                                    total_gpu_count=mig_total, used_gpu_count=mig_used, gpu_mode=GPU_MIG_MODE, node_label=node_label)
            node_gpu_info_list.append(node_mig_gpu_info)

        return node_gpu_info_list

    def _get_node_cpu_memory_info(self, node, db_node, pod_list):
        """
            Description : cpu / memory 정보 및 사용량 정보 획득

            Args:
                node (object) : k8s를 통해 가져온 node object
                db_node (dict) : db에서 가져온 node 정보 dict
                pod_list (object) : k8s를 통해 가져온 pod list object

            Return:
                (NodeCPUMemoryInfo)
        """
        def get_pod_cpu_memory_usage_per_node(pod_list, node_name, node_cpu_cores, node_memory_size):
            allocated_cpu_cores = 0
            allocated_memory_size = 0
            for pod in pod_list.items:
                if kube_parser.parsing_pod_node_name(pod) == node_name:
                    pod_cpu_limit = kube_parser.parsing_pod_resource_cpu(pod)
                    pod_memory_limit =  kube_parser.parsing_pod_resource_memory(pod)
                    if pod_cpu_limit is None:
                        pod_cpu_limit = node_cpu_cores
                    else :
                        pod_cpu_limit = common.convert_unit_num(value=pod_cpu_limit, target_unit=CPU_CORES_DEFAULT_UNIT, return_num=True)

                    if pod_memory_limit is None:
                        pod_memory_limit = node_memory_size
                    else :
                        pod_memory_limit = common.convert_unit_num(value=pod_memory_limit, target_unit=MEMORY_DEFAULT_UNIT, return_num=True)

                    allocated_cpu_cores += pod_cpu_limit
                    allocated_memory_size += pod_memory_limit

            return allocated_cpu_cores, allocated_memory_size

        def get_logical_cpu_cores_memory_size(db_node, node_cpu_cores, node_memory_size):
            node_cpu_lock_per_pod = db_node[NODE_CPU_CORE_LOCK_PER_POD_DB_KEY]
            node_cpu_lock_per_gpu = db_node[NODE_CPU_CORE_LOCK_PER_GPU_DB_KEY]
            node_memory_lock_per_pod = db_node[NODE_MEMORY_LOCK_PER_POD_DB_KEY]
            node_memory_lock_per_gpu = db_node[NODE_MEMORY_LOCK_PER_GPU_DB_KEY]

            node_cpu_lock_percent_per_pod = db_node[NODE_CPU_CORE_LOCK_PERCENT_PER_POD_DB_KEY]
            node_cpu_lock_percent_per_gpu = db_node[NODE_CPU_CORE_LOCK_PERCENT_PER_GPU_DB_KEY]
            node_memory_lock_percent_per_pod = db_node[NODE_MEMORY_LOCK_PERCENT_PER_POD_DB_KEY]
            node_memory_lock_percent_per_gpu = db_node[NODE_MEMORY_LOCK_PERCENT_PER_GPU_DB_KEY]

            logical_cpu_cores_per_pod = round(node_cpu_cores * (node_cpu_lock_percent_per_pod/100) if node_cpu_lock_per_pod else -1, 2)
            logical_cpu_cores_per_gpu = round(node_cpu_cores * (node_cpu_lock_percent_per_gpu/100) if node_cpu_lock_per_gpu else -1, 2)
            logical_memory_size_per_pod = round(node_memory_size * (node_memory_lock_percent_per_pod/100) if node_memory_lock_per_pod else -1, 2)
            logical_memory_size_per_gpu = round(node_memory_size * (node_memory_lock_percent_per_gpu/100) if node_memory_lock_per_gpu else -1, 2)

            return logical_cpu_cores_per_pod, logical_cpu_cores_per_gpu, logical_memory_size_per_pod, logical_memory_size_per_gpu

        node_ip, node_name = kube_parser.parsing_node_ip_and_hostname(node)
        node_other_resource = kube_parser.parsing_node_other_resource(node)
        node_cpu_cores = int(node_other_resource[K8S_RESOURCE_CPU_KEY])
        node_memory = common.convert_unit_num(value=node_other_resource[K8S_RESOURCE_MEMORY_KEY], target_unit=MEMORY_DEFAULT_UNIT, return_num=True)

        cpu_model = db_node["cpu"]
        cpu_lock_per_pod = db_node[NODE_CPU_CORE_LOCK_PER_POD_DB_KEY]
        cpu_lock_per_gpu = db_node[NODE_CPU_CORE_LOCK_PER_GPU_DB_KEY]
        memory_lock_per_pod = db_node[NODE_MEMORY_LOCK_PER_POD_DB_KEY]
        memory_lock_per_gpu = db_node[NODE_MEMORY_LOCK_PER_GPU_DB_KEY]


        allocated_cpu_cores, allocated_memory_size = get_pod_cpu_memory_usage_per_node(pod_list=pod_list, node_name=node_name, node_cpu_cores=node_cpu_cores, node_memory_size=node_memory)

        logical_cpu_cores_per_pod, logical_cpu_cores_per_gpu, logical_memory_size_per_pod, logical_memory_size_per_gpu = get_logical_cpu_cores_memory_size(db_node=db_node, node_cpu_cores=node_cpu_cores, node_memory_size=node_memory)


        return NodeCPUMemoryInfo(cpu_model=cpu_model, cpu_cores=node_cpu_cores, allocated_cpu_cores=allocated_cpu_cores,
                            cpu_lock_per_pod=cpu_lock_per_pod, cpu_lock_per_gpu=cpu_lock_per_gpu,
                            logical_cpu_cores_per_pod=logical_cpu_cores_per_pod, logical_cpu_cores_per_gpu=logical_cpu_cores_per_gpu,
                            memory_size=node_memory, allocated_memory_size=allocated_memory_size,
                            memory_lock_per_pod=memory_lock_per_pod, memory_lock_per_gpu=memory_lock_per_gpu,
                            logical_memory_size_per_pod=logical_memory_size_per_pod, logical_memory_size_per_gpu=logical_memory_size_per_gpu)

    def _get_node_network_info(self, node_id):
        """
            Description : node id로 해당 node가 가지고 있는 network group 정보 조회

            Args:
                node_id (int)

            Return:
                (NodeNetworkInfo)

        """
        network_group_and_interface_list = db.get_network_group_and_interface_list_by_node_id(node_id=node_id)
        node_interface_list = [ d["interface"] for d in db.get_node_interface(node_id=node_id) ]  # job, hps에서는 net=host 사용으로 사용하지 않을 interface를 지정하는데 이때 사용 될 목록들

        network_group_info_list = [NetworkGroupInfo(network_group_id=SINGLE_NODE_NETWORK_GROUP_ID, network_group_name=SINGLE_NODE_NETWORK_GROUP_NAME,
                                                    speed=None, category=None, container_interface=SINGLE_NODE_NETWORK_GROUP_INTERFACE, node_interface=SINGLE_NODE_NETWORK_GROUP_INTERFACE)]
        for data in network_group_and_interface_list:
            network_group_info_list.append(NetworkGroupInfo(network_group_id=data["id"], network_group_name=data["name"], speed=data["speed"], category=data["category"],
                                                            container_interface=data["container_interface"], node_interface=data["node_interface"]))

        return NodeNetworkInfo(network_group_info_list=network_group_info_list, node_interface_list=node_interface_list)

    def _get_node_avaliable_resource_info(self, resource_dict):
        """
            Description : node id로 해당 node가 가지고 있는 network group 정보 조회

            Args:
                resource_dict (dict): {"resource1": 1, "resource2": 1, ...}

            Return:
                (NodeResourceAvaliableInfo)

        """
        return NodeResourceAvaliableInfo(resource_dict)

    def _get_node_resource_limit_info(self, node, db_node):
        """
            Description : Pod 생성 관련 Resource limit 정보 (Node에서 제한하는 값 및 최대 가능 값)

            Args:
                db_node (dict) : db node list 결과 값

            Return
                (NodeResourceLimitInfo)
        """
        node_other_resource = kube_parser.parsing_node_other_resource(node)
        cpu_cores = int(node_other_resource[K8S_RESOURCE_CPU_KEY])
        memory = common.convert_unit_num(value=node_other_resource[K8S_RESOURCE_MEMORY_KEY], target_unit=MEMORY_DEFAULT_UNIT, return_num=True)

        cpu_limit_per_pod = db_node[NODE_CPU_LIMIT_PER_POD_DB_KEY]
        cpu_limit_per_gpu = db_node[NODE_CPU_LIMIT_PER_GPU_DB_KEY]
        memory_limit_per_pod = db_node[NODE_MEMORY_LIMIT_PER_POD_DB_KEY]
        memory_limit_per_gpu = db_node[NODE_MEMORY_LIMIT_PER_GPU_DB_KEY]
        ephemeral_storage_limit = db_node[NODE_EPHEMERAL_STORAGE_LIMIT_KEY]

        return NodeResourceLimitInfo(max_cpu_limit=cpu_cores, max_memory_limit=memory, cpu_limit_per_pod=cpu_limit_per_pod, cpu_limit_per_gpu=cpu_limit_per_gpu,
                             memory_limit_per_pod=memory_limit_per_pod, memory_limit_per_gpu=memory_limit_per_gpu, ephemeral_storage_limit=ephemeral_storage_limit)

    def _get_node_specific_resource_limit_info(self, node_network_info, node_gpu_info):
        """
            Description : Network 정보와 GPU 정보로 부터 특별한 resource 정보 저장

            Args :
                node_network_info (NodeNetworkInfo) - rdma, infiniband 사용 정보 및 key 획득
                node_gpu_info (NodeGPUInfo) - gpu 사용 종류에 따른 resource key 획득

            Return :
                (NodeSpecificResourceLimitInfo)
        """
        gpu_model = node_gpu_info.gpu_model
        gpu_resource_key = common.convert_gpu_model_to_resource_key_form(gpu_model=gpu_model)

        node_ib_interface_list = node_network_info.get_infiniband_network_group_node_interface_list()

        return NodeSpecificResourceLimitInfo(gpu_resource_key=gpu_resource_key, node_interface_list=node_ib_interface_list)

    def _get_node_basic_info(self, db_node):
        """
            Description : Node의 기본적인 정보를 저장하는 영역

            Args:
                db_node (dict) : db node list 결과 값

            Return
                (NodeBasicInfo)
        """
        node_id = db_node["id"]
        node_name = db_node["name"].lower()
        node_ip = db_node["ip"]

        is_gpu_server = db_node["is_gpu_server"]
        is_cpu_server = db_node["is_cpu_server"]

        return NodeBasicInfo(node_id=node_id, node_name=node_name, node_ip=node_ip, is_gpu_server=is_gpu_server, is_cpu_server=is_cpu_server)

    def _get_node_requested_info(self):

        return NodeRequestedInfo()

    ### 필요한 노드를 찾는 함수
    def _get_specific_node_info_by_gpu_model(self, gpu_model, node_name):
        """
            Description : NodeInfo에서 node_gpu_info 기준으로 GPU MODEL명 및 NODE NAME명에 맞춰 일치하는 node_info 내려주는 함수

            Args:
                gpu_model (str) : GPU Model 명 ex) NVIDIA-GeForce-GTX-1080-Ti
                node_name (str) : 일치하는 노드 이름 ex) jf-node-06

            Return:
                (list (NodeInfo)) - 일반적으로 gpu_model - node_name 조합은 0~1개의 결과가 나오나
                                       TBD 추후 gpu_model만 입력받고 전체를 사용하는 케이스와 같은 상황을 대응하기 위해 여러개의 return을 내려주는 상황 가정
        """
        match_list = []
        for node_info in self._node_info_list:
            if node_info.get_gpu_model() == gpu_model and node_info.get_node_name() == node_name:
                match_list.append(node_info)
        return match_list

    def _get_specific_node_info_by_gpu_mode(self, gpu_mode):
        """
            Description : NodeInfo에서 node_gpu_info 기준으로 gpu_mode 값에 맞춰 일치하는 node_info 내려주는 함수

            Args:
                gpu_mode (str) : GPU_ALL_MODE(전체 사용), GPU_GENERAL_MODE, GPU_MIG_MODE 를 선택할 수 있으며 GPU 형태 값

            Return:
                (list (NodeInfo)) -
        """
        match_list = []
        for node_info in self._node_info_list:
            node_gpu_info = node_info.node_gpu_info
            if node_gpu_info.gpu_mode == gpu_mode:
                match_list.append(node_info)

        return match_list

    def _get_specific_node_info_by_network_group_id(self, network_group_id):
        """
            Description : NodeInfo에서 node_network_info 기준으로 network_group_id 값에 맞춰 일치하는 node_info 내려주는 함수

            Args:
                network_group_id(int) : network group id값

            Return:
                (list (NodeInfo)) -
        """
        match_list = []
        for node_info in self._node_info_list:
            node_network_info = node_info.node_network_info
            if node_network_info.is_my_network_group(network_group_id=network_group_id):
                match_list.append(node_info)

        return match_list

    def _get_specific_node_info_by_node_name(self, node_name):
        """
            Description : DB node_name(dict) 컬럼 정보에서 KEY로 사용하는 node_name (str) 일치하는 node 찾아서 내려줌

            Args:
                node_name (str) : 일치하는 노드 이름 ex) jf-node-06

            Return:
                (list (NodeInfo))
        """
        match_list = []
        for node_info in self._node_info_list:
            if node_info.get_node_name() == node_name:
                match_list.append(node_info)

        return match_list

    def _get_specific_node_info_by_is_cpu_server(self):
        """
            Description : node_info_list 에서 cpu server로 등록되어 있는 노드만 가져오는 함수

            Return :
                (list (NodeInfo))
        """

        match_list = []
        for node_info in self.node_info_list:
            if node_info.node_basic_info.is_cpu_server == 1:
                match_list.append(node_info)

        return match_list

    def _get_specific_node_info_by_is_gpu_server(self):
        """
            Description : node_info_list 에서 gpu server로 등록되어 있는 노드만 가져오는 함수

            Return :
                (list (NodeInfo))
        """
        match_list = []
        for node_info in self.node_info_list:
            if node_info.node_basic_info.is_gpu_server == 1:
                match_list.append(node_info)

        return match_list


    ### 필요한 노드만 남기는 작업 관련 함수
    def update_node_info_list_by_reserved_gpu_model(self, reserved_gpu_model):
        """
            Description : reserved_gpu_model 값에 맞춰서 reserved_gpu_model 을 제외한 나머지 list 만 남김

            Args :
                reserved_gpu_model (dict) : Scheduler가 계산하면서 우선순위에 따라 예약해놓은 gpu_model 집합.  ex) {"NVIDIA-GeForce-GTX-1080-Ti": ["jf-node-02"]}
        """
        if reserved_gpu_model is not None:
            self._node_info_list = list(set(self._node_info_list) - set(self.get_node_info_manager_by_gpu_model(gpu_model=reserved_gpu_model).node_info_list))

    def update_node_info_list_by_gpu_model(self, gpu_model=None):
        """
            Description : 작업을 요청하는 gpu_model 값에 맞춰서 그에 맞는 list만 남김

            Args :
                gpu_model (dict) : DB에 GPU 선택 관련으로 저장하는 gpu_model - None 시 전체 사용.  ex) {"NVIDIA-GeForce-GTX-1080-Ti": ["jf-node-02"]}
        """
        self._node_info_list = self.get_node_info_manager_by_gpu_model(gpu_model=gpu_model).node_info_list

    def update_node_info_list_by_gpu_mode(self, gpu_mode):
        """
            Description : 작업을 요청하는 gpu_mode 값에 맞춰서 그에 맞는 list만 남김

            Args :
                gpu_mode (str) : GPU_ALL_MODE(전체 사용), GPU_GENERAL_MODE, GPU_MIG_MODE 를 선택할 수 있으며 GPU 형태 값
        """
        self._node_info_list = self.get_node_info_manager_by_gpu_mode(gpu_mode=gpu_mode).node_info_list

    def update_node_info_list_by_node_name(self, node_name):
        """
            Description : 작업을 요청하는 gpu_model 값에 맞춰서 그에 맞는 list만 남김

            Args :
                node_name (dict) : DB에 GPU 선택 관련으로 저장하는 node_name - None 시 전체 사용.
                                   ex) {"@all": {"is_active": true, "cpu_cores_limit_per_pod": 1, "ram_limit_per_pod": 1, "cpu_cores_limit_per_gpu": 1, "ram_limit_per_gpu": 1}, "jf-node-02": {"cpu_cores_limit_per_gpu": 4, "ram_limit_per_gpu": 4}}

        """
        self._node_info_list = self.get_node_info_manager_by_node_name(node_name=node_name).node_info_list

    def update_node_info_list_by_is_cpu_server(self):
        """
            Description : 작업을 요청하는 is_cpu_server 값에 맞춰서 그에 맞는 list만 남김
        """
        self._node_info_list = self.get_node_info_manager_by_is_cpu_server().node_info_list

    def update_node_info_list_by_is_gpu_server(self):
        """
            Description : 작업을 요청하는 is_gpu_server 값에 맞춰서 그에 맞는 list만 남김
        """
        self._node_info_list = self.get_node_info_manager_by_is_gpu_server().node_info_list


    ### 새 NodeInfoManager를 내려주는 관련 함수
    def get_node_info_manager_by_gpu_model(self, gpu_model=None):
        """
            Description : 작업을 요청하는 gpu_model 값에 맞춰서 그에 맞는 list만 남김

            Args :
                gpu_model (dict) : DB에 GPU 선택 관련으로 저장하는 gpu_model - None 시 전체 사용.  ex) {"NVIDIA-GeForce-GTX-1080-Ti": ["jf-node-02"]}

            Return:
                (NodeInfoManager)
        """
        if gpu_model is None:
            return NodeInfoManager(node_info_list=self.node_info_list)

        new_node_info_list = []

        for key, value in gpu_model.items():
            # key - GPU MODEL
            # value - NODE LIST
            for item in value:
                new_node_info_list += self._get_specific_node_info_by_gpu_model(gpu_model=key, node_name=item)

        return NodeInfoManager(node_info_list=list(set(new_node_info_list)))

    def get_node_info_manager_by_gpu_mode(self, gpu_mode):
        """
            Description : 작업을 요청하는 gpu_mode 값에 맞춰서 그에 맞는 list만 남김

            Args :
                gpu_mode (str) : GPU_ALL_MODE(전체 사용), GPU_GENERAL_MODE, GPU_MIG_MODE 를 선택할 수 있으며 GPU 형태 값

            Return:
                (NodeInfoManager)
        """
        if gpu_mode == GPU_ALL_MODE or gpu_mode is None:
            return NodeInfoManager(node_info_list=self.node_info_list)

        new_node_info_list = self._get_specific_node_info_by_gpu_mode(gpu_mode=gpu_mode)

        return NodeInfoManager(node_info_list=new_node_info_list)

    def get_node_info_manager_by_network_group_id(self, network_group_id):
        """
            Description : 해당하는 Network Group에 속한 (NodeInfoManager)를 가져오는 함수

            Args :
                network_group_id(int) : network group id값

            Return :
                (NodeInfoManager)
        """

        new_node_info_list = self._get_specific_node_info_by_network_group_id(network_group_id=network_group_id)
        return NodeInfoManager(node_info_list=new_node_info_list)

    def get_node_info_manager_by_node_name(self, node_name):
        """
            Description : 작업을 요청하는 gpu_model 값에 맞춰서 그에 맞는 list만 남김

            Args :
                node_name (dict) : DB에 GPU 선택 관련으로 저장하는 node_name - None 시 전체 사용.
                                   ex) {"@all": {"is_active": true, "cpu_cores_limit_per_pod": 1, "ram_limit_per_pod": 1, "cpu_cores_limit_per_gpu": 1, "ram_limit_per_gpu": 1}, "jf-node-02": {"cpu_cores_limit_per_gpu": 4, "ram_limit_per_gpu": 4}}

            Return:
                (NodeInfoManager)
        """
        new_node_info_list = []

        # TODO node_name 고도화 시 node_name (dict)에 담겨있는 값 그 자체를 사용할 것. 지금은 GPU 사용량 정보와 같이 있기 때문에 parsing을 수행함 (2022-11-25 Yeobie)
        node_name = common.parsing_node_name(node_name=node_name)["node_name_cpu"]
        for key, value in node_name.items():
            # key - NODE NAME
            # value - RESOURCE VALUE
            new_node_info_list += self._get_specific_node_info_by_node_name(node_name=key)

        return NodeInfoManager(node_info_list=new_node_info_list)

    def get_node_info_manager_by_is_cpu_server(self):
        """
            Description : cpu 사용이 등록된 노드들의 NodeInfoManager를 내려줌

            Return:
                (NodeInfoManager)
        """
        new_node_info_list = self._get_specific_node_info_by_is_cpu_server()

        return NodeInfoManager(node_info_list=new_node_info_list)

    def get_node_info_manager_by_is_gpu_server(self):
        """
            Description : gpu 사용이 등록된 노드들의 NodeInfoManager를 내려줌

            Return:
                (NodeInfoManager)
        """

        new_node_info_list = self._get_specific_node_info_by_is_gpu_server()

        return NodeInfoManager(node_info_list=new_node_info_list)

    def get_node_info_manager_for_pod(self, requested_gpu_count):
        # MIG 노드 검색 단계에서 requested_gpu_count 가 2 이상이면 진행하지 않도록 고려 필요 (상위에서 필터 걸고 사용하는 방식으로 진행)
        # 이전 방법에서는 rdma option을 줄때만 infiniband를 사용했음 - 자동 활성화 ?

        # Intra node check
        # 유형에 따라서 처리 방법이 조금 다름
        # 유형 1. JOB, HPS - 네트워크 인터페이스 필요 없음
        # 유형 2. TOOL(JOB|HPS 제외), Deployment Worker - 속해있는 모든 네트워크 인터페이스 필요함
        def get_intra_avaliable_node_info_list(requested_gpu_count):
            # used - 오름차순 (사용량 적은순으로)
            # avaliable - 오름차순 (사용 가능량 적은순으로) - intra 검색이기 때문에 avaliable이 많은 곳에서 동작하면 낭비가 생길 수 있음 - 서버에 최소개수의 프로젝트들이 돌아가는 것이 목표
            # 내림차순 (-XXXX)

            node_info_for_pod_list = [] # 선택된 노드 묶음
            node_info_list = sorted(self.node_info_list, key=lambda node_info: (
                    -(node_info.node_gpu_info.gpu_mode == GPU_MIG_MODE), # MIG를 먼저 사용하도록
                    node_info.get_used_gpu_count(),
                    node_info.get_avaliable_gpu_count()
                ))
            for i, node_info in enumerate(node_info_list):
                # GPU 요청 개수가 1 이상 있는데 노드 정보상 하나도 사용할 수 없는 노드라면 스킵
                if requested_gpu_count > 0 and node_info.get_avaliable_gpu_count() == 0:
                    continue

                # GPU 요청 개수 보다 노드의 사용 가능 개수가 많을 때
                if requested_gpu_count <= node_info.get_avaliable_gpu_count():
                    node_info.set_resource_requested_gpu_count(requested_gpu_count=requested_gpu_count)
                    node_info.set_requested_network_group_id(requested_network_group_id=SINGLE_NODE_NETWORK_GROUP_ID)
                    node_info_for_pod_list.append(node_info)
                    break

            return node_info_for_pod_list

        # Extra node check
        # 1. 전체 Network Group List를 가져와서 speed 빠른 순으로 정렬
        # 2. network group에 소속된 노드인지 확인하여 소속된 노드면 GPU 할당 -> 요청한 GPU 개수를 모두 만족하면 stop
        #     -> 만족하지 못하면 다음 network group으로 확인
        #     -> 마지막까지 만족 못하면 None Return
        # 고려사항 - 특정 network group 을 원하는 경우에 대한 대응 ? (Job HPS에 해당)
        # 고려사항 - 멀티노드 멀티GPU의 경우 기존 방법에서는 MIG를 제외하고 검색했음. 해당 조건을 유지?
        #               MIG일 땐 GPU 1개만 사용가능한 구조
        #               개발에 따라서는 Genernal + General + MIG 조합의 멀티노드 멀티GPU 학습도 가능함

        def get_net_avaliable_node_info_list(node_info_list, requested_gpu_count, network_group_id):
            # used - 오름차순 (사용량 적은순으로)
            # avaliable - 내림차순 (사용 가능량 많은순으로)
            #   - 사용가능한 양만큼 채워서 남은거는 다음으로 노드로 넘어가기 때문에 한번에 많이 할당하는 것이 목표
            #   - 어차피 여기 스탭으로 넘어온 것은 intra에서 만족하는 노드가 없는 상태임

            node_info_for_pod_list = [] # 선택된 노드 묶음

            node_info_list = sorted(node_info_list, key=lambda node_info: (node_info.get_used_gpu_count(), node_info.get_avaliable_gpu_count()))

            for i, node_info in enumerate(node_info_list):
                node_avaliable_gpu_count = node_info.get_avaliable_gpu_count()
                if requested_gpu_count > 0 and node_avaliable_gpu_count == 0:
                    continue

                # Infiniband 자원을 고려하는 부분
                # 현재 JOB/HPS에서는 --net=host를 사용하기에 자원을 무한정 사용 가능하나 변경 뒤를 고려해서 강제로 제한해놓음
                if node_info.is_network_resource_enough(network_group_id=network_group_id) == False:
                    continue

                if requested_gpu_count > node_avaliable_gpu_count:
                    # CASE 1. 요청한 GPU 개수가 노드에서 사용가능한 개수보다 많을 때
                    #   - 사용가능한 GPU 개수만큼 노드에 할당하고 나머지를 다음 노드에 넘김
                    node_info.set_resource_requested_gpu_count(requested_gpu_count=node_avaliable_gpu_count)
                    node_info.set_requested_network_group_id(requested_network_group_id=network_group_id)
                    node_info_for_pod_list.append(node_info)
                    requested_gpu_count = requested_gpu_count - node_avaliable_gpu_count
                else:
                    # CASE 2. 요청한 GPU 개수가 노드에서 사용가능한 개수와 같거나 보다 적을 때
                    #   - 요청한 GPU 개수를 노드에 할당하고 종료
                    node_info.set_resource_requested_gpu_count(requested_gpu_count=requested_gpu_count)
                    node_info.set_requested_network_group_id(requested_network_group_id=network_group_id)
                    node_info_for_pod_list.append(node_info)
                    requested_gpu_count = 0


                if requested_gpu_count == 0:
                    # 모든 GPU는 할당이 끝났음
                    break

            if requested_gpu_count == 0:
                return node_info_for_pod_list

            else:
                return None

        # IntraCheck
        intra_node_info_list = get_intra_avaliable_node_info_list(requested_gpu_count=requested_gpu_count)
        if len(intra_node_info_list) > 0:
            return NodeInfoManager(node_info_list=intra_node_info_list)

        # NetCheck
        # TODO 내부적으로 있는 Node List에서 사용할 수 있는 노드 그룹을 찾는 방향으로 ?
        net_node_info_list = None
        network_group_list = db.get_network_group_list()
        network_group_list = sorted(network_group_list, key=lambda network_group: (-network_group["speed"]))

        for network_group in network_group_list:
            # For문을 돌때마다 다음으로 빠른 Network Group을 검색함
            specific_network_group_node_info_manager = self.get_node_info_manager_by_network_group_id(network_group_id=network_group["id"])
            net_node_info_list = get_net_avaliable_node_info_list(node_info_list=specific_network_group_node_info_manager.node_info_list, requested_gpu_count=requested_gpu_count, network_group_id=network_group["id"])
            if net_node_info_list is not None:
                break

        if net_node_info_list is not None:
            return NodeInfoManager(node_info_list=net_node_info_list)
        else:
            return None

    def get_node_info_manager_for_cpu_pod(self):
        # NODE에
        #   1. cpu cores allocated ratio 적은 순으로
        #   2. memory allocated ratio 적은 순으로
        #   3. cpu cores 남아 있는게 많은 순으로 (물리적으로)
        #   4. memory 남아 있는게 많은 순으로 (물리적으로)
        # sorted(node_info, key=lambda node_list: (
        #         node_list[NODE_POD_ALLOC_CPU_CORES_RATIO_KEY],
        #         node_list[NODE_POD_ALLOC_MEMORY_RATIO_KEY],
        #         -node_list[NODE_POD_ALLOC_REMAINING_NUM_OF_CPU_CORES_KEY],
        #         -node_list[NODE_POD_ALLOC_REMAINING_MEMORY_SIZE_KEY]
        #     )
        # )
        def get_intra_avaliable_node_info_list(node_info_list):
            # Node가 무엇이냐에 따라서 CPU / MEMORY 값이 서로 다름
            # node 마다 request값이 종속되어 있음. -> 공통된 조건으로 정렬할 수 없음
            # 할당 되었을 때를 기준으로 정렬하는 이유.
            #   - 사용 중/총 코어 가 각각
            #   - A = 0/10,  B = 10/100
            #   - 단순 정렬 시 A는 사용 비율이 0 B는 10%기 때문에 정렬 시 A -> B 순서임
            #   - 여기서 요청을 5개씩 했다고 하면 A = 5/10 , B = 10/100 이 되어버림
            #   - 다음 작업에 대해서는 B -> A 순서로 되겠으나 사용 비율만 높고보면 원할한 분배가 아니게 되어보임
            #   - 미리 5개를 할당했을 때 어느 노드가 효율적인가로 정렬을 하면 B -> A 순서가 되기 때문에 조금 더 원할한 분배가 가능하다고 보임
            # 노드 제공 방법
            #   1. 요청이 어느 정도에 상관 없이 단순 우선순위 정렬 후 할당 가능하면 제공
            #   2. 요청량을 할당 받았을 때 가정 후 우선순위 정렬 후 할당 가능하면 제공 (헌재 구현 방식) - 노드 사용량 최적화 관점 ?
            #   3. 사용 요청량이 서로 다른데 결과적으로 가장 많은 CPU cores / memory를 사용할 수 있는 노드를 제공 - 사용자 경험 최고 관점 ?
            #       - 사용자 요청량이 많은 순으로 정렬 후 체크 ?
            #       - 사용자 경험을 추구한다면 원하는 노드만 선택 후 할당도 가능함 -> 시스템이 자동으로 제공해줄 때

            node_info_for_pod_list = []
            node_info_list = sorted(node_info_list, key=lambda node_info: (
                                node_info.node_cpu_memory_info.get_allocated_cpu_cores_ratio_by_requested(
                                    requested_cpu_cores=node_info.node_requested_info.requested_cpu_cores_per_pod
                                ),
                                node_info.node_cpu_memory_info.get_allocated_memory_size_ratio_by_requested(
                                    requested_memory_size=node_info.node_requested_info.requested_memory_size_per_pod
                                ),
                                -node_info.node_cpu_memory_info.get_physical_avaliable_cpu_cores_by_requested(
                                    requested_cpu_cores=node_info.node_requested_info.requested_cpu_cores_per_pod
                                ),
                                -node_info.node_cpu_memory_info.get_physical_physical_avaliable_memory_size_by_requested(
                                    requested_memory_size=node_info.node_requested_info.requested_memory_size_per_pod
                                )
                            ))
            for i, node_info in enumerate(node_info_list):
                # CPU 요청량 만큼 해당 노드가 생성 해줄 수 있는지 확인
                if node_info.node_cpu_memory_info.is_cpu_cores_allocatable_for_pod(requested_cpu_cores=node_info.node_requested_info.requested_cpu_cores_per_pod):
                    pass
                else:
                    continue

                # Memory 요청량 만큼 해당 노드가 생성 해줄 수 있는지 확인
                if node_info.node_cpu_memory_info.is_memory_allocatable_for_pod(requested_memory_size=node_info.node_requested_info.requested_memory_size_per_pod):
                    pass
                else:
                    continue

                node_info_for_pod_list.append(node_info)
                node_info.set_requested_network_group_id(requested_network_group_id=SINGLE_NODE_NETWORK_GROUP_ID)
                break

            return node_info_for_pod_list

        intra_node_info_list = get_intra_avaliable_node_info_list(node_info_list=self.node_info_list)
        if len(intra_node_info_list) > 0:
            return NodeInfoManager(node_info_list=intra_node_info_list)


    def apply_node_resource_limit(self, gpu_model, node_name):
        """
            Description: GPU 선택 / CPU 선택 후 cpu / memory 사용량 제한 값을 반영하여 pod 생성할 수 있도록

            Args:
                gpu_model (dict) - 현재는 cpu / memory 사용 정보를 포함하지 않음
                node_name (dict) - GPU/CPU 사용 시 각각에 대한 cpu / memory 정보 포함
                                    ex) {"@all": {"is_active": true, "cpu_cores_limit_per_pod": 1, "ram_limit_per_pod": 1, "cpu_cores_limit_per_gpu": 1, "ram_limit_per_gpu": 1}, "jf-node-02": {"cpu_cores_limit_per_gpu": 4, "ram_limit_per_gpu": 4}}
        """
        pass
        # TODO gpu_model -> GPU 사용관련 cpu/memory 할당, node_name -> CPU 사용관련 cpu/memory 할당 필요
        # 기능 분리 시 코드 구조 변경 될 것.

        # TODO CPU / MEMORY 제한 중 하나만 선언 할 경우 아예 반영 안하는 상황.
        node_name_gpu = common.parsing_node_name(node_name=node_name)["node_name_gpu"]
        node_name_cpu = common.parsing_node_name(node_name=node_name)["node_name_cpu"]

        if len(node_name_cpu) > 0:
            for key, value in node_name_cpu.items():
                # key - node name
                # value = { "cpu_cores_limit_per_pod": 1, "ram_limit_per_pod": 1 }
                for node_info in self._get_specific_node_info_by_node_name(node_name=key):
                    node_info.set_requested_cpu_memory_resource_limit_for_cpu(cpu_limit=value.get(NODE_CPU_LIMIT_PER_POD_DB_KEY), memory_limit=value.get(NODE_MEMORY_LIMIT_PER_POD_DB_KEY))
        else:
            # 전체 랜덤 시 사용할 수 있는 최대값 할당
            for node_info in self.node_info_list:
                node_info.set_requested_cpu_memory_resource_limit_for_cpu(cpu_limit=None, memory_limit=None)

        if len(node_name_gpu) > 0:
            for key, value in node_name_gpu.items():
                # key - node name
                # value = { "cpu_cores_limit_per_pod": 1, "ram_limit_per_pod": 1 }
                for node_info in self._get_specific_node_info_by_node_name(node_name=key):
                    node_info.set_requested_cpu_memory_resource_limit_for_gpu(cpu_limit=value.get(NODE_CPU_LIMIT_PER_GPU_DB_KEY), memory_limit=value.get(NODE_MEMORY_LIMIT_PER_GPU_DB_KEY))
        else:
            # 전체 랜덤 시 사용할 수 있는 최대값 할당
            for node_info in self.node_info_list:
                node_info.set_requested_cpu_memory_resource_limit_for_gpu(cpu_limit=None, memory_limit=None)

    ### 리스트에 있는 노드에서의 통계 정보 획득 함수
    def get_avaliable_gpu_count(self):

        # 정보가 필요할 때 매번 함수를 조회해야하는가 ?
        avaliable_gpu_count = 0
        for node_info in self.node_info_list:
            avaliable_gpu_count += node_info.get_avaliable_gpu_count()

        return avaliable_gpu_count

    def get_number_of_node(self):
        return len(self.node_info_list)

    def get_hosts_include_interfaces_exclude_interfaces(self):
        # interfaces {'include': ['lo'], 'exclude': ['ib1', 'vethwe-bridge', 'datapath', 'enp1s0f1', 'vethwepl1aede3b', 'docker0', 'veth6ab8a3f', 'enp67s0f3u2u3c2', 'vethweplb49d7a2', 'enp1s0f0', 'vxlan-6784', 'ib0', 'vethwe-datapath', 'vethwepl949e791', 'weave', 'enp129s0f1', 'enp129s0f0', 'vethwepl2f70566'], 'type': 'Intra Server'}
        # 선택된 Node들에서 어떤 네트워크를 선택했던건지 알아야함
        # 1. node list에서 공통적인 네트워크 그룹 찾는 함수
        # 2. 해당 네트워크 기준으로 각각 들고와서 interfaces 폼 생성
        # net=host 기반이 아니게 되면 exclude는 필요없어짐
        all_include_interfaces = []
        all_exclude_interfaces = []
        hosts = [] # "{IP}:{Num of Process = GPU Count}" ex)  "192.168.1.1:2"

        for node_info in self.node_info_list:
            host = "{node_ip}:{gpu_count}".format(node_ip=node_info.node_basic_info.node_ip, gpu_count=node_info.get_requested_gpu_count())
            hosts.append(host)

            include_interfaces, exclude_interfaces = node_info.get_requested_include_exclude_interfaces()
            all_include_interfaces += include_interfaces
            all_exclude_interfaces += exclude_interfaces

        hosts = ",".join(hosts)
        all_include_interfaces = ",".join(list(set(all_include_interfaces)))
        all_exclude_interfaces = ",".join(list(set(all_exclude_interfaces)))

        return hosts, all_include_interfaces, all_exclude_interfaces
