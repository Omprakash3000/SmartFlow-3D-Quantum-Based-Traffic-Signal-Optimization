import pytest
from backend.app.models.simulation_models import (
    ApproachDirection,
    SignalColor,
    SimulationConfig,
)
from backend.app.simulation.traffic_light import (
    TrafficLightController,
    CONFLICTING_PAIRS,
)
from backend.app.simulation.engine import SimulationEngine
from backend.app.optimization.validator import SafetyValidator
from backend.app.models.optimization_models import (
    IntersectionSchedule,
    PhaseAssignment,
)


def test_traffic_light_strictly_enforces_clearance_and_no_conflicts():
    controller = TrafficLightController("INT_TEST")

    # Run controller for 2 full cycles (120 seconds with dt=0.5)
    for _ in range(240):
        controller.step(0.5)
        state = controller.get_state()

        # Check all approaches
        greens = [
            ApproachDirection(app)
            for app, color in state.approach_signals.items()
            if color == SignalColor.GREEN
        ]

        # Verify no conflicting green lights
        for i in range(len(greens)):
            for j in range(i + 1, len(greens)):
                assert (
                    greens[i],
                    greens[j],
                ) not in CONFLICTING_PAIRS, f"Safety violation: {greens[i]} and {greens[j]} green at same time!"


def test_safety_validator_detects_conflicts():
    # Valid schedule
    valid_schedule = [
        IntersectionSchedule(
            intersection_id="INT_1",
            assignments=[
                PhaseAssignment(
                    step_index=0,
                    timestamp_s=0.0,
                    duration_s=10.0,
                    phase_id=0,
                    phase_name="NS",
                    green_approaches=["NB", "SB"],
                ),
                PhaseAssignment(
                    step_index=1,
                    timestamp_s=10.0,
                    duration_s=10.0,
                    phase_id=1,
                    phase_name="EW",
                    green_approaches=["EB", "WB"],
                ),
            ],
            total_cycle_time_s=20.0,
        )
    ]
    is_valid, err = SafetyValidator.audit_schedule(valid_schedule)
    assert is_valid is True
    assert err is None

    # Invalid schedule: conflicting green approaches NB and EB in same phase assignment
    invalid_schedule = [
        IntersectionSchedule(
            intersection_id="INT_1",
            assignments=[
                PhaseAssignment(
                    step_index=0,
                    timestamp_s=0.0,
                    duration_s=10.0,
                    phase_id=99,
                    phase_name="Dangerous Collision Phase",
                    green_approaches=["NB", "EB"],  # Conflicting!
                )
            ],
            total_cycle_time_s=10.0,
        )
    ]
    is_invalid, err = SafetyValidator.audit_schedule(invalid_schedule)
    assert is_invalid is False
    assert "SAFETY AUDIT FAILED" in err
