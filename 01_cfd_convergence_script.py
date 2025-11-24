import numpy as np
import pandas as pd
import os
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext


def load_cfd_data(file_path, skiprows):
    """CFD 데이터 로드 함수"""
    df = pd.read_csv(file_path, skiprows=skiprows)
    return df


def detect_period_fft(data, period_percent):
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
        period = period_filtered  # 자동으로 필터 버전 사용
        peak_idx = peak_idx_filtered
        dominant_freq = dominant_freq_filtered
    else:
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


def check_convergence(amplitude_ratio, threshold):
    """수렴 여부 판단 함수"""
    return amplitude_ratio <= threshold


def analyze_all_outlets(df_massflow, max_amplitude_percent, period_percent):
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

        fft_result, period = detect_period_fft(flow_single, period_percent)
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


def analyze_rms_residuals(file_path2, skiprows, last_n, residual_percent):
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


class CFDAnalysisGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("CFD 수렴성 분석 도구")
        self.root.geometry("1200x800")

        # 그래프 저장용 변수
        self.current_figure = None

        # 메인 프레임
        main_frame = ttk.Frame(root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # 입력 파라미터 프레임
        input_frame = ttk.LabelFrame(main_frame, text="입력 파라미터", padding="10")
        input_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)

        # 파일 경로 입력
        ttk.Label(input_frame, text="Mass Flow 데이터 경로:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.filepath_entry = ttk.Entry(input_frame, width=50)
        self.filepath_entry.grid(row=0, column=1, pady=2, padx=5)
        self.filepath_entry.insert(0, r"C:\Users\user\Desktop\data_engineering\00_practice\case1\output.csv")
        ttk.Button(input_frame, text="찾아보기", command=self.browse_massflow).grid(row=0, column=2, pady=2)

        ttk.Label(input_frame, text="RMS 데이터 경로:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.filepath2_entry = ttk.Entry(input_frame, width=50)
        self.filepath2_entry.grid(row=1, column=1, pady=2, padx=5)
        self.filepath2_entry.insert(0, r"C:\Users\user\Desktop\data_engineering\00_practice\case1\output_RMS.csv")
        ttk.Button(input_frame, text="찾아보기", command=self.browse_rms).grid(row=1, column=2, pady=2)

        # 파라미터 입력
        ttk.Label(input_frame, text="최대 진폭 기준 (%):").grid(row=2, column=0, sticky=tk.W, pady=2)
        self.max_amplitude_entry = ttk.Entry(input_frame, width=20)
        self.max_amplitude_entry.grid(row=2, column=1, sticky=tk.W, pady=2, padx=5)
        self.max_amplitude_entry.insert(0, "2.0")

        ttk.Label(input_frame, text="엑셀 내 헤더 수:").grid(row=3, column=0, sticky=tk.W, pady=2)
        self.skiprows_entry = ttk.Entry(input_frame, width=20)
        self.skiprows_entry.grid(row=3, column=1, sticky=tk.W, pady=2, padx=5)
        self.skiprows_entry.insert(0, "4")

        ttk.Label(input_frame, text="주기 유효범위 비율:").grid(row=4, column=0, sticky=tk.W, pady=2)
        self.period_percent_entry = ttk.Entry(input_frame, width=20)
        self.period_percent_entry.grid(row=4, column=1, sticky=tk.W, pady=2, padx=5)
        self.period_percent_entry.insert(0, "0.2")

        ttk.Label(input_frame, text="잔차 분석 주기 범위:").grid(row=5, column=0, sticky=tk.W, pady=2)
        self.last_n_entry = ttk.Entry(input_frame, width=20)
        self.last_n_entry.grid(row=5, column=1, sticky=tk.W, pady=2, padx=5)
        self.last_n_entry.insert(0, "500")

        ttk.Label(input_frame, text="잔차 허용 범위:").grid(row=6, column=0, sticky=tk.W, pady=2)
        self.residual_percent_entry = ttk.Entry(input_frame, width=20)
        self.residual_percent_entry.grid(row=6, column=1, sticky=tk.W, pady=2, padx=5)
        self.residual_percent_entry.insert(0, "1e-5")

        # 버튼 프레임
        button_frame = ttk.Frame(input_frame)
        button_frame.grid(row=7, column=0, columnspan=3, pady=10)

        # 실행 버튼
        self.run_button = ttk.Button(button_frame, text="분석 실행 (Result)", command=self.run_analysis,
                                      style='Accent.TButton')
        self.run_button.pack(side=tk.LEFT, padx=5)

        # 그래프 저장 버튼
        self.save_button = ttk.Button(button_frame, text="그래프 저장", command=self.save_graph)
        self.save_button.pack(side=tk.LEFT, padx=5)
        self.save_button.config(state='disabled')  # 초기에는 비활성화

        # 결과 표시 프레임
        result_frame = ttk.LabelFrame(main_frame, text="분석 결과", padding="10")
        result_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)

        # 스크롤 가능한 텍스트 영역
        self.result_text = scrolledtext.ScrolledText(result_frame, width=60, height=30, wrap=tk.WORD)
        self.result_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # 그래프 프레임
        self.graph_frame = ttk.LabelFrame(main_frame, text="그래프", padding="10")
        self.graph_frame.grid(row=1, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5, padx=5)

        # 그리드 가중치 설정
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(1, weight=1)
        result_frame.columnconfigure(0, weight=1)
        result_frame.rowconfigure(0, weight=1)

    def browse_massflow(self):
        filename = filedialog.askopenfilename(
            title="Mass Flow 데이터 선택",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if filename:
            self.filepath_entry.delete(0, tk.END)
            self.filepath_entry.insert(0, filename)

    def browse_rms(self):
        filename = filedialog.askopenfilename(
            title="RMS 데이터 선택",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if filename:
            self.filepath2_entry.delete(0, tk.END)
            self.filepath2_entry.insert(0, filename)

    def run_analysis(self):
        try:
            # 입력값 가져오기
            filepath = self.filepath_entry.get()
            filepath2 = self.filepath2_entry.get()
            max_amplitude_percent = float(self.max_amplitude_entry.get())
            skiprows = int(self.skiprows_entry.get())
            period_percent = float(self.period_percent_entry.get())
            last_n = int(self.last_n_entry.get())
            residual_percent = float(self.residual_percent_entry.get())

            # 결과 텍스트 초기화
            self.result_text.delete(1.0, tk.END)

            # 유량 데이터 분석
            self.result_text.insert(tk.END, "=" * 70 + "\n")
            self.result_text.insert(tk.END, "📊 유량 데이터 분석\n")
            self.result_text.insert(tk.END, "=" * 70 + "\n\n")

            df_massflow = load_cfd_data(filepath, skiprows)
            massflow_results = analyze_all_outlets(df_massflow, max_amplitude_percent, period_percent)

            for outlet, result in massflow_results.items():
                self.result_text.insert(tk.END, f"{outlet}:\n")
                self.result_text.insert(tk.END, f"  평균 유량: {result['mean_flow']:.2f} kg/s\n")
                self.result_text.insert(tk.END, f"  진폭 비율: {result['amplitude_ratio']:.2f}%\n")
                converged_symbol = '✓' if result['converged'] else '✗'
                self.result_text.insert(tk.END, f"  수렴 여부: {converged_symbol}\n")
                self.result_text.insert(tk.END, f"  권장 주기: {result['period']} iterations (f={result['dominant_freq']:.6f})\n\n")

            # RMS 잔차 분석
            self.result_text.insert(tk.END, "=" * 70 + "\n")
            self.result_text.insert(tk.END, "📉 RMS 잔차 분석\n")
            self.result_text.insert(tk.END, "=" * 70 + "\n\n")

            rms_results = analyze_rms_residuals(filepath2, skiprows, last_n, residual_percent)

            for col, result in rms_results.items():
                self.result_text.insert(tk.END, f"{col}:\n")
                self.result_text.insert(tk.END, f"  최종값: {result['final_value']:.2e}\n")
                self.result_text.insert(tk.END, f"  평균(last {last_n}): {result['mean_last_n']:.2e}\n")
                converged_symbol = '✓' if result['converged'] else '✗'
                self.result_text.insert(tk.END, f"  수렴 여부: {converged_symbol}\n\n")

            # 그래프 생성
            self.create_graphs(massflow_results)

            # 그래프 저장 버튼 활성화
            self.save_button.config(state='normal')

            self.result_text.insert(tk.END, "\n✅ 분석 완료!\n")

        except Exception as e:
            self.result_text.delete(1.0, tk.END)
            self.result_text.insert(tk.END, f"❌ 오류 발생: {str(e)}\n")

    def save_graph(self):
        """그래프 저장 함수"""
        if self.current_figure is None:
            self.result_text.insert(tk.END, "❌ 저장할 그래프가 없습니다. 먼저 분석을 실행하세요.\n")
            return

        # 파일 저장 대화상자
        filename = filedialog.asksaveasfilename(
            title="그래프 저장",
            defaultextension=".png",
            filetypes=[
                ("PNG files", "*.png"),
                ("PDF files", "*.pdf"),
                ("SVG files", "*.svg"),
                ("JPEG files", "*.jpg"),
                ("All files", "*.*")
            ]
        )

        if filename:
            try:
                self.current_figure.savefig(filename, dpi=300, bbox_inches='tight')
                self.result_text.insert(tk.END, f"\n✅ 그래프가 저장되었습니다: {filename}\n")
            except Exception as e:
                self.result_text.insert(tk.END, f"\n❌ 그래프 저장 오류: {str(e)}\n")

    def create_graphs(self, massflow_results):
        try:
            # 기존 그래프 삭제
            for widget in self.graph_frame.winfo_children():
                widget.destroy()

            # 새 그래프 생성
            fig, ax = plt.subplots(2, 2, figsize=(12, 8))

            # 현재 figure 저장
            self.current_figure = fig

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
                ax[0,1].plot(iterations[start_iteration:], last_cycle_data, linewidth=2,
                             label=f'{outlet_name}={last_cycle_mean:.2f} kg/s', alpha=0.7)

                # figure 3: FFT 결과 그래프
                ax[1,0].plot(xf, power, linewidth=1, label=outlet_name, alpha=0.7)

                # figure 4: FFT 유효 주기 범위 강조
                ax[1,1].plot(xf, power, linewidth=2, label=outlet_name, alpha=0.7)

            # 첫 번째 outlet 기준으로 주석 및 보조선 추가
            result_full = massflow_results
            all_power_valid = np.hstack([v['power_valid'] for v in result_full.values()])
            power_valid_full = np.max(all_power_valid)

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
            ax[0,0].set_title('Mass flow at Outlets [kg/s]', fontsize=12, fontweight='bold')
            ax[0,0].grid(True, alpha=0.3)
            ax[0,0].legend(loc='upper right', fontsize=6)
            ax[0,0].set_xlabel('Iteration', fontsize=10)
            ax[0,0].axvspan(start_iteration, end_iteration, alpha=0.2, color='yellow')

            # figure 2: 보조선 및 주석
            ax[0,1].set_title('Mass flow at Outlets for Last Period [kg/s]', fontsize=12, fontweight='bold')
            ax[0,1].grid(True, alpha=0.3)
            ax[0,1].legend(loc='upper left', fontsize=7)
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
                        fontsize=8, fontweight='bold',
                        arrowprops=dict(arrowstyle='->', color='red', lw=2))
            ax[1,0].set_title(f'FFT Power Spectrum (for abs values in 50% data)', fontsize=12, fontweight='bold')
            ax[1,0].set_xlabel('Frequency [cycles/iteration]', fontsize=10)
            ax[1,0].set_ylabel('Power', fontsize=10)
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
            ax[1,1].set_title('FFT with Valid Period Range Highlighted', fontsize=12, fontweight='bold')
            ax[1,1].set_xlabel('Frequency [1/iteration]', fontsize=10)
            ax[1,1].grid(True, alpha=0.3)
            ax[1,1].legend(loc='upper right', fontsize=6)

            plt.tight_layout()

            # tkinter에 matplotlib 그래프 임베딩
            canvas = FigureCanvasTkAgg(fig, master=self.graph_frame)
            canvas.draw()
            canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        except Exception as e:
            self.result_text.insert(tk.END, f"\n❌ 그래프 생성 오류: {str(e)}\n")
            import traceback
            self.result_text.insert(tk.END, f"{traceback.format_exc()}\n")


if __name__ == "__main__":
    root = tk.Tk()
    app = CFDAnalysisGUI(root)
    root.mainloop()
