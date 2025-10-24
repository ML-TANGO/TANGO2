import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy import signal
from scipy.ndimage import gaussian_filter1d
import warnings
warnings.filterwarnings('ignore')

def detect_smooth_curves(temperature_data, time_data, window_size=12, curvature_threshold=0.1, 
                        smoothness_threshold=0.05, min_duration_minutes=30):
    """
    온도 데이터에서 자연스러운 곡선 구간을 감지하는 함수
    
    Parameters:
    - temperature_data: 온도 데이터 (numpy array)
    - time_data: 시간 데이터 (datetime array)
    - window_size: 분석할 윈도우 크기 (5분 단위, 기본 12 = 1시간)
    - curvature_threshold: 곡률 임계값 (낮을수록 더 부드러운 곡선)
    - smoothness_threshold: 부드러움 임계값 (낮을수록 더 부드러운 곡선)
    - min_duration_minutes: 최소 지속 시간 (분)
    
    Returns:
    - smooth_segments: 자연스러운 곡선 구간들의 리스트
    """
    
    def calculate_curvature(x, y):
        """곡률 계산"""
        dx = np.gradient(x)
        dy = np.gradient(y)
        ddx = np.gradient(dx)
        ddy = np.gradient(dy)
        
        curvature = np.abs(dx * ddy - dy * ddx) / (dx**2 + dy**2)**(3/2)
        return curvature
    
    def calculate_smoothness(data, window=5):
        """부드러움 계산 (변화율의 표준편차)"""
        diff = np.diff(data)
        smoothness = []
        
        for i in range(len(diff) - window + 1):
            window_diff = diff[i:i+window]
            smoothness.append(np.std(window_diff))
        
        return np.array(smoothness)
    
    # 시간을 숫자로 변환 (분 단위)
    time_numeric = np.array([(t - time_data[0]) / np.timedelta64(1, 'm') for t in time_data])
    
    # 곡률 계산
    curvature = calculate_curvature(time_numeric, temperature_data)
    
    # 부드러움 계산
    smoothness = calculate_smoothness(temperature_data, window=window_size)
    
    # 부드러움 배열을 원본 길이에 맞게 확장
    smoothness_extended = np.full(len(temperature_data), np.nan)
    smoothness_extended[window_size//2:window_size//2 + len(smoothness)] = smoothness
    
    # 자연스러운 구간 식별
    smooth_mask = (curvature < curvature_threshold) & (smoothness_extended < smoothness_threshold)
    
    # 연속된 구간 찾기
    smooth_segments = []
    in_smooth = False
    start_idx = 0
    
    for i, is_smooth in enumerate(smooth_mask):
        if is_smooth and not in_smooth:
            # 부드러운 구간 시작
            start_idx = i
            in_smooth = True
        elif not is_smooth and in_smooth:
            # 부드러운 구간 끝
            duration = time_numeric[i-1] - time_numeric[start_idx]
            if duration >= min_duration_minutes:
                smooth_segments.append({
                    'start_idx': start_idx,
                    'end_idx': i-1,
                    'start_time': time_data[start_idx],
                    'end_time': time_data[i-1],
                    'duration_minutes': duration,
                    'temperature_range': (temperature_data[start_idx], temperature_data[i-1]),
                    'avg_curvature': np.mean(curvature[start_idx:i]),
                    'avg_smoothness': np.nanmean(smoothness_extended[start_idx:i])
                })
            in_smooth = False
    
    # 마지막 구간 처리
    if in_smooth:
        duration = time_numeric[-1] - time_numeric[start_idx]
        if duration >= min_duration_minutes:
            smooth_segments.append({
                'start_idx': start_idx,
                'end_idx': len(time_data)-1,
                'start_time': time_data[start_idx],
                'end_time': time_data[-1],
                'duration_minutes': duration,
                'temperature_range': (temperature_data[start_idx], temperature_data[-1]),
                'avg_curvature': np.mean(curvature[start_idx:]),
                'avg_smoothness': np.nanmean(smoothness_extended[start_idx:])
            })
    
    return smooth_segments, curvature, smoothness_extended

def visualize_smooth_curves(date_str, temperature_data, time_data, smooth_segments, 
                           curvature, smoothness, save_plot=True):
    """
    자연스러운 곡선 구간을 시각화하는 함수
    """
    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(20, 12))
    fig.suptitle(f'Smooth Curve Detection - {date_str}', fontsize=16, fontweight='bold')
    
    # 1. 온도 데이터와 자연스러운 구간 표시
    ax1.plot(time_data, temperature_data, 'b-', linewidth=1, alpha=0.7, label='Temperature')
    
    # 자연스러운 구간을 다른 색으로 표시
    for i, segment in enumerate(smooth_segments):
        start_idx = segment['start_idx']
        end_idx = segment['end_idx']
        ax1.plot(time_data[start_idx:end_idx+1], temperature_data[start_idx:end_idx+1], 
                'r-', linewidth=3, alpha=0.8, label=f'Smooth Segment {i+1}' if i < 5 else '')
    
    ax1.set_title('Temperature with Smooth Curve Segments')
    ax1.set_ylabel('Temperature (°C)')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    ax1.tick_params(axis='x', rotation=45)
    
    # 2. 곡률 그래프
    ax2.plot(time_data, curvature, 'g-', linewidth=1, alpha=0.7)
    ax2.axhline(y=0.1, color='r', linestyle='--', alpha=0.7, label='Curvature Threshold')
    ax2.set_title('Curvature Analysis')
    ax2.set_ylabel('Curvature')
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    ax2.tick_params(axis='x', rotation=45)
    
    # 3. 부드러움 그래프
    ax3.plot(time_data, smoothness, 'm-', linewidth=1, alpha=0.7)
    ax3.axhline(y=0.05, color='r', linestyle='--', alpha=0.7, label='Smoothness Threshold')
    ax3.set_title('Smoothness Analysis')
    ax3.set_ylabel('Smoothness (std of changes)')
    ax3.legend()
    ax3.grid(True, alpha=0.3)
    ax3.tick_params(axis='x', rotation=45)
    
    # 4. 구간별 통계
    if smooth_segments:
        segment_info = []
        for i, segment in enumerate(smooth_segments):
            start_time_str = pd.to_datetime(segment['start_time']).strftime('%H:%M')
            end_time_str = pd.to_datetime(segment['end_time']).strftime('%H:%M')
            segment_info.append([
                f"Segment {i+1}",
                f"{start_time_str} - {end_time_str}",
                f"{segment['duration_minutes']:.0f}min",
                f"{segment['temperature_range'][0]:.1f}°C - {segment['temperature_range'][1]:.1f}°C",
                f"{segment['avg_curvature']:.3f}",
                f"{segment['avg_smoothness']:.3f}"
            ])
        
        ax4.axis('tight')
        ax4.axis('off')
        table = ax4.table(cellText=segment_info,
                         colLabels=['Segment', 'Time Range', 'Duration', 'Temp Range', 'Avg Curvature', 'Avg Smoothness'],
                         cellLoc='center',
                         loc='center')
        table.auto_set_font_size(False)
        table.set_fontsize(9)
        table.scale(1.2, 1.5)
        ax4.set_title('Smooth Curve Segments Summary')
    else:
        ax4.text(0.5, 0.5, 'No smooth curve segments found', 
                ha='center', va='center', transform=ax4.transAxes, fontsize=14)
        ax4.set_title('No Smooth Segments')
    
    plt.tight_layout()
    
    if save_plot:
        plt.savefig(f'smooth_curves_{date_str}.png', dpi=300, bbox_inches='tight')
    
    # plt.show()
    plt.close()  # 창을 띄우지 않고 닫기

    return fig

def analyze_daily_smooth_curves():
    """
    일별 데이터에서 자연스러운 곡선 구간을 분석하는 메인 함수
    """
    print("자연스러운 곡선 구간 분석 중...")
    
    # 데이터 로드
    df = pd.read_csv('merged_sample_with_kma.csv')
    df['datetime'] = pd.to_datetime(df['date'] + ' ' + df['time'])
    
    # 날짜별로 그룹화
    df['date_only'] = df['datetime'].dt.date
    unique_dates = sorted(df['date_only'].unique())
    
    # 처음 5일만 분석
    analysis_dates = unique_dates[:5]
    
    all_smooth_segments = []
    
    for date in analysis_dates:
        print(f"\n{date} 분석 중...")
        
        daily_df = df[df['date_only'] == date].copy()
        daily_df = daily_df.sort_values('datetime')
        
        if len(daily_df) < 50:  # 최소 데이터 포인트 확인
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
            window_size=12,  # 1시간 윈도우
            curvature_threshold=0.1,  # 곡률 임계값
            smoothness_threshold=0.05,  # 부드러움 임계값
            min_duration_minutes=30  # 최소 30분 지속
        )
        
        print(f"  발견된 자연스러운 곡선 구간: {len(smooth_segments)}개")
        
        # 각 구간 정보 출력
        for i, segment in enumerate(smooth_segments):
            start_time_str = pd.to_datetime(segment['start_time']).strftime('%H:%M')
            end_time_str = pd.to_datetime(segment['end_time']).strftime('%H:%M')
            print(f"    구간 {i+1}: {start_time_str} - {end_time_str} "
                  f"({segment['duration_minutes']:.0f}분, {segment['temperature_range'][0]:.1f}°C → {segment['temperature_range'][1]:.1f}°C)")
        
        # 시각화
        visualize_smooth_curves(str(date), temperature_data, time_data, 
                               smooth_segments, curvature, smoothness)
        
        # 전체 결과에 추가
        for segment in smooth_segments:
            segment['date'] = date
            all_smooth_segments.append(segment)
    
    # 전체 결과 요약
    print(f"\n=== 전체 분석 결과 ===")
    print(f"총 자연스러운 곡선 구간: {len(all_smooth_segments)}개")
    
    if all_smooth_segments:
        avg_duration = np.mean([s['duration_minutes'] for s in all_smooth_segments])
        avg_curvature = np.mean([s['avg_curvature'] for s in all_smooth_segments])
        avg_smoothness = np.mean([s['avg_smoothness'] for s in all_smooth_segments])
        
        print(f"평균 지속 시간: {avg_duration:.1f}분")
        print(f"평균 곡률: {avg_curvature:.3f}")
        print(f"평균 부드러움: {avg_smoothness:.3f}")
        
        # 시간대별 분포
        time_distribution = {}
        for segment in all_smooth_segments:
            hour = pd.to_datetime(segment['start_time']).hour
            time_distribution[hour] = time_distribution.get(hour, 0) + 1
        
        print(f"\n시간대별 자연스러운 곡선 구간 분포:")
        for hour in sorted(time_distribution.keys()):
            print(f"  {hour:02d}시: {time_distribution[hour]}개")
    
    return all_smooth_segments

if __name__ == "__main__":
    smooth_segments = analyze_daily_smooth_curves()
