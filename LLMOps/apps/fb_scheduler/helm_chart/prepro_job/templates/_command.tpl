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
    echo "============================================"
    echo "🚀 JONATHAN 전처리 필수 패키지 설치"
    echo "============================================"
    echo ""
    cd /support && ./check_package_installed.sh
    {{- if gt (int $.Values.spec.containers.env.JF_TOTAL_GPU) 1 }}
    echo "============================================"
    echo "⚙️  JONATHAN 딥스피드 환경 설정"
    echo "============================================"
    echo ""
    cp -ar /distributed ~; cd ~/distributed; ./init.sh;
    {{- end }}
    cd $JF_HOME
    {{- if eq .index 0 }}
    (
    echo "============================================"
    echo "✅ JONATHAN 전처리 코드를 실행합니다"
    echo "============================================"
    cd $JF_HOME
    {{ $.Values.spec.containers.command }}
    # 전처리 코드의 종료코드를 붙잡아 둔다. sleep 은 로그 플러시용이라 남기지만,
    # 서브셸의 마지막 문이 sleep 이면 그 0 이 종료코드를 덮어 실패한 잡이
    # 성공(done)으로 보고된다. 학습 차트(project_job/_command.tpl)는 명령이
    # 마지막이라 원래 정상 전파된다 — 그 동작에 맞춘다.
    _rc=$?
    sleep 10
    exit $_rc
    )
    {{- else }}
    while true; do sleep 30; done;
    {{- end }}


{{- end -}}


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