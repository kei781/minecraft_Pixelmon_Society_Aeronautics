# Pixelmon PC가 접속 뒤 갱신되지 않는 문제

2026-11-14 운영 서버에서 다음 증상이 보고됐다.

1. 파티가 여섯 마리로 찬 상태에서 포켓몬 B를 잡으면 PC로 보냈다는 안내가 나온다.
2. PC를 열면 B가 없다.
3. 그 상태에서 파티의 포켓몬 A를 PC에 넣으면 A가 파티와 PC 양쪽에 보인다.

## 원인

Pixelmon 9.2.3 자체의 접속 순서 문제다. 이 저장소의 보정이나 다른 모드는 PC·파티 동기화 코드를
건드리지 않는다(모든 JAR의 믹신 대상과 상수 풀을 조사).

- 접속할 때 `PixelmonStorageManager.onPlayerLogin`(우선순위 HIGHEST)이 PC 전체를 보내고,
  그 뒤 `PixelmonPlayerTracker.onPlayerLogin`(HIGH)이 `ServerConfigListPacket`을 보낸다.
- 클라이언트는 `ServerConfigListPacket`을 받으면 `ClientStorageManager.load()`를 불러 알고 있던 PC
  목록을 비운다. PC가 먼저 도착했으면 방금 받은 PC가 목록에서 사라지고, PC는 다시 오지 않는다.
  PC 파일 읽기가 설정 패킷보다 늦게 끝난 접속에서는 순서가 맞아 문제가 없다. 접속마다 다르다.
- 목록에 없는 PC에 대한 변경 패킷(`ClientSetPacket`)은 클라이언트가 버린다. 클라이언트 로그에
  `No storage on the client side with UUID` 줄이 남는다. PC 화면은 접속 때 받은 내용을 계속 그린다.
- 그래서 서버 PC에 들어간 B가 화면에 없다. 빈칸처럼 보이는 그 자리에 A를 넣으면 클라이언트는 자기
  화면에서 먼저 옮기고, 서버는 그 자리에 B가 있으므로 거부하고 두 자리의 실제 내용을 다시 보낸다.
  파티 쪽은 적용되고 PC 쪽은 버려져 A가 두 곳에 보인다.

**서버에는 복제가 생기지 않는다.** 서버는 옮기기·놓아주기 요청마다 그 자리의 포켓몬 UUID를
확인한다. 증상이 보고된 날 운영 서버의 저장 파일에서 네 명의 파티와 PC 전체를 읽어, 같은 UUID나
같은 개체값·성격·성별·크기·종을 가진 포켓몬이 없고 파티가 찼을 때 잡은 포켓몬이 서버 PC에 들어가
있음을 확인했다. 화면의 사본은 게임을 완전히 종료했다 다시 켜면 사라진다. 서버 연결만 끊었다
다시 접속하면 예전 PC 화면이 남을 수 있다.

## 수정

`PixelmonPcResyncMixin`은 `PixelmonPlayerTracker.onPlayerLogin`이 끝난 자리에서 그 플레이어의 PC를
한 번 더 보낸다. 설정 패킷 뒤에 도착하므로 클라이언트 목록에 PC가 다시 들어가고, PC를 열 때 그
내용으로 바뀐다. Pixelmon의 저장소·파티·패킷 내용은 바꾸지 않는다. 접속마다 PC 내용이 한 번 더
전송된다(포켓몬이 들어 있는 칸마다 패킷 하나). 다시 보내는 중에 예외가 나면 경고만 남기고 접속은
그대로 진행한다. 다시 보낼 때마다 서버 `logs/debug.log`에 `PC sent again after login: <이름>` 줄을
남긴다.

서버에서만 동작하는 코드지만 공통 JAR에 넣었다. 싱글플레이 월드도 같은 순서 문제를 가지기 때문이다.
멀티플레이는 서버의 공통 JAR만 바뀌어도 고쳐진다.

Pixelmon을 올리는 방법은 쓰지 않았다. 9.2.4~9.2.6 변경 내역에서 이 문제를 고쳤다는 항목을 찾지
못했다(웹 검색 요약 기준, 원문 대조는 못 함).

## 빌드

[포팅 수정](coexistence-audit.md#포팅-jar-수정)까지 반영한 공통 JAR(`28e19585…`)에 클래스 하나와 믹신
설정을 더한다. 나머지 4,185개 항목은 바이트 단위로 그대로다. 두 작업 트리의 빌드 결과가 같았다.
입력·소스·클래스 해시는 [`compat/pc-resync-build.json`](../compat/pc-resync-build.json)에 고정했고,
결과 공통 JAR의 SHA256은 `814b13eb950b738d17526b50dc5e19bb6454c486be05b012cd4b78182a98fee3`다.

```sh
gradle --offline --no-daemon --max-workers=2 -p /path/to/prepared-port-workspace \
  -I /path/to/repository/tools/forge-pc-resync.gradle \
  -PpsaPcResyncSource=/path/to/repository/compat/forge-port \
  -PpsaPixelmonJar=/path/to/Pixelmon-1.20.1-9.2.3-universal.jar \
  reobfPsaPcResyncJar
python3 tools/forge_resources.py canonical-jar \
  /path/to/prepared-port-workspace/build/libs/psa-pc-resync-0.1.jar /path/to/psa-pc-resync-canonical.jar
python3 tools/forge_pcsync_compat.py --base /path/to/port-fixed-common.jar \
  --tested-patch /path/to/psa-pc-resync-canonical.jar --output /path/to/new-common.jar
```

## 검증 구분

- **코드 추적**: 위 원인은 Pixelmon 9.2.3과 Forge 47.4.20의 바이트코드를 읽어 정리했고, 두 번째
  검토자가 결정적인 메서드를 다시 읽어 첫 설명의 빠진 부분(설정 패킷이 PC 목록을 비우는 호출)을
  찾았다. 게임에서 재현하지는 않았다.
- **서버 쪽 실행**: 준비한 프로필의 일회용 서버에서 Pixelmon의 접속 처리 메서드를 대역 플레이어로
  실행했다. 메서드가 끝까지 실행됐고 새 클래스가 그 플레이어의 PC를 다시 보낸 기록을 남겼다. 접속
  이벤트 자체는 보내지 않았으므로 그 플레이어의 PC를 요청한 것은 새 클래스뿐이다. 이 검사는 전체
  게임 검사에 들어 있다(`pc_resend`).
- **확인하지 않은 것**: 실제 클라이언트의 접속, 다시 보낸 PC를 클라이언트가 받아 화면이 맞게 되는 것,
  증상이 사라지는 것. 접속한 플레이어의 클라이언트 로그에 `No storage on the client side` 줄이 더
  생기지 않는지 보면 확인된다. 이전 공통 JAR을 쓰는 v20 클라이언트가 새 공통 JAR의 서버에 접속하는
  것도 실행해 보지 않았다(모드 ID·버전·레지스트리는 같다).

[조사·검증 기록](../evidence/pixelmon-pc-resync.json).

## 같이 발견한 것 (고치지 않음)

- `ServerSwapPacket`은 요청을 거부할 때 두 번째 자리의 내용을 잘못된 저장소(파티)에서 읽어 보낸다.
  `PartyStorage.get`의 범위 검사도 한 칸 어긋나 있다. 클라이언트와 서버의 PC가 어긋난 경우에만
  드러나고, 서버 저장소는 바꾸지 않는다.
