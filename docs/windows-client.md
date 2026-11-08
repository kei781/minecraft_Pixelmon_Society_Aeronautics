# Windows 플레이어 설치

현재 생성 가능한 파일 `PSA-DIAGNOSTIC-NO-SOCIETY-bundled.mrpack`은 **Pixelmon + Create Aeronautics의 진단용**입니다. Society가 들어 있지 않습니다. 전체 세 프로젝트를 플레이하는 최종 패키지는 아직 제공하지 않습니다. 서버와 클라이언트의 버전·설정이 맞아야 하므로 이 파일을 Society 서버 접속용으로 사용하지 마세요.

## 플레이어가 한 번 준비할 것

1. [공식 Prism Launcher Windows 다운로드](https://prismlauncher.org/download/windows/)에서 설치판 또는 휴대용 ZIP을 받습니다. 검증에 사용한 버전은 [11.1.1](https://github.com/PrismLauncher/PrismLauncher/releases/tag/11.1.1)입니다. 휴대용 ZIP은 폴더 전체를 압축 해제하고 `prismlauncher.exe`를 실행합니다.
2. Prism의 계정 메뉴에서 본인의 Microsoft 계정을 추가합니다. Minecraft Java Edition 이용 권한이 필요합니다. 비밀번호나 계정 파일을 다른 플레이어에게 공유하지 않습니다.
3. 설정의 Java 항목에서 **Autodetect Java version**과 **Auto-download Mojang Java**를 켭니다. Minecraft 1.21.1에는 Java 21이 필요합니다. Java 자동 다운로드를 사용할 수 없는 환경은 [Prism 공식 Java 안내](https://prismlauncher.org/wiki/getting-started/installing-java/)에 따라 Java 21을 설치합니다.

## 패키지 하나 가져오기

1. 전달받은 `.mrpack`을 저장합니다. 현재 파일 포함형 시험 파일명은 `PSA-DIAGNOSTIC-NO-SOCIETY-bundled.mrpack`입니다.
2. Prism에서 **Add Instance → Import**를 누르고 해당 파일을 선택한 뒤 **OK**를 누릅니다. [공식 가져오기 안내](https://prismlauncher.org/wiki/getting-started/download-modpacks/)와 같은 방식입니다.
3. 파일 포함형은 여섯 모드가 이미 들어 있습니다. Prism이 로컬 모드에 대한 신뢰 확인창을 띄우면, 파일을 이 프로젝트의 관리자로부터 받았는지 확인하고 진행합니다. 이 패키지는 공개 원본을 해시 검증한 뒤 포함합니다. 일반 다운로드형 `.mrpack`도 지원하지만 이번 시험에서는 Pixelmon 대용량 다운로드가 HTTP/2 오류로 실패했습니다.
4. 런처가 정해진 Minecraft·NeoForge·리소스를 추가로 내려받습니다. Java 추가 다운로드는 첫 실행 때 진행될 수도 있습니다. 따라서 파일 포함형도 처음에는 인터넷이 필요합니다. 현재 진단용 기본 파일명에는 **NO-SOCIETY**가 표시됩니다. 이름을 바꾸지 않고 가져온 인스턴스를 선택해 실행합니다. 최소/최대 메모리는 PC의 실제 RAM 여유를 확인해 설정합니다. 전체 Society 팩의 적정 클라이언트 메모리는 아직 검증하지 않았습니다.
5. 서버 관리자가 이 패키지와 맞는 서버를 열었을 때 멀티플레이에서 전달받은 주소를 입력합니다. 현재 진단 시험 서버는 검증 후 종료한 상태입니다. 저장소에는 개인 서버 주소를 넣지 않습니다.

모드를 개별 검색해 하나씩 설치할 필요는 없습니다. 진단 패키지는 Pixelmon, Create, Create Aeronautics, Sable, KubeJS, Rhino의 고정 버전 여섯 개와 일반 몹 공존 설정을 준비합니다. 계정·월드·셰이더·검사용 서버 모드는 포함하지 않습니다.

## 개발자가 패키지를 만드는 방법

검증된 다운로드 캐시와 Python 3.9+가 있는 개발 체크아웃에서:

```sh
python3 tools/export_client.py diagnostic --bundle-downloads
python3 tools/export_client.py diagnostic
python3 tools/export_client.py integration --output dist/PSA-integration.mrpack
```

`--bundle-downloads`는 이미 검증한 원본을 패키지 안에 넣어 Prism의 개별 모드 다운로드를 생략합니다. 원본 URL·SHA1·SHA512·크기는 `psa-client-profile.json`에 보존하며, 포함된 각 파일의 SHA256도 기록합니다. 큰 파일을 전달해야 하지만 플레이어의 모드 설치는 파일 한 번 가져오기로 끝납니다. 이 파일은 로컬/개인 배포용으로 생성하며 저장소나 릴리스에 자동 업로드하지 않습니다.

기존 출력 파일은 덮어쓰지 않습니다. 재실험은 `--output`으로 다른 출력 파일명을 사용하세요. Windows 플레이어에게 Python·Git·개발용 Java JDK 설치를 요구하지 않습니다.

전체 내보내기는 고정 upstream 체크아웃, CreativeCore 호환 빌드 및 네 필수 개발 파일의 해시 검증이 선행되어야 합니다. 현재 미확보인 `society-2.0-1.21.1.jar`, `sunrisegardening-1.0.jar` 때문에 두 번째 명령은 패키지를 만들지 않고 중단됩니다. 공개 원본은 다운로드 URL·SHA1·SHA512·크기를 인덱스에 기록합니다. 수정 CreativeCore와 필수 개발 파일은 로컬 통합 패키지의 overrides에 배치하며 원본 CreativeCore를 중복 설치하지 않습니다. 이 명령이 제3자 바이너리의 공개 재배포 허가를 부여하지는 않습니다.

전체 패키지는 고정 Society 소스의 설정·KubeJS와 압축이 풀린 `sunlit_overrides` 리소스를 포함하도록 구현했습니다. 이 리소스의 `pack_format: 43`도 원본 그대로 보존합니다. 원본이 설정한 `force_compatible`에 의존하는 부분과 실제 화면은 이후 전체 클라이언트 시험에서 확인해야 합니다. 원본에 없는 `configureddefaults`, `patchouli_books`나 이미 압축된 리소스 파일을 임의로 만들어 넣지 않습니다.

설정·KubeJS·리소스는 Git에 추적된 일반 파일만 복사하며 무시 파일을 제외하고 심볼릭 링크를 거부합니다. 고정 소스의 가장 긴 설정 경로는 108자입니다. 예시 기본 경로 `C:\Users\Player\AppData\Roaming\PrismLauncher\instances\PSA-integration\minecraft\`를 붙이면 190자로, 검사한 경로는 모두 260자 미만이었습니다. 실제 사용자명·설치 폴더·인스턴스 이름이 훨씬 길면 짧은 휴대용 설치 경로를 사용하세요. 이는 경로 길이 측정이며 Windows 실행 검증은 아닙니다.

자동 검사는 다음과 같습니다.

```sh
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

실제 가져오기 시험 환경은 macOS의 Prism 11.1.1입니다. 파일 포함형 가져오기가 완료됐으며, 설치된 모드 6개 전부의 크기·SHA512 및 메타데이터 외 overrides 79개 전부의 SHA256을 대조했습니다. Minecraft 1.21.1 / NeoForge 21.1.262 구성도 확인했습니다. [검증 기록](../evidence/client-import-verification.json)에 초기 다운로드 실패와 성공 경로를 함께 남겼습니다. Windows 실행, Microsoft 로그인, 서버 접속·게임 플레이 검증은 아직 완료하지 않았습니다.
