# 수레와 게시판 메뉴의 정수 전송 보정

Windows 탱크 수레 화면이 서버의 물 1,000mB를 0mB로 표시했다. 수레의 실제 런타임 번호 251,992가 메뉴 패킷에서 -10,152로 잘려 클라이언트가 수레를 찾지 못했다. [Forge 1.20.1 공식 문서](https://docs.minecraftforge.net/en/1.20.1/gui/menus/)도 `DataSlot`과 `ContainerData` 값의 전송 범위가 signed 16-bit라고 설명한다.

같은 유형을 조사해 More Minecarts 1.8.3의 배터리 수레에서도 같은 번호 전송 경로를 발견했다. 배터리의 클라이언트 생성자가 탱크 메뉴 종류를 사용하던 오류도 별도로 확인했다. Bountiful 6.0.4 게시판의 누적 완료 횟수 역시 같은 전송 경로를 사용해 큰 횟수가 잘렸다.

`MenuIntData`는 기존 논리 데이터의 int 하나를 유지하면서 전송할 때만 16비트 두 개로 나눈다. 탱크·배터리는 첫 두 값이 모두 도착하기 전 수레 조회를 보류한다. 번호 일부만 도착한 순간 다른 수레를 캐시하는 경우도 대조 시험에 포함했다. 게시판에도 같은 전송 래퍼를 적용한다. 배터리 생성자는 이미 등록된 배터리 메뉴 종류를 사용한다. 모든 수정은 해당 생성자·초기화 호출에 한정하며 원본 모드 JAR과 전역 패킷 형식은 보존한다.

이 메뉴 하위 작업 수락 당시 공통 JAR은 `59466e8555cb442e3aa042d8c673cb05b8a2bcdf3a3931494920829156bc58fe`, 44,453,781바이트다. 아래 진단 재현 명령은 이 역사적 파일을 고정한다. 현재 준비 도구는 [Jade](jade-sublevel-coordinates.md)·[누케닌 HP](pixelmon-dynamax-hitpoints.md)·[스타터 로그아웃 보정](pixelmon-starter-disconnect.md)을 포함한 `351ecb0905a7f05a262a9401fe0e968402896f527e5983838ef2014641e3a3db`, 44,465,167바이트를 사용한다. 이전 `53429378…`는 v16 HP 단계 이력이자 starter overlay 기준 입력이며 `31e38f3b…`는 v12~v15 이력과 HP overlay 기준 입력이다. 이전 메뉴 클래스의 바이트는 그대로이며 양쪽에 같은 현재 파일이 필요하다. 진단 모드는 배포에 포함하지 않는다.

최소 구성과 전체 313개 모드 구성에서 원본 대조군과 수정본을 실행했다. 실제 바닐라 `ClientboundContainerSetDataPacket` 쓰기·읽기를 거쳐 탱크·배터리의 16가지 경계값, 다른 수레를 선택하는 2가지 대조, 전체 팩에서는 게시판의 8가지 경계값을 확인했다. 같은 게시판 메뉴를 연 상태에서 `broadcastChanges`가 보내는 실제 갱신도 5가지 값으로 추가 확인했다. 전용 서버 안에서 실제 클라이언트 생성자와 메뉴 로직을 검사하는 시험이며, 인증된 Windows 클라이언트의 렌더링 검증과 구분한다.

준비된 독립 소스 트리 두 곳의 build/reobfJar 결과를 정규화해 바이트 일치를 확인했다. 이전 등록 순서 보정 후보와 비교하면 자체 클래스 6개, 믹신 설정과 출처 기록만 추가·변경됐다. [프로토콜 시험 기록](../evidence/menu-data-wire-verification.json)과 [같은 유형 조사](../evidence/menu-data-family-audit.json)에 범위와 한계를 남긴다. 같은 후보의 실제 Windows 탱크·배터리·깃발·게시판 큰 카운터 표시와 갱신을 확인했고, 최신 Claude Opus5.5 R4 CLEAN 및 실제 PR 미해결0건으로 메뉴 정수 보정 범위를 수락했다. v8 새 GUI 가져오기·전체 플레이 완료를 뜻하지 않는다. [하위 작업 수락](../evidence/task7-menu-data-review-acceptance.json). 고평판 할인 툴팁과 서버 제한이 다른 기존 표시 오류는 별도 후속으로 남긴다.

진단 빌드는 기존 고정 Forge 개발 트리에서 다음처럼 수행한다. `psaMenuIdProbeJar`만 실행한 파일은 개발 매핑을 사용하므로 실제 서버에 넣지 않는다.

```bash
JAVA_HOME="$JDK17" GRADLE_USER_HOME="$TASK_GRADLE_HOME" \
  "$GRADLE" --no-daemon --offline -p "$PORT" \
  -I "$PSA/tools/forge-menu-id-probe.gradle" \
  -PpsaMenuIdProbeSource="$PSA/tests/forge-menu-id-probe" \
  -PpsaMenuIdPortJar="$PORT_JAR" \
  reobfPsaMenuIdProbeJar reobfPsaMenuIdPatchedProbeJar
```

출력은 `build/libs/psa-menu-id-probe-0.1.jar`와 `build/libs/psa-menu-id-patched-probe-0.1.jar`다. `PORT_JAR`는 위 59466e… 공통 포팅본이다. 전체 모드 시험에서는 원본 공통 후보와 새 공통 후보에 각각 원본 관찰 진단을 더해 실행한다. 최소 수정 시험에는 고정 해시를 검증한 포팅본에서 자체 메뉴 클래스 5개와 커밋된 시험용 믹신 설정만 더하는 보정 작업을 사용한다. 정규화는 두 출력 모두 `tools/forge_resources.py canonical-jar`로 수행한다. 원본 대조군은 `-Dpsa.menu.baseline=true`로 실행한다. 새 일회용 월드에서만 사용하며 기존 보고서를 비우고 새 결과 파일·성공 표식·실패 표식 부재·프로세스 종료를 함께 검사한다. [후속 재생성 검증](../evidence/diagnostic-probe-recipes.json).
