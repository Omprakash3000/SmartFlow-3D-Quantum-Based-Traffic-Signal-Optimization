from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
from backend.app.models.optimization_models import (
    OptimizationRequest,
    MethodBenchmarkResult,
    IntersectionSchedule,
    PhaseAssignment,
)
from backend.app.models.simulation_models import ApproachDirection


class TrafficOptimizationProblem:
    """
    Standardized mathematical formulation data for traffic signal scheduling.
    Used identically by both QAOA and classical (OR-Tools) optimizers.
    """

    def __init__(
        self,
        intersection_ids: List[str],
        planning_horizon_steps: int,
        step_duration_s: float,
        current_queues: Dict[str, Dict[str, int]],  # {int_id: {"NB": q, "SB": q, "EB": q, "WB": q}}
        arrival_rates: Dict[str, Dict[str, float]],  # {int_id: {"NB": r, ...}}
        weights: Any,
        travel_offset_steps: int = 2,  # Steps between INT_1 and INT_2 for green wave
    ):
        self.intersection_ids = intersection_ids
        self.T = planning_horizon_steps
        self.dt_step = step_duration_s
        self.current_queues = current_queues
        self.arrival_rates = arrival_rates
        self.weights = weights
        self.travel_offset_steps = travel_offset_steps

        # Standard Phase 0: NS, Phase 1: EW
        self.phases = [0, 1]
        self.phase_names = {0: "North-South Flow", 1: "East-West Flow"}
        self.phase_approaches = {
            0: [ApproachDirection.NORTHBOUND.value, ApproachDirection.SOUTHBOUND.value],
            1: [ApproachDirection.EASTBOUND.value, ApproachDirection.WESTBOUND.value],
        }


class BaseTrafficOptimizer(ABC):
    @abstractmethod
    def solve(self, problem: TrafficOptimizationProblem) -> MethodBenchmarkResult:
        """Solves the traffic signal optimization problem and returns benchmark metrics."""
        pass
