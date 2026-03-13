# Lessons

- When a guide or strategy button may not have a backing PDF yet, confirm whether the user wants a real file link or a UI-only placeholder before wiring the click behavior.
- When entry orders start failing after a refactor, check live trade logs for the exact exchange reject payload before blaming the broader flow change; request serialization bugs can look like logic regressions.
- When reducing entry-bot polling, do not stop the relay consumer immediately after order submit if downstream risk-cancel signals still need to be honored.
