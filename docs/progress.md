# 진행 기록

| 완료 목표 | 상태 |
| --- | --- |
| Windows 플레이어용 세 프로젝트 설치 패키지 | 진행 중 — 설치 도구/진단 패키지 검증 완료, 별도 Forge 후보 전체 기동 확인, 최종 클라이언트 구성 중 |
| N100 세 프로젝트 통합 서버 | 진행 중 — 최소 조합 시험 통과, 별도 Forge 후보 로컬 전체 기동 확인, N100 배치 예정 |

이전 검증: N100에서 Pixelmon/Create/Aeronautics/Sable 최소 조합이 기동하고 물리 엔진 초기화와 엔티티 검사를 통과했다. 전체 Society는 포함하지 않았다. 해당 호환 코드 `12f9a56`은 Claude Opus 5.5 독립 리뷰에서 CLEAN이었다.

Phase별 구현 BASE, 검증 결과, 리뷰 SHA와 미해결 수를 이 문서에 추가한다. 로컬 리뷰 패킷과 개인 환경 정보는 Git에서 제외한 `review/`에 보관한다.

## Phase 1 — 설치 패키지 경로 완료

- BASE `3bf90f122e2b98aba8a2f69f559a4968c7b69199`.
- 구현 `df239b6884669af3aaa63d8c9a8072b08150e563`; 리뷰 지적 수정 `395a36ca203d14d8198d0f6e862b5c95183dddf6`.
- [PR #1](https://github.com/kei781/minecraft_Pixelmon_Society_Aeronautics/pull/1)은 열려 있으며 병합하지 않았다.
- 실제 최신 Claude Opus 5.5 두 회차. R1의 P2 한 건(무시 파일/심볼릭 링크 복사)을 수정했다. R2 CLEAN, 브리지 적용 후 실제 미해결 스레드 0건. CI 체크는 설정되어 있지 않아 별도 CI 통과로 주장하지 않는다.
- 자동 검사 14개 통과. 실제 고정 upstream 설정 2,996개와 리소스 89개를 확인했다. 리소스 재구성 SHA256은 변하지 않았다. 예시 Windows 설치 경로 길이 측정도 완료했다.
- `PSA-DIAGNOSTIC-NO-SOCIETY-bundled.mrpack` 생성. 실제 macOS Prism 11.1.1에서 가져오기 완료, Minecraft/NeoForge 구성과 모드 6개 크기·SHA512, 메타데이터 외 overrides 79개 SHA256을 확인했다. 최초 다운로드형은 Pixelmon HTTP/2 오류로 실패했고 파일 포함형으로 설치 경로를 검증했다.
- [Windows 안내](windows-client.md), 내보내기 도구, 실제 검증 기록을 제공한다. Windows 실행·게임 접속과 전체 세 프로젝트 최종 패키지는 이 단계의 완료에 포함되지 않는다.

## Phase 2 — 필수 콘텐츠/전체 기동 진행 중

`society-2.0-1.21.1.jar`와 `sunrisegardening-1.0.jar`는 아직 없다. 전체 staging/export는 계속 차단하며 가짜 모드·다른 프로젝트로 누락을 숨기지 않는다. Orchard와 Plentiful Ponds 소스 후보 두 개는 확보했다.

요청한 REA 6.8.0을 작업 폴더에서 실제 실행했다. 공개 Society 1.22 JAR의 ZIP 목록 분석은 성공했지만 auto 심층 분석은 `capability_unavailable/unsupported_provider`로 종료했다. Java 분석은 기존 CFR·javap 경로가 가능하다. [REA 결과](rea-findings.md)에 실제 범위와 추가 소스 계보 조사를 남겼다.

사용자는 개발자에게 문의를 게시하지 않기로 명시했다. 외부 문의는 게시하지 않았다. 사용자가 파일을 설치해 확보하는 경로와 공개 파일/소스 조사를 이어간다. 필수 두 파일을 확보하면 해시와 정체성을 확인하고 전체 기동 검증을 재개한다.

별도 1.20.1 후보: 정식 Society 4.1.5A 서버팩 원본 311개 모드를 유지하고 Pixelmon 9.2.3 베타 및 실제 Aeronautics Forge 포팅 소스를 더해 전체 월드가 시작됐다. 데이터/아트 누락과 Leaves Be Gone의 조립 충돌을 수정했다. 수정본에서 퀘스트 1,142개, 정상 몹 공존, 필수 물리 태그, 실제 1블록 구조물 조립 및 명령 권한 검사를 확인했다. 게임 플레이·Windows·N100 전체 팩·6인 검증은 남아 있다. [후보 상세](forge-candidate.md). Phase 2 Claude 리뷰는 아직 진행 전이다.
