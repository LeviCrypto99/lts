# Lessons

- When a guide or strategy button may not have a backing PDF yet, confirm whether the user wants a real file link or a UI-only placeholder before wiring the click behavior.
- When entry orders start failing after a refactor, check live trade logs for the exact exchange reject payload before blaming the broader flow change; request serialization bugs can look like logic regressions.
- When reducing entry-bot polling, do not stop the relay consumer immediately after order submit if downstream risk-cancel signals still need to be honored.
- When cleaning dead trading code, preserve both entry blockers: existing positions and existing open entry orders must each continue to reject new entry signals.
- Before deleting a "dead" API, search all UI/page constructors for stale callers; page-transition code can still reference cleanup hooks that no longer do anything.
- When adding multiple UI actions inside a constrained container, do not default to vertical stacking; first match the surrounding layout pattern and prefer a horizontal arrangement such as `top row 2 + bottom row 1` when it uses space better.
- When a user adjusts UI placement after an initial layout pass, revisit the container as a whole and leave space for likely adjacent additions instead of only nudging the single existing element.
- When creating a titled panel, reserve explicit vertical clearance under the title bar before placing labels or buttons; otherwise the title strip can visually cover the first row.
- After moving a titled panel, verify that all child controls still remain inside the panel bounds; fixing title overlap by pushing controls downward can create a new bottom overflow.
- When only one panel title visually collides with nearby content, use a panel-specific title offset instead of shifting unrelated controls and creating new layout regressions.
- First distinguish whether the user wants the title text moved or the title bar itself resized; for titled-panel overlap, changing the bar height is often the correct fix.
