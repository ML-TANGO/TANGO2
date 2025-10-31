#!/bin/bash
set -e # Immediate exit if error occurrs
sudo -v # Get sudo permission

. ../variables.sh
OFFLINE=$1  # ./installer offline
INSTALL_TYPE=$2  # install/remove

packages_ubuntu_docker=("curl" "gnupg" \
                        "ca-certificates" \
                        "docker-ce=5:24.0.7-1~ubuntu.20.04~${OS_CODE_NAME}" \
                        "docker-ce-cli=5:24.0.7-1~ubuntu.20.04~${OS_CODE_NAME}" \
                        "containerd.io=1.6.24-1" \
                        "docker-buildx-plugin=0.11.2-1~ubuntu.20.04~${OS_CODE_NAME}" \
                        "docker-compose-plugin=2.20.2-1~ubuntu.20.04~${OS_CODE_NAME}" \
                        "runc"
)
packages_ubuntu_nvidia=("nvidia-docker2=2.13.0-1")  # Nvidia container toolkit

if [[ "$OS" == *"Ubuntu"* ]]; then
    if [[ $INSTALL_TYPE == "install" ]]; then
        echo -e "${YELLOW}===================${CLEAR}"
        echo -e "${YELLOW}[Installer] docker ${CLEAR}"
        echo -e "${YELLOW}===================${CLEAR}"
        echo
        sudo apt update

        # Update keyrings
        if [[ $OFFLINE != "offline" ]]; then
            curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
            sudo chmod a+r /etc/apt/keyrings/docker.gpg
            # Add the repository to Apt sources:
            echo \
            "deb [arch="$(dpkg --print-architecture)" signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
            "$(. /etc/os-release && echo "$VERSION_CODENAME")" stable" | \
            sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
            sudo apt update
        fi
        

        # [Install] packages (docker)
        sudo install -m 0755 -d /etc/apt/keyrings
        
        for package in $packages_ubuntu_docker; do
            echo -e "${YELLOW}[Install] $package ${CLEAR}"
            sudo apt install -y -qq --show-progress $package
        done

        # Update apt source.list
        if [[ $OFFLINE != "offline" ]]; then
            curl https://get.docker.com | sh && sudo systemctl --now enable docker
            distribution=$(. /etc/os-release;echo $ID$VERSION_ID) \
                && curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add - \
                && curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list
            sudo apt update
        fi
        
        # [Install] packages (Nvidia docker)
        for package in $packages_ubuntu_nvidia; do
            echo -e "${YELLOW}[Install] $package ${CLEAR}"
            sudo apt install -y -qq --show-progress $package
        done

        # Configure containerd 
        echo -e "${YELLOW}[INFO] Configure containerd ${CLEAR}"
        sudo mkdir -p /etc/containerd
        cp ./containerd_config.toml /etc/containerd/config.toml
        # containerd config default > /etc/containerd/config.toml

        systemctl enable containerd
        systemctl daemon-reload
        systemctl restart containerd
        systemctl status containerd

        # Restart docker service
        echo -e "${YELLOW}[INFO] restart docker ${CLEAR}"
        sudo systemctl daemon-reload
        sudo systemctl restart docker
        sudo systemctl enable docker
        echo

    elif [[ $INSTALL_TYPE == "remove" ]]; then
        echo -e "${YELLOW}================${CLEAR}"
        echo -e "${YELLOW}[Remove] docker ${CLEAR}"
        echo -e "${YELLOW}================${CLEAR}"
        echo

        for package in "${packages_ubuntu_docker[@]}"; do
            echo -e "${YELLOW}[Remove] $package ${CLEAR}"
            sudo apt remove -y -q --show-progress $package
        done

        for package in "${packages_ubuntu_nvidia[@]}"; do
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
    # https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/1.8.1/install-guide.html
fi


