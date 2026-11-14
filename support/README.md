# PSA Discord 문의 봇

지정한 Discord 서버의 텍스트 채널 하나에서 한국어 문의를 받고, 운영 합팩 자료로 답변한다.
버그 의심 건은 SQLite에 PSA-0001 형식으로 접수하며, 운영자가 남긴 처리 결과를 같은 채널에 알린다.
일반 대화 문의 방식이므로 Developer Portal에서 **Message Content Intent**가 필요하다.

## 권한과 동작

- 서버 ID + 채널 ID를 AI 호출·내용 읽기·저장 전에 비교한다. DM, 다른 채널, 하위 스레드,
  다른 봇과 웹훅은 처리하지 않는다. Discord 역할도 해당 채널에만 View/Send/Read History를 허용한다.
- 게임 서버 명령, SSH, RCON, 아이템/포켓몬 지급, 순간이동, 인벤토리 수정 도구는 없다.
  Codex의 셸·브라우저·앱·플러그인·하위 에이전트 도구를 끄고 read-only 샌드박스로 실행한다.
  모델 출력에 도구 동작이 나타나면 답변을 거부하며, 응답은 구조화된 답변/분류 데이터로만 소비한다.
- 배포 서비스는 별도 Linux 계정으로 실행하고 `/home` 접근을 차단한다. Minecraft 프로세스와
  별도 서비스다. 야간 작업은 운영자가 제어하는 Codex 작업이며 Discord 봇에 개발 권한을 주지 않는다.
- 사용자 보고만으로 확정 버그라 하지 않는다. `suspected_bug`는 재현/조사 대기다.
- 버그가 아닌 질문에도 정상 진행 방법을 안내한다. 근거 없는 레시피는 확인 질문으로 바꾼다.
- 같은 스냅샷의 **정확히 같은 제목**만 중복 접수한다. 유사한 제목은 야간 조사에서 비교한다.
- 유저별 최근 6시간/4건의 자기 문의만 이어받는다. 일반 문의 기록은 다음 문의 처리 시 7일 경과분을 정리한다.
  티켓에 연결된 문의는 보존한다. `/새문의` 명령이나 첨부 이미지 분석은 아직 제공하지 않는다.
- 입력 3,000자, 기본 동시 2건, 유저당 20초 간격, 한국 날짜 기준 하루 200건이다.
  각 문의는 검색 계획과 답변의 Codex 호출 2회다. ChatGPT 구독의 Codex 사용량을 개인 작업과 공유한다.
  API 키나 별도 API 과금 경로는 사용하지 않는다. 로그인/사용량 제한 시 오류를 안내하며 유료 API로 전환하지 않는다.
- 전송 대기 답변은 DB에 저장하고 재시작 후 재전송한다. Discord 전송 성공 직후 DB 기록 전에
  프로세스가 종료되면 동일 답변이 중복될 수 있다. 티켓은 메시지 ID로 중복 생성하지 않는다.
- API 오류 시 접수 완료로 표시하지 않는다. 실행 로그에 질문/예외 본문/토큰은 기록하지 않는다.

## 자료 구성

`snapshot` 명령은 운영자가 실행한다. `kubejs` 레시피/데이터, FTB Quests, 게임 안내서와
관리자가 작성한 조사 메모를 청크와 출처로 저장하고, 모드 JAR의 SHA256을 배포 식별자로 기록한다.
월드, 플레이어 데이터, 서버 로그, `server.properties`, 임의 설정 파일은 읽지 않는다.
이 자료는 **정적 합팩 스냅샷**이다. 현재 NPC 좌표나 실시간 서버 장애를 확인한 것으로 답하지 않는다.
기본 모드 JAR 안에만 있는 자료, 일부 동적 동작은 검색 대상이 아니다. 그런 문의는 확인 질문 또는
조사 티켓으로 남기고 야간 담당자가 실제 로그/코드를 조사한다. 합팩 변경 후 다시 추출하고 봇을 재시작한다.

```sh
uv sync --frozen
uv run psa-support snapshot --server /path/to/active/server --notes knowledge --output state/knowledge.json
cp config.example.json config.json
# config.json: 서버/채널 ID, 모델과 파일 경로를 설정한다.
# DISCORD_BOT_TOKEN만 비공개 환경변수로 제공한다. Codex는 ChatGPT로 로그인한다.
uv run psa-support --config config.json check
uv run psa-support --config config.json run
```

기본 제안 모델은 `gpt-6.1-sol`; ChatGPT 구독에서 사용 가능한 Codex 모델로 설정 가능하다.
공식 Codex CLI 0.164.0을 사용하며 `codex login --device-auth`로 직접 로그인한다.
OAuth 토큰을 앱 코드가 읽거나 API에 대신 전달하지 않는다. Codex가 로그인 갱신을 관리한다.
`codex_home`은 봇 전용 `/var/lib/psa-support/codex-auth`이며 다른 사용자의 인증 파일을 복사하지 않는다.
운영 비밀 값은 `/etc/psa-support.env`에 root 소유 0600으로 저장한다.
`config.json`, `.env`, `state/`, DB와 실제 서버 스냅샷은 Git에 넣지 않는다.

## N100 설치

`deploy/install.sh`는 봇 코드, 고정 의존성과 서비스 정의를 설치한다. 실행하거나 자동 시작을 활성화하지 않는다.
루트로 기존 설치를 교체하기 전에 실행 중인 서비스는 중지해야 한다. 게임 서버는 건드리지 않는다.
설정 `/etc/psa-support.json`의 database는 `/var/lib/psa-support/support.db`, knowledge는
`/opt/psa-support/knowledge.json`으로 설정한다. JSON 파일은 root:psa-support 0640이다.
관리자가 생성한 스냅샷을 `/opt/psa-support/knowledge.json`에 root:psa-support 0640으로 설치한다.
환경 파일에 `DISCORD_BOT_TOKEN=...` 한 줄을 넣고 root:root 0600으로 저장한다.
ChatGPT 로그인은 다음 명령에서 표시한 기기 인증 화면으로 완료한다.

```sh
sudo -u psa-support env CODEX_HOME=/var/lib/psa-support/codex-auth /opt/psa-support/bin/codex login --device-auth
```

Discord 새 전용 봇을 생성하고 초대할 때 Administrator 권한은 주지 않는다.
서버 전체의 View Channel을 끄고 지정 채널에 View Channel, Send Messages, Read Message History만 허용한다.
Message Content Intent를 켠다. 서버/채널 ID를 입력하고 `check` 및 실제 채널 확인을 마친 뒤:

```sh
sudo systemctl enable --now psa-support
sudo systemctl status psa-support --no-pager
```

## 새벽 4시 작업

Codex 앱 자동화에서 매일 **Asia/Seoul 04:00**에 이 대화의 작업을 이어간다.
스케줄 등록은 앱의 automation 도구로 수행하며 서버 crontab을 중복 생성하지 않는다.
Mac의 Codex가 작업을 실행할 수 있는 상태여야 한다. N100 봇은 독립 실행된다.
야간 절차는 `nightly-runbook.md`에 있다. 자동화 등록 전에는 접수 문구의 4시 처리를 활성 서비스로 보장하지 않는다.

운영자만 다음 CLI를 실행한다. Discord에는 상태 변경 명령을 노출하지 않는다.

```sh
sudo -u psa-support /opt/psa-support/.venv/bin/psa-support --config /etc/psa-support.json tickets
# result.json = {"summary":"플레이어에게 공개할 결과", "evidence":"비공개 검증 증거/경로"}
sudo -u psa-support /opt/psa-support/.venv/bin/psa-support --config /etc/psa-support.json update 1 \
  --status needs_information --result-file /var/lib/psa-support/result.json
```

`resolved`는 실제 검증 및 필요한 운영 반영을 완료했을 때만 사용한다. 수정안만 준비된 경우 `investigating`으로 유지한다.
결과의 summary만 Discord로 전송하고 evidence는 DB에 보관한다. 봇 토큰이 없으면 시작하지 않으며, Codex 로그인이 없으면 문의 처리가 실패한다.
실제 Discord/Codex 연결 전에는 로컬 단위 검증을 운영 성공으로 표현하지 않는다.

## 검증

```sh
uv run python -m unittest discover -s tests -v
```

채널/DM 필터, 잘못된 설정 차단, 재시작 시 티켓/전송 대기 보존, 버전별 중복 접수,
사용자별 문맥 분리, 입력/동시성 제한, 증거 없는 해결 처리 차단, 잘못된 AI 출처 거부를 검증한다.
모의 AI/Discord 테스트는 실제 Codex 응답 품질이나 Discord 수신 검증을 대신하지 않는다.
