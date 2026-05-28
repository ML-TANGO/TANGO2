{{/*
<<에러 가능성>>
- 맨 처음과 끝에 double quote 확인
- 괄호   - & or ; 로 끝나야함
- 문장끝 - ;, \n 로 끝나야함. 비어있으면 에러
- 주석   - \n로 끝나야함

<<resource_log 파일>>
- 정보 > *_usage.json
- *_usage.json >> *_usage_history.log

sleep infinity 넣으면 error 상태 안됨

install_package - 삭제함 LLM에서는 고정 이미지 사용
*/}}

{{- define "command" -}}
"
{{ include "set_pod_env_path" . }}
{{ include "check_api_running" . }}&
{{ include "install_package" . }}
{{ include "check_required_bin" . }}
{{ include "log_cpu_ram_usage" . }}
{{ include "log_gpu_usage" . }}
{{ include "log_network_usage" . }}
{{ include "log_pod_run_time" . }}
{{ include "log_pod_per_hour_call_count" . }}
{{ include "set_nginx_count" . }} &
service nginx restart;
{{ include "run_pod_deployment_graph_log" . }}
{{ include "run_code" . }}"
{{- end }}


{{- define "command.log" -}}
"{{ include "echo_file_log" . }}"
{{- end -}}

{{- define "run_code" -}}
{{- if eq .index 0 }}
ray start --head --port 6379;
{{- else }}
ray start --address deployment-llm-playground-{ .Values.llm.playground.playground_id }--service-ray:6379;
{{- end }}
cd $JF_DEPLOYMENT_PWD;
echo 'DEPLOYMENT RUNCODE START';
cd /llm;
{{- $file := "" }}
{{- if eq .Values.llm.type "playground" }}
{{- $file = "playground" }}
{{- else if contains .Values.llm.type "embedding" }}
{{- $file = "embedding" }}
{{- else if contains .Values.llm.type "rag" }}
{{- $file = "reranker" }}
{{- end }}
python3 /llm/{{ $file }}.py;
sleep infinity;
{{- end -}}


{{- define "set_pod_env_path" -}}
echo 'export \"PATH=$PATH:/usr/bin/support\"' >> $HOME/.bashrc;
PATH=$PATH:/usr/bin/support;
echo 'export \"AAAA=$PYTHONPATH:/addlib\"' >> $HOME/.bashrc;
PYTHONPATH=$PYTHONPATH:/addlib;
source $HOME/.bashrc;
{{- end -}}

{{- define "check_api_running" -}}
{{/* readinessProbe 사용으로 필요 X??, 로그 확인용도로만 */}}
for i in $(seq 0 999);
do
netstat -nltp | grep :8555 ;
netstat -nltp | grep :18555 2> /dev/null && break;
sleep 1;
done
{{- end -}}

{{- define "check_required_bin" -}}
(
    echo datamash ? $(which datamash) $(datamash --version)
    echo curl ?  $(which curl) $(curl --version)
    echo netstat ? $(which netstat) $(netstat --version)
) > /required_bin_check;
{{- end -}}

{{- define "install_package" -}}
{{/*LLM 이미지 고정 사용*/}}
if pip3 list | grep fastapi; \n
then \n
    echo 'pip pass';
else \n
    pip3 install -U fastapi uvicorn httptools uvloop watchfiles websockets six typing_extensions;
fi;

if apt list --installed | grep nginx; \n
then \n
    echo 'apt pass';
else \n
    apt update;
    DEBIAN_FRONTEND=noninteractive apt install -y nginx;
fi;
{{- end -}}

{{- define "set_nginx_count" -}}
while [ 1 -eq 1 ];
do
total=`cat /log/nginx_access.log 2> /dev/null | wc -l`;
success=`grep '\"status\": \"2[0-9][0-9]\"' /log/nginx_access.log 2> /dev/null | wc -l`;
echo '{\"total_count\":'${total}',\"success_count\":'${success}'}' > /log/nginx_count.json;
sleep 1;
done
{{- end -}}


{{- define "run_pod_deployment_graph_log" -}}
echo 'run pod deployment graph log';
python3 /addlib/history.py --deployment_worker_id {{ .Values.deployment.deploymentWorkerId }} --interval 600 --search_type range --update_time 10 & 
python3 /addlib/history.py --deployment_worker_id {{ .Values.deployment.deploymentWorkerId }} --interval 1 --search_type live --update_time 1 &
{{- end -}}


{{- define "echo_file" -}}
while true; do

if [ -f /log/dashboard_history.json ]; then
LOG=\"[worker/dashboard_history] $(cat /log/dashboard_history.json)\";
echo $LOG;
fi;

if [ -f /log/dashboard_live_history.json ]; then
LOG=\"[worker/dashboard_live_history] $(cat /log/dashboard_live_history.json)\";
echo $LOG;
fi;

if [ -f /log/nginx_count.json ]; then
LOG=\"[worker/nginx_count] $(cat /log/nginx_count.json)\";
echo $LOG;
fi;

if [ -f /log/nginx_access_per_hour.log ]; then
LOG=\"[worker/nginx_access_per_hour] $(cat /log/nginx_access_per_hour.log )\";
echo $LOG;
fi;

sleep 1;
done
{{- end -}}

{{- define "echo_file_log" -}}
while true; do

if [ -f /log/dashboard_history.json ]; then
LOG=\"[worker/dashboard_history] $(cat /log/dashboard_history.json)\";
echo $LOG;
fi;

if [ -f /log/dashboard_live_history.json ]; then
LOG=\"[worker/dashboard_live_history] $(cat /log/dashboard_live_history.json)\";
echo $LOG;
fi;

if [ -f /log/nginx_count.json ]; then
LOG=\"[worker/nginx_count] $(cat /log/nginx_count.json)\";
echo $LOG;
fi;

if [ -f /log/nginx_access_per_hour.log ]; then
LOG=\"[worker/nginx_access_per_hour] $(cat /log/nginx_access_per_hour.log )\";
echo $LOG;
fi;

sleep 1;
done;
{{- end -}}




{{- define "log_pod_run_time" -}}
(
    #========= log file: pod runtime ========= \n

    format=\"+%Y-%m-%d %H:%M:%S\";
    old_start_time=$(cat /log/pod_run_time.json  2>/dev/null  | sed 's/,.*//g'  | sed 's/^{ \"start_time\": //g'  | sed 's/\"//g');                             

    if [ \"$old_start_time\" == \"\" ] \n
    then \n
        start_time=$(date \"$format\");
    else \n
        start_time=$old_start_time;
    fi \n

    while [ 1 -eq 1 ]; do \n
        current_time=$(date \"$format\");
        echo '{ \"start_time\": \"'$start_time'\", \"end_time\": \"'$current_time'\" }' > /log/pod_run_time.json;
        sleep 1;
    done \n
) &
{{- end -}}


{{- define "log_pod_per_hour_call_count" -}}
{{/*
    # 시간당 Call Count + Response Time 측정을 위한 스크립트
    # Worker마다 실행하며 매 시간마다 특정 파일에 {"time":"2021-12-11T08","count":111,"median":333} 와 같은 값이 쌓임
    # Deployment에서는 워커마다 있는 해당 파일을 읽은 후 "time"을 순차정렬하며 (중간에 빈 값은 0으로 ? ) 
    # 읽은 파일 전체에서 가장 높은 time 기준으로 24개의 아이탬을 내려주기?
*/}}
(
    #========= log file:  ========= \n

    DATE_FORMAT=\"+%Y-%m-%dT%H\";
    DATE_FORMAT2=\"+%Y-%m-%d %H\"
    NGINX_LOG_FILE=/log/nginx_access.log;
    API_MONITOR_LOG_FILE=/log/monitor.txt;
    NUM_OF_LOG_PER_HOUR_FILE=/log/nginx_access_per_hour.log;
    LAST_POINT=$(date $DATE_FORMAT);
    LAST_POINT2=$(date \"$DATE_FORMAT2\");

    while [ 1 -eq 1 ] \n
    do \n
        POINT=$(date $DATE_FORMAT);
        POINT2=$(date \"$DATE_FORMAT2\");

        if [ \"$LAST_POINT\" != \"$POINT\" ] \n
        then \n

            # POINT CHANGE -> LAST UPDATE \n
            NUM_OF_LOG=$(cat $NGINX_LOG_FILE 2> /dev/null | grep $LAST_POINT | wc -l);

            # RESPONSE TIME \n
            RESPONSE_TIME_LIST=$(cat $NGINX_LOG_FILE 2> /dev/null | grep $LAST_POINT | sed \"s/.*request_time.://\" | sed \"s/,.*//\" | sed \"s/['\\\" ]//g\");
            # echo $RESPONSE_TIME_LIST \n

            if [ \"$RESPONSE_TIME_LIST\" == \"\" ] \n
            then \n
                # SKIP \n
                MEAN=0;
                MEDIAN=0;
            else \n
                RESULT=($(printf '%s ' $RESPONSE_TIME_LIST | datamash mean 1 median 1));
                MEAN=${RESULT[0]};
                MEDIAN=${RESULT[1]};
                if [ \"$MEDIAN\" == \"\" ] \n
                then \n
                    MEDIAN=0;
                fi \n
            fi \n

            NUM_OF_NGINX_ABNORMAL_LOG=$(cat $NGINX_LOG_FILE 2> /dev/null | grep $LAST_POINT | grep [\\\"]status[\\\"' ':]*[01456789][0-9]*\\\" | wc -l);
            # echo \"NUM_OF_ABBORMAL\", $NUM_OF_NGINX_ABNORMAL_LOG \n
            NUM_OF_API_MONITOR_ABNORMAL_LOG=$(cat $API_MONITOR_LOG_FILE 2> /dev/null | grep \"$LAST_POINT2\" | grep \"error_code\"  | wc -l);                
            
            # echo \"NUM_OF_ABNORMAL2\", $NUM_OF_API_MONITOR_ABNORMAL_LOG \n
            # echo \"LAST UPDATE\" \n
        
            POINT_FORM='\"time\":\"'\"$LAST_POINT\"'\"';
            NUM_OF_CALL_LOG_FORM='\"count\":'$NUM_OF_LOG;
            MEDIAN_LOG_FORM='\"median\":'$MEDIAN;
            NUM_OF_NGINX_ABNORMAL_LOG_FORM='\"nginx_abnormal_count\":'$NUM_OF_NGINX_ABNORMAL_LOG;
            NUM_OF_API_MONITOR_ABNORMAL_LOG_FORM='\"api_monitor_abnormal_count\":'$NUM_OF_API_MONITOR_ABNORMAL_LOG;
                
            sed -i 's/{'\"$POINT_FORM\"'.*/{'\"$POINT_FORM\"','\"$NUM_OF_CALL_LOG_FORM\"','\"$MEDIAN_LOG_FORM\"',' \"$NUM_OF_NGINX_ABNORMAL_LOG_FORM\"','\"$NUM_OF_API_MONITOR_ABNORMAL_LOG_FORM\"'}/' $NUM_OF_LOG_PER_HOUR_FILE;

            LAST_POINT=$POINT;
            LAST_POINT2=$POINT2;
        fi \n

        # echo RUN $POINT \n
        NUM_OF_LOG=$(cat $NGINX_LOG_FILE 2> /dev/null | grep $POINT | wc -l);

        # RESPONSE TIME \n
        RESPONSE_TIME_LIST=$(cat $NGINX_LOG_FILE 2> /dev/null | grep $POINT | sed \"s/.*request_time.://\" | sed \"s/,.*//\" | sed \"s/['\\\" ]//g\");

        if [ \"$RESPONSE_TIME_LIST\" == \"\" ] \n
        then\n
            echo \"@@@@@@@@@#! SKIP\";
            MEAN=0;
            MEDIAN=0;
        else\n
            RESULT=($(printf '%s\n' $RESPONSE_TIME_LIST | datamash mean 1 median 1));
            MEAN=${RESULT[0]};
            MEDIAN=${RESULT[1]};
            echo \"?????\" $MEDIAN;
            echo \"?????\" $RESPONSE_TIME_LIST;
            if [ \"$MEDIAN\" == \"\" ] \n
            then \n
                MEDIAN=0;
            fi \n
        fi \n

        # Abnormal COUNT \n
        NUM_OF_NGINX_ABNORMAL_LOG=$(cat $NGINX_LOG_FILE 2> /dev/null | grep $POINT | grep [\\\"]status[\\\"' ':]*[01456789][0-9]*\\\" | wc -l);
        # echo \"NUM_OF_ABBORMAL\", $NUM_OF_NGINX_ABNORMAL_LOG \n
        NUM_OF_API_MONITOR_ABNORMAL_LOG=$(cat $API_MONITOR_LOG_FILE 2> /dev/null | grep \"$POINT2\" | grep \"error_code\"  | wc -l);
        # echo \"NUM_OF_ABNORMAL2\", $NUM_OF_API_MONITOR_ABNORMAL_LOG, $POINT2 \n

        POINT_FORM='\"time\":\"'\"$POINT\"'\"';
        NUM_OF_CALL_LOG_FORM='\"count\":'$NUM_OF_LOG;
        MEDIAN_LOG_FORM='\"median\":'$MEDIAN;
        NUM_OF_NGINX_ABNORMAL_LOG_FORM='\"nginx_abnormal_count\":'$NUM_OF_NGINX_ABNORMAL_LOG;
        NUM_OF_API_MONITOR_ABNORMAL_LOG_FORM='\"api_monitor_abnormal_count\":'$NUM_OF_API_MONITOR_ABNORMAL_LOG;

        # echo $LOG_FORM \n
        cat $NUM_OF_LOG_PER_HOUR_FILE | grep $POINT > /dev/null;
        if [ $? -gt 0 ] \n
        then \n
            # echo CREATE ITEM \n
            echo '{'$POINT_FORM,$NUM_OF_CALL_LOG_FORM,$MEDIAN_LOG_FORM,$NUM_OF_NGINX_ABNORMAL_LOG_FORM,$NUM_OF_API_MONITOR_ABNORMAL_LOG_FORM'}' >> $NUM_OF_LOG_PER_HOUR_FILE;
        else
            # echo UPDATE ITEM \n
            sed -i 's/{'\"$POINT_FORM\"'.*/{'\"$POINT_FORM\"','\"$NUM_OF_CALL_LOG_FORM\"','\"$MEDIAN_LOG_FORM\"','\"$NUM_OF_NGINX_ABNORMAL_LOG_FORM\"','\"$NUM_OF_API_MONITOR_ABNORMAL_LOG_FORM\"'}/' $NUM_OF_LOG_PER_HOUR_FILE;
        fi

        sleep 1;
    done \n
) > /per_hour_log 2> /per_hour_log &
{{- end -}}


{{/* ================= resource log ================= */}}

{{- define "log_cpu_ram_usage" -}}
(
    nproc=$(nproc);
    period=$(cat /sys/fs/cgroup/cpu/cpu.cfs_period_us 2> /dev/null );
    quota=$(cat /sys/fs/cgroup/cpu/cpu.cfs_quota_us 2> /dev/null );
    podnproc=$(awk '{print $1/$2}' <<<\"$quota $period\");
    
    touch /resource_log/resource_usage.json;
    chmod 755 /resource_log/resource_usage.json;

    while [ 1 -eq 1 ]; do\n
        mem_usage=$(cat /sys/fs/cgroup/memory/memory.usage_in_bytes 2> /dev/null );
        mem_limit=$(cat /sys/fs/cgroup/memory/memory.limit_in_bytes 2> /dev/null );

        tstart=$(date +%s%N);
        cstart=$(cat /sys/fs/cgroup/cpu/cpuacct.usage 2> /dev/null );
        sleep 1;
        tstop=$(date +%s%N);
        cstop=$(cat /sys/fs/cgroup/cpu/cpuacct.usage 2> /dev/null );
        cpu_usage=$(awk '{print ($1-$2)/($3-$4)*100 }' <<<\"$cstop $cstart $tstop $tstart\"  2> /dev/null );
        timestamp=$(date +%s);

        cpu_usage_on_node=$(awk '{print $1/$2}' <<<\"$cpu_usage $nproc\"  2> /dev/null );
        cpu_usage_on_pod=$(awk '{print $1/$2}' <<<\"$cpu_usage $podnproc\"  2> /dev/null );

        mem_usage_per=$(awk \"BEGIN {print $mem_usage / $mem_limit * 100}\"  2> /dev/null );
        mem_usage_per=$(printf \"%.4f\" $mem_usage_per);                                
        echo '{\"cpu_usage_on_node\":'$cpu_usage_on_node',\"cpu_usage_on_pod\":'$cpu_usage_on_pod',\"mem_usage\" :'$mem_usage',\"mem_limit\":'$mem_limit',\"mem_usage_per\":'$mem_usage_per',\"timestamp\":'$timestamp',\"cpu_cores_on_pod\":'$podnproc'}' > /resource_log/resource_usage.json;
        cat /resource_log/resource_usage.json >> /resource_log/resource_usage_history.log;

        HISTORY_DATA_LEN=$(cat /resource_log/resource_usage_history.log | wc -l);
        MAX_LEN=300;

        if [ $HISTORY_DATA_LEN -gt 600 ] \n
        then\n
            DEL_LEN=$(expr $HISTORY_DATA_LEN - $MAX_LEN);
            sed -i '1,'$DEL_LEN'd' /resource_log/resource_usage_history.log;
        fi
    done
) &
{{- end -}}


{{/*nvidia-smi가 컨테이너에서 실행되어야 함*/}}
{{- define "log_gpu_usage" -}}
(
    #========= log file: gpu ========= \n

    # nvidia-smi 명령어가 존재하는지 확인
    if ! command -v nvidia-smi &> /dev/null; then
        echo "nvidia-smi command not found. Skipping GPU logging.";
        exit 0;
    fi

    nvidia_gpu_count=$(nvidia-smi -L | wc -l);
    echo gpu_count $nvidia_gpu_count;

    nvidia-smi >> /dev/null;
    nvidia_smi_result=$?;
    echo $nvidia_smi_result;

    re='^[ ]*?[0-9]+([.][0-9]+)?$';

    while [ $nvidia_smi_result -eq 0 ] && [ $nvidia_gpu_count -gt 0 ]; do\n
        nvidia_log=$(nvidia-smi --format=csv,noheader,nounits --query-gpu=utilization.gpu,utilization.memory,memory.free,memory.used,memory.total | sed -e \"s/Insufficient Permissions/Insufficient_Permissions/g\" | tr \", \" \" \");
        timestamp=$(date +%s);
        
        SAVEIFS=$IFS;
        IFS=$'\n';
        nvidia_logs=($nvidia_log);
        IFS=$SAVEIFS;

        nvidia_log_jsons=();

        for (( i=0; i<${#nvidia_logs[@]}; i++ )) \n
        do \n
            array=(${nvidia_logs[$i]});

            util_gpu=${array[0]};
            util_memory=${array[1]};
            memory_free=${array[2]};
            memory_used=${array[3]};
            memory_total=${array[4]};

            if ! [[ $util_gpu =~ $re ]] ; then \n
                util_gpu='\"'$util_gpu'\"';
            fi \n
            if ! [[ $util_memory =~ $re ]] ; then \n
                util_memory='\"'$util_memory'\"';
            fi \n
            if ! [[ $memory_free =~ $re ]] ; then \n
                memory_free='\"'$memory_free'\"';
            fi \n
            if ! [[ $memory_used =~ $re ]] ; then \n
                memory_free='\"'$memory_free'\"';
            fi \n
            if ! [[ $memory_used =~ $re ]] ; then \n
                memory_used='\"'$memory_used'\"';
            fi \n
            if ! [[ $memory_total =~ $re ]] ; then \n
                memory_total='\"'$memory_total'\"';
            fi \n

            if [ $i -eq 0 ] \n
            then \n
                nvidia_log_jsons[$i]='{ \"'$i'\": { \"util_gpu\": '$util_gpu', \"util_memory\": '$util_memory', \"memory_free\": '$memory_free', \"memory_used\": '$memory_used', \"memory_total\": '$memory_total', \"timestamp\": '$timestamp' }';
            else \n
                nvidia_log_jsons[$i]=', \"'$i'\": { \"util_gpu\": '$util_gpu', \"util_memory\": '$util_memory', \"memory_free\": '$memory_free', \"memory_used\": '$memory_used', \"memory_total\": '$memory_total', \"timestamp\": '$timestamp' }';
            fi \n
        done \n
        nvidia_log_jsons[$i]='}';

        echo ${nvidia_log_jsons[@]} > /resource_log/gpu_usage.json \n
        cat /resource_log/gpu_usage.json >> /resource_log/gpu_usage_history.log \n
        sleep 1;

        HISTORY_DATA_LEN=$(cat /resource_log/gpu_usage_history.log | wc -l);
        MAX_LEN=300;

        if [ $HISTORY_DATA_LEN -gt 600 ] \n
        then \n
            DEL_LEN=$(expr $HISTORY_DATA_LEN - $MAX_LEN);
            sed -i '1,'$DEL_LEN'd' /resource_log/gpu_usage_history.log;
        fi \n
    done
) &
{{- end -}}



{{- define "log_network_usage" -}}
{{/*network usage log ???*/}}
(
    #========= log file: /resource_log/network_usage_history.log ========= \n

    DEFAULT_ETH=eth0;
    while [ 1 -eq 1 ];
    do \n
        R1=`cat /sys/class/net/$DEFAULT_ETH/statistics/rx_bytes`;
        T1=`cat /sys/class/net/$DEFAULT_ETH/statistics/tx_bytes`;

        sleep 1;

        R2=`cat /sys/class/net/$DEFAULT_ETH/statistics/rx_bytes`;
        T2=`cat /sys/class/net/$DEFAULT_ETH/statistics/tx_bytes`;
        TXBytes=`expr $T2 - $T1`;
        RXBytes=`expr $R2 - $R1`;

        timestamp=$(date +%s);
        echo '{\"tx_bytes\":'$TXBytes',\"rx_bytes\":'$RXBytes',\"@TIMESTAMP_KEY\":'$timestamp'}' > /resource_log/network_usage.json;

        cat /resource_log/network_usage.json >>  /resource_log/network_usage_history.log;

        HISTORY_DATA_LEN=$(cat /resource_log/network_usage_history.log | wc -l);
        MAX_LEN=300;

        if [ $HISTORY_DATA_LEN -gt 600 ] \n
        then \n
            DEL_LEN=$(expr $HISTORY_DATA_LEN - $MAX_LEN);
            sed -i '1,'$DEL_LEN'd' /resource_log/network_usage_history.log;
        fi \n
    done
)&
{{- end -}}

{{- define "set_nginx_config" -}}
{{/*worker_processes 부분 추가 안함 -> TODO*/}}
cp -f /etc/nginx_ex/nginx.conf /etc/nginx/;
cp -f /etc/nginx_ex/api.conf /etc/nginx/conf.d/;

sed 's/@DEPLOYMENT_NGINX_DEFAULT_PORT/18555/' -i /etc/nginx/conf.d/api.conf;
sed 's/@DEPLOYMENT_API_DEFAULT_PORT/8555/' -i /etc/nginx/conf.d/api.conf;

sed 's/@NGINX_ACCESS_LOG_DEFAULT_PATH/\\/log\\/nginx_access.log/' -i /etc/nginx/conf.d/api.conf;
sed 's/@NGINX_ERROR_LOG_DEFAULT_PATH/\\/log\\/nginx_error.log/' -i /etc/nginx/conf.d/api.conf;

service nginx restart;
{{- end -}}
