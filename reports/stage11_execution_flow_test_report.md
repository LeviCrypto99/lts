# Stage 11 Execution Flow Test Report

- Generated at (UTC): `2026-02-07 08:55:44Z`
- Python: `3.12.3`
- Scope: fill synchronization, phase transition, risk-management PNL branching, OCO mutual cancel, exit partial 5-second rule

## Commands

```bash
python3 -m py_compile auto_trade/*.py tests/test_stage11_execution_flow.py
python3 -m unittest -v tests/test_stage11_execution_flow.py
python3 -m unittest -q tests/test_stage1_4.py tests/test_stage5_state_machine.py tests/test_stage6_filtering_targets.py tests/test_stage7_trigger_engine.py tests/test_stage8_price_source.py tests/test_stage9_order_gateway.py tests/test_stage10_entry_pipeline.py tests/test_stage11_execution_flow.py
```

## Results

1. Stage 11 only (`tests/test_stage11_execution_flow.py`)
- Total tests: `21`
- Passed: `21`
- Failed: `0`
- Errors: `0`
- Result: `OK`

2. Regression (Stage 1-11 combined)
- Total tests: `119`
- Passed: `119`
- Failed: `0`
- Errors: `0`
- Result: `OK`

## Verified Behaviors

- Fill sync / phase transitions
  - FIRST_ENTRY `PARTIALLY_FILLED`: keep `ENTRY_ORDER`, TP monitor active
  - FIRST_ENTRY `FILLED`: transition to `PHASE1`, second-entry monitoring start
  - SECOND_ENTRY `PARTIALLY_FILLED`: transition/keep `PHASE2`, profit-TP off + breakeven-only mode
  - SECOND_ENTRY `FILLED`: keep/confirm `PHASE2`, MDD stop submit signal on full fill
- PNL branch (`ROI` with short formula)
  - negative / exact zero / positive branch split
  - exact-zero rule uses strict equality (`ROI == 0.0`)
- Risk management plan
  - monitoring reset
  - `ENTRY_ORDER` with no position: cancel entry and reset
  - `PNL <= 0`: market-exit priority
  - `PHASE1 + PNL > 0`: breakeven STOP_MARKET + TP keep/create-once policy
  - `PHASE2 + PNL > 0`: keep breakeven-limit mode, keep existing MDD only when second entry fully filled
- OCO mutual cancel
  - filled order excluded from cancel targets
  - remaining cancel failure => lock-new-orders signal
- Exit partial 5-second rule
  - exit-order `PARTIALLY_FILLED` stall >= 5s => force-market-exit signal
  - additional fill resets timer
  - risk-market-exit in same loop suppresses 5-second rule
- Structured logging wrappers include required fields:
  - `input`, `decision`, `result`, `state_transition`, `failure_reason`
