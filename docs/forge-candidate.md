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
- 실제 조립에서 재현된 Leaves Be Gone 8.0.0의 `Random block ticks was null` 오류를 위해 [청크 생성자 호환 소스](../compat/forge-port/LeavesBeGoneChunkMixin.java)를 추가했다. 새 청크의 긴 생성자에서만 선택적 큐를 초기화한다. 기존 청크의 큐를 다시 설정하지 않는다. 실제 재검증 결과는 evidence에 기록한다.
- 포팅본의 `/sable` 루트 명령 권한 0을 2로 바꿨다. 일반 플레이어가 구조물 생성·삭제·물리 일시정지 명령을 쓸 수 없게 한다. 실제 명령 트리 검사는 `tests/forge-candidate-probe.js`를 격리 시험에만 추가해 수행한다.

`compat/forge-port/candidate-build.patch`는 위 고정 소스에 적용하는 빌드/메타데이터/명령 권한 변경이다. `@PSA_LOCAL_MAVEN@`은 개인 작업 폴더 Maven 경로 자리표시자다. 호환 Java 소스와 `psa-forge.mixins.json`은 별도로 복사해야 한다. 이 패치만으로 원본 아트나 생성 데이터를 얻는다고 주장하지 않는다. 현 단계는 직접 검증한 개발 절차이며 완성된 자동 소스 빌더는 아니다.

## 격리 서버 준비

해시를 고정한 세 입력이 로컬에 있을 때 다음 도구로 새로운 프로필을 준비한다. 입력 해시, 원본 311개 JAR, Pixelmon 교체 데이터 68개를 확인한다. 기존 경로를 덮어쓰지 않는다.

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
