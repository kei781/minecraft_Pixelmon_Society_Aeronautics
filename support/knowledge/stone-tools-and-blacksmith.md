# 돌곡괭이와 대장장이 진행 안내

검색어: 돌곡괭이 돌곡갱이 대장장이 평판 호감도 목수 초대장 stone pickaxe stone_pickaxe blacksmith carpenter invitation reputation smithing.
2026-11-15 KST에 PSA 운영 서버에서 아래 원본 파일을 직접 읽어 확인한 안내다. 원본이 변경되면 재검증한다.

돌곡괭이를 만드는 해당 레시피에는 대장장이 호감도나 평판 검사가 없다. 대장장이 작업대(smithing table)에서
틀 칸에 톱니 동전 Cog (`numismatics:cog`) 1개, 도구 칸에 나무 곡괭이, 재료 칸에 돌 도구용 재료
(`#minecraft:stone_tool_materials`, 예: 조약돌)를 넣는 강화 방식이다. 일반 제작대의 기존 레시피는 제거된다.
이 작업대 블록과 대장장이 NPC는 서로 다르다. 돌곡괭이에는 대장장이 NPC를 먼저 초대할 필요가 없다.
근거: `kubejs/server_scripts/recipes/addToolRecipes.js`의 `upgradeTool`과 `toolTypes` 반복 호출,
`kubejs/server_scripts/recipes/removeRecipes.js`의 기본 조합 제거.

목수 초대장(Carpenter Invitation)은 제작대 + 나무 도끼 + 조약돌을 모양 없는 조합으로 만든다.
목수 초대장은 `society:invitation`에 type.id=`society:carpenter`가 붙은 아이템이다.
근거: `kubejs/server_scripts/recipes/addMiscRecipes.js` 첫 번째 `shapeless` 조합.

목수의 초대장 상점에서 대장장이 초대장(Blacksmith Invitation)을 `meadow:fire_log` 4개로 교환한다.
해당 거래 항목의 ID는 `village_management_blacksmith`이며 그 항목에는 `stage_required` 조건이 없다.
근거: `kubejs/data/society_trading/shops/invitations.json`의 해당 offer/request.
Getting Started의 Starting Your Village 퀘스트는 목수 초대장을 제작하는 진행을 안내한다.
근거: `kubejs/assets/ftbquestlocalizer/lang/en_us.json`의 quest66D159252C70D5F2 설명.

대장장이 NPC가 현재 어느 좌표에 있거나 누가 어디에 초대했는지는 정적 자료로 알 수 없다.
따라서 시작 마을에 반드시 있다/없다라고 답하지 않는다. 아직 초대하지 않았다면 위 초대장 경로를 안내한다.
정적 자료만 보고 사용자의 평판이 부족하다고 단정하거나 운영자가 NPC를 소환해 주겠다고 약속하지 않는다.
