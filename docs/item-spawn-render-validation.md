# 실제 아이템 소환과 렌더링 검증

기존 레지스트리 검사는 모드 아이템 17,239개의 기본 스택 저장·복원만 확인했다. 실제 소환·표시·사용과 구분한다. Task 9의 진단은 운영 팩에 넣지 않고 새 폐기 가능 QA 프로필에서만 사용한다.

`tests/forge-render-probe`와 `tools/forge-render-probe.gradle`을 고정 Forge 개발 트리에서 `-PpsaRenderProbeSource=/absolute/path/tests/forge-render-probe`로 지정하고 `reobfPsaRenderProbeJar`를 빌드한다. `tools/forge_resources.py canonical-jar`로 정규화한다. 출력은 `psa-render-probe-0.3.jar`다.

QA 서버는 고정 313개 모드와 진단 하나만 허용하는 별도 `render-qa-control.py`를 쓴다. 기존 운영 제어기의 313개 검사나 원래 월드를 바꾸지 않는다. 온라인 인증과 최대 6명 설정을 유지한다. `.psa-disposable-qa`, 정확한 원본 목록·진단 해시가 담긴 QA 영수증, JVM의 `-Dpsa.render.enabled=true`가 필요하다.

명령은 서버 콘솔에서만 실행한다. 다음 두 모드는 결과를 구분한다.

- `psa_render native 0 20000`: 정렬된 비바닐라 아이템을 최대 4개씩 실제 서버에 소환하고 레벨에 등록된 엔티티를 확인한다. 클라이언트·렌더 검사를 하지 않는다.
- `psa_render start PLAYER 0 20000`: 인증된 플레이어 앞에 최대 4개씩 소환한다. 클라이언트가 실제 엔티티의 ID·UUID·아이템 레지스트리를 대조하고 원래 렌더러가 반환한 뒤 응답해야 다음 묶음으로 넘어간다. 플레이어 이름은 콘솔 인수에만 쓰며 공개 기록에 넣지 않는다.
- `psa_render status`, `psa_render stop`: 진행 상태 확인과 해당 실행의 소유 UUID만 정리한다.

기본 스택 생성 전 후보 ID를 기록하고, 첫 예외·누락 모델·응답 지연·접속 해제에서 멈춘다. Forge가 기본 아이템 엔티티를 사용자 정의 `ItemEntity`로 바꾸면 실제 등록된 대체 엔티티를 관찰한다. 다른 종류의 사용자 정의 엔티티나 관찰할 수 없는 경로는 통과로 세지 않고 멈춰 조사한다. 완료 묶음은 실행별 JSONL, 현재 상태는 `psa-validation/render-server-current.json`에 남긴다. 클라이언트도 렌더 진입·반환과 마지막 묶음을 기록하며 게임의 렌더 예외를 삼키지 않는다.

서버 소환 성공만으로 렌더 성공을 세지 않는다. 렌더 반환도 모든 텍스처·NBT 변형·블록 설치·아이템 사용 검증을 뜻하지 않는다. 화면·상호작용 검사는 별도로 이어간다. 장애 발견 시 같은 아이템 클래스·렌더러·API 사용처를 조사하고 관련 회귀 검사를 마친 뒤 다음 묶음으로 진행한다.

초기 0.2의 플레이어 없는 검사에서 비활성 청크 때문에 첫 묶음이 시간 초과됐다. 같은 파일·같은 16개는 청크 활성화 후 모두 소환돼 진단 조건 문제로 구분했다. 0.3은 두 모드 모두 시험 위치의 청크를 유지하고 엔티티 틱 준비를 기다린다. 접속 해제·완료·서버 정상 종료 때 등록한 정확한 객체·UUID를 정리한 뒤 자신이 만든 청크 티켓만 해제한다. 기존 강제 로딩 티켓은 보존한다. 초기 실패·대조 기록은 보존한다.

진단 통신은 [Forge SimpleImpl 공식 문서](https://docs.minecraftforge.net/en/1.20.1/networking/simpleimpl/)의 메인 스레드 처리와 방향별 패킷 등록을 따른다. 잘못된 실행 UUID·묶음·엔티티 ID·UUID·레지스트리·응답자는 거부한다. [현재 준비 기록](../evidence/item-render-probe-preparation.json).
