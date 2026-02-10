# Stage 6 Filtering + Entry Target Test Report

- Generated at (UTC): `2026-02-07 08:07:35Z`
- Python: `3.12.3`
- Scope: Stage 6 common filtering rules + mode-based entry target calculation

## Commands

```bash
python3 -m py_compile auto_trade/*.py indicators.py tests/test_stage1_4.py tests/test_stage5_state_machine.py tests/test_stage6_filtering_targets.py
python3 -m unittest -v tests/test_stage6_filtering_targets.py
python3 -m unittest discover -s tests -p 'test_stage*.py' -v
```

## Results

1. Stage 6 only (`tests/test_stage6_filtering_targets.py`)
- Total tests: `14`
- Passed: `14`
- Failed: `0`
- Errors: `0`
- Result: `OK`

2. Regression (Stage 1-6 combined)
- Total tests: `50`
- Passed: `50`
- Failed: `0`
- Errors: `0`
- Result: `OK`

## Verified Behaviors

- Common filtering (`category`, `ranking`, `funding`)
  - excluded category keyword reject
  - `정보없음` reject
  - `(상승) 상위 1~10위` reject
  - `(하락)` direction allowed regardless of rank
  - `funding_rate_pct <= -0.1` reject
  - valid input pass
- Entry target calculation
  - aggressive mode uses previous confirmed 3m candle `high`
  - conservative mode uses `indicators.py` ATR upper (`calculate_atr_bands`) as single source
  - target reference index fixed to previous confirmed candle (`len(candles)-2`)
  - invalid/insufficient candle input rejects safely
- Structured logging wrappers include required fields
  - `input`, `decision`, `result`, `state_transition`, `failure_reason`

## Dependency Safety Note

- Runtime environment does not include `pip/pandas/numpy`.
- To keep Stage 6 testable without breaking prior stages, `indicators.py` ATR path was made dependency-safe while preserving `calculate_atr_bands` as single source.
