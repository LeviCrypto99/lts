# TODO

- [x] 메인 갭 박스 내 거래량 숫자(텍스트) 표시 제거
- [x] `box.new` 텍스트 인자 제거 후 수치 미표시 검증
- [x] 고정 설정 로그에 `boxVolumeText=false` 반영 및 Review 기록

- [x] 알림 정책 단순화: `저거래량 박스 첫 터치` 단일 alertcondition만 유지
- [x] 기존 FVG/완화/bull-only/bear-only alertcondition 제거
- [x] 단일 알림만 남았는지 정규식 검증 및 Review 반영

- [x] 설정 15개 요구사항 매핑(숨김 13개 + 색상 2개 노출) 확정
- [x] 숨김 대상 입력을 상수 고정값으로 치환하고 툴팁 제거
- [x] `bullCol`/`bearCol`만 입력 옵션 유지(툴팁 유지)
- [x] 고정 설정 1회 로그(`CONFIG_LOCKED`) 추가 및 Review 반영

- [x] 아이콘 유지 기준 재정의: "활성"이 아니라 "현재 차트에 박스가 시각적으로 남아있는 동안"으로 보정
- [x] FILLED 시 아이콘 삭제 제거, EXPIRED(실제 박스 삭제) 시에만 아이콘 삭제
- [x] FILLED 상태 아이콘 유지 로그 추가 및 Review 반영

- [x] MOON/SUN 아이콘이 과거에 잔존하는 원인 분석(`plotchar` 시리즈 마커 한계)
- [x] 아이콘 표시를 `plotchar`에서 박스-연동 `label` 객체 관리로 전환
- [x] 박스 비활성(완화/만료) 시 아이콘 삭제 처리 + 로그 추가 + Review 반영

- [x] 화살표 시각요소를 MOON/SUN 아이콘으로 치환
- [x] BEAR는 `🌕`(abovebar/red/normal), BULL은 `☀`(belowbar/green/normal)로 반영
- [x] Pine `plotchar` 단일 유니코드 문자 문법 근거 확인 및 Review 반영

- [x] 저거래량 터치 화살표를 BULL/BEAR 타입별 스타일로 분리
- [x] BEAR: red middle down arrow(abovebar), BULL: green middle up arrow(belowbar) 반영
- [x] 기존 박스당 1회 제한 유지 확인 및 Review 반영

- [x] `pine_script.txt` 화살표 중복 원인 점검(박스 단위 상태값 검증)
- [x] 박스당 1회 화살표를 `lowVolArrowBars` 인덱스 추적으로 강제
- [x] 상태 배열 생성/삭제 동기화 및 Review 반영

- [x] `pine_script.txt` 첫 터치 화살표 조건을 "봉 마감 후 박스 생존"으로 정밀화
- [x] `barstate.isconfirmed` + `na(fill)` 조건으로 깨진 박스 화살표 차단
- [x] 문법 근거 재확인 및 Review 반영

- [x] `pine_script.txt` 저거래량 색상 박스(BULL/BEAR) 첫 터치 요구사항 정밀 매핑
- [x] 박스별 첫 터치 상태 추적 배열 추가(`lowVolTouched`)
- [x] 첫 터치 캔들 화살표 표시 시그널/플롯 및 로그 추가
- [x] 인덱스 정합성(생성/삭제 시 배열 동기화) 점검
- [x] Review 섹션에 구현/검증/리스크 기록

- [x] 다운로드 `pine_script.txt` 사용자 표시 문자열(옵션/툴팁/알림) 현황 파악
- [x] Pine Script 공식 문서로 문자열/`input` 인자 문법 확인
- [x] 설정 수치(`defval`, `minval`, `step`) 유지한 채 영문 옵션 문자열 한글화 적용
- [x] 치환 결과 검증 및 Review 섹션 기록

- [x] AKE 케이스 최소 수정 범위 확정(과거 tracker 찌꺼기 차단 2건)
- [x] `trade_page.py` 포지션 0 리셋 시 `exit_partial_tracker` 초기화 추가
- [x] `trade_page.py` 5초 룰 평가 전 stale `exit_partial_tracker` 정리 가드 추가
- [x] 회귀 테스트 2건 추가(포지션0 리셋/오픈오더 불일치 stale clear)
- [x] 검증: 대상 테스트 + `python3 -m py_compile trade_page.py`
- [x] Review 섹션에 결과/잔여 리스크 기록
- [x] stage15 스텁 누락 필드(`_signal_loop_snapshot_cycle_seq`) 보정 및 전체 테스트 재확인

- [x] 추가 과호출 경로 점검(유저스트림 비정상/잔고 REST 중복)
- [x] `USER_STREAM_UNHEALTHY` 강제 REST 최소 간격 제한(필수 강제 호출 유지)
- [x] `/fapi/v2/balance` 공용 캐시 도입으로 동일 시점 중복 signed GET 축소
- [x] 기존 기능 영향 최소화 확인(강제 갱신/주기 갱신/명시 강제 경로 유지)
- [x] 수동 검증: `python3 -m py_compile trade_page.py`

- [x] AGENTS 규칙 재확인 및 과호출 원인-코드 경로 매핑
- [x] `signal-loop` 1틱 내 중복 강제 REST 스냅샷 억제(동작 보존)
- [x] 강제 REST 재조정 성공 조건을 "실제 REST 성공" 기준으로 보정(백오프 즉시 해제 방지)
- [x] 수동 검증: 문법 체크 + 로그 기반 동작 검토
- [x] 리뷰 섹션 업데이트

- [x] 버전/업데이트 메타데이터 구조 확인 (`config.py`, `version.json`, `build.py`)
- [x] `config.py` 버전을 `2.1.1`로 상향
- [x] `./.venv/Scripts/python.exe build.py --target all`로 런처/업데이터 재빌드
- [x] 생성 EXE SHA256 계산
- [x] `version.json`의 `min_version`, `app_url`, `app_sha256`, `updater_sha256` 동기화
- [x] SHA 재검증으로 자동업데이트 메타데이터 일치 확인

# Review (to fill after implementation)

- 구현 요약(AKE tracker stale 최소 수정): 포지션 수량 0으로 IDLE 리셋 시 `exit_partial_tracker`를 즉시 초기화하고, 5초 룰 평가 직전 현재 오픈 청산주문 집합과 tracker 주문 ID가 불일치하면 stale tracker를 선제 초기화하도록 `trade_page.py`에 가드를 추가했다.
- 검증 결과(AKE tracker stale 최소 수정):
  - 통과: `python3 -m unittest tests.test_stage15_trade_page_regression.TradePageRegressionTests.test_run_exit_supervision_clears_stale_exit_partial_tracker_before_five_second_rule`
  - 통과: `python3 -m unittest tests.test_stage15_trade_page_regression.TradePageRegressionTests.test_position_zero_reconciles_immediately_with_cancel_all`
  - 통과: `python3 -m py_compile trade_page.py`
- 잔여 리스크(AKE tracker stale 최소 수정): 단일 tracker 모델이므로 심볼 전환이 매우 빠른 구간에서 tracker 초기화 로그(`STALE_TRACKER_ORDER_MISMATCH`, `POSITION_ZERO_RESET`) 빈도를 운영 로그로 모니터링해 과초기화 여부를 확인할 필요가 있다.
- 구현 요약(stage15 스텁 보정): `tests/test_stage15_trade_page_regression.py`의 `TradePage.__new__` 기반 스텁에 `_signal_loop_snapshot_cycle_seq = 0` 초기화를 추가해 `_signal_loop_tick` 호출 경로 AttributeError를 제거했다.
- 검증 결과(stage15 스텁 보정):
  - 통과: `python3 -m unittest tests.test_stage15_trade_page_regression.TradePageRegressionTests.test_safety_lock_drops_signal_queue_immediately`
  - 통과: `python3 -m unittest tests.test_stage15_trade_page_regression` (30 tests)

- 구현 요약(과호출 안정화 2차): 유저스트림 비정상 시 강제 REST를 매틱 호출하지 않고 `ACCOUNT_REST_UNHEALTHY_FORCE_MIN_INTERVAL_SEC` 기준으로 제한했으며, `/fapi/v2/balance`는 단기 공용 캐시(`FUTURES_BALANCE_CACHE_TTL_SEC`)로 묶어 트리거/지갑/상태갱신 간 중복 조회를 줄였다.
- 검증 결과(과호출 안정화 2차): `python3 -m py_compile trade_page.py` 문법 검증 성공.
- 잔여 리스크(과호출 안정화 2차): 유저스트림 장기 불안정 구간에서 `Account snapshot REST reconcile throttled` 로그 비율과 실제 포지션 동기화 지연 여부를 운영 로그로 확인 필요.

- 구현 요약(과호출 안정화): `signal-loop` 한 틱에서 `USER_STREAM_UNHEALTHY` 사유의 강제 REST 스냅샷이 1회만 실행되도록 `snapshot_cycle_id` 게이트를 추가했고, REST 재조정 성공 판정을 "두 스냅샷 모두 실제 REST refresh 성공" 기준으로 바꿔 백오프 조기 해제를 막았다.
- 검증 결과(과호출 안정화): `python3 -m py_compile trade_page.py` 문법 검증 성공.
- 잔여 리스크(과호출 안정화): 자동매매 실운영 로그에서 `USER_STREAM_UNHEALTHY_ALREADY_FORCED` 및 `REST reconcile incomplete` 빈도를 확인해 과호출 감소와 상태 동기화 안정성을 함께 확인해야 한다.

- 구현 요약: `config.py`를 `2.1.1`로 상향하고, `./.venv/Scripts/python.exe build.py --target all`로 `LTS V2.1.1.exe`, `LTS-Updater.exe`를 재빌드한 뒤 루트 산출물 SHA256으로 `version.json`을 동기화했다.
- 검증 결과:
  - app sha256: `ff90cdcc5669a39940f801e592d1bdb9b740c7504fa20509340e545e53833fbd`
  - updater sha256: `548b69fff36dd705affc629aaae8e45f3e616500480b82639373f887b61ac26a`
  - `version.json` 메타 SHA와 파일 실제 SHA 일치 확인 완료(`app_sha_match=True`, `updater_sha_match=True`).
- 잔여 리스크: GitHub 배포 시 `LTS V2.1.1.exe`, `LTS-Updater.exe`, `version.json`이 같은 커밋/배포 단위로 올라가지 않으면 일시적으로 업데이트 검증 실패가 발생할 수 있다.
- 구현 요약(`pine_script.txt` 한글화): 다운로드 폴더의 `pine_script.txt`에서 사용자 노출 문자열(`indicator` 제목, `input`의 `title/group/tooltip`, `alertcondition` 제목/메시지, 볼륨 경고 문구)을 한글로 변환했고, 수치 설정값(`defval`, `minval`, `step`)과 로직은 유지했다.
- 검증 결과(`pine_script.txt` 한글화):
  - 원본 백업 생성: `/mnt/c/Users/dudfh/Downloads/pine_script_backup_before_korean.txt`
  - 반영 파일 확인: `/mnt/c/Users/dudfh/Downloads/pine_script.txt`
  - 문자열 인자 문법 근거 확인: Pine v5 Inputs 문서(`title`, `tooltip`, `group`는 const string), Pine Strings/Text 문서(문자열/유니코드 사용 가능)
- 잔여 리스크(`pine_script.txt` 한글화): 스크립트 헤더가 `//@version=6`이므로 TradingView에서 v6 규칙으로 컴파일된다. 요청은 v5였지만 문자열 치환 작업 자체는 v5/v6 공통 문자열 문법 내에서 수행했다.
- 구현 요약(`pine_script.txt` 저거래량 박스 첫 터치): `lowVolBoxes`와 인덱스를 맞춘 `lowVolTouched` 배열을 추가해 박스별 첫 터치 여부를 1회만 기록하고, 캔들 고가/저가가 저거래량 박스 가격 구간(`[lvLow, lvHigh]`)과 교차하면 `lowVolFirstTouchSignal`을 세트해 해당 봉 `abovebar`에 화살표를 표시하도록 반영했다. 또한 최초 터치 시 `log.info("LOW_VOL_BOX_FIRST_TOUCH ...")` 로그를 남기고 알림 조건을 추가했다.
- 검증 결과(`pine_script.txt` 저거래량 박스 첫 터치):
  - 반영 파일 확인: `/mnt/c/Users/dudfh/Downloads/pine_script.txt`
  - 상태 배열 동기화 확인: 생성 시 `array.unshift(lowVolTouched, false)`, 만료 삭제 시 `array.remove(lowVolTouched, i)` 반영
  - 표시/알림 확인: `plotshape(lowVolFirstTouchSignal, location=location.abovebar, style=shape.arrowdown)`, `alertcondition(lowVolFirstTouchSignal, ...)` 반영
- 잔여 리스크(`pine_script.txt` 저거래량 박스 첫 터치): TradingView 런타임 컴파일/시각 검증은 로컬 CLI에서 수행할 수 없어, 차트에 스크립트 적용 후 첫 터치 화살표 위치와 로그/알림 트리거를 실차트에서 1회 확인이 필요하다.
- 구현 요약(`pine_script.txt` 첫 터치 조건 정밀화): 첫 터치 판정을 `barstate.isconfirmed and na(fill)`로 제한해, 캔들 마감 시점에도 FVG 박스가 살아있는 경우에만 화살표를 남기도록 보정했다. 이로써 같은 봉에서 박스가 완화(깨짐)된 경우 화살표가 더 이상 표시되지 않는다.
- 검증 결과(`pine_script.txt` 첫 터치 조건 정밀화):
  - 반영 파일 확인: `/mnt/c/Users/dudfh/Downloads/pine_script.txt`
  - 핵심 조건 확인: `if barstate.isconfirmed and na(fill) and ...`
  - 문법 근거 확인: Pine `barstate.isconfirmed`(봉 확정), box getter 메서드(`box.get_top`, `box.get_bottom`) 공식 문서 재확인
- 잔여 리스크(`pine_script.txt` 첫 터치 조건 정밀화): 실시간 바(close 전)에는 신호가 확정되지 않으므로, TradingView 라이브 차트에서 바 마감 시점 신호 타이밍이 의도와 일치하는지 1회 확인이 필요하다.
- 구현 요약(`pine_script.txt` 박스당 1화살표 강제): 저거래량 박스의 화살표 발사 상태를 `bool` 대신 `int[] lowVolArrowBars`(박스별 첫 화살표 발생 바 인덱스)로 관리하도록 바꿨다. 해당 값이 `na`일 때만 터치 화살표를 발사하고, 발사 즉시 현재 `bar_index`를 기록해 동일 박스에서 추가 화살표를 차단한다.
- 검증 결과(`pine_script.txt` 박스당 1화살표 강제):
  - 반영 파일 확인: `/mnt/c/Users/dudfh/Downloads/pine_script.txt`
  - 초기화/삭제 동기화 확인: 생성 시 `array.unshift(lowVolArrowBars, na)`, 만료 삭제 시 `array.remove(lowVolArrowBars, i)`
  - 중복 차단 조건 확인: `na(array.get(lowVolArrowBars, i))` 조건 + 터치 후 `array.set(lowVolArrowBars, i, bar_index)`
- 잔여 리스크(`pine_script.txt` 박스당 1화살표 강제): 동일 봉에 여러 박스가 동시에 첫 터치되는 경우 현재 시각화는 `plotshape(bool)` 특성상 봉당 1개 화살표로 표현된다. 박스별 개별 마커가 필요하면 `label.new` 기반으로 확장해야 한다.
- 구현 요약(`pine_script.txt` 타입별 화살표 스타일 분리): 첫 터치 시그널을 `lowVolBullFirstTouchSignal`/`lowVolBearFirstTouchSignal` 두 개로 분리해 박스 타입별 표시를 분기했다. BEAR는 `shape.arrowdown`, `location.abovebar`, `color.red`, `size.normal`; BULL은 `shape.arrowup`, `location.belowbar`, `color.green`, `size.normal`으로 설정했다.
- 검증 결과(`pine_script.txt` 타입별 화살표 스타일 분리):
  - 반영 파일 확인: `/mnt/c/Users/dudfh/Downloads/pine_script.txt`
  - 시그널 분기 확인: `if typ == 1`이면 bull 신호, 아니면 bear 신호
  - 플롯 확인: `plotshape(lowVolBearFirstTouchSignal, ... color=color.red, size=size.normal, location=location.abovebar)` 및 `plotshape(lowVolBullFirstTouchSignal, ... color=color.green, size=size.normal, location=location.belowbar)`
- 잔여 리스크(`pine_script.txt` 타입별 화살표 스타일 분리): 같은 봉에 bull/bear 첫 터치가 동시에 발생하면 위/아래 화살표 2개가 함께 표시될 수 있다. 이는 현재 요구사항(타입별 표시) 기준 정상 동작이다.
- 구현 요약(`pine_script.txt` MOON/SUN 아이콘 치환): 타입별 화살표 출력(`plotshape`)을 타입별 아이콘 출력(`plotchar`)으로 교체했다. BEAR 신호는 `char="🌕"`를 캔들 위(`location.abovebar`)에 빨강/중간크기로 표시하고, BULL 신호는 `char="☀"`를 캔들 아래(`location.belowbar`)에 초록/중간크기로 표시한다.
- 검증 결과(`pine_script.txt` MOON/SUN 아이콘 치환):
  - 반영 파일 확인: `/mnt/c/Users/dudfh/Downloads/pine_script.txt`
  - 아이콘 플롯 확인: `plotchar(lowVolBearFirstTouchSignal, ..., char="🌕", ...)`, `plotchar(lowVolBullFirstTouchSignal, ..., char="☀", ...)`
  - 문법 근거 확인: TradingView Text and shapes 문서(`plotchar()`는 한 글자 표시, Unicode 문자 지원)
- 잔여 리스크(`pine_script.txt` MOON/SUN 아이콘 치환): TradingView/OS 폰트에 따라 emoji 렌더링이 컬러 이모지로 출력되면 `color.red/green`이 시각적으로 반영되지 않을 수 있다. 이 경우 단색 유니코드 아이콘(예: `▲/▼`)이나 `plotshape(text=...)` 대안을 사용해야 한다.
- 구현 요약(`pine_script.txt` 활성 박스 아이콘만 유지): 시리즈 기반 `plotchar`를 제거하고 박스별 `label` 객체 배열(`lowVolTouchLabels`)을 도입했다. 첫 터치 시 라벨을 생성해 박스 인덱스에 저장하고, 박스가 완화되어 `fill`이 생기거나(`reason=FILLED`) 만료로 삭제될 때(`reason=EXPIRED`) 해당 라벨을 즉시 삭제해 현재 활성 박스 아이콘만 남도록 변경했다.
- 검증 결과(`pine_script.txt` 활성 박스 아이콘만 유지):
  - 반영 파일 확인: `/mnt/c/Users/dudfh/Downloads/pine_script.txt`
  - 라벨 생성 확인: `label.new(... text = "☀"/"🌕" ...)` + `array.set(lowVolTouchLabels, i, touchLbl)`
  - 라벨 삭제 확인: `label.delete(filledLbl)`(완화), `label.delete(expLbl)`(만료)
  - 로그 확인: `LOW_VOL_TOUCH_ICON_REMOVED ... reason=FILLED/EXPIRED`
- 잔여 리스크(`pine_script.txt` 활성 박스 아이콘만 유지): TradingView 차트 리플로우/리로딩 환경에서 label 렌더링 개수 제한(`max_labels_count`)에 근접하면 오래된 라벨이 플랫폼 정책에 따라 정리될 수 있으므로, 활성 박스 수가 많은 심볼/타임프레임에서 1회 시각 확인이 필요하다.
- 구현 요약(`pine_script.txt` 시각 잔존 박스 기준 아이콘 유지): 아이콘 수명 기준을 "미완화(active)"에서 "차트에 박스가 남아있는 상태(완화 포함)"로 변경했다. 따라서 FILLED 시점에는 라벨을 삭제하지 않고 유지하며, 박스가 `age > maxBoxAge`로 실제 삭제될 때만 라벨을 제거한다.
- 검증 결과(`pine_script.txt` 시각 잔존 박스 기준 아이콘 유지):
  - 반영 파일 확인: `/mnt/c/Users/dudfh/Downloads/pine_script.txt`
  - FILLED 유지 확인: FILLED 블록에서 `label.delete(...)` 제거, `LOW_VOL_TOUCH_ICON_RETAINED ... reason=FILLED_VISIBLE` 로그 추가
  - EXPIRED 삭제 유지: `label.delete(expLbl)` + `LOW_VOL_TOUCH_ICON_REMOVED ... reason=EXPIRED` 유지
- 잔여 리스크(`pine_script.txt` 시각 잔존 박스 기준 아이콘 유지): 동일 박스에서 첫 터치 라벨은 터치 봉 위치에 고정되므로, 박스가 오래 남아도 아이콘 위치는 이동하지 않는다. 이는 "해당 박스의 첫 터치 지점 표시" 기준으로 의도된 동작이다.
- 구현 요약(`pine_script.txt` 설정 고정/숨김): 사용자 요청 15개 항목 중 13개를 `input.*`에서 상수로 치환해 설정창에서 숨겼고(툴팁 제거), `상승 박스 색상`/`하락 박스 색상`만 `input.color`로 유지해 조정 가능하게 남겼다. 또한 초기 1회 `CONFIG_LOCKED` 로그로 고정값 적용 사실을 기록한다.
- 검증 결과(`pine_script.txt` 설정 고정/숨김):
  - 반영 파일 확인: `/mnt/c/Users/dudfh/Downloads/pine_script.txt`
  - 고정값 확인: `volaLen=50`, `volaMult=1.5`, `maxBoxAge=500`, `preventOverlap=true`, `showBull=true`, `showBear=true`, `ltf="1"`, `bincount=7`, `lvWindow=2`, `showProfile=false`, `showLowVolZone=true`, `showGapZone=false`, `profgrad=false`
  - 옵션 유지 확인: `bullCol`, `bearCol`만 `input.color`로 잔존(툴팁 유지)
  - 로그 확인: `if barstate.isfirst -> log.info("CONFIG_LOCKED ...")`
- 잔여 리스크(`pine_script.txt` 설정 고정/숨김): `showGapZone=false` 고정으로 메인 갭 박스는 기본 숨김이며, 저거래량 박스/아이콘 중심 표시가 된다. 이는 요청사항과 일치하지만 사용자가 메인 갭 시각화를 기대하면 추가 조정이 필요하다.
- 구현 요약(`pine_script.txt` 알림 단일화): Alerts 블록에서 `alertcondition`을 `lowVolFirstTouchSignal` 하나만 남기고, `bullFVG/bearFVG/bullMit/bearMit/lowVolBullFirstTouchSignal/lowVolBearFirstTouchSignal` 기반 알림은 모두 제거했다.
- 검증 결과(`pine_script.txt` 알림 단일화):
  - 반영 파일 확인: `/mnt/c/Users/dudfh/Downloads/pine_script.txt`
  - 검증 명령: `rg -n "^alertcondition\\(" /mnt/c/Users/dudfh/Downloads/pine_script.txt`
  - 결과: `alertcondition(lowVolFirstTouchSignal, "저거래량 박스 첫 터치", ...)` 1개만 존재
- 잔여 리스크(`pine_script.txt` 알림 단일화): bull 전용/ bear 전용 알림 분리가 사라졌으므로, 타입별 별도 알림이 필요해지면 다시 두 알림 조건을 복구해야 한다.
- 구현 요약(`pine_script.txt` 박스 거래량 텍스트 제거): 메인 갭 박스 생성부 `box.new(...)`에서 `text`, `text_size`, `text_color`, `text_halign`, `text_valign` 인자를 제거해 박스 내부에 거래량 수치가 렌더링되지 않도록 변경했다.
- 검증 결과(`pine_script.txt` 박스 거래량 텍스트 제거):
  - 반영 파일 확인: `/mnt/c/Users/dudfh/Downloads/pine_script.txt`
  - 코드 확인: `box.new(... extend = extend.none)`만 남고 거래량 텍스트 인자 제거 완료
  - 검색 검증: `format.volume`, 해당 텍스트 정렬/크기 인자 미검출 확인
  - 로그 반영: `CONFIG_LOCKED ... boxVolumeText=false`
- 잔여 리스크(`pine_script.txt` 박스 거래량 텍스트 제거): 거래량 수치 표시가 완전히 제거되어 과거 대비 박스별 볼륨 직관 정보는 차트에서 직접 보이지 않는다.

- [x] PHASE1 TP를 단일 주문에서 10분할 컨디셔널 TP로 전환(설정 TP~TP+0.9%, 0.1% 간격)
- [x] PHASE2 TP를 10분할 컨디셔널 TP로 전환(평단 -1.0%~-0.1%, 0.1% 간격)
- [x] 분할 TP 수량을 step_size 기준으로 안전 분배(총합=보유수량, 주문당 최소수량 검증)
- [x] TP 1개 체결 시 남은 TP 유지 + PHASE1 본절 STOP_MARKET 보강 로직 반영
- [x] OCO 상호취소가 분할 TP를 지우지 않도록 체결 타입별 예외 처리
- [x] 수량 변경 재빌드 경로에서 분할 TP/본절 STOP 정책 유지
- [x] 리스크관리(수익 구간) 기존 동작 보존 검증: TP 유지 + 불필요한 TP 재생성/취소 방지
- [x] 회귀 테스트 추가/보정(phase1 분할TP, phase2 분할TP, TP 체결 후 OCO/본절STOP)
- [x] 검증 실행: 대상 unittest + py_compile

- [x] 릴리즈 작업 계획 확정: `2.1.1 -> 2.1.2` 반영 범위/파일 점검
- [x] `config.py` 버전을 `2.1.2`로 상향
- [x] `build.py --target all`로 런처/업데이터 재빌드
- [x] 새 산출물(`LTS V2.1.2.exe`, `LTS-Updater.exe`) SHA256 계산
- [x] `version.json`의 `min_version`, `app_url`, `app_sha256`, `updater_sha256` 동기화
- [x] SHA 재검증으로 자동업데이트 메타데이터 일치 확인
- [x] 릴리즈 작업 Review 섹션 기록

- 구현 요약(분할 트리거 TP 10개 + TP 체결 연속성):
  - `trade_page.py`의 PHASE1/PHASE2 exit 정책을 단일 TP 기준에서 분할 TP 기준으로 교체했다.
  - PHASE1은 설정 TP부터 +0.9%까지 0.1% 간격 10개, PHASE2는 평단 -1.0%~-0.1% 0.1% 간격 10개 트리거 주문(TAKE_PROFIT)을 유지/보강하도록 변경했다.
  - 분할 TP 1개 체결 시 OCO 상호취소를 우회해 남은 TP를 유지하고, PHASE1에서는 본절 STOP_MARKET 보강 플래그를 세워 다음 정책 루프에서 본절 스탑을 보장하도록 추가했다.
  - 분할 주문 제출은 개별 주문 실패 시 전체 시장가 폴백을 강제하지 않도록 분할 전용 경로(`allow_market_fallback=False`)를 분리했다.
  - 수량 재빌드/복구 경로에서도 분할 TP 정책이 유지되도록 phase 템플릿 적용 로직을 보정했다.
- 검증 결과(분할 트리거 TP 10개 + TP 체결 연속성):
  - 통과: `python3 -m unittest tests.test_stage15_trade_page_regression` (32 tests)
  - 통과: `python3 -m unittest tests.test_stage11_execution_flow tests.test_stage13_orchestrator_integration` (51 tests)
  - 통과: `python3 -m py_compile trade_page.py tests/test_stage15_trade_page_regression.py`
- 잔여 리스크(분할 트리거 TP 10개 + TP 체결 연속성):
  - 심볼별 `tick_size`가 거칠어 0.1% 가격대가 중복되는 경우 실주문 수가 10개 미만으로 축소될 수 있다(로그 `Split TP plan reduced order count`로 추적 가능).
  - 거래소 응답 지연 구간에서 가드 시간(20초) 내 누락 주문 재제출이 1틱 지연될 수 있으므로 운영 로그의 `missing`/`succeeded` 카운트를 모니터링해야 한다.

- 구현 요약(릴리즈 2.1.2): `config.py` 버전을 `2.1.2`로 상향하고, `./.venv/Scripts/python.exe build.py --target all` 재빌드 후 `dist` 산출물을 루트 배포 파일(`LTS V2.1.2.exe`, `LTS-Updater.exe`)로 동기화했다.
- 검증 결과(릴리즈 2.1.2):
  - 빌드 통과: `./.venv/Scripts/python.exe build.py --target all`
  - app sha256: `59a125c0f8c1aed4db65ff84bd08fb2f2fee44a4de6580e3751ad137cbf786b4`
  - updater sha256: `8cc13daf433203fec1c3f6e54f9866f876974e01f9e8403edee0763a594e7009`
  - `version.json` 동기화 확인: `min_version=2.1.2`, `app_url=LTS%20V2.1.2.exe`, `app_sha_match=True`, `updater_sha_match=True`
- 잔여 리스크(릴리즈 2.1.2): GitHub 배포 시 `LTS V2.1.2.exe`, `LTS-Updater.exe`, `version.json`이 동일 커밋 단위로 함께 올라가지 않으면 일시적인 해시 검증 실패가 발생할 수 있다.

- [x] 진입 트리거 조건(현재 0.5% 버퍼) 계산 경로를 1틱 선행 규칙으로 전환
- [x] TP 트리거 주문(`TAKE_PROFIT`) stopPrice 계산을 1틱 선행 규칙으로 전환
- [x] 트리거 가격 결정 규칙 변경에 대한 로그 필드/메시지 점검
- [x] 관련 회귀 테스트(stage7/stage15/stage13) 보정 및 실행
- [x] 작업 Review/리스크를 `tasks/todo.md`에 기록

- 구현 요약(트리거 1틱 선행 통일): 진입 트리거 루프는 심볼별 `tick_size`를 전달받아 `FIRST_ENTRY/SECOND_ENTRY` 임계값을 `target_price - 1tick`으로 계산하도록 전환했고, TP 트리거 주문(`TAKE_PROFIT`)의 `stopPrice`는 방향별 1틱 선행(숏 청산 BUY는 `target+1tick`, 롱 청산 SELL은 `target-1tick`)으로 통일했다.
- 검증 결과(트리거 1틱 선행 통일):
  - 통과: `python3 -m py_compile auto_trade/trigger_engine.py auto_trade/orchestrator.py trade_page.py tests/test_stage7_trigger_engine.py tests/test_stage15_trade_page_regression.py`
  - 통과: `python3 -m unittest tests.test_stage7_trigger_engine` (15 tests)
  - 통과: `python3 -m unittest tests.test_stage15_trade_page_regression` (32 tests)
  - 통과: `python3 -m unittest tests.test_stage13_orchestrator_integration tests.test_stage11_execution_flow tests.test_stage7_trigger_engine` (70 tests)
- 잔여 리스크(트리거 1틱 선행 통일): 극단적 급변 구간에서는 1틱 선행도 미체결/부분체결 가능성을 완전히 제거하지 못하므로, 운영 로그에서 `TP trigger result`의 실패 사유(`EXCHANGE_REJECTED`, `MIN_NOTIONAL_NOT_MET`) 빈도를 모니터링해야 한다.

- [x] 릴리즈 작업 계획 확정: `2.1.2 -> 2.1.3` 반영 범위/파일 점검
- [x] `config.py` 버전을 `2.1.3`로 상향
- [x] `build.py --target all`로 런처/업데이터 재빌드
- [x] `dist` 산출물을 루트 배포 파일(`LTS V2.1.3.exe`, `LTS-Updater.exe`)로 동기화
- [x] 새 산출물 SHA256 계산
- [x] `version.json`의 `min_version`, `app_url`, `app_sha256`, `updater_sha256` 동기화
- [x] SHA 재검증으로 자동업데이트 메타데이터 일치 확인

- 구현 요약(릴리즈 2.1.3): `config.py`를 `2.1.3`으로 상향한 뒤 Windows PyInstaller로 런처/업데이터를 재빌드하고, `dist` 산출물을 루트 배포 파일로 동기화했다. 이후 계산된 SHA256을 `version.json`에 반영해 자동업데이트 메타데이터와 실제 배포 파일 해시를 일치시켰다.
- 검증 결과(릴리즈 2.1.3):
  - 빌드 통과: `cmd.exe /c ".venv\\Scripts\\python.exe build.py --target all"`
  - app sha256: `a185b8347e2c8628ed2d9967ff070f3aa3dadbb189882da827272920028ee187`
  - updater sha256: `41dfe895098a3c0afd8707d8cce0a41a767da1b06a2f7b1ea0788663f35f3f37`
  - 메타 일치 확인: `app_sha_match=True`, `updater_sha_match=True`, `min_version=2.1.3`
  - 문법 검증: `python3 -m py_compile config.py main.py updater.py trade_page.py auto_trade/trigger_engine.py auto_trade/orchestrator.py`
- 잔여 리스크(릴리즈 2.1.3): GitHub 배포 시 `LTS V2.1.3.exe`, `LTS-Updater.exe`, `version.json`이 동일 커밋/동일 push로 함께 올라가지 않으면 짧은 시간 동안 SHA 검증 실패가 발생할 수 있다.
