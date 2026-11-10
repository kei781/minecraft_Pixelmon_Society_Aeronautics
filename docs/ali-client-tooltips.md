# 원격 접속 후 ALI 툴팁 등록 오류

원래 전체 클라이언트에서 원격 N100 서버로 접속하면 ALI의 거래 위젯 생성 중
`TooltipNode.empty()`가 null 서버 레지스트리를 조회해 NPE가 났다.
빈 노드 조회만 고친 중간 빌드에서는 다음 `TooltipBuilder.build()`가 같은 이유로 실패했다.
두 실제 오류와 중간 결과를 보존했다.

자체 클라이언트 전용 모드는 두 생성 함수의 캐시 조회 한 곳씩만 보정한다.
물리 클라이언트에서 서버 레지스트리가 없고 기존 클라이언트 레지스트리가 있으면
그 원래 캐시를 쓴다. 나머지는 원래 서버 레지스트리 조회를 그대로 호출한다.
네이티브 노드 생성·키·값·플래그·자식·캐시 재사용·인코딩/디코딩은 바꾸지 않는다.
새 대체 캐시나 더미 노드, 거래 제거, 예외 무시는 사용하지 않는다.

고정 ALI 바이너리에서 관련 서버 캐시 참조 후보는 세 클래스였다. 클라이언트에서
호출되는 두 생성 경로를 수정했고, 서버에서 전리품을 인코딩하고 캐시를 정리하는
`AbstractServer`는 그대로 뒀다. 문자열 참조 조사가 모든 동적 호출을 증명하지는 않는다.

## 실제 검증과 설정 보존

수정 전 실제 접속에서 클라이언트 레지스트리는 존재하고 서버 레지스트리는 null이었다.
캐시에 30,804개 노드와 원래 빈 노드가 있었지만 빈 노드 팩터리는 NPE로 실패했다.
수정 후에는 기존 빈 노드 ID 1을 재사용하고 기본·고급 모드 모두 빈 노드로 판정됐다.
일반 빌더의 네이티브 키 전용 제어 표본도 비어 있지 않은 실제 텍스트 컴포넌트를 만들었다.
이는 자체 표시문구 하나의 로컬 캐시 항목이며 게임 아이템·서버 데이터·인증을 합성하지 않는다.
검사 전 존재하던 모든 캐시 ID의 객체 정체성을 검사 후에도 유지했다.

최종 빌드의 첫 관찰에서는 캐시가 30,809개였고 빈 팩터리 호출 뒤에도 같았다.
자체 빌더 표본이 그 뒤 한 항목을 추가했으며 다시 호출하면 같은 ID를 재사용했다. 전체 데이터 등록이
`Data registration finished successfully`로 끝났고 원래의 등록 실패는 없었다.
기존 ALI 전리품 레시피 12,246개와 각 카테고리 수량도 보존됐다.

Society 원본은 `kubejs/assets/emi/recipe/filters/emi.json`에서
`ali:trade_loot`, `ali:fishing_loot`, `ali:hero_loot`를 EMI 결과에서 숨긴다.
그래서 수정 후에도 이 세 카테고리의 최종 레시피 수는 0이다. 이를 임의로 풀거나
레시피 증가를 성공 조건으로 만들지 않았다. 필터 SHA256은
`4b5d8a639a6089c984535f33635dbc5bdb9807f2144f666a5c1eaef9902f15cf`이며
서버·기존 클라이언트·새 팩에서 같은 바이트를 유지한다.
원래 전역 레시피 수만 보던 관찰 도구에 카테고리별 실제 조회도 추가해 이를 확인했다.

원본·중간·최종 기록과 각 진단 빌드는 [증거](../evidence/ali-client-tooltips.json)에 구분한다.
화면 조작은 정상 Prism 실행에만 사용했고, 스타터 선택 화면을 강제로 닫지 않았다.
실제 거래 화면의 육안 검수·단일 플레이·6인 부하·최신 Windows 가져오기는 합격으로
기록하지 않는다. 기존 Connectivity 경고와 ReliableEmi 그룹 오류도 별도 후속이다.

## 패키지와 재생성

서버의 313개 모드·공통 JAR·월드는 이 단계에서 바꾸지 않는다. v18 클라이언트는
기존 v17의 354개 모드에 `PSA-ALI-Client-Compat-0.1.jar` 하나를 더해 355개다.
모드 외에 달라진 것은 가져오기 색인과 프로필뿐이며 기존 payload 7,931개는 같다.
원래 ALI JAR도 그대로다. 진단 attach 도구·계정·세이브는 팩에 넣지 않는다.

호환 JAR는 7,095바이트·9개 항목이며 SHA256은
`8046126f8834b6e7fea3fa6e6691ca29b816a1ec27ef1d669a780081eb34e534`다.
두 독립 준비 환경의 정규화 빌드가 같다. [자체 소스·클래스·입력 고정값](../compat/ali-client-build.json).
최초 후보는 `pack.mcmeta` 누락으로 로딩 오류 화면에 머물러 거부했다.
두 번째 후보는 빈 노드만 고쳐 일반 빌더에서 실패했다. 두 후보 모두 배포 합격이 아니다.

```sh
gradle --offline --no-daemon --max-workers=2 -p /path/to/prepared-forge-workspace \
  -I /path/to/repository/tools/forge-ali-client.gradle \
  -PpsaAliSource=/path/to/repository/compat/ali-client \
  -PpsaAliJar=/path/to/AdvancedLootInfo-forge-1.20.1-1.12.0.jar reobfPsaAliClientJar
python3 tools/forge_resources.py canonical-jar \
  /path/to/prepared-forge-workspace/build/libs/PSA-ALI-Client-Compat-0.1.jar \
  /path/to/fresh-ali-client-compat.jar
```

Java 17.0.21·Forge 47.4.20 준비 환경을 사용한다. 필수 모드 생성자는 ALI 해시를
다시 검사하고 두 대상 클래스를 로드한 뒤 두 변환의 적용을 모두 확인한다.
Mixin plugin 초기화 예외가 설정만 빠뜨리고 계속 실행되는 경우도 거부한다.
재사용 가능한 helper/plugin은 mixin 전용 패키지 밖에 두었다.
네이티브 QA 관찰기는 `--kind ali`로 별도 빌드하며 production mod가 아니다.
버전별 클래스 이름을 나눠 이미 로드한 에이전트 클래스를 재정의하지 않는다.
