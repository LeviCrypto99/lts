# Stage 5 State Machine Test Report

- Generated at (UTC): `2026-02-07 07:52:58Z`
- Python: `3.12.3`
- Scope: Stage 5 state-machine core (`GLOBAL_BLOCKED`, `ENTRY_LOCK`, `SAFETY_LOCK`, `IDLE/MONITORING/ENTRY_ORDER/PHASE1/PHASE2`)

## Commands

```bash
python3 -m py_compile auto_trade/*.py tests/test_stage1_4.py tests/test_stage5_state_machine.py
python3 -m unittest -v tests/test_stage5_state_machine.py
python3 -m unittest discover -s tests -p 'test_stage*.py' -v
```

## Results

1. Stage 5 only (`tests/test_stage5_state_machine.py`)
- Total tests: `13`
- Passed: `13`
- Failed: `0`
- Errors: `0`
- Result: `OK`

2. Regression (Stage 1-5 combined)
- Total tests: `36`
- Passed: `36`
- Failed: `0`
- Errors: `0`
- Result: `OK`

## Verified Behaviors

- Global lock calculation
  - `ENTRY_OPEN` when no position and no open order
  - `ENTRY_LOCKED` when position exists or open order exists
  - `GLOBAL_BLOCKED = ENTRY_LOCKED OR SAFETY_LOCKED`
- Safety lock transition
  - lock on/off transitions without order logic
- Symbol state transitions
  - `IDLE -> MONITORING -> ENTRY_ORDER -> PHASE1 -> PHASE2`
  - partial fill keeps `ENTRY_ORDER`
  - invalid transitions are rejected
  - `RESET` returns to `IDLE`
- Structured logging fields are present in wrappers
  - `input`, `decision`, `result`, `state_transition`, `failure_reason`

## Log Evidence

Examples from `/tmp/LTS-AutoTrade.log`:
- `component=state_machine_global event=update_account_activity ...`
- `component=state_machine_global event=set_safety_lock ...`
- `component=state_machine_symbol event=apply_symbol_event ...`
