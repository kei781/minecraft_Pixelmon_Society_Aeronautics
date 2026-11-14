# 실제 전체 기동에 도달한 별도 Forge 후보

Minecraft 1.20.1 / Forge 47.4.20 / Java 17에서 Society의 정식 서버팩 전체에 실제 Pixelmon과 Aeronautics 포팅 코드를 추가해 새 월드 기동을 확인했다. 완성된 Windows 배포나 N100 전체 팩 검증은 아직 아니다. 기존 1.21.1 개발 조합과 누락 파일 차단은 유지한다.

| 구성 | 고정 입력 |
| --- | --- |
| Society | [공식 서버팩 4.1.5A, CurseForge 8980858](https://www.curseforge.com/minecraft/modpacks/society-sunlit-valley/files/8980858), 원본 모드 JAR 311개 전부 |
| Pixelmon | [공식 Modrinth 9.2.3 베타 / MC 1.20.1](https://modrinth.com/mod/pixelmon/version/KjmzoXMR), 현재 1.21.1용 9.4.1과 다름 |
| Aeronautics | [Reon-dragon의 비공식 Forge 포팅 소스](https://github.com/Reon-dragon/create-aeronautics-forge/tree/c026749ab4d2c7a29693d8f67617be76bac73601), 고정 커밋 `c026749ab4d2c7a29693d8f67617be76bac73601` |
| 원본 리소스 | [공식 Aeronautics 1.3.0](https://modrinth.com/mod/create-aeronautics/versions), 실제 다운로드 메타데이터·해시를 로컬에 보존 |

포팅 소스는 약 1,700개의 Java 파일과 실제 Sable/Simulated/Offroad 및 Rapier 연결 코드를 포함한다. 이름이나 블록 ID만 만든 대체 파일을 사용하지 않는다. 원본의 일부 렌더링·선택적 연동 코드가 제외된 실험 포팅이므로 클라이언트 화면, 조종과 비행은 별도 검증이 필요하다.

Society 4.1.5A의 공개 Modrinth 클라이언트팩과 CurseForge 서버팩도 파일 목록이 완전히 같지는 않다. 같은 파일명 25개의 해시가 다르며, 일부는 manifest 차이다. 클라이언트팩 이름만 맞춘 것으로 접속 호환을 주장하지 않는다. 실제 파일/코드 비교 후 같은 공통 모드와 설정을 배치해야 한다.

## 빌드와 수정

빌드 JDK는 17.0.21+9, Gradle은 7.6.4, ForgeGradle은 5.1.77, MixinGradle은 0.7.38로 고정했다. 의존성은 작업 폴더의 Maven 저장소에 넣었고 전역 `mavenLocal`을 사용하지 않았다. 실제 `build`와 `reobfJar`를 통과했다.

- 포팅 저장소가 제외한 공식 아트 리소스 1,394개를 개인용 작업 폴더에 복원했다. 포팅의 번역 43개 파일은 보존했다.
- 실제 데이터 생성기를 실행했다. Gradle의 `runData`는 데이터 생성 후 부모 데몬 종료 오류를 냈으므로, `tools/run_forge_datagen.py`가 Gradle로 정확한 실행 정보를 준비한 뒤 독립 JVM에서 실행한다. 준비와 생성기 모두 실제 종료 코드 0을 확인했다. 실패는 성공으로 바꾸지 않는다.
- `--existing-mod create`를 데이터 생성 인수에 추가해 Create의 실제 텍스처를 참조한다.
- `tools/forge_resources.py`의 `flatten`은 모드별 생성 출력 917개를 표준 경로 901개로 정리하고 공유 태그 3개를 합친다. `combine`은 원본/생성 리소스 2,113개를 합친다. 번역은 수작업 값을 보존하고 누락 키를 추가한다. 사운드는 1.20.1용 생성 결과가 우선한다. 태그의 `values`와 Forge `remove`를 모두 보존하며 알 수 없는 충돌은 중단한다.
- 최종 리소스 디렉터리 하나만 패키징한다. 이전 출력의 빈 캐시 디렉터리도 제외한다.
- 실제 조립에서 재현된 Leaves Be Gone 8.0.0의 `Random block ticks was null` 오류를 위해 [청크 생성자 호환 소스](../compat/forge-port/LeavesBeGoneChunkMixin.java)를 추가했다. 새 청크의 긴 생성자에서만 선택적 큐를 초기화한다. 기존 청크의 큐를 다시 설정하지 않는다. 실제 조립과 저장 월드 재시작을 통과했다. FULL 청크 큐에 넣은 미래 틱도 저장·종료·재시작 후 그대로 남아 있음을 확인했다. 결과는 `evidence/forge-saved-world-verification.json`에 기록한다.
- 포팅본의 `/sable` 루트 명령 권한 0을 2로 바꿨다. 일반 플레이어가 구조물 생성·삭제·물리 일시정지 명령을 쓸 수 없게 한다. 실제 명령 트리 검사는 `tests/forge-candidate-probe.js`를 격리 시험에만 추가해 수행한다.

`compat/forge-port/candidate-build.patch`는 위 고정 소스에 적용하는 빌드/메타데이터/명령 권한 변경이다. `@PSA_LOCAL_MAVEN@`은 개인 작업 폴더 Maven 경로 자리표시자다. 현 단계는 직접 검증한 개발 절차이며 완성된 자동 소스 빌더는 아니다.

고정 소스의 새 복사본을 `PORT`, 이 저장소의 절대 경로를 `PSA`, JDK 17 경로를 `JDK17`, Gradle 7.6.4 실행 파일을 `GRADLE`로 준비한다. 전역 Maven 대신 개인 작업 폴더 Maven 저장소에 Create 6.0.8, Flywheel 1.0.5, Ponder 1.0.91, Registrate 1.3.3, MixinExtras Forge/common 0.4.1의 JAR/POM이 있어야 한다. 좌표는 포팅 소스의 build.gradle에 고정돼 있다. 이들은 확인한 공식 Create와 내장 라이브러리에서 준비했다. 해당 경로로 패치의 자리표시자를 바꾼 뒤 다음 순서를 따른다.

1. 고정 커밋의 깨끗한 소스에 `candidate-build.patch`와 `renderer-locals.patch`를 차례로 적용한다. `META-INF/mods.toml` 수정도 이때 적용된다.
2. 이 저장소의 `compat/forge-port/` Java 파일은 선언한 패키지에 맞춰 복사한다. 믹신은 `PORT/src/main/java/dev/psa/compat/`, `MenuIntData.java`는 `dev/psa/menudata/`, `JadeCoordinateMath.java`는 `dev/psa/jademath/` 아래에 둔다. 기존 같은 클래스 복사본을 중복으로 남기지 않는다. `psa-forge.mixins.json`, `PSA_PROVENANCE.txt`, `licenses/`는 `PORT/src/main/resources/`에 복사한다. 플레이어/광산수레 동기화 보정은 [별도 기록](player-data-compatibility.md)에 설명한다.
3. 공식 아트 파일을 검증·복원한다. 새 소스에서 실제 신규 파일 1,291개를 쓰고, 같은 내용 103개와 수작업 번역 43개를 보존했다.
4. 아래 데이터 생성·평탄화·결합·빌드를 차례로 실행한다. 모든 명령이 성공했을 때만 다음 명령으로 진행한다. 출력 디렉터리는 새 경로여야 한다.

```bash
python3 "$PSA/tools/restore_forge_assets.py" \
  --official-jar /path/to/create-aeronautics-bundled-1.21.1-1.3.0.jar \
  --resources "$PORT/src/main/resources"
python3 "$PSA/tools/run_forge_datagen.py" --project "$PORT" \
  --gradle "$GRADLE" --java-home "$JDK17" --gradle-home /path/to/task-gradle-home
python3 "$PSA/tools/forge_resources.py" flatten \
  "$PORT/src/generated/resources" "$PORT/src/generated/merged-resources"
python3 "$PSA/tools/forge_resources.py" combine \
  "$PORT/src/main/resources" "$PORT/src/generated/merged-resources" \
  "$PORT/src/generated/complete-resources"
JAVA_HOME="$JDK17" GRADLE_USER_HOME=/path/to/task-gradle-home \
  "$GRADLE" --no-daemon --max-workers 2 -p "$PORT" build
python3 "$PSA/tools/forge_resources.py" canonical-jar \
  "$PORT/build/libs/create-aeronautics-forge-1.20.1-1.3.0.jar" \
  /path/to/new-canonical-port.jar
```

데이터 생성 준비에 쓰는 `psaDataRecipe` 속성이 있으면 패치된 Gradle은 `src/main/resources`를 사용한다. 따라서 최초 `complete-resources`가 없어도 실행되며 초기 결합은 필요 없다. 최종 `build`는 `complete-resources`만 사용한다. 새 git-archive 소스에서 이 순서로 실제 생성기 종료 코드 0, 결합 2,113개, build/reobfJar 종료 코드 0을 확인했다.

두 빌드는 내부 파일 4,166개의 내용이 모두 같았으나 Forge 재난독화 후 ZIP 메타데이터가 달랐다. 마지막 `canonical-jar`가 파일 내용을 보존하고 ZIP 메타데이터를 정규화한다. 두 독립 빌드의 정규화 JAR SHA256은 모두 `0f7d57241f73b3de723a8c7fd2a7dba89e2d415323a9a49e0bd1c8ea66d12d08`이다. `evidence/forge-clean-rebuild.json`에 재현 범위와 실제 메타데이터 파일 해시가 있다.

위 해시는 Phase 2의 보존 기록이다. Phase 3의 실제 클라이언트 시험에서 포팅본의 `@ModifyArg` 세 개가 Oculus 콜백 지역 변수를 덮어쓰는 `VerifyError`를 재현했다. `renderer-locals.patch`는 같은 좌표 선택을 단일 `@WrapOperation`으로 수행한다. Pixelmon 9.2.3의 메뉴 코드도 없는 Realms 버튼을 참조했으므로 클라이언트 전용 `PixelmonMenuCompatMixin`은 기본 버튼 세 개가 모두 있을 때만 기존 메뉴 꾸미기를 실행한다. 기본 데모/사용자 지정 메뉴와 인증 제한은 유지한다.

v5 당시 배치용 정규화 JAR SHA256은 `cc31e4ab2684567361aab8fedc0be25bf437ea29f3b8626fa412ad16bd01a8de`다. 준비된 독립 소스 트리 두 개에 같은 수정과 메타데이터를 적용해 build/reobfJar 및 정규화 결과가 일치했다. 데이터 내용은 바뀌지 않아 데이터 생성기는 이 수정에서 다시 실행하지 않았다. 기존 JAR와 비교해 클라이언트 클래스·refmap·호환 설정·출처 기록만 바뀌었다. [재빌드 기록](../evidence/forge-client-fixes-rebuild.json).

## 격리 서버 준비

v6 당시 준비 도구는 Pixelmon 셰이더 패킷 보정을 포함한 `a59a0f5cd89f319fb8280191388ab11752fefdf5553f864780c95bb479081b74`를 고정했다. 위 `cc31e4…`와 함께 이전 운영본의 보존 기록이다. [v6 변경 범위](pixelmon-shader-compatibility.md)를 참조한다.

현재 준비·내보내기 도구의 공통 JAR 고정값은 `814b13eb950b738d17526b50dc5e19bb6454c486be05b012cd4b78182a98fee3`, 44,471,262바이트다. 아래 v17 공통 JAR에 [포팅 결함 수정 두 건](coexistence-audit.md#포팅-jar-수정)을 더하고(`28e1958563c4c313bbbf42448b15594c2cc8a3ca7a7f8d1ac5b7f47426f36c1c`, 44,468,740바이트, v20 팩과 2026-11-14까지의 운영 서버), 거기에 [접속 뒤 PC 다시 보내기](pixelmon-pc-resync.md)를 더한 것이다. 그 v17 공통 JAR은 `351ecb0905a7f05a262a9401fe0e968402896f527e5983838ef2014641e3a3db`, 44,465,167바이트다. 기존 등록·메뉴·[Jade](jade-sublevel-coordinates.md)·[누케닌 HP](pixelmon-dynamax-hitpoints.md) 보정에 [스타터 로그아웃 보정](pixelmon-starter-disconnect.md)을 더한 v17 후보이며 같은 JAR를 양쪽에 설치해야 한다. 이전 `53429378ccb8f591936736aee47da3b414222203b4e7650aa695b98d1f116e8c`는 v16 HP 단계 이력이자 starter overlay의 기준 입력이다. 이전 `31e38f3be687d1fa5f95570599abd3ee8e28e65506b2ac872fc3428ecd8426a5`는 v12~v15 이력과 HP overlay의 기준 입력이다. 이전 `59466e…` 메뉴 수락 파일도 현재 준비 도구 입력으로는 거부한다. 최신 N100 기동·검증은 [운영 기록](n100-server.md)에 구분한다.

해시를 고정한 세 입력이 로컬에 있을 때 다음 도구로 새로운 프로필을 준비한다. `forge-candidate-lock.json`의 실제 공식 다운로드 URL·배포처 SHA1/SHA512·크기도 확인하고 입력 검증 결과를 프로필 영수증에 남긴다. 원본 311개 JAR, Pixelmon 교체 데이터 68개를 확인한다. 기존 경로를 덮어쓰지 않는다.

```bash
python3 tools/stage_forge_candidate.py \
  --server-pack /path/to/SERVER-PACK-Society-Sunlit-Valley-4.1.5A.zip \
  --pixelmon /path/to/Pixelmon-1.20.1-9.2.3-universal.jar \
  --port /path/to/verified-private-port.jar \
  --destination /path/to/fresh-test-profile
```

Java 17과 Forge 47.4.20 서버 라이브러리는 별도로 설치해야 한다. 이 단계의 도구는 다운로드·서비스 설치·공개 포트 개방을 하지 않는다. 루프백 TCP/UDP 시험 포트 25573, 인증 사용, 최대 6명, 거리 4, 새 `world-psa-new`, 최대 힙 6 GB로 설정한다. 시험 후 콘솔 `stop`으로 종료한다.

Pixelmon 9.2.3은 `config/pixelmon/config.yml`의 `allow-vanilla-mobs`를 읽는다. 1.21.1용 `general.yml`과 경로가 다르다. 엔티티 교체 JSON도 `data/pixelmon/spawn_replacement/`의 구형 형식이므로 별도로 처리한다. 설정과 교체 데이터 68개를 함께 수정한다. 포켓몬 자체 스포너는 제거하지 않는다.

## 라이선스와 검증 한계

포팅 저장소의 포괄적인 MIT 표기만 믿고 모든 내용을 재배포하지 않는다. Aeronautics 코드 MIT, [Sable PolyForm Shield](https://github.com/ryanhcode/sable/blob/main/LICENSE.md), 아트 All Rights Reserved를 구분했다. 원본 리소스·제삼자 소스·개인용 합성 JAR·월드는 Git과 공개 리뷰에서 제외한다. 현재 공개 바이너리 배포는 하지 않았다.

전체 월드 시작과 퀘스트 로딩은 실제 플레이 성공을 의미하지 않는다. Windows 설치/접속, Pixelmon 포획·전투, Society 농사·경제·진행, Aeronautics 조립·비행, N100 전체 팩과 6인 부하 검증이 남아 있다. 일부 기존 모드의 ERROR 로그도 있어 오류 없는 팩이라고 표현하지 않는다.
