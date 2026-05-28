import pandas as pd
from src.utils import COLUMN_CONDITION, COLUMN_LIST


def to_datetime_index(df: pd.DataFrame, time_col: str) -> pd.DataFrame:
    if time_col not in df.columns:
        raise ValueError(f"time_col이 df에 없습니다: {time_col}")

    result = df.copy()
    # ISO8601 형식과 다양한 시간 형식을 처리하기 위해 format='mixed' 사용
    result[time_col] = pd.to_datetime(result[time_col], format='mixed')
    result = result.sort_values(time_col)
    result = result.set_index(time_col)
    
    # 중복된 인덱스가 있는 경우 마지막 값만 유지
    if result.index.duplicated().any():
        result = result[~result.index.duplicated(keep='last')]
    
    return result


def resample_time_index(df: pd.DataFrame, freq: str, agg: str = "mean") -> pd.DataFrame:
    if not isinstance(df.index, pd.DatetimeIndex):
        raise ValueError("df.index는 DatetimeIndex여야 합니다")

    if agg == "mean":
        return df.resample(freq).mean(numeric_only=True)
    if agg == "first":
        return df.resample(freq).first()
    if agg == "last":
        return df.resample(freq).last()

    raise ValueError("agg는 'mean'|'first'|'last'만 지원합니다")


def merge_asof_nearest(
    left: pd.DataFrame,
    right: pd.DataFrame,
    tolerance: str = "60s",
    suffix: str | None = None,
) -> pd.DataFrame:
    if not isinstance(left.index, pd.DatetimeIndex) or not isinstance(right.index, pd.DatetimeIndex):
        raise ValueError("left/right index는 DatetimeIndex여야 합니다")

    left_sorted = left.sort_index().reset_index(names="_ts")
    right_sorted = right.sort_index().reset_index(names="_ts")

    merged = pd.merge_asof(
        left_sorted,
        right_sorted,
        on="_ts",
        direction="nearest",
        tolerance=pd.Timedelta(tolerance),
        suffixes=("", f"_{suffix}" if suffix else "_r"),
    )
    merged = merged.set_index("_ts")
    merged.index.name = None
    return merged
    


def adjust_to_edge_value(col_name: str, value):
    """값을 범위의 경계값으로 조정"""
    if col_name not in COLUMN_CONDITION:
        col_name = "default"
    min_val = COLUMN_CONDITION[col_name]["min"]
    max_val = COLUMN_CONDITION[col_name]["max"]
    if value < min_val:
        return min_val
    elif value > max_val:
        return max_val
    else:
        return value

def general_linear_interpolation(time_index, column: pd.Series) -> pd.Series:
    """일반적인 선형 보간을 적용"""
    result_col = column.copy()

    # 데이터 점이 2개 미만이면 선형 보간(기울기 계산)이 불가능하므로 앞의 값으로 채움
    if len(result_col) < 2:
        result_col = result_col.reindex(time_index, method='ffill')
        return result_col
        
    # 중복 인덱스 제거 (가장 마지막 값 유지)
    if result_col.index.duplicated().any():
        result_col = result_col[~result_col.index.duplicated(keep='last')]
        
    # 1. 원본 데이터 인덱스와 1분 단위 인덱스 병합 (시간 간격 기준점 확보)
    combined_index = result_col.index.union(time_index).sort_values().drop_duplicates()
    
    # 2. 통합 인덱스 기준으로 시리즈 재배치 (1분 인덱스 자리는 우선 NaN으로 들어감)
    temp_series = result_col.reindex(combined_index)
    
    # 3. 시간 비례 선형 보간 및 끝점 외삽(Extrapolation) 일괄 처리
    interpolated = temp_series.interpolate(method='slinear', fill_value='extrapolate', limit_direction='both')

    result_col = interpolated.reindex(time_index)
    return result_col

def out_wind_direction_interpolation(time_index, column: pd.Series) -> pd.Series:
    """out_wind_direction 컬럼의 특별한 보간을 적용"""
    result_col = column.copy()
    
    # 중복 인덱스 제거 (가장 마지막 값 유지)
    if result_col.index.duplicated().any():
        result_col = result_col[~result_col.index.duplicated(keep='last')]
    
    # 1. 원본 데이터 인덱스와 1분 단위 인덱스 병합 (시간 간격 기준점 확보)
    combined_index = result_col.index.union(time_index).sort_values().drop_duplicates()
    
    # 2. 통합 인덱스 기준으로 시리즈 재배치 (1분 인덱스 자리는 우선 NaN으로 들어감)
    temp_series = result_col.reindex(combined_index)
    
    # 3. 시간 비례 각도 변화를 실제 각도 변화가 작은 방향으로 보정
    # 350 -> 30 일 때, 350, 340, 330, ..., 40, 30 이 아닌 350, 0, 10, 20, 30 으로 보정
    interpolated = temp_series.copy()
    
    # 유효한 데이터 포인트 찾기
    valid_mask = interpolated.notna()
    valid_indices = interpolated[valid_mask].index
    
    if len(valid_indices) < 2:
        # 유효한 데이터가 2개 미만이면 선형 보간 불가, forward fill
        interpolated = interpolated.ffill().bfill()
    else:
        # 각 구간에 대해 원형 보간 수행
        for i in range(len(valid_indices) - 1):
            start_idx = valid_indices[i]
            end_idx = valid_indices[i + 1]
            
            start_val = interpolated.loc[start_idx]
            end_val = interpolated.loc[end_idx]
            
            # 두 각도 사이의 최단 경로 계산
            diff = end_val - start_val
            
            # 차이가 180도보다 크면 반대 방향으로 보정
            if abs(diff) > 180:
                if diff > 0:
                    # 정방향이 너무 크면 역방향으로 조정
                    end_val_adj = end_val - 360
                else:
                    # 역방향이 너무 크면 정방향으로 조정
                    end_val_adj = end_val + 360
                
                diff_adj = end_val_adj - start_val
                
                # 보간할 인덱스 찾기
                interp_mask = (interpolated.index > start_idx) & (interpolated.index < end_idx)
                interp_indices = interpolated.index[interp_mask]
                
                if len(interp_indices) > 0:
                    # 시간 비례로 선형 보간
                    start_time = start_idx
                    end_time = end_idx
                    
                    for interp_idx in interp_indices:
                        # 시간 비례 계수 계산
                        time_ratio = (interp_idx - start_time) / (end_time - start_time)
                        # 보간값 계산
                        interp_val = start_val + diff_adj * time_ratio
                        
                        # 0-360 범위로 정규화
                        interp_val = interp_val % 360
                        interpolated.loc[interp_idx] = interp_val
            else:
                # 일반적인 경우는 선형 보간 사용
                interp_mask = (interpolated.index > start_idx) & (interpolated.index < end_idx)
                interp_indices = interpolated.index[interp_mask]
                
                if len(interp_indices) > 0:
                    start_time = start_idx
                    end_time = end_idx
                    
                    for interp_idx in interp_indices:
                        time_ratio = (interp_idx - start_time) / (end_time - start_time)
                        interp_val = start_val + diff * time_ratio
                        interpolated.loc[interp_idx] = interp_val
        
        # 나머지 NaN 값은 선형 보간으로 채우기
        interpolated = interpolated.interpolate(method='slinear', fill_value='extrapolate', limit_direction='both')

    result_col = interpolated.reindex(time_index)
    return result_col

def col_specific_linear_interpolation(time_index, column: pd.Series) -> pd.Series:
    """특정 컬럼의 특징에 기반한 보간을 적용"""
    COLUMN_TO_FUNC = {
        # 예시: 특정 컬럼에만 특별한 처리를 하고 싶을 때
        # 'column_name': lambda x: x.interpolate(method='linear')
        'out_wind_direction': out_wind_direction_interpolation,
        "default": general_linear_interpolation
    }
    col_func = COLUMN_TO_FUNC.get(column.name, general_linear_interpolation)
    result = col_func(time_index, column)
    result = result.apply(lambda x: adjust_to_edge_value(column.name, x))
    return result

def resample_to_minute(df: pd.DataFrame, agg: str = "first", fill_method: str = "nearest") -> pd.DataFrame:
    """데이터를 분 단위로 리샘플링하고 빈 값을 채움"""
    if not isinstance(df.index, pd.DatetimeIndex):
        raise ValueError("df.index는 DatetimeIndex여야 합니다")
    
    # 분 단위로 리샘플링 (1min = 1 minute)
    resampled = df.resample('1min')
    
    if agg == "mean":
        result = resampled.mean(numeric_only=True)
    elif agg == "first":
        result = resampled.first()
    elif agg == "last":
        result = resampled.last()
    elif agg == "max":
        result = resampled.max()
    elif agg == "min":
        result = resampled.min()
    else:
        raise ValueError("agg는 'mean', 'first', 'last', 'max', 'min'만 지원합니다")
    
    # 빈 값 채우기
    if fill_method == "nearest":
        # 가장 가까운 시간의 값으로 채우기 (앞뒤 모두 확인)
        # 수치형 컬럼만 보간 처리
        numeric_cols = result.select_dtypes(include=['number']).columns
        if len(numeric_cols) > 0:
            result[numeric_cols] = result[numeric_cols].interpolate(method='nearest')
    elif fill_method == "linear":
        # 선형 보간: 원본 데이터를 직접 보간하여 데이터 손실 방지
        numeric_cols = df.select_dtypes(include=['number']).columns
        categorical_cols = df.select_dtypes(exclude=['number']).columns
        
        # 분 단위 시간 인덱스 생성 (원본 범위의 모든 분)
        min_time = df.index.min()
        max_time = df.index.max()
        minute_index = pd.date_range(start=min_time.floor('1min'), end=max_time.ceil('1min'), freq='1min')
        
        # 새로운 결과 데이터프레임 생성
        result = pd.DataFrame(index=minute_index)
        
        # 수치형 컬럼은 시간 기반 선형 보간
        for col in numeric_cols:
            # 결측치를 제외한 유효한 원본 데이터만 추출
            valid_data = df[col].dropna()

            result[col] = col_specific_linear_interpolation(minute_index, valid_data)
        
        # 범주형 컬럼은 forward fill
        for col in categorical_cols:
            original_series = df[col]
            resampled_series = original_series.resample('1min')
            # 중복된 인덱스가 있는 경우 처리
            resampled_filled = resampled_series.ffill()
            if len(resampled_filled.index) != len(resampled_filled.index.unique()):
                # 중복된 인덱스가 있는 경우, 마지막 값만 유지
                resampled_filled = resampled_filled[~resampled_filled.index.duplicated(keep='last')]
            result[col] = resampled_filled.reindex(minute_index)
            
    elif fill_method == "forward":
        # 이전 값으로 채우기
        result = result.fillna(method='ffill')
    elif fill_method == "backward":
        # 다음 값으로 채우기
        result = result.fillna(method='bfill')
    elif fill_method == "both":
        # 앞으로 채우고, 그래도 비어있으면 뒤로 채우기
        result = result.fillna(method='ffill').fillna(method='bfill')
    elif fill_method == "none":
        # 채우지 않음
        pass
    else:
        raise ValueError("fill_method는 'nearest', 'linear', 'forward', 'backward', 'both', 'none'만 지원합니다")
    
    return result

def get_common_valid_minutes(
    frames: dict[str, pd.DataFrame],
    time_cols: dict[str, str],
    motor_tables: list[str],
    motor_threshold: str = "5min",  # 모터 관련 테이블 허용 간격
    sensor_threshold: str = "10min" # 그 외 센서 테이블 허용 간격
) -> pd.DatetimeIndex:
    """
    테이블별로 다른 임계값(threshold)을 적용하여, 
    데이터가 유실되지 않은 유효한 구간들을 파악한 후, 
    모든 테이블이 '공통으로' 존재하는 1분 단위 시점(교집합)만 추출합니다.
    """
    valid_minute_sets = []

    for key, df in frames.items():
        if df.empty:
            return pd.DatetimeIndex([]) # 하나라도 데이터가 없으면 교집합도 없음

        time_col = time_cols.get(key)
        if time_col not in df.columns:
            raise ValueError(f"'{key}' 데이터프레임에 time_col이 없습니다: {time_col}")

        # 1. 실제 데이터의 시간 추출 및 정렬
        ts = pd.to_datetime(df[time_col], format='mixed').dropna().sort_values()
        if ts.empty:
            return pd.DatetimeIndex([])

        # 2. 테이블 성격에 따른 동적 Threshold 설정
        threshold = pd.Timedelta(motor_threshold if key in motor_tables else sensor_threshold)

        # 3. 해당 테이블의 전체 탐색 범위(분 단위) 생성
        min_min = ts.min().floor('1min')
        max_min = ts.max().ceil('1min')
        minute_idx = pd.date_range(start=min_min, end=max_min, freq='1min')

        # 4. 각 1분(minute) 시점을 기준으로, 앞뒤로 가장 가까운 실제 원본 데이터 시점 탐색
        df_minutes = pd.DataFrame({'minute': minute_idx})
        df_ts = pd.DataFrame({'ts': ts})

        # backward: 현재 1분 시점 기준, 과거 방향으로 가장 최근에 기록된 실제 시간 (last_seen)
        fwd = pd.merge_asof(df_minutes, df_ts.rename(columns={'ts': 'last_seen'}),
                            left_on='minute', right_on='last_seen', direction='backward')

        # forward: 현재 1분 시점 기준, 미래 방향으로 가장 가까이 다가올 실제 시간 (next_seen)
        bwd = pd.merge_asof(df_minutes, df_ts.rename(columns={'ts': 'next_seen'}),
                            left_on='minute', right_on='next_seen', direction='forward')

        # 5. 유효성 검증 로직
        # 원본 데이터 간의 간격(next_seen - last_seen)이 Threshold 이내인 구간에 포함된 분(minute)만 True
        gap = bwd['next_seen'] - fwd['last_seen']
        valid_mask = (gap <= threshold) & fwd['last_seen'].notna() & bwd['next_seen'].notna()

        # 유효한 분(minute)들만 Set으로 저장
        valid_minutes = fwd.loc[valid_mask, 'minute']
        valid_minute_sets.append(set(valid_minutes))

    if not valid_minute_sets:
        return pd.DatetimeIndex([])

    # 6. 모든 테이블에서 판별된 유효 시간의 완전한 교집합(Intersection) 추출
    common_minutes = set.intersection(*valid_minute_sets)

    # 7. 교집합 결과를 정렬된 DatetimeIndex로 반환 (중간에 이빨이 빠져있으므로 freq=None)
    return pd.DatetimeIndex(sorted(list(common_minutes)), freq=None)

def align_time_series(
    frames: dict[str, pd.DataFrame],
    time_cols: dict[str, str],
    base_key: str,
    tolerance: str = "100s",
    resample_to_min: bool = True,
    minute_agg: str = "first",
    fill_method: str = "linear",
) -> pd.DataFrame:
    if base_key not in frames:
        raise ValueError(f"base_key가 frames에 없습니다: {base_key}")
    if base_key not in time_cols:
        raise ValueError(f"base_key의 time_col이 지정되지 않았습니다: {base_key}")

    # 모든 데이터프레임을 시간 인덱스로 변환
    processed_frames = {}
    all_time_ranges = []
    
    # common_time_index = get_common_valid_minutes(frames, time_cols, fill_method)

    for key, df in frames.items():
        print(f"******{key}*****")
        if key not in time_cols:
            raise ValueError(f"time_cols에 key가 없습니다: {key}")
        
        # 시간 인덱스로 변환
        time_indexed = to_datetime_index(df, time_cols[key])
        
        # 분 단위로 리샘플링 (요청된 경우)
        print("fill_method:", fill_method)
        if resample_to_min:
            time_indexed = resample_to_minute(time_indexed, agg=minute_agg, fill_method=fill_method)
        
        processed_frames[key] = time_indexed
        
        # 모든 테이블의 시간 범위 수집
        if len(time_indexed) > 0:
            all_time_ranges.append(time_indexed.index)
    
    # 모든 테이블의 전체 시간 범위 계산
    if all_time_ranges:
        min_time = min(rng.min() for rng in all_time_ranges)
        max_time = max(rng.max() for rng in all_time_ranges)
        full_time_range = pd.date_range(start=min_time, end=max_time, freq='1min')
    else:
        raise ValueError("처리할 데이터가 없습니다")

    # 기준 테이블 설정
    base = processed_frames[base_key]
    
    # 기준 테이블을 전체 시간 범위로 확장
    base_extended = base.reindex(full_time_range)
    
    # 다른 테이블들과 병합
    merged = base_extended
    for key, df in processed_frames.items():
        if key == base_key:
            continue
        
        # 다른 테이블도 전체 시간 범위로 확장
        df_extended = df.reindex(full_time_range)
        merged = merge_asof_nearest(merged, df_extended, tolerance=tolerance, suffix=key)

    return merged
