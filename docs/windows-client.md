# Windows 플레이어 설치

현재 시험 후보는 **`PSA-Forge-Full-Experimental-v21.mrpack`**이다. 세 프로젝트, 모드 JAR 355개, 리소스팩·셰이더·Society 설정을 담은 약 1.14 GB 파일이다. 모드를 개별 설치할 필요는 없다. 개인용 산출물이며 GitHub 릴리스에 공개 업로드하지 않았다. v21은 아직 누구도 가져오거나 실행해 보지 않았다.

Minecraft 1.20.1 / Forge 47.4.20 / Society 정식 4.1.5A / Pixelmon 9.2.3 베타 / Aeronautics 1.3.0 비공식 Forge 포팅본을 사용한다. [구성과 검증 범위](forge-candidate.md).

v21은 v20과 모드 354개가 바이트 단위로 같고 세 가지가 다르다. 공통 JAR에 [접속 뒤 PC를 다시 보내는 수정](pixelmon-pc-resync.md)이 들어갔고, 기차역에 연결된 우편함의 화물 복제를 막도록 [물리 조립에서 빼는 블록 목록](coexistence-audit.md#최종-리뷰-2026-11-14)이 서버와 같은 것으로 바뀌었고(싱글플레이 월드에 적용된다), 기본 키 파일에 [Pixelmon 키 여섯 줄](#기본-키-겹침)이 더해졌다. [v21 기록](../evidence/player-pack-v21-candidate.json).

v20은 v19와 같은 355개 모드 구성에서 공통 JAR을 [서버 중단 결함 두 건을 고친 것](coexistence-audit.md#포팅-jar-수정)으로 바꾸고, 싱글플레이용으로 서버와 같은 [공존 보정 파일](coexistence-audit.md)을 넣었다. **운영 서버는 2026-11-13부터 v20 프로필·314개 모드·새 월드다. v20과 v21의 공통 JAR 차이는 서버 쪽에서만 동작하는 클래스 하나와 그 믹신 설정뿐이고, 나머지 차이(물리 조립 제외 스크립트·기본 키 파일)는 접속과 무관해서 모드 ID·버전·레지스트리가 같다(v20 팩으로 새 공통 JAR의 운영 서버에 접속되는 것은 2026-11-14에 확인했다. v21 팩의 접속은 아직 해 보지 않았다). v19 이하의 팩은 공통 JAR이 달라 쓰지 않는다.** [반영 기록](../evidence/n100-v20-fresh-world-deployment.json).

## 한 번 준비하기

1. [공식 Prism Windows 다운로드](https://prismlauncher.org/download/windows/)에서 런처를 설치한다. 가져오기 검사에 사용한 버전은 [11.1.1](https://github.com/PrismLauncher/PrismLauncher/releases/tag/11.1.1)이다.
2. **Settings → Java**에서 **Autodetect Java version**, **Auto-download Mojang Java**를 켠다. 이 팩은 Java 17을 사용한다. 자동 관리가 안 되면 [공식 Java 안내](https://prismlauncher.org/wiki/getting-started/installing-java/)에 따라 Java 17을 설치하고 선택한다.
3. 본인 Microsoft 계정으로 로그인한다. Minecraft Java Edition 이용 권한이 필요하다. 계정 정보는 패키지에 포함하지 않는다.

## 파일 하나 가져오기

1. 전달받은 v21 파일을 저장한다. 이전 인스턴스는 보존하고 새 인스턴스로 가져온다.
2. **Add Instance → Import → 파일 선택 → OK**를 누른다. [공식 가져오기 안내](https://prismlauncher.org/wiki/getting-started/download-modpacks/).
3. 외부 모드 확인창이 나오면 파일을 관리자에게서 받았는지, 아래 SHA256과 일치하는지 확인한 뒤 신뢰 체크를 하고 진행한다.
4. Minecraft **1.20.1**, Forge **47.4.20**인지 확인한다. 첫 설치에는 Minecraft·로더·Java 다운로드용 인터넷이 필요하다.
5. **Edit → Settings → Java**에서 메모리를 정한다. 16 GB 이상 PC에서는 최대 8192 MB를 첫 시작값으로 사용할 수 있다. [메모리 설정 안내](https://prismlauncher.org/wiki/help-pages/java-settings/).
6. **Launch → Multiplayer → Add Server**에서 관리자가 별도로 전달한 서버 주소를 입력한다. 실제 사용자 서버 주소와 SSH 정보는 공개 저장소·패키지에 넣지 않았다.

현재 파일(v21)은 1,137,886,845바이트이며 SHA256은 다음과 같다.

```text
c1e2866a01f770a9972f1525c76bfd26e01976a089ef20a8cc93062683bdd98c
```

```powershell
Get-FileHash ".\PSA-Forge-Full-Experimental-v21.mrpack" -Algorithm SHA256
```

설치 경로와 인스턴스 이름은 짧게 쓴다. 가장 긴 상대 경로는 108자다.

## 실제 확인한 범위

v21은 내보내기 도구의 검사(선언 파일·해시·서버와 같은 보정 파일)를 통과했고, v20 팩과 항목별로 대조해 8,007개 항목 중 다섯 개(가져오기 색인, 프로필 정보, 공통 JAR, 기본 키 파일, 물리 조립 제외 스크립트)만 다름을 확인했다. 가져오기·실행·접속은 Windows와 Mac 어디에서도 하지 않았다. 기본 키의 확인 범위는 [아래](#기본-키-겹침)에 적었다.

이하는 이전 팩의 이력이다. v20(1,137,884,479바이트, SHA256 `80febd9a8c8cc1c60e48f44f08e029b117c7e2fa10e70daf5b761646de01502c`)은 내보내기 도구의 검사와 아카이브 안의 공통 JAR·보정 스크립트 해시만 확인했다. 2026-11-13 플레이어 3명이 v20 서버에 접속했다([기록](../evidence/n100-v20-player-checks.json)). v19 이하는 이전 공통 JAR(`351ecb09…`)을 쓴다.

v18은 원격 접속 후 ALI 툴팁 등록 오류를 고치는 클라이언트 전용 모드 하나를 더했고([ALI 수정](ali-client-tooltips.md), [스타터 오류 수정](pixelmon-starter-disconnect.md)), v19는 v18의 모드들을 유지하고 잘못된 전리품 목록 JSON만 보정했다([수정·변경/복원 검사](datapack-reload-recovery.md)). 당시 운영 서버는 v17·313개 모드였다.

v19는 v18과 같은 355개 모드와 진단 제외를 확인했다. JSON·색인·프로필 외 파일은
모두 같다. 같은 구성을 적용한 Mac QA의 실제 인증 입장과 서버 데이터 변경·복원
수신을 확인했다. 기존 인스턴스 갱신이며 새 Windows 가져오기 검증은 아니다.
[패키지·네이티브 실행 기록](../evidence/datapack-reload-recovery.json).

v18은 기존 v17에서 클라이언트 전용 ALI 보정 JAR 하나만 더했고, 기존 항목 7,931개는
같다. 진단은 포함하지 않는다. 실제 Mac QA 클라이언트의 배포 JAR 355개 해시 일치,
원격 접속 후 두 툴팁 경로와 데이터 등록 성공을 확인했다. 원래 Society가 숨기는 거래·낚시·
영웅 카테고리 설정은 보존한다. [구분된 원본·중간·최종 결과](../evidence/ali-client-tooltips.json).
이전 후보 둘은 로딩 메타데이터 누락과 남은 일반 빌더 오류로 거부했다. 새 Windows
가져오기·실제 거래 화면 육안 검수·6인 합격으로 확대하지 않는다.

v17의 354개 모드·7,932개 override와 진단 도구 부재를 확인했다. v16에서 공통
JAR·가져오기 색인·프로필만 달라졌고 나머지 7,930개 항목은 같다. Mac QA 클라이언트의
배포 모드 354개를 새 팩과 해시 대조했다. 서버 대조와 실제 로그인 결과는
[스타터 오류 기록](../evidence/pixelmon-starter-disconnect.json)을 따른다.
Windows는 꺼진 상태로 두었으므로 v17의 새 Windows 설치는 미검증이다.

v16의 354개 모드와 7,932개 override 파일을 검사했다. v15와 비교해 공통 호환 JAR·가져오기 색인·프로필 정보만 달라지고 나머지 파일은 같다. 진단 도구는 포함하지 않는다. N100의 전체 313개 모드 후보에서 같은 공통 JAR의 HP 대조 20개와 원본 누케닌 검사가 통과했다. 이는 v16의 Windows 새 가져오기·GUI·실제 6인 부하 확인을 뜻하지 않는다. [v16 패키지 기록](../evidence/player-pack-v16-candidate.json).

v12의 354개 운영 모드와 구성 파일을 확인했다. v9과 모든 payload 경로가 같고 공통 JAR·프로필 메타데이터 두 파일만 다르며 나머지 바이트는 같다. 진단 두 개는 포함하지 않는다. v12 자체의 새 Windows 가져오기는 아직 통과로 기록하지 않는다. [패키지 비교](../evidence/forge-client-v12-package.json).

v9 아카이브의 선언된 파일 7,925개 SHA256, 모드 354개, 구성 버전과 진단 코드 부재를 확인했다. 서버 공통 313개 파일은 N100 검증 후보와 일치한다. Windows Prism에서 사용자가 신뢰 확인을 직접 처리한 뒤 새 `PSA-v9-QA` 인스턴스 가져오기와 설치 파일7,925개 해시·354개 모드 일치를 확인했다. 원본354개를 그대로 두고 시험용 진단0.7 하나만 추가한 새 인스턴스를 Java17·8192MiB로 실행해 정품 접속·월드 입장, 기본 아이템16개 실제 렌더 반환·모델 조회를 확인했다. 진단은 전달용 팩에 포함하지 않는다. [패키지 검사](../evidence/forge-client-v9-package.json), [Windows 가져오기](../evidence/forge-client-v9-import-windows.json), [실제 새 실행](../evidence/forge-client-v9-launch-windows.json).

이전 v7는 macOS Prism의 실제 GUI 가져오기와 설치 파일 해시 대조를 통과했다. 앞선 Windows 메뉴 검사는 기존 인스턴스에 v9과 동일한 공통 수정본과 메뉴 보정을 적용해 진행했고, 현재 렌더 검사는 새 v9 인스턴스를 사용한다. [이전 가져오기 기록](../evidence/forge-client-import-v7.json).

Windows 인증 접속, 큰 번호의 탱크 수레 1000→2000→1000mB 표시와 메뉴 재열기를 확인했다. 배터리의 실시간 충방전·재열기, 깃발 색상 교체와 게시판 큰 카운터 갱신도 확인했다. 실제 모드의 로더·언로더로 이송했으며 직접 양동이 주입은 원래 지원하는 동작이 아니다. [메뉴 수정·검증 범위](menu-data-compatibility.md). Pixelmon 포획·전투, Society 농사·경제·진행, 조종 비행과 실제 6인 부하는 별도 검증 중이다.

할인 표시의 새 수정은 [별도 기록](bountiful-discount-display.md)에 있다. 기존 Windows 인증 인스턴스에서 평판 30·31·564·802의 할인 40.0%, 0 복구·재열기와 일시정지 메뉴를 확인했다. 최신 Claude Opus 5.5 독립 재리뷰도 통과했다. 이전 셰이더·모델·일시정지 메뉴 보정도 포함한다. [셰이더 패킷](pixelmon-shader-compatibility.md), [모델](forge-model-compatibility.md), [메뉴 배치](pause-menu-compatibility.md).

## 기본 키 겹침

Pixelmon은 기본 키를 코드에 정해 두고, Society의 기본 키 파일에는 Pixelmon 키가 없다. 그래서
v20까지는 화면이 닫힌 상태에서 아래 여섯 키를 누르면 Pixelmon 동작과 Society 쪽 모드 동작이 함께
실행됐다. v21은 기본 키 파일에 Pixelmon 키 여섯 줄을 더해 Pixelmon 쪽을 다른 키로 옮겼다.
Society 쪽 키는 바꾸지 않았다.

| Pixelmon 동작 | v20까지 | v21 | 같은 키에 있는 Society 쪽 동작 |
| --- | --- | --- | --- |
| 필드 기술 사용 | `G` | `;` | Curios 장신구 화면 |
| 필드 기술 고르기 | `B` | `'` | JourneyMap 웨이포인트 만들기, Sophisticated Backpacks 배낭 열기 |
| 포켓몬 오버레이 접기·펴기 | `O` | `0` | Oculus 셰이더 선택 화면. 어깨 시점에서는 좌우 전환도 |
| 퀘스트 일지 | `N` | `F6` | JourneyMap 웨이포인트 관리 |
| 퀘스트 표시 넘기기 | `M` | `F8` | FTB Chunks 지도(초반 퀘스트로 해금된 뒤). 자석을 갖고 있으면 자석 켜고 끄기 |
| 바라보는 블록의 위키 페이지 열기 | `K` | `Home` | Pufferfish Skills 스킬 화면 |

**새 키는 게임이 키 설정을 한 번도 저장하지 않은 인스턴스(새로 만든 인스턴스 포함)에만 적용된다. 서버에 접속해 본 인스턴스에는 적용되지 않는다.** 기본 키를 넣어 주는 Configured Defaults는 플레이어의
설정 파일에 없는 항목만 채운다. 게임이 키 설정을 한 번 저장한 인스턴스에는 Pixelmon 키가 이미 예전
값으로 적혀 있어서, 그 위에 v21 파일을 덮어써도 바뀌지 않는다. 그런 인스턴스는
**설정 → 조작 → 키 설정**의 `Pixelmon` 분류에서 직접 바꾼다.

아래 두 가지는 특정 상황에서만 겹치고 Pixelmon에서 가장 자주 쓰는 키라 그대로 두었다.

| 키 | Pixelmon 동작 | 함께 실행되는 동작 |
| --- | --- | --- |
| `↑` `↓` | 파티 포켓몬 선택 | 어깨 시점일 때 카메라 거리 |
| `R` | 포켓몬 꺼내기·넣기 | 공구 벨트를 차고 있을 때 벨트 메뉴 |

새 키 여섯 개 가운데 `;`, `'`, `F8`, `Home`에는 다른 기본 키가 없다. 나머지 둘은 다음과 같다.

- `F6`에는 Scholar의 책 가져오기 키가 코드에 기본값으로 정해져 있다. Scholar는 책 편집 화면 안에서만
  이 키를 읽고 Pixelmon 퀘스트 일지는 화면이 닫혀 있을 때만 열리므로, 한 번 눌러 둘이 함께 실행되지는
  않는다. 조작 화면에는 두 항목이 겹침으로 표시된다(코드로 판단했고 화면을 띄워 보지는 않았다).
- `0`에는 다른 기본 키가 없다. 다만 F3 프로파일러 차트를 켜 둔 동안, Supplementaries의 화살통류
  아이템을 사용하는 동안, Linked Typewriter를 조작하는 동안에는 그 기능도 `0`을 직접 읽는다.

확인한 방법은 다음과 같고, 게임을 실행해 눌러 보지는 않았다. [기록](../evidence/player-pack-v21-candidate.json).

- 팩의 모든 모드 JAR에서 키 등록을 찾아 새 키와 대조했다. 기본 키 파일에 없고 코드 기본값을 쓰는 키는
  40개(Pixelmon 19, 포팅본 3, Society 쪽 모드 17, 바닐라 공격 키 1)이며 모두 [표](../compat/client-keys/default-keys.json)에 있다.
- 팩 안의 Configured Defaults 병합 코드를 꺼내 실행했다. 새 인스턴스와 게임이 설정을 저장한 적 없는
  인스턴스에는 여섯 줄이 들어가고, 게임이 설정을 저장한 인스턴스는 바뀌지 않았다. 게임은 멀티플레이
  화면을 처음 열 때와 서버에 처음 접속할 때 설정을 저장하므로, 서버에 접속해 본 인스턴스는 뒤쪽이다.
- Forge가 이 줄을 모드 키 등록 뒤에 읽는 것, 여섯 키 이름이 실제 키 코드로 풀리는 것, Pixelmon의 여섯
  동작이 고정 키 코드 없이 키 설정을 따라가는 것을 바이트코드로 확인했다.

## 개발자 재생성

공식 입력과 검증한 캐시가 있을 때 새 서버 프로필을 준비한 다음 내보낸다. 현재 공통 JAR 고정 SHA256은 `d597065c5fef2abaec1bb01c616a5c5dc0787f672b5428693f23e696c37d23e4`이고(v20 팩은 `28e19585…`, v19까지의 팩은 `351ecb09…`이며 [포팅 결함 수정](coexistence-audit.md#포팅-jar-수정)이 없다), 클라이언트 전용 메뉴 보정은 `44cacaa5794d6ff581f8b8d4e877942187d28843c30d4d05395f91b6bbd1d9f9`다. 공통 JAR은 세 단계로 다시 만든다. [스타터 보정 JAR 재생성](pixelmon-starter-disconnect.md#재생성)으로 `351ecb09…`를 만들고, 그것을 입력으로 [포팅 수정 빌드·결합](coexistence-audit.md#포팅-jar-수정)을 수행해 `28e19585…`를 얻고, 다시 그것을 입력으로 [PC 다시 보내기 빌드·결합](pixelmon-pc-resync.md#빌드)을 수행해 `d597065c…`를 얻는다. 준비 도구는 앞 단계의 JAR만으로는 입력 해시 불일치로 거부한다.

```bash
python3 tools/export_forge_client.py \
  --server /path/to/fresh-staged-forge-server \
  --extras /path/to/verified-client-only-cache \
  --society-client /path/to/Society-Sunlit-Valley-4.1.5A.zip \
  --menu-fix /path/to/PSA-Client-Menu-Compat-1.1.jar \
  --ali-fix /path/to/PSA-ALI-Client-Compat-0.1.jar \
  --vanilla-data /path/to/libraries/net/minecraft/server/1.20.1-20230612.114412/server-1.20.1-20230612.114412-extra.jar \
  --output /path/to/new-full-client.mrpack
```

`--server`는 `--coexistence-fix`로 준비한 프로필이다. 그 프로필에는 다시 만든 전리품 표가 있어, 같은 표를 클라이언트용으로 재현하는 데 `--vanilla-data`(staging에 준 것과 같은 바닐라 데이터 JAR)가 필요하다.

기본 키 파일에 더하는 줄은 `compat/client-keys/default-keys.json`에 있다. 이 표는 Pixelmon JAR, 공통 JAR, `forge-client-lock.json`의 해시에 고정돼 있어서 모드 구성이 달라지면 내보내기가 멈춘다. 옮길 키에 표에 적지 않은 다른 기본 키가 있거나, 겹치던 Society 키가 그 자리에 없어도 멈춘다.

공식 manifest의 모드 351개에 Pixelmon·포팅 JAR·메뉴 보정·ALI 클라이언트 보정을 더해 355개다. 나머지 15개는 리소스팩, 1개는 셰이더다. 필수 파일·해시·경로·스크립트가 다르면 중단한다. 테스트용 JAR·임시 QA 스크립트·계정·세이브는 내보내지 않는다.
