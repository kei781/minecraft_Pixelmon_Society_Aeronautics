# 전체 데이터팩 갱신 복구

Task18은 전체 `/reload`가 SerializerDebug의 개인 전송 대상에 null을 넘겨 실패하던
문제를 고친다. Forge의 null 플레이어 이벤트는 전체 접속자 동기화다. 원본 최소
서버에서 실제 원본 Future의 NPE를 재현했고, 서버 전용 보정 추가 후 0인 갱신이
완료됐다. 전체 팩에서도 0인 1회와 실제 인증 접속자 1명이 있는 상태 3회를 확인했다.
[구분된 실행 증거](../evidence/datapack-reload-recovery.json).

원본 `serializer_debug-1.0.1.jar`와 공통 포팅 JAR은 그대로 둔다. 별도
`PSA-Datapack-Sync-Compat-0.1.jar`는 원래 전송 호출 한 곳만 바꾼다. 개인 이벤트는
기존 채널·대상·패킷을 사용하고, 전체 이벤트는 실제 수신자 각각에게 같은 원래
패킷을 전송한다. 직렬화 목록·패킷 형식·진단은 유지한다. 수신자가 0명이면 전송을
하지 않으며, 예외를 삼켜 성공으로 바꾸지 않는다. 필수 원본 해시와 정확한 주입
메타데이터·생성자 적용 검사를 통과하지 못하면 로딩을 거부한다.

## 같은 유형 조사와 리소스 수정

고정 서버 JAR 313개와 중첩 JAR 150개에서 이벤트를 직접 참조하는 후보 클래스
26개를 조사했다. `getPlayer`와 `PacketDistributor`를 함께 쓰는 세 후보 중
SerializerDebug의 잘못된 경로를 확인했다. Placebo는 null일 때 전체 대상,
Curios는 실제 플레이어 목록을 사용한다. Species의 두 관리자, Exposure와 Sawmill의
위임 전송 도우미도 null의 전체 전송 분기를 확인했다. 이는 고정 입력의 직접 참조와
해당 도우미 조사이며 반사 호출·모든 후속 콜백의 완전한 증명은 아니다.

별도로 원래 KubeJS의 Forge 전리품 수정 목록에는 필수 `replace`·`entries`가
없었다. Forge가 이 오류를 잡아 로그에 남기므로 전체 Future 실패의 원인과 구분한다.
정확한 원본 SHA256 `46c89c99…`와 조건 전용 구조에 한해 `replace=false`,
`entries=[]`를 추가한다. 원래 조건은 보존하며 다른 네이티브 목록 24개는 바꾸지
않는다. 서버 staging과 클라이언트 내보내기에 같은 바이트를 적용한다. 알 수 없는
KubeJS 차이의 기존 거부 정책도 유지한다.

## 실제 변경·복원 대조

검증 전용 데이터팩으로 `minecraft:chests/simple_dungeon`을 종이 37~41개가 나오는
표로 바꿨다. 실제 플레이어를 문맥으로 원래 게임의 loot 명령을 실행해 종이 40개를
확인했다. 원본 모드 자산이나 배포 팩에는 이 검사 데이터를 넣지 않았다.

| 실제 수신 세대 | 서버·클라이언트의 순서 포함 항목 수 | 내용·자식 ID 해시 |
| --- | ---: | --- |
| 0인 갱신 후 최초 입장 | 30,801 | 일치 |
| 접속 중 기존 데이터 갱신 | 30,801 | 일치 |
| 검사 전리품 적용 | 30,778 | 일치 |
| 검사 팩 해제·원본 복원 | 30,801 | 일치 |

네 번 모두 실제 SerializerDebug 패킷 처리를 확인했고 ALI 등록도 네 번 완료됐다.
기존 데이터도 갱신 시 항목 순서가 달라질 수 있으므로 과거 해시와 무조건 같다고
보지 않고, 각 서버 전송과 해당 클라이언트 수신을 대조했다. 변경 데이터 수신 뒤
원래 ALI 팩토리·빌더와 기존 ID 보존 검사도 통과했다. 원본 복원 뒤 추가 스냅샷과
팩토리 검사를 요청했을 때에는 이미 실제 월드가 없어 검사가 거부됐다. 이 두 결과를
통과로 세지 않으며, 먼저 기록된 복원 수신·등록 결과와 구분한다.

검증 서버는 운영 서버와 분리한 소유 표시·루프백·최대 1명·4GB 힙 구성이었다.
실제 인증·입장·퇴장 각 1회, 원본 Future 갱신 완료 4회, 대상 갱신 오류와 크래시
0개를 확인했다. 정상 저장·종료 후 검사 데이터팩을 월드 밖에 보존했다. Mac 게임도
종료 로그와 프로세스 부재를 확인했다. 운영 v17 서버는 계속 실행 중이며 바꾸지 않았다.

## 설치 후보와 재생성

플레이어 v19는 기존 v18의 모드 355개를 모두 유지하고, 위 전리품 JSON과 색인·프로필
정보만 바꾼다. 서버 전용 보정이나 진단은 클라이언트에 넣지 않는다.
`PSA-Forge-Full-Experimental-v19.mrpack`은 1,137,811,877바이트,
SHA256 `72f814d0acf7fa57928d011552114c1c2165e69704818d7afe82560a899abbf7`다.
새 접속용 서버 후보는 기존 313개 모드에 보정 1개를 더한 314개다. N100의 별도
준비 경로에도 전송해 모든 모드 해시와 독립 Java·라이브러리를 확인했다. 아직 정지
상태이며 실행 중인 운영 월드는 복사하지 않았다. 실제 운영 v17은 그대로다.

Java 17과 기존 ForgeGradle 프로젝트·검증한 오프라인 캐시를 사용한다. 원본 모드의
클래스를 복사하거나 빌드 결과에 넣지 않는다.

```bash
gradle --offline --no-daemon --max-workers=2 -p /path/to/forge-project \
  -I "$PWD/tools/forge-datapack-sync.gradle" \
  -PpsaDatapackSource="$PWD/compat/datapack-sync" \
  -PpsaSerializerDebugJar=/path/to/serializer_debug-1.0.1.jar \
  reobfPsaDatapackSyncJar
python3 tools/forge_resources.py canonical-jar \
  /path/to/forge-project/build/libs/PSA-Datapack-Sync-Compat-0.1.jar \
  /path/to/new/PSA-Datapack-Sync-Compat-0.1.jar
```

[빌드 잠금](../compat/datapack-sync-build.json)은 독립 두 빌드의 동일 바이트를 기록한다.
서버 보정 SHA256은 `02ef84d99f5cbd086624403160a6e0ba4cd2c87516874692f1e1cdcc4f5d948d`다.
staging에 `--datapack-fix`로 전달한다. 런처는 정확한 추가 파일·원본·선언을 검증한
경우에만 314개를 허용하고, 선언된 보정이 빠졌을 때 313개로 낮춰 시작하지 않는다.

컴파일 가드 14개와 파일·스키마·staging·클라이언트 내보내기 검사 33개를 통과했다.
R1 리뷰 뒤 새 `stage()` 성공 경로 313/314와 전리품 누락/변경·보정 파일 변경의
출력 전 거부를 추가했다. 실제 생성된 리소스·프로필 선언·모드 해시 목록을 검사한다.
Linux 제어 검사 6개도 통과했다. 이는 별도 셸 프로세스 픽스처이며 실제 Minecraft 실행 결과와 구분한다.
진단 Future 관찰기는 `tests/forge-datapack-reload`와 별도 빌드 레시피로 재생성하며
명시적 플래그·소유 마커·정확한 루프백 포트 없이는 적용하지 않는다. 원본 Future를
바꾸지 않으며 관찰된 반환 후 시간은 전체 갱신 지연 시간이 아니다.

가드 14개는 저장소의 실행기로 다시 컴파일·실행할 수 있다. 아래 의존 JAR는 기존
로더/빌드의 로컬 파일을 사용한다. 실행기 자체는 다운로드하지 않으며 새 출력 폴더를
요구한다. 원본 클래스는 ASM 메타데이터로만 읽고 수정한 원본 클래스를 로딩하지 않는다.

```bash
python3 tools/run_datapack_sync_guards.py \
  --java-home /path/to/jdk17 \
  --module /path/to/PSA-Datapack-Sync-Compat-0.1.jar \
  --target /path/to/serializer_debug-1.0.1.jar \
  --dependency /path/to/asm-9.6.jar \
  --dependency /path/to/asm-tree-9.6.jar \
  --dependency /path/to/mixin-0.8.5.jar \
  --output /path/to/new-guard-results
```

소스·모듈·원본·의존성 해시와 각 결과는 `result.json`에 남긴다. 이 실행기로 현재
보정 JAR에 대해 14개를 다시 통과했다. 고정 Forge 47.4.20 원본 이벤트의
`getPlayers(): java.util.List`와 nullable `getPlayer()` 선언도 로컬 원본 API에서
확인했다. 게임 원문·바이너리는 공개 저장소나 외부 리뷰에 제공하지 않는다.

최신 안정 Claude Opus 5.5/high R1의 검사 보강 P3 한 건을 수정했고 R2는 소스
`2c26e01b762e6e8f110f8b9f6537d6d359a9ecfe`를 CLEAN으로 판정했다. 검증한 브리지
적용 뒤 실제 PR15 미해결 0건을 확인했다. CI 체크런·상태 컨텍스트는 없으며 CI 통과로
표현하지 않는다. [수락 기록](../evidence/task18-review-acceptance.json).
최신 Windows 신규 가져오기, 실제 6명·
장시간 부하, 모든 화면·아이템 사용과 운영 서버 교체는 이 결과의 완료 범위가 아니다.
