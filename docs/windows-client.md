# Windows 플레이어 설치

현재 시험 파일은 **`PSA-Forge-Full-Experimental-v2.mrpack`**이다. 세 프로젝트, 모드 JAR 353개, 리소스팩·셰이더·Society 설정을 포함한 약 1.14 GB 파일이다. 모드를 개별 설치할 필요는 없다. 개인용 산출물이며 GitHub 릴리스에 공개 업로드하지 않았다.

구성은 Minecraft 1.20.1 / Forge 47.4.20 / Society 정식 4.1.5A / Pixelmon 9.2.3 베타 / Aeronautics 1.3.0 비공식 Forge 포팅본이다. 현재 공식 1.21.1 배포본과 구분한다. [구성과 검증 범위](forge-candidate.md).

## 한 번 준비하기

1. [공식 Prism Windows 다운로드](https://prismlauncher.org/download/windows/)에서 설치한다. 가져오기 검사 버전은 [11.1.1](https://github.com/PrismLauncher/PrismLauncher/releases/tag/11.1.1)이다.
2. **Settings → Java**에서 **Autodetect Java version**, **Auto-download Mojang Java**를 켠다. 이 팩은 Java 17을 사용한다. 자동 관리가 안 되면 [공식 Java 안내](https://prismlauncher.org/wiki/getting-started/installing-java/) 또는 [Corretto 17 Windows x64 MSI](https://corretto.aws/downloads/latest/amazon-corretto-17-x64-windows-jdk.msi)로 Java 17을 설치하고 Auto-Detect에서 선택한다.
3. 본인 Microsoft 계정으로 로그인한다. Minecraft Java Edition 이용 권한이 필요하다. 계정 정보는 모드팩에 들어 있지 않다.

## 파일 하나 가져오기

1. 전달받은 위 v2 파일을 저장한다. 예전 `NO-SOCIETY` 진단 파일과 v1 시험 파일은 이 서버에 사용하지 않는다.
2. **Add Instance → Import → 파일 선택 → OK**를 누른다. [공식 가져오기 안내](https://prismlauncher.org/wiki/getting-started/download-modpacks/).
3. 외부 모드 확인창이 나오면 이 프로젝트가 구성한 파일인지 아래 SHA256으로 확인한 뒤 신뢰 체크를 하고 진행한다.
4. 새 인스턴스가 Minecraft **1.20.1**, Forge **47.4.20**인지 확인한다. 첫 설치에는 Minecraft·로더·Java 다운로드용 인터넷이 필요하다.
5. **Edit → Settings → Java**에서 메모리를 PC 여유에 맞춘다. 16 GB 이상 PC의 첫 검사에는 최대 8192 MB를 시작값으로 쓸 수 있다. Windows 실행으로 튜닝한 결과는 아니다. [메모리 설정](https://prismlauncher.org/wiki/help-pages/java-settings/).
6. **Launch** 후 멀티플레이에서 별도로 전달받은 서버 주소를 입력한다. 실제 주소와 SSH 정보는 공개 저장소·패키지에 넣지 않았다.

현재 파일 SHA256:

```text
59d8a8348e7724685293921fcf3c49bd51ecce6df1d344233e5b371787ab0897
```

Windows PowerShell 확인 명령:

```powershell
Get-FileHash ".\PSA-Forge-Full-Experimental-v2.mrpack" -Algorithm SHA256
```

설치 경로와 인스턴스 이름은 짧게 쓴다. 가장 긴 상대 경로는 108자다. 다른 버전 모드를 추가하거나 원본 Society 팩 위에 수동으로 겹쳐 넣지 말고 새 인스턴스로 가져온다.

## 실제 확인한 범위

macOS Prism 11.1.1의 실제 GUI 가져오기를 통과했다. 설치 파일 7,921개의 SHA256, JAR 353개, Minecraft/Forge 버전과 리소스·셰이더 위치를 확인했다. v1의 ZIP 오분류를 수정했고 v2의 mods 폴더에는 ZIP이 없다. [검증 기록](../evidence/forge-client-import-verification.json).

Windows 게임 실행·인증 접속·포획/전투·농사/경제·조종 비행·6인 부하는 아직 검증하지 않았다. 가져오기 성공을 플레이 완료로 표현하지 않는다. [이전 1.21.1 진단 절차](windows-client-1.21-diagnostic.md)는 별도로 보존한다.

## 개발자 재생성

검증한 CF 클라이언트 ZIP, 서버 공통 파일과 클라이언트 전용 캐시가 있을 때:

```bash
python3 tools/export_forge_client.py \
  --server /path/to/fresh-staged-forge-server \
  --extras /path/to/verified-client-only-cache \
  --society-client /path/to/Society-Sunlit-Valley-4.1.5A.zip \
  --output /path/to/new-full-client.mrpack
```

`forge-client-lock.json`은 공식 CF manifest 367개 항목을 고정한다. JAR 351개에 Pixelmon·포팅 JAR를 더해 353개다. 나머지 15개는 리소스팩, 1개는 셰이더다. 공개 CF SHA1·크기로 원본을 확인했고 SHA512는 확인한 바이트에서 계산했다. 공통 모드 311개와 원본 KubeJS 5,290개는 서버와 일치한다. 필수 파일·해시·경로·스크립트가 다르면 중단한다. 계정 파일은 복사하지 않으며 기존 출력도 덮어쓰지 않는다.
