# Beymons 구성요소 간 센서 데이터 전송 관련 공통사항

> Beymons 구성요소 간 명령 전송 관련 공통사항은 [여기](command)를 참조

## MQTT 메시지

### 메시지 정의 규칙

- 메시지 내에서 사용하는 key는 특별한 사유가 없는 경우 snake_case를 사용한다.
- 센서의 종류에 따라 서로 다른 구성을 갖는다.
- `ts` 필드는 선택 사항이며, 이 필드가 비어있는 경우 메시지를 받는 서버에서 timestamp를 입력한다.
    - 이에 대한 내용은 서버에서 구현이 필요하다. (구현됨)
    - "ts" 필드를 비우고 전송하는 것을 권장하지 않는다.
- ❗각 node 아래의 `address` 및 `channel` 을 통해 개별 센서들을 구분한다.
    - ❗기존 “channel” 의 개념이 “address”로 변경
    - ❗기존 “probe”의 개념이 “channel” 로 변경

### 메시지 공통 포맷

- 데이터 전송 메시지의 기본 구조는 아래와 같이 구성된다.
- 각 채널 아래의 `sensor_data_object` 부분은 이후 문단을 참조하여 센서 타입 별 고유한 형태로 구성된다.
- 각 센서 데이터에 `invalid` 필드가 존재하며, 정상 데이터인 경우 해당 필드를 포함하지 않는다. parsing 오류 등으로 노드에서 비정상 데이터로 판단한 경우에는 `invalid` 필드를 “true” 로 전송하며, 이후 응용에서 해당 레코드를 무시하고 처리한다.
- 각 Node 에서 전송한 데이터들을 모아서 전송한다.
    - 각 노드 별 하나의 object가 생성
    - 노드에서는 각각의 modubs_address(RS-485 국번)에서 수집한 데이터를 전송하며, 각 채널은 센서의 종류에 따라 데이터 구조가 변경된다.
- TODO: invalid 필드의 구체적인 의미에 대해서는 다시 정의 예정

```json
{
    "data": [
        {
            "node_id": "node_id_1",
            "address_1": [
                {sensor_data_object}, ...
            ],
            "rssi": [
                {
                    "device": "01",
                    "rssi": int
                }
            ]
        }
    ]
}
```


## 데이터 수집 형태에 따른 MQTT 메시지 형태 분류

### 센서 하나에 여러 개의 CH이 존재하는 형태

- 온도
    - 하나의 센서 아래에 여러 개의 채널 데이터를 전송한다.

```json
{
    "ts": "<unsigned long>",
    "invalid": true,
    "channel_1": {
        "temp": float
    }
}
```

- 계수기 (Counter)
    - 노드에 설정된 수집 주기 동안 카운트 된 횟수를 전송한다.
    - 

```json
{
    "ts": "<unsigned long>",
    "invalid": true,
    "channel_1": {
        "value": long
    },
    "channel_2": {
        "value": long
    }
}
```

- 릴레이 모듈
    - 측정 시점의 릴레이 상태를 전송한다.
    - is_closed 가 true 인 경우, COM-NO 단자가 연결된 상태를 의미한다.

```json
{
    "ts": "<unsigned long>",
    "invalid": true,
    "channel_1": {
        "is_closed": bool
    },
    "channel_2": {
        "is_closed": bool
    }
}

```

### 센서 당 하나의 데이터를 전송하는 형태

- 온습도
    - 하나의 센서에서 한 지점의 온/습도 데이터를 수집한다.

```json
{
    "ts": "<unsigned long>",
    "invalid": true,
    "temp": float,
    "humi": float
}
```

- 우적 센서
    - 우적 센서 제품은 일반적으로 2개 이상의 감지 패널을 가지고 있으며, 모든 패널에서 수분이 인식될 때 비가 오는 상황이라고 판단한다.
    - 데이터는 다음 수식의 결과로 출력된다. 소수점 둘째 자리에서 반올림하며, 값이 1인 경우에만 비가 오는 상황이라고 해석한다.
    
    $$
    출력 값 = round( \frac{감지된\ 패널\ 수}{전체\ 패널\ 수} )
    $$
    

```json
{
    "ts": "<unsigned long>",
    "invalid": true,
    "channel_1": [
        {
            "temp": float,
            "humi": float
        }
    ],
    "channel_2": [
        {
            "rain": float
        }
    ]
}
```

- AGS 릴레이 제어 보드
    - (임시)

```json
{
    "ts": "<unsigned long>",
    "invalid": true,
    "state": "open/stop/close",
    "open_rate": [0, 100, 0, 100, ...]
}
```

### 수집 주기가 짧은 시계열 데이터 (Multi CH)

- AGS 전류센서
    - sampling_rate 필드를 통해 샘플링 주기를 나타낸다. (단위: ms)
    - 모터가 동작한 시간 동안의 데이터를 전송한다.

```json
{
  "ts": "<unsigned long>",
  "invalid": true,
  "sampling_rate": int,
  "channel_1": {
    "amp": [int, int, ...]
  },
  "channel_2": {
    "amp": [int, int, ...]
  },
  "channel_3": {
    "amp": [int, int, ...]
  }
}
```

### 수집 주기가 짧은 시계열 데이터 (Single CH)

- 가속도
    - sampling_rate 필드를 통해 샘플링 주기를 나타낸다. (단위: ms)
    - 서버에 설정된 수집 주기동안 측정된 값들을 하나의 메시지로 구성한다.
    - 3축 가속도 센서와 6축 가속도 센서는 별도의 타입으로 정의해야 한다.

```json
{
  "ts": "<unsigned long>",
  "invalid": true,
  "sampling_rate": int,
  "x": [double, double, ...],
  "y": [double, double, ...],
  "z": [double, double, ...],
  "roll": [double, double, ...],
  "pitch": [double, double, ...],
  "yaw": [double, double, ...]
}
```

- 지자기

```json
{
  "ts": "<unsigned long>",
  "invalid": true,
  "sampling_rate": int,
  "x": [double, double, ...],
  "y": [double, double, ...],
  "z": [double, double, ...]
}

```

### 아직 분류되지 않은 형태

- ADC
  - sampling_rate 필드를 통해 샘플링 주파수를 나타낸다. (단위: ms)
  - bit_depth 필드를 통해 quantization 시 진폭의 해상도를 나타낸다. (단위: bit, 일반적인 CD 음원은 16bit)
  - ex) 마이크

```json
{
  "ts": "<unsigned long>",
  "invalid": true,
  "sampling_rate": int,
  "bit_depth": int,
  "data": "base64 encoded string"
}
```

- 조도
  - 제품 선정이 먼저 필요
  - 아래 내용은 잠정적인 포맷이며, 변경될 수 있음

```json
{
  "ts": "<unsigned long>",
  "invalid": true,
  "lux": int
}
```
