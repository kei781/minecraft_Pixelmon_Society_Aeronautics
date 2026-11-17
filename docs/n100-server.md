# N100 통합 서버 운영

**현재 운영(2026-11-14): v20 프로필, 모드 314개.** 공통 JAR
`d597065c5fef2abaec1bb01c616a5c5dc0787f672b5428693f23e696c37d23e4`([포팅 결함 수정](coexistence-audit.md#포팅-jar-수정)과
[접속 뒤 PC 다시 보내기](pixelmon-pc-resync.md) 포함, 2026-11-14 10:21 UTC 교체, [기록](../evidence/n100-v20-pc-resync-deployment.json)),
[공존 보정](coexistence-audit.md) 포함. 월드는 2026-11-14 03:04 UTC에 운영자가 새로 만든 것이다. 플레이어는 v20 또는 v21 팩이 필요하다(v20의 공통 JAR에는 서버에서만 동작하는 PC 다시 보내기 클래스가 없을 뿐이다. 교체 뒤 v20 팩으로 접속되는 것을 확인했다). 이전 v17은 정상 정지했고
월드는 그 폴더에 그대로 있다. [반영 기록](../evidence/n100-v20-fresh-world-deployment.json).
아래 v16·v17 문단은 그 이전의 이력이다.

서버는 기존 데이터와 분리한 새 전용 폴더에 준비한다. 런타임과 라이브러리도 그 안에 설치하며 시스템 Java·기존 서비스·월드를 바꾸지 않는다. 실제 접속 주소와 SSH 설정은 공개 저장소에 포함하지 않는다.

v16 접속용 서버는 2026-11-09 17:39:17 UTC에 스타터 선택 대기자의 로그아웃으로
종료됐다. 원본 월드·로그·설정은 정지 상태에서 백업해 보존했다. 전체 QA 대조와
실제 인증 접속·로그아웃을 각 2회 확인하고 정상 저장·종료했다. 독립 리뷰 수락 뒤
2026-11-10 01:34:45 UTC에 진단 없는 v17 접속용 서버의 기동 완료를 확인했다.
원본 월드의 복사본·독립 런타임과 운영 모드 313개를 사용한다. 같은 v17 클라이언트로
실제 인증·월드 입장·1명 접속, TPS 20·전체 평균 틱 7.725ms·크래시 0개를 확인했다.
[원인·수정](pixelmon-starter-disconnect.md), [새 배치 증거](../evidence/n100-v17-player-deployment.json).
ALI 클라이언트 오류는 Task17에서 수정·독립 리뷰를 수락했다. Task18은 전체 데이터팩
갱신 보정을 더한 314개 모드의 새 서버 후보를 준비했고, 별도 QA에서 실제 데이터
변경·복원과 정상 저장·종료까지 확인했다. [갱신 복구 범위](datapack-reload-recovery.md).
새 후보의 독립 리뷰는 수락했고 N100의 새 준비 경로에 해시 검증한 314개 모드와 독립
런타임을 전송했다. 준비 프로필은 정지 상태이며 운영 월드를 복사하지 않았다.
운영 교체, ReliableEmi 표시 오류와 새 Windows 가져오기·직접 LAN
연결·실제 6인 부하는 미완료다. 현재 운영 v17은 계속 실행 중이다.

## 구성

- N100 / Ubuntu / RAM 16 GB, 최대 6명.
- Java 17.0.21.0.11 Amazon Corretto / Forge 47.4.20 / Minecraft 1.20.1.
- Society 4.1.5A 서버 원본 JAR 311개 + Pixelmon + Aeronautics 포팅 JAR = 313개.
- 최대 힙 6 GB, view/simulation distance 4. 실제 6인 부하에 맞춘 최종 튜닝은 아직 아니다.
- v17 공통 JAR SHA256: `351ecb0905a7f05a262a9401fe0e968402896f527e5983838ef2014641e3a3db`. [스타터 로그아웃 보정](pixelmon-starter-disconnect.md). 기존 누케닌 HP 보정도 유지한다.
- 온라인 인증 사용. 게임 포트 25573. 물리 이동의 잘못된 비행 판정으로 인한 추방을 피하도록 `allow-flight=true`를 사용한다. 일반 플레이어에게 크리에이티브 비행 권한을 주는 설정은 아니다.

## 시작·정지·상태

해당 서버 폴더에서 실행한다. Python 3, Bash, tmux, sha256sum, flock이 필요하다. 실제 장비에는 준비돼 있었다.

```bash
bash server-control.sh start
bash server-control.sh status
bash server-control.sh command "forge tps"
bash server-control.sh stop
```

처음 시작할 때 운영자가 Minecraft EULA를 읽고 동의한 경우에만 `start --accept-eula`를 쓴다. staging은 `eula=false`를 만들고, 설치기는 동의하지 않는다.

전용 tmux 소켓을 사용하며 일반 tmux 세션을 건드리지 않는다. 시작 작업은 프로필별 파일 잠금으로 직렬화하므로 동시 호출이 실행 중인 로그를 옮기지 않는다. 잠금은 Java·tmux에 상속하지 않는다. 시작할 때 모드의 SHA256·수량·온라인 인증을 확인한다. 기존 구성은 313개이며, 정확한 추가 서버 보정·원본·프로필 선언을 확인한 새 구성만 314개를 허용한다. 정지는 콘솔 `stop`을 보내고 최대 120초 기다린다. 시간 초과 시 강제 종료하지 않고 로그 확인을 요구한다. 재시작 전에는 `stop` 완료를 확인한다.

실제 시작 완료는 `console.log`의 새 `Done` 줄로 확인한다. `status`의 Running은 tmux 프로세스 상태다. SSH 연결을 닫아도 실행이 유지된다. OS 재부팅 후 자동 시작 서비스는 등록하지 않았으므로 위 시작 명령을 다시 실행한다.

## 새 장비에 준비하는 개발 절차

저장소 루트에서 검증한 입력으로 접속용 새 프로필을 만든다. `--mode player`는 `server-ip=0.0.0.0`, `level-name=world`를 설정한다. 생략하거나 `--mode smoke`를 쓰면 `127.0.0.1`과 별도 시험 월드 `world-psa-new`를 사용한다. 두 모드 모두 온라인 인증을 사용하고 EULA는 동의 전 상태다.

```bash
python3 tools/stage_forge_candidate.py \
  --server-pack /path/to/SERVER-PACK-Society-Sunlit-Valley-4.1.5A.zip \
  --pixelmon /path/to/Pixelmon-1.20.1-9.2.3-universal.jar \
  --port /path/to/verified-canonical-port.jar \
  --datapack-fix /path/to/PSA-Datapack-Sync-Compat-0.1.jar \
  --destination /path/to/new-player-profile --mode player
```

`--port`에는 현재 공통 JAR(`d597065c…`)을 준다. [포팅 결함 두 건](coexistence-audit.md#포팅-jar-수정)과 [접속 뒤 PC 다시 보내기](pixelmon-pc-resync.md)까지 반영한 것이다.
마을·전리품·레시피·물리 조립 공존 보정([마을](village-structure-compatibility.md),
[전체 목록](coexistence-audit.md))을 함께 넣으려면 같은 명령에
`--coexistence-fix /path/to/libraries/net/minecraft/server/1.20.1-20230612.114412/server-1.20.1-20230612.114412-extra.jar`
를 더한다. 모드 JAR 구성은 그대로이고 `kubejs/` 아래 파일과 `config/lithium.properties`만
달라진다. 이미 생성된 청크의 마을은 바뀌지 않으며, 기존 월드의 시작 지점은 운영자가 콘솔에서
`psa_village_spawn apply`를 실행할 때만 옮겨진다.

`server-control.sh`, `.psa-mods.sha256`, 두 소유/구성 마커가 있는지 확인한다. Linux x64 장비의 전용 폴더로 프로필을 옮기고, `tools/install_forge_runtime.py`와 `forge-runtime-lock.json`도 상대 경로를 유지해 복사한 뒤 해당 프로필 폴더에서 실행한다.

```bash
python3 tools/install_forge_runtime.py --profile . --lock forge-runtime-lock.json
```

같은 프로필에서 설치기를 다시 실행할 때는 먼저 `server-control.sh stop`이 완료됐는지 확인한다. 설치기는 실행 중인 서버를 자동으로 정지하지 않는다.

설치 도구는 공식 Java·Forge 파일을 고정 해시·크기로 확인한다. 검증한 캐시가 있으면 재사용한다. Temurin 배포 URL의 504 오류 때문에 이 장비에는 공식 Corretto 17로 공급자를 변경해 고정했다. 설치 아카이브도 시스템 밖의 전용 캐시에 보존한다. 기존 캐시가 손상됐으면 덮어쓰지 않고 중단한다.

이미 만든 시험 프로필을 접속용으로 전환하려면 정상 `stop` 완료 후 `server.properties`의 `server-ip=0.0.0.0`, `level-name=world`, `allow-flight=true`, `online-mode=true`, `max-players=6`을 확인하고 다시 시작한다. 시험용 `world-psa-new`는 보존하며 월드를 삭제하거나 덮어쓰지 않는다. 초기 배치에서는 이 전환 후 별도 `world`를 사용했다. v16 원본 프로필은 장애 증거와 함께 정지해 보존한다. 원격 인터넷 회선의 공유기 포트 전달은 별도 네트워크 조건이며, 상태 핑이나 SSH 경유 접속 성공을 인터넷 공개 접속 성공으로 간주하지 않는다.

## 확인 범위

실제 장비에서 전체 기동, KubeJS startup 97/97·server 188/188 오류 0, 퀘스트 1,142개, 5종 일반 몹 유지, 포켓몬 생성 명령, 필수 물리 태그와 한 블록 구조물 조립을 확인했다. 정상 저장·정지·재시작 후 몹과 구조물도 복구했다.

초기 배치의 5종 시험 몹과 구조물 하나, 인증 접속자 0명 상태에서 TPS 20, 전체 평균 tick 2.963 ms, RSS 약 5.17 GiB였다. 이후 QA 배치에서는 인증 접속·실제 포획/전투·Society 농사/경제·수직 조종 비행을 확인했다. 최신 v17 새 Windows 설치·생존 세부 조건·수평 비행·장시간 및 6인 부하는 남아 있으며 이전 QA나 위의 1명 수치를 6인 성능으로 환산하지 않는다.


이하 기록은 이전 배치 이력이다. 렌더 QA 서버는 v12 공통 보정본 `31e38f3be687d1fa5f95570599abd3ee8e28e65506b2ac872fc3428ecd8426a5`와 Render0.8·Jade0.4를 사용했고, 2026-11-09 11:00:02 UTC(20:00:02 KST)에 부팅했다. 이 QA 월드는 정상 정지해 보존했으며, 당시 접속용 v16 서버에는 진단을 넣지 않았다. QA 공통 313개 목록 SHA256은 `ae8fb30dc8d959a4abd6b9482502cc35ca38c97381c50ff492a9cc9ce89af53e`였다. 이 QA 기록은 6인 성능 합격이 아니다. [Jade 검증](jade-sublevel-coordinates.md), [메뉴 검증](menu-data-compatibility.md).

Jade0.3의 2026-11-09 18:09:18 KST 부팅과 당시 조준·크리에이티브 비행은 이전 검사 이력이다. Jade0.4 전환의 10:28:09 UTC 부팅도 이전 이력이며 같은 월드·세대를 보존하고 관찰 파일 메타데이터만 바꿨다. 이후 Render0.8 전환에서도 운영 파일·Jade0.4·서버 설정을 유지했다. QA 기본값은 `gamemode=survival`, `force-gamemode=false`로 고쳤으며 실제 재접속에서도 서바이벌·자체 비행 해제를 확인했다. 인증·OP·RCON 설정은 변경하지 않았다.

2026-11-09 00:12 KST 기준 v6 셰이더 패킷 보정을 배치했다. 기존 월드를 정상 저장·백업하고 포팅 JAR 하나 및 검증 기록만 갱신했다. 모드 313개 해시가 일치하고 Done·온라인 인증·0/6명·TPS20·평균1.251ms를 확인했다. 이전 v5의 지정 Windows 장치 인증 접속은 확인했지만, v6 Windows 재접속과 실제 게임 검증은 아직이다. 플레이어는 v6 팩을 사용한다. [배치 증거](../evidence/n100-v6-shader-deployment.json), [수정·독립 리뷰 범위](pixelmon-shader-compatibility.md).

클라이언트 v7는 메뉴 겹침을 고치는 클라이언트 전용 JAR 하나만 추가하므로 N100 v6의 공통 모드 313개·포팅 JAR·월드·시작 설정은 바꾸지 않는다. v6에 작은 보정 JAR를 추가하거나 v7를 새로 가져올 수 있다. [메뉴 보정 안내](pause-menu-compatibility.md).
