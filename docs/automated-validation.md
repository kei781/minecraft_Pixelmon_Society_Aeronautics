# 자동 검증과 개발 도구

검사 순서는 정적 검사 → 자동 게임 검사 → 필요한 화면 확인이다.

| 수단 | 검사 범위 | 이 프로젝트 상태 |
| --- | --- | --- |
| Python/Java 코드 검사 | 패키지 해시·경로·의존성·실패 조건·좌표 계산 | 구현 및 실행 중 |
| Forge `runData`, `ExistingFileHelper` | 데이터 생성 시 모델·텍스처 등 참조 검사 | 포팅 리소스 생성 경로 사용. 모든 외부 모드를 자동으로 검증해 주는 것은 아님 |
| Forge GameTest / `runGameTestServer` | 화면 없이 게임 엔진에서 블록·월드 동작 검사 | 사용할 수 있는 공식 기능. 현재 전체 팩용 GameTest 시나리오는 아직 추가하지 않음 |
| QA 서버의 기존 네이티브 검사 모드 | 실제 등록·직렬화·소환·정리 및 클라이언트 응답 | 구현 및 실제 서버/인증 클라이언트에서 실행 |
| 클라이언트 모델 조회 진단 | 실제 기본 스택의 누락 모델·조회 예외 | 17,239개를 약 9.4초에 검사. 렌더·사용 증거와 구분 |
| 클라이언트 렌더 관찰 | 실제 소환 개체의 원래 렌더 경로 반환·모델 마스크 | 자동 실행. 별도 화면 조작 없이 결과·ACK 수집 |

GameTest는 테스트할 장면과 판정 코드를 작성해야 한다. 서버 엔진으로 검사하므로
사람이 게임 화면을 열어 조작할 필요는 없다. 렌더링 검사는 실제 클라이언트와 그래픽
컨텍스트를 실행하되, 한 번 실행한 클라이언트 안에서 여러 검사를 자동으로 돌린다.
로그인·신뢰 확인과 실제 화면 배치는 필요한 UI 확인으로 남는다.

공식 문서: [GameTest](https://docs.minecraftforge.net/en/1.20.x/misc/gametest/),
[데이터 생성과 ExistingFileHelper](https://docs.minecraftforge.net/en/1.20.1/datagen/).
# Native Pixelmon battle assertions without a client

The pinned upstream binary contains ten console-run native battle tests.
The separate [world fixture diagnostic](native-pixelmon-tests.md) supplies
actual owned Pokemon entities while retaining those original methods and
assertions. Its stock and adapted results are recorded separately; failures
and incomplete tests are not silently accepted. This diagnostic does not
belong in the player package and does not replace authenticated gameplay,
rendering or six-player load checks.
