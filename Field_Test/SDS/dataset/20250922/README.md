# Software-defined Ship (SDS) 학습 데이터 - 1차 데이터

에이브노틱스가 제공하는 1차 데이터셋의 주요 목적은 학습 데이터의 초기 사양을 정의하고 모델의 1차 학습 결과 생성을 위한 데이터를 제공하는 것입니다.

## 폴더 구조

- datasetN: 데이터 캡쳐를 수행한 특정 시퀀스
    - frame_N.png: 1분 주기로 캡쳐된 이미지 화면, N 크기가 커질수록 N분 후 상황임. 해상도는 1024 x 768.
    - input.csv: 캡쳐된 이미지 화면 내 선박에 대한 데이터. 모든 이미지에 대한 데이터를 담고 있음.
    - output.csv: 캡쳐된 이미지 화면에 대한 라벨링 데이터
    - ImageWithBBox: 캡쳐된 이미지 화면에 대한 바운딩박스 시각화 데이터용 폴더 (참고용)

### input.csv 데이터 형식

- file_name: 선박 데이터가 담긴 이미지 파일 이름
- timestamp: 이미지가 촬영·수집된 시간
- ship_id: 선박 고유 식별 ID (현재는 int, 추후 변경 가능)
- my_ship: 자선 여부 (1이면 자선, 0이면 아님)
- ship_type: 선박 종류 
- length: 선박 길이
- width: 선박 폭
- draft: 선박의 흘수(수면 아래 잠긴 깊이)
- latitude: 선박 위치의 위도 좌표
- longitude: 선박 위치의 경도 좌표
- knot: 선박 속력(노트 단위)
- heading: 선박 진행 방향(방위각)
- bbox_x: 이미지 내 바운딩 박스 좌상단 X좌표
- bbox_y: 이미지 내 바운딩 박스 좌상단 Y좌표
- bbox_width: 바운딩 박스의 가로 길이
- bbox_height: 바운딩 박스의 세로 길이

### output.csv 데이터 형식

- file_name: 선박 데이터가 담긴 이미지 파일 이름
- text: 이미지 파일에 대한 항해 맥락적 상황인식 서술