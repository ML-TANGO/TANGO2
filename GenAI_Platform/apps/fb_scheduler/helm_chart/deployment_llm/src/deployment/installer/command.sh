#!/bin/bash

# set_pod_env_path
# check_api_running
# install_package
# check_required_bin
# check & set rdma

# 1 log_cpu_ram_usage
# 2 log_gpu_usage
# 3 log_pod_run_time
# 4 log_pod_per_hour_call_count
# log_network_usage -> X
 
# set_nginx_count
# service_nginx_start
# run_pod_deployment_graph_log
# run_code

# ============================================================

# set_pod_env_path
echo 'export "PATH=$PATH:/usr/bin/support"'
export "PATH=$PATH:/usr/bin/support" >> $HOME/.bashrc
echo 'export "PATH=$PATH:/usr/bin/distributed"'
export "PATH=$PATH:/usr/bin/distributed" >> $HOME/.bashrc
echo 'export "AAAA=$PYTHONPATH:/addlib"'
export PYTHONPATH=$PYTHONPATH:/addlib >> $HOME/.bashrc
source $HOME/.bashrc 


# ============================================================
# check_api_running
# ============================================================
(
    for i in $(seq 0 999); do
        netstat -nltp | grep :8555
        netstat -nltp | grep :18555 2> /dev/null && break
        sleep 1
    done
) &

# ============================================================
# install_package
# ============================================================
### pip
if pip3 list | grep fastapi; then 
    echo 'pip pass'
else
    pip3 install -U fastapi uvicorn httptools uvloop watchfiles websockets six typing_extensions
fi
### apt
if apt list --installed | grep nginx; then
    echo 'apt pass'
else
    apt update
    DEBIAN_FRONTEND=noninteractive apt install -y nginx
fi

# ============================================================
# check_required_bin
# ============================================================
(
    echo datamash ? $(which datamash) $(datamash --version)
    echo curl ?  $(which curl) $(curl --version)
    echo netstat ? $(which netstat) $(netstat --version)
) > /required_bin_check

# ============================================================
# check & set rdma
# ============================================================
if [ "$JF_RDMA_ENABLED" == "true" ]; then
    RDMA_IP=$(ip -o -4 addr list "net1" | awk '{print $4}' | cut -d/ -f1)

    # Define the gateway and prefix based on JF_RDMA_IS_P2P
    if [ "$JF_RDMA_IS_P2P" = "true" ]; then
        GATEWAY="$RDMA_IP"
    else
        GATEWAY=$(echo $RDMA_IP | awk -F. '{print $1"."$2"."$3".1"}')
    fi

    # Extract the network prefix for the route
    PREFIX=$(echo $RDMA_IP | awk -F. '{print $1"."$2".0.0/16"}')

    # Add the route rule
    if ip route add "$PREFIX" via "$GATEWAY"; then
        echo "Route added: $PREFIX via $GATEWAY"
    else
        echo "Failed to add route: $PREFIX via $GATEWAY"
    fi

    read GID_INDEX DEV < <(show_gids | awk '$6 == "v2" && $5 != "" { print $3, $1 }')
    if ! [[ "$GID_INDEX" =~ ^[0-9]+$ ]]; then
        echo "Error: gid_idx is not valid. (GID_INDEX=$GID_INDEX)"
    fi

    echo "export NCCL_IB_GID_INDEX=$GID_INDEX \
           NCCL_DEBUG=INFO \
           NCCL_IB_HCA=$DEV \
           NCCL_SOCKET_IFNAME=net1
           "
    export NCCL_IB_GID_INDEX=$GID_INDEX \
           NCCL_DEBUG=INFO \
           NCCL_IB_HCA=$DEV \
           NCCL_SOCKET_IFNAME=net1

fi


# ============================================================
# log
# ============================================================
# 1 log_cpu_ram_usage: /resource_log/resource_usage.json -------------------------------------------------------------------------
(
nproc=$(nproc)
period=$(cat /sys/fs/cgroup/cpu/cpu.cfs_period_us 2> /dev/null )
quota=$(cat /sys/fs/cgroup/cpu/cpu.cfs_quota_us 2> /dev/null )
podnproc=$(awk '{print $1/$2}' <<<"$quota $period")

touch /resource_log/resource_usage.json
chmod 755 /resource_log/resource_usage.json

while [ 1 -eq 1 ]; do
    mem_usage=$(cat /sys/fs/cgroup/memory/memory.usage_in_bytes 2> /dev/null )
    mem_limit=$(cat /sys/fs/cgroup/memory/memory.limit_in_bytes 2> /dev/null )

    tstart=$(date +%s%N)
    cstart=$(cat /sys/fs/cgroup/cpu/cpuacct.usage 2> /dev/null )
    sleep 1
    tstop=$(date +%s%N)
    cstop=$(cat /sys/fs/cgroup/cpu/cpuacct.usage 2> /dev/null );
    cpu_usage=$(awk '{print ($1-$2)/($3-$4)*100 }' <<<"$cstop $cstart $tstop $tstart"  2> /dev/null )
    timestamp=$(date +%s)

    cpu_usage_on_node=$(awk '{print $1/$2}' <<<"$cpu_usage $nproc"  2> /dev/null );
    cpu_usage_on_pod=$(awk '{print $1/$2}' <<<"$cpu_usage $podnproc"  2> /dev/null )

    mem_usage_per=$(awk "BEGIN {print $mem_usage / $mem_limit * 100}"  2> /dev/null )
    mem_usage_per=$(printf "%.4f" $mem_usage_per);                                
    echo '{"cpu_usage_on_node":'$cpu_usage_on_node',"cpu_usage_on_pod":'$cpu_usage_on_pod',"mem_usage" :'$mem_usage',"mem_limit":'$mem_limit',"mem_usage_per":'$mem_usage_per',"timestamp":'$timestamp',"cpu_cores_on_pod":'$podnproc'}' > /resource_log/resource_usage.json
    cat /resource_log/resource_usage.json >> /resource_log/resource_usage_history.log

    HISTORY_DATA_LEN=$(cat /resource_log/resource_usage_history.log | wc -l)
    MAX_LEN=300

    if [ $HISTORY_DATA_LEN -gt 600 ]; then
        DEL_LEN=$(expr $HISTORY_DATA_LEN - $MAX_LEN)
        sed -i '1,'$DEL_LEN'd' /resource_log/resource_usage_history.log
    fi
done
) &

# 2 log_gpu_usage: /resource_log/gpu_usage_history.log; -------------------------------------------------------------------------
(
nvidia_gpu_count=$(nvidia-smi -L | wc -l);
echo gpu_count $nvidia_gpu_count;

nvidia-smi >> /dev/null;
nvidia_smi_result=$?;
echo $nvidia_smi_result;

re='^[ ]*?[0-9]+([.][0-9]+)?$'
while [ $nvidia_smi_result -eq 0 ] && [ $nvidia_gpu_count -gt 0 ]; do

    nvidia_log=$(nvidia-smi --format=csv,noheader,nounits --query-gpu=utilization.gpu,utilization.memory,memory.free,memory.used,memory.total | sed -e "s/Insufficient Permissions/Insufficient_Permissions/g" | tr ", " " ");
    timestamp=$(date +%s);
    
    SAVEIFS=$IFS;
    IFS=$'\n';
    nvidia_logs=($nvidia_log);
    IFS=$SAVEIFS;

    nvidia_log_jsons=();

    for (( i=0; i<${#nvidia_logs[@]}; i++ )); do
        array=(${nvidia_logs[$i]});

        util_gpu=${array[0]};
        util_memory=${array[1]};
        memory_free=${array[2]};
        memory_used=${array[3]};
        memory_total=${array[4]};

        if ! [[ $util_gpu =~ $re ]] ; then
            util_gpu='"'$util_gpu'"';
        fi 
        if ! [[ $util_memory =~ $re ]] ; then 
            util_memory='"'$util_memory'"';
        fi 
        if ! [[ $memory_free =~ $re ]] ; then 
            memory_free='"'$memory_free'"';
        fi 
        if ! [[ $memory_used =~ $re ]] ; then 
            memory_free='"'$memory_free'"';
        fi 
        if ! [[ $memory_used =~ $re ]] ; then 
            memory_used='"'$memory_used'"';
        fi 
        if ! [[ $memory_total =~ $re ]] ; then 
            memory_total='"'$memory_total'"';
        fi 

        if [ $i -eq 0 ] 
        then 
            nvidia_log_jsons[$i]='{ "'$i'": { "util_gpu": '$util_gpu', "util_memory": '$util_memory', "memory_free": '$memory_free', "memory_used": '$memory_used', "memory_total": '$memory_total', "timestamp": '$timestamp' }';
        else 
            nvidia_log_jsons[$i]=', "'$i'": { "util_gpu": '$util_gpu', "util_memory": '$util_memory', "memory_free": '$memory_free', "memory_used": '$memory_used', "memory_total": '$memory_total', "timestamp": '$timestamp' }';
        fi 
    done 
    nvidia_log_jsons[$i]='}';

    echo ${nvidia_log_jsons[@]} > /resource_log/gpu_usage.json 
    cat /resource_log/gpu_usage.json >> /resource_log/gpu_usage_history.log 
    sleep 1;

    HISTORY_DATA_LEN=$(cat /resource_log/gpu_usage_history.log | wc -l);
    MAX_LEN=300;

    if [ $HISTORY_DATA_LEN -gt 600 ]; then 
        DEL_LEN=$(expr $HISTORY_DATA_LEN - $MAX_LEN);
        sed -i '1,'$DEL_LEN'd' /resource_log/gpu_usage_history.log;
    fi 
done
) &

# 3 log_pod_run_time: /log/pod_run_time.json -------------------------------------------------------------------------

(
    format="+%Y-%m-%d %H:%M:%S";
    old_start_time=$(cat /log/pod_run_time.json  2>/dev/null  | sed 's/,.*//g'  | sed 's/^{ "start_time": //g'  | sed 's/"//g')
    if [ "$old_start_time" == "" ]; then 
        start_time=$(date "$format");
    else 
        start_time=$old_start_time;
    fi 

    while [ 1 -eq 1 ]; do 
        current_time=$(date "$format");
        echo '{ "start_time": "'$start_time'", "end_time": "'$current_time'" }' > /log/pod_run_time.json;
        sleep 1;
    done 
) &


# 4 log_pod_per_hour_call_count -------------------------------------------------------------------------
# 시간당 Call Count + Response Time 측정을 위한 스크립트
# Worker마다 실행하며 매 시간마다 특정 파일에 {"time":"2021-12-11T08","count":111,"median":333} 와 같은 값이 쌓임
# Deployment에서는 워커마다 있는 해당 파일을 읽은 후 "time"을 순차정렬하며 (중간에 빈 값은 0으로 ? ) 
# 읽은 파일 전체에서 가장 높은 time 기준으로 24개의 아이탬을 내려주기?
(
    DATE_FORMAT="+%Y-%m-%dT%H"
    DATE_FORMAT2="+%Y-%m-%d %H"
    NGINX_LOG_FILE=/log/nginx_access.log;
    API_MONITOR_LOG_FILE=/log/monitor.txt;
    NUM_OF_LOG_PER_HOUR_FILE=/log/nginx_access_per_hour.log;
    LAST_POINT=$(date "$DATE_FORMAT");
    LAST_POINT2=$(date "$DATE_FORMAT2");

    while true; do 
        POINT=$(date "$DATE_FORMAT");
        POINT2=$(date "$DATE_FORMAT2");

        if [ "$LAST_POINT" != "$POINT" ]; then

            # POINT CHANGE -> LAST UPDATE
            NUM_OF_LOG=$(cat $NGINX_LOG_FILE 2> /dev/null | grep $LAST_POINT | wc -l);

            # RESPONSE TIME
                # RESPONSE TIME \n
            RESPONSE_TIME_LIST=$(cat $NGINX_LOG_FILE 2> /dev/null | grep $LAST_POINT | sed "s/.*request_time.://\" | sed \"s/,.*//\" | sed \"s/['\\\" ]//g")

            echo $RESPONSE_TIME_LIST

            if [ "$RESPONSE_TIME_LIST" == "" ]; then
                # SKIP
                MEAN=0
                MEDIAN=0
            else
                RESULT=($(printf '%s ' $RESPONSE_TIME_LIST | datamash mean 1 median 1))
                MEAN=${RESULT[0]}
                MEDIAN=${RESULT[1]}
                if [ "$MEDIAN" == "" ]; then
                    MEDIAN=0
                fi
            fi

            NUM_OF_NGINX_ABNORMAL_LOG=$(cat $NGINX_LOG_FILE 2> /dev/null | grep $LAST_POINT | grep [\\\"]status[\\\"' ':]*[01456789][0-9]*\\\" | wc -l)
            echo "NUM_OF_ABBORMAL", $NUM_OF_NGINX_ABNORMAL_LOG
            NUM_OF_API_MONITOR_ABNORMAL_LOG=$(cat $API_MONITOR_LOG_FILE 2> /dev/null | grep "$LAST_POINT2" | grep "error_code"  | wc -l)                
                
            echo "NUM_OF_ABNORMAL2", $NUM_OF_API_MONITOR_ABNORMAL_LOG
            echo "LAST UPDATE"
        
            POINT_FORM='"time":\"'"$LAST_POINT"'"';
            NUM_OF_CALL_LOG_FORM='"count":'$NUM_OF_LOG;
            MEDIAN_LOG_FORM='"median":'$MEDIAN;
            NUM_OF_NGINX_ABNORMAL_LOG_FORM='"nginx_abnormal_count":'$NUM_OF_NGINX_ABNORMAL_LOG;
            NUM_OF_API_MONITOR_ABNORMAL_LOG_FORM='"api_monitor_abnormal_count":'$NUM_OF_API_MONITOR_ABNORMAL_LOG;
                    
            sed -i 's/{'"$POINT_FORM"'.*/{'"$POINT_FORM"','"$NUM_OF_CALL_LOG_FORM"','"$MEDIAN_LOG_FORM"',' "$NUM_OF_NGINX_ABNORMAL_LOG_FORM"','"$NUM_OF_API_MONITOR_ABNORMAL_LOG_FORM"'}/' $NUM_OF_LOG_PER_HOUR_FILE

            LAST_POINT=$POINT;
            LAST_POINT2=$POINT2;
        fi

        echo RUN $POINT
        NUM_OF_LOG=$(cat $NGINX_LOG_FILE 2> /dev/null | grep $POINT | wc -l);

        # RESPONSE TIME
        cat $NGINX_LOG_FILE
        RESPONSE_TIME_LIST=$(cat $NGINX_LOG_FILE 2> /dev/null | grep $POINT | sed "s/.*request_time.://" | sed "s/,.*//" | sed "s/['\\' ]//g");
        echo $RESPONSE_TIME_LIST

        if [ "$RESPONSE_TIME_LIST" == "" ]; then
            echo "@@@@@@@@@#! SKIP"
            MEAN=0
            MEDIAN=0
        else
            RESULT=($(printf '%s\n' $RESPONSE_TIME_LIST | datamash mean 1 median 1))
            MEAN=${RESULT[0]};
            MEDIAN=${RESULT[1]};
            echo "?????" $MEDIAN;
            echo "?????" $RESPONSE_TIME_LIST;
            if [ "$MEDIAN" == "" ]; then
                MEDIAN=0;
            fi
        fi

        # Abnormal COUNT
        # NUM_OF_NGINX_ABNORMAL_LOG=$(cat $NGINX_LOG_FILE 2> /dev/null | grep $POINT)
        NUM_OF_NGINX_ABNORMAL_LOG=$(cat $NGINX_LOG_FILE 2> /dev/null | grep $LAST_POINT | grep [\\\"]status[\\\"' ':]*[01456789][0-9]*\\\" | wc -l);
        echo NUM_OF_ABBORMAL, $NUM_OF_NGINX_ABNORMAL_LOG
        NUM_OF_API_MONITOR_ABNORMAL_LOG=$(cat $API_MONITOR_LOG_FILE 2> /dev/null | grep "$POINT2" | grep "error_code"  | wc -l)
        echo NUM_OF_ABNORMAL2, $NUM_OF_API_MONITOR_ABNORMAL_LOG, $POINT2

        POINT_FORM='"time":"'$POINT'"';
        NUM_OF_CALL_LOG_FORM='"count":'$NUM_OF_LOG;
        MEDIAN_LOG_FORM='"median":'$MEDIAN;
        NUM_OF_NGINX_ABNORMAL_LOG_FORM='"nginx_abnormal_count":'$NUM_OF_NGINX_ABNORMAL_LOG;
        NUM_OF_API_MONITOR_ABNORMAL_LOG_FORM='"api_monitor_abnormal_count":'$NUM_OF_API_MONITOR_ABNORMAL_LOG;

        echo $LOG_FORM
        cat $NUM_OF_LOG_PER_HOUR_FILE | grep $POINT > /dev/null;
        if [ $? -gt 0 ]; then
            echo CREATE ITEM
            echo '{'$POINT_FORM,$NUM_OF_CALL_LOG_FORM,$MEDIAN_LOG_FORM,$NUM_OF_NGINX_ABNORMAL_LOG_FORM,$NUM_OF_API_MONITOR_ABNORMAL_LOG_FORM'}' >> $NUM_OF_LOG_PER_HOUR_FILE;
        else
            echo UPDATE ITEM
            sed -i 's/{'"$POINT_FORM"'.*/{'"$POINT_FORM"','"$NUM_OF_CALL_LOG_FORM"','"$MEDIAN_LOG_FORM"','"$NUM_OF_NGINX_ABNORMAL_LOG_FORM"','"$NUM_OF_API_MONITOR_ABNORMAL_LOG_FORM"'}/' $NUM_OF_LOG_PER_HOUR_FILE;
        fi

        sleep 1;
    done
) > /per_hour_log 2> /per_hour_log &

# ================================================================================================
# set_nginx_count: /log/nginx_count.json
# ================================================================================================
(
    while true; do
        total=`cat /log/nginx_access.log 2> /dev/null | wc -l`
        success=`grep '"status": "2[0-9][0-9]"' /log/nginx_access.log 2> /dev/null | wc -l`
        echo '{"total_count":'${total}',"success_count":'${success}'}' > /log/nginx_count.json
        sleep 1
    done
) &
service nginx restart;

# ================================================================================================
# run_pod_deployment_graph_log 
# ================================================================================================

echo 'run pod deployment graph log';
DEPLOYMENT_WORKER_ID=${POD_DEPLOYMENT_WORKER_ID}
python3 /addlib/history.py --deployment_worker_id "$DEPLOYMENT_WORKER_ID" --interval 600 --search_type range --update_time 10 & 
python3 /addlib/history.py --deployment_worker_id "$DEPLOYMENT_WORKER_ID" --interval 1 --search_type live --update_time 1 &



# ================================================================================================
# NVIDIA_VISIBLE_DEVICES: UUID -> INT 변환 후 CUDA_VISIBLE_DEVICES 설정
# ================================================================================================
# NVIDIA_VISIBLE_DEVICES 환경 변수가 설정되어 있는지 확인
if [ -n "$NVIDIA_VISIBLE_DEVICES" ]; then
    # NVIDIA_VISIBLE_DEVICES에서 UUID 가져오기
    UUIDS=$(nvidia-smi --query-gpu=uuid --format=csv,noheader 2>/dev/null)
    if [ $? -eq 0 ] && [ -n "$UUIDS" ]; then
        # UUID를 인덱스로 매핑
        INDEX=0
        MAPPED_DEVICES=""
        for UUID in $UUIDS; do
            if [[ "$NVIDIA_VISIBLE_DEVICES" == *"$UUID"* ]]; then
                # 현재 UUID가 NVIDIA_VISIBLE_DEVICES에 있으면 인덱스 추가
                if [[ -z "$MAPPED_DEVICES" ]]; then
                    MAPPED_DEVICES="$INDEX"
                else
                    MAPPED_DEVICES="$MAPPED_DEVICES,$INDEX"
                fi
            fi
            INDEX=$((INDEX + 1))
        done

        # CUDA_VISIBLE_DEVICES 설정 (Ray와 PyTorch에서 사용)
        if [ -n "$MAPPED_DEVICES" ]; then
            export CUDA_VISIBLE_DEVICES="$MAPPED_DEVICES"
            echo "Updated CUDA_VISIBLE_DEVICES: $CUDA_VISIBLE_DEVICES"
        else
            echo "Warning: NVIDIA_VISIBLE_DEVICES was set but no matching GPU UUIDs found"
        fi
    else
        echo "Warning: nvidia-smi failed or no GPUs available"
    fi
else
    echo "Warning: NVIDIA_VISIBLE_DEVICES environment variable is not set"
fi


# ================================================================================================
# ray, run_code
# ================================================================================================
echo 'DEPLOYMENT RUNCODE START';
cd $JF_DEPLOYMENT_PWD;
cd /llm;
if [ "$LLM_TYPE" = "playground" ]; then
    echo 1
    if [ "$LLM_GPU_TOTAL_COUNT" = "0" ]; then

        python3 /llm/playground.py;

    elif [ "$LLM_POD_INDEX" = "0" ]; then
        echo 2
        ray start --head --port 6379  --disable-usage-stats # --include-dashboard=True 

        # 단일 GPU의 경우 대기 루프 스킵
        if [ "$LLM_GPU_TOTAL_COUNT" = "1" ]; then
            echo "Single GPU playground - skipping GPU cluster wait"
        else
            while true; do
                # ray status 출력 저장
                STATUS_OUTPUT=$(ray status)
                # 총 GPU 수 추출
                TOTAL_GPUS=$(echo "$STATUS_OUTPUT" | grep "GPU" | awk -F'/' '{print $2}' | awk '{print $1}' | cut -d'.' -f1)
                if [ "$TOTAL_GPUS" == "$LLM_GPU_TOTAL_COUNT" ]; then
                    echo RAY TOTAL GPU COUNT $TOTAL_GPUS
                    break        
                fi
                sleep 1
            done
        fi
        python3 /llm/playground.py;
    else
        ray start --address deployment-llm-playground-"$LLM_PLAYGROUND_ID"--service-ray:6379 --disable-usage-stats

        while true; do
            curl -s deployment-llm-playground-"$LLM_PLAYGROUND_ID"--service:18555
            if [ $? -eq 0 ]; then
                # startupProbe
                python -m http.server 8555 &
                break
            fi
        done
        sleep infinity &
    fi
elif [[ "$LLM_TYPE" == *"rag"* ]]; then

    echo 4
    if [[ "$LLM_TYPE" == *"embedding"* ]]; then
        echo 5
        python3 /llm/embedding.py;
    else
        echo 6 
        python3 /llm/reranker.py;
    fi
fi

sleep infinity;