# 메테노 장판 내장 검사 분류

Pixelmon 9.2.3의 원래 `shields_down_should_not_remove_hazards` 실패를
곧바로 실제 전투 버그로 간주하지 않고, 검사 조건과 진입 효과를 분리해 조사했다.
원래 판정·기술·난수·참가자 구성은 바꾸지 않았다. 기존 월드 기반 fixture를
그대로 사용하고 별도 관찰 모듈만 추가한다. 플레이어 팩에는 넣지 않는다.

[공식 스텔스록 설명](https://pixelmonmod.com/wiki/Stealth_Rock)은 교체 진입 때
타입 상성에 따른 피해를 받는다고 한다.
[공식 압정 설명](https://pixelmonmod.com/wiki/Spikes)도 교체 진입 조건과
비행 타입의 면역을 명시한다. 문서의 일반 규칙과 고정 바이너리의 실제 관찰을 구분한다.

원본 검사 관찰에서 메테노는 장판 설치 전부터 이미 필드에 있었다.
그 뒤 압정과 스텔스록이 설치됐고, 턴 종료 및 원래 판정 시점에도 둘 다 남았다.
HP는 12/12였다. 원본 검사에는 장판 설치 뒤 메테노를 교체 투입하는 단계가 없다.
이 조건에서 HP 감소를 요구한 원래 판정은 계속 실패로 기록한다.
특성이 장판을 지웠다는 증거는 이 경로에서 관찰되지 않았다.

별도로 명시적 옵션을 켠 새 실행에서는 원래 실패 결과가 계산된 **뒤** 같은 소유 전투의
원본 `applyEffectOnSwitch`를 직접 호출했다. 메테노 스텔스록 HP 12→9,
비행 메테노 압정 12→12, 잉어킹 스텔스록·압정 각각 11→10을 확인했다.
메테노의 원본 특성은 압정·스텔스록·독압정·끈적끈적네트·강철 장판과
대타출동을 허용했다. 이것은 해당 특성 API의 허용 응답이며 각 상태의 실제 적용 전체를
검증한 것은 아니다.

이 결과는 내장 검사의 누락된 진입 조건을 가리킨다. 별도 효과 호출은 실제 플레이어의
교체 선택이나 전체 교체 처리 경로를 실행한 것이 아니므로, 모든 교체·폼 전환·도구
조합의 정상 동작으로 확대하지 않는다. 이 조사만으로 운영 전투 코드를 보정하거나
원래 테스트를 강제로 통과시키지 않는다. 다른 내장 검사 실패도 보존한다.

## 진단 재생성

Java 17.0.21 / Gradle 7.6.4 / 준비된 Forge 47.4.20 환경과 원본 Pixelmon
SHA256 `8f2777f5a7cd2b5fc48ac3f5531d434af4120c7d40adc9929d5a3737c404246a`를 사용한다.
[기존 fixture 빌드](native-pixelmon-tests.md)를 먼저 준비한다.
이 모듈은 해당 소스나 JAR를 바꾸지 않는다.

```sh
gradle --offline --no-daemon --max-workers=2 -p /path/to/prepared-forge-workspace \
  -I /path/to/repository/tools/forge-pixelmon-hazard.gradle \
  -PpsaHazardSource=/path/to/repository/tests/forge-pixelmon-hazard \
  -PpsaPixelmonJar=/path/to/Pixelmon-1.20.1-9.2.3-universal.jar reobfPsaHazardJar
python3 tools/forge_resources.py canonical-jar \
  /path/to/prepared-forge-workspace/build/libs/psa-pixelmon-hazard-trace-0.1.jar \
  /path/to/fresh-hazard-trace.jar
```

새 폐기용 전용 서버만 사용한다. localhost 바인딩·온라인 인증·RCON 비활성·접속자
0명 조건을 유지한다. 기존 fixture 표식과 `psa.pixelmonFixture=true` 외에 다음이 필요하다.

- `.psa-pixelmon-hazard-trace`의 내용은 정확히 `psa-disposable-hazard-trace-v1` + 줄바꿈.
- JVM 옵션 `-Dpsa.pixelmonHazardTrace=true`.
- 효과 실험은 별도 `-Dpsa.pixelmonHazardEffects=true`로만 활성화.
- 기존 진단은 `psa-hp-fixture02-baseline-r2-current.jar`(SHA256 `26b8111035df030d44adf95e2a35eb581ecf834a6478c72776acc12284c46682`) 또는
  `psa-hp-fixture02-patched-r2-current.jar`(`21cd4d77d0f8e9e28dff49ba0c02669abbda175cf418cd6ba9a7679bb8b4c0c5`) 중 정확히 하나.

콘솔에서 기존 `psa_pixelmon_fixture`를 한 번 실행한다. 원래 검사와 별도 관찰 모듈의
두 mixin 설정이 모두 필요하다. 원본 네 반환 경로를 포함한 주입 개수를 엄격하게 확인한다.
최초 진단 빌드의 반환 개수 오류는 기동 전에 거부됐으며 실제 실행 증거로 사용하지 않는다.

Mixin plugin의 초기화 예외만으로는 Forge 전체가 중단되지 않고 설정만 빠질 수 있다.
실제 표식 누락 대조에서 이 약점을 확인해, 모드의 필수 생성자에서도 프로필을 검사하고
고정 검사 클래스를 로드한 뒤 정확한 관찰 변환의 적용 확인을 요구하도록 보강했다.
따라서 plugin의 검사와 실제 적용 증거를 각각 확인한다. 보강 전 실패 대조도 보존한다.

부모 fixture의 `FINISHED` 및 실제 엔티티·전투·바닥·청크 정리 결과를 먼저 확인한다.
그 뒤 `psa-pixelmon-hazard-trace/<UUID>/`의 순서가 가장 뒤인 `*-finished.json`을 읽는다.
원본 판정이 턴 종료 안에서 계산되므로, 그 뒤의 `after_end_turn` 관찰도 finished 파일을
추가한다. 파일은 교체하지 않고 매번 새 이름으로 쓴다.

`original_native_pass`는 원래 판정이며 변경하지 않는다. `probes`는 원래 결과 뒤의
별도 실험이다. 효과 실험은 HP를 복원하지만 네이티브 전투 기록·내부 카운터의 완전한
롤백을 제공하지 않는다. 전체 실험 전투를 폐기·정리해야 한다. `errors`가 있거나
효과 행의 `pass`·`health_restored`가 거짓이면 해당 실험을 통과로 간주하지 않는다.
I/O 실패는 예외로 드러내고, 오류나 치명적 중단으로 finished 파일이 없으면 완료가 아니다.
