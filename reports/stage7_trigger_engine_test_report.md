# Stage 7 Trigger Engine Test Report

- Generated at (UTC): `2026-02-07 08:16:05Z`
- Python: `3.12.3`
- Scope: 0.1% trigger engine (simulation-first), deterministic tie-break (`received_at_local` then `message_id`)

## Commands

```bash
python3 -m py_compile auto_trade/*.py tests/test_stage1_4.py tests/test_stage5_state_machine.py tests/test_stage6_filtering_targets.py tests/test_stage7_trigger_engine.py
python3 -m unittest -v tests/test_stage7_trigger_engine.py
python3 -m unittest discover -s tests -p 'test_stage*.py' -v
```

## Results

1. Stage 7 only (`tests/test_stage7_trigger_engine.py`)
- Total tests: `13`
- Passed: `13`
- Failed: `0`
- Errors: `0`
- Result: `OK`

2. Regression (Stage 1-7 combined)
- Total tests: `63`
- Passed: `63`
- Failed: `0`
- Errors: `0`
- Result: `OK`

## Verified Behaviors

- 0.1% trigger threshold/condition
  - `FIRST_ENTRY`, `SECOND_ENTRY`: `current >= target*(1-0.001)`
  - `TP`: `current <= target*(1+0.001)`
  - `BREAKEVEN`: `current >= target*(1+0.001)`
- Immediate trigger on first evaluation when condition already satisfied
- Missing/invalid price safely rejected (no trigger)
- Same-loop multi-symbol tie-break
  1) later `received_at_local` wins
  2) if equal, larger `message_id` wins
- Simulation-first verification
  - multi-step simulated price snapshots
  - optional stop on first selected trigger
- Structured logging wrappers include required fields:
  - `input`, `decision`, `result`, `state_transition`, `failure_reason`

## Log Evidence

Examples from `/tmp/LTS-AutoTrade.log`:
- `component=trigger_engine event=evaluate_trigger_loop ... reason_code=MULTI_TRIGGER_TIEBREAK_RECEIVED_AT ...`
- `component=trigger_simulation event=run_trigger_simulation ... selected_symbol=ETHUSDT ...`
