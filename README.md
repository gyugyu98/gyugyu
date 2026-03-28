# gyugyu

# CFD 수렴 진단 자동화 시스템 (CFD Convergence Diagnostics Tool)

> 정상상태 CFD 해석의 수렴성을 다면적으로 진단하는 Python 기반 자동화 도구

[![Python](https://img.shields.io/badge/Python-3.7+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

---

## 📋 프로젝트 개요

CFD 해석에서 수렴성 판단은 결과 신뢰성을 확보하는 핵심 과정입니다. 특히 다중 출구(Multi-outlet) 시스템의 경우, 각 출구별 유량 변동과 RMS 잔차를 종합적으로 검토해야 하나, 이를 수작업으로 수행할 경우 많은 시간이 소요되고 주관적 판단의 여지가 발생합니다.

본 시스템은 **복합 지표 기반 접근**을 통해 엔지니어의 의사결정을 지원합니다:
- ✅ **RMS Residual 분석**: 수치적 수렴도 평가
- ✅ **유량 진동 분석**: 모니터 변수 안정성 평가  
- ✅ **FFT 패턴 분석**: 진동 주기 정량화
- ✅ **4-Plot 시각화**: 종합 진단 리포트 자동 생성

### 개발 배경
- **문제점**: 수작업 분석 시 2시간 소요, 주관적 판단
- **해결책**: 자동화로 10분 단축, 정량적 기준 적용
- **적용 대상**: Ansys CFX 정상상태 해석 (상하수도 처리시설 등)

---

## 🚀 주요 기능

### 1. 다중 Outlet 자동 분석
- 8개 이상의 outlet을 한 번에 처리
- Outlet별 독립적인 수렴 기준 적용
- 평균 유량, 진폭 비율, 주기 자동 계산

### 2. FFT 기반 진동 패턴 분석
- 고속 푸리에 변환으로 iteration 진동 주기 검출
- 유효 범위 필터링 (5~20%)으로 트렌드 제거
- Power Spectrum 시각화

### 3. RMS Residual 교차 검증
- 마지막 500 iteration 통계 분석
- 수렴 기준 자동 평가 (< 1×10⁻⁵)
- 유량 분석과 교차 검증

### 4. 종합 시각화
- 4개 subplot 자동 생성:
  1. 전체 iteration 유량 변화
  2. 마지막 주기 확대도
  3. FFT Power Spectrum
  4. 유효 주파수 범위 확대

---

## 🛠 기술 스택

- **Python**: 3.7 이상
- **NumPy**: FFT 및 수치 연산
- **Pandas**: CSV 데이터 처리
- **Matplotlib**: 시각화

---

## 📦 설치 방법

### 1. Python 설치
- Python 3.7 이상 설치 ([다운로드](https://www.python.org/downloads/))

### 2. 필수 패키지 설치
```bash
pip install numpy pandas matplotlib
```

또는 requirements.txt 사용:
```bash
pip install -r requirements.txt
```

### 3. 스크립트 다운로드
```bash
git clone https://github.com/yourusername/CFD-Convergence-Diagnostics.git
cd CFD-Convergence-Diagnostics
```

---

## 💻 사용 방법

### Step 1: CFX에서 데이터 추출

#### Monitor Point 설정
1. Ansys CFX-Pre에서 Monitor Point 생성
2. **Mass Flow** 선택 (각 Outlet에 대해)
3. 해석 실행 후 결과 파일 생성

#### CSV 내보내기
1. CFX-Post 또는 CFX-Solver Manager 열기
2. Monitor 데이터 → **Export to CSV** 선택
3. 저장 위치 지정:
   - `output_massflow.csv` (유량 데이터)
   - `RMS_Turbulence.csv` (잔차 데이터)

**파일 형식 예시:**
```csv
[Name]
Timestep,Outlet01 Massflow,Outlet02 Massflow,...
[Data]
1,8.92,7.79,...
2,8.94,7.81,...
...
```

### Step 2: 스크립트 설정

`Step4_graph_modified.py` 파일을 열고 **파일 경로** 수정:

```python
# 메인 실행 부분 (파일 끝부분)
if __name__ == "__main__":
    # 유량 데이터 파일 경로
    df_massflow = load_cfd_data(
        r"C:\Users\user\Desktop\your_project\output_massflow.csv",  # ← 수정
        skiprows
    )
    
    # RMS 잔차 파일 경로
    rms_results = analyze_rms_residuals(
        r"C:\Users\user\Desktop\your_project\RMS_Turbulence.csv",  # ← 수정
        skiprows
    )
```

### Step 3: 실행

```bash
python Step4_graph_modified.py
```

### Step 4: 결과 확인

**콘솔 출력 예시:**
```
======================================================================
📊 유량 데이터 분석
======================================================================

Outlet01:
  평균 유량: 8.92 kg/s
  진폭 비율: 2.34%
  수렴 여부: ✓
  권장 주기: 153 iterations (f=0.006519)

Outlet02:
  평균 유량: 7.79 kg/s
  진폭 비율: 3.21%
  수렴 여부: ✓
  권장 주기: 151 iterations (f=0.006623)

======================================================================
📉 RMS 잔차 분석
======================================================================

RMS Turbulence K:
  최종값: 3.45e-06
  평균(last 500): 4.12e-06
  수렴 여부: ✓
```

**그래프 출력:**
- 4개 subplot 자동 생성
- 창에 표시 또는 파일로 저장 가능

---

## 📊 출력 결과 해석

### 수렴 판정 가이드

| RMS Residual | 유량 진폭 | 권장 조치 |
|--------------|-----------|-----------|
| ✅ < 1e-5 | ✅ < 5% | **수렴 판정 가능** |
| ✅ < 1e-5 | ⚠️ > 5% | 물리적 진동 가능성 검토 |
| ⚠️ > 1e-5 | ✅ < 5% | 국소 문제 또는 plateau 확인 |
| ❌ > 1e-5 | ❌ > 5% | **추가 iteration 필요** |

### 그래프 읽는 법

#### Figure 1: 전체 유량 변화
- 초기 과도 응답 확인
- 노란색 음영: 분석 대상 구간

#### Figure 2: 마지막 주기 확대
- 수렴 판정 기준 구간
- 평균값 및 변동폭 확인

#### Figure 3: FFT Power Spectrum
- 지배 주파수 식별 (빨간 점선)
- 노란색 영역: 유효 주기 범위

#### Figure 4: 유효 범위 확대
- 필터링된 주파수 영역
- 다중 피크 존재 여부 확인

---

## ⚙️ 설정 파라미터

스크립트 상단에서 조정 가능:

```python
# 사용자 변수
max_amplitude_percent = 5.0   # 수렴 기준: 진폭 비율 (%)
skiprows = 4                  # CSV 헤더 행 수
period_percent = 0.2          # 유효 주기 상한 (20%)
last_n = 500                  # RMS 분석 구간 (iterations)
residual_percent = 1e-5       # RMS 수렴 기준
```

### 파라미터 설명

| 파라미터 | 설명 | 기본값 | 권장 범위 |
|----------|------|--------|-----------|
| `max_amplitude_percent` | 진폭 비율 수렴 기준 | 5.0% | 1~10% |
| `skiprows` | CSV 헤더 행 수 | 4 | CFX 기본값 |
| `period_percent` | 유효 주기 최댓값 | 20% | 15~30% |
| `last_n` | RMS 통계 구간 | 500 | 300~1000 |
| `residual_percent` | RMS 기준값 | 1e-5 | 1e-4~1e-6 |

---

## 📂 입력 파일 형식

### 필수 요구사항

✅ **파일 형식**: CSV  
✅ **인코딩**: UTF-8  
✅ **헤더**: 4행 (CFX 기본)  
✅ **컬럼명**: `Timestep`, `Outlet01`, `Outlet02`, ...

## ⚠️ 제약사항 및 권장사항

### 적용 가능 조건
- ✅ 정상상태(Steady-state) CFD 해석
- ✅ Ansys CFX Monitor Point 데이터
- ✅ 2,000 iterations 이상 데이터 권장
- ✅ 다중 outlet 시스템

### 한계
- ⚠️ FFT는 iteration 진동 패턴 분석용 (물리적 주파수 아님)
- ⚠️ 다중 주기 성분 공존 시 단일 피크만 검출
- ⚠️ 최종 수렴 판단은 엔지니어가 종합적으로 결정

### 권장사항
1. **Power Spectrum 육안 검토** 필수
2. **RMS residual과 교차 검증** 수행
3. 다중 피크 발견 시 개별 분석
4. 짧은 데이터(<2000 iter) 신뢰도 낮음

---

## 📄 라이선스

MIT License - 자유롭게 사용, 수정, 배포 가능

---

## 👤 개발자

**규진**  
- CFD Analysis Engineer (Ansys CFX)  
- 전문 분야: 수처리 시설, 유동 해석, 해석 자동화  

---

## 🎯 향후 개발 계획

- [ ] GUI 인터페이스 개발 (PyQt5)
- [ ] 실시간 모니터링 기능
- [ ] 자동 리포트 생성 (PDF/Excel)
- [ ] 다중 피크 검출 알고리즘
- [ ] STFT 기반 비정상성 분석
- [ ] 머신러닝 기반 수렴 예측

---

## 📝 변경 이력

### v1.0 (2025.11)
- 초기 버전 출시
- 다중 outlet 분석 기능
- FFT 기반 주기 검출
- RMS 잔차 분석
- 4-plot 시각화

---
