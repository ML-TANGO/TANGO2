#!/bin/bash

helm uninstall -n jonathan-mariadb mariadb-init

helm install -n jonathan-mariadb mariadb-init mariadb-init/ -f values.yaml