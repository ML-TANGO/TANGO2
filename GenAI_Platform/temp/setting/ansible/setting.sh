#!/bin/bash
ansible-playbook -i conf/inventory.ini haproxy.yml -vv

# 로그 # -v -vv -vvv 
# vvv: 로그 상세

# ansible all -i inventory -m ping

