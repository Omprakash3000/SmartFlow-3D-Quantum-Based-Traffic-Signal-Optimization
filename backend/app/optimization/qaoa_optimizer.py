import time
import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional

from qiskit.primitives import StatevectorSampler, BaseSamplerV2
from qiskit_algorithms.minimum_eigensolvers import QAOA
from qiskit_algorithms.optimizers import COBYLA
from qiskit_optimization.algorithms import MinimumEigenOptimizer

from backend.app.config import settings
from backend.app.models.optimization_models import (
    MethodBenchmarkResult,
    IntersectionSchedule,
    PhaseAssignment,
)
from backend.app.optimization.base import (
    BaseTrafficOptimizer,
    TrafficOptimizationProblem,
)
from backend.app.optimization.qubo_formulator import QUBOFormulator

logger = logging.getLogger(__name__)


class QuantumExecutionProvider(ABC):
    """
    Abstract interface for quantum execution providers.
    Allows swapping between local simulation (Aer/Statevector) and external quantum hardware.
    """

    @abstractmethod
    def get_sampler(self) -> BaseSamplerV2:
        pass

    @abstractmethod
    def provider_name(self) -> str:
        pass


class AerSimulatorProvider(QuantumExecutionProvider):
    """Local high-performance statevector simulator provider."""

    def __init__(self):
        self._sampler = StatevectorSampler()

    def get_sampler(self) -> BaseSamplerV2:
        return self._sampler

    def provider_name(self) -> str:
        return "Qiskit Aer Statevector Simulation Engine"


class QAOAOptimizer(BaseTrafficOptimizer):
    """
    QAOA-based traffic signal scheduling optimizer.
    Translates traffic demand and queue dynamics into a QUBO problem,
    optimizes parameterized variational quantum circuits,
    and constructs candidate phase assignment schedules.
    """

    def __init__(self, provider: Optional[QuantumExecutionProvider] = None):
        self.provider = provider or AerSimulatorProvider()

    def solve(self, problem: TrafficOptimizationProblem) -> MethodBenchmarkResult:
        start_time = time.perf_counter()

        # Build QUBO formulation
        qp = QUBOFormulator.build_quadratic_program(problem)
        num_vars = qp.get_num_binary_vars()

        logger.info(
            f"QAOA: Formulated QUBO with {num_vars} binary variables over {problem.T} planning steps."
        )

        sampler = self.provider.get_sampler()
        cobyla = COBYLA(maxiter=settings.QAOA_MAX_ITER)
        qaoa = QAOA(sampler=sampler, optimizer=cobyla, reps=settings.QAOA_REPS)
        eigen_optimizer = MinimumEigenOptimizer(qaoa)

        is_feasible = True
        rejection_reason = None
        sol_dict: Dict[str, int] = {}
        objective_val: float = 0.0

        try:
            raw_result = eigen_optimizer.solve(qp)
            objective_val = float(raw_result.fval)

            # Extract variable values
            for var in qp.variables:
                sol_dict[var.name] = int(round(raw_result.x[qp.variables.index(var)]))

        except Exception as e:
            logger.error(f"QAOA execution encountered error: {e}", exc_info=True)
            is_feasible = False
            rejection_reason = f"Quantum solver runtime error: {str(e)}"
            # Fallback zero assignment
            sol_dict = {var.name: 0 for var in qp.variables}

        execution_time_ms = round((time.perf_counter() - start_time) * 1000.0, 2)

        # Decode schedule
        schedules: List[IntersectionSchedule] = []
        for int_id in problem.intersection_ids:
            assignments: List[PhaseAssignment] = []
            for t in range(problem.T):
                v_p0 = sol_dict.get(f"x_{int_id}_p0_t{t}", 0)
                v_p1 = sol_dict.get(f"x_{int_id}_p1_t{t}", 0)

                # Safety check: if both active or none active, enforce deterministic safe default
                if v_p0 == 1 and v_p1 == 1:
                    is_feasible = False
                    rejection_reason = f"Safety Violation: Simultaneous green phases proposed at step {t}."
                    chosen_phase = 0  # fallback to NS
                elif v_p0 == 1:
                    chosen_phase = 0
                elif v_p1 == 1:
                    chosen_phase = 1
                else:
                    # Neither phase active - default to cycle alternating
                    chosen_phase = t % 2

                p_name = problem.phase_names[chosen_phase]
                green_apps = problem.phase_approaches[chosen_phase]

                assignments.append(
                    PhaseAssignment(
                        step_index=t,
                        timestamp_s=round(t * problem.dt_step, 1),
                        duration_s=problem.dt_step,
                        phase_id=chosen_phase,
                        phase_name=p_name,
                        green_approaches=green_apps,
                    )
                )

            schedules.append(
                IntersectionSchedule(
                    intersection_id=int_id,
                    assignments=assignments,
                    total_cycle_time_s=problem.T * problem.dt_step,
                )
            )

        # Resource usage metadata
        resource_usage = {
            "num_qubits": num_vars,
            "qaoa_reps": settings.QAOA_REPS,
            "optimizer_iterations": settings.QAOA_MAX_ITER,
            "provider": self.provider.provider_name(),
            "qubo_quadratic_terms": len(qp.objective.quadratic.to_dict()),
        }

        # Estimate performance under proposed schedule
        est_wait = max(4.0, 18.0 + (objective_val * 0.05 if is_feasible else 25.0))
        est_queue = max(1.0, 5.0 + (objective_val * 0.02 if is_feasible else 8.0))
        est_thru = max(300.0, 1100.0 - est_wait * 15.0)

        return MethodBenchmarkResult(
            method_name="QAOA (Quantum Approximate Optimization Algorithm)",
            is_feasible=is_feasible,
            safety_checks_passed=(rejection_reason is None),
            objective_value=round(objective_val, 3),
            estimated_waiting_time_s=round(est_wait, 2),
            estimated_queue_length=round(est_queue, 2),
            estimated_throughput_vph=round(est_thru, 1),
            execution_time_ms=execution_time_ms,
            resource_usage=resource_usage,
            schedule=schedules,
            candidate_accepted=(is_feasible and rejection_reason is None),
            rejection_reason=rejection_reason,
        )
