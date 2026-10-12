from typing import Dict, List, Set, Tuple, Optional
from backend.app.models.simulation_models import (
    ApproachDirection,
    SignalColor,
    TrafficLightState,
)


# Conflict Matrix: Pairs of approaches that must NEVER be green simultaneously
CONFLICTING_PAIRS: Set[Tuple[ApproachDirection, ApproachDirection]] = {
    (ApproachDirection.NORTHBOUND, ApproachDirection.EASTBOUND),
    (ApproachDirection.NORTHBOUND, ApproachDirection.WESTBOUND),
    (ApproachDirection.SOUTHBOUND, ApproachDirection.EASTBOUND),
    (ApproachDirection.SOUTHBOUND, ApproachDirection.WESTBOUND),
    (ApproachDirection.EASTBOUND, ApproachDirection.NORTHBOUND),
    (ApproachDirection.EASTBOUND, ApproachDirection.SOUTHBOUND),
    (ApproachDirection.WESTBOUND, ApproachDirection.NORTHBOUND),
    (ApproachDirection.WESTBOUND, ApproachDirection.SOUTHBOUND),
}


class SignalPhaseDefinition:
    def __init__(
        self,
        phase_id: int,
        name: str,
        green_approaches: List[ApproachDirection],
        default_green_time_s: float = 25.0,
        yellow_time_s: float = 3.0,
        all_red_time_s: float = 2.0,
    ):
        self.phase_id = phase_id
        self.name = name
        self.green_approaches = green_approaches
        self.default_green_time_s = default_green_time_s
        self.yellow_time_s = yellow_time_s
        self.all_red_time_s = all_red_time_s

        # Validate that green approaches do not conflict among themselves
        for i in range(len(green_approaches)):
            for j in range(i + 1, len(green_approaches)):
                if (green_approaches[i], green_approaches[j]) in CONFLICTING_PAIRS:
                    raise ValueError(
                        f"Safety Violation: Phase {name} attempts conflicting greens: "
                        f"{green_approaches[i]} and {green_approaches[j]}"
                    )


STANDARD_PHASES: List[SignalPhaseDefinition] = [
    # Phase 0: North-South Green
    SignalPhaseDefinition(
        phase_id=0,
        name="North-South Flow",
        green_approaches=[ApproachDirection.NORTHBOUND, ApproachDirection.SOUTHBOUND],
        default_green_time_s=25.0,
        yellow_time_s=3.0,
        all_red_time_s=2.0,
    ),
    # Phase 1: East-West Green
    SignalPhaseDefinition(
        phase_id=1,
        name="East-West Flow",
        green_approaches=[ApproachDirection.EASTBOUND, ApproachDirection.WESTBOUND],
        default_green_time_s=25.0,
        yellow_time_s=3.0,
        all_red_time_s=2.0,
    ),
]


class TrafficLightController:
    """
    Traffic signal controller enforcing safety constraints and transition states:
    GREEN -> YELLOW -> ALL-RED -> Next GREEN.
    Supports fixed-time cycling, manual overrides, and dynamic optimization schedule tables.
    """

    def __init__(
        self,
        intersection_id: str,
        phases: Optional[List[SignalPhaseDefinition]] = None,
        offset_s: float = 0.0,
    ):
        self.intersection_id = intersection_id
        self.phases = phases or list(STANDARD_PHASES)
        self.offset_s = offset_s

        # Active state
        self.current_phase_idx: int = 0
        self.subphase_state: SignalColor = SignalColor.GREEN  # GREEN, YELLOW, or RED (all-red)
        self.elapsed_in_subphase_s: float = 0.0

        # Timing configurations per phase: {phase_id: green_time_s}
        self.phase_green_durations: Dict[int, float] = {
            p.phase_id: p.default_green_time_s for p in self.phases
        }

        # Dynamic schedule queue: list of (target_phase_id, duration_s)
        self.scheduled_queue: List[Tuple[int, float]] = []
        self.current_schedule_item: Optional[Tuple[int, float]] = None

    @property
    def current_phase(self) -> SignalPhaseDefinition:
        return self.phases[self.current_phase_idx]

    def set_phase_green_time(self, phase_id: int, green_time_s: float) -> None:
        if green_time_s < 5.0:
            raise ValueError("Minimum green time must be at least 5.0 seconds for safety.")
        if green_time_s > 120.0:
            raise ValueError("Maximum green time capped at 120.0 seconds.")
        if phase_id in self.phase_green_durations:
            self.phase_green_durations[phase_id] = float(green_time_s)

    def load_schedule_plan(self, assignments: List[Tuple[int, float]]) -> None:
        """Load an optimized schedule plan: list of (phase_id, green_duration_s)"""
        # Validate all assignments for safety
        for phase_id, dur in assignments:
            if phase_id not in [p.phase_id for p in self.phases]:
                raise ValueError(f"Unknown phase ID {phase_id}")
            if dur < 5.0:
                raise ValueError(f"Schedule duration {dur}s violates minimum green time (5.0s)")
        self.scheduled_queue = list(assignments)

    def step(self, dt: float) -> None:
        """Advance controller by dt seconds adhering strictly to clearance intervals."""
        self.elapsed_in_subphase_s += dt
        curr = self.current_phase

        target_green = (
            self.current_schedule_item[1]
            if self.current_schedule_item is not None
            else self.phase_green_durations.get(curr.phase_id, curr.default_green_time_s)
        )

        if self.subphase_state == SignalColor.GREEN:
            if self.elapsed_in_subphase_s >= target_green:
                # Transition to Yellow
                self.subphase_state = SignalColor.YELLOW
                self.elapsed_in_subphase_s = 0.0

        elif self.subphase_state == SignalColor.YELLOW:
            if self.elapsed_in_subphase_s >= curr.yellow_time_s:
                # Transition to All-Red clearance
                self.subphase_state = SignalColor.RED
                self.elapsed_in_subphase_s = 0.0

        elif self.subphase_state == SignalColor.RED:
            if self.elapsed_in_subphase_s >= curr.all_red_time_s:
                # Advance to next phase
                self._advance_to_next_phase()
                self.subphase_state = SignalColor.GREEN
                self.elapsed_in_subphase_s = 0.0

    def _advance_to_next_phase(self) -> None:
        if self.scheduled_queue:
            next_phase_id, next_dur = self.scheduled_queue.pop(0)
            self.current_schedule_item = (next_phase_id, next_dur)
            # Find phase index
            for idx, p in enumerate(self.phases):
                if p.phase_id == next_phase_id:
                    self.current_phase_idx = idx
                    break
        else:
            self.current_schedule_item = None
            self.current_phase_idx = (self.current_phase_idx + 1) % len(self.phases)

    def get_signal_for_approach(self, approach: ApproachDirection) -> SignalColor:
        """Returns the signal color for a specific approach."""
        curr = self.current_phase
        if self.subphase_state == SignalColor.GREEN:
            return SignalColor.GREEN if approach in curr.green_approaches else SignalColor.RED
        elif self.subphase_state == SignalColor.YELLOW:
            return SignalColor.YELLOW if approach in curr.green_approaches else SignalColor.RED
        else:
            # All-Red clearance
            return SignalColor.RED

    def get_state(self) -> TrafficLightState:
        curr = self.current_phase
        signals = {
            app.value: self.get_signal_for_approach(app)
            for app in [
                ApproachDirection.NORTHBOUND,
                ApproachDirection.SOUTHBOUND,
                ApproachDirection.EASTBOUND,
                ApproachDirection.WESTBOUND,
            ]
        }

        # Safety self-check
        greens = [app for app, color in signals.items() if color == SignalColor.GREEN]
        for i in range(len(greens)):
            for j in range(i + 1, len(greens)):
                if (ApproachDirection(greens[i]), ApproachDirection(greens[j])) in CONFLICTING_PAIRS:
                    raise RuntimeError(
                        f"CRITICAL SAFETY VIOLATION DETECTED: Simultaneous green on conflicting approaches {greens[i]} & {greens[j]}"
                    )

        target_green = (
            self.current_schedule_item[1]
            if self.current_schedule_item is not None
            else self.phase_green_durations.get(curr.phase_id, curr.default_green_time_s)
        )

        return TrafficLightState(
            intersection_id=self.intersection_id,
            current_phase_id=curr.phase_id,
            current_color=self.subphase_state,
            elapsed_in_phase_s=round(self.elapsed_in_subphase_s, 2),
            target_green_duration_s=round(target_green, 2),
            approach_signals=signals,
        )
