WTC 논문 캡처용 SUMO 시나리오
================================

핵심 변경점
- 차량 사진 없이 SUMO simple shapes를 사용
- Vehicle-A: 빨간 sedan
- Witness-W1/W2: 파란 hatchback
- 회색 배경 차량 7대 추가
- 교차로 중심 자동 확대
- 차량 ID와 POI ID 표시
- 횡단보도, 정지선, RSU, 통신 반경/링크를 additional.xml로 시각화
- crossings.guess로 생성된 불필요한 walking area 제거
- 차량을 캡처 위치 부근에 배치하여 시작 직후 화면 구성 완료

권장 실행
1. 이 폴더에서 PowerShell 실행
2. 다음 명령 입력

   .\run_capture.ps1

수동 검증
   python .\validate_capture.py
   sumo -c .\capture.sumocfg --check-route true

수동 실행
   sumo-gui -c .\capture.sumocfg --start --quit-on-end false

캡처 추천
- 시뮬레이션 2~5초
- Vehicle-A, Witness-W1, Witness-W2, RSU-1이 모두 보이는 기본 시점
- View Settings에서 차량 모양이 바뀌었다면 Vehicles > Shape scheme > simple shapes
- 그림 설명:
  "WTC 프로토콜의 Subject Vehicle, Peer Witness 및 RSU 배치를 설명하기 위한 SUMO 기반 시각화 시나리오"

주의
- 이 화면은 프로토콜 배치 설명용 시각화이다.
- 정량 성능 결과로 제시하려면 별도의 TraCI 실험 로그와 평가 조건이 필요하다.
