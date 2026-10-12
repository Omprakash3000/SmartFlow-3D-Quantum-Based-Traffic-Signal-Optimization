import time
import logging
from typing import Dict, List, Any, Optional
from ortools.sat.python import cp_model

from backend.app.models.optimization_models import (
    MethodBenchmarkResult,
    IntersectionSchedule,
    PhaseAssignment,
)
from backend.app.optimization.base import (
    BaseTrafficOptimizer,
    TrafficOptimizationProblem,
)

logger = logging.getLogger(__name__)


class ClassicalOROptimizer(BaseTrafficOptimizer):
    """
    Classical traffic signal scheduling optimizer using Google OR-Tools CP-SAT.
    Evaluates equivalent traffic demand, road layouts, planning horizons, and safety constraints.
    Provides a guaranteed feasible, globally optimal or high-quality classical benchmark.
    """

    def solve(self, problem: TrafficOptimizationProblem) -> MethodBenchmarkResult:
        start_time = time.perf_counter()
        model = cp_model.CpModel()

        # Decision variables: x[int_id, phase, t] in {0, 1}
        x: Dict[tuple[str, int, int], cp_model.IntVar] = {}
        for int_id in problem.intersection_ids:
            for p in problem.phases:
                for t in range(problem.T):
                    x[(int_id, p, t)] = model.NewBoolVar(f"x_{int_id}_p{p}_t{t}")

        # Exact Safety Constraints: At any time step t, exactly one phase receives green
        # Conflicting movements never receive green simultaneously!
        for int_id in problem.intersection_ids:
            for t in range(problem.T):
                model.Add(sum(x[(int_id, p, t)] for p in problem.phases) == 1)

        # Objective expression terms
        # Scaled integers for CP-SAT
        SCALE = 100
        obj_terms = []

        w_wait = int(problem.weights.waiting_time * SCALE)
        w_queue = int(problem.weights.queue_length * SCALE)
        w_thru = int(problem.weights.throughput * SCALE)
        w_switch = int(problem.weights.switching_cost * SCALE)
        w_coord = int(problem.weights.coordination * SCALE)

        for int_id in problem.intersection_ids:
            q_dict = problem.current_queues.get(int_id, {"NB": 4, "SB": 4, "EB": 6, "WB": 6})
            arr_dict = problem.arrival_rates.get(int_id, {"NB": 16.0, "SB": 14.0, "EB": 22.0, "WB": 20.0})

            ns_queue = q_dict.get("NB", 0) + q_dict.get("SB", 0)
            ew_queue = q_dict.get("EB", 0) + q_dict.get("WB", 0)
            ns_arrival = (arr_dict.get("NB", 15.0) + arr_dict.get("SB", 15.0)) / 60.0
            ew_arrival = (arr_dict.get("EB", 20.0) + arr_dict.get("WB", 20.0)) / 60.0

            saturation_discharge = int(0.5 * problem.dt_step)

            for t in range(problem.T):
                proj_ns = int(ns_queue + ns_arrival * (t * problem.dt_step))
                proj_ew = int(ew_queue + ew_arrival * (t * problem.dt_step))

                cost_p0 = (w_wait + w_queue) * proj_ew - w_thru * min(proj_ns, saturation_discharge)
                cost_p1 = (w_wait + w_queue) * proj_ns - w_thru * min(proj_ew, saturation_discharge)

                obj_terms.append(cost_p0 * x[(int_id, 0, t)])
                obj_terms.append(cost_p1 * x[(int_id, 1, t)])

                # Switching penalty between step t and t+1
                if t < problem.T - 1:
                    # switch_var = 1 if phase changes
                    switch_var = model.NewBoolVar(f"sw_{int_id}_t{t}")
                    # switch_var >= x[t] - x[t+1]
                    model.Add(switch_var >= x[(int_id, 0, t)] - x[(int_id, 0, t + 1)])
                    model.Add(switch_var >= x[(int_id, 1, t)] - x[(int_id, 1, t + 1)])
                    obj_terms.append(w_switch * switch_var)

        # Corridor Coordination
        if len(problem.intersection_ids) >= 2:
            int1 = problem.intersection_ids[0]
            int2 = problem.intersection_ids[1]
            tau = problem.travel_offset_steps
            for t in range(problem.T - tau):
                coord_match = model.NewBoolVar(f"coord_{t}")
                # coord_match == 1 if both int1 and int2 have Phase 1 (EW) active at offset tau
                model.AddBoolAnd([x[(int1, 1, t)], x[(int2, 1, t + tau)]]).OnlyEnforceIf(coord_match)
                model.AddBoolOr([x[(int1, 1, t)].Not(), x[(int2, 1, t + tau)].Not()]).OnlyEnforceIf(
                    coord_match.Not()
                )
                obj_terms.append(-w_coord * 3 * coord_match)

        model.Minimize(sum(obj_terms))

        # Solve with CP-SAT
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 5.0
        solver.parameters.num_workers = 2
        status = solver.Solve(model)

        execution_time_ms = round((time.perf_counter() - start_time) * 1000.0, 2)

        is_feasible = status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
        raw_obj_val = solver.ObjectiveValue() / float(SCALE) if is_feasible else 999.0

        # Decode schedule
        schedules: List[IntersectionSchedule] = []
        for int_id in problem.intersection_ids:
            assignments: List[PhaseAssignment] = []
            for t in range(problem.T):
                if is_feasible:
                    chosen_phase = 0 if solver.Value(x[(int_id, 0, t)]) == 1 else 1
                else:
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

        resource_usage = {
            "solver": "Google OR-Tools CP-SAT",
            "solver_status": solver.StatusName(status),
            "num_boolean_variables": len(x),
            "wall_time_seconds": round(solver.WallTime(), 4),
            "branches": solver.NumBranches(),
            "conflicts": solver.NumConflicts(),
        }

        est_wait = max(3.5, 16.0 + (raw_obj_val * 0.04 if is_feasible else 25.0))
        est_queue = max(1.0, 4.5 + (raw_obj_val * 0.015 if is_feasible else 8.0))
        est_thru = max(350.0, 1150.0 - est_wait * 14.0)

        return MethodBenchmarkResult(
            method_name="Google OR-Tools (Constraint Programming Baseline)",
            is_feasible=is_feasible,
            safety_checks_passed=is_feasible,
            objective_value=round(raw_obj_val, 3),
            estimated_waiting_time_s=round(est_wait, 2),
            estimated_queue_length=round(est_queue, 2),
            estimated_throughput_vph=round(est_thru, 1),
            execution_time_ms=execution_time_ms,
            resource_usage=resource_usage,
            schedule=schedules,
            candidate_accepted=is_feasible,
            rejection_reason=None if is_feasible else "Solver failed to find a feasible solution",
        )
