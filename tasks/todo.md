## Task - ExitManager Stale Caller Fix
- [x] `set_position_checker` 삭제 이후 남아 있던 호출 위치 확인
- [x] 로그인 페이지의 stale caller 제거로 런타임 예외 복구
- [x] 구문 검증과 Review 기록

## Review - ExitManager Stale Caller Fix
- `ExitManager.set_position_checker()`는 삭제됐는데 `login_page.py` 초기화 코드에 `exit_manager.set_position_checker(None)` 호출이 남아 있어서, 로그인 페이지 진입 시 `AttributeError`가 발생했음.
- 호출 위치는 `login_page.py` 한 곳뿐이었고, 실제 기능적으로도 더 이상 필요한 초기화가 아니므로 `ExitManager`에 no-op API를 되살리는 대신 stale caller 자체를 제거함.
- 검증: `python3 -m py_compile main.py login_page.py trade_page.py exit.py entry_bot.py` 통과. 이름 검색 기준으로 `set_position_checker` 참조는 더 이상 남아 있지 않음.

## Task - Dead Trading Residue Cleanup
- [x] 자동 STOP/체결감시 잔재와 MDD/TP UI 잔재 범위를 확정
- [x] 엔트리 1회, 미체결 리관 취소, 포지션/미체결 주문 존재 시 신규 진입 무시 경로를 유지한 채 잔재 제거
- [x] 삭제 후 핵심 경로 재검토와 구문 검증, Review 기록

## Review - Dead Trading Residue Cleanup
- `entry_bot.py`에서 죽은 체결감시/자동 STOP 잔재를 제거함. 구체적으로 `ENTRY_MODE_STOP_AFTER_SUBMIT`, `auto_stop_callback`, `refresh_snapshot_once()`, `_should_auto_stop_after_fill()`, `_should_refresh_pending_entry_snapshot()`, 그리고 이 함수들만 위해 남아 있던 대기 상태값들을 삭제함.
- `trade_page.py`에서는 더 이상 쓰이지 않던 MDD/TP 드롭다운과 관련 상수, reset 버튼 잔재, backend auto-stop 콜백 연결을 제거하고 레버리지 단일 설정 UI만 남김.
- `exit.py`에서는 실제 연결이 없던 `set_position_checker()`와 관련 상태를 제거함.
- 삭제 후에도 핵심 진입 차단 경로는 그대로 유지됨. `entry_bot.py`의 엔트리 경로는 여전히 `snapshot.positions`가 있으면 `reason=position_exists`, `snapshot.open_orders`에 엔트리 주문이 있으면 `reason=open_entry_order_exists`로 신규 진입을 무시함. 리관 경로도 여전히 `reason=no_open_entry_orders`, `reason=position_exists`, `Risk signal cancel summary` 흐름으로 미체결 주문만 취소함.
- 검증: `python3 -m py_compile entry_bot.py trade_page.py exit.py` 통과. 이름 검색 기준으로 `mdd_dropdown`, `tp_ratio_dropdown`, `ENTRY_MODE_STOP_AFTER_SUBMIT`, `refresh_snapshot_once`, `set_position_checker` 등 삭제 대상 참조는 모두 제거된 것을 확인함.

## Task - Entry-Only Flow Audit
- [x] 엔트리 주문 후 체결 감시/다음 페이즈/자동 종료 경로가 실제 루프에서 실행되는지 확인
- [x] 트레이드 페이지와 종료 매니저에서 포지션 기반 후속 거래 연결이 남아 있는지 확인
- [x] 남아 있는 죽은 코드와 실제 활성 경로를 Review에 정리

## Review - Entry-Only Flow Audit
- 현재 활성 실행 경로 기준으로는 `EntryRelayBot._run_loop()`가 신호 relay poll 후 `_handle_entry_signal()`과 `_handle_risk_signal()`만 호출하고 있으며, 주문 체결 후 다음 단계로 넘어가는 호출은 없음.
- 엔트리 주문 성공 후에는 숏 진입 주문 1회 제출만 수행하고, 이후 봇은 리스크 관리 신호 취소 지원을 위해 계속 살아 있지만 체결 감시용 `_should_auto_stop_after_fill()`와 `_should_refresh_pending_entry_snapshot()`는 현재 루프 어디에서도 호출되지 않아 죽은 코드 상태임.
- 리스크 관리 신호 경로는 `_handle_risk_signal()`에서 미체결 엔트리 주문만 조회해 취소하며, 이미 포지션이 생긴 경우에는 `reason=position_exists`로 무시하므로 체결 이후 추가 주문/청산/다음 페이즈 로직으로 이어지지 않음.
- `trade_page.py`에서는 `auto_stop_callback` 연결과 `_schedule_entry_auto_stop()` 함수는 남아 있지만, 현재 설정(`ENTRY_MODE_STOP_AFTER_SUBMIT = False`)과 비호출 상태인 체결 감시 헬퍼 때문에 실질적으로 작동하지 않음. `exit.py`도 거래 종료 로직이 아니라 트레이 아이콘/앱 종료 관리자임.
- 남은 흔적은 거래 버그라기보다 정리되지 않은 죽은 코드에 가까움. 실제 실동작상 중요한 경로는 `엔트리 신호 -> 주문 1회 제출`, `리관 신호 -> 미체결 주문 취소`, `수동 STOP -> 봇 중지` 정도로 좁혀져 있음.

## Task - Version 4.0.0 Update Build
- [x] 최신 커밋 기준으로 자동업데이트 관련 로직 파일 변경 여부 확인
- [x] 버전을 4.0.0으로 올리고 업데이트 메타데이터 경로를 새 런처 파일명 기준으로 조정
- [x] Windows PyInstaller로 런처/업데이터 재빌드 후 루트 exe 반영
- [x] 실제 exe SHA256을 `version.json`에 반영하고 검증 결과 기록

## Review - Version 4.0.0 Update Build
- 최신 커밋(`HEAD`) 대비 자동업데이트 관련 파일을 확인한 결과, `main.py`, `updater.py`, `update_security.py`, `build.py`에는 로직 변경이 없었고, 업데이트 경로 쪽 diff는 `config.py` 주석과 이번 버전 상수 변경, `version.json` 메타데이터 갱신뿐이었음.
- `config.py`의 `VERSION`을 `4.0.0`으로 올렸고, `version.json`의 `min_version`과 `app_url`을 `LTS V4.0.0.exe` 기준으로 바꾼 뒤 실제 빌드 결과 SHA256을 반영함.
- Windows Python 3.10 + PyInstaller 6.17.0으로 `build.py --target all`을 실행해 `dist/LTS V4.0.0.exe`, `dist/LTS-Updater.exe`를 새로 생성했고, 자동업데이트 raw URL 경로와 맞도록 루트의 `LTS V4.0.0.exe`, `LTS-Updater.exe`도 동일 산출물로 교체함.
- 최종 SHA256은 런처 `ab5901e23f4013681f105707f724c72cac612795616914040e2cde6097e11953`, 업데이터 `dc67bd1618d95c7fcd53a895e281afe565c5ce808cc9e7a04bf8fd354c0bb9fc`이며, `update_security.extract_sha256_from_metadata()`와 `verify_file_sha256()`로 `version.json` 메타데이터 해석 및 실제 파일 검증을 모두 통과함.
- 검증: `python3 -m py_compile main.py updater.py build.py update_security.py config.py` 통과. `python3 -m pytest tests/test_update_security.py`는 현재 WSL Python 환경에 `pytest`가 없어 실행하지 못함. Windows 빌드는 `cmd.exe /c C:/Users/dudfh/AppData/Local/Programs/Python/Python310/python.exe build.py --target all`로 성공함.

## Task - Risk Signal Cancel Recovery
- [x] 최근 로그에서 엔트리 주문 제출 뒤 리스크 신호 취소가 막힌 시점을 확인
- [x] 주문 제출 후 자동 정지가 리스크 신호 처리를 끊는 문제를 수정
- [x] 구문 검증 후 Review 기록

## Review - Risk Signal Cancel Recovery
- `logs/LTS-Trade_log_file/LTS-Trade.log` 기준 2026-03-13 12:50:52 `BTRUSDT` 엔트리 주문 성공 직후 `Entry relay loop exited.`와 `Auto-trade stopped by backend: reason=entry_order_submitted`가 바로 이어져, 이후 리스크 관리 신호를 더 이상 소비할 수 없는 상태였음.
- 원인은 `entry_bot.py`의 `ENTRY_MODE_STOP_AFTER_SUBMIT = True` 설정과 `_handle_entry_signal()` 내부 자동 정지 분기였고, 이 흐름이 미체결 엔트리 주문 취소보다 먼저 봇을 종료시켰음.
- `ENTRY_MODE_STOP_AFTER_SUBMIT`을 `False`로 바꾸고, 주문 제출 성공 후에는 봇을 계속 유지하면서 `reason=risk_signal_cancel_support` 로그를 남기도록 조정함. 이 변경으로 Binance 주기 스냅샷 감시는 복구하지 않고도 리스크 취소 신호 처리는 다시 살아남.
- 검증: `python3 -m py_compile entry_bot.py trade_page.py` 통과. 실제 리스크 신호 수신 후 취소 동작은 다음 실신호에서 확인 필요.

## Task - Entry Order Precision Fix
- [x] 최근 진입 실패 로그와 주문 전송 파라미터를 확인해 실제 거절 원인 파악
- [x] 엔트리 주문의 가격/수량/트리거 값을 Binance 허용 자릿수 문자열로 직렬화하도록 수정
- [x] 구문 검증과 재현값 직렬화 확인 후 Review 기록

## Review - Entry Order Precision Fix
- `logs/LTS-Trade_log_file/LTS-Trade.log` 기준 2026-03-13 12:42:27 `BTRUSDT` 진입 실패 원인은 `/fapi/v1/algoOrder` 요청이 `code=-1111`, `Precision is over the maximum defined for this asset.`로 거절된 것이었고, 실패 파라미터에 `price=0.12045000000000002` 같은 float 아티팩트가 그대로 기록되어 있었음.
- `entry_bot.py`에 `_format_order_value_by_increment()` 헬퍼를 추가해, 엔트리 주문 생성 시 `price`, `quantity`, `stopPrice`를 각각 tick/step 기준으로 양자화한 문자열로 변환해 전송하도록 조정함.
- 가격 계열은 `ROUND_HALF_UP`, 수량은 과주문을 막기 위해 `ROUND_DOWN`으로 직렬화해 기존 진입 계산 로직은 유지하면서 전송 문자열만 안전하게 고정함.
- 검증: `python3 -m py_compile entry_bot.py trade_page.py` 통과. 재현값 직렬화 확인 결과 `0.12045000000000002 -> 0.12045`, `1505.0 -> 1505`, `0.12044 -> 0.12044`로 출력됨.

## Task - Trade Page Strategy Panel
- [x] 트레이드 페이지의 활성 포지션 영역과 엔트리 봇 포지션 감시 경로를 확인
- [x] 활성 포지션 영역을 롱/숏/DCA 전략 가이드 버튼 3개 레이아웃으로 교체
- [x] 롱/숏 문서 연결과 DCA 준비중 안내, 관련 로그 추가
- [x] 엔트리 봇의 반복 포지션 감시를 제거하고 주문 제출 후 자동 정지 흐름으로 축소해 진입 기능은 유지
- [x] 구문 검증 후 Review 기록

## Review - Trade Page Strategy Panel
- `trade_page.py`의 기존 `활성화된 포지션` 패널을 `전략 가이드북` 패널로 교체하고, `📈롱포지션 전략 가이드북`, `📉숏포지션 전략 가이드북`, `🔄DCA 전략지표 가이드문서` 3개 버튼으로 재구성함.
- 롱/숏 버튼은 각각 `image/login_page/long.pdf`, `image/login_page/short.pdf`를 열도록 연결했고, DCA 버튼은 문서 미준비 상태라 준비중 안내 팝업과 로그만 남기도록 처리함.
- `TradePage`에서는 포지션 상태를 더 이상 UI에 반영하지 않도록 `_positions` 의존을 제거했고, 초기 진입 로그에 `strategy_panel=strategy_guides`를 추가함.
- `entry_bot.py`에서는 `START` 직후의 전체 포지션/오더 스냅샷 호출과 실행 중 5초 주기 포지션 감시 루프를 제거하고, 진입 신호에서 주문 제출이 성공하면 즉시 자동매매를 정지하는 `entry_mode_stop_after_submit` 흐름으로 축소함. 대신 실제 진입 전에는 여전히 1회 스냅샷으로 기존 포지션/오픈오더를 점검해 중복 진입을 막도록 유지함.
- 검증: `python3 -m py_compile trade_page.py entry_bot.py` 통과. 실제 Tkinter 수동 클릭 확인은 이번 턴에서 실행하지 않음.

## Task - Active Position API Check
- [x] 로그인 후 트레이드 페이지 진입과 스냅샷 갱신 경로 확인
- [x] 활성 포지션 관련 Binance API 호출 지점과 주기 확인
- [x] 확인 결과를 Review에 정리

## Review - Active Position API Check
- 로그인 성공 후 트레이드 페이지 진입 시에는 `TradePage._start_initial_snapshot_fetch()`가 `EntryRelayBot.refresh_wallet_balance_once()`만 호출하므로 초기에는 지갑 잔고만 조회하고 포지션/오픈오더 조회는 하지 않음.
- 자동매매 `START` 이후 `EntryRelayBot.start()`가 최초 1회 전체 스냅샷을 가져오고, 이후 `_refresh_account_snapshot()` 기준으로 잔고는 15초마다, 포지션(`/fapi/v2/positionRisk`)과 오픈오더(`/fapi/v1/openOrders`, `/fapi/v1/openAlgoOrders`)는 5초마다 갱신될 수 있음.
- 따라서 Binance 쪽 요청 부담은 포지션 테이블을 그리는 UI 때문이라기보다 `EntryRelayBot`의 스냅샷 관리 로직 때문임. 대략 자동매매 실행 중에는 5초마다 signed 요청 3개, 15초마다 signed 요청 1개가 기본 경로임.
- 현재 워크스페이스의 `trade_page.py` 기준으로 `_positions`는 스냅샷에서 받아와 내부 상태와 종료 체크에 쓰이지만, `_draw_table()`은 표 제목과 헤더만 그리고 실제 포지션 row를 렌더링하는 코드는 없음.

## Task - Product Guidebook Slot 6
- [x] 현재 6번 슬롯 비어 있는 상태와 기존 슬롯 패턴 확인
- [x] 6번 슬롯에 `🔄DCA 전략지표 가이드문서` 라벨과 버튼 추가
- [x] 문서 미준비 상태용 안내 클릭 처리와 로그 추가
- [x] 구문 검증 후 Review 기록

## Review - Product Guidebook Slot 6
- `ProductGuidebookWindow` 6번 슬롯에 `🔄DCA 전략지표 가이드문서` 라벨과 동일 문구 버튼을 추가해 3x2 그리드를 모두 채움.
- 문서는 아직 미연결 상태라 버튼 클릭 시 `DCA 전략지표 가이드문서는 준비 중입니다.` 안내 팝업이 뜨도록 했고, 클릭 및 안내 표시 로그를 남기도록 구현함.
- 레이아웃 로그의 `populated_slots` 값을 `6`으로 갱신해 전체 슬롯이 채워진 상태가 반영되도록 조정함.
- 검증: `python3 -m py_compile login_page.py` 통과. 실제 GUI 수동 클릭 확인은 이번 턴에서 실행하지 않음.

## Task - Product Guidebook Slots 3 to 5
- [x] 3, 4, 5번 슬롯에 연결할 `indicator.pdf`, `long.pdf`, `short.pdf` 파일 위치 확인
- [x] 3번 슬롯에 `🐳고래지표 설명 가이드북`, 4번 슬롯에 `📈롱포지션 전략 가이드북`, 5번 슬롯에 `📉숏포지션 전략 가이드북` 라벨과 버튼 추가
- [x] 각 버튼 클릭 시 대응 PDF를 여는 로직과 로그 추가
- [x] 구문 검증 후 Review 기록

## Review - Product Guidebook Slots 3 to 5
- `ProductGuidebookWindow`의 공통 슬롯 생성 구조를 그대로 사용해 3번 슬롯에 `🐳고래지표 설명 가이드북`, 4번 슬롯에 `📈롱포지션 전략 가이드북`, 5번 슬롯에 `📉숏포지션 전략 가이드북` 라벨과 동일 문구 버튼을 추가함.
- 각 버튼은 각각 `image/login_page/indicator.pdf`, `image/login_page/long.pdf`, `image/login_page/short.pdf`를 열도록 연결했고, 기존 공통 PDF 열기 헬퍼를 통해 클릭/파일 없음/열기 성공/실패 로그를 동일 포맷으로 남기도록 유지함.
- 레이아웃 로그의 `populated_slots` 값을 `5`로 갱신해 현재 채워진 슬롯 수가 반영되도록 조정함.
- 검증: `python3 -m py_compile login_page.py` 통과. 실제 GUI 수동 클릭 확인은 이번 턴에서 실행하지 않음.

## Task - Product Guidebook Slot 2
- [x] 두 번째 슬롯에 연결할 `lts_explain.pdf` 파일 위치 확인
- [x] 두 번째 슬롯에 `📚LTS 가이드 문서` 라벨과 버튼 추가
- [x] 버튼 클릭 시 `image/login_page/lts_explain.pdf`를 여는 로직과 로그 추가
- [x] 구문 검증 후 Review 기록

## Review - Product Guidebook Slot 2
- `ProductGuidebookWindow`에 공통 슬롯 생성 헬퍼를 추가하고, 두 번째 슬롯에 `📚LTS 가이드 문서` 라벨과 동일 문구 버튼을 배치함.
- 버튼 클릭 시 `image/login_page/lts_explain.pdf`를 열도록 연결했고, 공통 PDF 열기 헬퍼를 통해 클릭/파일 없음/열기 성공/실패 로그를 일관된 형식으로 남기도록 정리함.
- 레이아웃 로그의 `populated_slots` 값을 `2`로 갱신해 현재 채워진 슬롯 수가 반영되도록 조정함.
- 검증: `python3 -m py_compile login_page.py` 통과. 실제 GUI 수동 클릭 확인은 이번 턴에서 실행하지 않음.

## Task - Product Guidebook Item Width
- [x] 상품구성 및 가이드북 첫 슬롯의 라벨/버튼 폭 관련 코드 확인
- [x] `📡LTS 연결 가이드북` 라벨과 버튼의 가로 폭을 넓히도록 조정
- [x] 구문 검증 후 Review 기록

## Review - Product Guidebook Item Width
- `login_page.py`에 `PRODUCT_GUIDE_ITEM_WIDTH = 20` 상수를 추가하고, 첫 번째 슬롯의 `📡LTS 연결 가이드북` 라벨과 버튼에 같은 폭을 적용해 가로 길이를 넓힘.
- 레이아웃 로그에도 `item_width=20` 정보를 추가해 현재 항목 폭 설정이 함께 남도록 조정함.
- 검증: `python3 -m py_compile login_page.py` 통과. 실제 GUI 수동 클릭 확인은 이번 턴에서 실행하지 않음.

## Task - Product Guidebook Grid Layout
- [x] 상품구성 및 가이드북 창의 현재 단일 항목 배치 구조 확인
- [x] 상품구성 및 가이드북 창을 중앙 기준 3열 2행 슬롯 레이아웃으로 재구성
- [x] `📡LTS 연결 가이드북` 항목을 첫 번째 슬롯에 맞춰 재배치하고 로그 갱신
- [x] 구문 검증 후 Review 기록

## Review - Product Guidebook Grid Layout
- `ProductGuidebookWindow` 내부를 중앙 기준 3열 2행 슬롯 레이아웃으로 재구성해, 향후 총 6개 가이드 항목을 같은 패턴으로 배치할 수 있게 조정함.
- `📡LTS 연결 가이드북` 라벨과 버튼은 첫 번째 슬롯 안에서 중앙 정렬되도록 옮겼고, 나머지 슬롯 5개는 이후 항목 추가를 위한 빈 자리로 유지함.
- 레이아웃 로그를 `grid=3x2`, `slot_size=250x130`, `populated_slots=1` 정보가 남도록 갱신함.
- 검증: `python3 -m py_compile login_page.py` 통과. 실제 GUI 수동 클릭 확인은 이번 턴에서 실행하지 않음.

## Task - Product Guidebook LTS Entry
- [x] 상품구성 및 가이드북 새 창 내부 구조와 LTS 연결 PDF 경로 확인
- [x] 좌측 상단에 `📡LTS 연결 가이드북` 라벨과 버튼 추가
- [x] 버튼 클릭 시 `image/login_page/lts_connect_guide.pdf`를 여는 로직과 로그 추가
- [x] 구문 검증 후 Review 기록

## Review - Product Guidebook LTS Entry
- `ProductGuidebookWindow` 좌측 상단에 `📡LTS 연결 가이드북` 라벨과 동일 문구 버튼을 추가해 첫 번째 가이드 항목을 배치함.
- 버튼 클릭 시 `image/login_page/lts_connect_guide.pdf`를 열도록 연결했고, 클릭/파일 없음/열기 성공/실패 로그를 각각 남기도록 구현함.
- 배경 토글 시 새 라벨 영역 배경색이 함께 유지되도록 창 내부 컨테이너와 라벨 배경 처리도 확장함.
- 검증: `python3 -m py_compile login_page.py` 통과. 실제 GUI 수동 클릭 확인은 이번 턴에서 실행하지 않음.

## Task - Product Guidebook Window Height
- [x] 상품구성 및 가이드북 새 창의 현재 세로 크기 상수 확인
- [x] 상품구성 및 가이드북 새 창의 세로 크기를 기존 대비 2배로 조정
- [x] 구문 검증 후 Review 기록

## Review - Product Guidebook Window Height
- `login_page.py`에서 `PRODUCT_GUIDE_WINDOW_HEIGHT`를 `210`에서 `420`으로 조정해 상품구성 및 가이드북 새 창의 세로 크기를 2배로 늘림.
- 기존 레이아웃 로그에 실제 창 크기(`940x420`)를 함께 남기도록 보강함.
- 검증: `python3 -m py_compile login_page.py` 통과. 실제 GUI 수동 클릭 확인은 이번 턴에서 실행하지 않음.

## Task - Product Guidebook Window
- [x] 로그인 가이드 섹션의 문구와 버튼명 변경 범위를 확인
- [x] `login_page.py`에서 가이드 문구를 `📝상품구성 및 가이드북 리스트`, 버튼명을 `📝상품구성 및 가이드북`으로 변경
- [x] 기존 PDF 직접 열기 대신 별도 새 창을 띄우는 LTS 가이드북 전용 `Toplevel` 골격과 로그 추가
- [x] 구문 검증 후 Review 기록

## Review - Product Guidebook Window
- `login_page.py`의 세 번째 가이드 안내 문구를 `📝상품구성 및 가이드북 리스트`, 해당 버튼 라벨을 `📝상품구성 및 가이드북`으로 변경함.
- 기존 `LTS 가이드북` PDF 직접 열기 로직을 제거하고, `ProductGuidebookWindow`라는 별도 `Toplevel` 창 골격으로 전환함. 현재 창 내부는 다음 작업에서 요소를 채울 수 있도록 빈 컨테이너만 두고 로그를 남기도록 구성함.
- `LoginPage`에서 새 창 인스턴스를 재사용하도록 참조와 닫기 처리, 배경 토글 연동을 추가함.
- 검증: `python3 -m py_compile login_page.py` 통과. 실제 Tkinter 수동 클릭 확인은 이번 턴에서 실행하지 않음.

## Task - DCA Guide PDF Link
- [x] 로그인 페이지와 메인 페이지의 DCA 버튼 연결 지점 확인
- [x] 두 화면의 DCA 버튼이 `image/login_page/dca.pdf`를 열도록 수정하고 로그 반영
- [x] 구문 검증 후 Review 기록

## Review - DCA Guide PDF Link
- `login_page.py`의 상품구성 및 가이드북 창에서 `🔄DCA 전략지표 가이드문서` 슬롯이 더 이상 placeholder 안내창을 띄우지 않고, 공통 `_open_guide_pdf()` 경로를 통해 `image/login_page/dca.pdf`를 열도록 연결함.
- `trade_page.py`의 메인 화면 DCA 버튼도 기존 롱/숏 버튼과 같은 `_open_strategy_guide_pdf()` 경로를 사용해 `dca.pdf`를 열도록 맞췄고, 클릭/파일 없음/열기 성공/실패 로그 형식도 동일하게 유지함.
- 검증: `python3 -m py_compile login_page.py trade_page.py` 통과. 실제 GUI 클릭 확인은 이번 턴에서 실행하지 않음.

## Task - Wallet Container Vertical Raise
- [x] 지갑잔고 컨테이너와 내부 요소의 현재 세로 배치 좌표 확인
- [x] 컨테이너와 내부 요소를 현재 기준 약 30% 위로 올리도록 공통 오프셋 적용 및 로그 반영
- [x] 구문 검증 후 Review 기록

## Review - Wallet Container Vertical Raise
- `trade_page.py`에서 기존 지갑 컨테이너와 `START`/`STOP` 버튼의 원본 좌표를 `*_BASE_RECT` 상수로 분리한 뒤, 지갑 컨테이너 시작 높이(`263`)의 약 30%인 `78px`를 공통 `WALLET_VERTICAL_SHIFT`로 계산해 전체 지갑 블록을 위로 이동시킴.
- 내부 텍스트 배치는 기존처럼 컨테이너 상단과 버튼 상단 사이를 기준으로 계산되므로, 컨테이너와 버튼을 같이 올린 것만으로 지갑잔고/레버리지/현재 구동상태 텍스트도 함께 위로 이동함.
- 초기화 로그에 `wallet_vertical_shift`와 `wallet_vertical_shift_ratio`를 추가해 현재 배치 오프셋이 로그로 남도록 조정함.
- 검증: `python3 -m py_compile trade_page.py` 통과. 실제 GUI 수동 확인은 이번 턴에서 실행하지 않음.

## Task - Channel Info Container
- [x] 지갑잔고 아래 새 컨테이너 위치와 제목 바 스타일 확인
- [x] 지갑잔고 아래에 `채널정보` 제목의 새 컨테이너 추가 및 로그 반영
- [x] 구문 검증 후 Review 기록

## Review - Channel Info Container
- `trade_page.py`에 `CHANNEL_INFO_TOP_GAP = 24`를 두고, 지갑잔고 컨테이너 하단에서 24px 아래부터 시작해 좌우 폭은 지갑잔고와 맞추고 하단은 기존 좌측 패널 하단선(`TABLE_RECT[3]`)에 맞춘 `채널정보` 패널을 추가함.
- 제목 바는 기존 `전략 가이드북` 패널과 같은 색상/테두리/폰트를 쓰도록 `_draw_titled_panel()` 공통 헬퍼로 묶었고, 이 헬퍼를 `전략 가이드북`과 새 `채널정보` 컨테이너에 같이 적용함.
- 초기화 로그에 `channel_info_panel=title_only`와 `channel_info_top_gap=24`를 추가해 새 컨테이너 배치 상태가 로그로 남도록 조정함.
- 검증: `python3 -m py_compile trade_page.py` 통과. 실제 GUI 수동 확인은 이번 턴에서 실행하지 않음.

# todo

## Task
- [x] 로그인 이후 지갑잔고 컨테이너에 현재 구동상태 행 추가
- [x] 기존 `_trade_state` 값을 사용해 `실행중`/`중단됨` 문구 표시 및 관련 로그 반영
- [x] 변경 사항 검토 및 검증 결과 기록

## Review
- `trade_page.py` 지갑잔고 컨테이너에 `현재 구동상태` 행을 추가했고, 표시값은 `_trade_state` 기준으로 `실행중`/`중단됨`으로 노출되도록 연결함.
- 초기 진입 로그와 상태 전환 로그에 표시 문구를 함께 남기도록 조정함.
- 검증: `python3 -m py_compile trade_page.py` 통과. 전체 GUI 수동 확인은 이번 턴에서 실행하지 않음.

## Task - Wallet Text Centering
- [x] 지갑잔고 컨테이너 내부 텍스트를 START/STOP 버튼 제외 영역 기준으로 중앙 정렬
- [x] 중앙 정렬 레이아웃 반영 사실을 로그에 남기기
- [x] 변경 사항 검토 및 검증 결과 기록

## Review - Wallet Text Centering
- `trade_page.py`에서 지갑잔고, 레버리지, 현재 구동상태 3줄을 하나의 텍스트 블록으로 보고 START/STOP 버튼 위 남는 영역의 수직 중앙에 배치하도록 계산식을 변경함.
- 초기 진입 로그에 `wallet_text_layout=centered_above_buttons`를 추가해 중앙 정렬 레이아웃 적용 사실을 남기도록 조정함.
- 검증: `python3 -m py_compile trade_page.py` 통과. 전체 GUI 수동 확인은 이번 턴에서 실행하지 않음.

## Task - Wallet Text Offset
- [x] 지갑잔고 컨테이너 텍스트 블록을 현재 위치에서 소폭 아래로 이동
- [x] 조정된 오프셋 정보를 로그에 반영
- [x] 변경 사항 검토 및 검증 결과 기록

## Review - Wallet Text Offset
- `trade_page.py`에 `WALLET_TEXT_CENTER_OFFSET_Y = 10` 상수를 추가하고, 지갑잔고 텍스트 블록의 중앙 정렬 기준점에 해당 오프셋을 더해 전체 텍스트를 소폭 아래로 내림.
- 초기 진입 로그에 `wallet_text_center_offset_y=10`을 추가해 적용된 미세 조정값이 로그에 남도록 조정함.
- 검증: `python3 -m py_compile trade_page.py` 통과. 전체 GUI 수동 확인은 이번 턴에서 실행하지 않음.

## Task - SWING_PINE Input Visibility
- [x] 다운로드 폴더의 `swing_pine.txt` 입력 항목 구조 확인
- [x] 설정창에는 이모티콘 관련 입력만 남기고 나머지 옵션은 숨기도록 수정
- [x] 변경 내용과 검증 결과를 Review에 기록

## Review - SWING_PINE Input Visibility
- `/mnt/c/Users/dudfh/Downloads/swing_pine.txt`에서 사용자 입력을 `표시 이모티콘` 1개만 남기고, RSI 길이/임계값/로그 활성화는 상수로 고정해 설정창 노출을 제거함.
- `plotshape()` 텍스트는 입력값 기반 동적 문자열을 받을 수 없어, 차트 표시는 `label.new()` 기반 이모티콘 출력으로 변경하고 `max_labels_count=500`을 명시함.
- 로그 코드는 유지하되 `ENABLE_LOGS = false` 상수로 숨겼고, 디버그용 `plot()`은 `editable=false`로 조정해 추가 설정 노출을 줄임.
- 검증: `rg -n "input\\.|input\\(" /mnt/c/Users/dudfh/Downloads/swing_pine.txt` 결과 입력 정의가 `표시 이모티콘` 1개만 남은 것을 확인함. Pine 컴파일러는 현재 환경에 없어 TradingView 편집기에서의 최종 로드는 이번 턴에서 직접 실행하지 못함.

## Task - Channel Info Items
- [x] `trade_page.py`의 `채널정보` 패널 내부 배치와 기존 `전략 가이드북` 버튼 구조 확인
- [x] `채널정보` 패널에 요청한 3개 채널 라벨/버튼과 URL 연결, 관련 로그 추가
- [x] 변경 사항 검토 및 검증 결과 기록

## Review - Channel Info Items
- `trade_page.py`의 `채널정보` 패널에 세로 3단 구조의 채널 항목을 추가했고, 각 항목은 제목 텍스트와 동일 문구의 버튼으로 구성함. 항목은 `📈롱포지션 알림채널`, `📉숏포지션 알림채널`, `💥숏포지션 리스크관리 채널` 순서로 배치함.
- 각 버튼은 전달받은 텔레그램 URL로 연결되도록 공통 `_handle_channel_info_link()`와 `_open_url()` 경로를 추가했고, 클릭/오픈 성공/오픈 실패 로그가 모두 남도록 조정함.
- 초기화 로그도 `channel_info_panel=telegram_channels`와 `channel_info_item_count=3`으로 갱신해 현재 패널 상태가 로그에 기록되도록 맞춤.
- 검증: `python3 -m py_compile trade_page.py` 통과. 실제 GUI 클릭 동작은 이번 턴에서 직접 실행하지 않음.

## Task - Channel Info Layout Correction
- [x] `채널정보` 항목을 가로 기준으로 재배치할 수 있는 좌표 구조 재조정
- [x] 세 번째 리스크관리 채널 URL을 새 주소로 교체하고 로그 메타데이터 반영
- [x] 구문 검증 후 Review 기록

## Review - Channel Info Layout Correction
- `trade_page.py`의 `채널정보` 버튼 좌표를 세로 3단에서 가로 기준 배치로 조정했고, 패널 폭에 맞춰 상단 2개(`📈롱포지션 알림채널`, `📉숏포지션 알림채널`)와 하단 중앙 1개(`💥숏포지션 리스크관리 채널`) 구조로 재배치함.
- 채널 라벨과 버튼 글꼴은 `table_header` 기준으로 맞춰 좁은 폭에서도 문구가 더 안정적으로 들어가게 조정했고, 초기화 로그에 `channel_info_layout=top2_bottom1`를 추가해 현재 레이아웃 구성이 기록되도록 함.
- 세 번째 `💥숏포지션 리스크관리 채널` 링크는 `https://t.me/+GZhGHaQBVmhkMmRl`로 교체함.
- 검증: `python3 -m py_compile trade_page.py` 통과. 실제 GUI 클릭/배치 확인은 이번 턴에서 직접 실행하지 않음.

## Task - Channel Info Official Notice Button
- [x] 하단 행 기준으로 리스크관리 채널 위치를 왼쪽으로 보정하고 새 공지채널 슬롯 확보
- [x] `🔈LEVIA 공식 공지채널` 버튼과 링크 추가, 로그 메타데이터 갱신
- [x] 구문 검증 후 Review 기록

## Review - Channel Info Official Notice Button
- `trade_page.py`의 `채널정보` 영역을 2열 2행 기준으로 재정렬했고, 하단 행에서 `💥숏포지션 리스크관리 채널`을 좌측 슬롯으로 이동시킨 뒤 우측 슬롯에 `🔈LEVIA 공식 공지채널`을 추가함.
- 새 공지채널은 기존 채널 버튼들과 동일한 공통 데이터 구조(`CHANNEL_INFO_ITEMS`)와 클릭 핸들러를 사용해 `https://t.me/+7q67SFWYCTU1MzJl`로 연결되도록 구성함.
- 초기화 로그는 `channel_info_item_count=4`, `channel_info_layout=2x2` 기준으로 남도록 갱신함.
- 검증: `python3 -m py_compile trade_page.py` 통과. 실제 GUI 클릭/배치 확인은 이번 턴에서 직접 실행하지 않음.

## Task - Manager Connection Panel
- [x] 지갑잔고 컨테이너와 내부 요소를 위로 재배치하고 우측 패널 세로 스택 좌표 재구성
- [x] `관리자 연결` 컨테이너와 `관리자 연락처 A/B` 버튼, 링크, 로그 추가
- [x] `채널정보` 컨테이너 위치/버튼 좌표를 새 구조에 맞게 조정하고 구문 검증 후 Review 기록

## Review - Manager Connection Panel
- `trade_page.py`에서 지갑잔고 블록의 세로 이동 비율을 `0.47`로 높여 컨테이너와 내부 텍스트, `START`/`STOP` 버튼이 모두 함께 위로 이동하도록 조정함.
- 우측 패널을 `지갑잔고 -> 관리자 연결 -> 채널정보` 3단 스택으로 재구성했고, `관리자 연결` 패널은 지갑잔고 바로 아래에 별도 제목 바와 함께 추가함.
- `관리자 연결` 패널에는 `관리자 연락처 A`, `관리자 연락처 B` 항목을 2열로 배치했고, 각 버튼은 `https://t.me/crypto_LEVI9`, `https://t.me/LEVI_kimbob`로 연결되도록 공통 외부 링크 오픈 경로와 로그를 추가함.
- 기존 `채널정보` 패널은 새 관리자 패널 아래로 내려가도록 시작 좌표와 버튼 좌표를 다시 맞췄고, 초기화 로그에 `manager_connection_panel=contacts`, `manager_connection_item_count=2`, `manager_connection_top_gap=14`, `manager_connection_height=96`를 추가함.
- 검증: `python3 -m py_compile trade_page.py` 통과. 실제 GUI 클릭/배치 확인은 이번 턴에서 직접 실행하지 않음.

## Task - Wallet Manager Vertical Tuning
- [x] 지갑잔고와 관리자 연결 패널을 추가 상향 이동하도록 좌표 미세 조정
- [x] 관리자 연결 제목 바와 내부 요소가 겹치지 않도록 내부 여백/버튼 위치 보정
- [x] 구문 검증 후 Review 기록

## Review - Wallet Manager Vertical Tuning
- `trade_page.py`에서 지갑잔고 블록의 세로 이동 비율을 `0.52`로 다시 올려 컨테이너, 내부 텍스트, `START`/`STOP` 버튼 전체가 이전보다 조금 더 위로 이동하도록 조정함.
- `관리자 연결` 패널은 지갑잔고 바로 아래 간격을 `14`에서 `8`로 줄여 함께 더 위로 올렸고, 패널 높이는 `96`에서 `110`으로 늘려 내부 여백을 확보함.
- `관리자 연락처 A/B` 버튼은 `y=548~580`으로 내려 배치해 제목 바(`관리자 연결`)와 라벨/버튼이 시각적으로 겹치지 않도록 보정함.
- 검증: `python3 -m py_compile trade_page.py` 통과. 실제 GUI 배치 확인은 이번 턴에서 직접 실행하지 않음.

## Task - Manager Panel Inner Alignment Fix
- [x] 관리자 연결 패널 내부 라벨/버튼이 컨테이너 하단 밖으로 벗어나는 좌표 문제 수정
- [x] 제목 바와 겹치지 않으면서 패널 내부 상단 쪽으로 함께 올리도록 보정
- [x] 구문 검증 후 Review 기록

## Review - Manager Panel Inner Alignment Fix
- `trade_page.py`의 `관리자 연락처 A/B` 버튼 좌표를 `y=548~580`에서 `y=526~558`로 올려 패널 하단 밖으로 튀어나오던 상태를 바로잡음.
- 라벨은 기존 공통 오프셋(`button_y1 - 16`)을 그대로 쓰므로 버튼과 함께 같이 올라가며, 제목 바 아래 여백은 유지한 채 관리자 패널 내부 상단 쪽으로 정렬되도록 맞춤.
- 검증: `python3 -m py_compile trade_page.py` 통과. 실제 GUI 배치 확인은 이번 턴에서 직접 실행하지 않음.

## Task - Channel Info Title Offset Fix
- [x] `채널정보` 제목 텍스트가 내부 라벨을 침범하지 않도록 전용 오프셋 구조 추가
- [x] `채널정보` 제목만 소폭 위로 보정하고 초기화 로그 메타데이터 반영
- [x] 구문 검증 후 Review 기록

## Review - Channel Info Title Offset Fix
- `trade_page.py`에 `CHANNEL_INFO_TITLE_OFFSET_Y = -4` 상수를 추가하고, 공통 `_draw_titled_panel()`이 패널별 `title_offset_y`를 받을 수 있게 확장함.
- `채널정보` 패널만 해당 오프셋을 넘기도록 연결해 제목 텍스트를 소폭 위로 올렸고, 내부 라벨과의 시각적 간섭을 줄이도록 조정함.
- 초기화 로그에 `channel_info_title_offset_y=-4`를 추가해 현재 제목 보정값이 함께 기록되도록 맞춤.
- 검증: `python3 -m py_compile trade_page.py` 통과. 실제 GUI 배치 확인은 이번 턴에서 직접 실행하지 않음.

## Task - Channel Info Title Bar Height Fix
- [x] `채널정보` 패널은 제목 텍스트 이동 대신 제목 바 하단선을 올리는 방식으로 교정
- [x] `채널정보` 전용 title height 적용 및 이전 text offset 제거
- [x] 구문 검증 후 Review 기록

## Review - Channel Info Title Bar Height Fix
- `trade_page.py`에서 `채널정보` 패널 전용 `CHANNEL_INFO_TITLE_HEIGHT = 28` 상수를 추가해, 제목 바 하단선이 기존 공통 높이(`34`)보다 위로 올라가도록 조정함.
- 이전에 넣었던 `CHANNEL_INFO_TITLE_OFFSET_Y` 방식은 제거했고, 공통 `_draw_titled_panel()`은 패널별 `title_height`만 받도록 정리해 `채널정보`에는 제목 바 높이 축소 방식만 적용되게 맞춤.
- 초기화 로그도 `channel_info_title_height=28`로 갱신해 현재 보정값이 남도록 반영함.
- 검증: `python3 -m py_compile trade_page.py` 통과. 실제 GUI 배치 확인은 이번 턴에서 직접 실행하지 않음.

## Task - Version 5.0.0 Update Build
- [x] 자동업데이트 관련 버전/메타데이터 경로와 현재 워크트리 상태 확인
- [x] 버전을 5.0.0으로 올리고 새 런처 파일명 기준으로 업데이트 메타데이터 조정
- [x] Windows PyInstaller로 런처/업데이터 재빌드 후 루트 exe 반영
- [x] 실제 exe SHA256을 `version.json`에 반영하고 메타데이터 검증 수행
- [x] 검증 결과와 review를 문서에 기록

## Review - Version 5.0.0 Update Build
- 자동업데이트 로직 확인 결과, `main.py`는 `version.json`에서 `min_version`, `updater_url`, `updater_sha256`, `app_url`, `app_sha256`를 읽어 모두 검증한 뒤 업데이트를 진행하므로 이번 릴리스는 메타데이터와 루트 EXE 파일이 반드시 같이 맞아야 했음.
- `config.py`의 `VERSION`을 `5.0.0`으로 올렸고, `version.json`의 `min_version`과 `app_url`을 `LTS V5.0.0.exe` 기준으로 변경한 뒤 실제 빌드 산출물 SHA256을 반영함.
- Windows Python 3.10 + PyInstaller 6.17.0으로 `C:/Users/dudfh/AppData/Local/Programs/Python/Python310/python.exe build.py --target all`을 실행해 `dist/LTS V5.0.0.exe`, `dist/LTS-Updater.exe`를 생성했고, 이를 저장소 루트의 `LTS V5.0.0.exe`, `LTS-Updater.exe`로 반영함.
- 최종 SHA256은 런처 `d1fd35ff944195960bc0008a6b9081021f95f626c296fd8ede91bc80f6cdb444`, 업데이터 `75e877019e40bdbc4d5e3c827c28f5b0d9d281877d958bc6077d80029ccffdf8`이며, `update_security.extract_sha256_from_metadata()`와 `verify_file_sha256()` 기준으로 `version.json` 메타데이터 해석 및 실제 파일 검증을 모두 통과함.
- 검증: `python3 -m py_compile main.py updater.py build.py update_security.py config.py` 통과. `python3 -m unittest tests.test_update_security` 통과.
