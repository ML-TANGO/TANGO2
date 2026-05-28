# Software-defined Ship (SDS) 학습 데이터 - 3차 데이터

에이브노틱스가 제공하는 3차 데이터셋의 주요 목적은 동일한 데이터에 대한 항해상황묘사 및 항해조언 텍스트를 제공하는 것입니다.

본 데이터 생성 시 시뮬레이션은 항해 규칙 교과서의 예시를 기준으로 충돌상황 판단에 대한 사례 상황을 기반으로 만들어졌습니다.

데이터 폴더 이름의 timestamp는 실세계 시간 기반이고, input_data 내 timestamp는 가상세계 시간 기반입니다.

## 개별 데이터 구조

이번 데이터는 학습결과 평가 및 판단에 용이하도록 한국어/영어를 지원하도록 만들었습니다. 더불어 항해조언의 경우 compact 형태도 추가 작성 되었습니다.

### 데이터 폴더 이름 규칙
~~~
{proj}-{source}-{label}-{yyyymmdd}-v{major.minor}-{shortid}
~~~

1. **proj / task**: 프로젝트/태스크 (예: tango_sds)
2. **source / domain**: 데이터 출처/도메인 (예: unity)
3. **label**: 레이블 여부 (안된 경우 none, GPT로 레이블된 경우 llm, 사람이 한 경우 expert)
4. **date**: 생성 날짜 (최소 yyyymmdd)
5. **version**: 의미 있는 변경 시 증가 - 예:0.3
6. **shortid**: 충돌 방지용 8자 해시

### 데이터 폴더 구조

- input_image.png: Unity3D 시뮬레이터에서 특정 상황에 대해 캡쳐된 이미지 화면. 해상도는 1920 × 1080.
- input_data.csv: 캡쳐된 이미지 화면 내 선박에 대한 데이터(자선, 타선 포함). 모든 이미지에 대한 데이터를 담고 있음.
- output_describe_en.txt: 영문 항해상황묘사
- output_describe_kor.txt: 국문 항해상황묘사
- output_advice_en.txt: 영문 항해조언
- output_advice_kor.txt: 국문 항해조언
- output_advice_compact.txt: 간소화한 국문 항해조언

### input_data.csv 데이터 형식

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
