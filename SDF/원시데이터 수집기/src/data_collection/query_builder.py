# DB 쿼리 생성
# 사용자는 자기가 원하는 칼럼들, 시작시간, end시간을 입력하면, 그에 맞는 쿼리를 return한다.

from typing import List

# 쿼리 생성
# 사용자는 자기가 원하는 칼럼들, 시작시간, end시간을 입력하면, 그에 맞는 쿼리를 return한다.
class QueryBuilder:
    def __init__(self, db_client):
        self.columns = []
        self.start_time = None
        self.end_time = None
        self.ts_join_mode = 'nearest'
        self.db_client = db_client

    def _build_column_select(self, columns: list, table_alias: str = 't') -> list:
        """컬럼 선택 리스트 생성 (타임존 변환 포함)
        
        Args:
            columns: 컬럼 이름 리스트
            table_alias: 테이블 별칭 (기본값: 't')
            
        Returns:
            타임존 변환이 적용된 컬럼 선택 리스트
        """
        column_selects = []
        timestamp_columns = ['ts', 'created_at']
        
        for col in columns:
            if col in timestamp_columns:
                # timestamp with time zone 타입: AT TIME ZONE 'Asia/Seoul'로 KST 변환
                column_selects.append(f"{table_alias}.{col} AT TIME ZONE 'Asia/Seoul' as {col}")
            else:
                column_selects.append(f"{table_alias}.{col}")
        
        return column_selects
    
    def add_column(self, column):
        self.columns.append(column)
    
    def set_time_range(self, start_time, end_time):
        self.start_time = start_time
        self.end_time = end_time

    def set_ts_join_mode(self, mode: str):
        if mode not in ('exact', 'nearest', 'nearest_within_60s', 'bucket'):
            raise ValueError("ts_join_mode는 'exact', 'nearest', 'nearest_within_60s' 또는 'bucket'만 지원합니다.")
        self.ts_join_mode = mode

    def set_bucket_seconds(self, bucket_seconds: int):
        if bucket_seconds <= 0:
            raise ValueError("bucket_seconds는 1 이상의 정수여야 합니다.")
        self.bucket_seconds = bucket_seconds

    def build_per_sensor(
        self,
        sensor_id: str,
        sensor_type: str,
        start_date: str,
        end_date: str,
        channel: str = None,
    ):
        # 한 센서의 데이터 쿼리 빌드

        #'sensor' 테이블로 센서의 데이터가 속한 테이블 이름을 'sensor_type'으로 알아낼 수 있음.
        #해당 테이블에서 'sensor_id'로 데이터를 조회

        #sensor_type에 따른 조회 컬럼들
        sensor_type_columns = {
            'anemometer': ['wind_speed', 'wind_direction'],
            'thermohygro': ['temp', 'humi'],
            'agsmotor_green' : ['open_rate'],
            'raindrop': ['rain'],
            'counter' : ['current_count', 'accumulated_count'],
            'amperemeter' : ['amp'],
            'temperature' : ['probe', 'temp'],
        }

        channel_exist_tables = ['agsmotor_green', 'temperature']

        columns = sensor_type_columns.get(sensor_type, [])
        columns = ['ts', 'site_id', 'sensor_id', 'created_at'] + columns
        
        # 채널 조건 추가
        channel_condition = ""
        if sensor_type in channel_exist_tables and channel is not None:
            columns.append('probe')
            channel_condition = f" and probe = {channel}"
        
        # 타임존 변환이 적용된 컬럼 선택 리스트 생성
        column_selects = self._build_column_select(columns, 't')
        
        # agsmotor_green은 facility_controls 테이블 사용, 다른 센서는 facility_devices 사용
        if sensor_type == 'agsmotor_green':
            data_query = f"""
            SELECT {', '.join(column_selects)}, COALESCE(fc.facility_id, NULL) as facility_id
            FROM {sensor_type} t
            LEFT JOIN sensors s ON t.sensor_id = s.sensor_id
            LEFT JOIN facility_controls fc ON s.device_id = fc.device_id 
                AND (s.channel_id IS NULL OR s.channel_id = fc.modbus)
                AND fc.payload LIKE '%\"{channel}\"%'
            WHERE t.sensor_id = '{sensor_id}'{channel_condition}
            AND ts BETWEEN '{start_date}' AND '{end_date}'
            ORDER BY ts
            """
        else:
            data_query = f"""
            SELECT {', '.join(column_selects)}, COALESCE(fd.facility_id, NULL) as facility_id
            FROM {sensor_type} t
            LEFT JOIN sensors s ON t.sensor_id = s.sensor_id
            LEFT JOIN facility_devices fd ON s.device_id = fd.device_id 
                AND (s.channel_id IS NULL OR s.channel_id = fd.modbus)
            WHERE t.sensor_id = '{sensor_id}'{channel_condition}
            AND ts BETWEEN '{start_date}' AND '{end_date}'
            ORDER BY ts
            """
        
        return data_query
        
     
    def build(
        self,
        sensor_ids: List[str],
        start_date: str,
        end_date: str,
    ):
        # 여러 센서의 데이터 쿼리 빌드 로직 구현
        sensor_id_to_type = {}
        try:
            # sensor_ids에서 순수 sensor_id만 추출하여 sensor_type 조회
            pure_sensor_ids = []
            for s_id in sensor_ids:
                if ':' in s_id:
                    sensor_id, _ = s_id.split(':', 1)
                    pure_sensor_ids.append(sensor_id)
                else:
                    pure_sensor_ids.append(s_id)
            
            sensor_id_to_type = {row['sensor_id']: row['sensor_type'] for row in self.db_client.execute_sensor_types_query(pure_sensor_ids)}
        except Exception as e:
            print(f"sensor_type 조회 중 오류: {e}")
            sensor_id_to_type = {}

        sensor_queries = []
        for s_id in sensor_ids:
            # 센서 ID와 채널 분리
            if ':' in s_id:
                sensor_id, channel = s_id.split(':', 1)
            else:
                sensor_id = s_id
                channel = None
                
            s_type = sensor_id_to_type.get(sensor_id, 'unknown')
            query_result = self.build_per_sensor(sensor_id, s_type, start_date, end_date, channel)
            sensor_queries.append(query_result)

        return sensor_queries