# Stage 14 Signal Loop Integration Report

- Generated at (UTC): `2026-02-07 09:22:10Z`
- Python: `3.12.3`
- Scope: remaining integration gaps (recovery step6 exit-order rebuild, TradePage signal-loop wiring, direct signal injection path)

## Commands

```bash
python3 -m py_compile auto_trade/*.py trade_page.py tests/test_stage12_recovery_ui.py tests/test_stage13_orchestrator_integration.py inject_signal.py
python3 -m unittest -q tests/test_stage12_recovery_ui.py tests/test_stage13_orchestrator_integration.py
python3 -m unittest -q tests/test_stage1_4.py tests/test_stage5_state_machine.py tests/test_stage6_filtering_targets.py tests/test_stage7_trigger_engine.py tests/test_stage8_price_source.py tests/test_stage9_order_gateway.py tests/test_stage10_entry_pipeline.py tests/test_stage11_execution_flow.py tests/test_stage12_recovery_ui.py tests/test_stage13_orchestrator_integration.py
```

## Results

1. Stage 12 + 13 targeted tests
- Total tests: `23`
- Passed: `23`
- Failed: `0`
- Errors: `0`
- Result: `OK`

2. Regression (Stage 1-13 combined)
- Total tests: `142`
- Passed: `142`
- Failed: `0`
- Errors: `0`
- Result: `OK`

## Implemented Integration

- Recovery reconcile planning now computes:
  - `cancel_symbols` (open orders without position)
  - `register_symbols` (positions without open orders)
- TradePage recovery reconcile now:
  - cancels unnecessary orders
  - re-registers required exit protection orders (STOP_MARKET + TAKE_PROFIT_MARKET closePosition)
  - keeps recovery lock on registration failure
- TradePage signal loop now:
  - consumes queued signals
  - routes signals into orchestrator (`process_telegram_message`)
  - runs trigger-entry cycle (`run_trigger_entry_cycle`)
- Direct signal injection path:
  - in-memory API: `TradePage.inject_test_signal(...)`
  - file inbox: `%TEMP%/LTS-auto-trade-signal-inbox.jsonl`
  - CLI helper: `inject_signal.py`

## Notes

- UI-driven live/E2E runtime verification (actual app run with manual signal injection) should be executed after launching `python main.py`.
