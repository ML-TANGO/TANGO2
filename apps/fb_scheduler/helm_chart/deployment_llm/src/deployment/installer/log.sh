#!/bin/bash
while true; do

    if [ -f /log/dashboard_history.json ]; then
        LOG="[worker/dashboard_history] $(cat /log/dashboard_history.json)";
        echo $LOG
    fi

    if [ -f /log/dashboard_live_history.json ]; then
        LOG="[worker/dashboard_live_history] $(cat /log/dashboard_live_history.json)";
        echo $LOG;
    fi

    if [ -f /log/nginx_count.json ]; then
        LOG="[worker/nginx_count] $(cat /log/nginx_count.json)"
        echo $LOG;
    fi

    if [ -f /log/nginx_access_per_hour.log ]; then
        LOG="[worker/nginx_access_per_hour] $(cat /log/nginx_access_per_hour.log )";
        echo $LOG;
    fi

    sleep 1;
done