# Pixelmon + Society + Aeronautics

**현재 상태: 세 프로젝트 전체 실험 팩 생성 및 N100 전체 서버 기동·저장·재시작 확인. 실제 Windows 접속·게임 기능·6인 검증은 진행 중입니다.**

새로 찾은 **Society 정식 4.1.5A + Pixelmon 9.2.3 베타 + Aeronautics 비공식 Forge 포팅본**으로 전체 월드 기동에 성공했습니다. Minecraft 1.20.1 / Forge 47.4.20 / Java 17의 별도 실험 후보입니다. 아래 1.21.1 개발 조합의 누락 파일을 확보한 것은 아닙니다. [후보 구성·수정·검증 범위](docs/forge-candidate.md)를 참고하세요. N100에서도 전체 팩을 시작하고 시험 몹·물리 구조물의 저장/복구를 확인했습니다. Windows 접속·게임 기능·6인 검증은 남아 있습니다.

요청 구성은 Pixelmon + Society: Sunlit Valley + Create Aeronautics이며, 디지몬 데이터팩과 다른 대체 모드는 사용하지 않습니다. 서버 목표는 N100 / Ubuntu / RAM 16 GB / 동시 접속 최대 6명입니다.

Windows 설치는 런처·Java 같은 선행 프로그램을 안내에 따라 설치하고 준비된 모드팩을 가져오는 방식도 허용합니다. 모든 준비 과정을 자동화한 단일 실행 파일은 필수 조건이 아닙니다. 같은 구성의 클라이언트를 설치하고 실제 서버에 접속하는 것이 완료 조건입니다.

현재 전체 파일은 `PSA-Forge-Full-Experimental-v2.mrpack`(약 1.14 GB)입니다. [Windows 설치 안내](docs/windows-client.md)와 [N100 운영 안내](docs/n100-server.md)를 제공합니다. 실제 macOS Prism 가져오기와 설치 파일 7,921개 해시 대조를 통과했습니다. 원래 1.21.1 진단 팩과 별도 구성입니다. [실행 계획](docs/implementation-plan.md)과 [진행 상태](docs/progress.md)에서 두 목표를 따로 관리합니다.

## 보존한 최초 1.21.1 조사 기준

- Minecraft 1.21.1 / NeoForge 21.1.262 / Java 21
- Pixelmon 9.4.1 (사용자가 지정한 공식 사이트의 recommended 배포본)
- Create Aeronautics 1.3.2 / Sable 2.0.6 / Create 6.0.10
- Society 공식 저장소의 `project-honey` 개발 브랜치, 고정 커밋 `5e7c8fa9073a86f9ac74c7cbf087551e5872016c`

Society의 이 개발 브랜치는 정식 1.20.1 모드팩 4.1.5와 동일한 완성 배포본이 아닙니다.

## 실제로 수행한 검증

- 공식 다운로드 원본 277개 파일을 다운로드하고 upstream 해시 및 크기를 검증했습니다.
- 공식 클라이언트/서버 메타데이터에 따라 서버용 파일을 분리했습니다. 초기 서버 선택은 244개, 클라이언트 전용 분리 후 228개였습니다. 이후 아래 Plentiful Ponds 기동 시험에서 공통 라이브러리 두 개가 서버에도 필요함을 확인해 현재 서버 선택은 230개입니다. 클라이언트는 277개입니다. 파일 자체의 upstream 버전과 해시는 바꾸지 않았습니다. 다운로드 요약에는 사용한 lock의 SHA256을 기록합니다.
- 격리된 로컬 서버(127.0.0.1)에서 기동과 호환 패치 검증을 반복했습니다.
- Pixelmon의 `createCodec` 덮어쓰기와 CreativeCore의 mixin이 충돌하는 첫 번째 오류를 재현했습니다.
- CreativeCore의 수정 위치를 generic matcher 입력으로 옮기는 소스 포함 호환 패치를 작성했습니다. 실제 NeoForge에서 타입 배열 확장·중복 방지, CreativeCore 아이템 컴포넌트 저장/복원, Pixelmon 기본 및 명시적 타입 디코딩 검사가 통과했습니다. 전체 게임 플레이 호환성이 검증됐다는 뜻은 아닙니다.
- 서버와 클라이언트 준비 경로 모두 원본 CreativeCore 대신 해시를 확인한 패치본 하나만 배치합니다. 잘못된 패치 입력이 기존 정상 산출물을 손상시키지 않는 것도 확인했습니다.
- 이후 월드 생성은 `sunrisegardening:greenhouse_glass` 및 `greenhouse_glass_pane`이 없어서 중단됐습니다.
- 공개 소스에서 Orchard와 Plentiful Ponds를 직접 빌드했습니다. 고정 커밋의 원본 소스를 수정하지 않았으며, 별도 clean 재빌드도 동일한 SHA256을 생성했습니다. 개발자 설치 기록의 원본 바이너리와는 해시가 다른 후보 빌드입니다.
- 후보 두 개를 추가한 실제 로더 시험에서 오래된 내장 Fancy Tab Sections 충돌을 재현했습니다. 팩에 이미 고정된 Fancy Tab Sections 6.2.1과 LibTooltips 2.3.2를 서버에도 명시적으로 배치하자 모드 초기화와 KubeJS 서버 스크립트 44/44개 로딩을 통과했습니다. 월드 데이터는 여전히 Sunrise Gardening 블록 누락으로 중단됩니다. 이 부분 시험은 기존 로컬 개발 프로필에서 수행했으며 완성 설치기의 자동 검사로 주장하지 않습니다.
- Pixelmon의 일반 몹 교체도 코드와 실제 실행으로 확인했습니다. 설정만 바꾸면 소·닭·돼지·양·좀비의 월드 추가가 모두 거부됐고, 설정과 데이터 수정을 함께 적용하면 모두 유지됐습니다. 포켓몬 엔티티 추가는 양쪽에서 통과했습니다. `stage`는 고정 Pixelmon JAR의 교체 데이터 71개에 대응하는 KubeJS 수정 데이터와 설정을 생성하고, 생성 파일의 해시를 기록합니다. [범위와 재현 절차](docs/mob-compatibility.md)를 참고하세요. 전체 Society 게임플레이나 자연 스폰 빈도를 검증한 것은 아닙니다.
- 실제 N100의 새 임시 폴더에 휴대용 Java 21과 NeoForge를 설치하고 Pixelmon + Create + Aeronautics + Sable의 최소 조합을 실행했습니다. 서버 `Done`, 5개 차원의 Rapier 물리 엔진 초기화, 일반 몹 유지 및 포켓몬 엔티티 추가를 확인했습니다. 콘솔 `stop`으로 정상 종료하고 TCP·UDP 시험 포트가 닫힌 것을 확인했습니다. Society를 포함한 전체 팩, 비행·클라이언트 접속·6인 부하 시험은 아니며 서비스도 등록하지 않았습니다. 상세 범위는 `evidence/n100-minimal-smoke.json`에 있습니다.

## 1.21.1 개발 경로의 외부 의존성

Society 개발자의 설치 기록에는 아래 네 파일이 있지만 공개 다운로드 lock에는 없습니다. 인터넷에서 소스를 추가 조사해 두 개는 빌드했고, 두 개는 아직 확보하지 못했습니다.

이 설치 기록은 개발자 환경의 파일 이름·버전·해시 목록이며, 해당 JAR나 소스 파일 자체는 아닙니다. 실행에 맞는 JAR를 구하면 소스 없이도 설치할 수 있습니다. 공개 소스를 구하면 직접 빌드할 수도 있습니다. 개발자 문의는 배포 위치를 찾는 추가 경로이며 설치·개발 허락을 받기 위한 필수 절차가 아닙니다.

| 파일 | 현재 상태 | 확인한 출처 |
| --- | --- | --- |
| `society-2.0-1.21.1.jar` | 미확보 | 공개 Society Tweaks 배포 목록은 1.20.1뿐이며, 필요한 소스/바이너리를 찾지 못함 |
| `sunrisegardening-1.0.jar` | 미확보 | 공개 배포처와 해당 mod ID의 소스를 찾지 못함 |
| `orchard-1.21.1-1.0.0.jar` | 소스 후보 빌드 확보 | [Mnesikos/Orchard의 1.21.1 브랜치](https://github.com/Mnesikos/Orchard/tree/c04d3f242bd969a603d7a377948b1e42f6070cc3) |
| `plentifulponds-1.0.0-Beta.jar` | 소스 후보 빌드 확보 | [Chakyl/Plentiful-Ponds](https://github.com/Chakyl/Plentiful-Ponds/tree/76ffefef664599ef914594814cbc1170e9f368e2) |

검색 범위와 결과는 `evidence/artifact-research.json`, 빌드·부분 기동 결과는 `evidence/source-build-verification.json`에 있습니다. 공개 검색에서 찾지 못한 것을 비공개 또는 어디에도 없는 파일이라고 단정하지 않습니다. 이름이 비슷한 Sunrise Harvest는 다른 mod ID이므로 대체하지 않았습니다.

`external-artifacts.json`은 개발자 기록의 원본 SHA1을 보존하면서, 위 두 소스 후보의 별도 SHA256·커밋·라이선스 해시를 기록합니다. `python3 tools/build_external.py --java-home /path/to/jdk-21`을 실행하면 두 고정 소스를 내려받고 빌드하여, 확인한 크기와 SHA256이 맞을 때만 `inputs/`에 배치합니다. Git·Bash·Python 3.9+·Java 21 JDK가 있는 macOS/Linux 개발 환경용입니다. Gradle 의존성 다운로드에 네트워크가 필요합니다. 기존 소스가 수정됐거나 기존 입력 파일이 다르면 덮어쓰지 않고 중단합니다. 바이너리는 저장소에 재배포하지 않습니다.

`python3 tools/prepare.py preflight`는 현재 남은 두 파일만 누락으로 보고합니다. 필수 파일이 없는 상태에서 `stage`는 중단되며 파일을 조용히 생략하지 않습니다. 아직 확보하지 못한 파일의 다른 버전·해시를 임의로 허용하지 않습니다.

네 파일이 모두 검증되면 `preflight`는 각 파일을 `original` 또는 `source_candidate`로 구분해 실제 SHA256을 출력합니다. `stage`도 `.integration-staging.json`에 같은 분류·해시와 후보의 소스 커밋을 남깁니다. 이후의 기동 검증은 이 기록으로 사용한 바이너리를 구분할 수 있습니다.

## 남은 완료 조건

별도 Forge 후보의 실제 Windows 로그인/접속 → Pixelmon 포획/전투·Society 농사/경제/진행·Aeronautics 조종 비행 → N100 실제 6인 부하 검증. 1.21.1 경로의 누락 파일은 별도 보존하며 새 Forge 내보내기를 차단하지 않습니다.

현재의 `tools/prepare.py`는 개발용 다운로드/검증 도구입니다. 최종 Windows 원샷 설치기가 아닙니다.

개발용 도구는 `upstream/society`의 고정 커밋 체크아웃, 내려받은 원본 캐시 및 로컬 Java/NeoForge 컴파일 환경을 전제로 합니다. 패치 빌드는 `python3 tools/build_compat.py`, 원본 검증은 `python3 tools/prepare.py preflight`로 실행합니다. 패치 산출물과 upstream 바이너리는 Git에 포함하지 않습니다.

코덱 검사는 `python3 tools/build_probe.py baseline`과 `python3 tools/build_probe.py patched`로 각각 별도 테스트 프로필을 만듭니다. 각 명령이 출력한 Java 실행 명령을 해당 디렉터리에서 실행하고, 콘솔의 `PSA_PIXELMON_BASELINE` 또는 `PSA_CODEC_PROBE PASS`를 확인한 후 `stop`으로 종료합니다. 대조 프로필은 Pixelmon과 대조용 클래스 하나만, 패치 프로필은 Pixelmon·패치한 CreativeCore·검사용 클래스 하나만 포함합니다. 둘 다 127.0.0.1에 바인딩하며 실제 서버나 클라이언트 설치에 사용하지 않습니다.

이 개발 검사는 macOS/POSIX 환경용이며 Java 경로는 `--java-home /path/to/jdk-21`로 지정할 수 있습니다. 기본값은 `JAVA_HOME`, 없으면 이 작업에서 사용한 번들 JDK 경로입니다. 원시 게임 로그·역어셈블 덤프는 로컬에 보관하고, 검증 요약과 다운로드 실패 기록은 Git에 남깁니다.

`evidence/verification.txt`는 추적된 도구로 재현할 수 있는 검사와, 일회성 명령으로 실행한 수동 검사를 구분합니다. 수동 staging 픽스처와 일부 회귀 검사 실행기는 저장소에 포함하지 않았으며, 이를 자동 테스트로 주장하지 않습니다.

소스 후보 허용과 나머지 필수 파일 차단 회귀 검사는 `python3 -m unittest discover -s tests -p 'test_external_artifacts.py' -v`로 실행합니다.

몹 공존 검사는 `python3 tools/build_probe.py mobs-config-only` 및 `python3 tools/build_probe.py mobs-preserved`로 별도 로컬 프로필을 만듭니다. 각 명령이 출력한 실행 명령으로 시작하면 실제 엔티티 추가 결과를 검사한 뒤 자동 종료합니다. 검사 모드는 실제 서버나 클라이언트 배포에 포함하지 않습니다.

## 원본

- Pixelmon: https://reforged.gg/ko
- Society 소스: https://github.com/Chakyl/society-sunlit-valley/tree/5e7c8fa9073a86f9ac74c7cbf087551e5872016c
- Aeronautics: https://modrinth.com/mod/create-aeronautics
- CreativeCore 소스와 LGPL 라이선스: https://github.com/CreativeMD/CreativeCore

호환 패치의 수정 소스는 `compat/creativecore/ComponentSerializationMixin.java`에 있습니다. 이 저장소는 공식 프로젝트가 아니며, upstream에 PR이나 메시지를 게시하지 않았습니다.
