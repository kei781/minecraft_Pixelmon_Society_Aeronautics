# Bountiful 할인 표시와 서버 적용 범위 일치

완료 횟수 143의 게시판에서 평판 31·할인 41.3%가 표시됐다. 실제 서버의 의뢰 생성 경로는 평판을 -30..30으로 제한하므로 이 경우 적용 할인은 40%다. 작은 카운터에서도 재현돼 이전 16비트 정수 전송 오류와 구분한다. 큰 카운터 32,768·65,536에서는 화면에 752.0%·1069.3%가 표시됐다.

전체 v8 클라이언트 모드 354개, 중첩 라이브러리 75개와 클래스 79,467개를 검색했다. 같은 할인 API의 호출은 서버 의뢰 생성의 목표량 계산과 게시판 툴팁 두 곳이었다. 서버 생성자는 먼저 평판을 제한하지만 툴팁은 원래 평판으로 계산했다. 다른 모드의 동명 마나 할인 API는 다른 소유자·인수 형식이므로 구분했다. [호출부 조사](../evidence/bountiful-discount-callers.json).

클라이언트 전용 호환 모듈 1.1은 원래 할인 함수에 전달하는 평판을 같은 범위로 제한한다. 원래 평판·진행 막대·의뢰 완료 횟수는 보존한다. 기존 전용 서버의 의뢰 생성 경로에 맞춘 표시 보정이다. 일시정지 메뉴 보정 클래스 바이트는 이전 검토본과 같다.

후보 파일은 `PSA-Client-Menu-Compat-1.1.jar`, 4,778바이트, SHA256 `44cacaa5794d6ff581f8b8d4e877942187d28843c30d4d05395f91b6bbd1d9f9`다. 독립 소스 트리 두 곳의 빌드·재난독화·정규화 결과가 같다. 공통 포팅 JAR `59466e…`와 N100 공통 모드 313개는 그대로 사용한다. 최종 플레이어 안내는 [Windows 설치](windows-client.md)를 따른다.

격리 Forge 전체 팩에서 실제 원본 서버 생성자를 호출하고, 생성자에 전달되는 평판을 바꾸지 않는 관찰기로 읽었다. 이어 원본 할인 함수를 대조했다. 입력 70건에서 원본의 범위 밖 표시 차이 9건을 재현했고, 보정본은 모두 원래 서버 계산과 같았다. 정상 범위 61건의 원본·보정 결과는 IEEE754 비트 단위로 같다. [실행 기록](../evidence/bountiful-discount-runtime.json).

이 함수 검사는 클라이언트 전용 보정 클래스의 같은 바이트를 시험용 공통 믹신 설정으로 격리 전용 서버에 적용한 대조다. 해당 진단 JAR은 운영 서버·플레이어 패키지에 포함하지 않는다. 별도로 Windows 인증 접속 화면에서 평판 30·31·564·802의 할인 40.0%, 0 복구·재열기, 일시정지 메뉴 겹침 없음까지 확인했다. 기존 인스턴스에 후보를 적용한 검사이며 전체 팩 새 가져오기와 실제 의뢰 완료는 아직 검증하지 않았다. [Windows 결과](../evidence/bountiful-discount-runtime.json). 독립 재리뷰는 진행 중이다.

원본·보정 진단의 빌드 경로와 시험용 공통 믹신 설정을 저장소에 포함했다. 아래의 원본 작업은 후보 바이너리 인수 없이도 실행할 수 있다. 보정 작업은 정확한 1.1 후보 해시를 검증하고 해당 클래스 하나만 넣는다. 다른 버전 파일은 거부한다.

```bash
JAVA_HOME="$JDK17" GRADLE_USER_HOME="$TASK_GRADLE_HOME" \
  "$GRADLE" --no-daemon --offline -p "$PORT" \
  -I "$PSA/tools/forge-bounty-discount-probe.gradle" \
  -PpsaDiscountProbeSource="$PSA/tests/forge-bounty-discount-probe" \
  -PpsaDiscountHelperJar="$HELPER_JAR" \
  reobfPsaDiscountProbeJar reobfPsaDiscountPatchedProbeJar
python3 "$PSA/tools/forge_resources.py" canonical-jar \
  "$PORT/build/libs/psa-discount-probe-0.1.jar" /fresh/baseline.jar
python3 "$PSA/tools/forge_resources.py" canonical-jar \
  "$PORT/build/libs/psa-discount-patched-probe-0.1.jar" /fresh/patched.jar
```

`HELPER_JAR`는 위 44cac… 파일이다. 보정군은 `-Dpsa.discount.patched=true`로 실행한다. 새 보고서·성공 표식·실패 표식 부재·정상 종료를 함께 확인한다. 이전 수동 조립본과 새 빌드본의 해시 차이는 매니페스트·믹신 설정 직렬화·ZIP 메타데이터를 구분해 기록하며, 같은 클래스 바이트와 새 아티팩트 재실행으로 검증한다. [재생성 검증](../evidence/diagnostic-probe-recipes.json).
