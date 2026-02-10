# Stage 9 Order Gateway Test Report

- Generated at (UTC): `2026-02-07 08:34:46Z`
- Python: `3.12.3`
- Scope: Order gateway separation (`create/cancel/query + retry policy`) with filter/mode rule enforcement

## Commands

```bash
python3 -m py_compile auto_trade/*.py tests/test_stage9_order_gateway.py
python3 -m unittest -v tests/test_stage9_order_gateway.py
python3 -m unittest -q tests/test_stage1_4.py tests/test_stage5_state_machine.py tests/test_stage6_filtering_targets.py tests/test_stage7_trigger_engine.py tests/test_stage8_price_source.py tests/test_stage9_order_gateway.py
```

## Results

1. Stage 9 only (`tests/test_stage9_order_gateway.py`)
- Total tests: `15`
- Passed: `15`
- Failed: `0`
- Errors: `0`
- Result: `OK`

2. Regression (Stage 1-9 combined)
- Total tests: `88`
- Passed: `88`
- Failed: `0`
- Errors: `0`
- Result: `OK`

## Verified Behaviors

- `PRICE_FILTER`: target `price/stopPrice` rounding by `tickSize`, non-positive adjusted price rejection
- `LOT_SIZE`: `quantity` floor by `stepSize`, `minQty` enforcement
- `MIN_NOTIONAL`: order notional check with strict rejection on below-threshold
- Position mode rule enforcement
  - `ONE_WAY`
    - ENTRY: `reduceOnly=false`, `positionSide` omitted
    - EXIT LIMIT/MARKET: `reduceOnly=true`
    - EXIT `STOP_MARKET`/`TAKE_PROFIT_MARKET`: `closePosition=true`, `quantity` omitted
  - `HEDGE`
    - All orders: `positionSide=SHORT`
    - Stop-family EXIT: `closePosition=true`, `quantity` omitted
- Retry policy
  - create/cancel/query all use shared retry executor
  - retries only on configured retryable reason codes
  - immediate stop on non-retryable failure
  - create retry keeps same `newClientOrderId`
- Structured logging wrappers include required fields:
  - `input`, `decision`, `result`, `state_transition`, `failure_reason`
