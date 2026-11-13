# 세 프로젝트 공존 전수 조사와 보정 (Task 19)

목표는 한 서버·한 월드에서 Pixelmon, Society: Sunlit Valley, Create Aeronautics를 번갈아
즐기는 것이다. 마을 문제([별도 문서](village-structure-compatibility.md))를 고친 뒤,
**코드·데이터·로그로 증명할 수 있는** 공존 버그를 전수 조사했다. 게임 밸런스나 취향
문제는 다루지 않았다.

## 방법

1. **데이터 중복 조사** — `tools/audit_data_overrides.py`. 프로필의 모드 JAR 314개와
   KubeJS 데이터에서 둘 이상이 제공하는 데이터 파일 2,058개 중 Pixelmon·Aeronautics
   포팅이 관련된 78개를 가려냈다.
2. **다섯 영역 정적 조사 + 반박 검증** — 구조물/월드젠, 전리품·레시피·태그, 로그,
   KubeJS 스크립트, 설정을 각각 독립 조사하고, 영역마다 별도의 검증자가 같은 파일을
   다시 읽어 반박을 시도했다. 조사 34건 중 검증에서 범위가 줄거나 수정안이 기각된
   항목은 아래 표에 그대로 반영했다. 구조물 템플릿 1,009개의 블록·엔티티·풀·전리품
   참조와 레시피 1,330개의 재료를 실행 중 레지스트리와 대조했다.
3. **실제 게임 대조** — `tests/forge-village-probe.js`와 `tests/forge-coexistence-checks.json`.
   수정 전·후 프로필을 각각 새 월드로 기동해 태그 내용, 제작 결과, 전리품 추첨,
   구조물 조립, 물리 조립 시 아이템 낙하를 게임 API와 콘솔 명령으로 확인했다.
4. **블록 전수 물리 조립** — `tests/forge-assembly-probe.js`. 블록 엔티티가 있는 등록 블록을
   하나씩 설치해 표시한 아이템 한 개를 넣고(아이템 핸들러, 안 되면 저장 데이터), 포팅본의
   `sable assemble area` 명령으로 그 블록만 조립한 뒤 표시 아이템이 땅과 옮겨진 블록 중
   어디에 있는지 센다. 둘 다에 있으면 복제다. 출하함 한 건에서 멈추지 않고 같은 유형을
   전부 찾기 위한 검사이며, 이 검사 도중 레드스톤 접점과 Pixelmon 다중 블록의 문제도 드러났다.
5. **독립 리뷰** — 보정 파일은 구현과 별도의 검토자가 바이트코드에서 다시 유도해 검토했고,
   Pixelmon 블록의 복제 누락과 Miltank 스크립트의 아이템 삭제 가능 경로를 고쳤다.

## 고친 것

모드 JAR는 바꾸지 않았다. `--coexistence-fix`로 staging하면 서버의 `kubejs/` 추가·교체
파일과 `config/lithium.properties` 네 줄이 적용된다. 클라이언트 재설치 없이 서버만
갱신해도 멀티플레이에 적용된다. 표의 2번과 12번은 원인이 포팅 JAR 안에 있어 데이터로
막아 둔 것이며, JAR 자체를 고치는 일은 [다음 단계](#다음-단계-제안)에 적었다.

| # | 문제 (수정 전 실측) | 원인 | 보정 |
| --- | --- | --- | --- |
| 1 | 마을에서 Pixelmon 건물 누락, 사막 마을 포켓몬센터 10~17%, 시작점에 마을 없음 | 두 프로젝트가 같은 바닐라 마을 파일을 교체, 시작점 규칙 충돌 | [마을 문서](village-structure-compatibility.md) |
| 2 | **아이템 복제**: 내용물이 든 블록을 물리 조립(비행체로 만들기·해체·분리)하면 내용물이 원래 자리에 떨어지고 옮겨진 블록에도 그대로 남음. 블록 엔티티가 있는 등록 블록 4,181개를 게임 안에서 하나씩 조립해 본 결과 **306개**가 복제됨: Society 출하함·기계, Create 아이템 금고·보관소·대야·우편함 등 32개, 가구·주방·양조 모드 수납 블록, Pixelmon 체육관 표지판 48개 등 | 포팅본 `SubLevelAssemblyHelper.moveBlocks`는 블록 엔티티 데이터를 새 위치에 복사한 뒤 원래 블록을 공기로 바꾸는데, 이때 원래 블록의 `onRemove`가 내용물을 다시 떨어뜨림. `Clearable`인 바닐라식 상자만 미리 비워짐. Create 자체 구조물은 블록 엔티티를 먼저 제거하므로 원래는 없던 문제. 조립기는 Society의 이동 불가 태그(`create:non_movable`)도 무시 | 복제가 확인된 블록 310개를 포팅본의 `sable:silent_assembly_removal` 태그에 추가(옮기기 전에 원래 블록 엔티티를 떼어내 떨어뜨리지 않음). 실측 306개 + 바이트코드로 증명한 Pixelmon 복제 장치·화석 전시대·인퓨저. Society가 이동 불가로 지정한 52개는 조립기가 실제로 확인하는 `simulated:non_movable`에도 추가. 같은 전수 검사를 수정본에서 다시 돌려 복제 0개를 확인하고, 이후 모드가 바뀌면 이 검사가 새 복제 블록을 잡음 |
| 3 | Aeronautics 부품 5종(스팀 벤트, 조종사 고글, 레드스톤 축전기·유도기, 로프 커플링) 제작 불가, 명패 재염색 15색 불가 | 포팅 데이터가 정의되지 않은 태그(`c:dusts/redstone`, `c:stones`, `c:leathers`, `c:plates/*`, `c:dyes/*`, `forge:strings`)를 참조. 수정 전 실측에서 모두 빈 태그 | 같은 이름의 태그 22개를 Forge 태그에 연결 |
| 4 | 바닐라 상자 37종에서 갑옷 장식 템플릿(rib·vex·dune·wild·sentry·coast…), 염소 뿔, 레일 등이 0회 (300~600회 추첨) | Pixelmon JAR이 바닐라 상자 전리품 40개를 구버전 자체 사본으로 통째 교체 | 바닐라 1.20.1 원본 표를 그대로 두고 Pixelmon 사본에서 Pixelmon 아이템이 나오는 풀만 뒤에 붙여 다시 만듦. 그 풀 안의 바닐라 아이템 항목은 같은 가중치의 빈 항목으로 바꿔 Pixelmon 아이템 확률을 유지 |
| 5 | 바스티온 상자 3종에서 Pixelmon 전리품 0회 | Society KubeJS가 같은 파일을 교체 | Society 표 + Pixelmon 고유 풀 |
| 6 | 포켓볼 받침·Pixelmon 장식 레시피가 Society 쪽 모드 레시피와 같은 조합 | 서로 다른 모드가 같은 모양·재료 등록 | Pixelmon 받침 조합은 그대로. 겹치던 무쇠 다락문(철괴 3 + 아래 철 조각 1), 아이템 선반(나무 반블록 3 + 아래 막대기 1), Pixelmon 상자(종이 7장, 위 가운데 비움)의 모양을 바꾸고, Pixelmon 다리 블록·엔드 테이블 재료에서 Botania 목재를 제외, Pixelmon 은 블록·은 광석 제련은 Pixelmon 은만 받게 함 |
| 7 | 다이아 올가미로 포켓몬·석상·자전거를 아이템으로 집어감 | Pixelmon 엔티티가 `Animal` 계열, Mob Lassos 블랙리스트 비어 있음 | `moblassos:*_lasso_blacklist` 태그에 세 엔티티 추가 |
| 8 | 비행체 재로딩 시 NPE 가능 경로 | 포팅본이 `mods.toml` 최상위에 선언한 Radium 비호환 옵션 4개를 Radium이 읽지 않음 (수정 전 로그: 사용자 설정으로 꺼진 옵션 1개뿐) | `config/lithium.properties`에 같은 네 옵션을 직접 지정 |
| 9 | 페어리 체육관에 관장·트레이너 없음 (Pixelmon 자체 버그) | NPC 풀 `pixelmon:npc/gyms/fairy` 파일 누락 | 풀 파일 추가 |
| 10 | 평원·타이가 레이드 굴이 생성되지 않음 (Pixelmon 자체 누락) | 구조물은 있으나 구조물 세트에 미등록 | Lithostitched `add_structure_set_entries`로 `pixelmon:dens`에 두 구조물 등록(13 → 15종). 굴 격자 위치는 그대로이고 새로 생성되는 청크부터 적용 |
| 11 | Miltank에게 빈 양동이를 쓰면 우유가 사라지고 빈 양동이만 돌아옴 | Pixelmon은 바닐라 우유 양동이를 주는데 Society `milkBan.js`가 바닐라 우유 양동이를 금지 | Miltank 상호작용 직후(2틱 이내)에 생긴 우유 양동이만 `society:milk` 1개 + 빈 양동이로 교환. Society의 우유 금지는 그대로 |
| 12 | **서버 중단**: Create 레드스톤 접점(`create:redstone_contact`)을 설치하면 서버가 즉시 죽고, 저장된 뒤에는 그 청크가 로드될 때마다 다시 죽음. Create 엘리베이터 층 표시에 쓰는 블록 | 포팅본 `RedstoneContactBlockMixin.getTicker`의 `IBE.super.getTicker(...)` 호출을 이 팩의 Mixin이 대상 클래스 호출로 바꿔 JVM이 거부(`IncompatibleClassChangeError`). 314개 모드의 믹신 중 이 형태로 깨지는 것은 이 하나뿐임을 전수 확인 | **임시 차단(근본 수정 아님)**: 제작 레시피 제거 + 아이템 사용(플레이어·디플로이어) 거부. 운영자 명령 `/setblock` 등은 막지 못함. 근본 수정은 포팅 소스 한 줄 변경과 JAR 재빌드가 필요해 [다음 단계](#다음-단계-제안)로 분리 |

## 고치지 못한 치명 문제: Pixelmon 기계와 물리 구조물

**이 PR을 반영해도 남는다. 포팅 JAR을 고쳐야 한다([다음 단계](#다음-단계-제안)).**

Pixelmon의 여러 칸짜리 블록 92종(PC, 교환기, 자판기, 화석 기계·세척기·전시대, 복제 장치,
인퓨저, 요리 냄비, 소파, 러그, TV, 유리 탁자, 나무, TCG 관전석)은 포팅본의 물리 충돌
계산과 만나면 예외를 낸다. 수정본 프로필의 생성된 포켓몬센터에서 콘솔로 확인했다.
[기록](../evidence/pixelmon-multiblock-physics-crash.json).

| 한 일 | 결과 |
| --- | --- |
| `setblock`으로 PC 설치 | 예외로 실패. 아래 칸만 남고 위 칸과 블록 엔티티가 없음 |
| 생성된 PC 바로 위 칸에 돌 설치 | 같은 예외로 실패 |
| 그 돌을 물리 구조물로 조립 | **서버 중단** (`Exception ticking world`) |
| 같은 월드로 재시작 | **다시 중단** (구조물이 저장돼 있어 반복) |

원인은 포팅본 `RapierVoxelColliderBakery`가 블록의 충돌 모양을 물을 때 넘기는 가짜
월드(`PhysicsColliderBlockGetter`)에 블록 상태를 넣지 않아(`setup` 호출이 포팅 소스 어디에도
없음) 자기 자리의 블록을 `null`로 답하는 것이다. Pixelmon `MultiBlock.getShape`는 자기 자리의
블록을 읽는다. 이 계산은 로드된 청크의 모든 블록 변경과 그 이웃 여섯 칸, 그리고 물리
구조물이 가까이 온 청크 구역(16×16×16)의 모든 블록에 대해 실행된다.

플레이어에게는 이렇게 나타난다. 직접 확인한 것은 콘솔 경로이며, 플레이어의 설치와
실제 비행은 같은 코드를 지나지만 따로 시험하지 않았다.

- PC 등 위 블록을 직접 설치할 수 없다(마을에 생성된 것은 정상).
- 이 블록들 옆 칸에서 블록을 놓거나 부수는 동작이 서버에서 실패한다.
- 비행체 등 물리 구조물이 포켓몬센터 같은 곳에 가까이 가면 서버가 죽고, 구조물을
  지우기 전까지 재시작해도 죽는다. 마을 보정으로 시작 지점이 포켓몬센터가 있는 마을이
  되므로, JAR 수정 전에는 **마을 근처에서 Aeronautics 구조물을 만들지 않아야 한다.**

데이터만으로 피하는 방법은 찾지 못했다. 충돌 계산 앞에는 액체 여부 말고 건너뛰는 조건이
없다. 블록의 충돌 판정 자체를 없애는 방법은 기계의 성질을 바꾸므로 시험하지 않았다.

## 확인했지만 이번에 고치지 않은 것

| 항목 | 내용 | 이유 |
| --- | --- | --- |
| 포켓몬이 바닐라 동물 스폰 상한을 차지 | 야생 포켓몬이 CREATURE/WATER_CREATURE로 집계돼 오징어·돌고래 등 재스폰이 줄어듦 | 서버 전용 믹스인 JAR이 필요해 모드 구성(314개)과 시작 검사를 바꿔야 함. 별도 단계로 제안 |
| End 전용 Pixelmon 콘텐츠 | Society는 End를 없앴다. Iron Moth, Iron Thorns, Slither Wing, Walking Wake, Iron Leaves와 End 굴·그로토에 도달할 수 없음 | 어디에 옮길지는 콘텐츠 결정. 제안된 데이터 수정은 검증에서 동작하지 않는 것으로 판정 |
| Every Compat의 Pixelmon 목재 블록 144개 | 자동 등록됨 | 레지스트리를 바꾸는 설정이라 서버·클라이언트 동시 변경 필요. 게임 진행에 영향 없음 |
| ServerCore 활성 범위 | 16블록 밖 포켓몬 틱이 줄어 전설 타이머가 늘어남 | N100 부하를 위한 Society 설정의 절충. 그대로 둠 |
| Pixelmon 템플릿의 미등록 블록 3개·오타 풀 | 공기 한 칸, 장식 누락 | Pixelmon 상위 문제, 영향 미미 |
| Sable 전역 상세 로그, 서버의 클라이언트 클래스 참조 오류 | 로그 잡음 | 동작 영향 없음 |
| 전수 조립 검사의 한계 | 위 Pixelmon 다중 블록 92종은 설치 자체가 실패해 검사되지 않았고(`error` 94건 중 92건), 표시 아이템을 넣을 방법을 찾지 못한 블록 엔티티 2,319개도 대부분 인벤토리가 없는 블록이지만 전부 그렇다고 증명하지는 못함 | Pixelmon 쪽은 `onRemove` 재정의 10개를 모두 디컴파일해 복제 장치·화석 전시대·인퓨저를 태그에 넣음. 나머지는 포팅 JAR 수정으로 유형 자체를 없애는 것이 맞음 |

## 다음 단계 제안

이번 단계는 모드 JAR를 건드리지 않는 범위로 한정했다. 아래는 그 범위를 넘는 항목이다.

1. **포팅 JAR 수정** — 공통 JAR이 바뀌므로 서버 후보와 플레이어 팩을 함께 다시 만들어야 한다.
   - `RapierVoxelColliderBakery.buildPhysicsDataForBlock`가 충돌 모양을 묻기 전에 블록 상태를
     넣고, 다른 모드 블록의 모양 계산이 예외를 내면 꽉 찬 블록으로 처리한다. 상태만 넣어서는
     부족하다. Pixelmon 다중 블록의 위 칸은 아래 칸을 찾아 읽는데 가짜 월드의 이웃은 공기다.
   - `RedstoneContactBlockMixin.getTicker`가 `IBE.super.getTicker(...)` 대신 Create의 같은
     본문(`new SmartBlockEntityTicker<>()`)을 직접 반환하게 한다. 포팅본의 블록 엔티티는
     `SmartBlockEntity`를 상속하므로 동작은 같다. 반영하면 임시 차단 스크립트를 지운다.
     staging 전제조건이 현재 믹신 클래스의 해시를 고정하고 있어, JAR이 바뀌면 차단을 지우기
     전까지 staging이 멈춘다.
   - `SubLevelAssemblyHelper.moveBlocks`가 Create의 구조물 조립처럼 모든 블록에서 원래
     블록 엔티티를 먼저 떼어 내게 한다. 그러면 복제가 태그 목록과 무관하게 사라진다.
     현재 태그는 이 팩의 모드 구성에서 실측한 목록이라, 내용물을 넣어 볼 수 없었던
     블록(아래 한계)은 증명되지 않았다.
2. **야생 포켓몬의 스폰 상한 분리** — 서버 전용 믹스인 JAR이 필요하다(서버 모드 수 314 → 315).
3. **End 전용 Pixelmon 콘텐츠의 위치** — 콘텐츠 결정이 필요하다.

## 검증

| 검사 (실제 게임, 새 월드) | 수정 전 | 수정 후 |
| --- | --- | --- |
| 포팅 레시피·올가미·물리 태그 12개에 기대한 항목이 있음 | 1/12 | 12/12 |
| 제작 격자 19개의 결과물 | 9/19 | 19/19 |
| 은 광석 제련·용광로 6개 | 4/6 | 6/6 |
| 전리품 표 12개 추첨에서 기대 아이템·네임스페이스 | 0/12 | 12/12 |
| 네더 요새 상자 600회 중 rib 장식 | 0/600 | 34/600 |
| 바스티온 보물 상자의 Pixelmon 전리품 | 없음 | 있음 |
| `pixelmon:dens` 구조물 종류 | 13 | 15 |
| 페어리 체육관 표본 3곳의 NPC 조각 | 0/0/0 | 8/8/8 |
| 다이아 6개를 넣은 블록의 물리 조립 (땅에 떨어진 묶음 수·옮겨진 블록 안 개수) | basic_shipping_bin 떨어짐 1·블록 안 6, artisan_hopper 떨어짐 1·블록 안 6 | basic_shipping_bin 떨어짐 0·블록 안 6, artisan_hopper 떨어짐 0·블록 안 6 |
| 블록 엔티티 블록 전수 물리 조립 | 4181개 중 복제 306, 사라짐 0 | 4181개 중 복제 0, 사라짐 0 |
| 아이템 사용 요청(가짜 플레이어) | redstone_contact 허용, cobblestone 허용 | redstone_contact 거부, cobblestone 허용 |
| Radium이 설정으로 끈 옵션 수 | 1 | 5 |
| KubeJS 서버 스크립트 오류 | 0 | 0 |

수정 후 실행에서 실패한 검사는 없다. 기록:
[수정 전](../evidence/village-worldgen-baseline.json),
[수정 후](../evidence/village-worldgen-fixed.json),
전수 조립 [수정 전](../evidence/assembly-inventory-sweep-baseline.json)·[수정 후](../evidence/assembly-inventory-sweep-fixed.json),
[레드스톤 접점 서버 중단](../evidence/redstone-contact-server-crash.json).
Miltank 우유 교환은 플레이어 상호작용이 필요해 게임에서 실행하지 못했다. 스크립트는 팩의
Rhino 엔진과 대역 객체로만 검증했다. Python 검사는 152개가 통과한다(고정 입력이 없으면 6개 생략).

## 재현

```bash
python3 tools/stage_forge_candidate.py --server-pack … --pixelmon … --port … --datapack-fix … \
  --coexistence-fix /path/to/libraries/net/minecraft/server/1.20.1-20230612.114412/server-1.20.1-20230612.114412-extra.jar \
  --destination /path/to/fresh-profile --mode player
python3 tools/run_village_probe.py --source /path/to/fresh-profile --destination /path/to/disposable \
  --libraries /path/to/forge-libraries --java /path/to/jdk-17/bin/java --output result.json --accept-eula
python3 -m unittest discover -s tests -p 'test_*.py'
```
