#!/bin/bash

# --- 환경 변수 세팅 ---
echo 'export "PATH=$PATH:/usr/bin/support"' >> $HOME/.bashrc;
PATH="$PATH:/usr/bin/support"
echo 'export "AAAA=$PYTHONPATH:/addlib"' >> $HOME/.bashrc;
PYTHONPATH="$PYTHONPATH:/addlib"
source $HOME/.bashrc;

# --- 로그 디렉토리 생성 ---
mkdir -p /resource_log;
mkdir -p /log;

# --- API 포트 대기 (background) ---
(
  for i in $(seq 0 999);
  do
    netstat -nltp | grep :8555;
    netstat -nltp | grep :18555 2> /dev/null && break;
    sleep 1;
  done
) &

# --- 패키지 설치 ---
if pip3 show fastapi > /dev/null 2>&1; then
    echo 'pip pass';
else
    pip3 install -U fastapi uvicorn httptools uvloop watchfiles websockets six typing_extensions;
fi;

if apt list --installed | grep nginx > /dev/null 2>&1; then
    echo 'apt pass';
else
    # nginx 관련 기존 문제 먼저 해결
    echo "N" | sudo dpkg --configure -a > /dev/null 2>&1 || true;
    sudo apt --fix-broken install -y > /dev/null 2>&1 || true;
    
    # nginx 설치 (에러 숨김)
    apt update > /dev/null 2>&1;
    DEBIAN_FRONTEND=noninteractive apt install -y nginx > /dev/null 2>&1 || true;
fi;

# --- 필수 바이너리 확인 ---
(
    echo datamash ? $(which datamash) $(datamash --version)
    echo curl ?     $(which curl)     $(curl --version)
    echo netstat ?  $(which netstat)  $(netstat --version)
) > /required_bin_check;

# --- CPU/RAM 사용 로그 (background) ---
(
    nproc=$(nproc)
    # cgroup 버전 감지 및 pod코어수 계산
    if [ -f /sys/fs/cgroup/cpu.max ]; then
        read quota period < /sys/fs/cgroup/cpu.max
        if [ "$quota" = "max" ] || [ -z "$period" ]; then
            podnproc=$nproc
        else
            podnproc=$(awk "BEGIN { print $quota / $period }")
        fi
    elif [ -f /sys/fs/cgroup/cpu/cpu.cfs_quota_us ] && [ -f /sys/fs/cgroup/cpu/cpu.cfs_period_us ]; then
        quota=$(cat /sys/fs/cgroup/cpu/cpu.cfs_quota_us)
        period=$(cat /sys/fs/cgroup/cpu/cpu.cfs_period_us)
        if [ "$quota" -gt 0 ] && [ "$period" -gt 0 ]; then
            podnproc=$(awk "BEGIN { print $quota / $period }")
        else
            podnproc=$nproc
        fi
    else
        podnproc=$nproc
    fi

    touch /resource_log/resource_usage.json;
    chmod 755 /resource_log/resource_usage.json;

    while [ 1 -eq 1 ]; do
        # 메모리 사용량 수집 (cgroup v1/v2 호환)
        mem_usage=""
        mem_limit=""
        
        # cgroup v2 시도
        if [ -f /sys/fs/cgroup/memory.current ] && [ -f /sys/fs/cgroup/memory.max ]; then
            mem_usage=$(cat /sys/fs/cgroup/memory.current 2>/dev/null)
            mem_limit=$(cat /sys/fs/cgroup/memory.max 2>/dev/null)
        # cgroup v1 시도
        elif [ -f /sys/fs/cgroup/memory/memory.usage_in_bytes ] && [ -f /sys/fs/cgroup/memory/memory.limit_in_bytes ]; then
            mem_usage=$(cat /sys/fs/cgroup/memory/memory.usage_in_bytes 2>/dev/null)
            mem_limit=$(cat /sys/fs/cgroup/memory/memory.limit_in_bytes 2>/dev/null)
        fi
        
        # 메모리 값 검증 및 기본값 설정
        if [ -z "$mem_usage" ] || ! [[ "$mem_usage" =~ ^[0-9]+$ ]]; then
            mem_usage=0
        fi
        if [ -z "$mem_limit" ] || ! [[ "$mem_limit" =~ ^[0-9]+$ ]] || [ "$mem_limit" = "max" ]; then
            mem_limit=0
        fi

        # CPU 사용량 수집 (cgroup v1/v2 호환)
        cpu_usage=0
        
        tstart=$(date +%s%N);
        
        # cgroup v2 시도
        if [ -f /sys/fs/cgroup/cpu.stat ]; then
            cstart=$(awk '/usage_usec/ {print $2}' /sys/fs/cgroup/cpu.stat 2>/dev/null);
        # cgroup v1 시도
        elif [ -f /sys/fs/cgroup/cpu/cpuacct.usage ]; then
            cstart=$(cat /sys/fs/cgroup/cpu/cpuacct.usage 2>/dev/null);
            # 나노초를 마이크로초로 변환
            if [ -n "$cstart" ] && [[ "$cstart" =~ ^[0-9]+$ ]]; then
                cstart=$((cstart / 1000))
            fi
        fi
        
        sleep 1;
        
        tstop=$(date +%s%N);
        
        # cgroup v2 시도
        if [ -f /sys/fs/cgroup/cpu.stat ]; then
            cstop=$(awk '/usage_usec/ {print $2}' /sys/fs/cgroup/cpu.stat 2>/dev/null);
        # cgroup v1 시도
        elif [ -f /sys/fs/cgroup/cpu/cpuacct.usage ]; then
            cstop=$(cat /sys/fs/cgroup/cpu/cpuacct.usage 2>/dev/null);
            # 나노초를 마이크로초로 변환
            if [ -n "$cstop" ] && [[ "$cstop" =~ ^[0-9]+$ ]]; then
                cstop=$((cstop / 1000))
            fi
        fi
        
        # CPU 사용률 계산 (값 검증 포함)
        if [ -n "$cstart" ] && [ -n "$cstop" ] && [ -n "$tstart" ] && [ -n "$tstop" ] && \
           [[ "$cstart" =~ ^[0-9]+$ ]] && [[ "$cstop" =~ ^[0-9]+$ ]] && \
           [[ "$tstart" =~ ^[0-9]+$ ]] && [[ "$tstop" =~ ^[0-9]+$ ]] && \
           [ "$tstop" -gt "$tstart" ] && [ "$cstop" -ge "$cstart" ]; then
            cpu_usage=$(awk "BEGIN { 
                cdiff = $cstop - $cstart; 
                tdiff = ($tstop - $tstart) / 1000; 
                if (tdiff > 0) print (cdiff / tdiff) * 100; 
                else print 0 
            }")
        fi
        
        # CPU 사용률 검증 및 기본값 설정
        if [ -z "$cpu_usage" ] || ! [[ "$cpu_usage" =~ ^[0-9]*\.?[0-9]+$ ]]; then
            cpu_usage=0
        fi
        
        timestamp=$(date +%s);

        cpu_node=$(awk "BEGIN { if ($nproc > 0) print $cpu_usage / $nproc; else print 0 }")
        cpu_pod=$(awk "BEGIN { if ($podnproc > 0) print $cpu_usage / $podnproc; else print 0 }")

        # 메모리 사용률 계산
        if [ "$mem_limit" -gt 0 ]; then
            mem_per=$(awk "BEGIN { print ($mem_usage / $mem_limit) * 100 }")
        else
            mem_per=0
        fi
        mem_per=$(printf "%.4f" $mem_per);

        echo '{"cpu_usage_on_node":'$cpu_node',"cpu_usage_on_pod":'$cpu_pod',"mem_usage":'$mem_usage',"mem_limit":'$mem_limit',"mem_usage_per":'$mem_per',"timestamp":'$timestamp',"cpu_cores_on_pod":'$podnproc'}' > /resource_log/resource_usage.json;
        cat /resource_log/resource_usage.json >> /resource_log/resource_usage_history.log;

        HISTORY_DATA_LEN=$(cat /resource_log/resource_usage_history.log | wc -l);
        MAX_LEN=300;
        if [ $HISTORY_DATA_LEN -gt 600 ]; then
            DEL_LEN=$(expr $HISTORY_DATA_LEN - $MAX_LEN);
            sed -i '1,'$DEL_LEN'd' /resource_log/resource_usage_history.log;
        fi
    done
) &

# --- GPU 사용 로그 (background) ---
(
    while [ 1 -eq 1 ]; do
        nvidia_gpu_count=$(nvidia-smi -L 2> /dev/null | wc -l);
        #echo gpu_count $nvidia_gpu_count;

        nvidia-smi >> /dev/null;
        nvidia_smi_result=$?;
        #echo $nvidia_smi_result;

        re='^[ ]*?[0-9]+([.][0-9]+)?$';
        nvidia_log=$(nvidia-smi --format=csv,noheader,nounits --query-gpu=utilization.gpu,utilization.memory,memory.free,memory.used,memory.total | sed -e "s/Insufficient Permissions/Insufficient_Permissions/g" | tr ", " " ");
        timestamp=$(date +%s);

        SAVEIFS=$IFS; IFS=$'\n'; nvidia_logs=($nvidia_log); IFS=$SAVEIFS;
        json="{";
        for (( i=0; i<${#nvidia_logs[@]}; i++ )); do
            array=(${nvidia_logs[$i]});
            util_gpu=${array[0]}; util_mem=${array[1]}; mem_free=${array[2]}; mem_used=${array[3]}; mem_total=${array[4]};
            if ! [[ $util_gpu =~ $re ]]; then util_gpu='"'$util_gpu'"'; fi;
            if ! [[ $util_mem =~ $re ]]; then util_mem='"'$util_mem'"'; fi;
            if ! [[ $mem_free =~ $re ]]; then mem_free='"'$mem_free'"'; fi;
            if ! [[ $mem_used =~ $re ]]; then mem_used='"'$mem_used'"'; fi;
            if ! [[ $mem_total =~ $re ]]; then mem_total='"'$mem_total'"'; fi;
            entry='"'$i'":{ "util_gpu": '$util_gpu', "util_memory": '$util_mem', "memory_free": '$mem_free', "memory_used": '$mem_used', "memory_total": '$mem_total', "timestamp": '$timestamp' }';
            if [ $i -eq 0 ]; then json+=$entry; else json+=","$entry; fi;
        done;
        json+="}";
        echo $json > /resource_log/gpu_usage.json;
        cat /resource_log/gpu_usage.json >> /resource_log/gpu_usage_history.log;
        sleep 1;

        HISTORY_DATA_LEN=$(cat /resource_log/gpu_usage_history.log | wc -l);
        if [ $HISTORY_DATA_LEN -gt 600 ]; then
            DEL_LEN=$(expr $HISTORY_DATA_LEN - 600);
            sed -i '1,'$DEL_LEN'd' /resource_log/gpu_usage_history.log;
        fi
    done
) &

# --- 네트워크 사용 로그 (background) ---
(
    while [ 1 -eq 1 ]; do
        R1=`cat /sys/class/net/eth0/statistics/rx_bytes`;
        T1=`cat /sys/class/net/eth0/statistics/tx_bytes`;
        sleep 1;
        R2=`cat /sys/class/net/eth0/statistics/rx_bytes`;
        T2=`cat /sys/class/net/eth0/statistics/tx_bytes`;
        TXBytes=`expr $T2 - $T1`;
        RXBytes=`expr $R2 - $R1`;
        timestamp=$(date +%s);
        echo '{"tx_bytes":'$TXBytes',"rx_bytes":'$RXBytes',"@TIMESTAMP_KEY":'$timestamp'}' > /resource_log/network_usage.json;
        cat /resource_log/network_usage.json >> /resource_log/network_usage_history.log;
    done
) &

# --- Pod 실행 시간 로그 (background) ---
(
    format="+%Y-%m-%d %H:%M:%S";
    old_start_time=$(cat /log/pod_run_time.json 2>/dev/null | sed 's/,.*//g' | sed 's/^{ "start_time": //g' | sed 's/"//g');
    if [ "$old_start_time" == "" ]; then start_time=$(date "$format"); else start_time=$old_start_time; fi;
    while [ 1 -eq 1 ]; do
        current_time=$(date "$format");
        echo '{ "start_time": "'$start_time'", "end_time": "'$current_time'" }' > /log/pod_run_time.json;
        sleep 1;
    done
) &

# --- 시간별 호출 카운트 로그 (background) ---
(
    while [ 1 -eq 1 ]; do
        DATE_FORMAT="+%Y-%m-%dT%H"; DATE_FORMAT2="+%Y-%m-%d %H";
        LAST_POINT=$(date $DATE_FORMAT);
        POINT=$(date $DATE_FORMAT);
        if [ "$LAST_POINT" != "$POINT" ]; then
            NUM_OF_LOG=$(cat /log/nginx_access.log 2>/dev/null | grep $LAST_POINT | wc -l);
            RESPONSE_TIME_LIST=$(cat /log/nginx_access.log 2>/dev/null | grep $LAST_POINT | sed "s/.*request_time.://" | sed "s/,.*//" | sed "s/['\" ]//g");
            if [ "$RESPONSE_TIME_LIST" == "" ]; then MEAN=0; MEDIAN=0; else RESULT=($(printf '%s ' $RESPONSE_TIME_LIST | datamash mean 1 median 1)); MEAN=${RESULT[0]}; MEDIAN=${RESULT[1]}; fi;
            NUM_OF_NGINX_ABNORMAL_LOG=$(cat /log/nginx_access.log 2>/dev/null | grep $LAST_POINT | grep "status" | wc -l);
            NUM_OF_API_MONITOR_ABNORMAL_LOG=$(grep "error_code" /log/monitor.txt | wc -l);
            echo '{"time":"'$LAST_POINT'","count":'$NUM_OF_LOG',"median":'$MEDIAN',"nginx_abnormal_count":'$NUM_OF_NGINX_ABNORMAL_LOG',"api_monitor_abnormal_count":'$NUM_OF_API_MONITOR_ABNORMAL_LOG'}' >> /log/nginx_access_per_hour.log;
        fi;
        sleep 1;
    done
) &

# --- nginx 접근 로그 카운트 (background) ---
(
    while [ 1 -eq 1 ]; do
        total=`cat /log/nginx_access.log 2>/dev/null | wc -l`;
        success=`grep '"status": "2[0-9][0-9]"' /log/nginx_access.log 2>/dev/null | wc -l`;
        echo '{"total_count":'${total}',"success_count":'${success}'}' > /log/nginx_count.json;
        sleep 1;
    done
) &

# --- nginx 재시작 (에러 숨김) ---
service nginx restart > /dev/null 2>&1 || true

# --- 배포 그래프 로그 (background) ---
echo 'run pod deployment graph log'
python3 /addlib/history.py --deployment_worker_id "$DEPLOYMENT_WORKER_ID" --interval 600 --search_type range --update_time 10 &
python3 /addlib/history.py --deployment_worker_id "$DEPLOYMENT_WORKER_ID" --interval 1   --search_type live  --update_time 1 &

# --- 로그 출력 (background) ---
(
  while true; do
    if [ -f /log/dashboard_history.json ]; then
      LOG="[worker/dashboard_history] $(cat /log/dashboard_history.json)"
      echo "$LOG"
    fi

    if [ -f /log/dashboard_live_history.json ]; then
      LOG="[worker/dashboard_live_history] $(cat /log/dashboard_live_history.json)"
      echo "$LOG"
    fi

    if [ -f /log/nginx_count.json ]; then
      LOG="[worker/nginx_count] $(cat /log/nginx_count.json)"
      echo "$LOG"
    fi

    if [ -f /log/nginx_access_per_hour.log ]; then
      LOG="[worker/nginx_access_per_hour] $(cat /log/nginx_access_per_hour.log)"
      echo "$LOG"
    fi

    sleep 1
  done
) &

# --- 유저 코드 실행 ---
if [ "$DEPLOYMENT_MODEL_TYPE" != "custom" ]; then
    python3 /addlib/built_in_model_download.py
fi
echo 'DEPLOYMENT RUNCODE START'
$RUN_CODE

# --- 종료 방지 ---
exec sleep infinity
