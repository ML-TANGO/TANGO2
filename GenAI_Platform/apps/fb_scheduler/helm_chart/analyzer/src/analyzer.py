# pip
import pandas as pd
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

def main():
    # data read =============================================
    df = pd.read_csv(file_path)

    # x, y 추출 =============================================
    x = []
    y = []
    # 연속형 데이터
    if df[column].dtype in ['int64', 'float64']:
        value_counts = df[column].value_counts().sort_index()
        x = value_counts.index.tolist()  # 고유값 (x축)
        y = value_counts.values.tolist()  # 빈도수 (y축)
    # 범주형 데이터
    elif df[column].dtype == 'object' or df[column].dtype.name == 'category':
        value_counts = df[column].value_counts()
        x = value_counts.index.tolist()  # 범주 값 (x축)
        y = value_counts.values.tolist()  # 빈도수 (y축)

    # 파이차트일 경우, 빈도수 -> 비율전환
    if graph_type == "pie":
        total = sum(y)
        tmp_y = y
        y = [round(value / total * 100, 2) for value in tmp_y]
        difference = 100 - sum(y)  # 100%에서의 차이
        y[-1] += round(difference, 2)  # 마지막 값에 차이를 더함

    # DB저장 =============================================
    graph_data = {'x' : x, 'y' : y}
    db.update_analyzer_graph_sync(graph_id=graph_id, graph_data=json.dumps(graph_data))


main()