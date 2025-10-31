#!/bin/bash

. ../variables.sh
set -e # Immediate exit if error occurrs
sudo -v # Get sudo permission

OFFLINE=$1  # ./installer offline
INSTALL_TYPE=$2  # install/remove

packages_ubuntu=("kubelet=1.27.4-00" "kubeadm=1.27.4-00" "kubectl=1.27.4-00")
    

if [[ "$OS" == *"Ubuntu"* ]]; then
    if [[ $INSTALL_TYPE == "install" ]]; then
        echo -e "${YELLOW}=======================${CLEAR}"
        echo -e "${YELLOW}[Installer] kubernetes ${CLEAR}"
        echo -e "${YELLOW}=======================${CLEAR}"
        echo
        sudo apt update
        
        if [[ $OFFLINE != "offline" ]]; then
            # Download the public signing key for the Kubernetes package repositories
            curl -fsSL https://pkgs.k8s.io/core:/stable:/v1.27/deb/Release.key | sudo gpg --dearmor -o /etc/apt/keyrings/kubernetes-apt-keyring.gpg
            # Add teh appropriate Kubernetes apt repository
            echo 'deb [signed-by=/etc/apt/keyrings/kubernetes-apt-keyring.gpg] https://pkgs.k8s.io/core:/stable:/v1.27/deb/ /' | sudo tee /etc/apt/sources.list.d/kubernetes.list
            sudo apt update
            # curl -s https://packages.cloud.google.com/apt/doc/apt-key.gpg | sudo apt-key add -
            # echo "deb https://apt.kubernetes.io/ kubernetes-xenial main" | sudo tee /etc/apt/sources.list.d/kubernetes.list
            # sudo apt update
        fi
        
        # cri-tools

        # VERSION="v1.28.0"
        # wget https://github.com/kubernetes-sigs/cri-tools/releases/download/$VERSION/crictl-$VERSION-linux-amd64.tar.gz
        # sudo tar zxvf crictl-$VERSION-linux-amd64.tar.gz -C /usr/local/bin
        # rm -f crictl-$VERSION-linux-amd64.tar.gz
        
        # Disable swap - 1 (permanently)
        sudo swapoff -a
        sed -ri '/\sswap\s/s/^#?/#/' /etc/fstab
        
        # Disable swap - 2 (permanently)
        output=$(systemctl list-unit-files --type swap)
        swap_unit=""

        if [ -n "$output" ]; then
            echo "$output" | awk '{print $1}' | while read line; do
                if [[ $line == *'.swap' ]]; then
                    swap_unit=$line
                    echo -e "${YELLOW}[Swapoff] disable swap ${swap_unit} permanently ${CLEAR}"
                    sudo systemctl mask ${swap_unit}
                fi
            done
            echo -e "${YELLOW}[Swapoff] List unit files ${swap_unit} permanently ${CLEAR}"
            sleep 2
            sudo systemctl list-unit-files --type swap
        else
            echo -e "${YELLOW}[Swapoff] No swap units found. ${CLEAR}"
        fi

        # Install packages
        for package in "${packages_ubuntu[@]}"; do
            echo -e "${YELLOW}[Install] $package ${CLEAR}"
            sudo apt install -y -qq --show-progress $package
        done
        
        # Configure bridge, ipv4 (k8s)
        echo -e "${YELLOW}[Kubernetes] configure bridge, ipv4 ${swap_unit} permanently ${CLEAR}"
        cat <<EOF | sudo tee /etc/modules-load.d/k8s.conf
            overlay
            br_netfilter
EOF
        sudo modprobe overlay
        sudo modprobe br_netfilter

        # 필요한 sysctl 파라미터를 설정하면, 재부팅 후에도 값이 유지된다.
        cat <<EOF | sudo tee /etc/sysctl.d/k8s.conf
        net.bridge.bridge-nf-call-iptables  = 1
        net.bridge.bridge-nf-call-ip6tables = 1
        net.ipv4.ip_forward                 = 1
EOF
        # 재부팅하지 않고 sysctl 파라미터 적용하기
        sudo sysctl --system

        # Prevent package updates (kubelet, kubeadm, kubectl)
        # setting 단계에서 hold 해야 할 듯. 패키지 설치되지 않았을 때에도 hold 진행하기 때문
        # echo -e "${YELLOW}[INFO] Hold k8s packages to prevent unintentional updates ${CLEAR}"
        # Hold packages to prevent unintentional updates
        # sudo apt-mark hold kubelet kubeadm kubectl

        echo -e "${YELLOW}[INFO] restart kubelet ${CLEAR}"
        systemctl enable kubelet
        systemctl stop kubelet
        systemctl start kubelet
        echo

    elif [[ $INSTALL_TYPE == "remove" ]]; then
        echo -e "${YELLOW}====================${CLEAR}"
        echo -e "${YELLOW}[Remove] kubernetes ${CLEAR}"
        echo -e "${YELLOW}====================${CLEAR}"
        echo

        for package in "${packages_ubuntu[@]}"; do
            echo -e "${YELLOW}[Remove] $package ${CLEAR}"
            sudo apt remove -y -q --show-progress $package
        done

        echo -e "${YELLOW}[INFO] apt autoremove & autoclean ${CLEAR}"
        sudo apt autoremove -y
        sudo apt autoclean -y
        echo
    fi

elif [[ "$OS" == *"CentOS"* ]]; then
    echo
fi