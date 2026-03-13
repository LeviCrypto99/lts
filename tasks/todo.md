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
