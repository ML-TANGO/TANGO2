import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy import stats
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import PolynomialFeatures
from sklearn.metrics import r2_score, mean_squared_error
import warnings
warnings.filterwarnings('ignore')

def analyze_solar_temp_relationship(df, date, smooth_segments):
    """
    특정 날짜의 자연스러운 곡선 구간에서 일조량-온도 관계 분석
    """
    daily_df = df[df['date_only'] == date].copy()
    daily_df = daily_df.sort_values('datetime')
    
    # 자연스러운 구간의 데이터만 추출
    smooth_data = []
    for segment in smooth_segments:
        start_idx = segment['start_idx']
        end_idx = segment['end_idx']
        segment_data = daily_df.iloc[start_idx:end_idx+1].copy()
        segment_data['segment_id'] = len(smooth_data) + 1
        smooth_data.append(segment_data)
    
    if not smooth_data:
        return None, None, None
    
    # 모든 자연스러운 구간 데이터 합치기
    smooth_df = pd.concat(smooth_data, ignore_index=True)
    
    # 유효한 데이터만 필터링 (NaN 제거)
    valid_data = smooth_df.dropna(subset=['kma_solar_irradiance', 'indoor_temperature'])
    
    if len(valid_data) < 10:  # 최소 데이터 포인트 확인
        return None, None, None
    
    # 일조량이 0인 데이터 필터링 (직전/직후에 일조량 > 0인 경우만 포함)
    filtered_data = []
    
    for i in range(len(valid_data)):
        current_solar = valid_data.iloc[i]['kma_solar_irradiance']
        
        if current_solar > 0:
            # 일조량이 0보다 크면 항상 포함
            filtered_data.append(valid_data.iloc[i])
        else:
            # 일조량이 0인 경우, 직전 또는 직후에 일조량 > 0인지 확인
            include_point = False
            
            # 직전 데이터 확인
            if i > 0:
                prev_solar = valid_data.iloc[i-1]['kma_solar_irradiance']
                if prev_solar > 0:
                    include_point = True
            
            # 직후 데이터 확인
            if i < len(valid_data) - 1:
                next_solar = valid_data.iloc[i+1]['kma_solar_irradiance']
                if next_solar > 0:
                    include_point = True
            
            if include_point:
                filtered_data.append(valid_data.iloc[i])
    
    if len(filtered_data) < 10:  # 필터링 후 최소 데이터 포인트 확인
        return None, None, None
    
    # 필터링된 데이터를 DataFrame으로 변환
    filtered_df = pd.DataFrame(filtered_data)
    
    return filtered_df, smooth_df, smooth_segments

def fit_temperature_models(solar_irradiance, indoor_temp, outdoor_temp=None, time_data=None):
    """
    일조량-온도 관계를 위한 여러 모델 피팅
    """
    models = {}
    
    # 1. 선형 모델 (일조량만)
    lr = LinearRegression()
    lr.fit(solar_irradiance.reshape(-1, 1), indoor_temp)
    models['linear'] = {
        'model': lr,
        'r2': r2_score(indoor_temp, lr.predict(solar_irradiance.reshape(-1, 1))),
        'mse': mean_squared_error(indoor_temp, lr.predict(solar_irradiance.reshape(-1, 1))),
        'equation': f"T = {lr.coef_[0]:.3f} * Solar + {lr.intercept_:.3f}"
    }
    
    # 2. 시간대별 선형 모델 (오전/오후 분리)
    if time_data is not None:
        morning_mask = np.array([(pd.to_datetime(t).hour < 14) for t in time_data])
        afternoon_mask = ~morning_mask
        
        if np.sum(morning_mask) >= 5:  # 최소 5개 데이터 포인트
            morning_solar = solar_irradiance[morning_mask]
            morning_temp = indoor_temp[morning_mask]
            lr_morning = LinearRegression()
            lr_morning.fit(morning_solar.reshape(-1, 1), morning_temp)
            models['linear_morning'] = {
                'model': lr_morning,
                'r2': r2_score(morning_temp, lr_morning.predict(morning_solar.reshape(-1, 1))),
                'mse': mean_squared_error(morning_temp, lr_morning.predict(morning_solar.reshape(-1, 1))),
                'equation': f"T = {lr_morning.coef_[0]:.3f} * Solar + {lr_morning.intercept_:.3f}",
                'time_period': 'Morning (00:00-13:59)'
            }
        
        if np.sum(afternoon_mask) >= 5:  # 최소 5개 데이터 포인트
            afternoon_solar = solar_irradiance[afternoon_mask]
            afternoon_temp = indoor_temp[afternoon_mask]
            lr_afternoon = LinearRegression()
            lr_afternoon.fit(afternoon_solar.reshape(-1, 1), afternoon_temp)
            models['linear_afternoon'] = {
                'model': lr_afternoon,
                'r2': r2_score(afternoon_temp, lr_afternoon.predict(afternoon_solar.reshape(-1, 1))),
                'mse': mean_squared_error(afternoon_temp, lr_afternoon.predict(afternoon_solar.reshape(-1, 1))),
                'equation': f"T = {lr_afternoon.coef_[0]:.3f} * Solar + {lr_afternoon.intercept_:.3f}",
                'time_period': 'Afternoon (14:00-23:59)'
            }
    
    # 2. 온도 차이 절댓값을 포함한 다중 선형 모델
    if outdoor_temp is not None:
        temp_diff_abs = np.abs(indoor_temp - outdoor_temp)
        # 다중 선형 회귀를 위한 특성 행렬 생성 [Solar, |ΔT|]
        X_multi = np.column_stack([solar_irradiance, temp_diff_abs])
        
        lr_multi = LinearRegression()
        lr_multi.fit(X_multi, indoor_temp)
        models['linear_multi'] = {
            'model': lr_multi,
            'r2': r2_score(indoor_temp, lr_multi.predict(X_multi)),
            'mse': mean_squared_error(indoor_temp, lr_multi.predict(X_multi)),
            'equation': f"T = {lr_multi.coef_[0]:.3f} * Solar + {lr_multi.coef_[1]:.3f} * |ΔT| + {lr_multi.intercept_:.3f}"
        }
        
    
    # 3. 변화량 모델 (Solar Irradiance Change vs Temperature Difference Change) - Solar ≤ 1.2만 사용
    if len(solar_irradiance) > 1 and outdoor_temp is not None:
        # Solar Irradiance ≤ 1.2인 데이터만 필터링
        solar_mask = solar_irradiance <= 1.2
        if np.sum(solar_mask) >= 6:  # 최소 6개 데이터 포인트 (변화량 계산을 위해)
            solar_filtered = solar_irradiance[solar_mask]
            indoor_temp_filtered = indoor_temp[solar_mask]
            outdoor_temp_filtered = outdoor_temp[solar_mask]
            
            # 온도 차이의 절댓값 계산
            temp_diff_abs = np.abs(indoor_temp_filtered - outdoor_temp_filtered)
            
            # 5분마다의 온도 차이 절댓값 변화량과 일조량 변화량 계산
            temp_diff_change = np.diff(temp_diff_abs)
            solar_change = np.diff(solar_filtered)
            
            if len(temp_diff_change) >= 5:  # 최소 5개 변화량 데이터 포인트
                lr_change = LinearRegression()
                lr_change.fit(solar_change.reshape(-1, 1), temp_diff_change)
                models['change_relationship'] = {
                    'model': lr_change,
                    'r2': r2_score(temp_diff_change, lr_change.predict(solar_change.reshape(-1, 1))),
                    'mse': mean_squared_error(temp_diff_change, lr_change.predict(solar_change.reshape(-1, 1))),
                    'equation': f"Δ|T_diff|/5min = {lr_change.coef_[0]:.3f} * ΔSolar/5min + {lr_change.intercept_:.3f}",
                    'description': 'Temperature Difference Change vs Solar Irradiance Change per 5min (Solar ≤ 1.2)',
                    'solar_filtered': solar_filtered,
                    'indoor_temp_filtered': indoor_temp_filtered,
                    'outdoor_temp_filtered': outdoor_temp_filtered,
                    'temp_diff_abs': temp_diff_abs
                }
    
    # 4. 로그 모델 (일조량 + 1을 로그 변환)
    log_solar = np.log(solar_irradiance + 1)
    lr_log = LinearRegression()
    lr_log.fit(log_solar.reshape(-1, 1), indoor_temp)
    models['logarithmic'] = {
        'model': lr_log,
        'r2': r2_score(indoor_temp, lr_log.predict(log_solar.reshape(-1, 1))),
        'mse': mean_squared_error(indoor_temp, lr_log.predict(log_solar.reshape(-1, 1))),
        'equation': f"T = {lr_log.coef_[0]:.3f} * ln(Solar+1) + {lr_log.intercept_:.3f}"
    }
    
    # 5. 제곱근 모델
    sqrt_solar = np.sqrt(solar_irradiance)
    lr_sqrt = LinearRegression()
    lr_sqrt.fit(sqrt_solar.reshape(-1, 1), indoor_temp)
    models['square_root'] = {
        'model': lr_sqrt,
        'r2': r2_score(indoor_temp, lr_sqrt.predict(sqrt_solar.reshape(-1, 1))),
        'mse': mean_squared_error(indoor_temp, lr_sqrt.predict(sqrt_solar.reshape(-1, 1))),
        'equation': f"T = {lr_sqrt.coef_[0]:.3f} * √Solar + {lr_sqrt.intercept_:.3f}"
    }
    
    return models

def visualize_models(date_str, solar_irradiance, indoor_temp, models, time_data=None, outdoor_temp=None, train_data=None, save_plot=True):
    """
    모델 비교 시각화
    """
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(15, 12))
    fig.suptitle(f'Greenhouse Temperature Prediction Models - {date_str}', fontsize=16, fontweight='bold')
    
    # 시간대별 색상 설정 (오후 2시 기준)
    if time_data is not None:
        colors = ['blue' if pd.to_datetime(t).hour < 14 else 'orange' for t in time_data]
        morning_data = np.array([(pd.to_datetime(t).hour < 14) for t in time_data])
        afternoon_data = ~morning_data
    else:
        colors = ['blue'] * len(solar_irradiance)
        morning_data = np.ones(len(solar_irradiance), dtype=bool)
        afternoon_data = np.zeros(len(solar_irradiance), dtype=bool)
    
    # 데이터 정렬
    sort_idx = np.argsort(solar_irradiance)
    solar_sorted = solar_irradiance[sort_idx]
    temp_sorted = indoor_temp[sort_idx]
    
    # 1. 선형 모델들
    # 전체 데이터 (회색, 작은 점)
    ax1.scatter(solar_irradiance[morning_data], indoor_temp[morning_data], 
                alpha=0.3, s=10, color='lightblue', label='All Data (Morning)')
    ax1.scatter(solar_irradiance[afternoon_data], indoor_temp[afternoon_data], 
                alpha=0.3, s=10, color='lightcoral', label='All Data (Afternoon)')
    
    # 학습 데이터 (Solar <= 1.2) 강조 표시
    if train_data is not None:
        train_solar = train_data['kma_solar_irradiance'].values
        train_temp = train_data['indoor_temperature'].values
        train_time = train_data['datetime'].values if 'datetime' in train_data.columns else None
        
        if train_time is not None:
            train_morning = np.array([(pd.to_datetime(t).hour < 14) for t in train_time])
            train_afternoon = ~train_morning
            ax1.scatter(train_solar[train_morning], train_temp[train_morning], 
                        alpha=0.8, s=30, color='blue', label='Training Data (Morning)')
            ax1.scatter(train_solar[train_afternoon], train_temp[train_afternoon], 
                        alpha=0.8, s=30, color='orange', label='Training Data (Afternoon)')
        else:
            ax1.scatter(train_solar, train_temp, 
                        alpha=0.8, s=30, color='red', label='Training Data (Solar ≤ 1.2)')
    
    solar_range = np.linspace(solar_irradiance.min(), solar_irradiance.max(), 100)
    
    # 기본 선형 모델
    lr = models['linear']['model']
    temp_pred = lr.predict(solar_range.reshape(-1, 1))
    ax1.plot(solar_range, temp_pred, 'r-', linewidth=2, label=f"Linear (R²={models['linear']['r2']:.3f})")
    
    # 시간대별 선형 모델
    if 'linear_morning' in models:
        lr_morning = models['linear_morning']['model']
        temp_pred_morning = lr_morning.predict(solar_range.reshape(-1, 1))
        ax1.plot(solar_range, temp_pred_morning, 'b--', linewidth=2, 
                label=f"Morning Linear (R²={models['linear_morning']['r2']:.3f})")
    
    if 'linear_afternoon' in models:
        lr_afternoon = models['linear_afternoon']['model']
        temp_pred_afternoon = lr_afternoon.predict(solar_range.reshape(-1, 1))
        ax1.plot(solar_range, temp_pred_afternoon, 'orange', linestyle='--', linewidth=2, 
                label=f"Afternoon Linear (R²={models['linear_afternoon']['r2']:.3f})")
    
    # Solar Irradiance = 1.2 수직선 표시
    ax1.axvline(x=1.2, color='red', linestyle='--', alpha=0.7, label='Training Threshold (1.2)')
    
    ax1.set_xlabel('Solar Irradiance')
    ax1.set_ylabel('Indoor Temperature (°C)')
    ax1.set_title('Linear Models (Trained on Solar ≤ 1.2)')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    # 2. 변화량 관계 모델 (Solar Irradiance Change vs Temperature Difference Change) - Solar ≤ 1.2만
    if 'change_relationship' in models:
        # 필터링된 데이터에서 변화량 계산
        solar_filtered = models['change_relationship']['solar_filtered']
        temp_diff_abs = models['change_relationship']['temp_diff_abs']
        temp_diff_change = np.diff(temp_diff_abs)
        solar_change = np.diff(solar_filtered)
        
        # 시간대별 마스크 (필터링된 데이터에 맞춰 조정)
        if time_data is not None and len(time_data) > 1:
            # Solar ≤ 1.2인 데이터의 시간 정보 추출
            solar_mask = solar_irradiance <= 1.2
            time_filtered = time_data[solar_mask]
            if len(time_filtered) > 1:
                time_for_change = time_filtered[1:]
                morning_change_mask = np.array([(pd.to_datetime(t).hour < 14) for t in time_for_change])
                afternoon_change_mask = ~morning_change_mask
            else:
                morning_change_mask = np.ones(len(temp_diff_change), dtype=bool)
                afternoon_change_mask = np.zeros(len(temp_diff_change), dtype=bool)
        else:
            morning_change_mask = np.ones(len(temp_diff_change), dtype=bool)
            afternoon_change_mask = np.zeros(len(temp_diff_change), dtype=bool)
        
        # 전체 데이터 (회색, 작은 점) - Solar > 1.2인 데이터
        if outdoor_temp is not None:
            all_temp_diff_abs = np.abs(indoor_temp - outdoor_temp)
            all_temp_diff_change = np.diff(all_temp_diff_abs)
            all_solar_change = np.diff(solar_irradiance)
            all_solar_mask = solar_irradiance[1:] > 1.2  # 변화량에 맞춰 조정
            
            if np.sum(all_solar_mask) > 0:
                ax2.scatter(all_solar_change[all_solar_mask], all_temp_diff_change[all_solar_mask], 
                            alpha=0.3, s=10, color='lightgray', label='All Data (Solar > 1.2)')
        
        # 학습 데이터 (Solar ≤ 1.2) 강조 표시
        ax2.scatter(solar_change[morning_change_mask], temp_diff_change[morning_change_mask], 
                    alpha=0.8, s=30, color='blue', label='Training Data Morning (Solar ≤ 1.2)')
        ax2.scatter(solar_change[afternoon_change_mask], temp_diff_change[afternoon_change_mask], 
                    alpha=0.8, s=30, color='orange', label='Training Data Afternoon (Solar ≤ 1.2)')
        
        # 모델 예측선
        lr_change = models['change_relationship']['model']
        solar_change_range = np.linspace(solar_change.min(), solar_change.max(), 100)
        temp_diff_change_pred = lr_change.predict(solar_change_range.reshape(-1, 1))
        ax2.plot(solar_change_range, temp_diff_change_pred, 'g-', linewidth=2, 
                label=f"Change Relationship (R²={models['change_relationship']['r2']:.3f})")
        
        # 데이터 포인트 개수 표 생성 (0.01 단위로 구간별 개수)
        if len(solar_change) > 0:
            # 0.01 단위로 구간 설정
            bin_width = 0.01
            min_val = np.floor(solar_change.min() / bin_width) * bin_width
            max_val = np.ceil(solar_change.max() / bin_width) * bin_width
            bins = np.arange(min_val, max_val + bin_width, bin_width)
            
            # 각 구간별 데이터 포인트 개수 계산
            counts, bin_edges = np.histogram(solar_change, bins=bins)
            bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2
            
            # 데이터가 있는 구간만 필터링
            data_points = []
            for center, count in zip(bin_centers, counts):
                if count > 0:
                    data_points.append({
                        'Solar_Change_Range': f"{center-bin_width/2:.3f} ~ {center+bin_width/2:.3f}",
                        'Count': count,
                        'Percentage': f"{count/len(solar_change)*100:.1f}%"
                    })
            
            # 개수 기준으로 정렬 (내림차순)
            data_points.sort(key=lambda x: x['Count'], reverse=True)
            
            # 표 생성
            if data_points:
                print(f"\n=== Solar Irradiance Change 구간별 데이터 포인트 개수 (0.01 단위) ===")
                print(f"{'구간':<20} {'개수':<8} {'비율':<8}")
                print("-" * 40)
                for point in data_points:
                    print(f"{point['Solar_Change_Range']:<20} {point['Count']:<8} {point['Percentage']:<8}")
                print(f"총 데이터 포인트: {len(solar_change)}개")
                print("=" * 50)
        
        ax2.set_xlabel('Solar Irradiance Change per 5min')
        ax2.set_ylabel('Temperature Difference Change per 5min (°C)')
        ax2.set_title('Temperature Difference Change vs Solar Irradiance Change (Trained on Solar ≤ 1.2)')
        ax2.legend()
        ax2.grid(True, alpha=0.3)
        
        # 0도 기준선 추가
        ax2.axhline(y=0, color='red', linestyle='--', alpha=0.5, label='No Temp Diff Change')
        ax2.axvline(x=0, color='red', linestyle='--', alpha=0.5, label='No Solar Change')
    else:
        # 온도 변화량 모델이 없는 경우 로그 모델 표시
        ax2.scatter(solar_irradiance[morning_data], indoor_temp[morning_data], 
                    alpha=0.6, s=20, color='blue', label='Morning (00:00-13:59)')
        ax2.scatter(solar_irradiance[afternoon_data], indoor_temp[afternoon_data], 
                    alpha=0.6, s=20, color='orange', label='Afternoon (14:00-23:59)')
        lr_log = models['logarithmic']['model']
        log_solar_range = np.log(solar_range + 1)
        temp_pred_log = lr_log.predict(log_solar_range.reshape(-1, 1))
        ax2.plot(solar_range, temp_pred_log, 'm-', linewidth=2, label=f"Logarithmic (R²={models['logarithmic']['r2']:.3f})")
        ax2.set_xlabel('Solar Irradiance')
        ax2.set_ylabel('Indoor Temperature (°C)')
        ax2.set_title('Logarithmic Model')
        ax2.legend()
        ax2.grid(True, alpha=0.3)
    
    
    plt.tight_layout()
    
    if save_plot:
        plt.savefig(f'greenhouse_models_{date_str}.png', dpi=300, bbox_inches='tight')
    
    plt.close()
    
    return fig

def predict_temperature(solar_irradiance, model_name, models, outdoor_temp=None, indoor_temp=None):
    """
    일조량으로부터 온도 예측
    """
    if model_name not in models:
        return None
    
    model_info = models[model_name]
    model = model_info['model']
    
    if model_name == 'change_relationship':
        lr_change = model
        return lr_change.predict(solar_irradiance.reshape(-1, 1))
    elif model_name == 'logarithmic':
        lr_log = model
        log_solar = np.log(solar_irradiance + 1)
        return lr_log.predict(log_solar.reshape(-1, 1))
    elif model_name == 'square_root':
        lr_sqrt = model
        sqrt_solar = np.sqrt(solar_irradiance)
        return lr_sqrt.predict(sqrt_solar.reshape(-1, 1))
    elif model_name == 'linear_multi':
        lr_multi = model
        # 온도 차이 절댓값의 평균값을 사용하여 예측
        if outdoor_temp is not None:
            temp_diff_abs = np.abs(indoor_temp - outdoor_temp)
            avg_temp_diff_abs = np.mean(temp_diff_abs)
        else:
            avg_temp_diff_abs = 0
        X_multi = np.column_stack([solar_irradiance, np.full_like(solar_irradiance, avg_temp_diff_abs)])
        return lr_multi.predict(X_multi)
    elif model_name in ['linear_morning', 'linear_afternoon']:
        lr = model
        return lr.predict(solar_irradiance.reshape(-1, 1))
    else:  # linear, linear_multi
        lr = model
        return lr.predict(solar_irradiance.reshape(-1, 1))

def analyze_greenhouse_models():
    """
    온실 온도 예측 모델 분석 메인 함수
    """
    print("온실 온도 예측 모델 분석 중...")
    
    # 데이터 로드
    df = pd.read_csv('merged_sample_with_kma.csv')
    df['datetime'] = pd.to_datetime(df['date'] + ' ' + df['time'])
    df['date_only'] = df['datetime'].dt.date
    
    # 자연스러운 곡선 구간 감지 (기존 코드 사용)
    from smooth_curve_detector import detect_smooth_curves
    
    # 월별로 그룹화하고 각 월에서 랜덤하게 5일씩 선택
    df['month'] = df['datetime'].dt.month
    months = sorted(df['month'].unique())
    
    selected_dates = []
    for month in months:
        month_dates = df[df['month'] == month]['date_only'].unique()
        if len(month_dates) >= 5:
            # 랜덤하게 5일 선택
            import random
            random.seed(42)  # 재현 가능한 결과를 위해 시드 설정
            selected_month_dates = random.sample(list(month_dates), 5)
        else:
            # 5일 미만이면 모든 날짜 선택
            selected_month_dates = list(month_dates)
        
        selected_dates.extend(selected_month_dates)
        print(f"{month}월: {len(selected_month_dates)}일 선택")
    
    print(f"\n총 {len(selected_dates)}일 분석 예정")
    
    # 분석할 날짜들
    unique_dates = selected_dates
    
    all_models = {}
    all_predictions = {}
    
    for date in unique_dates:
        print(f"\n{date} 분석 중...")
        
        daily_df = df[df['date_only'] == date].copy()
        daily_df = daily_df.sort_values('datetime')
        
        if len(daily_df) < 50:
            print(f"  데이터 부족: {len(daily_df)}개 포인트")
            continue
        
        # KMA 온도 데이터로 자연스러운 곡선 구간 감지
        temperature_data = daily_df['kma_temperature'].values
        time_data = daily_df['datetime'].values
        
        # NaN 값 제거
        valid_mask = ~np.isnan(temperature_data)
        temperature_data = temperature_data[valid_mask]
        time_data = time_data[valid_mask]
        
        if len(temperature_data) < 50:
            print(f"  유효 데이터 부족: {len(temperature_data)}개 포인트")
            continue
        
        # 자연스러운 곡선 구간 감지
        smooth_segments, curvature, smoothness = detect_smooth_curves(
            temperature_data, time_data,
            window_size=12,
            curvature_threshold=0.1,
            smoothness_threshold=0.05,
            min_duration_minutes=30
        )
        
        if not smooth_segments:
            print(f"  자연스러운 곡선 구간 없음")
            continue
        
        # 일조량-온도 관계 분석
        valid_data, smooth_df, segments = analyze_solar_temp_relationship(df, date, smooth_segments)
        
        if valid_data is None or len(valid_data) < 10:
            print(f"  유효한 일조량-온도 데이터 부족")
            continue
        
        # 모델 피팅용 데이터 (Solar Irradiance <= 1.2)
        train_mask = valid_data['kma_solar_irradiance'] <= 1.2
        train_data = valid_data[train_mask]
        
        if len(train_data) < 10:
            print(f"  Solar Irradiance <= 1.2인 데이터 부족 (필요: 10개, 실제: {len(train_data)}개)")
            continue
            
        solar_irradiance_train = train_data['kma_solar_irradiance'].values
        indoor_temp_train = train_data['indoor_temperature'].values
        outdoor_temp_train = train_data['kma_temperature'].values
        
        # 시각화용 데이터 (전체)
        solar_irradiance = valid_data['kma_solar_irradiance'].values
        indoor_temp = valid_data['indoor_temperature'].values
        outdoor_temp = valid_data['kma_temperature'].values
        
        print(f"  학습 데이터: {len(train_data)}개 (Solar <= 1.2), 시각화 데이터: {len(valid_data)}개 (전체)")
        
        # 시간 데이터 추출
        time_data_train = train_data['datetime'].values
        
        models = fit_temperature_models(solar_irradiance_train, indoor_temp_train, outdoor_temp_train, time_data_train)
        
        # 최적 모델 선택 (R² 기준)
        best_model = max(models.items(), key=lambda x: x[1]['r2'])
        print(f"  최적 모델: {best_model[0]} (R²={best_model[1]['r2']:.4f})")
        
        # 시각화
        time_data = valid_data['datetime'].values
        visualize_models(str(date), solar_irradiance, indoor_temp, models, time_data, outdoor_temp, train_data)
        
        # 예측 수행
        predictions = {}
        for model_name in models.keys():
            pred_temp = predict_temperature(solar_irradiance, model_name, models, outdoor_temp, indoor_temp)
            predictions[model_name] = pred_temp
        
        all_models[str(date)] = models
        all_predictions[str(date)] = predictions
        
        # 구간별 분석
        print(f"  자연스러운 구간: {len(smooth_segments)}개")
        print(f"  분석 데이터 포인트: {len(valid_data)}개")
        print(f"  일조량 범위: {solar_irradiance.min():.2f} ~ {solar_irradiance.max():.2f}")
        print(f"  온도 범위: {indoor_temp.min():.1f}°C ~ {indoor_temp.max():.1f}°C")
    
    # 전체 결과 요약
    print(f"\n=== 전체 분석 결과 ===")
    print(f"분석된 날짜: {len(all_models)}일")
    
    if all_models:
        # 각 모델의 평균 성능
        model_performance = {}
        for model_name in ['linear', 'polynomial_2', 'polynomial_3', 'logarithmic', 'square_root']:
            r2_scores = []
            for date, models in all_models.items():
                if model_name in models:
                    r2_scores.append(models[model_name]['r2'])
            
            if r2_scores:
                model_performance[model_name] = {
                    'avg_r2': np.mean(r2_scores),
                    'std_r2': np.std(r2_scores),
                    'count': len(r2_scores)
                }
        
        print(f"\n모델별 평균 성능:")
        for model_name, perf in model_performance.items():
            print(f"  {model_name}: R² = {perf['avg_r2']:.4f} ± {perf['std_r2']:.4f} ({perf['count']}일)")
        
        # 최고 성능 모델
        best_overall = max(model_performance.items(), key=lambda x: x[1]['avg_r2'])
        print(f"\n최고 성능 모델: {best_overall[0]} (평균 R² = {best_overall[1]['avg_r2']:.4f})")
    
    return all_models, all_predictions

if __name__ == "__main__":
    models, predictions = analyze_greenhouse_models()
