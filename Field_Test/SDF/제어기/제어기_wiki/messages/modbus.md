# Modbus Protocol

- client / server 또는 request / reply 형식의 프로토콜 (응용계층)
- RS-485는 디바이스 간 통신의 전기적 특성만을 정한 것 (물리계층)
  - 베이몬스실 내에서는 동일한 의미로 의사소통이 가능하지만, 명확한 의미로는 다른 것을 나타내기 때문에 혼동하지 않도록 주의
  - RS-485와 Modbus는 산업 자동화 및 데이터 통신에서 가장 흔히 조합되어 사용되는 기술

## Modbus master/slave 프로토콜 원칙

마스터 노드는 한 번에 하나의 Modbus 처리를 수행

- unicast
  - 마스터가 개개의 슬레이브를 호출, 요청을 받은 슬레이브는 마스터에게 응답
  - 각 슬레이브는 단일 주소를 가지며, 각 슬레이브 노드로부터 독립적으로 호출됨
- brocast
  - 마스터가 모든 슬레이브를 호출
  - 마스터가 보낸 요청에 대한 응답은 하지 않음

## Function Code

| function code | description |
| --- | --- |
| 1 | Read Coil Status |
| 2 | Read Input Status |
| 3 | Read Holding Registers |
| 4 | Read Input Registers |
| 5 | Write Single Coil Status |
| 6 | Write Single Register |
| 15 | Multiple Coil Write |
| 16 | Multiple Regsiter Write |
