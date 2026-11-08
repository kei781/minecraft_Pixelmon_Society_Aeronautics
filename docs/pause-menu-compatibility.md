# 일시정지 메뉴 겹침 수정

사용자가 보낸 Windows 화면에서 Wiki 버튼의 글자가 겹쳤다. Society 4.1.5A의 FancyMenu 설정은 같은 줄에 자체 Wiki·Credits 버튼을 추가하고 기본 피드백·버그 신고 버튼을 숨긴다. Pixelmon 9.2.3은 그 위치에 피드백·버그 신고 버튼을 새로 추가한다. 전체 클라이언트의 실제 버튼 좌표를 측정해 배율 2·3·4에서 각각 겹침 2쌍을 재현했다.

`PSA-Client-Menu-Compat-1.0.jar`는 자체 작성한 클라이언트 전용 보정이다. 일시정지 화면이며 Society·FancyMenu가 로드됐고, FancyMenu의 실제 화면 사용자 지정 API가 활성 상태를 반환하며, 고정 Society 원본 메뉴 설정 SHA256도 맞을 때만 Pixelmon의 중복 링크 버튼을 숨기고 비활성화한다. API를 확인할 수 없으면 보정하지 않는다. Wiki·Credits와 Pixelmon·Discord 버튼을 유지한다. 메뉴 설정을 사용자가 바꾸거나 비활성화했으면 보정하지 않는다. 서버 모드·월드·인증·게임 콘텐츠는 바꾸지 않는다.

기존 v6 이용자는 Minecraft를 정상 종료하고 Prism에서 해당 인스턴스의 폴더를 연 뒤 `minecraft/mods`에 이 JAR 하나를 넣고 다시 실행하면 된다. 같은 파일을 두 번 넣지 않는다. 되돌릴 때는 게임 종료 후 이 JAR만 mods 밖으로 옮긴다. v5에는 서버 패킷 보정이 없으므로 새 v7 파일을 별도 인스턴스로 가져온다.

새 플레이어용 v7는 이 보정을 포함한 `.mrpack` 하나다. 모드 354개이며 N100 v6의 서버 공통 JAR 313개는 그대로다. 진단 모드는 포함하지 않는다. [Windows 설치 안내](windows-client.md).

## 빌드와 내보내기

기존 고정 Forge 빌드 환경과 Java17에서 실행한다.

```bash
gradle --offline -p /path/to/pinned-forge-build \
  -I "$PWD/tools/forge-client-menu.gradle" \
  -PpsaClientMenuSource="$PWD" reobfPsaMenuFixJar
```

기존 `tools/forge_resources.py`의 `canonical_jar`로 ZIP 메타데이터를 정규화한다. 두 빌드 트리의 모든 파일 바이트와 정규화 해시가 일치해야 한다. 원본 Pixelmon JAR는 수정하지 않는다.

```bash
python3 tools/export_forge_client.py \
  --server /path/to/staged-v6-server \
  --extras /path/to/verified-client-cache \
  --society-client /path/to/Society-Sunlit-Valley-4.1.5A.zip \
  --menu-fix /path/to/PSA-Client-Menu-Compat-1.0.jar \
  --output /path/to/new-v7.mrpack
```

`--menu-fix`가 없으면 기존 v6 내보내기 경로를 유지한다. 인수가 있으면 고정 해시가 맞는 파일만 클라이언트 mods와 payload 해시·프로필 기록에 추가한다. 서버 파일을 변경하지 않는다. 검사 모드는 별도 `reobfPsaMenuProbeJar`로 만들며 플레이어 패키지에는 넣지 않는다.

실제 전체 클라이언트가 TitleScreen에 도달한 뒤 같은 진단으로 일시정지 메뉴를 초기화하고 각 배율에서 100틱을 기다려 측정했다. 배율 2·3·4의 활성 버튼 겹침은 원본 각각 2쌍에서 보정 후 각각 0쌍이 됐다. Wiki·Credits·Pixelmon·Discord가 모두 표시·활성 상태로 보존됐고 작은 화면의 다른 기본 버튼도 겹치지 않았다. 이 문단은 R1 이전 helper `564a…`의 측정이다. [당시 좌표·로그 해시·재빌드 기록](../evidence/pause-menu-verification.json). 최종 helper `512ca9ea…`의 결과는 아래 재검사 기록을 사용한다.

첫 비공개 시험본은 모드 진입점과 Mixin 패키지가 같아 실제 게임 로딩에서 거부됐다. 패키지를 분리해 재빌드한 최종본으로 위 검사를 다시 통과했다. 첫 시험본은 Windows에 전송하지 않았다. 진단 모드는 초기 로딩 오류가 있으면 실패하도록 하며, 공식 데모로 UI만 검사한다.

이 UI 검사를 인증 접속이나 포획·농사·비행·6인 검증으로 간주하지 않는다. 독립 리뷰와 최종 파일 가져오기·Windows 재확인 상태는 후속 증거로 기록한다.

Claude R1의 P2는 화면별 사용자 지정 해제가 다른 파일에 저장되므로 레이아웃 해시만으로 활성 상태를 판단할 수 없음을 지적했다. P3는 명시적인 화면 종류 검사를 요청했다. 위 API 검사와 `PauseScreen` 검사를 추가했다. 같은 진단으로 기본·파일 1바이트 추가·레이아웃 비활성·화면 사용자 지정 해제의 4가지 상태와 3가지 배율을 원본/보정본에서 각각 실행했다. 기본 설정의 보이는 위젯 겹침은 2/2/2→0/0/0이며 네 버튼이 모두 보존됐다. 나머지 9개 대조 조건은 표시·활성·라벨·종류·좌표 등 모든 위젯 상태가 원본과 같았다. 실제로 화면 사용자 지정이 해제된 경우에는 원본 레이아웃 해시가 그대로인데도 API가 false를 반환하고 보정이 건너뛰어졌다. 시험 후 두 설정 파일이 원본과 같은 것도 확인했다. [재검사 기록](../evidence/pause-menu-review-controls.json). 실제 최신 안정 Claude Opus 5.5 R2는 `8b7c91d`를 CLEAN으로 판정했고 검증된 브리지가 두 지적을 해소했다. 실제 PR 미해결은 0건이며 CI 체크는 설정돼 있지 않다. 최신 v7의 GUI 가져오기 후 payload 7,925개·JAR 354개·최종 helper 해시·진단 모드 부재도 확인했다. [가져오기 기록](../evidence/forge-client-import-v7.json). Windows의 실제 수정 후 화면은 아직 재확인하지 않았다.
