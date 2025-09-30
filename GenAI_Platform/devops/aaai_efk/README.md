# /devops/aaai_efk

## 개요

Elsaticsearch + Fluent**-bit** + Kibana 스택입니다.
K8s 환경에서 helm으로 설치하는 것을 전제로 합니다.

본 EFK 스택의 경우 해당 오픈소스 사용을 주로 하되, 설치 중 값 설정 및 최초 초기화 스크립트만 구성되어 있으므로 별도의 apps 폴더는 존재하지 않습니다.

## 설치 요약

```shell
./helm_repo_add.sh
./upgrade_elastic.sh
# 모든 elastic 파드의 동작 확인 이후 진행
./elastic_init.sh
./helm_upgrade_fluent.sh
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
log_middleware와 연관된 내용은 [해당 문서]()를 참고해 주세요.

## 설정 및 기타 사항

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
