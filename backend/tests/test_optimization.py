import pytest
from backend.app.models.optimization_models import (
    OptimizationWeights,
    MethodBenchmarkResult,
    IntersectionSchedule,
    PhaseAssignment,
)
from backend.app.optimization.base import TrafficOptimizationProblem
from backend.app.optimization.qubo_formulator import QUBOFormulator
from backend.app.optimization.classical_optimizer import ClassicalOROptimizer
from backend.app.optimization.qaoa_optimizer import QAOAOptimizer
from backend.app.optimization.validator import SafetyValidator


@pytest.fixture
def sample_problem():
    return TrafficOptimizationProblem(
        intersection_ids=["INT_1", "INT_2"],
        planning_horizon_steps=4,
        step_duration_s=10.0,
        current_queues={
            "INT_1": {"NB": 4, "SB": 3, "EB": 8, "WB": 7},
            "INT_2": {"NB": 3, "SB": 4, "EB": 6, "WB": 6},
        },
        arrival_rates={
            "INT_1": {"NB": 16.0, "SB": 14.0, "EB": 24.0, "WB": 20.0},
            "INT_2": {"NB": 14.0, "SB": 16.0, "EB": 22.0, "WB": 22.0},
        },
        weights=OptimizationWeights(
            waiting_time=1.0,
            queue_length=1.5,
            throughput=1.2,
            switching_cost=0.8,
            coordination=1.0,
        ),
        travel_offset_steps=1,
    )


def test_qubo_formulator(sample_problem):
    qp = QUBOFormulator.build_quadratic_program(sample_problem)
    # 2 intersections * 2 phases * 4 time steps = 16 binary variables
    assert qp.get_num_binary_vars() == 16
    assert len(qp.objective.quadratic.to_dict()) > 0


def test_classical_ortools_optimizer(sample_problem):
    optimizer = ClassicalOROptimizer()
    result = optimizer.solve(sample_problem)

    assert result.is_feasible is True
    assert result.safety_checks_passed is True
    assert len(result.schedule) == 2
    assert result.execution_time_ms > 0.0

    # Ensure each intersection has 4 step assignments
    for s in result.schedule:
        assert len(s.assignments) == 4


def test_qaoa_optimizer(sample_problem):
    # Test QAOA on single intersection, 4 time steps (8 qubits) for fast execution
    small_problem = TrafficOptimizationProblem(
        intersection_ids=["INT_1"],
        planning_horizon_steps=4,
        step_duration_s=10.0,
        current_queues={"INT_1": {"NB": 3, "SB": 3, "EB": 6, "WB": 5}},
        arrival_rates={"INT_1": {"NB": 15.0, "SB": 15.0, "EB": 20.0, "WB": 20.0}},
        weights=OptimizationWeights(),
    )
    optimizer = QAOAOptimizer()
    result = optimizer.solve(small_problem)

    assert result.method_name.startswith("QAOA")
    assert len(result.schedule) == 1
    assert result.resource_usage["num_qubits"] == 8
    assert result.resource_usage["qaoa_reps"] >= 1


def test_candidate_arbitration_and_rejection():
    # Construct a classical benchmark
    classical_res = MethodBenchmarkResult(
        method_name="OR-Tools",
        is_feasible=True,
        safety_checks_passed=True,
        objective_value=10.0,
        estimated_waiting_time_s=12.0,
        estimated_queue_length=3.0,
        estimated_throughput_vph=900.0,
        execution_time_ms=15.0,
        resource_usage={},
        schedule=[
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
                    )
                ],
                total_cycle_time_s=10.0,
            )
        ],
        candidate_accepted=True,
    )

    # Infeasible QAOA result
    bad_qaoa = MethodBenchmarkResult(
        method_name="QAOA",
        is_feasible=False,
        safety_checks_passed=False,
        objective_value=999.0,
        estimated_waiting_time_s=40.0,
        estimated_queue_length=15.0,
        estimated_throughput_vph=200.0,
        execution_time_ms=250.0,
        resource_usage={},
        schedule=[],
        candidate_accepted=False,
        rejection_reason="Infeasible solution",
    )

    # When QAOA is bad, SafetyValidator must reject QAOA and choose classical!
    winner, method_name = SafetyValidator.select_best_schedule(bad_qaoa, classical_res)
    assert winner == classical_res
    assert "rejected" in method_name or "Classical" in method_name
    assert bad_qaoa.candidate_accepted is False
