# Stage 13 Orchestrator Integration Test Report

- Generated at (UTC): `2026-02-07 09:22:10Z`
- Python: `3.12.3`
- Scope: end-to-end orchestration wiring for recovery/startup, telegram signal routing, trigger-entry cycle, fill sync, risk branch, price-guard, OCO/5-second exit rule

## Commands

```bash
python3 -m py_compile auto_trade/*.py tests/test_stage13_orchestrator_integration.py trade_page.py
python3 -m unittest -v tests/test_stage13_orchestrator_integration.py
python3 -m unittest -q tests/test_stage1_4.py tests/test_stage5_state_machine.py tests/test_stage6_filtering_targets.py tests/test_stage7_trigger_engine.py tests/test_stage8_price_source.py tests/test_stage9_order_gateway.py tests/test_stage10_entry_pipeline.py tests/test_stage11_execution_flow.py tests/test_stage12_recovery_ui.py tests/test_stage13_orchestrator_integration.py
```

## Results

1. Stage 13 only (`tests/test_stage13_orchestrator_integration.py`)
- Total tests: `12`
- Passed: `12`
- Failed: `0`
- Errors: `0`
- Result: `OK`

2. Regression (Stage 1-13 combined)
- Total tests: `141`
- Passed: `141`
- Failed: `0`
- Errors: `0`
- Result: `OK`

## Verified Behaviors

- Leading-market signal pipeline is connected:
  - dedup -> parse -> symbol mapping/validation -> cooldown rule -> common filters -> entry target -> trigger registration
- Trigger cycle is connected:
  - tie-break engine output is dispatched to first-entry pipeline
  - successful first-entry submit updates symbol state and entry-lock account state
- Risk signal pipeline is connected:
  - risk parser + PNL branch + risk action planner integration
- Recovery/startup integration is connected:
  - orchestrator runtime state is synchronized from stage12 recovery result
- Price source safety guard integration is connected:
  - stale guard result updates safety lock/global blocked
- Execution integration is connected:
  - fill sync state transition
  - OCO cancel execution failure -> new-order lock
  - exit partial-fill 5-second rule
- Router integration:
  - `process_telegram_message` routes by configured channel id (leading/risk)
- Structured logging wrappers include required fields:
  - `input`, `decision`, `result`, `state_transition`, `failure_reason`
