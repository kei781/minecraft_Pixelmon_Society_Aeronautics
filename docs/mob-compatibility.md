# Pixelmon과 Society의 일반 몹 공존

현재 검증은 Pixelmon 9.4.1, KubeJS 2101.7.2-build.377, Rhino 2101.2.8-build.91, NeoForge 21.1.262, Java 21 조합의 격리된 서버 시험입니다. Society 전체 기능·Aeronautics 비행·Windows 접속·N100 부하는 이 시험에 포함하지 않습니다.

## 원인과 수정

Pixelmon의 `WorldLoaded.onWorldLoaded`는 `EntityConfig.isAllowVanillaMobs()`에 따라 월드의 `doMobSpawning` 규칙을 설정합니다. 하지만 `MobSpawnReplacement.onEntitySpawn`은 별도로 `EntityJoinLevelEvent`를 처리하며, 등록된 교체 데이터에 따라 소 같은 일반 엔티티를 포켓몬으로 바꿉니다. 해당 경로는 `allow-vanilla-mobs`를 검사하지 않습니다.

Society의 원래 InControl 설정은 지상/지하 적대 몹을 구분하고, 상점·퀘스트에는 가축과 관련 아이템이 있습니다. 일반 몹을 모두 포켓몬으로 교체하면 이 진행 방식과 맞지 않습니다.

준비 도구는 다음을 함께 적용합니다.

1. `config/pixelmon/entity.yml`에 `allow-vanilla-mobs: true`를 설정합니다. 나머지 엔티티 설정의 기본값은 실제 Pixelmon 로더에서 유지되는 것을 확인했습니다.
2. 검증한 Pixelmon JAR의 `data/pixelmon/pixelmon/spawn_replacement/`에서 71개 JSON 경로를 읽습니다.
3. 같은 경로에 대응하는 KubeJS 데이터를 생성합니다. 직접 작성한 빈 `types` 검출 목록으로 교체가 어떤 엔티티에도 적용되지 않게 합니다. 원본 JAR는 수정하지 않습니다.
4. `stage`는 서버·클라이언트 양쪽에 동일하게 생성하고 `.integration-staging.json`에 경로와 SHA256을 남깁니다. Society 원본 InControl 규칙은 유지합니다.

Pixelmon의 자체 스포너는 수정하지 않습니다. 검증에서는 실제 포켓몬 엔티티를 생성하고 월드에 추가하는 경로도 확인했습니다. 자연 포켓몬 스폰 빈도나 포획·전투가 검증됐다는 뜻은 아닙니다.

## 대조 실행 결과

| 관찰 | 설정만 변경 | 설정 + 교체 데이터 수정 |
| --- | --- | --- |
| `allow-vanilla-mobs`와 나머지 엔티티 기본값 | 통과 | 통과 |
| 월드 `doMobSpawning` | true | true |
| 소·닭·돼지·양·좀비 각각 `level.addFreshEntity` | 모두 false | 모두 true |
| Pikachu 엔티티 `level.addFreshEntity` | true | true |
| 서버 기동 `Done` 및 정상 자동 종료 | 통과 | 통과 |

이 검사는 월드 엔티티 추가 시 실제 Pixelmon 이벤트 핸들러가 실행되는지 확인합니다. 자연 스폰·번식·Society 상점 구매를 대신하는 검사는 아닙니다. 두 시험 모두 원본 Pixelmon의 `pixelmon:spawning/drowned` 바이옴 태그 참조 오류를 기록했으며, 이 오류는 이번 수정으로 해결하지 않았습니다. 두 프로필의 기동과 검사 완료를 막지는 않았습니다.

## 재현

고정 다운로드 캐시와 로컬 NeoForge 설치가 있는 개발 환경에서 실행합니다.

```sh
python3 tools/build_probe.py mobs-config-only --java-home /path/to/jdk-21
python3 tools/build_probe.py mobs-preserved --java-home /path/to/jdk-21
```

각 명령이 출력한 디렉터리에서 출력된 Java 명령을 실행합니다. 포트는 각각 127.0.0.1:25568 및 25569이고, 성공 시 `PSA_MOBS_PROBE PASS`가 출력된 후 서버가 자동 종료됩니다. 각 프로필의 `.probe-overrides.json`이 적용 파일을 기록합니다.

테스트 전용 `psa-mobs-probe.jar`는 운영 팩에 포함하지 않습니다. `tools/prepare.py stage`는 여전히 실제 Society 2.0·Sunrise Gardening 파일이 없으면 중단합니다.

## 전체 공개 모드 프로필의 추가 확인

기존 월드를 가져오지 않은 새 디렉터리에 공개 서버 파일 230개, 기존 CreativeCore 패치, 두 소스 후보, 이 수정안과 테스트 모드를 복사해 실행했습니다. 설정 검사와 KubeJS 서버 스크립트 44/44개 로딩은 통과했으나, Sunrise Gardening의 온실 블록 누락으로 월드 데이터 로딩이 실패했습니다. 이 시도에서 전체 몹 공존 검사나 전체 서버 기동이 통과했다고 주장하지 않습니다. 상세 결과는 `evidence/mob-compatibility-verification.json`에 있습니다.
