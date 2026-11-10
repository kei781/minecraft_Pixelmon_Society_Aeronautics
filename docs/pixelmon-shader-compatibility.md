# Pixelmon 셰이더 패킷 호환 후보

이 문서는 셰이더 보정과 v6 당시의 구현·검증 기록이다. 해당 보정은 후속 통합 팩에도 포함되며, 최신 설치와 서버 짝 버전은 [Windows 안내](windows-client.md)와 [최신 진행 상태](progress.md)를 따른다.

Windows 게임을 켰다는 사용자 안내 뒤 N100 원문 로그에서 정품 인증과 월드 진입 2건을 확인했다. 첫 연결은 Pixelmon의 셰이더 매개변수를 엔티티 패킷에 기록하다 종료됐다. `ShaderParameters$Value.write:223`이 코덱 이름으로 null을 반환받아 `FriendlyByteBuf.writeUtf`에 전달한 오류다. [서버 관찰 기록](../evidence/n100-first-player-and-shader-failure.json).

이 기록의 실제 콘솔 `list`는 1/6명, `forge tps`는 TPS 20·전체 평균 8.141ms였다. 같은 시기의 TCP 상태 응답은 0명으로 달랐다. 실제 인원은 콘솔 결과를 기준으로 기록하며 이 수치를 6인 성능으로 환산하지 않는다. 두 인증 접속의 출발지가 지정된 같은 소유자 Windows 장치와 일치하는 것도 대조했다. Windows 파일 해시와 게임 화면은 상대 세션에서 아직 직접 대조하지 못했다.

## 확인한 원인과 수정

고정 [Pixelmon 9.2.3 원본](https://modrinth.com/mod/pixelmon/version/KjmzoXMR)의 셰이더 코덱 표는 기본값을 등록하는 메서드가 호출되지 않은 상태였다. 새 `PixelmonShaderCodecMixin`은 클래스 초기화 뒤 기존 이름 `int`, `float`, `float_array`와 대응하는 표준 코덱을 등록한다. 원래 초기화 메서드를 다시 호출해도 값과 이름이 유지되는 것을 검사했다. 임의 이름이나 대체 코덱을 만들지 않는다.

첫 문제를 해결한 뒤에는 색상 읽기 오류가 재현됐다. 원본 작성기는 RGBA의 0~255 값을 float로 쓰지만 원본 읽기는 0~1 float를 받는다. `PixelmonShaderColorMixin`은 해당 작성기 안의 정확히 네 `writeFloat` 인수만 255로 나눈다. 주입 개수가 다르면 로딩에 실패한다. 다른 숫자·셰이더 매개변수·플래그는 바꾸지 않는다. Pixelmon 원본 JAR도 수정하지 않는다.

## 실제 실행 검사

별도 루프백 Forge 47.4.20 / Java 17.0.21 서버에서 다음을 직접 실행했다. 검사 모드는 정상 종료되며 플레이어 설치 파일에 포함하지 않는다.

| 환경 | 결과 |
| --- | --- |
| 원본 Pixelmon + 자체 검사 모드 | 빈 코덱 표의 NPE 재현. 원래 초기화를 수동 호출한 대조에서도 색상 범위 오류 재현 |
| 같은 Pixelmon + 보정 믹신 + 검사 모드 | RGBA 4개, optional 2개 왕복 및 미지원 코덱 거부 1개, 총 7개 통과 |
| Society·Pixelmon·Aeronautics 전체 313 JAR + 검사 모드 1개 | 운영용 포팅 JAR의 믹신으로 같은 7개 통과. 퀘스트 1,142개, startup 97/97·server 188/188 스크립트 로딩 확인 |

왕복 검사는 코덱·int/float/float 배열 값·색상·플래그와 버퍼를 끝까지 소비했는지 비교한다. 지원하지 않는 문자열 코덱은 원래처럼 거부한다. 전체 팩에는 별도의 기존 레시피 fallback 경고가 남아 있으므로 전체 로그가 오류 없다고 주장하지 않는다. [검사·원문 로그 해시](../evidence/pixelmon-shader-wire-verification.json).

Claude R3는 합성 매개변수뿐 아니라 실제 Pixelmon이 만든 값을 확인하도록 P3를 지적했다. 이를 반영해 Pixelmon API로 Pikachu 엔티티를 만들고 내장 보스 등급을 설정해 시험 월드에 실제 추가했다. 실제 `SynchedEntityData`의 셰이더 값과 메타데이터 전체로 `ClientboundSetEntityDataPacket`을 구성하고 쓰기·읽기를 수행했다. 원본 보스에서도 두 오류가 재현됐으며, 보정 후에는 최소 구성과 전체 팩 각각 등록된 보스 9종 전부가 통과했다. 이 검사는 코덱을 고르거나 셰이더 매개변수를 직접 구성하지 않는다. 엔티티 ID와 셰이더의 코덱·값·색상·플래그 보존을 확인하고 생성한 시험 엔티티는 제거한다. 운영 패치는 이 재검사에서 바꾸지 않았다.

독립된 두 소스 트리에서 13개 빌드 작업을 모두 다시 실행했다. 정규화 결과는 동일하며, 실제 검사에 사용한 믹신 클래스와 전체 포팅 JAR의 해당 클래스도 바이트가 같았다. 이전 JAR에서 클래스 2개가 추가되고 호환 설정·출처 기록만 바뀌었다. 데이터 생성·리소스 내용은 그대로다. [재빌드 기록](../evidence/pixelmon-shader-port-rebuild.json).

## v6 배치와 남은 Windows 검증

Claude Opus 5.5 R4는 `d9c4de0`을 CLEAN으로 판정했고 검증된 브리지 적용 뒤 실제 미해결 스레드는 0건이다. CI 체크는 설정돼 있지 않다. 추가 정적 검사에서 Pixelmon 클래스 4,998개를 훑고 후보 7개를 디스어셈블했다. 보스 외 다이맥스·진화 경로도 FLOAT·FLOAT.listOf를 사용한다. 진화 뒤에는 기존 셰이더를 복구하는 호출도 있다. 이는 다이맥스·진화를 실제 실행한 증거는 아니다. [정적 검사](../evidence/pixelmon-shader-callsite-inspection.json).

2026-11-09 00:12 KST에 N100의 v6 정상 기동을 확인했다. 실제 콘솔 0/6명을 다시 확인하고 정상 저장·종료한 뒤 기존 월드·JAR·검증 목록·구성 기록을 백업했다. 패치 JAR 하나와 해당 검증 기록만 갱신했으며 모드 313개 해시가 일치했다. 재기동 후 Done, 온라인 인증 유지, 0/6명·TPS20·전체 평균1.251ms를 확인했다. 이 수치는 6인 성능이 아니다. [배치 기록](../evidence/n100-v6-shader-deployment.json).

아래 v6 파일, 서버 기동 완료 요청서와 비공개 접속 파일을 기존 같은 소유자 Taildrop으로 Windows PC에 전달했다. 채팅 read/send는 여전히 durable 호스트 오류로 실패하므로 상대 에이전트가 요청을 읽었다고 주장하지 않는다. Windows의 가져오기·파일 해시와 실제 재접속은 응답 대기 중이다. 서버에는 v6를 사용해야 하며 이전 v5는 보존만 한다.

- 파일: `PSA-Forge-Full-Experimental-v6.mrpack`, 1,137,774,105바이트.
- SHA256: `3b452f8068d4d02aeae89e293367540f3691c4c1134e3883b7691d5c6c979d2a`.
- 새 포팅 JAR SHA256: `a59a0f5cd89f319fb8280191388ab11752fefdf5553f864780c95bb479081b74`.
- 실제 macOS Prism 가져오기 후 payload 7,924개 해시·JAR 353개를 확인했다. 진단 모드는 포함되지 않았다. [가져오기 기록](../evidence/forge-client-import-v6.json).
- Python 회귀 검사: Ubuntu 47개 통과, macOS 44개 통과·Linux 전용 3개 제외. [검사 기록](../evidence/phase4-shader-controller-tests.json).

[독립 리뷰 수락 범위](../evidence/phase4-shader-review-acceptance.json)는 패킷 수정과 서버 배치 하위 작업까지다. 실제 Windows에서 보스 포켓몬을 추적해 같은 패킷 오류가 사라지는지, 포획·전투·Society 진행·조종 비행이 동작하는지는 별도 확인해야 한다. 실제 6인 부하와 최종 전체 리뷰도 남아 있다.

## 진단 재현

기존 고정 Forge 빌드 트리와 Java 17로 두 진단 JAR를 만든다.

```bash
gradle -p /path/to/pinned-forge-build \
  -I "$PWD/tools/forge-shader-probe.gradle" \
  -PpsaShaderProbeSource="$PWD/tests/forge-shader-probe" \
  -PpsaShaderPixelmonJar=/path/to/verified/Pixelmon-1.20.1-9.2.3-universal.jar \
  reobfPsaShaderBaselineJar reobfPsaShaderPatchedJar
```

입력 Pixelmon JAR는 원래 고정 SHA256과 맞아야 빌드한다. 새 루프백 시험 서버의 원본 대조에는 baseline JAR와 `-Dpsa.shader.baseline=true`를 쓴다. patched JAR에는 보정 믹신이 들어 있다. 전체 포팅 JAR를 검사할 때는 믹신이 중복되지 않도록 진단 클래스만 있는 baseline JAR를 쓰고 `-Dpsa.shader.baseline=false`로 실행한다. 원본은 실제 보스의 두 실패와 `BASELINE_REPRODUCED`, 보정본은 `REAL_BOSS_PASS tiers=9`와 마지막 `PATCHED_PASS cases=7`을 확인한다. 모든 경우 `FAILED` 부재·정상 종료·실제 입력 해시도 확인한다.
