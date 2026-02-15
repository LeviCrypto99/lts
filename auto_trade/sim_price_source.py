from __future__ import annotations

from collections import deque
from typing import Any, Mapping, Optional, Sequence

from .event_logging import StructuredLogEvent, log_structured_event
from .trigger_engine import TRIGGER_BUFFER_RATIO_DEFAULT, evaluate_trigger_loop
from .trigger_models import SimulationStepResult, TriggerCandidate, TriggerSimulationReport


def _normalize(value: Any) -> str:
    text = " ".join(str(value).split())
    return text if text else "-"


def _normalize_symbol(symbol: str) -> str:
    return (symbol or "").strip().upper()


class SimulatedPriceSource:
    def __init__(self, snapshots: Sequence[Mapping[str, float]]) -> None:
        normalized: list[dict[str, float]] = []
        for snapshot in snapshots:
            row: dict[str, float] = {}
            for symbol, price in snapshot.items():
                row[_normalize_symbol(symbol)] = float(price)
            normalized.append(row)
        self._snapshots: deque[dict[str, float]] = deque(normalized)
        self._initial_count = len(normalized)

    def has_next(self) -> bool:
        return bool(self._snapshots)

    def pop_next(self) -> Mapping[str, float]:
        if not self._snapshots:
            raise IndexError("no more simulated snapshots")
        return dict(self._snapshots.popleft())

    @property
    def total_steps(self) -> int:
        return self._initial_count


def run_trigger_simulation(
    *,
    candidates: Sequence[TriggerCandidate],
    price_source: SimulatedPriceSource,
    trigger_buffer_ratio: float = TRIGGER_BUFFER_RATIO_DEFAULT,
    stop_on_first_trigger: bool = True,
) -> TriggerSimulationReport:
    steps: list[SimulationStepResult] = []
    selected_step_index: Optional[int] = None
    step_index = 0

    while price_source.has_next():
        snapshot = price_source.pop_next()
        loop_result = evaluate_trigger_loop(
            candidates,
            snapshot,
            trigger_buffer_ratio=trigger_buffer_ratio,
        )
        steps.append(
            SimulationStepResult(
                step_index=step_index,
                snapshot_prices=snapshot,
                loop_result=loop_result,
            )
        )
        if loop_result.selected_candidate is not None and selected_step_index is None:
            selected_step_index = step_index
            if stop_on_first_trigger:
                break
        step_index += 1

    return TriggerSimulationReport(
        total_steps=len(steps),
        stopped_early=selected_step_index is not None and stop_on_first_trigger,
        first_selected_step=selected_step_index,
        steps=steps,
    )


def run_trigger_simulation_with_logging(
    *,
    candidates: Sequence[TriggerCandidate],
    price_source: SimulatedPriceSource,
    trigger_buffer_ratio: float = TRIGGER_BUFFER_RATIO_DEFAULT,
    stop_on_first_trigger: bool = True,
    simulation_label: str = "default",
) -> TriggerSimulationReport:
    report = run_trigger_simulation(
        candidates=candidates,
        price_source=price_source,
        trigger_buffer_ratio=trigger_buffer_ratio,
        stop_on_first_trigger=stop_on_first_trigger,
    )
    selected_symbol = "-"
    if report.first_selected_step is not None:
        selected = report.steps[report.first_selected_step].loop_result.selected_candidate
        if selected is not None:
            selected_symbol = _normalize_symbol(selected.symbol)

    log_structured_event(
        StructuredLogEvent(
            component="trigger_simulation",
            event="run_trigger_simulation",
            input_data=(
                f"candidate_count={len(candidates)} stop_on_first_trigger={stop_on_first_trigger} "
                f"trigger_buffer_ratio={trigger_buffer_ratio}"
            ),
            decision="iterate_snapshots_and_evaluate_trigger_loop",
            result="completed",
            state_before="simulation_ready",
            state_after="simulation_done",
            failure_reason="-",
        ),
        simulation_label=_normalize(simulation_label),
        total_steps=report.total_steps,
        stopped_early=report.stopped_early,
        first_selected_step=report.first_selected_step if report.first_selected_step is not None else "-",
        selected_symbol=selected_symbol,
    )
    return report
