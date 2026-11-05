# pip
import pandas as pd
from pandas.api import types as ptypes
import matplotlib.pyplot as plt
import json

# src
import settings
import db

analyzer_id = settings.JF_ANALYZER_ID
graph_id = settings.JF_GRAPH_ID
graph_type = settings.JF_GRAPH_TYPE
file_path = settings.JF_POD_DATA_PATH
column = settings.JF_COLUMN

# 컬럼 목록 API(apps/fb_option/src/option/service.py)와 동일한 인코딩 폴백.
# 같은 방식으로 읽어야 사용자가 고른 컬럼명이 그대로 매칭된다.
ENCODINGS_TO_TRY = ['utf-8', 'cp949', 'latin1', 'ISO-8859-1', 'cp1252']

def read_csv_with_fallback(path):
    last_error = None
    for encoding in ENCODINGS_TO_TRY:
        try:
            df = pd.read_csv(path, engine='python', encoding=encoding, on_bad_lines='skip')
            if len(df.columns) > 0:
                return df
        except Exception as error:
            last_error = error
    raise last_error if last_error else ValueError(f"cannot read csv: {path}")

def main():
    # data read =============================================
    df = read_csv_with_fallback(file_path)

    # x, y 추출 =============================================
    series = df[column]
    # 연속형 데이터
    if ptypes.is_numeric_dtype(series) and not ptypes.is_bool_dtype(series):
        value_counts = series.value_counts().sort_index()
        x = value_counts.index.tolist()  # 고유값 (x축)
    # 범주형 데이터 (object/str/category/bool/datetime)
    else:
        value_counts = series.value_counts()
        x = [str(value) for value in value_counts.index]  # 범주 값 (x축)
    y = value_counts.values.tolist()  # 빈도수 (y축)

    # 파이차트일 경우, 빈도수 -> 비율전환
    if graph_type == "pie" and y:
        total = sum(y)
        tmp_y = y
        y = [round(value / total * 100, 2) for value in tmp_y]
        difference = 100 - sum(y)  # 100%에서의 차이
        y[-1] += round(difference, 2)  # 마지막 값에 차이를 더함

    # DB저장 =============================================
    graph_data = {'x' : x, 'y' : y}
    db.update_analyzer_graph_sync(graph_id=graph_id, graph_data=json.dumps(graph_data))


main()