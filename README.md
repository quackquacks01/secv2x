# KpqC Witnessed Trajectory Commitment 최소 프로토타입

이 프로젝트는 SUMO와 실제 KpqC를 붙이기 전에 다음 판정 흐름을 검증합니다.

- ACCEPT
- DUPLICATE
- CONFLICT
- VALID_UPDATE
- INVALID_UPDATE
- STALE
- INVALID_SIGNATURE

현재 암호 구현은 테스트용 HMAC 기반 MockSigner입니다. 실제 논문 실험 전에 AIMer/HAETAE 래퍼로 교체해야 합니다.

## Windows PowerShell 실행

```powershell
cd kpqc_wtc_prototype

py -3.11 -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
pip install -e ".[dev]"

python scripts/check_env.py
pytest
python -m wtc.scenarios
```

## Linux / WSL 실행

```bash
cd kpqc_wtc_prototype

python3 -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip
pip install -e '.[dev]'

python scripts/check_env.py
pytest
python -m wtc.scenarios
```

## 핵심 판정 규칙

1. 서명 검증 실패: INVALID_SIGNATURE
2. 만료된 Commitment: STALE
3. 동일 Consistency Key, 동일 Root: DUPLICATE
4. 동일 Consistency Key, 다른 Root: CONFLICT
5. 첫 Commitment가 Seq 0, parentRoot 없음: ACCEPT
6. Seq가 1 증가하고 parentRoot가 직전 Root와 같으며 contextDigest가 존재: VALID_UPDATE
7. 그 외 갱신: INVALID_UPDATE
