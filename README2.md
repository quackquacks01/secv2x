응. 아래 순서대로 그대로 실행하면 돼. 동작하는 전체 프로젝트를 만들어 두었고, 내가 직접 실행했을 때 자동 테스트 10개와 전체 시나리오가 모두 통과했어.

[전체 프로젝트 ZIP 다운로드](sandbox:/mnt/data/kpqc_wtc_prototype.zip)

[실행 순서만 정리한 파일](sandbox:/mnt/data/kpqc_wtc_prototype/RUNBOOK_KO.txt)

지금 단계에서는 SUMO를 설치하지 않는다. 먼저 Python 단일 프로세스에서 다음을 확인하는 단계야.

* Commitment 생성
* Mock 서명 및 검증
* Merkle Root 생성
* Witness Cache 저장
* 동일 Root 중복 판정
* 동일 Sequence의 다른 Root 탐지
* 정상 Re-Commitment 판정
* 잘못된 업데이트 거부
* Evidence Bundle 생성

1. ZIP 파일 압축 해제

Windows 다운로드 폴더에 ZIP을 받았다고 가정하면 PowerShell에서 실행한다.

```powershell
cd $HOME\Downloads

Expand-Archive `
  -Path .\kpqc_wtc_prototype.zip `
  -DestinationPath . `
  -Force

cd .\kpqc_wtc_prototype
```

현재 위치를 확인한다.

```powershell
Get-Location
Get-ChildItem
```

다음 파일이 보여야 한다.

```text
README.md
RUNBOOK_KO.txt
pyproject.toml
scripts
src
tests
```

2. Python 설치 상태 확인

```powershell
py --version
py -0p
python --version
```

`py -0p` 결과에서 Python 3.11 이상이 하나라도 있으면 된다.

예:

```text
-V:3.12  C:\...\Python312\python.exe
-V:3.11  C:\...\Python311\python.exe
```

Git도 확인한다.

```powershell
git --version
```

3. Python 가상환경 생성

Python 3.11을 사용하는 경우:

```powershell
py -3.11 -m venv .venv
```

Python 3.12만 있는 경우:

```powershell
py -3.12 -m venv .venv
```

PowerShell에서 현재 창에 한해 스크립트 실행을 허용한다.

```powershell
Set-ExecutionPolicy `
  -Scope Process `
  -ExecutionPolicy Bypass
```

가상환경을 활성화한다.

```powershell
.\.venv\Scripts\Activate.ps1
```

정상적으로 활성화되면 프롬프트 앞에 다음처럼 표시된다.

```text
(.venv) PS C:\...\kpqc_wtc_prototype>
```

사용 중인 Python 경로를 확인한다.

```powershell
python -c "import sys; print(sys.executable)"
```

출력 경로에 `.venv`가 포함되어야 한다.

4. 필요한 패키지 설치

```powershell
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

설치 확인:

```powershell
python -m pip list
```

다음 항목이 보여야 한다.

```text
kpqc-wtc-prototype
pytest
```

5. PC 환경 확인

```powershell
python scripts\check_env.py
```

예상 출력 형식:

```text
=== Python environment check ===
Python       : 3.11.x ...
Executable   : ...\.venv\Scripts\python.exe
OS           : Windows-...
Architecture : AMD64
Pointer bits : 64
git          : OK
gcc          : MISSING
clang        : MISSING
cmake        : MISSING
make         : MISSING

Environment check completed.
```

현재 Python 프로토타입에서는 `gcc`, `cmake`, `make`가 `MISSING`이어도 괜찮아. 이것들은 AIMer와 HAETAE C 구현을 빌드할 때 필요하다.

6. 전체 자동 테스트 실행

```powershell
python -m pytest
```

정상 결과:

```text
..........                                      [100%]
10 passed
```

내가 제공한 코드도 실제로 다음 결과로 통과했어.

```text
10 passed
```

테스트가 실패하면 상세 출력을 본다.

```powershell
python -m pytest -vv
```

특정 프로토콜 테스트만 실행:

```powershell
python -m pytest tests\test_protocol.py -vv
```

Merkle Tree 테스트만 실행:

```powershell
python -m pytest tests\test_merkle.py -vv
```

7. 전체 시나리오 실행

```powershell
python -m wtc.scenarios
```

정상 출력은 다음과 같다.

```text
1. initial commitment                -> ACCEPT
2. duplicate commitment              -> DUPLICATE
3. valid re-commitment               -> VALID_UPDATE
4. same-sequence different root      -> CONFLICT
5. invalid parent root               -> INVALID_UPDATE
6. skipped sequence                  -> INVALID_UPDATE
7. tampered after signing            -> INVALID_SIGNATURE
8. expired commitment                -> STALE

Evidence written to: ...\artifacts\evidence_bundle.json

ALL SCENARIOS PASSED
```

각 결과의 의미는 다음과 같다.

* `ACCEPT`: Seq 0의 최초 정상 Commitment 등록
* `DUPLICATE`: 동일 Consistency Key와 동일 Root 재수신
* `VALID_UPDATE`: Sequence와 parentRoot가 정상 연결된 Re-Commitment
* `CONFLICT`: 동일 Consistency Key에서 서로 다른 유효 서명 Root 발견
* `INVALID_UPDATE`: Sequence 또는 parentRoot 규칙 위반
* `INVALID_SIGNATURE`: 서명 이후 데이터가 변경됨
* `STALE`: 유효시간이 만료된 Commitment

8. Evidence Bundle 확인

PowerShell에서 확인:

```powershell
Get-Content `
  .\artifacts\evidence_bundle.json `
  -Encoding UTF8
```

또는 메모장으로 연다.

```powershell
notepad .\artifacts\evidence_bundle.json
```

생성된 예시 파일:

[Evidence Bundle 예시](sandbox:/mnt/data/kpqc_wtc_prototype/artifacts/evidence_bundle.json)

Evidence Bundle에는 다음이 들어 있다.

* 동일한 Consistency Key
* 첫 번째 Commitment
* 두 번째 Commitment
* 서로 다른 두 Merkle Root
* 두 차량 서명
* Witness ID
* 관찰 시각
* Witness 관찰 Receipt

여기서 두 번째 상충 Root에 대한 Receipt는 “승인 영수증”이 아니라 “Witness가 해당 서명문을 관찰했다는 기록”으로 해석해야 한다. 상충 Root는 정상 Head나 정상 Cache를 덮어쓰지 않는다.

9. 코드 파일별 역할

전체 코드는 ZIP 안에 모두 들어 있다.

자료구조:

[models.py](sandbox:/mnt/data/kpqc_wtc_prototype/src/wtc/models.py)

정의된 자료구조:

* `TrajectoryEnvelope`
* `Commitment`
* `WitnessReceipt`
* `EvidenceBundle`
* `ProcessResult`
* `ResultCode`

결정론적 직렬화:

[encoding.py](sandbox:/mnt/data/kpqc_wtc_prototype/src/wtc/encoding.py)

역할:

* 필드 순서 고정
* JSON 정렬
* 공백 제거
* UTF-8 인코딩
* 서명 대상 Byte 배열 통일

Mock 서명:

[crypto.py](sandbox:/mnt/data/kpqc_wtc_prototype/src/wtc/crypto.py)

현재 구현:

```python
sign(message, private_key) -> signature
verify(message, signature, public_key) -> bool
```

현재는 HMAC-SHA256을 이용한 테스트 전용 구현이다.

중요:

* 실제 공개키 전자서명이 아님
* 논문 성능값으로 사용하면 안 됨
* 프로토콜 흐름 확인 용도임
* 이후 AIMerSigner와 HAETAESigner로 교체함

Merkle Tree:

[merkle.py](sandbox:/mnt/data/kpqc_wtc_prototype/src/wtc/merkle.py)

구현 기능:

* Trajectory Envelope Leaf 해시
* 도메인 구분자 적용
* Merkle Tree 생성
* 홀수 Leaf 복제 처리
* Merkle Proof 생성
* Merkle Proof 검증

Commitment 생성:

[commitment.py](sandbox:/mnt/data/kpqc_wtc_prototype/src/wtc/commitment.py)

구현 기능:

* Trajectory 목록으로 Merkle Root 생성
* Commitment 생성
* Context Digest 생성
* Commitment 서명
* 공격 테스트용 다른 Root 재서명

핵심 Witness 판정 로직:

[witness.py](sandbox:/mnt/data/kpqc_wtc_prototype/src/wtc/witness.py)

판정 순서:

```text
1. 차량 서명 검증
2. 유효시간 검증
3. 동일 Consistency Key 검색
4. 같은 Root이면 DUPLICATE
5. 다른 Root이면 CONFLICT
6. 최초 Seq 0이면 ACCEPT
7. 과거 Sequence이면 STALE
8. Sequence가 1씩 증가하는지 확인
9. parentRoot가 직전 Root인지 확인
10. Context Digest 존재 여부 확인
11. 조건 충족 시 VALID_UPDATE
```

시나리오 실행:

[scenarios.py](sandbox:/mnt/data/kpqc_wtc_prototype/src/wtc/scenarios.py)

자동 테스트:

[test_protocol.py](sandbox:/mnt/data/kpqc_wtc_prototype/tests/test_protocol.py)

[test_merkle.py](sandbox:/mnt/data/kpqc_wtc_prototype/tests/test_merkle.py)

10. 코드에서 사용한 Consistency Key

현재 코드는 다음 네 필드로 비교한다.

```text
subject_id
session_id
epoch
sequence
```

코드:

```python
@property
def consistency_key(self):
    return (
        self.subject_id,
        self.session_id,
        self.epoch,
        self.sequence,
    )
```

따라서 다음 조건이면 같은 논리적 계획 버전이다.

```text
Vehicle-A
MERGE-001
Epoch 1
Seq 1
```

이 조건에서 Root가 다르고 두 서명이 모두 유효하면 `CONFLICT`다.

11. 직접 확인할 다섯 가지 핵심 시나리오

초기 정상 등록:

```text
Seq 0
Root R0
parentRoot 없음

결과: ACCEPT
```

동일 메시지 재수신:

```text
Seq 0
Root R0

결과: DUPLICATE
```

Equivocation:

```text
Vehicle B가 받은 계획:
Seq 1
Root R1A

Vehicle C가 받은 계획:
Seq 1
Root R1B

동일 ID, Session, Epoch, Sequence
두 서명 모두 유효
R1A != R1B

결과: CONFLICT
```

정상 Re-Commitment:

```text
기존:
Seq 0
Root R0

신규:
Seq 1
Root R1
parentRoot R0
contextDigest 존재

결과: VALID_UPDATE
```

잘못된 Re-Commitment:

```text
기존:
Seq 1
Root R1

신규:
Seq 2
Root R2
parentRoot RX

결과: INVALID_UPDATE
```

12. 현재 코드에서 중요한 설계 선택

Trajectory 값은 부동소수점이 아니라 정수로 저장했다.

```text
시간: ms
위치: mm
속도: mm/s
가속도: mm/s²
```

예:

```python
t_start_ms=200
pos_min_mm=100000
v_min_mmps=12000
```

그 이유는 Python, C, 다른 차량 플랫폼 사이에서 부동소수점 표현이 달라져 동일한 계획인데도 해시가 달라지는 문제를 줄이기 위해서야.

13. KpqC 소스 확인 전 WSL 설치 여부 확인

Windows PowerShell에서:

```powershell
wsl --status
wsl -l -v
```

Ubuntu가 이미 나오면 설치할 필요가 없다.

없으면 관리자 PowerShell에서:

```powershell
wsl --install -d Ubuntu-24.04
```

설치 후 재부팅이 요구될 수 있다.

Ubuntu 실행:

```powershell
wsl
```

14. WSL 빌드 도구 설치

Ubuntu 터미널에서:

```bash
sudo apt update
sudo apt install -y \
  build-essential \
  git \
  cmake \
  ninja-build \
  pkg-config \
  python3-dev \
  python3-venv \
  unzip \
  valgrind
```

설치 확인:

```bash
git --version
gcc --version
g++ --version
make --version
cmake --version
python3 --version
```

15. AIMer와 HAETAE 공식 소스 확인

현재 AIMer 저장소에는 여러 파라미터 세트의 C Reference Implementation이 구분되어 있다. HAETAE 공식 명세는 CryptoLabInc 저장소를 Reference Code로 지정하고 있으며, 현재 해당 저장소에서는 구현 코드가 `HAETAE.zip` 형태로 제공된다. ([GitHub][1])

프로젝트 폴더의 자동 확인 스크립트를 실행하는 방법이 가장 간단하다.

Windows 프로젝트가 다운로드 폴더에 있는 경우 WSL에서:

```bash
cd /mnt/c/Users
ls
```

본인의 Windows 사용자 폴더 이름을 확인한 뒤:

```bash
cd /mnt/c/Users/<사용자명>/Downloads/kpqc_wtc_prototype
```

스크립트 실행:

```bash
bash scripts/check_kpqc_sources.sh
```

이 스크립트가 자동으로 하는 작업:

* AIMer 저장소 Clone
* HAETAE 저장소 Clone
* Git Commit Hash 출력
* HAETAE.zip 압축 해제
* Makefile 검색
* CMakeLists.txt 검색
* README 검색
* `crypto_sign_keypair` 검색
* `crypto_sign_signature` 검색
* `crypto_sign_verify` 검색
* 공개키 크기 매크로 검색
* 비밀키 크기 매크로 검색
* 서명 크기 매크로 검색

스크립트 파일:

[check_kpqc_sources.sh](sandbox:/mnt/data/kpqc_wtc_prototype/scripts/check_kpqc_sources.sh)

16. 직접 명령어로 KpqC 소스 확인

자동 스크립트 대신 직접 하려면 다음 순서대로 실행한다.

```bash
mkdir -p ~/kpqc-work
cd ~/kpqc-work
```

AIMer Clone:

```bash
git clone \
  https://github.com/samsungsds-research-papers/AIMer.git
```

HAETAE Clone:

```bash
git clone \
  https://github.com/CryptoLabInc/HAETAE.git
```

Clone 확인:

```bash
ls -lh ~/kpqc-work
```

17. AIMer 버전과 구조 확인

```bash
cd ~/kpqc-work/AIMer
```

현재 사용한 Commit Hash 기록:

```bash
git rev-parse HEAD
git log -1 --oneline
git status --short
```

폴더 확인:

```bash
find . -maxdepth 3 -type d | sort | head -100
```

빌드 파일 검색:

```bash
find . -type f \
  \( \
    -name Makefile \
    -o -name CMakeLists.txt \
    -o -name 'README*' \
  \) \
  | sort
```

서명 API 검색:

```bash
grep -R \
  "crypto_sign_keypair\|crypto_sign_signature\|crypto_sign_verify" \
  -n Reference_Implementation \
  | head -50
```

키와 서명 크기 검색:

```bash
grep -R \
  "CRYPTO_PUBLICKEYBYTES\|CRYPTO_SECRETKEYBYTES\|CRYPTO_BYTES" \
  -n Reference_Implementation \
  | head -50
```

지원 파라미터 세트 확인:

```bash
find Reference_Implementation \
  -mindepth 1 \
  -maxdepth 1 \
  -type d \
  -printf '%f\n' \
  | sort
```

예상되는 파라미터 계열:

```text
aimer128f
aimer128s
aimer192f
aimer192s
aimer256f
aimer256s
```

실험 초기에는 하나만 선택하는 게 좋아.

추천 시작점:

```text
AIMer-128f 또는 AIMer-128s
```

다만 최종 선택은 공식 파라미터 정의와 성능 목적을 확인한 뒤 고정해야 한다.

18. HAETAE 버전과 구조 확인

```bash
cd ~/kpqc-work/HAETAE
```

Commit Hash 기록:

```bash
git rev-parse HEAD
git log -1 --oneline
git status --short
```

파일 확인:

```bash
ls -lh
```

압축 내부 확인:

```bash
unzip -l HAETAE.zip | head -100
```

압축 해제:

```bash
rm -rf unpacked
mkdir unpacked

unzip -q \
  HAETAE.zip \
  -d unpacked
```

폴더 확인:

```bash
find unpacked \
  -maxdepth 4 \
  -type d \
  | sort \
  | head -150
```

빌드 파일 검색:

```bash
find unpacked \
  -type f \
  \( \
    -name Makefile \
    -o -name CMakeLists.txt \
    -o -name 'README*' \
  \) \
  | sort
```

서명 API 검색:

```bash
grep -R \
  "crypto_sign_keypair\|crypto_sign_signature\|crypto_sign_verify" \
  -n unpacked \
  | head -50
```

크기 매크로 검색:

```bash
grep -R \
  "CRYPTO_PUBLICKEYBYTES\|CRYPTO_SECRETKEYBYTES\|CRYPTO_BYTES" \
  -n unpacked \
  | head -50
```

19. 아직 `make` 명령을 임의로 실행하지 않는 이유

AIMer와 HAETAE의 정확한 빌드 위치는 다음 결과를 먼저 확인해야 한다.

```bash
find . -type f -name Makefile
find . -type f -name CMakeLists.txt
```

Makefile이 발견된 폴더가 예를 들어 다음처럼 나온다면:

```text
./Reference_Implementation/aimer128f/tests/Makefile
```

그때 다음처럼 실행한다.

```bash
make \
  -C Reference_Implementation/aimer128f/tests \
  clean

make \
  -C Reference_Implementation/aimer128f/tests \
  -j"$(nproc)"
```

HAETAE도 동일하게 실제로 발견된 Makefile 경로를 사용한다.

```bash
make -C <HAETAE_MAKEFILE이_있는_폴더> clean
make -C <HAETAE_MAKEFILE이_있는_폴더> -j"$(nproc)"
```

저장소 내부 구조를 확인하지 않고 경로를 단정하면 틀린 명령어를 줄 가능성이 있으므로, 여기서는 검색 결과를 기준으로 빌드 경로를 정해야 한다.

20. 실험 재현성을 위해 기록할 명령어

```bash
mkdir -p ~/kpqc-work/records
```

PC 및 컴파일러 정보 저장:

```bash
{
  echo "DATE"
  date -Iseconds

  echo
  echo "UNAME"
  uname -a

  echo
  echo "CPU"
  lscpu

  echo
  echo "GCC"
  gcc --version

  echo
  echo "CMAKE"
  cmake --version

  echo
  echo "PYTHON"
  python3 --version
} | tee ~/kpqc-work/records/environment.txt
```

AIMer Commit 저장:

```bash
git -C ~/kpqc-work/AIMer \
  rev-parse HEAD \
  | tee ~/kpqc-work/records/aimer_commit.txt
```

HAETAE Commit 저장:

```bash
git -C ~/kpqc-work/HAETAE \
  rev-parse HEAD \
  | tee ~/kpqc-work/records/haetae_commit.txt
```

21. 이번 단계 완료 기준

다음이 모두 확인되면 최소 프로토타입 단계가 끝난다.

* `python -m pytest` 결과가 `10 passed`
* `python -m wtc.scenarios`가 정상 종료
* `ACCEPT` 출력
* `DUPLICATE` 출력
* `VALID_UPDATE` 출력
* `CONFLICT` 출력
* `INVALID_UPDATE` 출력
* `INVALID_SIGNATURE` 출력
* `STALE` 출력
* `artifacts/evidence_bundle.json` 생성
* AIMer 저장소 Clone 성공
* HAETAE 저장소 Clone 성공
* 두 저장소 Commit Hash 기록
* `crypto_sign_keypair` 위치 확인
* `crypto_sign_signature` 위치 확인
* `crypto_sign_verify` 위치 확인
* `CRYPTO_PUBLICKEYBYTES` 확인
* `CRYPTO_SECRETKEYBYTES` 확인
* `CRYPTO_BYTES` 확인
* Makefile 또는 CMakeLists 위치 확인

이 단계가 끝난 뒤에는 MockHMACSigner를 그대로 둔 상태에서 AIMer와 HAETAE를 각각 Shared Library로 빌드하고, `ctypes` 기반 `AIMerSigner`, `HAETAESigner` 클래스로 교체하게 된다.

[1]: https://github.com/samsungsds-research-papers/AIMer "GitHub - samsungsds-research-papers/AIMer: The AIMer Digital Signature Scheme"
