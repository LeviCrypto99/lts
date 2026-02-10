# Stage 10 Entry Pipeline Test Report

- Generated at (UTC): `2026-02-07 08:45:37Z`
- Python: `3.12.3`
- Scope: 1st/2nd entry pipeline integration (budget, quantity, order gateway, state policy)

## Commands

```bash
python3 -m py_compile auto_trade/*.py tests/test_stage10_entry_pipeline.py
python3 -m unittest -v tests/test_stage10_entry_pipeline.py
python3 -m unittest -q tests/test_stage1_4.py tests/test_stage5_state_machine.py tests/test_stage6_filtering_targets.py tests/test_stage7_trigger_engine.py tests/test_stage8_price_source.py tests/test_stage9_order_gateway.py tests/test_stage10_entry_pipeline.py
```

## Results

1. Stage 10 only (`tests/test_stage10_entry_pipeline.py`)
- Total tests: `10`
- Passed: `10`
- Failed: `0`
- Errors: `0`
- Result: `OK`

2. Regression (Stage 1-10 combined)
- Total tests: `98`
- Passed: `98`
- Failed: `0`
- Errors: `0`
- Result: `OK`

## Verified Behaviors

- 1st entry budget: `wallet_balance * 50%`
- 2nd entry budget: `available * (1 - margin_buffer_pct)`
- Quantity calculation: `budget / target_price`
- 1st entry failure policy
  - generic failure: `RESET_AND_EXCLUDE`
  - `INSUFFICIENT_MARGIN`: immediate reset (no special reflow)
- 2nd entry failure policy
  - generic failure: `SECOND_ENTRY_SKIPPED_KEEP_STATE`
  - `INSUFFICIENT_MARGIN`: re-fetch available, reapply buffer, recalc quantity, single retry
  - retry failure: skip second entry and keep state
- State policy
  - 1st entry success: `MONITORING -> ENTRY_ORDER`
  - 2nd entry success: `PHASE1` 유지 (`SUBMIT_SECOND_ENTRY_ORDER`, no state change)
- Structured logging wrappers include required fields:
  - `input`, `decision`, `result`, `state_transition`, `failure_reason`
