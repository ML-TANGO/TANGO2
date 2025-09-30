#!/bin/bash
set -e # Immediate exit if error occurrs
sudo -v # Get sudo permission

. ../variables.sh
OFFLINE=$1  # ./installer online/offline
INSTALL_TYPE=$2  # ./installer online/offline install/remove

packages_ubuntu=("helm=3.13.1-1" "apt-transport-https")

if [[ "$OS" == *"Ubuntu"* ]]; then
    if [[ $INSTALL_TYPE == "install" ]]; then
        echo -e "${YELLOW}==========================${CLEAR}"
        echo -e "${YELLOW}[Installer] helm ${CLEAR}"
        echo -e "${YELLOW}==========================${CLEAR}"
        sudo apt update

        if [[ $OFFLINE != "offline" ]]; then
            curl https://baltocdn.com/helm/signing.asc | gpg --dearmor | sudo tee /usr/share/keyrings/helm.gpg > /dev/null
            echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/helm.gpg] https://baltocdn.com/helm/stable/debian/ all main" | sudo tee /etc/apt/sources.list.d/helm-stable-debian.list
            sudo apt update
        fi

        # [Helm]
        for package in $packages_ubuntu; do
            echo -e "${YELLOW}[Install] $package ${CLEAR}"
            sudo apt install -y -qq --show-progress $package
        done
        
    elif [[ $INSTALL_TYPE == "remove" ]]; then
        echo -e "${YELLOW}==============${CLEAR}"
        echo -e "${YELLOW}[Remove] helm ${CLEAR}"
        echo -e "${YELLOW}==============${CLEAR}"

        for package in "${packages_ubuntu[@]}"; do
            echo -e "${YELLOW}[Remove] $package ${CLEAR}"
            sudo apt remove -y -q --show-progress $package
        done

        echo -e "${YELLOW}[INFO] apt autoremove & autoclean ${CLEAR}"
        sudo apt autoremove
        sudo apt autoclean
        echo
    fi

elif [[ "$OS" == *"CentOS"* ]]; then
    echo
fi
