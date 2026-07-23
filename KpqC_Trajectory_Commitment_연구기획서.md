# 협력 자율주행 환경에서 상충 주행계획 공격 탐지 및 책임성 확보를 위한 KpqC 기반 Witnessed Trajectory Commitment 프로토콜

> **한 줄 설명**  
> 협력 자율주행차가 차선 변경·합류 등의 미래 주행계획을 공유할 때, 정상 키를 가진 악성 차량이 상대 차량마다 서로 다른 계획을 보내는 행위를 탐지하고 증거화하는 양자내성 인증 프로토콜을 제안한다.

---

## 0. 연구 개요

### 0.1 연구 배경

협력 자율주행 환경에서는 차량이 주변 차량이나 도로 인프라와 다음 정보를 공유할 수 있다.

- 차선 변경 의도
- 교차로 진입 순서
- 합류 예정 시점
- 예상 주행 경로
- 속도 변화 계획
- 군집주행 참여·이탈 계획

기존 전자서명은 메시지가 특정 차량에서 생성되었고 전송 중 변조되지 않았음을 확인하는 데 유용하다. 그러나 정상적인 개인키를 가진 차량이 서로 다른 수신자에게 상충하는 주행계획을 각각 정상 서명하여 전송하는 경우, 개별 서명 검증만으로는 모순을 판단하기 어렵다.

예시는 다음과 같다.

```text
차량 A → 차량 B:
"2초 후 왼쪽 차선으로 이동한다." + 정상 서명

차량 A → 차량 C:
"2초 후 오른쪽 차선으로 이동한다." + 정상 서명
```

두 메시지는 모두 차량 A의 정상 서명을 포함하므로 각각의 진위성은 확인된다. 하지만 차량 B와 C가 받은 계획은 동시에 성립할 수 없다.

본 연구에서는 이를 **상충 주행계획 공격(Trajectory Equivocation Attack)**으로 정의한다.

### 0.2 핵심 문제

전자서명은 다음을 보장한다.

- 발신자 인증
- 메시지 무결성
- 서명 부인 방지

그러나 전자서명 하나만으로는 다음을 자동으로 보장하지 않는다.

- 같은 차량이 모든 협력 참여자에게 동일한 계획을 제시했는가?
- 동일한 협력 세션에서 상충하는 계획이 동시에 존재하지 않는가?
- 정상적인 계획 변경과 악의적인 계획 변경을 구분할 수 있는가?

### 0.3 연구 아이디어

본 연구는 다음 구조를 제안한다.

1. 차량이 미래 주행계획을 시간 구간별 **주행 허용영역(Trajectory Envelope)**으로 표현한다.
2. 각 시간 구간의 계획을 해시하여 Merkle Tree를 생성한다.
3. Merkle Root와 세션 정보를 AIMer 또는 HAETAE로 서명한다.
4. RSU 또는 복수의 주변 차량이 해당 Commitment를 확인하고 증인 서명 또는 확인값을 제공한다.
5. 차량은 주행 중 현재 시간 구간에 해당하는 계획과 Merkle Proof만 공개한다.
6. 동일 차량·동일 세션·동일 순번에 서로 다른 Root가 발견되면 상충 공격의 암호학적 증거로 사용한다.
7. 긴급 회피 등 정상적인 계획 변경은 이전 Commitment와 연결된 별도의 갱신 절차로 처리한다.

### 0.4 중요한 기술적 보완

**Merkle Root에 KpqC 서명을 한 번 붙이는 것만으로는 상충 공격을 막을 수 없다.**

악성 차량이 서로 다른 두 개의 Merkle Root를 만들고 각각 정상 서명하여 서로 다른 차량에 보낼 수 있기 때문이다.

따라서 본 연구의 핵심은 단순한 `KpqC + Merkle Tree`가 아니라 다음 결합이다.

```text
KpqC 서명
+ Merkle Commitment
+ RSU/주변 차량의 일관성 확인
+ 상충 증거 생성
+ 정상 계획 변경 프로토콜
```

---

# 1. 서론

## 1.1 연구 배경

협력 자율주행은 개별 차량의 센서 정보뿐 아니라 주변 차량의 의도와 예상 움직임을 활용한다. 특히 차선 합류, 교차로 통과, 군집주행처럼 여러 차량의 행동이 서로 영향을 주는 상황에서는 미래 주행계획의 신뢰성이 중요하다.

양자컴퓨터 위협에 대응하기 위해 차량 통신에도 양자내성 전자서명을 적용할 필요가 있다. KpqC 최종 전자서명 알고리즘인 AIMer와 HAETAE는 이러한 장기 전환을 위한 국내 후보 기술로 활용할 수 있다.

## 1.2 기존 방식의 한계

기존 V2X 인증 방식은 주로 다음 질문에 답한다.

> “이 메시지를 보낸 차량이 누구이며, 전송 중 변조되지 않았는가?”

하지만 협력 자율주행에서는 다음 질문도 필요하다.

> “이 차량이 다른 참여자에게도 동일한 주행계획을 제시했는가?”

정상 키를 가진 내부 공격자는 서로 다른 주행계획에 각각 정상 서명할 수 있다. 따라서 단순 서명 검증만으로는 계획의 전역적 일관성을 확인할 수 없다.

## 1.3 연구 목적

본 연구의 목적은 다음과 같다.

- 상충 주행계획 공격을 구체적으로 정의한다.
- KpqC 서명과 Commitment를 결합한 주행계획 인증 구조를 설계한다.
- RSU 또는 주변 차량 증인을 통해 계획의 일관성을 확인한다.
- 정상적인 긴급 계획 변경을 지원한다.
- 상충 공격 발생 시 제3자가 검증할 수 있는 증거를 생성한다.
- 실제 KpqC 구현을 이용해 연산량과 통신 오버헤드를 정량 평가한다.

## 1.4 연구 질문

- **RQ1.** 정상 서명을 가진 차량의 상충 주행계획을 기존 서명 방식만으로 탐지할 수 있는가?
- **RQ2.** 제안 프로토콜은 서로 다른 수신자에게 전달된 상충 계획을 얼마나 빠르게 탐지할 수 있는가?
- **RQ3.** 매 메시지마다 KpqC 서명을 수행하는 방식과 비교했을 때 연산량과 통신량은 얼마나 달라지는가?
- **RQ4.** 긴급 상황에서 정상적인 계획 변경을 허용하면서 상충 공격을 방지할 수 있는가?
- **RQ5.** 차량 수, 계획 길이, 통신 지연이 증가할 때 제안 방식의 확장성은 어떠한가?

## 1.5 연구 기여

본 연구의 예상 기여는 다음과 같다.

1. 협력 자율주행의 **Trajectory Equivocation Attack**을 공격 모델로 정의한다.
2. KpqC 서명, Merkle Commitment, 증인 확인을 결합한 프로토콜을 제안한다.
3. 상충하는 두 Commitment 자체를 검증 가능한 공격 증거로 구성한다.
4. 긴급 상황을 위한 체인형 Re-Commitment 절차를 설계한다.
5. AIMer와 HAETAE를 실제 적용하여 보안성과 성능을 함께 평가한다.

---

# 2. 기술적 배경 및 관련 연구

## 2.1 협력 자율주행과 주행 의도 공유

협력 자율주행에서는 차량 간 협상을 위해 다음 형태의 정보가 공유될 수 있다.

```text
차량 식별자 또는 가명 ID
협력 세션 ID
계획 유효시간
차선 또는 도로 구간
예상 위치 범위
예상 속도 범위
수행 동작
계획 순번
```

본 연구는 복잡한 자율주행 제어기 전체를 구현하지 않는다. 주행계획을 시간별 공간·속도 범위로 추상화하여 암호 프로토콜의 유효성에 집중한다.

## 2.2 KpqC 전자서명

본 연구에서는 KpqC 전자서명 알고리즘인 AIMer와 HAETAE를 적용 후보로 사용한다.

KpqC 서명은 다음 항목을 보호한다.

- Commitment 생성 차량의 인증
- Commitment 데이터의 무결성
- 공격 증거에 대한 부인 방지
- 장기적인 양자컴퓨터 위협 대응

두 알고리즘은 서명·검증 시간, 공개키·서명 크기, 메모리 사용량 등의 차이를 비교한다.

## 2.3 Commitment

Commitment는 값을 즉시 공개하지 않고 특정 값에 미리 구속되었음을 증명하는 구조다.

필요한 성질은 다음 두 가지다.

- **Binding:** Commitment 생성 후 다른 값으로 바꾸기 어려워야 한다.
- **Hiding:** 필요에 따라 원래 값을 즉시 전부 공개하지 않을 수 있어야 한다.

본 연구에서는 주로 Binding 성질을 활용한다.

## 2.4 Merkle Tree

각 시간 구간의 주행계획을 Leaf로 만들고 Merkle Tree를 구성한다.

```text
Leaf 0 = H(0.0~0.2초 계획)
Leaf 1 = H(0.2~0.4초 계획)
Leaf 2 = H(0.4~0.6초 계획)
...
Root   = MerkleRoot(Leaf 0, Leaf 1, ...)
```

차량은 전체 계획을 매번 보내지 않고 해당 시간 구간의 데이터와 Merkle Proof만 공개할 수 있다.

## 2.5 상충 공격과 서명의 한계

악성 차량은 동일한 협력 세션에서 서로 다른 두 개의 Root를 만들 수 있다.

```text
Root_L = 왼쪽 차선 변경 계획
Root_R = 오른쪽 차선 변경 계획

Sig_L = Sign_KpqC(Root_L)
Sig_R = Sign_KpqC(Root_R)
```

두 서명은 모두 정상일 수 있다. 그러므로 상충 공격 탐지에는 수신자 간 Root 비교, RSU 확인, 증인 공동서명 또는 Gossip 절차가 추가로 필요하다.

## 2.6 선행연구와 연구 공백

관련 연구는 대체로 다음을 다룬다.

- V2X 메시지 인증
- 협력 주행계획 공유
- 차량 오동작 탐지
- PQC 기반 차량 통신
- 분산 시스템의 Equivocation 탐지

본 연구는 이들을 결합하여 다음 공백을 대상으로 한다.

> 양자내성 서명이 적용된 협력 자율주행에서, 정상 자격증명을 보유한 차량이 수신자별로 상충하는 주행계획을 전송하는 문제를 어떻게 탐지하고 증거화할 것인가?

※ 실제 독창성은 추가 논문·특허 선행조사를 통해 최종 확인해야 한다.

---

# 3. 시스템 모델 및 위협 모델

## 3.1 시스템 구성요소

- **Subject Vehicle:** 주행계획을 생성하고 공유하는 차량
- **Peer Vehicle:** 계획을 수신하고 협력 주행에 참여하는 주변 차량
- **RSU/Witness:** Commitment의 일관성을 확인하는 도로 인프라 또는 증인 차량
- **Misbehaviour Authority:** 공격 증거를 수집하고 사후 대응하는 관리 주체
- **KpqC PKI:** 차량의 KpqC 공개키 또는 가명 인증서를 관리하는 기반

## 3.2 기본 가정

- KpqC 개인키는 차량 내부의 보호된 영역에 저장된다고 가정한다.
- 공격자는 자신의 정상 키를 사용할 수 있다.
- 공격자는 메시지를 지연, 재전송, 누락하거나 서로 다르게 전달할 수 있다.
- 공격자는 다른 정상 차량의 KpqC 서명을 위조할 수 없다고 가정한다.
- 사용한 해시 함수에 실용적인 충돌 공격이 존재하지 않는다고 가정한다.
- 기본 모델에서는 최소 한 개의 정직한 RSU 또는 일정 수의 정직한 증인이 존재한다고 가정한다.

## 3.3 공격자 모델

공격자는 다음 능력을 가진다.

- 자신이 보유한 정상 KpqC 키로 여러 계획을 서명
- 차량 B와 C에 서로 다른 Commitment 전송
- 과거 Commitment 재전송
- 정상 계획 일부 변조
- 긴급 갱신 메시지 위조 시도
- 네트워크 지연과 패킷 손실 유발
- 다수의 가명 ID를 이용한 Sybil 공격 시도

## 3.4 보호 범위에서 제외되는 항목

본 연구의 1차 범위에서는 다음을 완전히 해결하지 않는다.

- 차량 센서 자체가 생성한 잘못된 데이터
- 차량 제어 알고리즘의 안전성
- 모든 RSU와 증인이 동시에 악성인 경우
- KpqC 개인키 자체가 완전히 탈취된 이후의 모든 공격
- 실제 차량 동역학과 물리적 충돌 회피 성능

## 3.5 보안 목표

- **Authenticity:** Commitment의 발신자를 확인한다.
- **Integrity:** Commitment와 공개된 Leaf의 변조를 탐지한다.
- **Binding:** 한 Root에 포함되지 않은 계획을 정상 계획처럼 제시하지 못하게 한다.
- **Non-equivocation Acceptance:** 같은 세션과 순번에서 서로 다른 Root가 동시에 정상 승인되지 않게 한다.
- **Public Evidence:** 상충 공격을 제3자가 검증 가능한 증거로 남긴다.
- **Freshness:** 오래된 계획의 재전송을 차단한다.
- **Update Continuity:** 정상 계획 변경이 이전 계획과 연결되도록 한다.

---

# 4. 제안 프로토콜

## 4.1 전체 흐름

```text
[1] 주행계획 생성
        ↓
[2] 시간 구간별 Trajectory Envelope 생성
        ↓
[3] Merkle Tree 및 Root 생성
        ↓
[4] Root와 세션 정보를 KpqC로 서명
        ↓
[5] RSU 또는 증인 차량의 일관성 확인
        ↓
[6] Commitment 배포
        ↓
[7] 시간별 계획 + Merkle Proof 공개
        ↓
[8] 계획 일치 여부 검증
        ↓
[9] 상충 발생 시 Evidence 생성
```

## 4.2 Trajectory Envelope 정의

정확한 좌표 하나만 약속하면 정상적인 제어 오차도 공격으로 판단될 수 있다. 따라서 각 시간 구간은 허용 범위로 정의한다.

```json
{
  "slot": 3,
  "time_start": 0.6,
  "time_end": 0.8,
  "road_segment": "R12",
  "lane": 2,
  "position_min": 104.0,
  "position_max": 109.0,
  "speed_min": 12.0,
  "speed_max": 15.0,
  "action": "LANE_KEEP"
}
```

Leaf는 정규화된 데이터에 도메인 구분자를 포함하여 생성한다.

```text
Leaf_i = H(
    DOMAIN ||
    vehicle_pseudonym ||
    session_id ||
    plan_version ||
    slot_i ||
    canonical_trajectory_envelope_i
)
```

## 4.3 Commitment 생성

Commitment 데이터는 다음 정보를 포함한다.

```json
{
  "vehicle_pseudonym": "VID-A",
  "session_id": "MERGE-2026-001",
  "plan_version": 7,
  "parent_commitment": null,
  "valid_from": 100.0,
  "valid_until": 102.0,
  "slot_count": 10,
  "merkle_root": "ROOT_A",
  "hash_algorithm": "SHA-3-256",
  "signature_algorithm": "AIMer-or-HAETAE"
}
```

차량은 위 데이터 전체에 KpqC 서명을 생성한다.

## 4.4 Witness 확인

### 4.4.1 RSU 기반 방식

RSU는 다음 키를 기준으로 기존 Commitment를 조회한다.

```text
(vehicle_pseudonym, session_id, plan_version)
```

- 기존 Root가 없으면 등록하고 Witness Receipt를 발급한다.
- 동일한 Root이면 기존 Receipt를 반환한다.
- 서로 다른 Root이면 등록을 거부하고 상충 증거를 생성한다.

```text
WitnessReceipt = Sign_Witness(
    vehicle_pseudonym ||
    session_id ||
    plan_version ||
    merkle_root ||
    timestamp
)
```

협력 차량은 차량 서명과 Witness Receipt를 모두 확인한 Commitment만 사용한다.

### 4.4.2 인프라 없는 방식

RSU가 없는 경우 주변 차량은 자신이 받은 Commitment 해시를 서로 Gossip한다.

```text
GossipRecord = {
    sender,
    session_id,
    plan_version,
    merkle_root,
    vehicle_signature
}
```

같은 키에 서로 다른 Root가 발견되면 두 개의 정상 서명된 Commitment를 상충 증거로 사용한다.

이 방식은 탐지는 가능하지만, 상충 계획이 탐지되기 전에 일부 차량이 잘못된 계획을 사용할 수 있다는 한계가 있다.

## 4.5 계획 공개 및 검증

각 시간 구간에 차량은 다음을 전송한다.

```json
{
  "session_id": "MERGE-2026-001",
  "plan_version": 7,
  "slot": 3,
  "trajectory_envelope": "...",
  "actual_state": "...",
  "merkle_proof": ["HASH_1", "HASH_2", "HASH_3"]
}
```

수신 차량은 다음을 확인한다.

1. Commitment의 KpqC 서명
2. Witness Receipt 또는 Gossip 상태
3. Merkle Proof
4. 현재 시각과 Slot의 일치 여부
5. 실제 상태가 약속된 Envelope 안에 있는지 여부

## 4.6 정상적인 계획 변경

계획 변경 자체는 공격이 아니다. 앞차 급제동, 장애물 출현, 도로 통제 등으로 계획이 바뀔 수 있다.

새 Commitment는 이전 Commitment와 연결한다.

```json
{
  "plan_version": 8,
  "parent_commitment": "HASH_OF_VERSION_7",
  "update_reason": "EMERGENCY_BRAKING",
  "trigger_digest": "HASH_OF_TRIGGER_EVENT",
  "merkle_root": "NEW_ROOT"
}
```

갱신 규칙은 다음과 같다.

- `plan_version`은 증가해야 한다.
- `parent_commitment`는 현재 승인된 Commitment를 가리켜야 한다.
- 갱신 사유와 유효 시각을 포함해야 한다.
- 새 Commitment는 KpqC 서명을 받아야 한다.
- RSU 또는 증인은 새 버전을 승인하기 전에 버전 연속성을 확인해야 한다.
- 이전 버전과 새 버전의 유효시간이 불명확하게 겹치지 않도록 한다.

## 4.7 상충 증거

상충 증거는 다음 두 Commitment로 구성된다.

```text
Evidence = {
    Commitment_A,
    Signature_A,
    Commitment_B,
    Signature_B
}
```

다음 조건을 만족하면 상충으로 판정한다.

```text
A.vehicle_pseudonym == B.vehicle_pseudonym
A.session_id        == B.session_id
A.plan_version      == B.plan_version
A.merkle_root       != B.merkle_root
Verify(A.signature) == true
Verify(B.signature) == true
```

이 증거는 해당 차량이 동일한 세션과 버전에 두 개의 상충 계획을 직접 서명했다는 사실을 보여준다.

---

# 5. 보안 분석

## 5.1 서명 위조 공격

공격자가 다른 차량의 Commitment를 만들려면 해당 차량의 KpqC 서명을 위조해야 한다. KpqC 서명의 위조 불가능성을 전제로 이를 방어한다.

## 5.2 계획 데이터 변조

Leaf 데이터가 변경되면 Merkle Root와 일치하지 않으므로 검증에 실패한다.

## 5.3 상충 계획 공격

단순 KpqC 서명 방식에서는 두 개의 정상 서명된 계획이 동시에 존재할 수 있다.

제안 방식에서는 다음 중 하나로 탐지한다.

- RSU가 동일 버전의 두 번째 Root 등록을 거부
- 증인 차량 간 Gossip으로 서로 다른 Root 발견
- 두 정상 서명본을 공개 증거로 제출

## 5.4 재전송 공격

다음 필드를 검증하여 오래된 Commitment를 차단한다.

- 세션 ID
- 계획 버전
- 유효 시작·종료 시각
- Nonce
- 이전 Commitment 해시

## 5.5 긴급 갱신 악용

공격자가 반복적으로 긴급 갱신을 발생시키는 경우 다음 정책을 추가로 적용할 수 있다.

- 갱신 빈도 제한
- 갱신 사유 기록
- 주변 차량 또는 RSU의 Trigger 확인
- 비정상 갱신 횟수 누적
- 안전모드 전환 또는 Misbehaviour Report 생성

단, 센서 데이터의 사실성까지 암호만으로 완전히 증명할 수는 없다.

## 5.6 Witness 공격

단일 RSU가 악성인 경우 서로 다른 Root를 각각 승인할 수 있다. 이를 강화하려면 다음 확장이 필요하다.

- 복수 RSU의 공동 확인
- 일정 수 이상의 Witness Receipt 요구
- 차량 간 Receipt Gossip
- 상위 관리 시스템의 Append-only 로그

논문의 기본 구현에서는 단일 정직한 RSU 모델을 사용하고, 복수 Witness 모델은 확장 실험으로 구분하는 것이 현실적이다.

## 5.7 보안 정리 초안

다음 명제의 형태로 정리할 수 있다.

- **정리 1:** 충돌 저항 해시를 가정할 때, 공격자는 승인된 Merkle Root에 포함되지 않은 계획을 유효한 Proof와 함께 제시하기 어렵다.
- **정리 2:** KpqC 서명이 위조 불가능하고 Witness가 동일 버전에 하나의 Root만 승인한다면, 상충하는 두 계획이 동시에 정상 승인되기 어렵다.
- **정리 3:** 동일 차량이 상충하는 두 Commitment를 직접 서명한 경우, 두 서명본은 공개 검증 가능한 Equivocation Evidence가 된다.

※ 최종 논문에서는 각 명제의 가정과 공격 게임을 더 엄밀하게 작성해야 한다.

---

# 6. 구현 설계

## 6.1 구현 범위

실차, CARLA, 라즈베리파이 없이 일반 PC에서 구현한다.

```text
Vehicle Process A
Vehicle Process B
Vehicle Process C
RSU/Witness Process
Attack Generator
Result Collector
```

각 구성요소는 Python 프로세스 또는 컨테이너로 구현할 수 있다.

## 6.2 주요 모듈

```text
src/
├── kpqc/
│   ├── aimer_wrapper
│   └── haetae_wrapper
├── trajectory/
│   ├── generator.py
│   ├── canonicalizer.py
│   └── envelope.py
├── merkle/
│   ├── tree.py
│   └── proof.py
├── protocol/
│   ├── commitment.py
│   ├── witness.py
│   ├── reveal.py
│   ├── recommit.py
│   └── evidence.py
├── attacks/
│   ├── equivocation.py
│   ├── replay.py
│   ├── tampering.py
│   └── update_abuse.py
└── evaluation/
    ├── metrics.py
    └── report.py
```

## 6.3 주행계획 데이터 생성

복잡한 차량 동역학 대신 다음 시나리오를 시간·차선·위치 구간으로 생성한다.

- 직선 도로 차선 변경
- 고속도로 합류
- 교차로 진입 순서 조정
- 군집주행 합류·이탈
- 장애물 회피에 따른 정상 계획 갱신

## 6.4 구현 비교군

- **Baseline A:** 매 시간 구간 메시지마다 KpqC 서명
- **Baseline B:** 전체 계획 Root에 KpqC 서명만 적용하고 Witness 없음
- **Proposed:** KpqC Commitment + Witness/Gossip + Merkle Proof + Re-Commitment
- **Optional Baseline:** 기존 전자서명 기반 동일 구조

---

# 7. 실험 설계

## 7.1 실험 변수

| 구분 | 값 예시 |
|---|---|
| 차량 수 | 10, 50, 100, 500 |
| 계획 시간 | 1초, 2초, 5초 |
| Slot 개수 | 5, 10, 20, 50 |
| Witness 수 | 1, 3, 5 |
| 공격 차량 비율 | 0%, 1%, 5%, 10% |
| 네트워크 지연 | 0ms, 10ms, 50ms, 100ms |
| 패킷 손실 | 0%, 1%, 5%, 10% |
| 서명 알고리즘 | AIMer, HAETAE |
| 검증 방식 | Baseline A, Baseline B, Proposed |

## 7.2 정상 시나리오

- 모든 차량이 동일한 Commitment를 공유
- 계획에 따라 정상 주행
- 장애물 출현 후 정상 Re-Commitment
- 일시적 패킷 손실 후 재전송
- RSU 변경 또는 Witness 교체

## 7.3 공격 시나리오

### A1. Split-view Equivocation

```text
차량 A → 차량 B: Root_L
차량 A → 차량 C: Root_R
```

### A2. Replay

과거의 정상 Commitment를 현재 세션에서 다시 사용한다.

### A3. Leaf Tampering

공개되는 특정 시간 구간의 위치 또는 속도를 변경한다.

### A4. Fake Emergency Update

긴급 상황을 가장해 정상 계획을 반복적으로 변경한다.

### A5. Witness Unavailability

RSU 연결이 일시적으로 끊긴 상황에서 Gossip 방식으로 전환한다.

### A6. Multiple Malicious Vehicles

복수의 차량이 서로의 상충 계획을 정상으로 증언한다.

## 7.4 평가 지표

### 암호 연산 성능

- Commitment 서명 시간
- Commitment 검증 시간
- Merkle Proof 생성 시간
- Merkle Proof 검증 시간
- Re-Commitment 처리 시간

### 통신 비용

- 초기 Commitment 크기
- Witness Receipt 크기
- 시간 구간별 Reveal 메시지 크기
- 매 메시지 서명 방식 대비 총 전송량
- 차량 수 증가에 따른 네트워크 부하

### 보안 성능

- 상충 공격 탐지율
- 상충 공격 탐지시간
- 재전송 공격 차단율
- 변조 메시지 탐지율
- 정상 계획 변경 오탐률
- 공격 증거 생성 성공률

### 확장성

- 차량 수에 따른 처리량
- Witness 수에 따른 지연
- 동시 세션 수에 따른 메모리 사용량
- 계획 Slot 수에 따른 Proof 크기와 검증시간

## 7.5 결과 작성 원칙

결과를 미리 가정하지 않는다.

다음과 같은 표현은 실제 실험 후에만 사용한다.

```text
제안 방식은 Baseline 대비 상충 공격 탐지시간을 XX% 단축하였다.
제안 방식은 매 메시지 서명 방식 대비 총 전송량을 XX% 감소시켰다.
```

실험 전에 특정 수치나 탐지율 100%를 결론으로 정하지 않는다.

## 7.6 초기 최소 프로토타입 검증 결과

현재 구현된 Python 기반 최소 프로토타입을 실행하여, Commitment 등록, 중복 처리, Re-Commitment 검증, Equivocation 탐지 및 Evidence Bundle 생성 기능이 기본적으로 동작함을 확인하였다. 본 검증은 SUMO 기반 차량 이동 및 실제 KpqC 전자서명 적용 이전 단계의 기능 검증으로서, 프로토콜의 상태 전이와 판정 로직이 설계대로 동작하는지 확인하는 것을 목적으로 한다.

### 7.6.1 자동 테스트 결과

현재 구현에는 총 10개의 자동 테스트가 포함되어 있으며, 전체 테스트가 정상적으로 통과하였다.

- 자동 테스트 수: 10개
- 실행 결과: 10 passed
- 주요 검증 항목: Merkle Tree 생성 및 Merkle Proof 검증, Commitment 생성, Witness 판정, Re-Commitment 검증, 메시지 변조 검출

자동 테스트 결과는 현재 구현된 입력 조건과 시나리오에서 각 판정 함수가 예상한 결과를 반환했음을 의미한다. 이는 프로토콜의 모든 보안 속성을 검증했다는 의미는 아니다.

### 7.6.2 시나리오별 판정 결과

실행 결과는 다음과 같다.

```text
1. initial commitment                -> ACCEPT
2. duplicate commitment              -> DUPLICATE
3. valid re-commitment               -> VALID_UPDATE
4. same-sequence different root      -> CONFLICT
5. invalid parent root               -> INVALID_UPDATE
6. skipped sequence                  -> INVALID_UPDATE
7. tampered after signing            -> INVALID_SIGNATURE
8. expired commitment                -> STALE

ALL SCENARIOS PASSED
```

### 7.6.3 Evidence Bundle 요약

실행 중 생성된 Evidence Bundle에는 다음 정보가 포함되었다.

- Consistency Key: (Vehicle-A, MERGE-001, 1, 1)
- Witness ID: RSU-1
- 검출 시각: 1,000,000 ms
- 동일 Consistency Key를 가진 두 Commitment
- 서로 다른 두 Commitment의 Merkle Root
- 각 Commitment의 인증값
- 먼저 관찰된 Commitment에 대한 Witness Receipt
- 상충 Commitment에 대한 Witness 관찰 기록

검출 시각 1,000,000 ms는 테스트에서 사용한 고정 가상 시각이며, 실제 탐지 지연을 의미하지 않는다.

이 결과는 제안 프로토콜의 초기 기능 검증 기준점으로 해석할 수 있다. 현재 구현에서는 다음 동작을 확인하였다.

1. 최초 Commitment 수용
2. 동일 Commitment의 중복 메시지 식별
3. 정상 Re-Commitment 승인
4. 동일 Consistency Key의 서로 다른 Root 탐지
5. 잘못된 업데이트 거부
6. 인증 이후 메시지 변조 시 검증 실패 처리
7. 만료된 Commitment의 Stale 처리
8. 상충 탐지 시 Evidence Bundle 생성

현재 구현은 HMAC-SHA-256 기반의 테스트용 인증 모듈을 사용하므로, 위 결과는 양자내성 전자서명의 보안성이나 성능을 검증한 결과가 아니라 프로토콜 판정 로직과 증거 생성 기능의 검증 결과로 해석해야 한다.

### 7.6.4 향후 확장 방향

초기 최소 프로토타입 결과는 KpqC Wrapper 연결 전까지의 기능 기준점으로 유지한다. 이후 3장에서 확정한 프로토콜 규칙에 따라 다음 항목을 추가로 반영한다.

- Sequence 건너뛰기와 메시지 도착 순서 변경을 구분하는 Pending 처리
- Active Head, Observation, Pending Update 및 Evidence Store의 Cache 구조 분리
- Witness Receipt의 decision 필드 추가
- Commitment Digest 기반 중복 판정
- 차량 서명과 Witness Receipt를 검증하는 Gossip 처리 경로 추가

이러한 확장 작업은 AIMer·HAETAE Wrapper를 연결하기 전에 수행하여, 최종 프로토콜 규칙과 구현 코드의 판정 기준을 일치시키는 데 사용한다.

---

# 8. 예상 결과 분석 구조

## 8.1 KpqC 알고리즘 비교

- AIMer와 HAETAE의 서명·검증시간 비교
- 공개키와 서명 크기에 따른 통신 부담 비교
- Commitment 생성 빈도에 따른 총 연산량 비교

## 8.2 Merkle 구조 효과

- Slot 수 증가에 따른 Proof 크기 변화
- 전체 계획 재전송 대비 부분 공개의 통신량
- 매 메시지 KpqC 서명 대비 해시 검증의 처리량

## 8.3 상충 공격 탐지 효과

- Witness가 있을 때 두 번째 Root 승인 차단 여부
- Gossip 방식의 탐지 지연
- 네트워크 지연·손실에 따른 증거 수집 성공률

## 8.4 정상 계획 변경 분석

- Re-Commitment 처리시간
- 변경 빈도에 따른 오버헤드
- 정상 긴급 변경과 공격성 반복 변경의 구분 한계

## 8.5 종합 Trade-off

다음 관계를 분석한다.

```text
강한 일관성 보장
↔ Witness 통신량 증가

긴 계획 시간
↔ 갱신 빈도 감소
↔ 실제 상황 변화 대응성 감소

좁은 Trajectory Envelope
↔ 정밀한 검증
↔ 정상 오탐 증가

넓은 Trajectory Envelope
↔ 정상 오탐 감소
↔ 공격 탐지 민감도 감소
```

---

# 9. 논의

## 9.1 실제 적용 가능성

제안 프로토콜은 향후 다음 요소와 연계할 수 있다.

- V2X Maneuver Coordination
- RSU 기반 교차로 협력
- 고속도로 합류 협상
- 자율주행 군집주행
- Misbehaviour Reporting 시스템
- 차량용 가명 인증서 체계

## 9.2 개인정보 보호

고정 차량 ID를 사용하면 차량 이동경로가 추적될 수 있다. 따라서 실제 적용에서는 가명 ID와 협력 세션 간 연결성의 균형을 고려해야 한다.

상충 증거를 만들기 위해 일정 기간 동일 주체임을 연결해야 하지만, 불필요한 장기 추적은 방지해야 한다.

## 9.3 한계

- 실차 동역학을 검증하지 않는다.
- 일반 PC 결과를 차량 ECU 성능으로 주장할 수 없다.
- 단일 정직한 RSU 가정은 현실에서 강화가 필요하다.
- 실제 V2X 표준 메시지와 완전한 호환성을 입증하려면 추가 작업이 필요하다.
- 악성 차량이 Commitment와 실제 행동을 동시에 속이는 경우, 주변 센서와의 교차검증이 추가로 필요하다.
- KpqC 서명만으로 센서 데이터의 진실성을 보장할 수 없다.

## 9.4 연구의 차별점

본 연구는 단순히 다음을 수행하는 연구가 아니다.

```text
V2X 메시지에 KpqC 서명을 붙이고 성능을 측정한다.
```

핵심은 다음과 같다.

```text
정상 서명을 가진 내부 차량의 상충 주행계획
→ KpqC로 발신자를 인증
→ Merkle Commitment로 계획 변경을 구속
→ Witness/Gossip으로 수신자 간 일관성을 확인
→ 상충 시 공개 검증 가능한 증거 생성
→ 정상 긴급 변경은 체인형 갱신으로 허용
```

---

# 10. 결론 및 향후 연구

## 10.1 결론

본 연구는 협력 자율주행에서 정상 자격증명을 가진 차량이 서로 다른 참여자에게 상충하는 주행계획을 전달하는 문제를 다룬다.

KpqC 전자서명은 발신자와 메시지 무결성을 제공하지만, 여러 수신자가 동일한 계획을 받았는지는 단독으로 보장하지 않는다. 이를 해결하기 위해 KpqC 서명, Merkle Commitment, Witness 확인, Re-Commitment, 공개 증거 생성을 결합한 프로토콜을 제안한다.

## 10.2 향후 연구

- 복수 RSU 및 Threshold Witness 구조
- 실제 ETSI 또는 SAE 메시지 형식과 연계
- CARLA·Autoware를 이용한 주행 안전성 검증
- 차량용 ARM 보드에서 KpqC 성능 측정
- 가명 변경과 상충 증거 연결의 개인정보 보호
- 형식 검증 도구를 이용한 프로토콜 검증
- 센서 기반 정상 계획 변경 Trigger의 신뢰성 검증

---

# 11. 논문 목차 요약

```text
초록

1. 서론
  1.1 연구 배경
  1.2 기존 방식의 한계
  1.3 연구 목적
  1.4 연구 질문
  1.5 연구 기여

2. 기술적 배경 및 관련 연구
  2.1 협력 자율주행과 주행 의도 공유
  2.2 KpqC 전자서명
  2.3 Commitment
  2.4 Merkle Tree
  2.5 상충 공격과 전자서명의 한계
  2.6 선행연구 및 연구 공백

3. 시스템 모델 및 위협 모델
  3.1 시스템 구성요소
  3.2 기본 가정
  3.3 공격자 모델
  3.4 연구 범위
  3.5 보안 목표

4. 제안 프로토콜
  4.1 전체 흐름
  4.2 Trajectory Envelope 정의
  4.3 Commitment 생성
  4.4 Witness 확인
  4.5 계획 공개 및 검증
  4.6 정상 계획 변경
  4.7 상충 증거 생성

5. 보안 분석
  5.1 서명 위조 공격
  5.2 계획 데이터 변조
  5.3 상충 계획 공격
  5.4 재전송 공격
  5.5 긴급 갱신 악용
  5.6 Witness 공격
  5.7 보안 정리

6. 구현 설계
  6.1 구현 범위
  6.2 주요 모듈
  6.3 주행계획 데이터 생성
  6.4 비교군

7. 실험 설계
  7.1 실험 변수
  7.2 정상 시나리오
  7.3 공격 시나리오
  7.4 평가 지표
  7.5 결과 작성 원칙

8. 실험 결과 및 분석
  8.1 KpqC 알고리즘 비교
  8.2 Merkle 구조 효과
  8.3 상충 공격 탐지 효과
  8.4 정상 계획 변경 분석
  8.5 종합 Trade-off

9. 논의
  9.1 실제 적용 가능성
  9.2 개인정보 보호
  9.3 한계
  9.4 차별점

10. 결론 및 향후 연구
  10.1 결론
  10.2 향후 연구
```

---

# 12. 참고문헌 후보

1. KpqC 연구단, *Selected Algorithms from the KpqC Competition Round 2*, 2025.
2. ETSI TR 103 578 V2.1.1, *Intelligent Transport Systems; Vehicular Communications; Manoeuvre Coordination Service; Pre-standardization study; Release 2*, 2024.
3. ETSI TS 103 300-2 V2.1.1, *Intelligent Transport Systems; Vulnerable Road Users Awareness; Functional Architecture and Requirements Definition*, 2020.
4. SAE J3186, *Application Protocol and Requirements for Maneuver Sharing and Coordinating*.
5. SAE J3216, *Taxonomy and Definitions for Terms Related to Cooperative Driving Automation*.
6. Laurie, Langley, Kasper, *Certificate Transparency*, RFC 6962.
7. Hirata et al., *Roadside-assisted Cooperative Planning using Future Path Sharing for Autonomous Driving*, 2021.
8. Wu et al., *When Distributed Consensus Meets Wireless Connected Autonomous Systems: A Review and a DAG-based Approach*, 2023.
9. Ruj et al., *Data-centric Misbehavior Detection in VANETs*, 2011.

---

# 13. 현재 단계에서 먼저 해야 할 일

1. `Trajectory Equivocation`, `Maneuver Coordination Misbehavior`, `Non-equivocation V2X`, `Trajectory Commitment` 키워드로 논문·특허 선행조사를 수행한다.
2. RSU 기반 Witness 모델을 논문의 기본 모델로 확정한다.
3. Trajectory Envelope 데이터 구조와 정규화 규칙을 먼저 정의한다.
4. AIMer·HAETAE 공식 구현 패키지를 PC에서 빌드하고 서명·검증 API를 확인한다.
5. 차량 3대와 RSU 1대로 최소 기능 프로토타입을 구현한다.
6. 상충하는 두 Root가 생성·탐지되고 Evidence가 출력되는지 검증한다.
7. 이후 차량 수와 네트워크 조건을 늘려 성능 실험을 진행한다.
