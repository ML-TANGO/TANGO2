# 기상청 API 호출 및 텍스트 원본 수집
import re
import requests
import yaml
import pandas as pd

import logging
import os
import time
from typing import Dict, Any, Optional
from string import Template
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv

class WeatherAPIClient:
    """기상청 지상관측 API 클라이언트"""
    
    def __init__(self):
        """
        기상청 API 클라이언트 초기화
        
        Args:
            config_path: 설정 파일 경로
        """
        load_dotenv()
        self.session = requests.Session()
        self.session.timeout = int(os.environ.get("WEATHER_API_TIMEOUT"))
        self.logger = self._setup_logger()

    def _setup_logger(self) -> logging.Logger:
        """로거 설정"""
        logger = logging.getLogger(__name__)
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(
                getattr(logging, 
                    os.environ.get("LOGGING_LEVEL", "INFO"))
            )
        return logger
    
    def get_long_term_weather_data(self, start_datetime: str, end_datetime: str, station_id: int = 0) -> str:
        """
        기상청 지상관측 데이터 조회 (기간 조회)
        Args:
            start_datetime: 조회 시작 시각 (YYYYMMDDHHMI 형식)
            end_datetime: 조회 종료 시각 (YYYYMMDDHHMI 형식)
            station_id: 지점번호 (0: 전체, 기본값: 0)
        """
        # 문자열을 datetime 객체로 변환
        try:
            start_dt = datetime.strptime(start_datetime, "%Y%m%d%H%M")
            end_dt = datetime.strptime(end_datetime, "%Y%m%d%H%M")
        except ValueError as e:
            raise ValueError(f"날짜 형식이 올바르지 않습니다. (YYYYMMDDHHMI) - {e}")

        if start_dt > end_dt:
            raise ValueError("시작 시각은 종료 시각보다 이후일 수 없습니다.")

        # 한 달(31일) 이하이면 단기 조회 한 번으로 처리
        if (end_dt - start_dt).days <= 31:
            return self.get_short_term_weather_data(start_datetime, end_datetime, station_id)

        # 한 달을 초과하면 31일 단위로 나누어 여러 번 호출 후 결과를 이어붙임
        current_start = start_dt
        combined_text_parts: list[str] = []

        while current_start <= end_dt:
            current_end = min(current_start + timedelta(days=31), end_dt)

            part_start_str = current_start.strftime("%Y%m%d%H%M")
            part_end_str = current_end.strftime("%Y%m%d%H%M")

            self.logger.info(
                f"장기 기간 조회를 위한 분할 호출: "
                f"{part_start_str} ~ {part_end_str} (stn={station_id})"
            )

            part_text = self.get_short_term_weather_data(
                part_start_str,
                part_end_str,
                station_id,
            )
            combined_text_parts.append(part_text)

            # 다음 구간 시작 시각은 현재 구간 종료 시각 이후 1분으로 설정
            current_start = current_end + timedelta(minutes=1)

        combined_text = "\n".join(combined_text_parts)

        text_output_dir = Path("pipeline_output/kma_data/text")
        text_output_dir.mkdir(parents=True, exist_ok=True)
        start_token = start_datetime[:8]
        end_token = end_datetime[:8]
        text_filename = f"kma_{station_id}_{start_token}_{end_token}.txt"
        text_path = text_output_dir / text_filename

        with text_path.open("w", encoding="utf-8") as f:
            f.write(combined_text)

        self.parse_kma_text_to_dataframe(
            combined_text,
            station_id=station_id,
            start_datetime=start_datetime,
            end_datetime=end_datetime,
        )

        return combined_text
    
    
    
    def get_short_term_weather_data(self, start_datetime: str, end_datetime: str, station_id: int = 0) -> str:
        """
        기상청 지상관측 데이터 조회 (기간 조회)
        한번에 최대로 가져올 수 있는 데이터는 1달 단위임
        Args:
            start_datetime: 조회 시작 시각 (YYYYMMDDHHMI 형식)
            end_datetime: 조회 종료 시각 (YYYYMMDDHHMI 형식)
            station_id: 지점번호 (0: 전체, 기본값: 0)
            
        Returns:
            API 응답 텍스트 데이터
        """
        # 문자열을 datetime 객체로 변환
        try:
            start_dt = datetime.strptime(start_datetime, "%Y%m%d%H%M")
            end_dt = datetime.strptime(end_datetime, "%Y%m%d%H%M")
        except ValueError as e:
            raise ValueError(f"날짜 형식이 올바르지 않습니다. (YYYYMMDDHHMI) - {e}")

        # 한달보다 긴 기간인지 확인하고, 길면 에러
        if (end_dt - start_dt).days > 31:
            raise ValueError("한달보다 긴 기간은 조회할 수 없습니다")

        # KMA 지상관측 API 엔드포인트 및 파라미터 구성
        url = "https://apihub.kma.go.kr/api/typ01/url/kma_sfctm3.php"
        params = {
            "tm1": start_datetime,
            "tm2": end_datetime,
            "stn": station_id,
            "authKey": os.environ.get("WEATHER_API_SERVICE_KEY"),
        }

        # 기상청 API는 최대 max_retries회 재시도
        max_retries = 5
        delay_seconds = 1

        for attempt in range(1, max_retries + 1):
            try:
                response = self.session.get(
                    url,
                    params=params,
                    timeout=self.session.timeout,
                )

                if response.status_code == 200:
                    # 응답 인코딩 설정 후 텍스트 확보
                    if not response.encoding:
                        response.encoding = response.apparent_encoding or "utf-8"
                    text = response.text

                    # 원본 TXT를 파일로 저장
                    text_output_dir = Path("pipeline_output/kma_data/text")
                    text_output_dir.mkdir(parents=True, exist_ok=True)
                    start_token = start_datetime[:8]
                    end_token = end_datetime[:8]
                    text_filename = f"kma_{station_id}_{start_token}_{end_token}.txt"
                    text_path = text_output_dir / text_filename

                    with text_path.open("w", encoding="utf-8") as f:
                        f.write(text)

                    # TXT를 바로 파싱하여 CSV도 생성
                    self.parse_kma_text_to_dataframe(
                        text,
                        station_id=station_id,
                        start_datetime=start_datetime,
                        end_datetime=end_datetime,
                    )

                    # 호출자에게는 원본 텍스트를 그대로 반환
                    return text

                self.logger.warning(
                    f"기상청 API 응답 코드 비정상: {response.status_code}, "
                    f"본문 일부: {response.text[:200]!r}"
                )

            except requests.RequestException as e:
                self.logger.error(f"기상청 API 호출 실패 (시도 {attempt}/{max_retries}): {e}")

            # 마지막 시도가 아니면 대기 후 재시도
            if attempt < max_retries:
                time.sleep(delay_seconds)

        raise RuntimeError("기상청 API 호출이 최대 재시도 횟수(5회)를 초과하여 실패했습니다.")
    
        
        def get_available_stations(self) : 
            """
            전국 지상관측소 정보 반환
            
            Returns:
                지점번호: 지점명 딕셔너리
            """

    # def get_available_stations(self) -> Dict[int, str]:
    #     """
    #     전국 지상관측소 정보 반환
        
    #     Returns:
    #         지점번호: 지점명 딕셔너리
    #     """
    #     return {station_id: info["name_ko"] for station_id, info in WEATHER_STATIONS.items()}
    
    # def get_station_info(self, station_id: int) -> Optional[Dict[str, Any]]:
    #     """
    #     특정 지점의 상세 정보 반환
        
    #     Args:
    #         station_id: 지점번호
            
    #     Returns:
    #         지점 정보 딕셔너리 (없으면 None)
    #     """
    #     return WEATHER_STATIONS.get(station_id)
    
    # def get_stations_by_region(self, region: str) -> Dict[int, str]:
    #     """
    #     지역별 지점 정보 반환
        
    #     Args:
    #         region: 지역명 (수도권, 강원, 충청, 전라, 경상, 제주)
            
    #     Returns:
    #         지점번호: 지점명 딕셔너리
    #     """
    #     station_ids = REGION_STATIONS.get(region, [])
    #     return {sid: WEATHER_STATIONS[sid]["name_ko"] for sid in station_ids if sid in WEATHER_STATIONS}
    
    def parse_kma_text_to_dataframe(
        self,
        text: str,
        station_id: Optional[int] = None,
        start_datetime: Optional[str] = None,
        end_datetime: Optional[str] = None,
    ):
        """
        기상청 지상관측 TXT 응답 문자열을 파싱하여 DataFrame 으로 변환하는 함수
        - 헤더/데이터 모두 1칸 이상 공백을 딜리미터로 사용
        - 헤더에 있는 모든 컬럼을 그대로 CSV 컬럼으로 사용
        
        Args:
            text (str): 기상청 API에서 받은 원본 텍스트
        
        Returns:
            pandas.DataFrame: 파싱된 데이터프레임
        """
        print("기상청 TXT 파싱 시작 (in-memory text)")
        
        data_rows = []
        columns: Optional[list[str]] = None
        
        for line_num, line in enumerate(text.splitlines(), 1):
            raw_line = line
            line = line.strip()
            
            if not line:
                continue
            
            # 헤더 라인 처리 (예: "# YYMMDDHHMI STN  WD  ...")
            if line.startswith("#"):
                if "YYMMDDHHMI" in line and columns is None:
                    header_part = line.lstrip("#").strip()
                    columns = re.split(r"\s+", header_part)
                continue
            
            # 컬럼 정의가 아직 없으면 스킵
            if columns is None:
                print(f"라인 {line_num}: 헤더 이전 데이터로 판단되어 스킵됨: {raw_line}")
                continue
            
            try:
                tokens = re.split(r"\s+", line)
                
                # 토큰 수가 컬럼 수보다 적으면 None 으로 패딩, 많으면 잘라냄
                if len(tokens) < len(columns):
                    tokens = tokens + [None] * (len(columns) - len(tokens))
                elif len(tokens) > len(columns):
                    tokens = tokens[: len(columns)]
                
                row = dict(zip(columns, tokens))
                data_rows.append(row)
            except Exception as e:
                print(f"라인 {line_num} 파싱 오류: {e} | 원본: {raw_line}")
                continue
        
        df = pd.DataFrame(data_rows)

        # CSV 저장 경로 구성
        # 인자로 station_id, start_datetime, end_datetime 이 반드시 주어진다고 가정
        stn_value = str(station_id)
        start_token = start_datetime[:8]
        end_token = end_datetime[:8]

        output_dir = Path("pipeline_output/kma_data/csv")
        output_dir.mkdir(parents=True, exist_ok=True)

        output_filename = f"kma_{stn_value}_{start_token}_{end_token}.csv"
        output_path = output_dir / output_filename

        df.to_csv(output_path, index=False)
        print(f"CSV 저장 완료: {output_path}")

        return df
