# Beymons 응용

- Beymons 응용에 따라 세부 코드로 구분된다.
- 각 응용에 따라 다음과 같이 분류되며, 각 응용에 전용으로 사용하는 모듈이나 메시지 형태 등이 있다.
- 공통적인 메시지 설명은 [데이터 전송](protocol/data), [명령 전송](protocol/command) 페이지 참조.

## [AGS](/applications/ags)

- Beymons GREEN
  - 스마트 팜 응용

## [DAQ](/applications/daq)

- Beymons BLUE
  - 데이터 수집, 저장, 모니터링
  - 스마트 제조 지원사업
  - 스마트공장 구축 지원사업

## [HPS](/applications/hps)

- Beymons RED
  - 극저온 냉동고 등의 장비 예지보전

# 제품 코드 구성

- 각 응용 별 제품 코드가 구성되어야 함
- 코드 형식: AAA-BB-subcode
  - AAA: 제품군 코드
    - 3자리의 영어 대문자로 표기
    - 미리 지정된 제품군 코드를 사용
  - BB: 제품군에 속하는 세부 제품 코드
    - 2자리의 영어 대문자로 표기
    - 세부 제품 코드를 표현하되, 기존에 정의된 코드와 중복되지 않도록 지정
  - subcode: 세부 제품에서 스펙을 간단히 나타내는 코드
    - 대/소문자 및 숫자 사용 가능
