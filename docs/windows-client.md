# Windows 플레이어 설치

현재 시험 패키지는 **`PSA-Forge-Full-Experimental-v12.mrpack`**이다. 세 프로젝트, 모드 JAR 354개, 리소스팩·셰이더·Society 설정을 담은 약 1.14 GB 파일이다. 모드를 개별 설치할 필요는 없다. 개인용 산출물이며 GitHub 릴리스에 공개 업로드하지 않았다. v12 새 Windows 가져오기·실행 검증은 진행 중이다.

Minecraft 1.20.1 / Forge 47.4.20 / Society 정식 4.1.5A / Pixelmon 9.2.3 베타 / Aeronautics 1.3.0 비공식 Forge 포팅본을 사용한다. v12는 v9의 공통·메뉴 보정에 Jade 비행체 좌표 계산 보정을 추가한 후보다. 같은 공통 보정본의 서버를 사용한다. [구성과 검증 범위](forge-candidate.md).

## 한 번 준비하기

1. [공식 Prism Windows 다운로드](https://prismlauncher.org/download/windows/)에서 런처를 설치한다. 가져오기 검사에 사용한 버전은 [11.1.1](https://github.com/PrismLauncher/PrismLauncher/releases/tag/11.1.1)이다.
2. **Settings → Java**에서 **Autodetect Java version**, **Auto-download Mojang Java**를 켠다. 이 팩은 Java 17을 사용한다. 자동 관리가 안 되면 [공식 Java 안내](https://prismlauncher.org/wiki/getting-started/installing-java/)에 따라 Java 17을 설치하고 선택한다.
3. 본인 Microsoft 계정으로 로그인한다. Minecraft Java Edition 이용 권한이 필요하다. 계정 정보는 패키지에 포함하지 않는다.

## 파일 하나 가져오기

1. 전달받은 v12 파일을 저장한다. 이전 인스턴스는 보존하고 새 인스턴스로 가져온다.
2. **Add Instance → Import → 파일 선택 → OK**를 누른다. [공식 가져오기 안내](https://prismlauncher.org/wiki/getting-started/download-modpacks/).
3. 외부 모드 확인창이 나오면 파일을 관리자에게서 받았는지, 아래 SHA256과 일치하는지 확인한 뒤 신뢰 체크를 하고 진행한다.
4. Minecraft **1.20.1**, Forge **47.4.20**인지 확인한다. 첫 설치에는 Minecraft·로더·Java 다운로드용 인터넷이 필요하다.
5. **Edit → Settings → Java**에서 메모리를 정한다. 16 GB 이상 PC에서는 최대 8192 MB를 첫 시작값으로 사용할 수 있다. [메모리 설정 안내](https://prismlauncher.org/wiki/help-pages/java-settings/).
6. **Launch → Multiplayer → Add Server**에서 관리자가 별도로 전달한 서버 주소를 입력한다. 실제 사용자 서버 주소와 SSH 정보는 공개 저장소·패키지에 넣지 않았다.

현재 파일은 1,137,793,542바이트이며 SHA256은 다음과 같다.

```text
bd884f35b18d157e7bbed3f3e1961539f0ac1913e914e3721a5d50eef94090e5
```

```powershell
Get-FileHash ".\PSA-Forge-Full-Experimental-v12.mrpack" -Algorithm SHA256
```

설치 경로와 인스턴스 이름은 짧게 쓴다. 가장 긴 상대 경로는 108자다.

## 실제 확인한 범위

v12의 354개 운영 모드와 구성 파일을 확인했다. v9과 모든 payload 경로가 같고 공통 JAR·프로필 메타데이터 두 파일만 다르며 나머지 바이트는 같다. 진단 두 개는 포함하지 않는다. v12 자체의 새 Windows 가져오기는 아직 통과로 기록하지 않는다. [패키지 비교](../evidence/forge-client-v12-package.json).

v9 아카이브의 선언된 파일 7,925개 SHA256, 모드 354개, 구성 버전과 진단 코드 부재를 확인했다. 서버 공통 313개 파일은 N100 검증 후보와 일치한다. Windows Prism에서 사용자가 신뢰 확인을 직접 처리한 뒤 새 `PSA-v9-QA` 인스턴스 가져오기와 설치 파일7,925개 해시·354개 모드 일치를 확인했다. 원본354개를 그대로 두고 시험용 진단0.7 하나만 추가한 새 인스턴스를 Java17·8192MiB로 실행해 정품 접속·월드 입장, 기본 아이템16개 실제 렌더 반환·모델 조회를 확인했다. 진단은 전달용 팩에 포함하지 않는다. [패키지 검사](../evidence/forge-client-v9-package.json), [Windows 가져오기](../evidence/forge-client-v9-import-windows.json), [실제 새 실행](../evidence/forge-client-v9-launch-windows.json).

이전 v7는 macOS Prism의 실제 GUI 가져오기와 설치 파일 해시 대조를 통과했다. 앞선 Windows 메뉴 검사는 기존 인스턴스에 v9과 동일한 공통 수정본과 메뉴 보정을 적용해 진행했고, 현재 렌더 검사는 새 v9 인스턴스를 사용한다. [이전 가져오기 기록](../evidence/forge-client-import-v7.json).

Windows 인증 접속, 큰 번호의 탱크 수레 1000→2000→1000mB 표시와 메뉴 재열기를 확인했다. 배터리의 실시간 충방전·재열기, 깃발 색상 교체와 게시판 큰 카운터 갱신도 확인했다. 실제 모드의 로더·언로더로 이송했으며 직접 양동이 주입은 원래 지원하는 동작이 아니다. [메뉴 수정·검증 범위](menu-data-compatibility.md). Pixelmon 포획·전투, Society 농사·경제·진행, 조종 비행과 실제 6인 부하는 별도 검증 중이다.

할인 표시의 새 수정은 [별도 기록](bountiful-discount-display.md)에 있다. 기존 Windows 인증 인스턴스에서 평판 30·31·564·802의 할인 40.0%, 0 복구·재열기와 일시정지 메뉴를 확인했다. 최신 Claude Opus 5.5 독립 재리뷰도 통과했다. 이전 셰이더·모델·일시정지 메뉴 보정도 포함한다. [셰이더 패킷](pixelmon-shader-compatibility.md), [모델](forge-model-compatibility.md), [메뉴 배치](pause-menu-compatibility.md).

## 개발자 재생성

공식 입력과 검증한 캐시가 있을 때 새 서버 프로필을 준비한 다음 내보낸다. 포팅 JAR 고정 SHA256은 `31e38f3be687d1fa5f95570599abd3ee8e28e65506b2ac872fc3428ecd8426a5`이고, 클라이언트 전용 메뉴 보정은 `44cacaa5794d6ff581f8b8d4e877942187d28843c30d4d05395f91b6bbd1d9f9`다.

```bash
python3 tools/export_forge_client.py \
  --server /path/to/fresh-staged-forge-server \
  --extras /path/to/verified-client-only-cache \
  --society-client /path/to/Society-Sunlit-Valley-4.1.5A.zip \
  --menu-fix /path/to/PSA-Client-Menu-Compat-1.1.jar \
  --output /path/to/new-full-client.mrpack
```

공식 manifest의 모드 351개에 Pixelmon·포팅 JAR·메뉴 보정을 더해 354개다. 나머지 15개는 리소스팩, 1개는 셰이더다. 필수 파일·해시·경로·스크립트가 다르면 중단한다. 테스트용 JAR·임시 QA 스크립트·계정·세이브는 내보내지 않는다.
