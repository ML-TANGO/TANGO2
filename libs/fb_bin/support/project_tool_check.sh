#!/bin/bash

# apt가 설치되어 있는지 확인
if ! command -v apt &> /dev/null
then
    echo "apt가 설치되어 있지 않습니다. 설치를 시도합니다."

    # /etc/os-release 파일을 확인하여 배포판 정보를 얻음
    if [[ -f /etc/os-release ]]; then
        . /etc/os-release
        OS=$ID
        VERSION=$VERSION_ID

        # Debian 기반의 시스템인지 확인
        if [[ "$OS" == "debian" || "$OS" == "ubuntu" ]]; then
            echo "Debian 기반의 시스템을 감지했습니다. apt 설치를 시도합니다."

            # dpkg 및 관련 도구가 설치되어 있는지 확인하고, 설치
            if ! command -v dpkg &> /dev/null; then
                echo "dpkg가 설치되어 있지 않습니다. 설치를 시도합니다."
                
                # 필요한 도구 설치
                if [[ "$OS" == "debian" ]]; then
                    sudo apt-get update
                    sudo apt-get install -y dpkg wget
                elif [[ "$OS" == "ubuntu" ]]; then
                    sudo apt-get update
                    sudo apt-get install -y dpkg wget
                else
                    echo "지원되지 않는 배포판입니다. 스크립트를 종료합니다."
                    exit 1
                fi
            fi

            # apt 설치
            wget http://ftp.de.debian.org/debian/pool/main/a/apt/apt_2.2.4_amd64.deb
            sudo dpkg -i apt_2.2.4_amd64.deb
            sudo apt-get install -f -y

            # apt 설치 확인
            if command -v apt &> /dev/null; then
                echo "apt가 성공적으로 설치되었습니다."
            else
                echo "apt 설치에 실패했습니다."
            fi

        else
            echo "Debian 기반의 시스템이 아닙니다. 스크립트를 종료합니다."
            exit 1
        fi

    else
        echo "/etc/os-release 파일을 찾을 수 없습니다. 시스템 정보를 확인할 수 없습니다."
        exit 1
    fi

else
    echo "apt가 이미 설치되어 있습니다."
fi
