# 개요

Flightbase 시스템 앱들에서 EFK 스택에 저장된 로그를 쿼리하는 과정을 간단하게 하고, 역할을 분산시키기 위하여 로그 쿼리를 담당하는 middleware로, gRPC 및 REST api를 지원함.

로그 저장 및 처리 과정 등 EFK 스택과 관련해서는 [/devops/aaai_efk](/devops/aaai_efk)를 참조

현재 golang에 대한 작업 이슈로 poc로 개발되었으며, 이후 리팩토링하여 devops 작성 예정.

## middleware -> elasticsearch

`go-elasticserach` 공식 라이브러리를 활용하여 elasticsearch에 쿼리를 요청함.
이 때 https 인증서 이슈로 현재 인증서 없이 쿼리하도록 하였으며, 추후 보안 관련 이슈를 대비한다면 es에서 인증서를 받아와서 등록하는 과정(configmap 활용?)이 필요할 수 있음.

## app -> middleware

미들웨어 레벨에서 1차 쿼리 이후 대부분의 처리를 마친 뒤 반환하도록 함.

엔드포인트 주소 및 메서드의 경우 `./proto/logquery/logquery.proto` 파일을 확인하면 있으며, request에 있는 변수명을 대소문자 그대로 하여 json key값으로 하여 요청하면 response가 json에 담겨서 반환됨.

### 예시

해당 미들웨어가 32715 nodeport를 통해 개방되어 있다면, 아래 커맨드로 테스트 가능
```
curl --location --request POST http://localhost:32715/v1/dashboard/admin --data-raw '{"timespan": "15m","count": 10, "offset": 0}'
```


# 개발

## 환경
./setup_go.sh로 golang 설치
gRPC 프로토콜 변경이 필요한 경우, `./proto/logquery/logquery.proto`를 수정한 뒤 ./build_proto.sh로 빌드할 수 있도록 스크립트가 준비되어 있음

## 쿼리 수정이 필요한 경우
비교적 최근에 작성한 쿼리 코드의 경우 golang 객체로 하여 쿼리문을 작성한 뒤 json으로 변환하도록 되어 있음.
비교적 이전에 작성된 코드의 경우 단순 text로 되어 있음.

어느 쪽이건, elastic 쿼리 코드이므로(텍스트냐 딕셔너리 형태냐의 차이) [Elasticserach 공식 문서](https://www.elastic.co/docs/reference/query-languages/querydsl)를 참조하여 변형하면 됨

## 입/출력 변경이 필요한 경우
proto 파일은 `./proto/logquery/logquery.proto`에 있으며, 대부분 `...Request` 를 받아 `...Response` 를 반환하는 형태로 구성해 두었음
proto 파일 하단에서 해당 구조체를 찾아 원하는 멤버 변수를 추가하면 됨.
당연히 다시 빌드 후 golang에서 해당 값을 읽거나 쓰도록 수정하여야 함.

## 새로운 메서드를 추가하는 경우
기존 구조를 참고하여, 요청 및 반환 구조체를 새로 만들거나 재활용하고, 요청에 대한 엔드포인트를 작성함.
이후 `./server/handler` 내에 기존 처리 `.go` 파일을 만들어서 메서드를 추가하거나 ~ 기존 파일들을 참고하여 새로운 `.go` 파일을 만듦.
해당 파일에서 로직 구현한 다음, 최종적으로 `./server/logquery_server.go` 에서 해당 핸들러로 래핑해 줌. (기존 파일을 사용하지 않고 새 파일을 사용하는 경우에는, `type LogQueryServer struct` 에 새로운 멤버 추가하고 해당 멤버를 할당해 주는 과정을 추가로 진행해야 함.)


# 로컬에서 실행
`server.go` 에서 elasticserach 서버 주소를 찾으며, 기본적으로 `https://elasticsearch-master-hl:9200`를 사용하도록 되어 있음. (k8s 내에서 `jonathan-efk` 네임스페이스를 공유하는 것을 전제하므로)

로컬에서 실행하는 경우는 위 dns를 resolve하지 못하므로, 이를 회피하기 위해 nodeport를 열고 9200 포트에 대해서 주소를 포함하여 `ELASTICSEARCH_ADDRESS` 환경변수로 그 주소를 설정할 것. 
(ex: `export ELASTICSEARCH_ADDRESS=https://192.168.0.20:32495`)

이후 아래 커맨드로 실행
```
go run server.go
```

# 이미지 빌드 후 배포
```
./image_build_push.sh <필요한경우이미지이름및태그>
```

# 배포
현재 poc 단계로 별도의 devops 폴더가 구성되어 있지 않음
```
kubectl apply -f test.yaml
```
로 deployment 및 service 배포포