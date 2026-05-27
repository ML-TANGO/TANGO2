# MQTT Message

JSON Object 형태로 MQTT 통신

## 주요 특징

- 경량(Lightweight): 작은 코드 공간과 낮은 오버헤드로 리소스가 부족한 기기에 적합
- 발행/구독 모델: 송신자(Publisher)와 수신자(Subscriber)가 직접 연결되지 않고 브로커를 통해 느슨하게 결합되어 통신
- 토픽(Topic): 메시지를 분류하는 키워드이며 계층 구조를 가짐 (예: home/livingroom/temperature)
- QoS(Quality of Service): 메시지 전달의 신뢰성을 보장하는 세 가지 수준(0, 1, 2)을 지원
- 효율적인 통신: 낮은 대역폭과 불안정한 네트워크 환경에서도 안정적으로 작동하도록 설계

## 작동 방식

- 연결: 클라이언트(IoT 기기 등)가 브로커에 연결
- 구독: 특정 토픽을 구독하여 해당 토픽에 대한 메시지를 받겠다고 요청
- 발행: 클라이언트가 특정 토픽으로 메시지를 전송 (Publish)
- 전달: 브로커는 해당 토픽을 구독 중인 모든 클라이언트에게 메시지를 전달(Deliver) 

# Beymons 에서 MQTT

## Endpoint

- AWS의 IoT Core 서비스 혹은 MQTT Broker 서비스를 통해 메시지 전송
- mqtt://{site_id}:{password}/iot.beymons.kr:1883
- mqtts://{identifier}.iot.{region}.amazonaws.com:8883

## Topic 구조

Beymons 설치 형태에 맞게 topic 구조를 정의함.

- Topic 형태: {application}/{region_id}/{message_type}/{gateway_id}
  - application: 베이몬스 응용 형태 (ex. ags, hps, daq 등)
  - region_id: 베이몬스 디바이스가 설치되는 장소를 논리적으로 구분한 단위
  - message_type: 메시지의 특성을 나타내는 필드
    - _data: 센서 모듈에서 수집하는 데이터, 제어 모듈의 상태 데이터
    - _upstream: Beymons Device에서 서버로 전송하는 제어 관련 메시지
    - _downstream: 서버에서 Beymons Device로 전송하는 제어 관련 메시지
  - gateway_id: Gateway의 ID
- Beymons 디바이스 중 NodeGateway라는 타입이 있는데, 이것은 Node의 역할과 Gateway의 역할을 모두 수행하는 디바이스이다. 이 디바이스는 topic 명의 gateway_id 부분과 메시지 내에 "node_id" 라는 필드의 값을 모두 동일한 값으로 명시한다.
