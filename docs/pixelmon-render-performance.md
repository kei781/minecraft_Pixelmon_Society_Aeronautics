# Pixelmon 렌더링 성능 후보

[이슈 #21](https://github.com/kei781/minecraft_Pixelmon_Society_Aeronautics/issues/21)의 첫 후보다. 시야·포켓몬 표시 거리·모델·애니메이션·셰이더 품질 설정을 낮추지 않는다. CPU를 더 많은 코어에 분배하거나 애니메이션을 GPU로 옮긴 구현은 아니다. 먼저 Pixelmon이 보내는 동일한 정점 데이터를 더 효율적으로 기록한다.

## 측정에서 확인한 범위

7800X3D / RTX 5080 / RAM 32 GB, Forge 1.20.1 47.4.20 / Pixelmon 9.2.3 / Oculus 1.8.0 / Embeddium 0.3.31의 실제 클라이언트를 조사했다. 실제 framebuffer는 2091×1352, 시야 24청크다. 최대 FPS 120·VSync가 켜져 있었다.

12초 측정에서 메인 렌더 스레드가 논리 코어 하나의 93.9%, GPU가 44~69%를 사용했다. VRAM은 약 7.5/16 GB였다. 35초 JFR 렌더 스레드 표본 2,042개 중 Pixelmon 82.71%, 포켓몬 엔티티 render 75.22%, SmdModel.buildVBO 62.68%가 관측됐다. leaf 표본은 DirectByteBuffer.putFloat 30.51%, Iris computeTangentSmooth 14.05%였다. 중첩 표본 비율이며 합산하지 않는다.

같은 위치·카메라·24청크의 화면에서는 셰이더 ON 55~61 FPS, OFF 108~111 FPS를 봤다. 복원 후 ON 71 FPS도 관측했다. 서버 시간과 엔티티가 변했고 통제된 평균 벤치마크가 아니다. 사용자 보고 약 30 FPS와 이동 시 저하는 이 관찰에서 직접 재현하지 못했다. 원시 JFR·로그·계정·서버 정보는 저장소에 싣지 않는다.

## 구현 경계

Oculus의 Pixelmon 호환 믹신은 DeformVertex.id2 읽기를 -1로 바꿔 Pixelmon의 고정 NEW_ENTITY stride 복사를 막는다. 셰이더 확장 정점에서는 필요한 보호이므로 이 패치는 이를 유지한다.

별도 클라이언트 모드의 PixelmonFaceMixin은 NormalizedFace.addFaceForRender의 완성 정점 호출 두 곳만 redirect한다. 기존 위치·애니메이션·UV·색·조명·법선 값을 그대로 받는다. 대상 BufferBuilder가 지원하는 경우에만 native stores로 기본 속성을 기록하고, 원래 nextElement 여섯 번과 endVertex를 호출한다. Oculus의 entity-ID, midpoint, tangent 및 polygon 처리와 버퍼 증설은 기존 코드가 수행한다. 다른 consumer·terrain/glyph 형식·고정 색·진행 중인 정점·지원하지 않는 버퍼에서는 원래 호출로 돌아간다.

빌드 입력은 고정 해시로 검사하고 실행 시 모드 버전 범위를 제한하는 실험 후보다. 실행 중인 JAR의 SHA-256을 재검사하는 구현은 아니며, 같은 버전 문자열로 수정된 바이너리는 검증 범위 밖이다. 기본 비활성이고 Mixin 플러그인이 클래스 변형 자체를 막는다. `-Dpsa.pixelmon.fastVertices=true`가 명시된 별도 QA 인스턴스에서 시험한다. 사용 중인 인스턴스나 배포 팩에 자동 설치하지 않는다. 해당 속성을 제거하고 다시 실행하면 두 대상 클래스 모두 이 후보의 변형을 받지 않는다. 아직 게임 FPS 향상이나 전체 팩의 시각적 동일성을 주장하지 않는다.

## 재현 가능한 빌드와 검사

원본 Pixelmon·Oculus·Embeddium은 고정 해시로 확인하며 산출물에 포함하지 않는다. 로컬 Prism의 libraries와 mods 경로 및 Java 17 JDK를 명시한다. 출력은 기존 파일이나 mods 폴더를 가리킬 수 없다.

컴파일과 Java 검사 실행은 모두 argfile을 사용한다. Minecraft 고정 client와 이 스택의 LWJGL 3.3.1·Mixin 0.8.5·Forge 47.4.20을 먼저 선택하고, 중복을 뺀 실제 classpath 전체의 상대 경로·SHA-256을 빌드 receipt에 기록한다. 나머지 공유 라이브러리 전체를 고정 버전으로 강제하는 구현은 아니므로 재현 시 receipt도 대조해야 한다.

JDK 17의 argfile은 시스템 인코딩으로 기록한다([Java 17 문서](https://docs.oracle.com/en/java/javase/17/docs/specs/man/java.html)). Windows에서는 Python UTF-8 모드와 무관하게 ACP를 따르는 `mbcs`를 사용하고, 표현할 수 없는 문자는 파일 기록 전에 명시적으로 거부한다. 한국어 Windows에서 한글·공백 경로의 실제 javac/java 실행과 Python UTF-8 모드 검사를 모두 통과했다. Java 소스 파일 자체의 인코딩은 기존대로 UTF-8이다.

POSIX에서는 Python 3.9에도 있는 `nl_langinfo(CODESET)`으로 인코딩을 구하며, 검사는 같은 helper를 사용한다. Java를 실제 실행하는 회귀 검사는 빌드 도구와 동일하게 JDK 17을 요구한다. CI는 저장소 최소 지원 Python 3.9와 Python 3.12에서 각각 전체 검사를 실행한다.

```text
python tools/build_pixelmon_render.py --libraries PATH/PrismLauncher/libraries --mods PATH/instance/minecraft/mods --java-home PATH/jdk17 --output PATH/qa/PSA-Pixelmon-Render-0.1.0.jar --test
python -m unittest discover -s tests -p test_pixelmon_render_build.py -v
python -m unittest discover -s tests -v
```

`--test`는 실제 고정 Minecraft의 BufferVertexConsumer 기본 구현을 독립 기준으로 사용한다. 10,016개 입력의 색·좌표·UV·overlay·light·법선 및 보호 바이트를 대조한다. 색·UV·법선의 NaN·무한대, 음수 0·법선 범위 초과도 포함한다. 비유한 좌표는 signaling NaN의 float→double→float 변환까지 보존하도록 원래 호출로 돌아간다. heap/read-only/big-endian/부족한 limit/음수·overflow offset은 native access 전에 거부한다. 이 검사는 base attribute 인코딩 검사이며 실제 Mixin 적용과 확장 셰이더 정점 출력은 별도 검사다.

별도 `tests/forge-pixelmon-render-probe`는 QA 전용 모드다. 로컬 Forge 빌드 classpath와 후보 JAR로 이 소스만 컴파일하고, resources와 함께 `dev/psa/pixelmonrenderprobe/` prefix·MixinConfigs 없이 `package_jar`로 별도 포장한다. 최소 Pixelmon/Oculus/Embeddium + 후보 + 진단 모드로 실행하고 `-Dpsa.render.probe.output=ABSOLUTE_JSON_PATH`를 준다. 진단은 월드를 만들거나 접속하지 않고 TRIANGLES 300개·QUADS 400개 정점의 원본/후보 확장 속성을 비교한 뒤 자기 QA 클라이언트만 종료한다. 패딩은 의미 있는 셰이더 속성이 아니므로 비교에서 제외한다. 이 역시 실제 월드·포켓몬 모델·셰이더 화면·FPS 대조를 대신하지 않는다.

Windows의 전체 기존 Python 테스트는 변경 전 LF 복제본에서도 169개 중 symlink 권한 관련 오류 17개·제외 15개가 있었다. 원본 파일을 바꾸거나 실패를 숨기지 않으며 Linux CI에서도 전체 검사를 실행한다.

2026-11-16 리뷰 수정 후보 대조에서는 비유한 좌표 fallback을 포함해 확장 속성 37,100바이트가 다시 일치했다. 실제 Forge 안의 CPU 정점 처리 microbenchmark는 표본당 460,800개 정점, 워밍업 후 순서를 번갈아 7회 측정했다. 중앙값은 원본 39.1666 ms, 후보 33.0583 ms로 해당 구간 시간이 15.60% 감소했다. GPU draw와 실제 포켓몬 월드 FPS를 측정한 수치가 아니다. OFF로 다시 실행했을 때는 BufferBuilder adapter와 NormalizedFace redirect가 모두 없는 것도 확인했다. [검증 요약](../evidence/pixelmon-render-candidate.json).

코드 커밋 `096bbb8737c89439a515bd3468cd16dc28eeae65`의 [Linux CI 실행](https://github.com/kei781/minecraft_Pixelmon_Society_Aeronautics/actions/runs/43731428037)에서 Python 3.9와 3.12 각각 177개 실행·제외 5개·실패/오류 0개를 확인했다. 이 실행은 명시한 코드 커밋의 검증 기록이며, 그 뒤 증거 문서만 갱신한 커밋 자체를 검사했다는 뜻은 아니다.

같은 후보 JAR를 별도 QA의 실제 모드 355개 조합에도 추가해 ON/OFF를 재검사했다. 기본 설정·월드 미접속 상태에서 ON의 정점/확장 속성 대조와 OFF의 클래스 변형 부재가 모두 통과했다. 종료 시 Pixelmon Discord SDK의 `TRANSACTION_ABORTED`가 ON/OFF 양쪽에서 관측됐다. 원래 플레이 설정·월드를 복제하지 않은 로더/버퍼 대조이므로 전체 팩의 화면·FPS 승격 조건은 그대로 남는다.

## 승격 조건

1. 실제 Forge에서 믹신 적용과 확장 정점 대조 통과.
2. 전체 모드팩에서 일반·그림자·발광·반투명·윤곽선·HUD/도감 모델 경로의 원본/후보 대조.
3. 같은 장소·해상도·시야·셰이더에서 충분히 워밍업한 반복 A/B 기록. 프레임 시간 중앙값·상위 지연과 메인 스레드·GPU 수치를 함께 비교.
4. 의미 있는 성능 개선과 시각적 회귀 부재가 확인된 뒤에만 기본 활성화 또는 배포 후보 반영.

CPU 애니메이션의 병렬화·GPU skinning은 별도 설계가 필요하다. 이 후보의 검증을 그 작업의 완료로 해석하지 않는다.

## 기본 속성 커서 이동을 합치는 다음 후보

첫 후보 이후 실제 월드의 렌더 스레드 leaf 표본에서 `nextElement`가 26.03%였다. 다음 후보는 기본 속성의 여섯 단계 이동을 동일한 최종 커서 상태로 합친다. 원래 `endVertex`와 Iris의 entity-ID·midpoint·tangent, 다른 모드의 emission·batching 처리는 그대로 호출한다. 새로운 작업 스레드나 GPU skinning을 추가하지 않는다.

기존 `-Dpsa.pixelmon.fastVertices=true`와 별도로 `-Dpsa.pixelmon.fastAdvance=true`가 필요하며 재시작 후 적용된다. 두 번째 옵션이 없으면 추가 mixin과 interface가 없고 기존 정점 함수의 명령도 그대로다. 실제 합성 클래스에서 기존 r4와 새 후보의 native-only 정점 함수는 디버그 메타데이터를 제외한 opcode/operand 해시 `6ccbaf73b93130f1ffdbd6a446878fec146e4c7100c982a80a263bc96d09beba`, 코드 크기 204바이트가 일치했다.

새 mixin은 현재 단계 이동 메서드가 고정 Embeddium 구현과 같은지 확인한다. 확인된 경우에만 authored 정점 함수의 정확한 6회 루프 앞에 세 명령을 넣어 새 이동에 성공하면 원래 `endVertex`로 간다. 다른 메서드 본문이나 예상하지 못한 authored 루프는 기존 호출을 유지하고 새 이동을 비활성화한다. 디버그 label·frame·행 번호는 해시에서 제외한다. Mixin 적용 이후의 다른 postApply 플러그인이나 임의의 bytecode agent까지 보호하는 보안 경계는 아니다.

실제 배열·형식·시작/도착 요소·패딩을 포함한 이동량·고정 색·진행 중인 정점·버퍼 범위를 검사한 뒤 네 커서 필드만 바꾼다. 검증한 여섯 요소와 도착 요소의 참조를 매번 확인하므로 배열의 요소가 교체되면 기존 경로로 돌아간다. Embeddium이 추가하는 필드는 Mixin 준비 단계의 shadow로 찾을 수 없어, MAIN 이후 INJECT 단계에서 생성되는 accessor로 연결한다.

실제 355개 원본 모드 + 후보/진단 모드의 별도 기본 설정 QA에서 다음을 확인했다. 월드를 만들거나 접속하지 않은 로더/버퍼 검사이며 실제 포켓몬 화면이나 GPU draw를 측정한 것은 아니다.

- 원본 여섯 단계와 합친 이동의 커서 상태, 정상 폴리곤을 완료한 뒤 재사용, 고정 색·부분 정점·잘못 종료된 버퍼 재사용·terrain/glyph·교체된 배열 요소의 거부 등 12개 상태 검사 통과.
- TRIANGLES/QUADS에서 원본/전체 후보/원본과 후보의 교차 제출을 비교해 정점 1,400개에 해당하는 의미 있는 확장 속성 74,200바이트 일치. 버퍼 증설과 비유한 좌표 fallback 통과.
- 최소 3초 동안 원본과 후보를 교대로 워밍업한 뒤, 측정 순서를 번갈아 7회 실행했다. 한 표본은 사전 계산한 속성의 정점 460,800개다.

| 실행 옵션 | 원본 중앙값 | 후보 중앙값 | 해당 구간 시간 감소 |
|---|---:|---:|---:|
| fastVertices + fastAdvance | 36.2516 ms | 26.3996 ms | 27.18% |
| fastVertices만 | 35.6276 ms | 29.3253 ms | 17.69% |

각 행은 별도 JVM에서 그 안의 원본과 후보를 짝지어 측정했다. 행 사이의 단순 차이나 이 비율을 전체 게임 FPS 개선율로 해석하지 않는다. 초기의 짧은 워밍업 기록에서는 측정 중 속도 변화가 관측돼 최종 표에는 충분히 워밍업한 기록만 사용했다. 실제 월드의 모든 consumer·모델·재질·그림자·HUD 및 반복 FPS A/B 승격 조건은 남는다. 기본 비활성과 draft를 유지한다.

완전 OFF의 실제 로더 실행에서는 BufferBuilder adapter·새 advance interface·NormalizedFace redirect가 모두 없다는 검사를 통과했다. 최종 소스 커밋·산출물 해시·원시 구간 표본은 [검증 요약](../evidence/pixelmon-vertex-advance.json)에 기록한다.
