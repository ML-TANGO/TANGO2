#!/bin/bash
set -e # Immediate exit if error occurrs
sudo -v # Get sudo permission

. ../variables.sh
OFFLINE=$1  # ./installer offline
INSTALL_TYPE=$2  # install/remove

packages_ubuntu=("nvidia-driver-535-server")

if [[ "$OS" == *"Ubuntu"* ]]; then
    if [[ $INSTALL_TYPE == "install" ]]; then
        echo -e "${YELLOW}==========================${CLEAR}"
        echo -e "${YELLOW}[Installer] nvidia-driver ${CLEAR}"
        echo -e "${YELLOW}==========================${CLEAR}"
        echo
        sudo apt update

        # [Nvidia driver]
        for package in $packages_ubuntu; do
            echo -e "${YELLOW}[Install] $package ${CLEAR}"
            sudo apt install -y -qq --show-progress $package
        done
        
        echo -e "${YELLOW}[INFO] nvidia-smi ${CLEAR}"
        nvidia-smi

        # Ask reboot to apply nvidia-driver
        while true; do
            read -p "Do you want to reboot for the nvidia-driver to take effect? (y / n) " input

            if [[ "${input}" =~ ^[yY](es)?$ ]]; then
                echo "Rebooting for the nvidia-driver"
            reboot now
                break
            elif [[ "${input}" =~ ^[nN](o)?$ ]]; then
                echo "Cancel reboot"
                break
            else
                echo "Input was incorrect. Please answer (y/yes) or (n/no)"
            fi
        done
        
    elif [[ $INSTALL_TYPE == "remove" ]]; then
        echo -e "${YELLOW}======================${CLEAR}"
        echo -e "${YELLOW}[Remove] nvidia-driver ${CLEAR}"
        echo -e "${YELLOW}======================${CLEAR}"
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


