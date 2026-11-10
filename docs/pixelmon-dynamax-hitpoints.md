# 누케닌 다이맥스 최대 HP

고정 Pixelmon 9.2.3에서 다이맥스 전환은 누케닌의 HP 증가를 제외하지만,
`PixelmonWrapper.getMaxHealth(boolean)` 조회는 보너스를 더해 최대 HP를 2로 반환했다.
원본 내장 전투 검사는 최대 HP 1을 요구한다. [상류의 과거 동일 증상 기록](https://pixelmonmod.com/tracker.php?p=2&t=16276)도 이 규칙을 확인한다. 과거 기록의 버전이 현재 고정 버전을 뜻하지는 않는다.

`PixelmonDynamaxHitpointsMixin`은 다이맥스 중이고, 기본 HP를 요청하지 않았으며,
원래 포켓몬 종이 누케닌이고 실제 기본 HP가 1인 경우에만 반환값을 1로 보정한다.
현재 HP나 상태·명중·난수·원본 테스트 판정은 변경하지 않는다. 다른 포켓몬, 일반 상태,
기본 HP 조회 및 별도로 HP를 100으로 바꾼 누케닌의 기존 계산을 유지한다.
변신 전투나 레이드 전체의 실제 플레이를 검증했다고 주장하지 않는다.

고정 IV/EV 0, 레벨 1·50·100, 다이맥스 레벨 0·10으로 원본 API를 조회했다.
원본은 누케닌 여섯 경우만 최대 HP 2로 실패하고 나머지 14개 대조는 통과했다.
수정 후 단독 시험과 전체 313개 모드의 실제 공통 JAR 시험에서 20개가 모두 통과했다.
별도 기본 HP 100인 누케닌도 원래의 150/200 계산을 유지했다.
이 수치 검사는 가상 참가자의 조회이며, 실제 조작이나 전투와 구분한다.

리뷰 후 HP를 1로 바꾼 잉어킹 두 경우를 추가해 종 조건도 구분했다.
새 단독 원본·수정 JVM에서 22개를 다시 실행해 원본은 같은 여섯 경우만 실패했고,
수정은 22개 모두 통과했다. 잉어킹 HP 1의 다이맥스 조회는 두 레벨 모두 수정 전후 2로
유지됐다. 두 준비 빌드의 새 진단 JAR도 동일하며, 보정 클래스와 재생성 공통 JAR은
기존 v16과 바이트가 같다. 313개 전체 모드의 기존 20개 검사 기록은 그대로 보존한다.
[추가 종 조건 대조](../evidence/pixelmon-dynamax-hp-species-guard-regression.json).

별도로 실제 월드 엔티티를 쓰는 원래 누케닌 전투 검사도 실패에서 성공으로 바뀌었다.
전체 원본 검사 묶음은 아직 실패다. 메테노는 계속 실패했고, 전체 모드의 이번 표본에는
춤 기술 실패도 있었다. 춤 기술·셸트랩의 간헐 실패는 원본 Pixelmon만 여섯 번 반복한
대조에서도 재현됐다. 결과를 통과시키거나 반복성이 확보됐다고 주장하지 않는다.
[실제 결과](../evidence/pixelmon-dynamax-hp-native-regression.json).

## 재생성

Java 17.0.21, Gradle 7.6.4와 준비된 Forge 47.4.20 빌드 환경에서 실행한다.
원본 Pixelmon JAR 및 기준 공통 JAR의 해시는 `compat/pixelmon-hp-build.json`에 고정했다.
기준 공통 JAR은 이전 v15 팩에서 추출할 수 있다.

```sh
gradle --offline --no-daemon --max-workers=2 -p /path/to/prepared-forge-workspace \
  -I /path/to/repository/tools/forge-pixelmon-fixture.gradle \
  -PpsaPixelmonFixtureSource=/path/to/repository/tests/forge-pixelmon-fixture \
  -PpsaPixelmonJar=/path/to/Pixelmon-1.20.1-9.2.3-universal.jar \
  reobfPsaPixelmonFixtureJar reobfPsaPixelmonFixturePatchedJar
python3 tools/forge_resources.py canonical-jar \
  /path/to/prepared-forge-workspace/build/libs/psa-pixelmon-fixture-0.2-patched.jar \
  /path/to/fresh-tested-patch.jar
python3 tools/forge_hitpoint_compat.py --base /path/to/v15-common.jar \
  --tested-patch /path/to/fresh-tested-patch.jar \
  --pixelmon /path/to/Pixelmon-1.20.1-9.2.3-universal.jar \
  --output /path/to/fresh-v16-common.jar
```

검사용 baseline/patched JAR는 진단 전용이며 플레이어 팩에 넣지 않는다.
baseline은 새 보정 클래스와 등록을 제외한다. patched의 실제 사용 클래스와 공통 JAR의
보정 클래스 바이트는 동일하다. 두 준비 빌드에서 진단 JAR가 일치했고, 공통 overlay도
두 번 생성해 동일 바이트를 확인했다. 공통 JAR은 새 자체 클래스 하나와 자체 mixin 등록·
출처 기록 두 리소스만 달라지며 나머지 4,179개 항목은 그대로다.

완성된 공통 JAR은 44,462,825바이트, SHA256
`53429378ccb8f591936736aee47da3b414222203b4e7650aa695b98d1f116e8c`다.
소스·원본·검사용 JAR·클래스 해시가 다르거나 추가 등록이 섞이면 overlay를 거부한다.
기존 파일과 `mods/` 아래 직접 쓰기도 거부하며 새 경로에만 산출한다.

`psa_pixelmon_hp_controls` 명령은 기존 폐기용 fixture 표식·명시적 JVM 옵션,
전용 서버·온라인 플레이어 0명·콘솔 권한 4를 요구한다. 22개 수치 대조를 실행하고
고유 JSON을 `psa-pixelmon-hp-controls/`에 남긴다. 실제 월드 내장 전투 검사는 별도
`psa_pixelmon_fixture` 명령으로 실행한다. [진단 실행 조건](native-pixelmon-tests.md).

v16 팩은 v15와 비교해 공통 JAR·색인·프로필 정보 세 파일만 바뀌었다.
354개 모드, 리소스·스크립트와 기존 여섯 모델 연결을 유지하고 진단 도구는 제외한다.
새 Windows 가져오기, 실제 생존·수평 비행·6인 검증은 여전히 남아 있다.
