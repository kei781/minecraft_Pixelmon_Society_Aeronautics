# 실제 아이템 소환과 렌더링 검증

기존 레지스트리 검사는 모드 아이템 17,239개의 기본 스택 저장·복원만 확인했다. 실제 소환·표시·사용과 구분한다. Task 9의 진단은 운영 팩에 넣지 않고 새 폐기 가능 QA 프로필에서만 사용한다.

`tests/forge-render-probe`와 `tools/forge-render-probe.gradle`을 고정 Forge 개발 트리에서 `-PpsaRenderProbeSource=/absolute/path/tests/forge-render-probe`로 지정하고 `reobfPsaRenderProbeJar`를 빌드한다. `tools/forge_resources.py canonical-jar`로 정규화한다. 출력은 `psa-render-probe-0.6.jar`다.

QA 서버는 고정 313개 모드와 진단 하나만 허용하는 별도 `render-qa-control.py`를 쓴다. 기존 운영 제어기의 313개 검사나 원래 월드를 바꾸지 않는다. 온라인 인증과 최대 6명 설정을 유지한다. `.psa-disposable-qa`, 정확한 원본 목록·진단 해시가 담긴 QA 영수증, JVM의 `-Dpsa.render.enabled=true`가 필요하다.

QA 제어기는 `enable-rcon=false`도 확인한다. 처음 시작할 때 새 `world-render-qa`에 프로필·생성 UUID가 담긴 소유 표식을 만든다. 이미 있는 월드에 맞는 표식이 없으면 시작·복구를 거부한다.

명령은 서버 콘솔에서만 실행한다. 다음 두 모드는 결과를 구분한다.

- `psa_render native 0 20000`: 정렬된 비바닐라 아이템을 최대 4개씩 실제 서버에 소환하고 레벨에 등록된 엔티티를 확인한다. 클라이언트·렌더 검사를 하지 않는다.
- `psa_render start PLAYER 0 20000`: 인증된 플레이어 앞에 최대 4개씩 소환한다. 클라이언트가 실제 엔티티의 ID·UUID·아이템 레지스트리를 대조하고 원래 렌더러가 반환한 뒤 응답해야 다음 묶음으로 넘어간다. 플레이어 이름은 콘솔 인수에만 쓰며 공개 기록에 넣지 않는다.
- `psa_render status`, `psa_render stop`: 진행 상태 확인과 해당 실행의 소유 UUID만 정리한다.

기본 스택 생성 전 후보 ID를 기록하고, 첫 예외·누락 모델·응답 지연·접속 해제에서 멈춘다. Forge가 드롭을 대체하면 원래 공장이 반환한 정확한 객체를 관찰하고, 지원하는 운반 API로 아이템을 대조한다. 관찰할 수 없는 경로는 통과로 세지 않고 멈춰 조사한다. 완료 묶음은 실행별 JSONL, 현재 상태는 `psa-validation/render-server-current.json`에 남긴다. 클라이언트도 렌더 진입·반환과 마지막 묶음을 기록하며 게임의 렌더 예외를 삼키지 않는다.

0.3 전수 소환은 3,484개 뒤 Create 꾸러미에서 멈췄다. 꾸러미는 원래 일반 드롭이 아닌 `PackageEntity`로 바뀐다. 전체 팩 354개 JAR·중첩 75개·클래스 79,468개에서 같은 Forge API 선언을 검색해 Create, Factory Logistics 꾸러미 두 종류, Sophisticated Backpacks 네 클래스를 확인했다. [동일 유형 조사](../evidence/custom-item-entity-family.json). 0.4는 Forge의 원래 공장을 한 번 그대로 호출한 결과를 관찰해 정확한 대체 객체·UUID를 추적한다. Create·하위 꾸러미는 공개 `getBox()` API로 아이템을 대조하며, 일반·하위 `ItemEntity`는 기존 API를 쓴다. 지원하지 않는 운반 형태는 중단한다. 원래 0.3 시험 월드는 통째로 보존했다.

0.4 관찰에서는 진단이 넣은 줍기 지연 `32767` 때문에 Create의 `verifyInitialEntity`가 꾸러미를 제거하는 것도 확인했다. 같은 검사를 상속하는 Factory Logistics 두 꾸러미도 조사했다. 0.5 기본 지연은 `32766`이며 무제한 수명의 나이 표식으로 병합을 막는다. `psa_render baseline_pickup INDEX`는 같은 진단 파일에서 원래 지연값을 한 아이템에만 재현하는 대조다. 실제 같은 0.5 파일에서 원본값의 꾸러미 제거를 재현했고, 수정값은 Create 일반·희귀 꾸러미와 Factory Logistics·기본 배낭 계열 44개를 통과했다. [회귀 결과](../evidence/custom-item-entity-regressions.json). 업그레이드를 조합한 NBT 변형의 검증으로 확대하지 않는다.

응답과 기록에 실제 엔티티 타입·클래스·대체 여부, 모델 조회 관찰 마스크를 넣는다. 렌더 반환과 모델 검증 수를 따로 센다. 모델 조회를 관찰하지 못하면 `model_lookup_unverified_mask`로 멈추며 정상 모델로 세지 않는다. 이 경우 자체 렌더러의 모델 경로를 추가 조사해야 한다.

서버 소환 성공만으로 렌더 성공을 세지 않는다. 렌더 반환도 모든 텍스처·NBT 변형·블록 설치·아이템 사용 검증을 뜻하지 않는다. 화면·상호작용 검사는 별도로 이어간다. 장애 발견 시 같은 아이템 클래스·렌더러·API 사용처를 조사하고 관련 회귀 검사를 마친 뒤 다음 묶음으로 진행한다.

초기 0.2의 플레이어 없는 검사에서 비활성 청크 때문에 첫 묶음이 시간 초과됐다. 같은 파일·같은 16개는 청크 활성화 후 모두 소환돼 진단 조건 문제로 구분했다. 0.3은 두 모드 모두 시험 위치의 청크를 유지하고 엔티티 틱 준비를 기다린다. 접속 해제·완료·서버 정상 종료 때 등록한 정확한 객체·UUID를 정리한 뒤 자신이 만든 청크 티켓만 해제한다. 기존 강제 로딩 티켓은 보존한다. 초기 실패·대조 기록은 보존한다.

비정상 종료 대비로 대체 공장 호출·등록 전에 소유 UUID와 청크 좌표를 원자적 체크포인트·추가 기록에 남긴다. 미정리 실행이 남으면 제어기는 재기동을 거부한다. 서버가 완전히 정지한 상태에서 `python3 render-qa-control.py recover`를 실행하면 소유 표식·프로필·생성 UUID가 일치하는 **해당 QA 월드 전체를 보존 디렉터리로 이동**하고 새 시험 월드를 만든다. 사용자가 시험 세이브 폐기를 허용한 범위의 복구다. 정상 정리는 개별 소유 객체만 대상으로 하고, 크래시 복구는 이 식별된 일회용 월드에만 한정한다. 다른 월드나 임의 NBT를 수정하지 않는다. `psa_render crash_test`는 이를 검사하는 의도적 QA 서버 크래시이며, 보통의 소환 검사는 이 명령을 사용하지 않는다.

실제 0.4 의도적 크래시에서 4개 UUID와 청크 좌표가 남았고, 0.5 제어기의 재기동 차단·RCON 활성 거부·복구를 확인했다. 보존한 월드의 전체 파일 트리 해시는 이동 전후 같았다. [크래시 복구 결과](../evidence/item-render-crash-recovery.json). 크래시 후 일부 작업 스레드로 JVM 종료가 지연됐다가 자체 종료했다. 종료 신호는 보내지 않았으며, 이 기록을 빠른 자동 복구나 모든 상류 모드의 종료 동작 검증으로 표현하지 않는다.

0.5는 기본 스택 17,239개를 실제 서버에 소환했고, 고유 아이템·엔티티 UUID·실행 ID와 4,310개 묶음을 대조했다. [전체 소환 결과](../evidence/item-render-native-full.json). 렌더·사용 검증 수는 0이다.

Claude R2가 찾은 부분 정리 실패도 보완했다. 0.6은 `discard()`가 반환하고 실제 레벨 조회에서 사라진 항목만 소유 목록에서 제거한다. 예외가 나면 실패 UUID·최초 원인과 영구 실패 플래그를 남기고 정리 완료를 표시하지 않는다. 청크 해제 실패도 같은 규칙을 쓴다. 비동기 응답 처리 예외는 기록 후 즉시 중단한다. 실제 `cleanup_failure_test`는 두 번째 소유 객체의 `EntityLeaveLevelEvent`에 예외를 넣어 원인 보존·다음 실행 거부·재기동 거부·실패 체크포인트 보존 복구를 확인했다. [부분 실패 검사](../evidence/item-render-cleanup-failure.json). 수정된 정상 정리 경로의 전체 소환 회귀 검사는 진행 중이다.

진단 통신은 [Forge SimpleImpl 공식 문서](https://docs.minecraftforge.net/en/1.20.1/networking/simpleimpl/)의 메인 스레드 처리와 방향별 패킷 등록을 따른다. 잘못된 실행 UUID·묶음·엔티티 ID·UUID·레지스트리·응답자는 거부한다. [현재 준비 기록](../evidence/item-render-probe-preparation.json).
