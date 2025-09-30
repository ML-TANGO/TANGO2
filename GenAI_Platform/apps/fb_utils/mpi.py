import os
import sys
sys.path.insert(0, os.path.abspath('..'))
from utils.TYPE import *

def get_log_command(item_id, log_base):
    log_command = " > {log_base}/{item_id}.jflog 2>> {log_base}/{item_id}.jflog".format(log_base=log_base, item_id=item_id)
    return log_command

# def get_python_command(run_code, parameter):
#     if run_code.split(' ')[0][-3:]=='.py':
#         python_command = "python -u {run_code} {parameter}".format(run_code=run_code, parameter=parameter)
#     elif run_code.split(' ')[0][-3:]=='.sh':
#         python_command = "bash {run_code} {parameter}".format(run_code=run_code, parameter=parameter)
#     else:
#         python_command = "{run_code} {parameter}".format(run_code=run_code, parameter=parameter)
#     return python_command
"""
AZURE VERSION
mpirun --allow-run-as-root -np 4 -H 10.0.0.14:2,10.0.0.13:2 \
-bind-to none -map-by slot \
-x NCCL_NET_GDR_READ=1 \
-x NCCL_DEBUG=INFO \
-x NCCL_IB_DISABLE=0 \
-x NCCL_IB_CUDA_SUPPORT=1 \
-x NCCL_SOCKET_IFNAME=ib0 \
-x NCCL_P2P_LEVEL=4 \
-x NCCL_SHM_DISABLE=0 \
-x LD_LIBRARY_PATH -x PATH \
-mca btl_openib_allow_ib 1 \
-mca btl openib  \
-mca plm_rsh_args '-p 50000' \
-mca pml ^ucx \
-mca mpi_warn_on_fork 0 \
-mca btl_tcp_if_exclude datapath,docker0,lo,weave,eth0,eth1 \
python /examples/horovod/examples/tensorflow2_mnist.py
"""
"""
# RDMA 사용 관련 NCCL (2022-12-01 Yeobie)
mpirun --allow-run-as-root -np {total_gpu} -H {hosts} \
    -bind-to none -map-by slot \
    -x MASTER_ADDR=$MASTER_ADDR \
    -x MASTER_PORT=$MASTER_PORT \
    -x MPI_MODE=p2p \
    -x NCCL_DEBUG=INFO \
    -x NCCL_NET_GDR_READ=1 \
    -x NCCL_NET_GDR_LEVEL=4 \
    -x NCCL_IB_DISABLE=0 \
    -x NCCL_IB_CUDA_SUPPORT=1 \
    -x NCCL_SOCKET_IFNAME={nifs} \
    -x LD_LIBRARY_PATH -x PATH \
    -mca plm_rsh_args '-p 29000' \
    -mca btl_tcp_if_exclude {exnifs} \
"""


def get_base_mpirun_command(total_gpu, hosts, env_list=None):
    # mpirun_env = ""
    # if env_list is not None:
    #     for env in env_list:
    #         mpirun_env += " -x {key}={value} ".format(key=env["name"], value=env["value"])

    # base_mpi_run_command = """
    #     mpirun --allow-run-as-root -np {total_gpu} -H {hosts} \
    #     -bind-to none -map-by slot -x ENV_TEST=TRUE {mpirun_env} \
    # """.format(total_gpu=total_gpu, hosts=hosts, mpirun_env=mpirun_env)

    base_mpi_run_command = """
        mpirun --allow-run-as-root -np {total_gpu} -H {hosts} \
        -bind-to none -map-by slot \
        -x MASTER_ADDR=$MASTER_ADDR \
        -x MASTER_PORT=$MASTER_PORT \
    """.format(total_gpu=total_gpu, hosts=hosts)

    return base_mpi_run_command

def get_rdma_env(nifs, mpi_port, exnifs):
    rdma_env = """
        -x MPI_MODE=p2p \
        -x NCCL_DEBUG=INFO \
        -x NCCL_NET_GDR_READ=1 \
        -x NCCL_NET_GDR_LEVEL=4 \
        -x NCCL_IB_DISABLE=0 \
        -x NCCL_IB_CUDA_SUPPORT=1 \
        -x NCCL_SOCKET_IFNAME={nifs} \
        -x NCCL_SHM_DISABLE=0 \
        -x LD_LIBRARY_PATH -x PATH \
        -mca plm_rsh_args '-p {mpi_port}' \
        -mca btl_tcp_if_exclude {exnifs} \
    """.format(nifs=nifs, mpi_port=mpi_port, exnifs=exnifs)
    return rdma_env

def get_p2p_env(nifs, mpi_port, exnifs):
    p2p_env = """
        -x MPI_MODE=p2p \
        -x NCCL_DEBUG=INFO \
        -x NCCL_IB_DISABLE=1 \
        -x NCCL_IB_CUDA_SUPPORT=0 \
        -x NCCL_SOCKET_IFNAME={nifs} \
        -x NCCL_P2P_LEVEL=4 \
        -x NCCL_SHM_DISABLE=0 \
        -x LD_LIBRARY_PATH -x PATH \
        -mca pml ob1 -mca btl ^openib \
        -mca plm_rsh_args '-p {mpi_port}' \
        -mca btl_tcp_if_exclude {exnifs} \
    """.format(nifs=nifs, mpi_port=mpi_port, exnifs=exnifs)
    return p2p_env

def get_default_env(nifs, mpi_port, exnifs):
    default_env = """
        -x MPI_MODE=default \
        -x NCCL_DEBUG=INFO \
        -x NCCL_IB_DISABLE=1 \
        -x NCCL_IB_CUDA_SUPPORT=0 \
        -x NCCL_SOCKET_IFNAME={nifs} \
        -x NCCL_P2P_DISABLE=1 \
        -x NCCL_SHM_DISABLE=1 \
        -x LD_LIBRARY_PATH -x PATH \
        -mca pml ob1 -mca btl ^openib \
        -mca plm_rsh_args '-p {mpi_port}' \
        -mca btl_tcp_if_exclude {exnifs}\
    """.format(nifs=nifs, mpi_port=mpi_port, exnifs=exnifs)
    return default_env



def command_combine(run_code, parameter, item_id, log_base, mpi_command="", env_add_command="", with_log=True):
    import utils.common as common
    python_command = common.convert_run_code_to_run_command(run_code=run_code, parameter=parameter)

    if with_log == True:
        log_command = get_log_command(item_id=item_id, log_base=log_base)
    else :
        log_command = ""

    run_command = """
        {mpi_command} \
        {python_command} \
        {log_command} \
    """.format(mpi_command=mpi_command.replace("\n",""), python_command=python_command, log_command=log_command)

    return run_command

def get_rdma_run_command(total_gpu, hosts, nifs, mpi_port, exnifs, run_code, parameter, item_id=None, log_base=None, with_log=True):
    if total_gpu == 1:
        mpi_command = ""
    else :
        mpi_command = get_base_mpirun_command(total_gpu=total_gpu, hosts=hosts)
        mpi_command += get_rdma_env(nifs=nifs, mpi_port=mpi_port, exnifs=exnifs)

    run_command = command_combine(run_code=run_code, parameter=parameter, item_id=item_id, log_base=log_base, with_log=with_log,
                    mpi_command=mpi_command)

    return run_command

def get_p2p_run_command(total_gpu, hosts, nifs, mpi_port, exnifs, run_code, parameter, item_id=None, log_base=None, with_log=True):
    if total_gpu == 1:
        mpi_command = ""
    else :
        mpi_command = get_base_mpirun_command(total_gpu=total_gpu, hosts=hosts)
        mpi_command += get_p2p_env(nifs=nifs, mpi_port=mpi_port, exnifs=exnifs)

    run_command = command_combine(run_code=run_code, parameter=parameter, item_id=item_id, log_base=log_base, with_log=with_log,
                    mpi_command=mpi_command)

    return run_command

def get_default_run_command(total_gpu, hosts, nifs, mpi_port, exnifs, run_code, parameter, item_id=None, log_base=None, with_log=True):
    if total_gpu == 1:
        mpi_command = ""
    else :
        mpi_command = get_base_mpirun_command(total_gpu=total_gpu, hosts=hosts)
        mpi_command += get_default_env(nifs=nifs, mpi_port=mpi_port, exnifs=exnifs)

    run_command = command_combine(run_code=run_code, parameter=parameter, item_id=item_id, log_base=log_base, with_log=with_log,
                    mpi_command=mpi_command)
    return run_command

def get_cpu_run_command(run_code, parameter, item_id=None, log_base=None, with_log=True, **kwargs):
    run_command = command_combine(run_code=run_code, parameter=parameter, item_id=item_id, log_base=log_base, with_log=with_log)

    return run_command

def get_ssh_check_command(mpi_port, total_gpu, hosts):
    # Multi Node에서 실행 시 이미지가 없는 노드는 이미지 Pull을 받느라 오래 걸릴 수 있음
    # 따라서 아래 코드는 최장 2시간을 기다리도록 되어 있음
    # - mpirun 명령어가 없을 경우 체크를 종료하는 로직 추가 (2022-08-17)
    # TODO 나머지 Worker가 아예 실행하지 못한 경우 [ex) API 재시작] 발생 시 현재 구조로는 대처 방법이 마땅히 없음 (2022-10-11 yeobie)
    ssh_check_command = """
        for i in $(seq 1 3600); do
        /usr/sbin/sshd -p {mpi_port}
        mpirun --allow-run-as-root -np {total_gpu} -H {hosts} -mca plm_rsh_args "-p {mpi_port}" echo check && break
                echo $i
                sleep 2

        # mpirun command check
        which mpirun || break

        done
        echo END
    """.format(mpi_port=mpi_port, total_gpu=total_gpu, hosts=hosts)
    return ssh_check_command

#TODO ENV 변수화
def set_master_addr_and_port_env():
    # For Torch
    set_command = """
    MASTER_ADDR=$(echo $JF_OMPI_HOSTS | sed "s/:.*//" )
    MASTER_PORT_START=50000
    PORT_RANGE=10000

    for (( i = 0 ; i < 10000 ; i++ ))
    do
    #     SCAN_PORT=$(awk '{print $1+$2}' <<< "$i $MASTER_PORT")
        SCAN_PORT="$(($RANDOM% $PORT_RANGE+$MASTER_PORT_START))"
        echo $SCAN_PORT
        PORT_CHECK=$(netstat -nltp | grep LISTEN | grep :$SCAN_PORT | wc -l)
        if [ $PORT_CHECK -eq 0 ];
        then
            MASTER_PORT=$SCAN_PORT
            break
        fi
    done

    echo NEXT, $MASTER_PORT

    export MASTER_ADDR=$MASTER_ADDR
    export MASTER_PORT=$MASTER_PORT

    """
    return set_command


def get_infiniband_dev_set_command(network_group_category):
    # Infiniband <> no Infiniband 가 묶여서 학습 시 Infiniband disable 세팅을 주더라도 강제로 ib를 잡는 이슈 때문에
    if network_group_category != NETWORK_GROUP_CATEGORY_INFINIBAND:
        return "rm -r /dev/infiniband"
    else:
        return "echo SKIP"

def get_master_init_command(total_gpu, hosts, mpi_port, mpi_run, network_group_category):
    if total_gpu <= 1:
        ssh_check_command = ""
    else :
        ssh_check_command = get_ssh_check_command(mpi_port=mpi_port, total_gpu=total_gpu, hosts=hosts)

    infiniband_dev_set_command = get_infiniband_dev_set_command(network_group_category=network_group_category)
    set_master_addr_and_port_env_command = set_master_addr_and_port_env()
    mpi_init = """
        (
        rm /dev/nvidia*
        {set_master_addr_and_port_env_command}
        {infiniband_dev_set_command}
        sleep 2
        {ssh_check_command}
        cd /built_in_model/
        {mpi_run}
        sleep 2
        # sleep infinity
        )
    """.format(infiniband_dev_set_command=infiniband_dev_set_command, set_master_addr_and_port_env_command=set_master_addr_and_port_env_command,
                ssh_check_command=ssh_check_command, mpi_run=mpi_run)
    return mpi_init

def get_worker_init_command(mpi_port, network_group_category):
    infiniband_dev_set_command = get_infiniband_dev_set_command(network_group_category=network_group_category)

    mpi_init = """
        rm /dev/nvidia*; {infiniband_dev_set_command}; sleep 2; /usr/sbin/sshd -p {mpi_port}; sleep infinity
    """.format(infiniband_dev_set_command=infiniband_dev_set_command, mpi_port=mpi_port)
    return mpi_init

