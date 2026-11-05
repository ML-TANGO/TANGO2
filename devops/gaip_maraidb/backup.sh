#!/bin/bash
NAMESPACE='jonathan-mariadb'
CONTAINER_NAME='mariadb-galera'
USER='root'
PASSWORD='tango1234@'
DATABASE='msa_jfb'
TIME=$(date -u +"%Y%m%d-utc%H%M")

kubectl get pod -n $NAMESPACE -o name |                      \
xargs -I {} kubectl exec -n $NAMESPACE {} -c $CONTAINER_NAME \
-- bash -c "mkdir -p /bitnami/mariadb/backup;                \
mariadb-dump -u $USER -p$PASSWORD $DATABASE                  \
> /bitnami/mariadb/backup/backup_$TIME.sql"

