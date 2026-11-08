# REA 실제 실행 결과

요청한 REA를 메타데이터 조회에 그치지 않고 설치·실행했다. 고정 버전은 npm `rea-agents@6.8.0`이며, 작업 폴더의 휴대용 Node 22.23.4로 실행했다. 기존 시스템 Node와 에이전트 전역 설정은 바꾸지 않았다.

`setup --dry-run --client codex`는 Codex MCP 등록과 REA 스킬 설치 계획을 반환했다. 실제 분석은 CLI를 직접 호출하면 되므로 적용한 설정 변경은 0개다. 분석 엔진을 새로 설치하거나 다른 계정·서비스에 파일을 보내지 않았다.

실행 대상은 공식 공개 Society 1.22 JAR다. 이는 Minecraft 1.20.1 Forge용 파일이며, 누락된 Society 2.0 1.21.1 파일과 다르다.

| 명령 | 실제 결과 |
| --- | --- |
| `rea inspect-artifact cache/research/society-1.22.jar --format json` | 종료 0. ZIP 리소스 그래프 분석, 노드 1,694개. Java 동작을 복원한 결과는 아니다. |
| `rea analyze cache/research/society-1.22.jar --format json` | 종료 1. `capability_unavailable`, `unsupported_provider`, `target_unsupported`. 자동 선택의 native 엔진들은 이 archive 입력을 지원하지 않으며 현재 설치 환경에도 설정돼 있지 않다. |

이 결과는 실행한 명령·버전·환경의 범위다. REA의 모든 공급자나 미래 버전이 Java를 분석할 수 없다는 일반적인 결론으로 확대하지 않는다. 현재 확보한 Java JAR은 이미 검증한 CFR·JDK javap으로 클래스·mixin을 분석할 수 있다. REA 설치 자체가 Society/Sunrise의 없는 입력 파일을 만들어 주지는 않았다.

`evidence/rea-assessment.json`에 실행 명령, 원본 입력 SHA256, REA 판정 코드, 산출물 해시를 기록했다. 원본 도구 출력에는 로컬 환경 정보가 포함되어 Git에서 제외한 `cache/research/`에 보관한다. 역분석한 제3자 Java 소스도 공개 저장소나 Claude 리뷰에 보내지 않는다.

공개 배포처와 고정 Society 브랜치의 도달 가능한 전체 이력 960개 커밋에서 필수 두 JAR/Java 소스를 아직 찾지 못했다. 정식 1.20.1 팩 파일을 이름만 바꿔 넣거나 임의의 가짜 모드로 누락을 숨기지 않는다. 사용자는 외부 개발자에게 문의를 게시하지 않기로 명시했다. 확보한 파일의 분석과 전체 기동 검증을 이어가는 경로로 진행한다.

추가로 Sunrise 설정의 `dewdrop:waterable` 주석을 따라 Chakyl의 [Dew Drop Farmland Growth 소스](https://github.com/Chakyl/Dew-Drop-Farmland-growth/tree/610f117103a652bae309385b5e21c753feaeeb37)와 공개 포크들을 확인했다. [1.21.1 이식 브랜치](https://github.com/yansunsky/Dew-Drop-Farmland-growth-NeoForge1.21.1/tree/2f3a44faac49b02f9a68fe01b849e357a5e44838)도 있지만 모드 ID는 `dew_drop_farmland_growth`이며 README가 기능 미완성을 명시한다. 계보 가능성을 조사한 것이며 Sunrise Gardening 소스를 찾았다는 뜻은 아니다. 기존 누락 파일을 이 포크로 대체하거나 허용 해시를 바꾸지 않았다. `evidence/sunrise-lineage-research.json`에 확인한 커밋과 범위를 기록했다.
