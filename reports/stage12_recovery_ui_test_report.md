# Stage 12 Recovery/UI Test Report

- Generated at (UTC): `2026-02-07 09:07:11Z`
- Python: `3.12.3`
- Scope: recovery/restart sequence, `RECOVERY_LOCK` gating, signal-loop resume policy, `trade_page.py` Start/Stop integration

## Commands

```bash
python3 -m py_compile auto_trade/*.py trade_page.py tests/test_stage12_recovery_ui.py
python3 -m unittest -v tests/test_stage12_recovery_ui.py
python3 -m unittest -q tests/test_stage1_4.py tests/test_stage5_state_machine.py tests/test_stage6_filtering_targets.py tests/test_stage7_trigger_engine.py tests/test_stage8_price_source.py tests/test_stage9_order_gateway.py tests/test_stage10_entry_pipeline.py tests/test_stage11_execution_flow.py tests/test_stage12_recovery_ui.py
```

## Results

1. Stage 12 only (`tests/test_stage12_recovery_ui.py`)
- Total tests: `10`
- Passed: `10`
- Failed: `0`
- Errors: `0`
- Result: `OK`

2. Regression (Stage 1-12 combined)
- Total tests: `129`
- Passed: `129`
- Failed: `0`
- Errors: `0`
- Result: `OK`

## Verified Behaviors

- Recovery startup sequence executes fixed order:
  - `RECOVERY_LOCK=ON` -> persisted state restore -> exchange snapshot apply -> reconcile planning/execution -> monitoring queue clear -> price source check -> lock release
- Signal loop resume gate:
  - signal loop is resumed only when snapshot is loaded and price source is healthy
  - snapshot failure keeps `RECOVERY_LOCK` and keeps signal loop paused
- Entry lock recomputation:
  - snapshot `has_any_position` / `open_order_count` is mapped back to global entry-lock state
- Reconciliation planning:
  - no-position + open-orders snapshot creates cancel plan
  - position-present snapshot requires exit-order reconciliation path
- Structured logging wrappers include required fields:
  - `input`, `decision`, `result`, `state_transition`, `failure_reason`
