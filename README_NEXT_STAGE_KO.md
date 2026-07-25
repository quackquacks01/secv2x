# WTC 다음 단계 실행 패키지

이 패키지는 다음 두 작업을 추가합니다.

1. AIMer-128f Windows DLL 및 Python/WTC End-to-End 연동
2. HAETAE/AIMer 원시 암호 연산과 WTC 처리 단계의 반복 벤치마크

## 적용

프로젝트 루트 `C:\Users\wah43\secv2x`에 이 ZIP을 동일 폴더 구조로 덮어씁니다.
기존 파일을 덮어쓰지 않고 새 파일만 추가합니다.

## AIMer 빌드와 검증

```powershell
Set-Location C:\Users\wah43\secv2x
$env:PATH = "C:\msys64\ucrt64\bin;$env:PATH"
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
.\scripts\build_aimer_128f.ps1
python -m wtc.scenarios_aimer
python -m pytest -q
```

성공 기준:

```text
AIMER WTC END-TO-END: PASS
```

## 빠른 벤치마크

```powershell
python .\scripts\benchmark_kpqc_wtc.py --algorithm haetae --iterations 20 --warmup 3
python .\scripts\benchmark_kpqc_wtc.py --algorithm aimer --iterations 10 --warmup 2
```

## 논문용 1차 반복 측정

```powershell
python .\scripts\benchmark_kpqc_wtc.py --algorithm haetae --iterations 200 --warmup 20
python .\scripts\benchmark_kpqc_wtc.py --algorithm aimer --iterations 100 --warmup 10
```

결과는 `artifacts\benchmarks\` 아래 JSON/CSV로 저장됩니다.
