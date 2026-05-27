## 추후 train 프로젝트에 본 코드가 합병될 예정입니다

2_anal_every_csv.py는 시각화 분석용입니다. 실행하지 않아도 됩니다.

실제로 데이터가 들어오게 되면, 다음과 같은 순서로 돌리면 됩니다.


- 들어온 Json데이터를 csv로 변환 (추후 들어오는 데이터 자체가 csv로 올 것이므로, 나중엔 이 부분 삭제 예정)
1_json_to_csv_all.py
-> csv_data 디렉토리에 결과물 출력

- 변환된 csv에 센서타입 칼럼 추가 (추후 들어오는 데이터 자체에 센서타입이 포함되어 들어오면 이 부분 삭제 예정)
0_add_sensor_type.py
-> csv_data_with_sensor_type 디렉토리에 결과물 출력

- 공통적으로 데이터가 유요한 구간을 파악
3_get_validate_area.py
-> valid_time_ranges  디렉토리에 결과물 출력

- 유효한 데이터 구간만 가져옴
4_get_valid_data.py
-> valid_data 디렉토리에 결과물 출력

- 각 분 00초로 데이터를 맞춤
5_time_sync.py
-> time_sync_valid_data 디렉토리에 결과물 출력

- 맞춰진 시간 칼럼을 기준으로 데이터 병합
6_merge_data.py
-> merged_data 디렉토리에 결과물 출력

- 병합된 데이터 후처리(적산온도 등)
7_postprocess_merged_data.py
-> merged_data_postprocessed 디렉토리에 결과물 출력
