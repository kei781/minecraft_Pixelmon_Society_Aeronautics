# 세 프로젝트 공존 전수 조사와 보정 (Task 19)

목표는 한 서버·한 월드에서 Pixelmon, Society: Sunlit Valley, Create Aeronautics를 번갈아
즐기는 것이다. 마을 문제([별도 문서](village-structure-compatibility.md))를 고친 뒤,
**코드·데이터·로그로 증명할 수 있는** 공존 버그를 전수 조사했다. 게임 밸런스나 취향
문제는 다루지 않았다.

결과는 두 묶음이다.

- **데이터 보정 11건** — 서버의 `kubejs/` 파일과 `config/lithium.properties` 네 줄. 모드 JAR는
  그대로다.
- **포팅 JAR 수정 2건** — 서버를 중단시키는 결함 두 가지는 데이터로 고칠 수 없어 공통
  JAR(Aeronautics 포팅본)에 믹신 클래스 두 개를 더했다. 공통 JAR이 바뀌므로 **서버와
  플레이어 팩을 함께 교체해야 한다.**

## 방법

1. **데이터 중복 조사** — `tools/audit_data_overrides.py`. 보정 전 프로필의 모드 JAR 314개와
   KubeJS 데이터에서 둘 이상이 제공하는 데이터 파일 2,058개 중 Pixelmon·Aeronautics
   포팅이 관련된 78개를 가려냈다. [목록](../evidence/village-data-overlaps.json).
2. **다섯 영역 정적 조사 + 반박 검증** — 구조물/월드젠, 전리품·레시피·태그, 로그,
   KubeJS 스크립트, 설정을 각각 독립 조사하고, 영역마다 별도의 검증자가 같은 파일을
   다시 읽어 반박을 시도했다. 검증에서 범위가 줄거나 수정안이 기각된 항목은 아래 표에
   그대로 반영했다. 이 단계의 작업 기록은 저장소에 남기지 않았다.
3. **실제 게임 대조** — `tests/forge-village-probe.js`와 `tests/forge-coexistence-checks.json`.
   수정 전·후 프로필을 각각 새 월드로 기동해 태그 내용, 제작 결과, 전리품 추첨,
   구조물 조립을 게임 API와 콘솔 명령으로 확인했다.
4. **블록 전수 물리 조립** — `tests/forge-assembly-probe.js`. 블록 엔티티가 있는 등록 블록을
   하나씩 설치해 표시한 아이템 한 개를 넣고(아이템 핸들러, 안 되면 저장 데이터), 포팅본의
   `sable assemble area` 명령으로 그 블록만 조립한 뒤 표시 아이템이 땅과 옮겨진 블록 중
   어디에 있는지 센다. 둘 다에 있으면 복제다. 출하함 한 건에서 멈추지 않고 같은 유형을
   전부 찾기 위한 검사이며, 아래 포팅 JAR 결함 두 건도 이 검사를 돌리다 드러났다.
5. **독립 리뷰** — 보정 파일은 구현과 별도의 검토자가 바이트코드에서 다시 유도해 검토했고,
   전체 변경은 최신 Claude Opus가 네 영역으로 나눠 검토한 뒤 각 지적을 다른 검토자가
   반박 검증했다. 받아들인 지적은 [리뷰 반영](#리뷰-반영)에 적었다.

## 데이터 보정

`--coexistence-fix`로 staging하면 적용된다.

| # | 문제 | 원인 | 보정 |
| --- | --- | --- | --- |
| 1 | 마을에서 Pixelmon 건물 누락, 사막 마을 포켓몬센터 30곳 중 3곳, 시작점에 마을 없음 | 두 프로젝트가 같은 바닐라 마을 파일을 교체, 시작점 규칙 충돌 | [마을 문서](village-structure-compatibility.md) |
| 2 | **아이템 복제**: 내용물이 든 블록을 물리 조립(비행체로 만들기·해체·분리)하면 내용물이 원래 자리에 떨어지고 옮겨진 블록에도 그대로 남음. 블록 엔티티가 있는 블록 4,181개를 검사해, 표시 아이템을 넣을 수 있었던 1,558개를 조립한 결과 **306개**가 복제됨: Society 출하함·기계, Create 아이템 금고·보관소·대야·우편함 등, 가구·주방·양조 모드 수납 블록, Pixelmon 체육관 표지판 48개 등 | 포팅본 `SubLevelAssemblyHelper.moveBlocks`는 블록 엔티티 데이터를 새 위치에 복사한 뒤 원래 블록을 공기로 바꾸는데, 이때 원래 블록의 `onRemove`가 내용물을 다시 떨어뜨림. `Clearable`인 바닐라식 상자만 미리 비워짐. 포팅 소스의 주석도 이 문제를 알고 있으며 블록별 태그로 고치도록 해 두었음. 조립기는 Society의 이동 불가 태그(`create:non_movable`)도 무시 | 포팅본이 마련한 `sable:silent_assembly_removal` 태그에 310개 블록을 추가(옮기기 전에 원래 블록 엔티티를 떼어내 떨어뜨리지 않음). 구성: 이전 공통 JAR에서 실측한 복제 306개, 게임에서 복제를 보이지는 못했지만 코드 분석으로 넣은 4개(`pixelmon:cloning_machine`, `pixelmon:fossil_display`, `pixelmon:infuser`, `society:auto_worm_farm`). Society가 이동 불가로 지정한 52개와 Create 기차역은 조립기가 실제로 확인하는 `simulated:non_movable`에도 추가. 같은 전수 검사를 수정본에서 다시 돌려 복제 0개를 확인했고, 이후 모드가 바뀌면 이 검사가 새 복제 블록을 잡음 |
| 3 | Aeronautics 부품 5종(스팀 벤트, 조종사 고글, 레드스톤 축전기·유도기, 로프 커플링) 제작 불가, 명패 재염색 15색 불가 | 포팅 데이터가 정의되지 않은 태그 22개(`c:dusts/redstone`, `c:stones`, `c:leathers`, `c:plates/*`, `c:dyes/*`, `forge:strings`)를 참조. 수정 전 실행에서 측정한 8개는 모두 비어 있었음. 제작 불가는 빈 태그에서 따라 나오는 결과이며 제작 자체를 시험하지는 않음 | 같은 이름의 태그 22개를 Forge 태그에 연결 |
| 4 | 바닐라 상자에서 갑옷 장식 템플릿(rib·vex·dune·wild·sentry·coast), 염소 뿔, 레일 등이 나오지 않음. 측정한 9개 표에서 300~600회 추첨에 0회 | Pixelmon JAR이 바닐라 상자 전리품 40개를 구버전 자체 사본으로 통째 교체 | 37개 표를 다시 만듦: 바닐라 1.20.1 원본 표를 그대로 두고 Pixelmon 사본에서 Pixelmon 아이템이 나오는 풀만 뒤에 붙임. 그 풀 안의 바닐라 아이템 항목은 같은 가중치의 빈 항목으로 바꿔 Pixelmon 아이템 확률을 유지 |
| 5 | 바스티온 상자 3종에서 Pixelmon 전리품 0회 | Society KubeJS가 같은 파일을 교체 | Society 표 + Pixelmon 고유 풀 |
| 6 | 포켓볼 받침·Pixelmon 장식 레시피가 Society 쪽 모드 레시피와 같은 조합 | 서로 다른 모드가 같은 모양·재료 등록 | Pixelmon 받침 조합은 그대로. 겹치던 무쇠 다락문(철괴 3 + 아래 철 조각 1), 아이템 선반(나무 반블록 3 + 아래 막대기 1), Pixelmon 상자(종이 7장, 위 가운데와 정가운데를 비운 U자 모양)의 모양을 바꾸고, Pixelmon 다리 블록·엔드 테이블 재료에서 Botania 목재를 제외, Pixelmon 은 블록·은 광석 제련은 Pixelmon 은만 받게 함 |
| 7 | 다이아 올가미로 포켓몬·석상·자전거를 아이템으로 집어감 | Pixelmon 엔티티가 `Animal` 계열, Mob Lassos 블랙리스트 비어 있음 | `moblassos:*_lasso_blacklist` 태그에 세 엔티티 추가 |
| 8 | 비행체 재로딩 시 NPE 가능 경로 | 포팅본이 `mods.toml` 최상위에 선언한 Radium 비호환 옵션 4개를 Radium이 읽지 않음 (수정 전 로그: 설정으로 꺼진 옵션 1개뿐) | `config/lithium.properties`에 같은 네 옵션을 직접 지정 |
| 9 | 페어리 체육관에 관장·트레이너 없음 (Pixelmon 자체 버그) | NPC 풀 `pixelmon:npc/gyms/fairy` 파일 누락 | 풀 파일 추가 |
| 10 | 평원·타이가 레이드 굴이 생성되지 않음 (Pixelmon 자체 누락) | 구조물은 있으나 구조물 세트에 미등록 | Lithostitched `add_structure_set_entries`로 `pixelmon:dens`에 두 구조물 등록(13 → 15종). 굴 격자 위치는 그대로이고 새로 생성되는 청크부터 적용 |
| 11 | Miltank에게 빈 양동이를 쓰면 우유가 사라지고 빈 양동이만 돌아옴 | Pixelmon은 바닐라 우유 양동이를 주는데 Society `milkBan.js`가 바닐라 우유 양동이를 금지 | Miltank 상호작용 직후(2틱 이내)에 생긴 우유 양동이만 `society:milk` 1개 + 빈 양동이로 교환. Society의 우유 금지는 그대로 |

## 포팅 JAR 수정

두 결함 모두 **서버가 중단되고, 재시작해도 반복**된다. 수정 전 재현 기록:
[레드스톤 접점](../evidence/redstone-contact-server-crash.json),
[Pixelmon 다중 블록](../evidence/pixelmon-multiblock-physics-crash.json).
재현은 콘솔 명령으로 했다. 플레이어의 설치와 실제 비행은 같은 코드를 지나지만 따로
시험하지 않았다.

| # | 문제 (수정 전, 콘솔로 재현) | 원인 | 수정 |
| --- | --- | --- | --- |
| 12 | Create 레드스톤 접점(`create:redstone_contact`)을 설치하면 서버가 즉시 중단되고, 저장된 뒤에는 그 청크가 로드될 때마다 다시 중단됨. Create 엘리베이터가 층을 지정할 때 쓰는 블록 | 포팅본 `RedstoneContactBlockMixin.getTicker`의 `IBE.super.getTicker(...)` 호출을 이 팩의 Mixin이 대상 클래스 자신에 대한 호출로 바꾸고, JVM이 그 호출을 거부(`IncompatibleClassChangeError`). 314개 모드의 믹신 클래스에서 인터페이스 super 호출 6곳을 모두 찾아 확인했고 이 형태로 깨지는 것은 이 하나뿐 | `PortRedstoneContactTickerMixin`: 문제의 호출에 도달하기 전에, Create의 `IBE.getTicker`가 `SmartBlockEntity`에 돌려주는 것과 같은 값을 돌려줌 |
| 13 | Pixelmon의 여러 칸짜리 블록(PC, 교환기, 자판기, 화석 기계·세척기·전시대, 복제 장치, 인퓨저, 요리 냄비, 소파, 러그, TV, 유리 탁자, 나무, TCG 관전석)을 설치하면 예외로 실패해 한 칸만 남음. 기본 상태로 놓으면 92개 id, 아래 칸 상태로 놓으면 유리 탁자를 뺀 91개 id가 실패. 생성된 PC 바로 위 칸에 블록을 놓아도 같은 예외. 그 옆 블록을 물리 구조물로 조립하면 **서버 중단**(`Exception ticking world`), 같은 월드로 재시작해도 중단 | 포팅본 `RapierVoxelColliderBakery`가 블록의 충돌 모양을 물을 때 넘기는 대역 월드(`PhysicsColliderBlockGetter`)에 블록 상태를 넣지 않아(`setup` 호출이 포팅 소스 어디에도 없음) 자기 자리의 블록을 `null`로 답함. Pixelmon `MultiBlock.getShape`는 자기 자리의 블록을 읽음. 이 계산은 로드된 청크의 모든 블록 변경과 그 이웃 여섯 칸, 그리고 물리 구조물이 가까이 온 청크 구역(16×16×16)의 모든 블록에 대해 실행됨 | `PortColliderShapeMixin`: 모양을 묻기 전에 블록 상태를 넣고, 그래도 예외를 내는 블록은 꽉 찬 블록으로 충돌 처리하며 블록 종류마다 한 번 경고를 남김. 상태만 넣어서는 부족함: Pixelmon 다중 블록의 위 칸은 아래 칸을 찾아 읽는데 대역 월드의 이웃은 공기임 |

두 클래스는 `compat/forge-port/`에 소스가 있고, `tools/forge-port-fix.gradle`로 포팅 작업
트리에서 컴파일한 뒤 `tools/forge_portfix_compat.py`가 기존 공통 JAR에 두 클래스와 믹신
설정만 더한다. 나머지 4,182개 항목은 바이트 단위로 그대로다. 독립된 두 작업 트리의 빌드
결과가 같았다. 입력·소스·클래스 해시는 [`compat/port-fix-build.json`](../compat/port-fix-build.json)에
고정했고, 결과 공통 JAR의 SHA256은
`28e1958563c4c313bbbf42448b15594c2cc8a3ca7a7f8d1ac5b7f47426f36c1c`다.

```sh
gradle --offline --no-daemon --max-workers=2 -p /path/to/prepared-port-workspace \
  -I tools/forge-port-fix.gradle -PpsaPortFixSource=/path/to/repository/compat/forge-port \
  reobfPsaPortFixJar
python3 tools/forge_resources.py canonical-jar \
  /path/to/prepared-port-workspace/build/libs/psa-port-fix-0.1.jar /path/to/psa-port-fix-canonical.jar
python3 tools/forge_portfix_compat.py --base /path/to/accepted-starter-common.jar \
  --tested-patch /path/to/psa-port-fix-canonical.jar --output /path/to/new-common.jar
```

## 동작이 달라지는 것

- 무쇠 다락문, 아이템 선반, Pixelmon 상자의 조합 모양이 위 6번처럼 바뀐다. 다시 등록된
  세 레시피는 id가 `psa_coexistence:*`라서 기존 레시피 해금 발전 과제가 가리키는 id와 다르다.
- Society가 이동 불가로 지정한 기계 52종과 Create 기차역은 물리 조립기로 옮길 수 없다.
  조립을 그 블록에서 시작하면 실패한다.
- 평원·타이가 굴이 추가돼, 새로 생성되는 청크에서 굴 종류의 분포가 달라진다.
- 다시 만든 상자 전리품은 바닐라 표에 Pixelmon 풀을 더한 것이라 상자당 아이템 수가 늘 수 있다.
- 이미 생성된 청크의 마을과 전리품 상자는 바뀌지 않는다.

## 확인했지만 이번에 고치지 않은 것

| 항목 | 내용 | 이유 |
| --- | --- | --- |
| 포켓몬이 바닐라 동물 스폰 상한을 차지 | 야생 포켓몬이 CREATURE/WATER_CREATURE로 집계돼 오징어·돌고래 등 재스폰이 줄어듦 | 서버 전용 믹스인 JAR이 필요해 모드 구성(314개)과 시작 검사를 바꿔야 함. 별도 단계로 제안 |
| End 전용 Pixelmon 콘텐츠 | Society는 End를 없앴다. Iron Moth, Iron Thorns, Slither Wing, Walking Wake, Iron Leaves와 End 굴·그로토에 도달할 수 없음 | 어디에 옮길지는 콘텐츠 결정. 제안된 데이터 수정은 검증에서 동작하지 않는 것으로 판정 |
| Every Compat의 Pixelmon 목재 블록 144개 | 자동 등록됨 | 레지스트리를 바꾸는 설정이라 서버·클라이언트 동시 변경 필요. 게임 진행에 영향 없음 |
| ServerCore 활성 범위 | 16블록 밖 포켓몬 틱이 줄어 전설 타이머가 늘어남 | N100 부하를 위한 Society 설정의 절충. 그대로 둠 |
| Pixelmon 템플릿의 미등록 블록 3개·오타 풀 | 공기 한 칸, 장식 누락 | Pixelmon 상위 문제, 영향 미미 |
| Sable 전역 상세 로그, 서버의 클라이언트 클래스 참조 오류 | 로그 잡음 | 동작 영향 없음 |
| 드문 기동 실패 | 검사 실행 20여 회 중 한 번, 모드 로딩 단계에서 `Supplementaries has failed to load correctly`(Zeta 이벤트 버스의 `ArrayIndexOutOfBoundsException`)로 서버가 뜨지 않음. 다시 시작하면 정상 | Quark(Zeta)와 Supplementaries가 동시에 이벤트를 등록할 때의 경합으로, Society 팩 자체의 문제. 세 프로젝트 조합과 무관 |
| 전수 조립 검사의 한계 | 표시 아이템을 넣을 방법을 찾지 못한 블록 엔티티 2,408개는 조립되지 않았다. 대부분 인벤토리가 없는 블록이지만 전부 그렇다고 증명하지는 못함. 검사는 한 번에 블록 하나만 옮기므로 여러 칸짜리 저장소가 일부만 옮겨지는 경우는 다루지 않음 | 복제의 근본 원인은 포팅본의 옮기기 코드에 있다. 태그는 이 모드 구성에서 실측한 목록이다 |
| Create 기차역의 물리 이동 | 조립기로는 옮길 수 없게 했지만 운영자 명령(`sable assemble area`)으로 옮기면 옛 철도 그래프 항목이 남음 | 운영자 명령 경로뿐이며 아이템 복제는 없음 |
| 물리 구조물만 수백 개 있을 때의 물리 엔진 중단 | 검사 스크립트의 오류로 한 칸짜리 구조물 880여 개가 지워지지 않고 남았을 때 `Rapier native panic: No center of mass for body`로 한 번 중단됨. 같은 블록들을 하나씩 조립해서는 재현되지 않음 | 원인을 특정하지 못함. 플레이에서 닿는 경로인지 불명 |

## 다음 단계 제안

1. **야생 포켓몬의 스폰 상한 분리** — 서버 전용 믹스인 JAR이 필요하다(서버 모드 수 314 → 315).
2. **End 전용 Pixelmon 콘텐츠의 위치** — 콘텐츠 결정이 필요하다.
3. **플레이어 접속 상태의 확인** — 이 단계의 검증은 모두 플레이어 없이 콘솔과 게임 API로
   했다. 레드스톤 접점과 Pixelmon 기계를 손으로 설치하는 것, 포켓몬센터 옆에서 실제
   비행체를 조립하는 것, Miltank 우유 교환은 접속해서 확인해야 한다.

## 리뷰 반영

독립 리뷰(Opus, 네 영역, 지적마다 반박 검증)가 확인한 결함과 조치다. staging·내보내기
도구에서는 기능 결함이 나오지 않았다.

- 레드스톤 접점 임시 차단(레시피 제거 + 우클릭 거부)은 빈 공간을 향한 Create 디플로이어를
  막지 못했다. 임시 차단을 없애고 포팅 JAR을 고쳤다(12번).
- `create:track_station`을 조용히 떼어 내면 옛 철도 그래프 항목이 남는다. 조립기가 옮기지
  못하게 했다.
- 팩의 로그 필터(Log Begone)가 검사 기록 줄 일부를 콘솔에서 지워, 블록 레지스트리 목록의
  한 부분(1,500개)이 빠진 채 기록됐다. 검사 기록을 KubeJS 자체 로그에서 읽고, 부분이
  빠지면 실행을 실패로 처리한다.
- NBT 코덱이 BMP 밖 문자와 NUL을 Java가 읽는 형식으로 쓰지 않았다. 산출물에는 그런
  문자열이 없지만 코덱을 고치고 정확한 바이트를 검사한다.
- 문서의 수치와 표현 8곳(측정 범위, 태그 구성, 검사 수, 조합 모양 등)을 추적된 기록에 맞췄다.

## 검증

| 검사 (실제 게임, 새 월드) | 수정 전 | 수정 후 |
| --- | --- | --- |
| 포팅 레시피·올가미·물리 태그 12개에 기대한 항목이 있음 | 1/12 | 12/12 |
| 제작 격자 19개의 결과물 | 10/19 | 19/19 |
| 은 광석 제련·용광로 6개 | 4/6 | 6/6 |
| 전리품 표 12개 추첨에서 기대 아이템·네임스페이스 | 0/12 | 12/12 |
| 네더 요새 상자 600회 중 rib 장식 | 0/600 | 34/600 |
| 바스티온 보물 상자의 Pixelmon 전리품 | 없음 | 있음 |
| `pixelmon:dens` 구조물 종류 | 13 | 15 |
| 페어리 체육관 표본 3곳의 NPC 조각 | 0/0/0 | 8/8/8 |
| 다이아 6개를 넣은 블록의 물리 조립 (땅에 떨어진 묶음 수·옮겨진 블록 안 개수) | basic_shipping_bin 떨어짐 1·블록 안 6, artisan_hopper 떨어짐 1·블록 안 6 | basic_shipping_bin 떨어짐 0·블록 안 6, artisan_hopper 떨어짐 0·블록 안 6 |
| 블록 엔티티 블록 전수 물리 조립 | 4,181개 검사, 1,558개 조립: 복제 306, 사라짐 0, 검사 중 예외 93(Pixelmon 다중 블록 91) | 4,181개 검사, 1,560개 조립: 복제 0, 사라짐 0, 검사 중 예외 2(Pixelmon 0) |
| 레드스톤 접점 설치 후 서버 생존·블록 엔티티 | 서버 중단 | 통과 |
| Pixelmon PC 설치, 옆 칸 블록 설치, 옆 블록 물리 조립 후 서버 생존 | 실행되지 않음(앞 검사에서 서버 중단). 별도 재현에서는 서버 중단 | 통과 |
| Radium이 설정으로 끈 옵션 수 | 1 | 5 |
| KubeJS 서버 스크립트 오류 | 0 | 0 |

수정 후 실행에서 실패한 검사는 없다. 기록:
[수정 전](../evidence/village-worldgen-baseline.json),
[수정 후](../evidence/village-worldgen-fixed.json),
전수 조립 [수정 전](../evidence/assembly-inventory-sweep-baseline.json)·[수정 후](../evidence/assembly-inventory-sweep-fixed.json).
수정 전 실행은 레드스톤 접점 설치에서 서버가 중단되므로 그 뒤의 Pixelmon 기계 검사는
실행되지 않는다. 그 결함의 수정 전 기록은 위의 별도 재현이다. 같은 이유로 수정 전 실행의
전수 조립에서는 레드스톤 접점을 빼고 돌렸다(`--skip-in-sweep create:redstone_contact`).

Miltank 우유 교환은 플레이어 상호작용이 필요해 게임에서 실행하지 못했다. 스크립트는 팩의
Rhino 엔진과 대역 객체로만 검증했다.

Python 검사는 160개를 실행해 154개가 통과한다. 6개는 Linux tmux 제어
검사라 macOS에서 생략되고, 고정된 비공개 입력이 없으면 4개가 더 생략된다.

## 재현

```bash
python3 tools/stage_forge_candidate.py --server-pack … --pixelmon … --port /path/to/new-common.jar \
  --datapack-fix … \
  --coexistence-fix /path/to/libraries/net/minecraft/server/1.20.1-20230612.114412/server-1.20.1-20230612.114412-extra.jar \
  --destination /path/to/fresh-profile --mode player
python3 tools/run_village_probe.py --source /path/to/fresh-profile --destination /path/to/disposable \
  --libraries /path/to/forge-libraries --java /path/to/jdk-17/bin/java --output result.json --accept-eula
python3 -m unittest discover -s tests -p 'test_*.py'
```
