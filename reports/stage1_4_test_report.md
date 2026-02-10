# Stage 1-4 Test Report

- Generated at (UTC): `2026-02-07 07:48:34Z`
- Python: `3.12.3`
- Scope: `auto_trade` stage 1-4 modules (config, structured logging, message parsing/dedup, symbol mapping, cooldown)

## Commands

```bash
python3 -m unittest -v tests/test_stage1_4.py
python3 -m unittest discover -s tests -p 'test_stage1_4.py' -v
```

## Summary

- Total tests: `23`
- Passed: `23`
- Failed: `0`
- Errors: `0`
- Result: `OK`

## Validated Areas

1. Stage 1 (`config`)
- default values load correctly
- invalid/out-of-range env values fall back to defaults

2. Stage 2 (`event_logging` usage via wrappers)
- parser/mapping/dedup logging wrappers emit required structured fields:
  - `input`
  - `decision`
  - `result`
  - `state_transition`
  - `failure_reason`

3. Stage 3 (`message_parser`)
- leading-market parse success/failure branches
- risk-management parse success/failure branches (`.P` removal + normalization)
- `message_id` dedup accepts new and rejects old/invalid ids

4. Stage 4 (`symbol_mapping`, `cooldown`)
- ticker-to-symbol mapping success/failure
- exchangeInfo validation success/failure (not found, not trading, exchangeInfo unavailable)
- mapping failure action split (`IGNORE_KEEP_STATE` vs `RESET_AND_EXCLUDE`)
- cooldown record decision rules (entry lock/safety lock/no symbol/record)
- cooldown window check and record behavior

## Notes

- This report validates logic-unit behavior only.
- Telegram real-channel E2E validation is still pending for later integration stages.
