# Pixelmon + Society + Aeronautics

**현재 상태: 통합 개발 중. 실행 가능한 완성 모드팩이나 Windows 설치기를 배포한 상태가 아닙니다.**

요청 구성은 Pixelmon + Society: Sunlit Valley + Create Aeronautics이며, 디지몬 데이터팩과 다른 대체 모드는 사용하지 않습니다. 서버 목표는 N100 / Ubuntu / RAM 16 GB / 동시 접속 최대 6명입니다.

## 확인한 공통 기반

- Minecraft 1.21.1 / NeoForge 21.1.262 / Java 21
- Pixelmon 9.4.1 (사용자가 지정한 공식 사이트의 recommended 배포본)
- Create Aeronautics 1.3.2 / Sable 2.0.6 / Create 6.0.10
- Society 공식 저장소의 `project-honey` 개발 브랜치, 고정 커밋 `5e7c8fa9073a86f9ac74c7cbf087551e5872016c`

Society의 이 개발 브랜치는 정식 1.20.1 모드팩 4.1.5와 동일한 완성 배포본이 아닙니다.

## 실제로 수행한 검증

- 공식 다운로드 원본 277개 파일을 다운로드하고 upstream 해시 및 크기를 검증했습니다.
- 공식 클라이언트/서버 메타데이터에 따라 서버용 파일을 분리했습니다. 초기에는 upstream pakku의 side 설정만 사용해 244개를 선택했고, 이후 공식 Modrinth의 `server_side=unsupported`를 반영해 16개를 클라이언트 전용으로 재분류했습니다. 현재 서버 선택은 228개, 클라이언트 선택은 여전히 277개입니다. 초기 실패 기록의 provenance 필드에 16개 목록과 근거 URL을 남겼으며, 이후 다운로드 요약에는 사용한 lock의 SHA256을 기록합니다.
- 격리된 로컬 서버(127.0.0.1)에서 기동과 호환 패치 검증을 반복했습니다.
- Pixelmon의 `createCodec` 덮어쓰기와 CreativeCore의 mixin이 충돌하는 첫 번째 오류를 재현했습니다.
- CreativeCore의 수정 위치를 generic matcher 입력으로 옮기는 소스 포함 호환 패치를 작성했습니다. 실제 NeoForge에서 타입 배열 확장·중복 방지, CreativeCore 아이템 컴포넌트 저장/복원, Pixelmon 기본 및 명시적 타입 디코딩 검사가 통과했습니다. 전체 게임 플레이 호환성이 검증됐다는 뜻은 아닙니다.
- 서버와 클라이언트 준비 경로 모두 원본 CreativeCore 대신 해시를 확인한 패치본 하나만 배치합니다. 잘못된 패치 입력이 기존 정상 산출물을 손상시키지 않는 것도 확인했습니다.
- 이후 월드 생성은 `sunrisegardening:greenhouse_glass` 및 `greenhouse_glass_pane`이 없어서 중단됐습니다.
- N100에는 읽기 전용 상태 점검만 수행했습니다. Minecraft 설치, 서비스 등록, 기존 데이터 변경은 하지 않았습니다.

## 현재 외부 의존성

Society 개발자의 실제 설치 기록에는 아래 네 파일이 있지만, 해당 개발 브랜치의 공개 다운로드 lock에는 없습니다. 기록된 SHA1로 조회한 공식 Modrinth API도 네 파일 모두 404를 반환했습니다. 이를 비공개 파일이라고 단정할 수는 없지만 현재 확인한 공개 경로에서는 다운로드하지 못했습니다.

- `society-2.0-1.21.1.jar`
- `sunrisegardening-1.0.jar`
- `orchard-1.21.1-1.0.0.jar`
- `plentifulponds-1.0.0-Beta.jar`

기록된 해시와 원본 위치는 `external-artifacts.json`, 조회 결과는 `evidence/missing-artifact-lookups.json`에 있습니다. 원본을 확보하면 `inputs/`에 두고 `python3 tools/prepare.py preflight`로 검증할 수 있습니다. 해시가 다른 새 개발본을 확보하면 해당 원본과 버전을 다시 감사해야 합니다. 필수 파일이 없는 상태에서 `stage`는 중단되며, 파일을 조용히 생략하지 않습니다.

## 남은 완료 조건

필수 개발 파일 확보 → 전체 서버 기동 → 농사/상점/퀘스트 및 Pixelmon 몹 교체 충돌 검증 → Windows 더블클릭 클라이언트 설치기 제작과 실제 접속 → Aeronautics 조립/비행 시험 → N100에서 6명 부하 검증.

현재의 `tools/prepare.py`는 개발용 다운로드/검증 도구입니다. 최종 Windows 원샷 설치기가 아닙니다.

개발용 도구는 `upstream/society`의 고정 커밋 체크아웃, 내려받은 원본 캐시 및 로컬 Java/NeoForge 컴파일 환경을 전제로 합니다. 패치 빌드는 `python3 tools/build_compat.py`, 원본 검증은 `python3 tools/prepare.py preflight`로 실행합니다. 패치 산출물과 upstream 바이너리는 Git에 포함하지 않습니다.

코덱 검사는 `python3 tools/build_probe.py baseline`과 `python3 tools/build_probe.py patched`로 각각 별도 테스트 프로필을 만듭니다. 각 명령이 출력한 Java 실행 명령을 해당 디렉터리에서 실행하고, 콘솔의 `PSA_PIXELMON_BASELINE` 또는 `PSA_CODEC_PROBE PASS`를 확인한 후 `stop`으로 종료합니다. 대조 프로필은 Pixelmon과 대조용 클래스 하나만, 패치 프로필은 Pixelmon·패치한 CreativeCore·검사용 클래스 하나만 포함합니다. 둘 다 127.0.0.1에 바인딩하며 실제 서버나 클라이언트 설치에 사용하지 않습니다.

이 개발 검사는 macOS/POSIX 환경용이며 Java 경로는 `--java-home /path/to/jdk-21`로 지정할 수 있습니다. 기본값은 `JAVA_HOME`, 없으면 이 작업에서 사용한 번들 JDK 경로입니다. 원시 게임 로그·역어셈블 덤프는 로컬에 보관하고, 검증 요약과 다운로드 실패 기록은 Git에 남깁니다.

`evidence/verification.txt`는 추적된 도구로 재현할 수 있는 검사와, 일회성 명령으로 실행한 수동 검사를 구분합니다. 수동 staging 픽스처와 일부 회귀 검사 실행기는 저장소에 포함하지 않았으며, 이를 자동 테스트로 주장하지 않습니다.

## 원본

- Pixelmon: https://reforged.gg/ko
- Society 소스: https://github.com/Chakyl/society-sunlit-valley/tree/5e7c8fa9073a86f9ac74c7cbf087551e5872016c
- Aeronautics: https://modrinth.com/mod/create-aeronautics
- CreativeCore 소스와 LGPL 라이선스: https://github.com/CreativeMD/CreativeCore

호환 패치의 수정 소스는 `compat/creativecore/ComponentSerializationMixin.java`에 있습니다. 이 저장소는 공식 프로젝트가 아니며, upstream에 PR이나 메시지를 게시하지 않았습니다.
