#!/bin/bash
set -e # Immediate exit if error occurrs
sudo -v # Get sudo permission

# unzip | wget | cockpit | tree | nfs-common | nfs-server | dpkg-dev | ansible | make==4.2.1 | gcc==9.4.0 | g++==9.4.0 | haproxy==2.0.31-0ubuntu0.2 


. ../variables.sh
OFFLINE=$1  # ./installer offline
INSTALL_TYPE=$2  # install/remove

packages_ubuntu=("unzip" "wget" "sshpass" "tree" "dpkg-dev" "nfs-common" "nfs-server" "net-tools" "openssl" \
                "make" "gcc" "g++" "haproxy" \
                "ansible" "cockpit" "software-properties-common" \
)
    
# packages_ubuntu=("unzip" "wget" "sshpass" "tree" "dpkg-dev" "nfs-common" "nfs-server" \
#             "make=4.2.1-1.2" "gcc=4:9.3.0-1ubuntu2" "g++=4:9.3.0-1ubuntu2" "haproxy=2.0.31-0ubuntu0.2" \
#             "ansible=5.10.0-1ppa~${OS_CODE_NAME}" "cockpit")
    

# ansible 설정 관련 tutorial (https://www.digitalocean.com/community/tutorials/how-to-install-and-configure-ansible-on-ubuntu-20-04#step-2-setting-up-the-inventory-file)

if [[ "$OS" == *"Ubuntu"* ]]; then
    if [[ $INSTALL_TYPE == "install" ]]; then
        echo -e "${YELLOW}====================${CLEAR}"
        echo -e "${YELLOW}[Installer] default ${CLEAR}"
        echo -e "${YELLOW}====================${CLEAR}"
        sudo apt update
        
        if [[ $OFFLINE != "offline" ]]; then
            sudo apt-add-repository -y ppa:ansible/ansible
            sudo apt update
        fi
        
        for package in "${packages_ubuntu[@]}"; do
            echo -e "${YELLOW}[Install] $package ${CLEAR}"
            sudo apt install -y -qq --show-progress $package
        done
        
        # cockpit configuration
        echo -e "${YELLOW}[INFO] cockpit configuration ${CLEAR}"
        sudo mkdir /etc/systemd/system/cockpit.socket.d
        sudo echo "[Socket]" > /etc/systemd/system/cockpit.socket.d/listen.conf
        sudo echo "ListenStream=" >> /etc/systemd/system/cockpit.socket.d/listen.conf
        sudo echo "ListenStream=9999" >> /etc/systemd/system/cockpit.socket.d/listen.conf
        sudo systemctl daemon-reload
        sudo systemctl restart cockpit.socket
        echo

        # nfs-server configuration
        echo -e "${YELLOW}[INFO] nfs-server configuration ${CLEAR}"
        sudo systemctl start nfs-server
        sudo systemctl enable nfs-server
        echo
        
    elif [[ $INSTALL_TYPE == "remove" ]]; then
        echo -e "${YELLOW}====================${CLEAR}"
        echo -e "${YELLOW}[Remove] default ${CLEAR}"
        echo -e "${YELLOW}====================${CLEAR}"
        echo

        for package in "${packages_ubuntu[@]}"; do
            echo -e "${YELLOW}[Remove] $package ${CLEAR}"
            sudo apt remove -y -q --show-progress $package
        done

        echo -e "${YELLOW}[INFO] apt autoremove & autoclean ${CLEAR}"
        echo
        sudo apt autoremove -y
        sudo apt autoclean -y
    fi

elif [[ "$OS" == *"CentOS"* ]]; then
    #TODO: ansible 설치 추가 + 미리 python 설치 필요
    echo CentOS
    yum -y install cockpit
    yum install -y nfs-utils
    yum install -y unzip wget make gcc g++ haproxy sshpass
    
    # haproxy configuration
    if [ -e "/etc/haproxy/haproxy.cfg" ]; then
        mv /etc/haproxy/haproxy.cfg /etc/haproxy/haproxy_backup.cfg
    fi

    # cockpit configuration
    systemctl enable --now cockpit.socket

    # nfs-server configuration
    systemctl start nfs-server
    systemctl enable nfs-server
fi