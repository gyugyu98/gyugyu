"""
Step 4: 함수화 + RMS 잔차 분석
목표:
1. 지금까지 만든 코드를 함수로 정리
2. RMS 잔차 데이터 분석 추가
3. 여러 outlet을 한번에 처리
"""

import numpy as np
import pandas as pd
import os
import matplotlib.pyplot as plt

# 사용자 변수
max_amplitude_percent = 5.0  # 수렴 기준 5%
skiprows = 4  # CSV 파일의 헤더 행 수
period_percent = 0.2  # 주기 탐색 시 유효 범위 비율
last_n = 500  # RMS 잔차 분석 시 마지막 N개 데이터 사용
residual_percent = 1e-5  # RMS 잔차 수렴 기준


def load_cfd_data(file_path, skiprows):
    """CFD 데이터 로드 함수"""
    df = pd.read_csv(file_path, skiprows = skiprows)
    return df


def detect_period_fft(data):
    """FFT를 이용한 주기 검출 함수"""
    N_full = len(data)
    start_idx = N_full // 2
    stable_data = data[start_idx:]
    N = len(stable_data)
    
    xf = np.fft.fftfreq(N, d=1)[:N//2]
    yf = np.fft.fft(stable_data)
    power = 2.0/N * np.abs(yf[:N//2])

    power[0] = 0
    
    # 주기 계산 1 (필터 없는 버전)
    peak_idx_full = np.argmax(power)
    dominant_freq_full = xf[peak_idx_full]
    period_full = int(1 / dominant_freq_full) if dominant_freq_full > 0 else N
    
    # 주기 계산 2 (필터 있는 버전)
    min_period = int(N * 0.05)
    max_period = int(N * 0.20)
    min_freq = 1 / max_period
    max_freq = 1 / min_period

    valid_mask = (xf >= min_freq) & (xf <= max_freq)
    power_valid = power.copy()
    power_valid[~valid_mask] = 0

    peak_idx_filtered = np.argmax(power_valid)
    dominant_freq_filtered = xf[peak_idx_filtered]
    period_filtered = int(1 / dominant_freq_filtered) if dominant_freq_filtered > 0 else min_period
    
    
    # 버전 판단 기준
    if period_full > N_full * period_percent:
        print(f"  ⚠️ 주의: 최대 피크의 주기({period_full})가 데이터의 {int(period_percent*100)}% 초과")
        print(f"          → 트렌드일 가능성 높음. 필터 적용 권장.")
        period = period_filtered  # 자동으로 필터 버전 사용
        peak_idx = peak_idx_filtered
        dominant_freq = dominant_freq_filtered
    else:
        print(f"  ✓ 최대 피크가 유효 범위 내. 전체 스펙트럼 피크 사용 권장.")
        period = period_full  # 전체 스펙트럼 피크 사용
        peak_idx = peak_idx_full
        dominant_freq = dominant_freq_full
        
    fft = {
        'period': period,
        'peak_idx': peak_idx,
        'power': power,
        'power_valid': power_valid,
        'xf': xf,
        'min_freq': min_freq,
        'max_freq': max_freq,
        'dominant_freq': dominant_freq
    }
        
    return fft, period

def analyze_last_cycle(data, period):
    """마지막 주기 데이터 분석 함수"""
    last_cycle_start = int(len(data) - period)
    last_cycle_data = data[last_cycle_start:]  # 마지막 주기 시작점부터 끝까지의 Outlet 데이터
    last_cycle_mean = np.mean(last_cycle_data)
    last_cycle_std = np.std(last_cycle_data)
    
    last_cycle_amplitude = np.max(last_cycle_data) - np.min(last_cycle_data)

    # 수렴 판단
    amplitude_ratio = (last_cycle_amplitude / last_cycle_mean) * 100

    results = {
        'start_iteration': last_cycle_start,
        'end_iteration': int(len(data)),
        'mean': last_cycle_mean,
        'std': last_cycle_std,
        'amplitude': last_cycle_amplitude,
        'amplitude_ratio': amplitude_ratio,
        'last_cycle_mean': last_cycle_mean,
        'last_cycle_data': last_cycle_data
    }
    
    return results

def check_convergence(amplitude_ratio, threshold = max_amplitude_percent):
    """수렴 여부 판단 함수"""
    return amplitude_ratio <= threshold

def analyze_all_outlets(df_massflow, max_amplitude_percent):
    """모든 Outlet에 대해 분석 수행 함수"""
    outlet_columns = [col for col in df_massflow.columns if 'Outlet' in col]
    iteration_cols = [col for col in df_massflow.columns if 'Timestep' in col]
    iterations = df_massflow[iteration_cols[0]].values
    flow_data_raw = df_massflow[outlet_columns].values
    flow_data_abs = np.abs(flow_data_raw)
    
    results_dict = {}
    
    for idx, outlet_col in enumerate(outlet_columns):
        outlet_name = f"Outlet{idx+1:02d}"
        flow_single = flow_data_abs[:, idx]
        flow_single_raw = flow_data_raw[:, idx]
        
        fft_result, period = detect_period_fft(flow_single)
        last_cycle_result = analyze_last_cycle(flow_single, period)
        is_converged = check_convergence(last_cycle_result['amplitude_ratio'], max_amplitude_percent)
        
        results_dict[outlet_name] = {
            'period': fft_result['period'],
            'peak_idx': fft_result['peak_idx'],
            'power': fft_result['power'],
            'power_valid': fft_result['power_valid'],
            'xf': fft_result['xf'],
            'min_freq': fft_result['min_freq'],
            'max_freq': fft_result['max_freq'],
            'dominant_freq': fft_result['dominant_freq'],
            'start_iteration': last_cycle_result['start_iteration'],
            'end_iteration': last_cycle_result['end_iteration'],
            'mean_flow': last_cycle_result['mean'],
            'std_flow': last_cycle_result['std'],
            'amplitude': last_cycle_result['amplitude'],
            'amplitude_ratio': last_cycle_result['amplitude_ratio'],
            'converged': is_converged,
            'iterations': iterations,
            'flow_single_raw': flow_single_raw,
            'flow_single': flow_single,
            'last_cycle_mean': last_cycle_result['last_cycle_mean'],
            'last_cycle_data': last_cycle_result['last_cycle_data']
        }
    return results_dict

def analyze_rms_residuals(file_path2, skiprows):
    """RMS 잔차 데이터 분석 함수"""
    df_rms = load_cfd_data(file_path2, skiprows)
    
    residuals_cols = [col for col in df_rms.columns if 'RMS' in col]
    
    rms_results = {}
    for col in residuals_cols:
        rms_data = df_rms[col].values
        last_values = rms_data[-last_n:]  # 마지막 N개 데이터 선택
        
        rms_results[col] = {
            'final_value': rms_data[-1],
            'mean_last_n': np.mean(last_values),
            'max_last_n': np.max(last_values),
            'converged': np.max(last_values) < residual_percent  # 예시 수렴 기준
        }
        
    return rms_results

# 메인 실행
if __name__ == "__main__":
    # 유량 데이터 분석
    print("=" * 70)
    print("📊 유량 데이터 분석")
    print("=" * 70)
    
    df_massflow = load_cfd_data(r"C:\Users\user\Desktop\data_engineering\00_practice\case1\output_massflow.csv", skiprows)
    massflow_results = analyze_all_outlets(df_massflow, max_amplitude_percent)
    
    for outlet, result in massflow_results.items():
        print(f"\n{outlet}:")
        print(f"  평균 유량: {result['mean_flow']:.2f} kg/s")
        print(f"  진폭 비율: {result['amplitude_ratio']:.2f}%")
        print(f"  수렴 여부: {'✓' if result['converged'] else '✗'}")
        print(f"  권장 주기: {result['period']} iterations (f={result['dominant_freq']:.6f})")
        
    # RMS 잔차 분석
    print("\n" + "=" * 70)
    print("📉 RMS 잔차 분석")
    print("=" * 70)
    
    rms_results = analyze_rms_residuals(r"C:\Users\user\Desktop\data_engineering\00_practice\case1\RMS_Turbulence.csv", skiprows)
    
    for col, result in rms_results.items():
        print(f"\n{col}:")
        print(f"  최종값: {result['final_value']:.2e}")
        print(f"  평균(last {last_n}): {result['mean_last_n']:.2e}")
        print(f"  수렴 여부: {'✓' if result['converged'] else '✗'}")
    
    # 시각화    
    fig, ax = plt.subplots(2,2, figsize=(16, 8))

    # 모든 outlet 데이터를 그래프에 표시
    for outlet_name, result in massflow_results.items():
        iterations = result['iterations']
        flow_single_raw = result['flow_single_raw']
        start_iteration = result['start_iteration']
        end_iteration = result['end_iteration']
        last_cycle_data = result['last_cycle_data']
        last_cycle_mean = result['last_cycle_mean']
        power = result['power']
        xf = result['xf']
        
        # figure 1: Iteration별 유량 그래프
        ax[0,0].plot(iterations, flow_single_raw, linewidth=1, label=outlet_name, alpha=0.7)
        
        # figure 2: 마지막 주기 확대 그래프
        ax[0,1].plot(iterations[start_iteration:], last_cycle_data, linewidth=2, label=f'{outlet_name}={last_cycle_mean:.2f} kg/s', alpha=0.7)
        
        # figure 3: FFT 결과 그래프
        ax[1,0].plot(xf, power, linewidth=1, label=outlet_name, alpha=0.7)
        
        # figure 4: FFT 유효 주기 범위 강조
        ax[1,1].plot(xf, power, linewidth=2, label=outlet_name, alpha=0.7)
    
    # 첫 번째 outlet 기준으로 주석 및 보조선 추가
    result_full = massflow_results
    all_power_valid = np.hstack([v['power_valid'] for v in result_full.values()])  # concatenate all power_valid arrays
    power_valid_full = np.max(all_power_valid)
    # make result_full callable (the next line in the script calls it) — identity wrapper
    result_full = lambda x: x
    max_power_in_range = result_full(np.max(power_valid_full))

    first_outlet = list(massflow_results.keys())[0]
    result = massflow_results[first_outlet]
    power_valid = result['power_valid']

    start_iteration = result['start_iteration']
    end_iteration = result['end_iteration']
    period = result['period']
    xf = result['xf']
    peak_idx = result['peak_idx']
    dominant_freq = result['dominant_freq']
    min_freq = result['min_freq']
    max_freq = result['max_freq']
    peak_power = power_valid[peak_idx]
  
    
    # figure 1: 보조선 및 주석
    ax[0,0].set_title('Mass flow at Outlets [kg/s]', fontsize=16, fontweight='bold')
    ax[0,0].grid(True, alpha=0.3)
    ax[0,0].legend(loc='upper right', fontsize=6)
    ax[0,0].set_xlabel('Iteration', fontsize=12)
    ax[0,0].axvspan(start_iteration, end_iteration, alpha=0.2, color='yellow')
    
    # figure 2: 보조선 및 주석 
    ax[0,1].set_title('Mass flow at Outlets for Last Period [kg/s]', fontsize=16, fontweight='bold')
    ax[0,1].grid(True, alpha=0.3)
    ax[0,1].legend(loc='upper left', fontsize=8)
    ax[0,1].axvspan(start_iteration, end_iteration, alpha=0.2, color='yellow')
    
    # figure 3: 보조선 및 주석
    ax[1,0].axvline(min_freq, color='gray', linestyle=':', alpha=0.5)
    ax[1,0].axvline(max_freq, color='gray', linestyle=':', alpha=0.5)
    ax[1,0].axvspan(min_freq, max_freq, alpha=0.2, color='yellow')
    ax[1,0].axvline(dominant_freq, color='red', linestyle='--', linewidth=2)
    ax[1,0].scatter([dominant_freq], [peak_power], s=30, color='red', zorder=5)
    ax[1,0].annotate(f'Period = {period} iter\nf = {dominant_freq:.6f}', 
                xy=(dominant_freq, peak_power),
                xytext=(dominant_freq*2, peak_power*0.8),
                fontsize=10, fontweight='bold',
                arrowprops=dict(arrowstyle='->', color='red', lw=2))
    ax[1,0].set_title(f'FFT Power Spectrum (for abs values in 50% data)', fontsize=16, fontweight='bold')
    ax[1,0].set_xlabel('Frequency [cycles/iteration]', fontsize=12)
    ax[1,0].set_ylabel('Power', fontsize=12)
    ax[1,0].legend(loc='upper right', fontsize=6)
    ax[1,0].grid(True, alpha=0.3)
    ax[1,0].set_xlim([0, 0.05])
    
    # figure 4: 보조선 및 주석
    ax[1,1].axvline(min_freq, color='gray', linestyle=':', alpha=0.5)
    ax[1,1].axvline(max_freq, color='gray', linestyle=':', alpha=0.5)
    ax[1,1].axvline(dominant_freq, color='red', linestyle='--', linewidth=2)
    ax[1,1].scatter([dominant_freq], [peak_power], s=50, color='red', zorder=5)
    ax[1,1].set_xlim([min_freq, max_freq])
    ax[1,1].set_ylim([0, power_valid_full*1.1])
    ax[1,1].set_title('FFT with Valid Period Range Highlighted', fontsize=16, fontweight='bold')
    ax[1,1].set_xlabel('Frequency [1/iteration]', fontsize=12)
    ax[1,1].grid(True, alpha=0.3)
    ax[1,1].legend(loc='upper right', fontsize=6)

    plt.show()
