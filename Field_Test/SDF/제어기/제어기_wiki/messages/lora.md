# LoRa Packet

메시지 구조는 다음 순서대로 정의된다

## 메시지 시작 표지 (1 byte)

메시지 시작 표지로 `0x0D` 를 사용한다.

## 메시지 헤더 (고정길이/길이 미정)

| packet type | device depth | device ID | packet sequence | device version | payload length | trailer length |
| --- | --- | --- | --- | --- | --- | --- |
| 1 byte | 1 byte | 5 or 6 bytes | 2 bytes | 1 byte | 1 byte | 1 byte |

### packet type

- 1 byte 길이로, 메시지의 종류를 정의한다.
- 짝수 메시지는 Upstream, 홀수 메시지는 Downstream 메시지로 사용한다.

| Hex | Decimal | 이름 | 설명 | 방향 |
| --- | --- | --- | --- | --- |
| 0x02 | 2 | Data Packet | 데이터 패킷 | Up |
| 0x03 | 3 | Data Ack | 데이터 패킷 수신 확인 | Down |
| 0x04 | 4 | Command Ack | 디바이스 제어 명령 수신 확인 | Up |
| 0x05 | 5 | Command Packet | 디바이스 제어 명령 패킷 | Down |
| 0x06 | 6 | Error Report | 디바이스 에러 발생 패킷 | Up |
| 0x07 | 7 | Error Report Ack | 디바이스 에러 발생 패킷 수신 확인 | Down |

### device depth

- 1 byte 길이로, 해당 메시지를 전송하는 디바이스의 depth를 나타낸다.
- Device의 역할 및 Repeater depth 정의
    - 0x01: Node
    - 0x02 ~ 0xFE: Repeater
    - 0xFF: Gateway
- Repeater인 경우 중요하게 다뤄야 하는 필드이다. 자신에게 설정된 depth와 메시지에서 받은 device depth, packet type을 비교하여 재전송할 패킷과 그렇지 않을 패킷을 선택한다.
    - upstream packet인 경우: 자신의 depth보다 낮은 곳에서 수신한 데이터만 재전송 (Node → Gateway)
    - downstream packet 인 경우: 자신의 depth보다 높은 곳에서 수신한 데이터만 재전송 (Gateway → Node)
- Repeater가 패킷을 재전송하는 경우, 이 필드의 값을 자신에게 설정된 depth로 변경 후 전송한다.

### device ID

- 해당 패킷을 생성하는 디바이스의 ID
- 5 or 6 bytes (맨 앞 0D를 포함할지 여부 결정 필요)
- ‘0DYYMMDDnnnn’ 형태의 device 고유 번호
- 마지막 2bytes 는 동작 모드에 따라 ID 범위가 지정되어 있다
    - 0001 ~ 0FFF: Edge (4094개)
    - 1000 ~ 1FFF: Gateway (4095개)
    - 2000 ~ 3FFF: Repeater (8191개)
    - 4000 ~ 4FFF: NodeGateway (4095개)
    - 5000 ~ FFFF: Node (45,054개)

### packet sequence

- 2 bytes
- 메시지를 생성하는 디바이스에서 관리하는 일련번호

### device version

- 1 byte

### payload length

- 1 byte
- 압축된 payload 길이

### trailer length

- 1 byte
- 압축된 trailer 길이

## Payload (가변 길이)

payload header와 data 영역으로 구분된다.

### Payload Header

- 데이터의 타입을 표현하는 필드
- 데이터 전송, upstream command, downstream command로 구분
    - 패킷 자체의 목적이나 방향은 메시지 헤더에 이미 정의됨
    - 패킷 자체의 목적을 좀 더 세분화하고, 각 타입에 맞는 번호를 다시 1 byte로 구분하는 방법도 고려 (4안)
    - 현재 메시지 헤더는 데이터, device 제어, device 에러만 정의됨
    - Node → Gateway 로 요청, 응답 부분을 추가로 정의 필요


#### 💡 1안

> - 긴 수집주기, 단일 채널
>   - header (데이터 타입)
>   - data
> - 긴 수집주기, 다중 채널
>   - header (데이터 타입, probe 수)
>   - data
> - 짧은 수집주기, 단일 채널
>   - header (데이터 타입, sampling 주기, sampling 횟수)
>   - data
> - 짧은 수집주기, 다중 채널
>   - header (데이터 타입, sampling 주기, sampling 횟수, probe 수)
>   - data

#### 💡 2안
> 
> - 긴 수집주기 데이터
>   - header (데이터 타입, probe 수)
>   - data
> - 짧은 수집주기 데이터
>   - header (데이터 타입, sampling 주기, sampling 횟수, probe 수)
>   - data

#### 💡 3안

> - 데이터
>   - header (데이터 타입, sampling 주기, sampling 횟수, probe 수)
>   - data

## Trailer (가변 길이)

Payload 외 부가 정보들을 추가하여 전송하기 위한 영역이다.

### Repeater RSSI

메시지 버전 (v1.0.0) 에서 사용되며, Trailer를 구성하는 유일한 요소이다.

node로 부터 받은 메시지의 rssi, repeater로 부터 받은 메시지의 rssi로 구성된다.

| repeater_no | rssi |
| --- | --- |
| 1 byte | 1 byte |
- repeater_no: DBMS에 등록된 리피터 번호
    - Node는 repeater_no 가 0으로 고정된다.
- 고객에게 repeater를 배포할 때 해당 값이 중복되지 않도록 해야 한다.

리피터를 거치면서 trailer에 RSSI를 구성한다.


#### 💡 예시 환경

> - 구성: Node(N), Repeater 1(R1), Repeater 2(R2), Gateway(GW)
> - R1의 repeater_no: 1
> - R1이 수신한 RSSI: 80
> - R2의 repeater_no: 2
> - R2가 수신한 RSSI: 90
> - GW가 수신한 RSSI: 100


| N tx | 0 | 0 |  |  |  |  |
| --- | --- | --- | --- | --- | --- | --- |
| R1 rx | 0 | 0 |  |  |  |  |
| R1 tx | 0 | 80 | 1 | 0 |  |  |
| R2 rx | 0 | 80 | 1 | 0 |  |  |
| R2 tx | 0 | 80 | 1 | 90 | 2 | 0 |
| GW rx | 0 | 80 | 1 | 90 | 2 | 0 |
| GW 수정 | 0 | 80 | 1 | 90 | 2 | 100 |

(확정 내용은 아니며, Node tx 단계에서 0 0 을 추가하는 부분은 생략될 수 있음)

## CRC (2 bytes)

- 데이터의 오류 확인을 위해 사용하는 필드
- 메시지 시작 구분자 ~ Trailer 까지의 데이터에 대한 CRC 계산 결과
