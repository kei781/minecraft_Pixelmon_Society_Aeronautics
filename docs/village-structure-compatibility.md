# 마을·시작 지점 공존 (Task 19)

세 프로젝트를 한 서버·한 월드에서 번갈아 즐기려면 Pixelmon의 마을 요소(포켓몬센터·
마트 등)와 Society의 마을 요소가 같은 마을에 함께 생성돼야 한다. 조사 결과 두
프로젝트가 **같은 바닐라 마을 파일을 통째로 교체**하고 있었고, 나중에 적용되는
Society(KubeJS 데이터)가 Pixelmon 것을 덮어써 일부가 사라졌다. 시작 지점도 서로의
규칙을 덮어쓰고 있었다. 이 문서는 원인·수정·검증 범위를 기록한다.

수정은 **모드 JAR를 바꾸지 않는다.** 서버의 `kubejs/` 아래 파일 8개(추가 6, 교체 2)만
바뀌며 월드 생성과 시작 지점은 서버에서만 결정되므로 **플레이어 팩 재설치 없이**
서버만 갱신해도 적용된다. Society의 원본 요소는 제거하지 않는다.

## 원인

| # | 대상 | 원인 | 실제 영향(수정 전 실측) |
| --- | --- | --- | --- |
| 1 | 평원·사바나·눈·타이가 마을의 집 풀, 사바나 길 풀 | Pixelmon JAR과 Society KubeJS가 같은 `minecraft:village/*/houses.json`·`savanna/streets.json` 5개를 모두 교체. KubeJS가 마지막에 적용돼 Pixelmon이 넣은 TCG 상점·열매 농장·사바나 배틀 아레나 항목 30개가 사라짐 | 네 종류 마을 120곳 중 TCG 상점·열매 농장 0곳, 사바나 배틀 아레나 0/30 |
| 2 | 사막 마을 중심 `desert_meeting_point_1/2.nbt` | Pixelmon은 마을 중심 템플릿에 포켓몬센터·마트 연결용 직소를 넣어 둔다. Society가 같은 두 파일을 슬라임 스포너·낚시터가 있는 자기 버전으로 교체 | 사막 마을 30곳 중 포켓몬센터 3곳(남은 중심 `_3`에서만 생성) |
| 3 | 새 월드의 시작 지점 | Pixelmon은 월드 생성 이벤트를 **취소**하고 가까운 마을을 시작점으로 잡는다. Society의 Biome Spawn Point는 취소된 이벤트도 받아(`receiveCanceled=true`) 허용 바이옴 12종 중 하나의 중심으로 다시 옮긴다 | 시작점에서 가장 가까운 마을까지 706블록(수정 전 검사 월드), 384블록(기존 월드 대조). 포켓몬센터 없는 시작 |

두 프로젝트가 함께 교체하는 데이터 파일 전체는 `tools/audit_data_overrides.py`로
조사했다. 수치는 보정 전 프로필 기준이다(보정 후에는 다시 만든 전리품 표가 더해져 달라진다).
팩 전체의 중복 2,058개 중 Pixelmon·Aeronautics 포팅이 관련된 것은 78개이며,
의도한 몹 교체 중립화 68개를 빼면 위 7개와 바스티온 전리품 3개다.
[중복 목록](../evidence/village-data-overlaps.json).

생성되는 블록·NPC 자체는 정상이다. 실제 생성된 포켓몬센터에서 회복기 2대, PC 1대(2칸),
교환기 2대(6칸)와 간호사 NPC 1명, 마트에서 상점 NPC 2명을 저장된 청크에서 확인했다.
마을 생성의 문제는 위 세 가지 덮어쓰기뿐이었다. 다만 PC·교환기 같은 여러 칸짜리 Pixelmon
블록은 이전 공통 JAR에서 Aeronautics 물리 구조물과 만나면 서버를 중단시켰다. 이 결함은
[공통 JAR 수정](coexistence-audit.md#포팅-jar-수정)으로 고쳤고, 마을 보정은 그 JAR과 함께 써야 한다.

## 수정

`tools/forge_village_compat.py`가 고정 해시의 Pixelmon JAR과 Society 원본에서 다음을
만든다. 입력 해시나 겹치는 파일 집합이 예상과 다르면 staging을 중단한다.

1. **풀 항목 복원(추가 파일 5개)** — Society의 풀 파일은 그대로 두고, Society에 이미
   포함된 Lithostitched의 `add_template_pool_elements` 수정자로 Pixelmon 고유 항목만
   원래 가중치대로 더한다. `kubejs/data/psa_village/lithostitched/worldgen_modifier/`.
2. **사막 마을 중심 2개(교체)** — Society 버전(슬라임 스포너·낚시터·낙타·집터 포함)에
   Pixelmon의 포켓몬센터·마트 직소만 추가한다. `_1`은 길 3개와 집터를 유지하고 서쪽 끝
   남북에 배치한다. `_2`는 Pixelmon 원본과 같은 배치(동쪽 길 자리에 포켓몬센터, 서쪽
   길을 남쪽으로 옮기고 마트)다. 직소 값은 Pixelmon이 남겨 둔 `_3`과 같은지 확인한다.
3. **시작 지점 스크립트(추가 1개)** — `compat/village/psa_village_spawn.js`.
   새 월드에서 Society가 고른 바이옴 위치를 기준으로, **실제 구조물 조립 결과에
   포켓몬센터가 있는** 가장 가까운 평원 마을로 월드 스폰을 옮긴다. 평원 마을만
   쓰는 이유는 Society의 시작 바이옴(온대)과 맞추기 위해서다. 찾지 못하거나 오류가
   나면 Society의 시작점을 그대로 둔다. **기존 월드는 자동으로 바꾸지 않는다**
   (게임 시간 200틱 초과 시 `existing-world-unchanged` 기록). 운영자가 원하면 콘솔에서
   `psa_village_spawn apply`로 한 번 적용할 수 있고 `psa_village_spawn status`로 확인한다.

staging은 `--coexistence-fix`로 선택한다([전체 공존 보정](coexistence-audit.md)과 함께 적용). 플레이어 팩 내보내기는 서버 프로필의 선언을
읽어 같은 바이트를 싱글플레이용 KubeJS에 넣고, 서버와 다르면 중단한다.
산출물 해시는 [`compat/village-build.json`](../compat/village-build.json)에 있다.

## 검증

`tests/forge-village-probe.js`(격리 시험 전용)는 실행 중인 게임의 `Structure.generate`로
바닐라 마을 배치 격자의 **실제 생성 위치**에서 종류별 30개씩 마을을 조립한다.
`tools/run_village_probe.py`는 그 뒤 종류별 가까운 마을 2개를 Chunky로 실제 생성·저장하고
리전 파일을 다시 읽어 조립 결과와 대조한다. 모든 실행은 루프백의 일회용 월드다.

| 마을 | 포켓몬센터 전→후 | 마트 전→후 | TCG 상점 전→후 | 열매 농장 전→후 | 배틀 아레나 전→후 |
| --- | --- | --- | --- | --- | --- |
| 사막 | 3 → 27 | 3 → 23 | 6 → 5 | 18 → 13 | 25 → 22 |
| 평원 | 26 → 24 | 25 → 25 | 0 → 10 | 0 → 21 | 18 → 20 |
| 사바나 | 27 → 24 | 28 → 25 | 0 → 7 | 0 → 17 | 0 → 20 |
| 눈 | 23 → 21 | 22 → 21 | 0 → 12 | 0 → 28 | 21 → 21 |
| 타이가 | 30 → 30 | 26 → 26 | 0 → 11 | 0 → 25 | 19 → 21 |

각 칸은 해당 건물이 하나 이상 있는 마을 수(30곳 중)다. 수정 전·후는 서로 다른 새
월드라 표본 마을이 같지 않다. Pixelmon 원래 설계에서도 길·건물 충돌로 포켓몬센터가
빠지는 마을이 있어 100%가 목표는 아니다. 수정 후 포켓몬센터·마트가 두 개씩 생긴
마을은 0곳이다. [수정 전](../evidence/village-worldgen-baseline.json),
[수정 후](../evidence/village-worldgen-fixed.json).

- 실제 생성한 10개 마을 모두 저장된 구조물 시작의 조각이 조립 결과와 일치했다.
  수정 후 사막 마을 한 곳에서 Society의 슬라임 스포너·낙타와 Pixelmon 회복기 2대,
  PC 1대, 교환기 2대, 간호사 1명, 마트 계산대·상점 NPC 2명을 **같은 마을**에서 확인했다.
  [저장된 청크 판독](../evidence/village-desert-read-back.json).
- 시작 지점: 새 월드에서 Society 시작점 (-864, -192) → 1285블록 떨어진 평원 마을로
  이동했다. `level.dat`의 스폰은 마을 중심에서 13블록이고, 그 마을의 조각에 포켓몬센터와
  간호사 NPC가 있다. 수정 전 월드의 가장 가까운 마을은
  706블록 밖이었다.
- 기존 월드 대조: 스크립트 없이 만든 월드를 수정본으로 열면 스폰이 그대로였고
  (`existing-world-unchanged`), 콘솔 `psa_village_spawn apply` 뒤에는 이미 생성돼 있던
  포켓몬센터 있는 평원 마을로 옮겨졌다. [기록](../evidence/village-start-existing-world.json).
- Python 검사: NBT 코덱 4, 마을 보정 8, 월드 읽기 3, 검사 드라이버 4, staging·내보내기 추가 2개.
  자체 NBT 코덱은 구조물 템플릿 1,492개를 바이트 단위로 왕복했고 nbtlib 결과와 대조했다.

## 사용한 도구

Lithostitched 월드젠 수정자(풀 항목 추가), Chunky(지정 영역 사전 생성), KubeJS 서버
스크립트(게임 API 직접 호출), Structure Essentials 로그, CFR(Pixelmon·Biome Spawn
Point·Lithostitched 디컴파일), 바닐라 서버 JAR의 원본 데이터, NBT/Anvil 리전 판독.

## 운영 반영과 한계

- 이미 생성된 청크의 마을은 바뀌지 않는다. 새로 생성되는 지역부터 적용된다.
  기존 사막 마을에 포켓몬센터가 필요하면 운영자가 `/place template`로 직접 놓아야 한다.
- 기존 월드의 스폰 이동은 운영자 명령으로만 한다. 침대 리스폰은 영향받지 않는다.
- 좀비 마을 중심은 Pixelmon 원본도 연결 직소가 없어 그대로다.
- 풀에 Pixelmon 건물이 더해지므로 집 자리에서 Society·바닐라 건물이 뽑힐 비율은
  그만큼 낮아진다(Pixelmon 원래 가중치 그대로).
- 실제 플레이어 접속 상태의 화면 확인, N100 운영 서버 반영은 이 단계에 포함하지 않았다.
- 시작 지점이 포켓몬센터가 있는 마을이 되므로 이전 공통 JAR과 함께 쓰면 안 된다. 그 JAR로는
  시작 마을의 Pixelmon 기계 옆에서 물리 구조물을 만들 때 서버가 중단된다(위 링크).

## 재현

```bash
python3 tools/stage_forge_candidate.py --server-pack … --pixelmon … --port /path/to/new-common.jar \
  --datapack-fix … --coexistence-fix /path/to/server-1.20.1-20230612.114412-extra.jar \
  --destination /path/to/fresh-profile --mode player
python3 tools/run_village_probe.py --source /path/to/fresh-profile \
  --destination /path/to/disposable-probe --libraries /path/to/forge-libraries \
  --java /path/to/jdk-17/bin/java --output result.json --accept-eula
python3 tools/audit_data_overrides.py --profile /path/to/profile-staged-without-coexistence-fix
python3 -m unittest discover -s tests -p 'test_*village*.py' -v
```
