# N100 통합 서버 운영

서버는 기존 데이터와 분리한 새 전용 폴더에 준비한다. 런타임과 라이브러리도 그 안에 설치하며 시스템 Java·기존 서비스·월드를 바꾸지 않는다. 실제 접속 주소와 SSH 설정은 공개 저장소에 포함하지 않는다.

## 구성

- N100 / Ubuntu / RAM 16 GB, 최대 6명.
- Java 17.0.21.0.11 Amazon Corretto / Forge 47.4.20 / Minecraft 1.20.1.
- Society 4.1.5A 서버 원본 JAR 311개 + Pixelmon + Aeronautics 포팅 JAR = 313개.
- 최대 힙 6 GB, view/simulation distance 4. 실제 6인 부하에 맞춘 최종 튜닝은 아직 아니다.
- 온라인 인증 사용. 게임 포트 25573. 물리 이동의 잘못된 비행 판정으로 인한 추방을 피하도록 `allow-flight=true`를 사용한다. 일반 플레이어에게 크리에이티브 비행 권한을 주는 설정은 아니다.

## 시작·정지·상태

해당 서버 폴더에서 실행한다. Python 3, Bash, tmux, sha256sum이 필요하다. 실제 장비에는 준비돼 있었다.

```bash
bash server-control.sh start
bash server-control.sh status
bash server-control.sh command "forge tps"
bash server-control.sh stop
```

처음 시작할 때 운영자가 Minecraft EULA를 읽고 동의한 경우에만 `start --accept-eula`를 쓴다. staging은 `eula=false`를 만들고, 설치기는 동의하지 않는다.

전용 tmux 소켓을 사용하며 일반 tmux 세션을 건드리지 않는다. 시작할 때 모드 313개의 SHA256·수량·온라인 인증을 확인한다. 정지는 콘솔 `stop`을 보내고 최대 120초 기다린다. 시간 초과 시 강제 종료하지 않고 로그 확인을 요구한다. 재시작 전에는 `stop` 완료를 확인한다.

실제 시작 완료는 `console.log`의 새 `Done` 줄로 확인한다. `status`의 Running은 tmux 프로세스 상태다. SSH 연결을 닫아도 실행이 유지된다. OS 재부팅 후 자동 시작 서비스는 등록하지 않았으므로 위 시작 명령을 다시 실행한다.

## 새 장비에 준비하는 개발 절차

저장소 루트에서 검증한 입력으로 접속용 새 프로필을 만든다. `--mode player`는 `server-ip=0.0.0.0`, `level-name=world`를 설정한다. 생략하거나 `--mode smoke`를 쓰면 `127.0.0.1`과 별도 시험 월드 `world-psa-new`를 사용한다. 두 모드 모두 온라인 인증을 사용하고 EULA는 동의 전 상태다.

```bash
python3 tools/stage_forge_candidate.py \
  --server-pack /path/to/SERVER-PACK-Society-Sunlit-Valley-4.1.5A.zip \
  --pixelmon /path/to/Pixelmon-1.20.1-9.2.3-universal.jar \
  --port /path/to/verified-canonical-port.jar \
  --destination /path/to/new-player-profile --mode player
```

`server-control.sh`, `.psa-mods.sha256`, 두 소유/구성 마커가 있는지 확인한다. Linux x64 장비의 전용 폴더로 프로필을 옮기고, `tools/install_forge_runtime.py`와 `forge-runtime-lock.json`도 상대 경로를 유지해 복사한 뒤 해당 프로필 폴더에서 실행한다.

```bash
python3 tools/install_forge_runtime.py --profile . --lock forge-runtime-lock.json
```

설치 도구는 공식 Java·Forge 파일을 고정 해시·크기로 확인한다. 검증한 캐시가 있으면 재사용한다. Temurin 배포 URL의 504 오류 때문에 이 장비에는 공식 Corretto 17로 공급자를 변경해 고정했다. 설치 아카이브도 시스템 밖의 전용 캐시에 보존한다. 기존 캐시가 손상됐으면 덮어쓰지 않고 중단한다.

이미 만든 시험 프로필을 접속용으로 전환하려면 정상 `stop` 완료 후 `server.properties`의 `server-ip=0.0.0.0`, `level-name=world`, `allow-flight=true`, `online-mode=true`, `max-players=6`을 확인하고 다시 시작한다. 시험용 `world-psa-new`는 보존하며 월드를 삭제하거나 덮어쓰지 않는다. 실제 장비는 이 전환 후 별도 `world`에서 실행 중이다. 원격 인터넷 회선의 공유기 포트 전달은 별도 네트워크 조건이며, 현재 직접 상태 핑 성공을 인터넷 공개 접속 성공으로 간주하지 않는다.

## 확인 범위

실제 장비에서 전체 기동, KubeJS startup 97/97·server 188/188 오류 0, 퀘스트 1,142개, 5종 일반 몹 유지, 포켓몬 생성 명령, 필수 물리 태그와 한 블록 구조물 조립을 확인했다. 정상 저장·정지·재시작 후 몹과 구조물도 복구했다.

5종 시험 몹과 구조물 하나, 인증 접속자 0명 상태에서 TPS 20, 전체 평균 tick 2.963 ms, RSS 약 5.17 GiB였다. 실제 6인 성능으로 환산하지 않는다. Windows 인증 접속·포획/전투·Society 진행·조종 비행·6인 부하는 별도 검증이 필요하다.
