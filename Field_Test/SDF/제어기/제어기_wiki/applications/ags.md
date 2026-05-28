# AGS (Beymons GREEN)

## 제품 코드 설명

- 제품군 코드: AGS
- 세부 제품 코드
  - GW: Gateway
  - ND: Node
  - OP: 제어 함체 및 내부 구성 포함 제품
  - XR: 제어 함체 및 내부 구성 포함 제품(외부 확장용)
  - NS: 양액기 제어 메인 함체 및 내부 구성 포함 제품
  - SN: 환경 센서

## 제품 코드

- AGS-GW
  - AGS용 게이트웨이
- AGS-ND-CONTROL
  - 제어기용 노드
- AGS-ND-SENSOR
  - 센서용 노드
- AGS-OP-24W-08M
  - 24W 모터 8채널 메인 제어 패널
- AGS-OP-48W-24M
  - 48W 모터 24채널 메인 제어 패널
- AGS-OP-120W-16E
  - 120W 모터 16채널 확장 제어 패널
- AGS-XR-08M
  - 외부 장치 제어 메인 패널
- AGS-XR-08E
  - 외부 장치 제어 확장 패널
- AGS-NS-08M
  - 양액기 제어 메인 패널
- AGS-SN-RAIN-cnt-wj24
  - 우적 센서
- AGS-SN-TEMP-abcd
  - 온도 센서
- AGS-SN-HT-xy-md02
  - 온습도 센서
- AGS-SN-SOIL-abcd
  - 토양 수분 센서
- AGS-SN-PH-abcd
  - PH 센서
- AGS-SN-LUX-abcd
  - 조도센서

## 센서 통신

### RS-485 address 예약

- 제어 모듈 및 필수 환경센서의 RS-485 주소 예약
- [이 파일](https://docs.google.com/spreadsheets/d/1IsV5lD10A9Eu1n1kJvYufFYPe1NiQfdXP_XjhbWthsw/edit?usp=sharing)에서 관리되고 있으며, 권한이 없는 경우 김응진 리더에게 문의 바람.
- 제어 모듈 관련 Address 예약
  - Broadcast: 0x00 (0)
  - 온습도 센서 그룹 1: 0x40 (64) ~ 0x4F (79)
  - 온습도 센서 그룹 2: 0x50 (80) ~ 0x5F (95)
  - 온습도 센서 그룹 3: 0x60 (96) ~ 0x6F (111)
  - 온습도 센서 그룹 4: 0x70 (112) ~ 0x7F (127)
  - ~~릴레이 제어 노드: 0xF7 (247)~~ - deprecated
  - ~~인터페이스 보드: 0xE6 (246)~~ - deprecated
  - 릴레이 제어 보드 그룹 A: 0xA0 (160) ~ 0xAF (175)
  - ~~릴레이 제어 보드 그룹 B: 0xB0 (176) ~ 0xBF (191)~~ - deprecated
  - ~~릴레이 제어 보드 그룹 C: 0xC0 (192) ~ 0xCF (207)~~ - deprecated
  - ~~릴레이 제어 보드 그룹 D: 0xD0 (208) ~ 0xDF (223)~~ - deprecated


# 통신 프로토콜

## 데이터 전송

- [DC 모터 제어 모듈](/protocol/data/dc_relay)

## 명령 전송

### 공통

- [모터 제어 모드 변경](/protocol/command/set_agsmotor_mode)
  - 현재 DC 모터와 AC 모터 제어 모드 변경 명령을 분리하여 정리해 둔 상태, 공통으로 사용 가능할지 검토 후 반영 필요
- [모터 제어 완료 보고](/protocol/command/set_agsmotor_action)
  - 현재 DC 모터와 AC 모터 제어 모드 변경 명령을 분리하여 정리해 둔 상태, 공통으로 사용 가능할지 검토 후 반영 필요
- [모터 오동작 보고](/protocol/command/set_agsmotor_error)
  - 현재 DC 모터와 AC 모터 제어 모드 변경 명령을 분리하여 정리해 둔 상태, 공통으로 사용 가능할지 검토 후 반영 필요

### DC 모터 제어 모듈 관련

- [DC 모터 제어](/protocol/command/dc_relay)
- [DC 모터 제어 (legacy)](/protocol/command/set_agsmotor)
- [DC 모터 calibration 명령](/protocol/command/dc_relay#dc모터-calibration)


### AC 모터 제어 모듈 관련

- [AC 모터 제어](/protocol/command/ac_motor)

### 마그네트 스위치 제어 모듈

마그네트 스위치 on/off 제어. 이 모듈을 사용해서 관수 모터, 유동팬 등을 제어한다.
마그네트 스위치 제어 모듈은 현재 8채널 범용 릴레이 모듈을 사용하며, 최대 4개의 마그네트 스위치를 제어한다.

- [MC 스위치 제어](/protocol/command/mc_switch)
  - 서버에서 마그네트 스위치 동작 제어 명령
- [MC 스위치 제어 오동작 보고](/protocol/command/mc_switch#동작-에러-보고)
  - MC 스위치 제어 명령에 대해 에러가 발생하는 경우 에러 메시지 전송
