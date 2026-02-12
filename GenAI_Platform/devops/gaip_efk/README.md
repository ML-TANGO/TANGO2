# /devops/aaai_efk

## 개요

Elsaticsearch + Fluent**-bit** + Kibana 스택입니다.
K8s 환경에서 helm으로 설치하는 것을 전제로 합니다.

본 EFK 스택의 경우 해당 오픈소스 사용을 주로 하되, 설치 중 값 설정 및 최초 초기화 스크립트만 구성되어 있으므로 별도의 apps 폴더는 존재하지 않습니다.

단 로그 쿼리 시 별도의 미들웨어를 두어 해당 미들웨어에서 처리하며,
`fb_log_middleware` app는 현재 devops 폴더 내 배포 처리가 진행되어 있지 않으므로
해당 폴더 내에서 지침을 따라 별도로 클러스터에 배포가 필요합니다.

## 설치 요약

```shell
./helm_repo_add.sh # 레포 추가
./helm_upgrade_elastic.sh # Elastic 설치(혹은 업그레이드)
# 모든 elastic 파드의 동작 확인 이후 이어서 진행
./elastic_init.sh # Elastic 인덱스 설정 등
./helm_upgrade_fluent.sh # Fluent 설정
```
순으로, 이 README 파일이 포함된 디렉토리에서 실행합니다.

## 설명

### 스택

Elasticsearch를 통한 로그 저장 및 쿼리, Kibana를 통한 시각화를 진행합니다.
Fluent-bit가 각 노드로부터 로그를 수집해서 Elasticsearch로 전송합니다.

### 역할

1. 서버 운용에 활용하기 위해 서버 전역의 로그를 수집합니다.
2. Jonathan의 사용자 앱(학습 job, 배포 등)의 로그를 저장 및 1차 가공합니다.

### 연계

로그 수집 및 저장/가공 레벨에서는 다른 프로젝트와 연계되지 않습니다.
로그 쿼리가 필요할 때에는 log_middleware와 연계하여, 해당 앱을 통해 elasticsearch 쿼리를 진행함을 전제로 합니다.
log_middleware와 연관된 내용은 [/apps/fb_log_middleware](/apps/fb_log_middleware/)를 참고해 주세요.

## 설정 및 기타 사항

### 인덱스 관리

ElasticSearch는 인덱스 단위로 로그들을 관리하게 되며, 인덱스 단위로의 보관 정책 적용이 필수 불가결하므로 로그 카테고리에 따라 인덱스로 나누어서 처리함.

이를 위해 Fluent-bit에서 로그를 적절히 분류한 다음, elasticsearch로 내보내야 함.

Fluent-bit에서 처리하는 세부적인 로직은 해당 문단 참조.

#### 분류

FB 시스템 앱의 경우 쿠버네티스 라벨에서 `acryl.ai/appType`을 `system`으로, FB 내 사용자가 제어할 앱(학습 job, worker 등)의 경우 `acryl.ai/appType`를 `user`로 설정하는 것으로 전제하였음.

위 기준에 따라, 라벨 값이 있는 경우에 대해,
- 시스템 앱 중 특정 헤더가 있으면 헤더를 기준으로 분류하고
- 시스템 앱 중 헤더가 없으면 표준출력인지 표준에러인지를 바탕으로 일반 로그와 디버그 로그를 분류하고
- 사용자 앱 중 특정 헤더가 있으면 해당 헤더에 따라 분류하고, (일부는 사용자 앱 로그임에도 사용자가 아닌 FB 개발자의 의도 하에 추가된 로그가 있음 - worker resource 로그)
- 그렇지 않으면 일반 유저 로그로 분류함

최종적으로 분류되는 로그의 경우 Kibana에 접속하여 확인하는 것을 권장

#### date_nanos

여러 줄을 빠르게 출력하는 경우(ex - 단순히 print로 여러 줄을 출력하는 경우) 로그 시간의 정밀도가 낮은 경우 동시에 출력된 여러 라인의 순서가 정해지지 않을 수 있음.
조나단 앱 레벨에서는 큰 이슈가 아닐 수 있으나, 조나단 특성상 학습 및 배포 등에서 사용자가 출력한 로그를 사용자가 확인해야 하는 경우가 있고, 이 때 정밀도가 낮은 상태로 시간이 같다면 단순히 순서가 뒤섞이는 것이 아닌 쿼리 레벨에 순서가 무작위로 결정되게 되어 화면 갱신 시마다 텍스트가 움직이게 되는 문제가 발생함.
이를 해결하기 위해 기본값 대신 elasticsearch 레벨에서 `date_nanos` 단위의 정밀도를 사용하게끔 하고, 이 과정에서 elasticserach에서 index template을 통해 매핑을 해 줄 뿐만 아니라 fluent-bit 역시 해당 정밀도로 값을 측정해서 전달할 수 있도록 하는 설정이 필요함.

해당하는 설정에 대해서는 각 부분에서 후술.


### elastic

Elastic에서 제공하는 공식 헬름 차트의 경우 일정 버전(대략 23년 중순) 이후 지원이 중단되었으므로, 서드 파티 차트를 사용합니다.
Bitnami 차트를 사용하며, kibana도 같이 처리할 수 있으므로 같이 처리합니다.

#### 설정

##### 노드

Elastic 차트에서 크게 네 유형의 파드를 띄웁니다. (kibana는 제외)
`master`, `ingest`, `data`, `coordinating`

###### Master
Master 노드는 인덱스 등을 관리하며, 이 과정에서 소량의 데이터 공간이 필요합니다. (1주일 사용 시 1MB 이내)
마스터는 네트워크 일부만 끊어진 이후 합쳐지는 과정에서의 이슈를 해결하기 위해, 절대적으로 3개 이상의 홀수개를 구성하도록 권장하고 있습니다.

###### Ingest
Ingest 파이프라인을 처리합니다.
다만 현재 구성상으로는 k8s event의 중복 방지를 위한 단순한 파이프라인만 존재하므로, 적은 수로 유지하여도 됩니다.

###### Data
실제 데이터를 저장합니다.
Primary shard 및 replica로 데이터 백업을 처리하기 위해서, 둘 이상을 두는 것이 권장됩니다.
CPU, I/O, 메모리 등 주요 처리는 여기서 수행되므로 적절한 자원 할당이 필요합니다.
로그 저장 범위 및 보관 기간에 따라 상당량의 데이터 공간이 필요합니다.
레플리카 개수에 따라 정비례하여 증가되며, 아래는 1 Primary, 1 Replica 기준입니다.
- k8s 시스템을 포함하여 redis, metallb, prometheus, grafana, ceph 등의 파드 로그를 기록하는 경우 1일에 30GB가량
- Flightbase 시스템 앱, 2024/09/11 기준 개발서버 사용 시 1일에 2GB가량

###### Coordinating
일종의 2차 로드밸런서 역할입니다.

##### 기타 설정
...

#### Kibana
kibanaEnabled: true 설정 시, Kibana dependency에 따라 kibana도 함께 설치합니다.

##### 설정
[Bitnami의 kibana 차트(버전 유의)](https://github.com/bitnami/charts/blob/main/bitnami/kibana/values.yaml)를 참고하여 설정을 진행합니다.

기본적으로 접근 불가능하게(ClusterIP) 설정되어 있으며, 설치 후 NodePort 등으로 변경하여 접근할 수 있습니다.

Ingress를 허용하려면, 주석 처리된 부분을 해제하여 ingress enable 및 hostname 과 path 등의 설정을 진행하되 경로상의 이슈(subpath)를 해결하기 위해 `kibana.configuration.server.publicBaseUrl`을 외부 접속 주소를 포함하여 적절히 설정해야 함에 유의하세요.

### Fluent-bit

Fluent에서 제공하는 공식 차트를 사용합니다.
커스텀 lua script 및 input-filter-output 설정을 진행했으며, 해당 값은 [fluent-values.yaml]()를 확인해 주세요.

#### 플로우

Fluent-bit는 기본적으로 Input-Filter-Output의 순서로 진행됩니다. 이에 관한 매뉴얼은 [Fluent-bit 매뉴얼](https://docs.fluentbit.io/manual/pipeline/pipeline-monitoring) 을 참고하세요.

위 값들은 fluent-values.yaml 내에 config.inputs / config.filters / config.outputs에 기재되며, 이는 차트 내에서 fluent 설정으로 적절히 넣어 줍니다.

로그는 Input에서 입력된 이후, tag가 지정되며 filter에서는 tag의 조건에 따라서 적절히 로그를 처리하고, output 역시 tag 조건에 따라 로그를 내보내게 됩니다.

##### Input

[Fluent-bit Inputs 매뉴얼](https://docs.fluentbit.io/manual/pipeline/inputs) 참고.

Input는 기본적으로 log 파일들을 읽는 것에서 시작합니다.

docker(를 비롯한 k8s에서 사용될 container runtime)의 경우 기본 경로상 /var/log/containers/*.log에 파일을 저장하고, 이에 따라 아래와 같이 input을 기재합니다.
실제로 해당 경로 내에는 log rotate가 원활하게 되도록 처리해 주고 있으며(아마도 container runtime이?), 그 구조상 symbolic link 파일만 존재합니다.
이에 따라 symlink가 해당 경로로 적절히 마운트되고, 로그가 있는 실제 경로 역시 적절히 마운트되어야 합니다. (마운트 관련 설명은 후술)

Refresh interval의 경우 **새로운 로그가 있는지 감지**하는 주기이므로 적절히 설정해 주어야 하며, Jonathan 특성상 pod가 새로 뜬 이후 로그를 보는 것이 의미가 있는 경우가 많으므로 시스템상 부하를 감안하고서라도 기본값 60에서 10으로 조정했습니다. 

```
    [INPUT]
        Name tail
        Path /var/log/containers/*.log
        multiline.parser cri, docker, multiline-custom, multiline-python-trace
        Tag kube.*
        Buffer_Max_Size 10MB
        Skip_Long_Lines Off
        Refresh_Interval 10
```

더불어, kubernetes 이벤트와 systemd 이벤트(중에서도 kubelet 및 containerd) 로그를 받아오기 위해 다음 Input도 추가로 설정합니다.
```
    [INPUT]
        Name systemd
        Tag host.*
        Systemd_Filter _SYSTEMD_UNIT=kubelet.service
        Systemd_Filter _SYSTEMD_UNIT=containerd.service
        Read_From_Tail On
```

마지막으로, kube-system 네임스페이스의 쿠버네티스 시스템 앱 로그 역시 처리하도록 하기 위해(어떤 이유에서인지 맨 위의 log에서는 처리하지 않음, 로그 파일 형식상 네임스페이스가 로그 이름에 붙음) 별도의 input을 만들어 줍니다.

```
    [INPUT]
        Name  tail
        Tag   kubecomp.*
        Path  /var/log/containers/*kube-system*
        multiline.parser docker, cri    
        Refresh_Interval 10
```

요약: kube-system 네임스페이스를 포함한 컨테이너 로그, k8s event, systemd 중 kubelet 및 containerd 로그를 input으로 가져옴

##### Filter

[Fluent-bit Filters 매뉴얼](https://docs.fluentbit.io/manual/pipeline/filters) 참고

Filter에서는 각종 로그에 대해 여러 처리를 거치게 됩니다.

우선 Kubernetes에 대해서 각종 label 등의 데이터를 붙이기 위해 [kubernetes 필터](https://docs.fluentbit.io/manual/pipeline/filters/kubernetes)를 거칩니다.
이 때 일부 라벨이 과도해지는 경우 등 기본값 buffer를 초과할 수 있으므로, 버퍼 사이즈를 한도 해제해줍니다.
```
    [FILTER]
        Name kubernetes
        Match kube.*
        Merge_Log Off
        K8S-Logging.Parser On
        K8S-Logging.Exclude On
        Labels On
        Annotations On
        Buffer_Size 0
```

이후 커스텀 스크립트를 통해 카테고리를 구분해줍니다. 스크립트의 경우 후술합니다.

이후 추출된 카테고리 정보를를 토대로 [rewrite_tag 필터](https://docs.fluentbit.io/manual/pipeline/filters/rewrite-tag)를 적용합니다. 
해당 필터의 경우 적용 이후 필터를 처음부터 다시 모두 거치는 판정이므로, 태그를 기존과 완전히 다르게 설정해 주어야 일부 필터가 이중 적용되는 현상을 피할 수 있습니다.
이에 따라 `kube.`로 시작하지 않도록 태그를 재설정해 줍니다.
```
    [FILTER]
        Name    lua
        Match   kube.*
        Script  /fluent-bit/scripts/jfb.lua
        Call    category_major_minor

    [FILTER]
        Name            rewrite_tag
        Match           kube.*
        Rule            $_cat_minor  ^(?!user$)  nonuser.$TAG  false
```

이후 조건 분기를 거쳐 특정 카테고리를 가진 값들의 경우, log에서 헤더가 제거하여 jfb-log 값을 추출하고, 이 값을 바탕으로 json을 추출하는 과정 등 기타 처리를 진행합니다.
```
    [FILTER]
        Name            parser
        Match           nonuser.kube.*
        Key_Name        log
        Parser          jfb-extract-level
        Preserve_Key    On
        Reserve_Data    On

    [FILTER]
        Name            parser
        Match           nonuser.kube.*
        Key_Name        log
        Parser          resource-extract-level
        Preserve_Key    On
        Reserve_Data    On

    [FILTER]
        Name            parser
        Match           nonuser.kube.*
        Key_Name        log
        Parser          worker-extract-level
        Preserve_Key    On
        Reserve_Data    On

    [FILTER]
        Name        lua
        Match_Regex nonuser.kube.*
        Script      /fluent-bit/scripts/jfb.lua
        Call        level_confirm

    [FILTER]
        Name            rewrite_tag
        Match           nonuser.kube.*
        Rule            $_cat_minor  ^(usage|resource)$  json.$TAG  false

    [FILTER]
        Name            parser
        Match           json.nonuser.kube.*
        Key_Name        jfb_log
        Parser          json
        Preserve_Key    On
        Reserve_Data    On

    [FILTER]
        Name    lua
        Match   *kube.*
        Script  /fluent-bit/scripts/jfb.lua
        Call    congregate_index

    [FILTER]
        Name modify
        Match k8s_event
        Rename message log

    [FILTER]
        Name        parser 
        Match       kube.*
        Key_Name    log
        Parser      jfb-extract-user-json-body
        Preserve_Key On
        Reserve_Data On
```

##### Output

최종적으로 Elasticsearch로 모든 데이터를 내보냅니다.

이 때 버퍼 사이즈가 늘어났음에 유의하여 마찬가지로 버퍼 세팅을 해 주어야 하며, 더불어 무한 새로고침하지 않도록 재시도 횟수를 5로 제한합니다. (es가 죽은 경우 fluent도 완전히 터지는 상황을 방지합니다 - 다만 재시도 횟수 제한으로 인해 일시적인 에러임에도 로그가 일부 누락될 가능성은 존재합니다)

추가로 Logstash_prefix 설정 등을 통해 태그에 따라 인덱스를 나누어 보낼 수 있도록 하며, Time_key_nano 등의 옵션을 통해 나노초 단위 정밀도 옵션을 활성화해줍니다. (나노초는 elastic_init 시 index 설정도 진행)

```
    [OUTPUT]
        Name es
        Match *kube.*
        Host elasticsearch
        Port 9200
        Buffer_Size False
        HTTP_User elastic
        HTTP_Passwd tango1234!
        tls On
        tls.verify Off
        Logstash_Format On
        Logstash_Prefix idx_failed
        Logstash_Prefix_Key $_jfb_index
        Logstash_DateFormat all
        Retry_Limit 5
        Suppress_Type_Name On
        Trace_Error On
        Replace_Dots On
        Include_Tag_Key On
        Tag_Key _fluentbit_tag
        Time_Key_Nanos On

    [OUTPUT]
        Name es
        Match host.*
        Host elasticsearch
        Port 9200
        Buffer_Size False
        HTTP_User elastic
        HTTP_Passwd tango1234!
        tls On
        tls.verify Off
        Logstash_Format On
        Logstash_Prefix system-kubelet
        Logstash_DateFormat all
        Retry_Limit 5
        Suppress_Type_Name On
        Trace_Error On
        Replace_Dots On
        Include_Tag_Key On
        Tag_Key _fluentbit_tag
        Time_Key_Nanos On

    [OUTPUT]
        Name es
        Match kubecomp.*
        Host elasticsearch
        Port 9200
        Buffer_Size False
        HTTP_User elastic
        HTTP_Passwd tango1234!
        tls On
        tls.verify Off
        Logstash_Format On
        Logstash_Prefix system-kubecomp
        Logstash_DateFormat all
        Retry_Limit 5
        Suppress_Type_Name On
        Trace_Error On
        Replace_Dots On
        Include_Tag_Key On
        Tag_Key _fluentbit_tag
        Time_Key_Nanos On

    [OUTPUT]
        Name es
        Match k8s_event
        Host elasticsearch
        Port 9200
        Buffer_Size False
        HTTP_User elastic
        HTTP_Passwd tango1234!
        tls On
        tls.verify Off
        Logstash_Format On
        Logstash_Prefix system-event
        Logstash_DateFormat all
        Retry_Limit 5
        Suppress_Type_Name On
        Trace_Error On
        Replace_Dots On
        Include_Tag_Key On
        Tag_Key _fluentbit_tag
        Pipeline deduplicate_logs
        Time_Key_Nanos On
```

#### 기타 설정값
##### Script

헬름 내 luaScripts 내 기입한 값은 차트 내에서 파싱해주므로, `luaScripts.jfb.lua` 값으로 스크립트를 설정해 줌.
이 때 반환값의 경우 [fluent-bit lua 문서](https://docs.fluentbit.io/manual/pipeline/filters/lua)를 참고할 것.

- category_major_minor: 헤더 분석을 통해 대분류/중분류를 추출해 냄(major: 대분류 / minor: 중분류)
- level_confirm: 소분류에 대해 마지막 체크를 함(level: 소분류)
- congregate_index: 최종 elasticsearch에 넣을 index 문자열을 구성함

##### Parser

여러 줄 로그 인식을 위해 multiline parser와, 헤더 제거를 위한 parser를를 만듦.

파이썬 멀티라인 파서는 내장되어 있으나 어쩐 이유인지 정상적으로 동작하지 않아 `multiline-python-trace` 를 제작했으나, 또 환경이 조금 다른 경우 정상 처리되지 않는 것으로 보여 보완 필요함. 

FB 환경에서의 멀티라인 처리를 위해 MultilineStart로 시작, MultilineEnd로 끝내는 `multiline-custom`을 만듦

추가로 소분류 추출을 위한 `...-extract-level` 파서 및 헤더 제거를 위한 `jfb-extract-user-json-body`를 만듦.

#### 로그 처리

로그는 기본적으로 `/var/log/container`에 저장되며, 이는 결국 심볼릭 링크가 걸려 있어서 `/var/lib/docker/containers` 내에 실질적인 로그 파일이 저장되게 됨.

따라서 fluent-bit가 이를 가져가기 위해서는 hostpath 마운트가 정상적으로 처리되어야 하며, fluent의 기본 동작은 `/var/log/containers` 내의 로그를 가져가므로 해당 경로는 정상적으로 처리되어야 함.

로그의 심볼릭 링크가 있는 `/var/log`에 설정된 경로를 fluent-bit 내의 `/var/log` 로 옮겨주어야 하며,
로그가 저장되는 실질 경로 `/var/lib/docker/containers` 내의 파일은 **그 위치 그대로** 마운트하여 심볼릭 링크가 파일을 찾아갈 수 있도록 마운트해주면 됨.

##### 클러스터 내 경로가 다르다면?

클러스터 내에 설정된 경로가 상이한 경우가 있음. (통일부)

설정했던 환경에서는 `/var/log/`의 경로는 동일하였으므로 해당 경로 그대로 설정해주면 되고,
docker root path가 다른 경우 그 경로 모두를 hostpath로 매핑해주어 해결할 수 있음. (hostpath 마운트를 존재하는 경로마다 지정해서 마운트를 여러 종류 생성, 한 노드에 모든 디렉토리가 있지 않아도 pod 정상 실행됨)

### elastic_init

#### 로직

기본적으로 elastic 설치 시 별도의 컨피그를 하는 과정을 확인하지 못 하여서, 인덱스 템플릿을 설정하고 ILP를 설정해주는 과정을 자동화해주기 위한 스크립트.

curl을 통해 elastic 서버에 요청을 보내므로 curl이 가능한 이미지를 선정함. (불가피한 경우 app 이미지들 재사용도 가능할 것으로 보임)

스크립트를 바탕으로 configmap 생성 -> 해당 cm을 활용해 job 실행 -> pod 내에서 curl로 요청하는 순으로 실행됨.

이 과정에서 인덱스 템플릿 설정(시간 나노초 설정을 비롯한 타입 강제 포함) 및 ILP 생성 및 적용 등을 수행함.

#### 수정

[./elastic_init/setup_elastic.sh](./elastic_init/setup_elastic.sh) 파일을 수정하면 됨.

해당 파일 내에서 보관 기간 등을 조절할 수 있으며, **일단 한 번 실행된 이후에는 ./elastic_init.sh를 재실행해서 ILP를 변경할 수 있음**.

다만 한 번도 실행된 적이 없다면 index template이 생성되지 않아 적용이 전혀 안 된 상태이므로, 만약 init 스크립트를 실행하지 않은 채 Fluent-bit가 실행되었다면 아래 Kibana 사용 참조하여 index를 모두 지우거나 완전 재설치하여 해결 필요. (완전 재설치 시 차트 uninstall 후 pv/pvc 삭제 필요)


### Kibana 사용

그냥 설치 후 kibana 서비스 유형을 NodePort로 변경하거나, 혹은 Ingress 활성화를 진행하여 설치한 이후 해당 서비스로 접근하면 됨.
`esvalues.yaml` 파일을 참고하여 `elastic` 계정으로 로그인하면 접근할 수 있음.

#### 설정

왼쪽의 3선 메뉴 > Management > Stack Management 메뉴로 진입하여 인덱스 관련 설정을 할 수 있음.

Index Management에서는 Index Template로 템플릿이 잘 생성되어 있는지 확인할 수 있으며,
Data Streams에서 생성된 인덱스들을 확인할 수 있음. 
Indices의 경우 정상적으로 설정이 진행되었다면 존재하지 않으나, 만약 elastic_init.sh를 실행하지 않은 채로 Fluent가 설치되었다면 여기에 Flightbase와 관련된 로그들이 잘못 쌓이게 되므로, 모든 Index를 지워주면 됨. (init을 실행한 이후에 지워야 정상 처리됨)

Index Lifecycle Policies에서 적용된 정책을 확인하거나 수동으로 수정할 수 있음.

#### 쿼리

3선 메뉴 > Discover 에서 검색을 할 수 있음.

우선 Data View를 만들어야 하며, 이는 검색 대상이 될 data stream들을 지정해 주는 것임.
필요에 따라 패턴을 지정하거나(와일드카드 `*` 사용 가능) 혹은 `*-all` 을 입력하면 모든 (FB에서 쓰는) 인덱스를 지정할 수 있음.
필요에 따라 Data View는 여러 종 작성할 수 있음.

이후 KQL 혹은 ES|QL을 활용하여 쿼리를 진행하면 되며, 쿼리 문법에 관해서는 [Elaistcsearch 공식 문서](https://www.elastic.co/docs/reference/query-languages/) 참고.

#### 내보내기

위 `쿼리` 에서 설명하는 내용을 따라 쿼리를 진행했으면, 현재 검색 결과를 csv로 내보낼 수 있음.

우측 상단의 save 왼쪽에 있는 아이콘을 누르면 share this search 메뉴가 뜨며, export를 눌러 csv로 내보낼 수 있으므로 참고.

### 기타

#### `.keyword`?

기본적으로 elasticsearch에서는 지능적으로 타입을 결정하는 관계로, 명시적으로 string으로 처리하기 위해서는 `키이름.keyword` 로 지정할 필요가 있음.

따라서 문자열 검색을 하는 등의 경우에는 가급적 `.keyword`를 붙여서 처리하는 것이 좋음.



