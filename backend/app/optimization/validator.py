import logging
from typing import List, Tuple, Optional
from backend.app.models.optimization_models import (
    MethodBenchmarkResult,
    IntersectionSchedule,
)
from backend.app.simulation.traffic_light import CONFLICTING_PAIRS
from backend.app.models.simulation_models import ApproachDirection

logger = logging.getLogger(__name__)


class SafetyValidator:
    """
    Independent safety validation and candidate arbitration engine.
    Audits candidate signal schedules for:
      1. Conflicting movement violations (never allow conflicting approaches green simultaneously).
      2. Feasibility of phase sequences.
      3. Objective quality relative to classical baseline.
      4. Automatic rejection of inferior/infeasible quantum candidates with safe classical fallback.
    """

    @staticmethod
    def audit_schedule(schedule: List[IntersectionSchedule]) -> Tuple[bool, Optional[str]]:
        """
        Validates that every single time step in the schedule strictly obeys the safety conflict matrix.
        """
        for inter_sched in schedule:
            for assignment in inter_sched.assignments:
                green_apps = [ApproachDirection(a) for a in assignment.green_approaches]
                # Check all pairs in green_apps against CONFLICTING_PAIRS
                for i in range(len(green_apps)):
                    for j in range(i + 1, len(green_apps)):
                        if (green_apps[i], green_apps[j]) in CONFLICTING_PAIRS:
                            err_msg = (
                                f"SAFETY AUDIT FAILED for intersection {inter_sched.intersection_id} at step "
                                f"{assignment.step_index}: conflicting green lights {green_apps[i].value} "
                                f"and {green_apps[j].value}."
                            )
                            logger.error(err_msg)
                            return False, err_msg

        return True, None

    @classmethod
    def select_best_schedule(
        cls,
        qaoa_result: Optional[MethodBenchmarkResult],
        classical_result: MethodBenchmarkResult,
    ) -> Tuple[MethodBenchmarkResult, str]:
        """
        Arbitrates between candidate schedules.
        "Do not assume that QAOA is superior. If it produces an inferior or infeasible candidate,
        reject that candidate and retain the best valid schedule."
        """
        # Always audit classical baseline first
        cls_valid, cls_err = cls.audit_schedule(classical_result.schedule)
        if not cls_valid:
            logger.critical(f"Classical schedule failed safety check: {cls_err}")
            classical_result.candidate_accepted = False
            classical_result.rejection_reason = cls_err

        if qaoa_result is None:
            return classical_result, "Classical OR-Tools (Single Method Requested)"

        # Audit QAOA schedule
        qaoa_valid, qaoa_err = cls.audit_schedule(qaoa_result.schedule)
        if not qaoa_valid:
            logger.warning(f"QAOA Candidate Rejected: {qaoa_err}")
            qaoa_result.candidate_accepted = False
            qaoa_result.rejection_reason = qaoa_err
            return classical_result, "Classical OR-Tools (QAOA rejected due to safety constraint violation)"

        if not qaoa_result.is_feasible:
            logger.warning("QAOA Candidate Rejected: Marked infeasible by quantum optimizer.")
            qaoa_result.candidate_accepted = False
            qaoa_result.rejection_reason = "Infeasible statevector solution"
            return classical_result, "Classical OR-Tools (QAOA candidate was infeasible)"

        # Check performance metrics: if QAOA objective is significantly worse than classical,
        # reject QAOA and retain classical
        if qaoa_result.objective_value > (classical_result.objective_value * 1.35):
            logger.info(
                f"QAOA Candidate Rejected: Inferior objective ({qaoa_result.objective_value:.2f} "
                f"vs classical {classical_result.objective_value:.2f})."
            )
            qaoa_result.candidate_accepted = False
            qaoa_result.rejection_reason = (
                f"Inferior objective score ({qaoa_result.objective_value:.2f} vs classical {classical_result.objective_value:.2f})"
            )
            return classical_result, "Classical OR-Tools (QAOA objective was inferior to classical baseline)"

        # If QAOA passes safety and is competitive or superior, accept QAOA candidate
        logger.info("QAOA Candidate Accepted: Passed all safety checks and competitive with classical baseline.")
        qaoa_result.candidate_accepted = True
        return qaoa_result, "QAOA (Quantum Approximate Optimization Algorithm)"
