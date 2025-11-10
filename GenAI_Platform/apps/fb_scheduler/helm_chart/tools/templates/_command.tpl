{{- define "command" -}}
    {{- if $.Values.offlineMode }}
    # 오프라인 상태일 경우 nexus 설정 적용 
    (
    echo "============================================"
    echo "🗄️  JONATHAN 저장소 설정"
    echo "============================================"
    {{ include "set_debian_repo" . }}
    )
    {{- end }}
    # 학습 도구 실행 시 실행되는 필수 패키지 설치
    {{ include "set_pod_package" . }}
    {{- if eq .index 0 }}
        (
        echo "==================="
        echo "change root password"
        echo "==================="
        cd /support; ./root_password_change.sh '{{ $.Values.tool_password }}'
        );
        {{- if eq $.Values.labels.tool_type "jupyter" }}
            {{ include "jupyter_install" . }}
        {{- else if eq $.Values.labels.tool_type "vscode" }}
            {{ include "vscode_install" . }}
        {{- else if eq $.Values.labels.tool_type "shell" }}
            {{ include "shell_install" . }}
        {{- end }}
    {{- else }}
        while true; do sleep 30; done;
    {{- end }}
{{- end }}


{{- define "set_debian_repo" -}}
    set -e

    echo "APT 기반 시스템 여부 확인..."
    if ! command -v apt-get >/dev/null 2>&1; then
        echo "apt-get이 설치되어 있지 않습니다. 종료합니다."
        exit 1
    fi

    echo "배포판 코드네임 확인 중..."
    if command -v lsb_release >/dev/null 2>&1; then
        codename=$(lsb_release -c -s)
    elif [ -f /etc/os-release ]; then
        codename=$(grep '^VERSION_CODENAME=' /etc/os-release | cut -d '=' -f2)
    fi

    if [ -z "$codename" ]; then
        echo "배포판 코드네임을 찾을 수 없습니다. 종료합니다."
        exit 1
    fi

    echo "배포판 코드네임: $codename"

    # Nexus 설정
    {{- $nexusHost := default "nexus-nexus-repository-manager.jonathan-nexus.svc.cluster.local" $.Values.nexus.hostname }}
    {{- $nexusPort := default "8081" (toString $.Values.nexus.port) }}
    {{- $nexusUrl := printf "http://%s:%s" $nexusHost $nexusPort }}
    {{- if $.Values.nexusPrefix }}
    repo_line="deb {{ $nexusUrl }}/{{ $.Values.nexusPrefix }}/repository/$codename-apt/ $codename main"
    {{- else }}
    repo_line="deb {{ $nexusUrl }}/repository/$codename-apt/ $codename main"
    {{- end }}

    # GPG 키 등록
    apt-key add /root/.apt/acryl_public.gpg.key || {
        echo "GPG 키 등록 실패"
        echo "gnupg 패키지를 설치하세요 ex) apt-get install -y gnupg"
        exit 1
    }
    echo "GPG 키 등록 완료"

    # 저장소 설정
    if [ ! -d /etc/apt/sources.list.d ]; then
        mkdir -p /etc/apt/sources.list.d
    fi

    # 기존 설정 백업
    if [ -f /etc/apt/sources.list.d/acryl.list ]; then
        cp /etc/apt/sources.list.d/acryl.list /etc/apt/sources.list.d/acryl.list.bak
    fi

    # 다른 레포 리스트 파일들 주석 처리
    echo "다른 레포 리스트 파일들을 주석 처리합니다..."
    for file in /etc/apt/sources.list.d/*.{list,sources}; do
        if [ -f "$file" ] && [ "$(basename "$file")" != "acryl.list" ]; then
            echo "주석 처리: $file"
            if [[ "$file" == *.list ]]; then
                sed -i 's/^deb/# deb/g' "$file"
                sed -i 's/^deb-src/# deb-src/g' "$file"
            elif [[ "$file" == *.sources ]]; then
                sed -i 's/^Types: deb/# Types: deb/g' "$file"
                sed -i 's/^URIs:/# URIs:/g' "$file"
                sed -i 's/^Suites:/# Suites:/g' "$file"
                sed -i 's/^Components:/# Components:/g' "$file"
                sed -i 's/^Signed-By:/# Signed-By:/g' "$file"
            fi
        fi
    done

    # /etc/apt/sources.list 파일도 주석 처리
    if [ -f /etc/apt/sources.list ]; then
        echo "주석 처리: /etc/apt/sources.list"
        sed -i 's/^deb/# deb/g' /etc/apt/sources.list
        sed -i 's/^deb-src/# deb-src/g' /etc/apt/sources.list
    fi

    # 새로운 nexus 설정 적용
    echo "$repo_line" > /etc/apt/sources.list.d/acryl.list

    echo "저장소 설정이 완료되었습니다."
{{- end }}

{{- define "set_pod_package" -}}
    {{- if ge (int $.Values.total_device_count) 2 }}
    cd /distributed; ./init.sh;
    cd $JF_HOME
    {{- else }}
    cd /support; ./check_package_installed.sh;
    {{- end }}
{{- end }}


{{- define "jupyter_install" -}}
    (
    # Python 버전 확인
    PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")

    cd $JF_HOME && export SHELL=/bin/bash

    # pip3 설치 및 업그레이드
    {{- if $.Values.offlineMode }}
    python3 /jonathan_tool_packages/get-pip.py --force-reinstall
    {{- else }}
    pip3 --version || (apt-get install -y python3-distutils && curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py && python3 get-pip.py --force-reinstall && rm get-pip.py)
    {{- end }}

    # 환경 변수 갱신
    export PATH=$PATH:~/.local/bin

    # Jupyter가 이미 설치되어 있는지 확인
    if command -v jupyter &> /dev/null
    then
        echo "======================================================"
        echo "Jupyter is already installed. Skipping installation."
        echo "======================================================"
    else
        echo "======================================================"
        echo "Jupyter installation."
        echo "======================================================"
        # Node.js 설치 (최신 LTS 버전)
        {{- if $.Values.offlineMode }}
        apt-get update && apt -y install nodejs gcc g++ make curl git
        {{- else }}
        curl -fsSL https://deb.nodesource.com/setup_lts.x | bash -
        apt-get update && apt -y install nodejs gcc g++ make curl git
        {{- end }}

        # # Yarn GPG 키 추가 및 설치 (최신 버전)
        # curl -sL https://dl.yarnpkg.com/debian/pubkey.gpg | gpg --dearmor | tee /usr/share/keyrings/yarnkey.gpg >/dev/null
        # echo "deb [signed-by=/usr/share/keyrings/yarnkey.gpg] https://dl.yarnpkg.com/debian stable main" | tee /etc/apt/sources.list.d/yarn.list
        # apt-get update && apt-get install -y yarn

        echo "======================================================"
        echo "node version."
        node --version
        # echo "yarn version."
        # yarn --version
        echo "======================================================"


        DEBIAN_FRONTEND=noninteractive apt install -y tzdata
        # jupyter 설치
        pip3 install jupyter-core --no-warn-script-location
        # jupyterlab 설치
        pip3 install jupyterlab --no-warn-script-location
        # jupyterlab-git 설치

        # pip3 install jupyterlab-git --no-warn-script-location
        # ipympl 설치 및 jupyter labextension 설치
        pip3 install ipympl --no-warn-script-location

        {{- if $.Values.offlineMode }}
        mkdir -p /usr/local/share/jupyter/labextensions/
        tar -xvf /jonathan_tool_packages/labextensions.tar --strip-components=1 -C /usr/local/share/jupyter/labextensions/
        {{- else }}
        jupyter labextension install @jupyter-widgets/jupyterlab-manager #jupyter-matplotlib @jupyterlab/git
        {{- end }}

        echo "======================================================"
        echo "Jupyter install success."
        echo "======================================================"
        
    fi
    # 환경 변수 다시 갱신
    source $HOME/.bashrc

    # jupyter 설치 경로 확인
    which jupyter

    # Jupyter Lab 실행
    # jupyter lab clean
    # jupyter lab build
    jupyter lab --allow-root --ip 0.0.0.0 --port={{ $.Values.service.port }} --notebook-dir=$JF_HOME --NotebookApp.base_url=/jupyter/{{ $.Values.pod_name }}-{{ .index }}/ --NotebookApp.allow_origin=*
    ); sleep infinity;
{{- end }}

{{- define "vscode_install" -}}
    (
    echo "==================="
    echo "check package and install code server"
    echo "==================="
    # Locate the code-server executable
    code_server_path=$(which code-server)

    # Check if the code-server executable was found
    # 원하는 버전 설정
    CODE_SERVER_VERSION="4.15.0"

    # 실행 경로 설정
    code_server_path="/usr/bin/code-server"

    # code-server 설치 여부 확인
    if [ -x "$code_server_path" ]; then
        echo "code-server is installed at: $code_server_path"
        $code_server_path --version
    else
        echo "code-server is not installed. Installing version $CODE_SERVER_VERSION..."
        {{- if $.Values.offlineMode }}
        mkdir -p /usr/lib/code-server
        tar -xzf /jonathan_tool_packages/code-server.tar.gz --strip-components=1 -C /usr/lib/code-server
        {{- else }}
            # 아키텍처 확인 (x86_64 또는 arm64)
            ARCH=$(uname -m)
            if [ "$ARCH" = "x86_64" ]; then
                ARCH="amd64"
            elif [ "$ARCH" = "aarch64" ]; then
                ARCH="arm64"
            else
                echo "Unsupported architecture: $ARCH"
                exit 1
            fi

            # /tmp 디렉터리 사용
            cd /tmp || exit 1

            # code-server 다운로드 및 설치
            wget -qO code-server.tar.gz "https://github.com/coder/code-server/releases/download/v${CODE_SERVER_VERSION}/code-server-${CODE_SERVER_VERSION}-linux-${ARCH}.tar.gz"
            
            if [ ! -f "code-server.tar.gz" ]; then
                echo "Download failed. Check network connection or GitHub availability."
                exit 1
            fi
            
            tar -xzf code-server.tar.gz
            rm code-server.tar.gz
            mv "code-server-${CODE_SERVER_VERSION}-linux-${ARCH}" /usr/lib/code-server
        {{- end }}
        ln -s /usr/lib/code-server/bin/code-server /usr/bin/code-server
        echo "code-server $CODE_SERVER_VERSION installed successfully."
        code-server --version
    fi

    ); ( 
    echo "==================="
    echo "start code server"
    echo "==================="
    whoami

    # Install extension and start code-server
    {{- if $.Values.offlineMode }}
    mkdir -p ~/.local/share/code-server/extensions/
    tar -xvf /jonathan_tool_packages/extensions.tar --strip-components=1 -C ~/.local/share/code-server/extensions/
    {{- else }}
    code-server --install-extension ms-python.python
    {{- end }}
    # https://github.com/coder/code-server/commit/93e60f7b0e524153d1cb16f95b17ca8208c7c219
    code-server --bind-addr 0.0.0.0:{{ $.Values.service.port }} --auth none --trusted-origins=* --log debug $JF_HOME
    );
    sleep infinity;
{{- end }}


{{- define "shell_install" -}}
    (
    if command -v curl &>/dev/null; then
    echo "==================="
    echo "curl found, using curl to download ttyd"
    echo "==================="
    else
    echo "==================="
    echo "curl not found, installing curl, wget"
    echo "==================="
    apt-get update && apt-get install -y curl wget
    fi
    echo "==================="
    echo "Installed ttyd"
    echo "==================="
    # ttyd가 이미 설치되어 있는지 확인
    if command -v ttyd &> /dev/null
    then
        echo "ttyd already installed. Skipping download."
    else
        {{- if $.Values.offlineMode }}
        cp /jonathan_tool_packages/ttyd /usr/local/bin/ttyd
        {{- else }}
        echo "ttyd not found. Downloading..."
        VER=$(curl --silent "https://api.github.com/repos/tsl0922/ttyd/releases/latest" | grep '"tag_name"' | sed -E 's/.*"([^"]+)".*/\1/')
        cd /tmp
        curl -LO https://github.com/tsl0922/ttyd/releases/download/$VER/ttyd.x86_64
        chmod +x ttyd.x86_64
        sudo mv ttyd.x86_64 /usr/local/bin/ttyd
        {{- end }}
        echo "ttyd successfully installed."
    fi

    echo "==================="
    echo "start ttyd"
    echo "==================="
    whoami && \
    ttyd -p {{ $.Values.service.port }} -b /{{ $.Values.labels.tool_type }}/{{ $.Values.pod_name }}-{{ .index }} -w $JF_HOME -W bash)
{{- end }}

