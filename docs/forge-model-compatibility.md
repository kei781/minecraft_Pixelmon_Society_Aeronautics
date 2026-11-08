# Forge 모델 호환 수정

전체 클라이언트의 실제 로그에서 조종간과 바퀴 모델 17개가 `neoforge:obj` 로더를 찾지 못했다. 이 후보는 Forge 1.20.1을 사용한다. [Forge 공식 문서](https://docs.minecraftforge.net/en/1.20.x/rendering/modelloaders/)의 해당 로더 이름은 `forge:obj`다.

v5는 검증된 포팅 JAR에서 해당 JSON 17개만 읽어 최상위 `loader` 값을 바꾼 `PSA-Forge-Model-Compat.zip`을 만든다. 다른 필드와 원본 OBJ·MTL·텍스처는 보존하며 Java 클래스는 포함하지 않는다. 서버 공통 JAR와 실행 중인 N100 월드는 바꾸지 않는다. 패키지에 추가하는 리소스팩은 8,660바이트이며 SHA256은 `b948455e04afce7fb0d067486bfc67684a67868b5272c46c87708c958ff228c1`이다.

원본 Society의 기본 리소스팩 선택을 유지하면서 Configured Defaults와 Resource Pack Overrides 설정에 호환 팩을 추가한다. 새 인스턴스의 첫 실행에서 자동 선택되며 required로 지정된다. [Resource Pack Overrides 1.20.1 설정 문서](https://github.com/Fuzss/resource-pack-overrides/tree/1.20.1). 플레이어는 별도로 활성화할 필요가 없다. 개인 산출물에만 생성하고 원본 모델 파일을 Git에 올리지 않는다.

## 실제 실행 비교

실제 macOS Prism 11.1.1 GUI에서 가져온 v4와 v5의 별도 복사본을 공식 데모로 실행했다. 게임 모드 353개에 자체 진단 모드 하나만 추가했고, 두 실행 모두 같은 17개 모델을 Forge 모델 등록·베이킹 이벤트에서 검사했다. 진단 모드는 플레이어 파일이나 N100에 넣지 않았다.

| 검사 | v4 대조군 | v5 수정본 |
| --- | --- | --- |
| 모델의 실제 활성 로더 | 17개 모두 `neoforge:obj` | 17개 모두 `forge:obj` |
| 로더·기하 데이터 조건 통과 | 0/17 | 17/17 |
| 모델별 생성 면 수 | 누락 모델 래퍼의 큐브 6면 | 46~300면 |
| 호환 팩 실제 선택 | false | true |

ModernFix는 누락 모델을 래핑하므로 missing-model 객체와 직접 비교하는 검사만으로는 판별할 수 없다. 로더와 면 생성도 함께 검사했다. 조종간의 item/wheel은 각각 236면/230면이었다. 이는 실제 모델 리소스 생성 검사이며 화면의 모양·텍스처·조종·셰이더 렌더링을 눈으로 확인한 결과는 아니다. 다른 모드의 경고와 리소스 오류도 남아 있으므로 전체 로그가 오류 없다고 주장하지 않는다. [17개별 결과·로그 해시](../evidence/forge-model-bake-verification.json).

v5의 실제 가져오기 후 payload 7,924개 SHA256과 JAR 353개 및 필수 선택 설정을 확인했다. 자동 검사 47개는 Ubuntu에서 모두 통과했고 macOS에서는 44개 통과·Linux 전용 3개 제외였다. [가져오기 검사](../evidence/forge-client-import-v5.json), [컨트롤러 검사](../evidence/phase4-model-controller-tests.json).

## 진단 재현

`tools/export_forge_client.py`가 고정 입력의 JAR 해시·모델 개수·OBJ 경로를 검증한 뒤 호환 팩과 파일별 변환 해시를 생성한다. 입력 해시나 대상 개수가 다르면 중단한다. 기존 출력과 기본 선택을 손상시키지 않는 회귀 검사도 포함한다.

진단 모드를 다시 빌드하려면 [포팅 빌드](forge-candidate.md)에 사용한 ForgeGradle 작업 트리와 Java 17이 필요하다. 다음 명령의 출력은 개발 검사에만 쓴다.

```bash
gradle -p /path/to/pinned-forge-build \
  -I "$PWD/tools/forge-model-probe.gradle" \
  -PpsaModelProbeSource="$PWD/tests/forge-model-probe" \
  reobfPsaModelProbeJar
```

생성된 `build/libs/psa-model-probe-1.0.jar`를 새 검사 인스턴스의 mods에만 넣고 실행한다. 로그의 `PSA_MODEL_PROBE SUMMARY`와 17개별 행을 확인한다. 이 과정은 인증이나 데모 제한을 변경하지 않는다. 최종 Windows 로그인/접속, 포획·전투, Society 진행, 조종 비행과 실제 6인 부하는 여전히 남은 완료 조건이다.
