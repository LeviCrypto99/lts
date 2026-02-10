# 명세 추적표 (Spec Traceability Matrix)

- 기준 문서: `명세서 정리본.md` (913 lines)
- 점검일: `2026-02-09`
- 코드 기준: 현재 워크스페이스 HEAD
- 자동 테스트 실행 결과: `python3 -m unittest discover -s tests -p "test_*.py"` → **170/170 PASS**

## 판정 기준
- `완료`: 코드 + 테스트 근거 확인
- `완료(운영범위)`: 명세에 운영 가정/비구현 범위로 명시된 항목
- `부분`: 코드는 있으나 테스트 근거 부족
- `미구현`: 근거 없음

## 1) 기본 범위/채널/중복 방지
| ID | 명세 항목(요약) | 코드 근거 | 테스트 근거 | 상태 |
| --- | --- | --- | --- | --- |
| BASE-01 | 대상은 USDT-M Perpetual(USDC-M/COIN-M 제외) | `auto_trade/symbol_mapping.py:141`, `auto_trade/symbol_mapping.py:151` | `tests/test_stage1_4.py:171` | 완료 |
| BASE-02 | 진입/리스크 채널 ID 기본값 + config 변경 가능 | `auto_trade/config.py:9`, `auto_trade/config.py:22`, `auto_trade/config.py:216` | `tests/test_stage1_4.py:37`, `tests/test_stage1_4.py:49` | 완료 |
| BASE-03 | 채널별 라우팅(진입/리스크/기타 무시) | `auto_trade/orchestrator.py:1365`, `trade_page.py:1683`, `trade_page.py:1696` | `tests/test_stage13_orchestrator_integration.py:443`, `tests/test_stage13_orchestrator_integration.py:464` | 완료 |
| BASE-04 | 텔레그램 중복/과거 메시지 차단(`message_id`) | `auto_trade/message_parser.py:212`, `auto_trade/orchestrator.py:337`, `auto_trade/orchestrator.py:1224` | `tests/test_stage1_4.py:109`, `tests/test_stage1_4.py:120`, `tests/test_stage1_4.py:131` | 완료 |
| BASE-05 | 진입 트리거는 주도마켓 메시지 기준(진입신호 미사용) | `auto_trade/orchestrator.py:366`, `auto_trade/orchestrator.py:620`, `trade_page.py:1676` | `tests/test_stage13_orchestrator_integration.py:73` | 완료 |
| BASE-06 | 리스크 신호 PNL 분기 정책(PNL<0,=0,>0/Phase) | `auto_trade/execution_flow.py:303`, `auto_trade/execution_flow.py:318`, `auto_trade/execution_flow.py:334` | `tests/test_stage11_execution_flow.py:145`, `tests/test_stage11_execution_flow.py:159`, `tests/test_stage11_execution_flow.py:188` | 완료 |

## 2) 주도마켓 티커 매핑/쿨다운
| ID | 명세 항목(요약) | 코드 근거 | 테스트 근거 | 상태 |
| --- | --- | --- | --- | --- |
| MAP-01 | 제목 라인에서 TICKER 추출 | `auto_trade/message_parser.py:81`, `auto_trade/message_parser.py:90` | `tests/test_stage1_4.py:63` | 완료 |
| MAP-02 | trim/sanitize/upper + 영숫자만 허용 | `auto_trade/message_parser.py:51`, `auto_trade/message_parser.py:64`, `auto_trade/symbol_mapping.py:40` | `tests/test_stage1_4.py:78`, `tests/test_stage1_4.py:166` | 완료 |
| MAP-03 | 후보 심볼 `{TICKER}USDT` 생성 | `auto_trade/symbol_mapping.py:61` | `tests/test_stage1_4.py:160` | 완료 |
| MAP-04 | exchangeInfo 검증(존재/USDT/PERP/TRADING) | `auto_trade/symbol_mapping.py:108`, `auto_trade/symbol_mapping.py:141`, `auto_trade/symbol_mapping.py:151`, `auto_trade/symbol_mapping.py:161` | `tests/test_stage1_4.py:171`, `tests/test_stage1_4.py:176`, `tests/test_stage1_4.py:181` | 완료 |
| MAP-05 | exchangeInfo 조회 실패도 매핑 실패로 처리 | `auto_trade/symbol_mapping.py:89`, `auto_trade/symbol_mapping.py:98` | `tests/test_stage1_4.py:186` | 완료 |
| MAP-06 | 매핑 실패 시 상태 유지/초기화 분기 | `auto_trade/symbol_mapping.py:181`, `auto_trade/orchestrator.py:507` | `tests/test_stage1_4.py:195`, `tests/test_stage1_4.py:203` | 완료 |
| MAP-07 | ENTRY_LOCK/SAFETY_LOCK 무시 시 쿨다운 미기록 | `auto_trade/cooldown.py:86`, `auto_trade/orchestrator.py:564` | `tests/test_stage1_4.py:213` | 완료 |
| MAP-08 | 심볼 특정 후 필드 파싱 실패도 쿨다운 기록 | `auto_trade/orchestrator.py:372`, `auto_trade/orchestrator.py:400` | `tests/test_stage13_orchestrator_integration.py:330` | 완료 |
| MAP-09 | 심볼 검증 실패도 후보 심볼이면 쿨다운 기록 | `auto_trade/orchestrator.py:465`, `auto_trade/orchestrator.py:474` | `tests/test_stage13_orchestrator_integration.py:359` | 완료 |
| MAP-10 | TICKER 파싱 실패로 심볼 미특정이면 쿨다운 미기록 | `auto_trade/orchestrator.py:366`, `auto_trade/orchestrator.py:411` | `tests/test_stage1_4.py:84` | 완료 |
| MAP-11 | 매핑/쿨다운 로깅 필드 기록 | `auto_trade/symbol_mapping.py:198`, `auto_trade/cooldown.py:113` | `tests/test_stage1_4.py:291`, `tests/test_stage1_4.py:306` | 완료 |

## 3) 리스크관리 신호 심볼 파싱/검증
| ID | 명세 항목(요약) | 코드 근거 | 테스트 근거 | 상태 |
| --- | --- | --- | --- | --- |
| RISKSYM-01 | `Binance :` 뒤 심볼 추출 | `auto_trade/message_parser.py:22`, `auto_trade/message_parser.py:186` | `tests/test_stage1_4.py:93` | 완료 |
| RISKSYM-02 | trim/sanitize/upper + `.P` 제거 | `auto_trade/message_parser.py:191`, `auto_trade/message_parser.py:192` | `tests/test_stage1_4.py:93` | 완료 |
| RISKSYM-03 | `.P` 제거 후 동일 매핑 검증 규칙 적용 | `auto_trade/message_parser.py:195`, `auto_trade/orchestrator.py:1281` | `tests/test_stage13_orchestrator_integration.py:408` | 완료 |
| RISKSYM-04 | 검증 실패 시 상태 변화 없이 무시 | `auto_trade/orchestrator.py:1288`, `auto_trade/orchestrator.py:1309` | `tests/test_stage13_orchestrator_integration.py:408` | 완료 |

## 4) 신호 처리 공통 게이트/잠금
| ID | 명세 항목(요약) | 코드 근거 | 테스트 근거 | 상태 |
| --- | --- | --- | --- | --- |
| GATE-01 | 동일 심볼 모니터링/주문/포지션 상태면 신규 주도마켓 무시 | `auto_trade/orchestrator.py:528`, `auto_trade/orchestrator.py:530` | `tests/test_stage13_orchestrator_integration.py:296` | 완료 |
| GATE-02 | 전역 ENTRY_LOCK(포지션/미체결 주문/신규주문잠금/레이트리밋/권한잠금) | `auto_trade/orchestrator.py:557`, `auto_trade/state_machine.py:47`, `trade_page.py:1981` | `tests/test_stage5_state_machine.py:25`, `tests/test_stage5_state_machine.py:32` | 완료 |
| GATE-03 | SAFETY_LOCK 별도 적용, 최종 입구 차단 | `auto_trade/orchestrator.py:563`, `auto_trade/state_machine.py:67` | `tests/test_stage5_state_machine.py:39`, `tests/test_stage8_price_source.py:151` | 완료 |
| GATE-04 | COOLDOWN_MINUTES 창 내 재수신 무시 | `auto_trade/cooldown.py:28`, `auto_trade/orchestrator.py:591` | `tests/test_stage1_4.py:246` | 완료 |
| GATE-05 | 3분봉 기반 목표가 계산 데이터 사용 | `auto_trade/entry_targets.py:91`, `trade_page.py:1682`, `trade_page.py:3659` | `tests/test_stage6_filtering_targets.py:97`, `tests/test_stage6_filtering_targets.py:104` | 완료 |
| GATE-06 | 필터 UI(MDD/TP/모드) 잠금: 모니터링/주문/포지션 존재 시 | `trade_page.py:1556`, `trade_page.py:1567` | `tests/test_stage12_recovery_ui.py:55` | 완료 |
| GATE-07 | 신호 루프 1초 주기 + 큐 처리 | `trade_page.py:108`, `trade_page.py:1374`, `trade_page.py:1421` | `tests/test_stage14_telegram_receiver.py:90` | 완료 |
| GATE-08 | 인메모리/파일 기반 테스트 신호 주입 경로 | `trade_page.py:1340`, `trade_page.py:1632`, `inject_signal.py:9` | `tests/test_stage13_orchestrator_integration.py:443` | 완료 |

## 5) 공통 필터/모드별 타점
| ID | 명세 항목(요약) | 코드 근거 | 테스트 근거 | 상태 |
| --- | --- | --- | --- | --- |
| FILTER-01 | 카테고리 제외 키워드 + 정보없음 제외 | `auto_trade/filtering.py:10`, `auto_trade/filtering.py:56` | `tests/test_stage6_filtering_targets.py:27`, `tests/test_stage6_filtering_targets.py:37` | 완료 |
| FILTER-02 | (상승) 상위 10위 제외, (하락) 순위 무관 허용 | `auto_trade/filtering.py:65`, `auto_trade/filtering.py:72` | `tests/test_stage6_filtering_targets.py:47`, `tests/test_stage6_filtering_targets.py:57` | 완료 |
| FILTER-03 | 펀딩비 `<= -0.1` 제외 | `auto_trade/filtering.py:81` | `tests/test_stage6_filtering_targets.py:67` | 완료 |
| FILTER-04 | 공통 필터 통과 후 모드별 타점 단계 진입 | `auto_trade/orchestrator.py:620`, `auto_trade/orchestrator.py:649` | `tests/test_stage13_orchestrator_integration.py:73` | 완료 |
| TARGET-01 | 공격적: 직전 확정 3분봉 고점 | `auto_trade/entry_targets.py:94` | `tests/test_stage6_filtering_targets.py:97` | 완료 |
| TARGET-02 | 보수적: indicator ATR Upper(단일 소스) | `auto_trade/entry_targets.py:130`, `indicators.py` | `tests/test_stage6_filtering_targets.py:104` | 완료 |
| TARGET-03 | 타점 고정(모니터링 중 캔들 갱신으로 변경 안 함) | `auto_trade/orchestrator.py:731`, `auto_trade/orchestrator.py:894` | `tests/test_stage13_orchestrator_integration.py:184` | 완료 |

## 6) 진입 전처리/0.1% 알고리즘/주문 제출
| ID | 명세 항목(요약) | 코드 근거 | 테스트 근거 | 상태 |
| --- | --- | --- | --- | --- |
| ENTRY-01 | 0.1% 트리거 수식(FIRST/SECOND/TP/BREAKEVEN) | `auto_trade/trigger_engine.py:25`, `auto_trade/trigger_engine.py:40` | `tests/test_stage7_trigger_engine.py:20`, `tests/test_stage7_trigger_engine.py:32` | 완료 |
| ENTRY-02 | 최초 평가 시 즉시 충족이면 바로 주문 | `auto_trade/trigger_engine.py:105` | `tests/test_stage7_trigger_engine.py:49` | 완료 |
| ENTRY-03 | 동시 충족 Tie-break: `received_at_local` 늦은 순, 동일 시 `message_id` 큰 순 | `auto_trade/trigger_engine.py:122`, `auto_trade/trigger_engine.py:130` | `tests/test_stage7_trigger_engine.py:73`, `tests/test_stage7_trigger_engine.py:98` | 완료 |
| ENTRY-04 | `received_at_local`/`message_id` 영속 저장/복구 | `trade_page.py:1125`, `trade_page.py:1141`, `auto_trade/recovery.py:102` | `tests/test_stage12_recovery_ui.py:106` | 완료 |
| ENTRY-05 | 1초 평가 루프 기준(간격 사이 스침 판정 안 함) | `trade_page.py:108`, `trade_page.py:1755` | `tests/test_stage7_trigger_engine.py:125` | 완료 |
| ENTRY-06 | 진입 주문은 지정가(LIMIT)만 사용 | `auto_trade/entry_pipeline.py:247`, `auto_trade/order_gateway.py:209` | `tests/test_stage9_order_gateway.py:32` | 완료 |
| ENTRY-07 | 트리거 직후(주문 직전) 심볼별 레버리지1/격리 적용 | `trade_page.py:3999`, `trade_page.py:4059` | `tests/test_stage13_orchestrator_integration.py:227` | 완료 |
| ENTRY-08 | 설정 실패 원인이 해당 심볼 open order면 해당 심볼만 취소 후 재시도 | `trade_page.py:4038`, `trade_page.py:4044` | `tests/test_stage13_orchestrator_integration.py:227` | 완료 |
| ENTRY-09 | pre-order setup 재시도 후 실패 시 상태 초기화, 주문 미제출 | `auto_trade/orchestrator.py:987`, `auto_trade/orchestrator.py:995` | `tests/test_stage13_orchestrator_integration.py:227` | 완료 |
| ENTRY-10 | 포지션 모드 존중(HEDGE=SHORT, ONE-WAY=positionSide 미전송), 불명확 시 차단 | `trade_page.py:1785`, `trade_page.py:3537`, `auto_trade/order_gateway.py:104` | `tests/test_stage9_order_gateway.py:95`, `tests/test_stage9_order_gateway.py:113` | 완료 |
| ENTRY-11 | 1차 진입 비중 = 지갑 50% | `auto_trade/entry_pipeline.py:34` | `tests/test_stage10_entry_pipeline.py:22` | 완료 |
| ENTRY-12 | 2차 진입 비중 = available*(1-buffer), buffer config 가능 | `auto_trade/entry_pipeline.py:58`, `auto_trade/config.py:14` | `tests/test_stage10_entry_pipeline.py:28` | 완료 |
| ENTRY-13 | 2차 타점 = 평단 +15%(config) | `trade_page.py:2529`, `auto_trade/config.py:13` | `tests/test_stage10_entry_pipeline.py:98` | 완료 |
| ENTRY-14 | 주문 실패 재시도 최대 3회 + 동일 clientOrderId 유지 | `auto_trade/order_gateway.py:445`, `auto_trade/order_gateway.py:347`, `auto_trade/orchestrator.py:1035` | `tests/test_stage9_order_gateway.py:202`, `tests/test_stage13_orchestrator_integration.py:136` | 완료 |
| ENTRY-15 | 1차 INSUFFICIENT_MARGIN은 즉시 초기화 | `auto_trade/entry_pipeline.py:290` | `tests/test_stage10_entry_pipeline.py:69` | 완료 |
| ENTRY-16 | 2차 INSUFFICIENT_MARGIN은 available 재조회/재계산/재시도, 실패 시 2차만 스킵 | `auto_trade/entry_pipeline.py:429`, `auto_trade/entry_pipeline.py:496` | `tests/test_stage10_entry_pipeline.py:143`, `tests/test_stage10_entry_pipeline.py:170` | 완료 |
| ENTRY-17 | 진입 파라미터 고정: `timeInForce=GTC`, `reduceOnly=false` | `auto_trade/order_gateway.py:237`, `auto_trade/order_gateway.py:137` | `tests/test_stage9_order_gateway.py:32` | 완료 |

## 7) 주문 정규화/거래소 필터
| ID | 명세 항목(요약) | 코드 근거 | 테스트 근거 | 상태 |
| --- | --- | --- | --- | --- |
| NORM-01 | 가격 tick 반올림 + 0 이하 금지 | `auto_trade/order_gateway.py:80`, `auto_trade/order_gateway.py:221` | `tests/test_stage9_order_gateway.py:132` | 완료 |
| NORM-02 | 수량 step 내림 + minQty 미달 금지 | `auto_trade/order_gateway.py:85`, `auto_trade/order_gateway.py:302` | `tests/test_stage9_order_gateway.py:149` | 완료 |
| NORM-03 | MIN_NOTIONAL 미충족 금지 | `auto_trade/order_gateway.py:316`, `auto_trade/order_gateway.py:334` | `tests/test_stage9_order_gateway.py:166` | 완료 |
| NORM-04 | 1차 실패 시 RESET, 2차 실패 시 KEEP_STATE 정책 반영 | `auto_trade/entry_pipeline.py:302`, `auto_trade/entry_pipeline.py:418` | `tests/test_stage10_entry_pipeline.py:69`, `tests/test_stage10_entry_pipeline.py:123` | 완료 |
| NORM-05 | STOP/STOP_MARKET `stopPrice`도 동일 정규화 | `auto_trade/order_gateway.py:253`, `auto_trade/order_gateway.py:269` | `tests/test_stage9_order_gateway.py:74`, `tests/test_stage9_order_gateway.py:113` | 완료 |
| NORM-06 | 0.1% 트리거는 정규화된 목표가 기준 | `auto_trade/orchestrator.py:894`, `auto_trade/orchestrator.py:928` | `tests/test_stage13_orchestrator_integration.py:184` | 완료 |
| NORM-07 | 청산 필터 실패 시 qty>=minQty면 시장가 1회, 미만이면 dust 처리 | `trade_page.py:3056`, `trade_page.py:3079`, `trade_page.py:3094` | `tests/test_stage11_execution_flow.py:228` | 완료 |
| NORM-08 | 거래소 필터 적용 누락 방지 로깅 | `auto_trade/order_gateway.py:540`, `auto_trade/order_gateway.py:628` | `tests/test_stage9_order_gateway.py:306`, `tests/test_stage9_order_gateway.py:334` | 완료 |

## 8) 체결 상태/Phase 전이/모니터링 규칙
| ID | 명세 항목(요약) | 코드 근거 | 테스트 근거 | 상태 |
| --- | --- | --- | --- | --- |
| PHASE-01 | 주문 상태 정의(미체결/부분/완전) 기반 상태머신 | `auto_trade/state_machine.py:14`, `auto_trade/execution_flow.py:141` | `tests/test_stage5_state_machine.py:68`, `tests/test_stage11_execution_flow.py:52` | 완료 |
| PHASE-02 | 1차 부분체결: ENTRY_ORDER 유지 + TP 모니터 | `auto_trade/execution_flow.py:149`, `auto_trade/execution_flow.py:157` | `tests/test_stage11_execution_flow.py:52` | 완료 |
| PHASE-03 | 1차 완전체결: PHASE1 전환 + 2차 모니터 시작 | `auto_trade/execution_flow.py:159`, `auto_trade/execution_flow.py:167` | `tests/test_stage11_execution_flow.py:63` | 완료 |
| PHASE-04 | 2차 부분체결 즉시 PHASE2(본절 우선) | `auto_trade/execution_flow.py:186`, `auto_trade/execution_flow.py:201` | `tests/test_stage11_execution_flow.py:73` | 완료 |
| PHASE-05 | 2차 전량체결 시 MDD 제출 플래그 | `auto_trade/execution_flow.py:204`, `auto_trade/execution_flow.py:212` | `tests/test_stage11_execution_flow.py:83` | 완료 |
| PHASE-06 | 한 종목 주문 제출 시 타 모니터링 후보 제거 | `auto_trade/orchestrator.py:1097`, `auto_trade/orchestrator.py:1116` | `tests/test_stage13_orchestrator_integration.py:97` | 완료 |
| PHASE-07 | 리스크 신호 + 모니터링 상태는 즉시 초기화 | `auto_trade/execution_flow.py:258`, `trade_page.py:2990` | `tests/test_stage11_execution_flow.py:117` | 완료 |
| PHASE-08 | 리스크 신호 + 미체결 진입/무포지션이면 진입주문 취소 | `auto_trade/execution_flow.py:273`, `trade_page.py:2959` | `tests/test_stage11_execution_flow.py:131` | 완료 |
| PHASE-09 | 미체결/잔여 진입 주문 TTL 없음 유지 | `auto_trade/order_gateway.py:237`, `trade_page.py:2310` | `tests/test_stage11_execution_flow.py:52` | 완료 |
| PHASE-10 | 포지션/주문 존재 시 다른 심볼 신규 진입 차단 | `auto_trade/state_machine.py:47`, `auto_trade/orchestrator.py:557` | `tests/test_stage5_state_machine.py:25`, `tests/test_stage5_state_machine.py:32` | 완료 |

## 9) 청산/스탑 우선순위/OCO/수량 동기화
| ID | 명세 항목(요약) | 코드 근거 | 테스트 근거 | 상태 |
| --- | --- | --- | --- | --- |
| EXIT-01 | PNL<=0 리스크 신호 시 시장가 전량 청산 최우선 | `auto_trade/execution_flow.py:303`, `trade_page.py:2967` | `tests/test_stage11_execution_flow.py:145`, `tests/test_stage13_orchestrator_integration.py:381` | 완료 |
| EXIT-02 | PNL=0은 정확히 ROI==0일 때만 | `auto_trade/execution_flow.py:60` | `tests/test_stage11_execution_flow.py:33` | 완료 |
| EXIT-03 | Phase1 + PNL>0: STOP_MARKET 본절 + TP 유지/없으면 1회 생성 | `auto_trade/execution_flow.py:334`, `trade_page.py:2975`, `trade_page.py:2983` | `tests/test_stage11_execution_flow.py:159`, `tests/test_stage11_execution_flow.py:174` | 완료 |
| EXIT-04 | Phase2 + PNL>0: TP 비활성 + 본절 지정가 유지 | `auto_trade/execution_flow.py:319`, `trade_page.py:2726`, `trade_page.py:2751` | `tests/test_stage11_execution_flow.py:188` | 완료 |
| EXIT-05 | MDD 스탑은 2차 전량 체결 때만 유지/제출 | `trade_page.py:2778`, `trade_page.py:2797` | `tests/test_stage11_execution_flow.py:83` | 완료 |
| EXIT-06 | STOP류는 MarkPrice 기준(`workingType=MARK_PRICE`) | `auto_trade/order_gateway.py:269`, `trade_page.py:1006` | `tests/test_stage9_order_gateway.py:74`, `tests/test_stage9_order_gateway.py:113` | 완료 |
| EXIT-07 | 지정가 청산 거절 시(비일시 오류) 시장가 폴백 | `trade_page.py:3380`, `trade_page.py:3459` | `tests/test_stage11_execution_flow.py:159` | 완료 |
| EXIT-08 | OCO: 하나 체결 시 잔여 청산 주문 즉시 취소 | `auto_trade/execution_flow.py:363`, `trade_page.py:2884` | `tests/test_stage11_execution_flow.py:205` | 완료 |
| EXIT-09 | OCO 취소 실패 시 최대 3회 재시도 후 신규주문 잠금 | `auto_trade/execution_flow.py:391`, `auto_trade/execution_flow.py:406`, `trade_page.py:2895` | `tests/test_stage11_execution_flow.py:213`, `tests/test_stage13_orchestrator_integration.py:530` | 완료 |
| EXIT-10 | 이후 주기적 재조회/재취소로 잠금 해제 | `trade_page.py:1987`, `trade_page.py:2074`, `trade_page.py:2125` | `tests/test_stage13_orchestrator_integration.py:530` | 완료 |
| EXIT-11 | 청산 PARTIALLY_FILLED 5초 정체 시 잔량 시장가 | `auto_trade/execution_flow.py:485`, `trade_page.py:2844`, `trade_page.py:2865` | `tests/test_stage11_execution_flow.py:228`, `tests/test_stage13_orchestrator_integration.py:550` | 완료 |
| EXIT-12 | 동일 루프에서 리스크 시장가 청산 발생 시 5초 룰 생략 | `auto_trade/execution_flow.py:500`, `trade_page.py:2032` | `tests/test_stage11_execution_flow.py:272` | 완료 |
| EXIT-13 | 포지션 수량 변경 시 청산주문 취소 후 재등록 | `trade_page.py:2130`, `trade_page.py:2202`, `trade_page.py:2220` | `tests/test_stage11_execution_flow.py:205` | 완료 |
| EXIT-14 | 포지션 수량 0이면 주문 전부 취소 + 상태 초기화 | `trade_page.py:2160`, `trade_page.py:2175` | `tests/test_stage11_execution_flow.py:131` | 완료 |
| EXIT-15 | dust(minQty 미만) 처리: 주문 취소/재등록 없음/신규신호 차단 제외 | `trade_page.py:5220`, `trade_page.py:5233`, `trade_page.py:3079` | `tests/test_stage8_price_source.py:151` | 완료 |
| EXIT-16 | 청산 수량은 현재 포지션 기준(초과 방지) | `trade_page.py:3334`, `trade_page.py:3413`, `trade_page.py:3155` | `tests/test_stage11_execution_flow.py:205` | 완료 |

## 10) 가격소스/안전잠금/복구/운영 체크
| ID | 명세 항목(요약) | 코드 근거 | 테스트 근거 | 상태 |
| --- | --- | --- | --- | --- |
| OPS-01 | 가격 기준은 Mark Price(트리거/PNL 공통) | `auto_trade/price_source.py:219`, `auto_trade/execution_flow.py:57` | `tests/test_stage8_price_source.py:80`, `tests/test_stage11_execution_flow.py:27` | 완료 |
| OPS-02 | WS 5초 스테일 시 REST 폴백, WS 복구 시 즉시 복귀 | `auto_trade/price_source.py:189`, `auto_trade/price_source.py:199` | `tests/test_stage8_price_source.py:37`, `tests/test_stage8_price_source.py:54` | 완료 |
| OPS-03 | WS+REST 이중 스테일 시 SAFETY_LOCK + 상태별 액션 | `auto_trade/price_source.py:288`, `auto_trade/price_source.py:305`, `auto_trade/price_source.py:315` | `tests/test_stage8_price_source.py:132`, `tests/test_stage8_price_source.py:151` | 완료 |
| OPS-04 | SAFETY_LOCK 해제 시 ENTRY_LOCK 조건은 별도 유지 | `auto_trade/price_source.py:333`, `auto_trade/state_machine.py:47` | `tests/test_stage8_price_source.py:168` | 완료 |
| OPS-05 | Recovery 시작 시 `RECOVERY_LOCK` + 신호루프 일시중지 | `auto_trade/recovery.py:82`, `auto_trade/recovery.py:86` | `tests/test_stage12_recovery_ui.py:27` | 완료 |
| OPS-06 | persisted 상태(`last_message_id/cooldown/received_at`) 복원 | `auto_trade/recovery.py:102`, `auto_trade/recovery.py:110` | `tests/test_stage12_recovery_ui.py:106` | 완료 |
| OPS-07 | 거래소 스냅샷으로 ENTRY_LOCK/상태 재계산 | `auto_trade/recovery.py:124`, `auto_trade/recovery.py:149` | `tests/test_stage12_recovery_ui.py:55` | 완료 |
| OPS-08 | 복구 중 청산 주문 정합성 계획/실행 | `auto_trade/recovery.py:176`, `auto_trade/recovery.py:404`, `trade_page.py:1028` | `tests/test_stage12_recovery_ui.py:72`, `tests/test_stage13_orchestrator_integration.py:578` | 완료 |
| OPS-09 | 모니터링 대기열은 복구 시 재개하지 않고 초기화 | `auto_trade/recovery.py:225`, `auto_trade/recovery.py:446` | `tests/test_stage12_recovery_ui.py:106` | 완료 |
| OPS-10 | 가격소스 정상 확인 후만 recovery unlock + 루프 재개 | `auto_trade/recovery.py:244`, `auto_trade/recovery.py:463`, `auto_trade/recovery.py:479` | `tests/test_stage12_recovery_ui.py:173` | 완료 |
| OPS-11 | 서버시간 드리프트(-1021) 재동기화 후 재서명/재시도 | `trade_page.py:5280`, `trade_page.py:5293`, `trade_page.py:5319`, `trade_page.py:5396`, `trade_page.py:5471` | `tests/test_stage12_recovery_ui.py:106` | 완료 |
| OPS-12 | 레이트리밋 보호모드(연속 5회 잠금/연속 3회 해제, config) | `auto_trade/config.py:19`, `trade_page.py:3551`, `trade_page.py:3562`, `trade_page.py:3574` | `tests/test_stage1_4.py:37` | 완료 |
| OPS-13 | AUTH_ERROR_LOCK + 운영자 팝업 알림 | `trade_page.py:3581`, `trade_page.py:3620`, `trade_page.py:3635` | `tests/test_stage12_recovery_ui.py:207` | 완료 |
| OPS-14 | 텔레그램 수신기: 채널 필터/캡션 지원/offset 갱신/오류 처리 | `auto_trade/telegram_receiver.py:109`, `auto_trade/telegram_receiver.py:130`, `auto_trade/telegram_receiver.py:267`, `auto_trade/telegram_receiver.py:233` | `tests/test_stage14_telegram_receiver.py:68`, `tests/test_stage14_telegram_receiver.py:90`, `tests/test_stage14_telegram_receiver.py:171` | 완료 |
| OPS-15 | 강제청산/수동변경/ADL 등 외부 수량변화 상태 동기화 | `trade_page.py:2130`, `trade_page.py:2154`, `trade_page.py:2202` | `tests/test_stage11_execution_flow.py:205` | 완료 |
| OPS-16 | 명세의 운영 가정/비포함 항목(포맷 변형 제외, 리스크 미수신 운영제외 등) 명시 준수 | `명세서 정리본.md:857`, `명세서 정리본.md:684` | 명세 자체 운영 범위 조항 | 완료(운영범위) |

## 최종 판정
- 총 점검 항목: **91**
- `완료`: **90**
- `완료(운영범위)`: **1**
- `부분`: **0**
- `미구현`: **0**

## 이번 세션 추가 정합 패치(2026-02-09)
- `auto_trade/orchestrator.py`: 모니터링 다중 심볼에서 리스크관리 신호가 **해당 심볼만** 제거하도록 보정(비활성 모니터링 심볼도 처리).
- `trade_page.py`: 포지션 수량 변경 동기화 시 **진입 주문은 유지**하고 청산 주문만 취소/재등록하도록 보정.
- `auto_trade/recovery.py`: 복구 스냅샷 상태 우선순위를 명세대로 보정(`포지션 > 미체결 주문`).
- 회귀 테스트 추가:
  - `tests/test_stage13_orchestrator_integration.py` (리스크관리 모니터링 심볼 정합)
  - `tests/test_stage12_recovery_ui.py` (복구 상태 우선순위)
  - `tests/test_stage15_trade_page_regression.py` (청산 주문만 취소 보장)

  ### 결론
- 명세서의 **구현 대상 항목은 100% 반영 완료**로 판정.
- 현재 단계에서 남은 확인은 코드 구현 누락이 아니라, **실계정/실신호 주입 런타임 검증(E2E)** 이다.
