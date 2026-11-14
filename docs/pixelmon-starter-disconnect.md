# Pixelmon 스타터 대기 중 로그아웃 오류

실제 N100 v16 서버는 2026-11-09 17:39:17 UTC(11월 10일 02:39:17 KST)에
Pixelmon 스타터 선택 재시도 중 종료됐다. 호스트 재부팅이 원인은 아니었다.
그 뒤 60초 watchdog 보고서는 종료 도중 발생한 후속 오류다. watchdog은 그대로 둔다.
이전 월드·설정·로그·크래시는 원본 서버를 정지한 상태에서 백업했다.

## 원인과 수정 범위

고정한 Pixelmon 9.2.3에서 `TickHandler.onServerTick`은 100틱마다 스타터 대기
UUID를 온라인 플레이어로 조회한다. 이미 나간 사람은 조회 결과가 null인데도
`StarterListPacket`을 전송해 Forge `PacketDistributor.playerConsumer`에서 NPE가 난다.

자체 mixin은 그 메서드의 패킷 호출 한 곳만 감싼다. 온라인 플레이어는 원래
`NetworkHelper.sendPacket`을 같은 인자로 호출한다. 오프라인 요청은 전송하지 않고,
원래 반복문이 끝난 뒤 그 재시도 구간에서만 목록에서 지운다. 반복 중 목록을
수정하지 않는다. 로그인 시 원래 Pixelmon의 등록 경로는 유지한다.
파티·포켓몬 저장소·선택 결과를 고치거나 일반 네트워크 전송기를 바꾸지 않는다.

기존 공통 JAR의 4,180개 항목은 바이트가 같다. 자체 클래스와 별도 mixin 설정을
추가하고 manifest·출처 기록만 바꾼다. 기존 HP mixin 설정도 그대로 유지한다.

## 검증 구분

- 원본 최소 서버: 합성한 **오프라인 대기 UUID 두 개**를 원래 목록에 넣으면
  실제 서버와 같은 NPE가 발생한다. 가짜 플레이어·인증 접속·6인 부하가 아니다.
- 수정 최소 서버: 같은 입력에서 220틱을 지나며 원래 목록에서 두 요청이 정리된다.
  진단 자체 정리 전에 목록을 확인한다. 정상 저장·종료와 크래시 0개를 확인했다.
- 전체 서버: 운영 모드 313개에 서버 전용 진단 하나를 더하고, 보존한 월드의 복사본으로
  같은 220틱 대조를 통과했다. 배포 팩에는 진단을 넣지 않는다.
- 실제 Mac 인증 접속: 원래 로그인 경로가 만든 온라인 스타터 요청이 추가 573틱 동안
  유지됐다. 정상 로그아웃 뒤 대기 목록은 0개가 됐고 서버는 계속 실행됐다.
  두 번째 실제 인증·월드 입장과 로그아웃도 확인했다. 두 번 나간 뒤 요청은 0개이며
  QA 서버 정상 저장·종료와 크래시 0개를 확인했다.
  [증거](../evidence/pixelmon-starter-disconnect.json).

이는 모든 아이템 사용·화면 렌더·장시간 안정성·실제 6인 부하의 합격을 뜻하지 않는다.
ALI·ReliableEmi 오류, 남은 모델·기술 동작 검증도 별도다.

같은 유형 조사는 스타터 목록 참조 5개 클래스와 UUID 조회·네트워크 참조 후보
9개 클래스를 대상으로 했다. 일부는 null 검사가 있지만 `PlayerPartyStorage`의
일부 전송 메서드와 TCG의 별도 전송기는 추가 대조가 필요하다.
문자열 참조 목록이 모든 동적 호출 경로를 보장하지는 않는다. 그 후보를 수정 완료로
기록하거나 전역 예외 무시로 덮지 않는다.

## 재생성

기존 [HP 공통 JAR](pixelmon-dynamax-hitpoints.md)을 먼저 만든다. 준비된
Forge 47.4.20 워크스페이스·Java 17에서 아래 두 작업을 실행한다.

```sh
gradle --offline --no-daemon --max-workers=2 -p /path/to/prepared-forge-workspace \
  -I /path/to/repository/tools/forge-starter-recipient.gradle \
  -PpsaStarterSource=/path/to/repository/tests/forge-starter-recipient \
  -PpsaPixelmonJar=/path/to/Pixelmon-1.20.1-9.2.3-universal.jar \
  reobfPsaStarterBaselineJar reobfPsaStarterPatchedJar
python3 tools/forge_resources.py canonical-jar \
  /path/to/prepared-forge-workspace/build/libs/psa-starter-probe-0.1-patched.jar \
  /path/to/fresh-patched-probe.jar
python3 tools/forge_starter_compat.py \
  --base /path/to/accepted-hp-common.jar \
  --tested-patch /path/to/fresh-patched-probe.jar \
  --pixelmon /path/to/Pixelmon-1.20.1-9.2.3-universal.jar \
  --output /path/to/fresh-starter-common.jar
```

입력·자체 소스·설정·클래스 해시는 `compat/pixelmon-starter-build.json`에 고정한다.
결과 SHA256은 `351ecb0905a7f05a262a9401fe0e968402896f527e5983838ef2014641e3a3db`다.
현재 준비·내보내기 도구는 이 JAR을 그대로 받지 않는다. 여기에
[포팅 결함 수정 두 건](coexistence-audit.md#포팅-jar-수정)을 더하면 `28e19585…`가 되고, 그 문서의 빌드·결합
절차에 이 결과를 `--base`로 준다. 현재 공통 JAR은 거기에 [접속 뒤 PC 다시 보내기](pixelmon-pc-resync.md)를
더한 `814b13eb…`다.
별도 준비 환경에서도 원본·수정 진단 두 JAR의 정규화 빌드가 각각 같았다.
포장 검사에 쓰는 모조 클래스 바이트는 게임으로 실행하지 않는다.

진단은 새 폐기용 프로필에만 설치한다. `.psa-starter-probe` 내용은 정확히
`psa-disposable-starter-probe-v1`과 줄바꿈이며 JVM에 `-Dpsa.starterProbe=true`가
필요하다. 필수 모드 생성자가 소유 표식과 원본 Pixelmon 해시를 확인한다.
실제 표식 누락 대조에서 생성자가 실패하고 월드·검사 결과가 생기기 전에 프로세스가
종료됐다. 이때 Forge 종료 코드는 0이었다. 최초 컨트롤러의 비영 종료 코드 가정은
실패했으며 그대로 기록했다. 시작 성공은 종료 코드만으로 판단하지 않고 새 `Done`·
월드와 실제 검사 결과를 확인한다.
원본 대조에는 baseline JAR만, 수정 최소 대조에는 patched JAR만 사용한다.
수정 공통 JAR를 사용한 전체 대조에는 **baseline 진단**을 써서 mixin 중복을 피한다.

콘솔 `psa_starter_probe_start`는 전용 서버·접속자 0명·빈 대기 목록에서 한 번만
실행한다. `psa_starter_queue_status`는 실제 인원과 대기 건수·서버 틱만 기록한다.
`psa_starter_probe_online_arm`은 실제 접속자 한 명·빈 목록일 때 원래 등록 API를
호출하는 별도 보조 명령이다. 이번 로그인 대조는 원래 경로에서 요청이 생겨 이
보조 명령을 사용하지 않았다. 원본 JSON은 고유 실행 경로에 새 파일로만 저장한다.
