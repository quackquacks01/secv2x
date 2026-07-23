# KpqC 기반 Witnessed Trajectory Commitment 논문 개선 TODO

## 0. 논문의 중심 문장

> 기존 V2X 전자서명은 개별 메시지의 발신자와 무결성은 검증하지만, 정상 자격증명을 가진 차량이 수신자마다 서로 다른 주행계획을 보내는 Split-View/Equivocation은 검증하지 못한다. 본 연구는 KpqC 서명, Merkle Commitment, Witness/Gossip, Re-Commitment를 결합하여 이를 탐지하고 제3자가 검증 가능한 증거를 생성한다.

## 1. 현재 자료의 역할

- **논문 초안 PDF**: 정식 논문 형식과 프로토콜·실험 장의 뼈대가 있으나, 실험 완료 전인데 결과가 확정된 것처럼 쓰인 부분이 있음.
- **연구기획서 MD**: 연구 질문, 위협 모델, 비교군, 구현 모듈, 실험 변수가 가장 상세하고 현재 단계에 가장 정직함.
- **쉽게 설명한 버전**: 논문의 문제와 해결책을 가장 명확하게 설명하며, 초록·서론·발표의 기준 문장으로 활용 가능함.

---

# A. 논리와 주장 정리

## TODO 1. 실험 전·후 문장과 표기 분리
- [ ] `구축하였다`, `입증하였다`, `확보하였다`, `증명하였다`를 실험 전 문장으로 수정
- [ ] 결과 표의 `실측값`을 `측정 예정` 또는 `-`로 수정
- [ ] 실험 완료 후 값을 다음으로 구분
  - 프로토타입 벤치마크 측정값
  - 시뮬레이션/에뮬레이션 측정값
  - 실험 설정값
  - 산출값
- [ ] 실험 완료 후에만 초록·기여·결론에 정량 결과 반영

**완료 기준:** 실험 전 상태의 논문 어디에도 완료된 결과처럼 보이는 문장이 남지 않음.

## TODO 2. 공격 판정과 Re-Commitment 판정을 분리해 통일
- [ ] Commitment 필드와 Consistency Key를 전 장에서 통일
- [ ] Equivocation 판정은 다음으로 고정
  - Same Subject
  - Same Session
  - Same Epoch
  - Same Sequence
  - Both Signatures Valid
  - Different Root
- [ ] 정상 Re-Commitment는 별도 분기로 정의
  - `Seq_new = Seq_prev + 1`
  - `parentRoot = Root_prev`
  - 유효시간·비소급성·예외 컨텍스트 조건 충족
- [ ] 알고리즘, 수식, 설명문, 그림의 판정 흐름을 동일하게 수정

**중요:** 정상 Re-Commitment가 Sequence 증가를 전제로 한다면, `SameSequence ∧ NotValidUpdate`를 하나의 식에 넣기보다 Equivocation과 Update 검증을 별도 분기로 처리하는 편이 논리적으로 더 정확함.

## TODO 3. 과장되거나 AI 문장처럼 보이는 표현 정리
- [ ] 법적·사법적 효력을 직접 주장하지 않고 `제3자가 암호학적으로 검증 가능한 증거`로 표현
- [ ] `기하급수적`, `확고한`, `안정적으로 방어`, `패러다임 개척` 등의 표현 축소
- [ ] 관찰 결과와 해석을 구분

**완료 기준:** 모든 핵심 문장이 `문제-방법-관찰-해석` 순서로 읽히며 과장 없이 검증 가능함.

## TODO 4. 계산 복잡도 재정의
- [ ] Merkle Tree 생성: `O(m)`
- [ ] 단일 Proof 생성/검증: `O(log m)`
- [ ] 모든 Slot Proof 처리: 구현 방식에 따라 `O(m log m)` 또는 전처리 포함 별도 기술
- [ ] Evidence Bundle 검증: Witness Receipt가 k개이면 최소 `O(k)` 서명 검증
- [ ] 차량 서명 2개, Witness 서명 k개, 필요 시 Proof 검증 비용을 분리 표기

## TODO 5. 오탈자·용어·표기 전수 수정
- [ ] Runtime Disclouser → Runtime Disclosure
- [ ] 급정제 → 급정지
- [ ] 재재현성 → 재현성
- [ ] 객복적으로 발라낸다 → 객관적으로 분리한다
- [ ] 절감율/오탐율 → 절감률/오탐률
- [ ] 제 3 자 → 제3자
- [ ] 기존 V2X 암호화 기법 → 기존 V2X 보안 및 인증 기법
- [ ] KpqC, AIMer, HAETAE, Merkle Root, Witness Receipt 표기 통일

---

# B. 논문 구조 재편

## TODO 6. 3장 소제목 통합 및 반복 제거
권장 구조:

```text
3. KpqC 기반 Witnessed Trajectory Commitment 프로토콜
3.1 시스템 및 위협 모델
3.2 KpqC-Merkle 기반 Commitment 생성
3.3 런타임 검증과 Equivocation 탐지
3.4 예외 컨텍스트 기반 Re-Commitment
```

- [ ] 7계층 구조는 구현·분석에서 실제로 쓰이지 않으면 삭제
- [ ] Trust State 표는 실제 상태 머신으로 구현하지 않으면 축소 또는 삭제
- [ ] 전체 동작 흐름 반복 설명은 Sequence Diagram 하나로 대체
- [ ] 계산 복잡도는 3.3 말미에 짧게 정리

## TODO 7. 관련 연구를 네 영역으로 재구성
- [ ] 협력 자율주행의 주행계획 공유와 V2X 보안
- [ ] Misbehavior Detection과 메시지 간 일관성 한계
- [ ] Equivocation, Witness, Gossip, Transparency, Commitment 연구
- [ ] KpqC 전자서명과 본 프로토콜에서의 역할
- [ ] 마지막 절에서 기존 연구의 공백과 본 연구의 차별점 표로 정리

**완료 기준:** 독자가 2장만 읽어도 `왜 기존 연구로 해결되지 않는가`를 이해할 수 있음.

## TODO 8. 결론·향후 연구 축소
- [ ] 5.1은 연구 문제, 제안 구조, 실제 실험 결과, 의미만 작성
- [ ] 5.2는 다음 한계만 한 문단씩 작성
  - Witness 관찰 가능성과 공모
  - Plan-to-Behavior 부재
  - Envelope/Exception Context 설정
  - KpqC 연산·통신 비용과 실제 장치 검증
  - 가명 연속성과 프라이버시
- [ ] SUMO→CARLA→OMNeT++→ARM→HIL 로드맵은 삭제 또는 부록 이동

---

# C. 구현 및 실험

## TODO 9. 시뮬레이션 범위 확정
### 1차 필수 범위
- [ ] Python 프로토타입
  - Canonical Encoding
  - Merkle Tree/Proof
  - KpqC Wrapper
  - Witness Cache/Receipt/Gossip
  - Re-Commitment
  - Evidence Bundle
- [ ] SUMO + TraCI
  - 차선 변경, 합류, 교차로 시나리오
  - 차량별 미래 Trajectory 추출
  - 공격 차량의 수신자별 상충 Commitment 전송
  - RSU/Peer Witness 관찰 범위

### 선택 확장
- [ ] 네트워크 지연·손실이 핵심 결과가 되면 Eclipse MOSAIC 또는 Veins/OMNeT++ 추가
- [ ] Plan-to-Behavior까지 확장할 때만 CARLA 사용

### 비교군
- [ ] Baseline A: Slot별 KpqC 서명
- [ ] Baseline B: Root 서명만 사용, Witness 없음
- [ ] Proposed: KpqC + Merkle + Witness/Gossip + Re-Commitment

### 최소 실험 질문
- [ ] 공격을 탐지하는가
- [ ] 정상 Re-Commitment를 오탐하지 않는가
- [ ] Witness 수·패킷 손실·차량 수에 따라 탐지율과 지연이 어떻게 변하는가
- [ ] KpqC 반복 서명을 Merkle Proof로 대체할 때 연산·통신 비용이 어떻게 변하는가

## TODO 10. 제목 확정
권장 제목:

**협력 자율주행의 주행계획 상충 공격 탐지를 위한 Witnessed Trajectory Commitment: KpqC 기반 설계 및 평가**

영문:

**Witnessed Trajectory Commitment for Detecting Trajectory Equivocation in Cooperative Autonomous Driving: A KpqC-Based Design and Evaluation**

- [ ] 실험 전에는 `설계` 중심 제목 사용 가능
- [ ] 실험 완료 후 `설계 및 평가` 사용
- [ ] 책임성은 제목보다 초록·기여에서 `검증 가능한 Evidence Bundle`로 명확히 제시

---

# D. 추가로 반드시 검토할 핵심 항목

## TODO 11. `서로 다른 Root`와 `의미론적으로 상충하는 주행계획`의 관계 명확화
현재 판정식은 같은 Consistency Key에 서로 다른 Root가 존재하면 **Commitment Equivocation**을 탐지한다. 그러나 서로 다른 Root가 항상 물리적으로 양립 불가능한 궤적을 뜻하는 것은 아니다.

다음 중 하나로 논문 범위를 명확히 해야 한다.

### 선택 A. 보안 위반을 Equivocation으로 정의
- 동일 Sequence에서 복수 Root를 발행하는 행위 자체를 금지
- 두 계획이 물리적으로 충돌하는지와 무관하게 프로토콜 위반으로 판정
- 제목과 본문에서 `Trajectory Equivocation`을 중심 용어로 사용

### 선택 B. 의미론적 상충까지 판정
- 서로 다른 Root 발견 후 공개된 Envelope 간 시간·공간·행동 호환성 검사 추가
- `Root 불일치 탐지`와 `Trajectory Conflict 판정`을 2단계로 분리

**권장:** 1차 논문은 선택 A가 더 명확하고 구현 가능함. `주행계획 상충 공격`은 동일 버전에서 복수의 주행계획을 발행한 Equivocation으로 정식 정의하고, 실제 궤적의 물리적 충돌 여부는 후속 연구로 구분함.

---

# E. 작업 순서

## Phase 1. 실험 전 원고 정리
1. TODO 11 연구 범위 확정
2. TODO 2 공격/업데이트 판정식 확정
3. TODO 1 시제·표기 수정
4. TODO 6~8 목차 재구성
5. TODO 3~5 문장·복잡도·용어 교정
6. TODO 10 제목 확정

## Phase 2. 최소 프로토타입
1. 차량 3대 + Witness 1대
2. 정상 Commitment 생성·검증
3. 동일 Sequence 복수 Root 탐지
4. 정상 Re-Commitment 승인
5. Evidence Bundle 검증

## Phase 3. 성능 벤치마크
1. AIMer/HAETAE 서명·검증
2. Merkle 생성·Proof 검증
3. 직렬화 Byte 크기
4. Baseline A/B/Proposed 비교

## Phase 4. SUMO 연계 실험
1. 차선 변경
2. 고속도로 합류
3. 교차로 진입 순서
4. 패킷 지연·손실
5. 차량 수·Witness 수 확장

## Phase 5. 논문 결과 작성
1. 측정값/설정값/산출값 구분
2. 연구 질문별 결과 제시
3. 관찰과 원인 해석 분리
4. 한계와 외적 타당성 명시
5. 초록·기여·결론 최종 수정

---

# F. 논문이 끝까지 유지해야 할 핵심 메시지

1. **문제:** 정상 서명은 메시지 진위를 보장하지만 여러 수신자에게 동일한 계획을 보냈는지는 보장하지 않는다.
2. **제안:** KpqC 서명으로 발신자와 부인방지를 확보하고, Merkle Commitment로 계획을 고정하며, Witness/Gossip으로 Split-View를 탐지한다.
3. **예외 처리:** 정상 계획 변경은 Sequence 증가와 parentRoot 연결을 갖는 Re-Commitment로 구분한다.
4. **결과:** 탐지 가능성, 오탐, 탐지 지연, 연산·통신 오버헤드, 확장성을 실제 측정값으로 평가한다.
5. **의미:** KpqC 알고리즘 적용 연구가 아니라, 양자내성 인증 위에 메시지 간 일관성 검증과 책임성을 추가한 프로토콜 연구다.
