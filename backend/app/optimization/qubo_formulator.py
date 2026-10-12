from typing import Dict, Tuple
from qiskit_optimization import QuadraticProgram
from backend.app.optimization.base import TrafficOptimizationProblem


class QUBOFormulator:
    """
    Formulates the traffic signal scheduling problem into a QuadraticProgram / QUBO.
    Objective terms balance:
      1. Vehicle waiting time
      2. Queue length pressure
      3. Traffic throughput (discharge reward)
      4. Signal switching penalties (discouraging rapid oscillations)
      5. Corridor coordination (green wave progression)
    Safety constraints enforce that conflicting movements never receive green simultaneously.
    """

    SAFETY_PENALTY: float = 50.0  # High penalty multiplier enforcing strictly one active phase

    @staticmethod
    def build_quadratic_program(problem: TrafficOptimizationProblem) -> QuadraticProgram:
        qp = QuadraticProgram(name="TrafficSignalSchedulingQUBO")

        # Decision variables: x_{i}_{p}_{t} in {0, 1}
        # where i = intersection_id, p = phase (0: NS, 1: EW), t = step index
        var_names: Dict[Tuple[str, int, int], str] = {}
        for int_id in problem.intersection_ids:
            for p in problem.phases:
                for t in range(problem.T):
                    v_name = f"x_{int_id}_p{p}_t{t}"
                    qp.binary_var(name=v_name)
                    var_names[(int_id, p, t)] = v_name

        linear_terms: Dict[str, float] = {}
        quadratic_terms: Dict[Tuple[str, str], float] = {}

        w_wait = problem.weights.waiting_time
        w_queue = problem.weights.queue_length
        w_thru = problem.weights.throughput
        w_switch = problem.weights.switching_cost
        w_coord = problem.weights.coordination

        for int_id in problem.intersection_ids:
            q_dict = problem.current_queues.get(int_id, {"NB": 4, "SB": 4, "EB": 6, "WB": 6})
            arr_dict = problem.arrival_rates.get(int_id, {"NB": 16.0, "SB": 14.0, "EB": 22.0, "WB": 20.0})

            # Queue pressures:
            # Phase 0 (NS) serves NB & SB. Conflicting/waiting approaches are EB & WB.
            # Phase 1 (EW) serves EB & WB. Conflicting/waiting approaches are NB & SB.
            ns_queue = q_dict.get("NB", 0) + q_dict.get("SB", 0)
            ew_queue = q_dict.get("EB", 0) + q_dict.get("WB", 0)
            ns_arrival = (arr_dict.get("NB", 15.0) + arr_dict.get("SB", 15.0)) / 60.0
            ew_arrival = (arr_dict.get("EB", 20.0) + arr_dict.get("WB", 20.0)) / 60.0

            saturation_discharge = 0.5 * problem.dt_step  # ~0.5 veh/sec per lane discharged during green

            for t in range(problem.T):
                var_p0 = var_names[(int_id, 0, t)]
                var_p1 = var_names[(int_id, 1, t)]

                # Projected queues at step t
                proj_ns = ns_queue + ns_arrival * (t * problem.dt_step)
                proj_ew = ew_queue + ew_arrival * (t * problem.dt_step)

                # If Phase 0 is green (var_p0=1):
                #   - NS vehicles discharged (negative cost / reward)
                #   - EW vehicles wait (positive cost)
                cost_p0 = (w_wait + w_queue) * proj_ew - w_thru * min(proj_ns, saturation_discharge)
                # If Phase 1 is green (var_p1=1):
                #   - EW vehicles discharged (negative cost / reward)
                #   - NS vehicles wait (positive cost)
                cost_p1 = (w_wait + w_queue) * proj_ns - w_thru * min(proj_ew, saturation_discharge)

                linear_terms[var_p0] = linear_terms.get(var_p0, 0.0) + cost_p0
                linear_terms[var_p1] = linear_terms.get(var_p1, 0.0) + cost_p1

                # Safety penalty: (x_p0 + x_p1 - 1)^2 = x_p0^2 + x_p1^2 + 2 x_p0 x_p1 - 2 x_p0 - 2 x_p1 + 1
                # In binary: x^2 = x, so: (1 - 2) * x_p0 = -1 * x_p0
                p_safe = QUBOFormulator.SAFETY_PENALTY
                linear_terms[var_p0] = linear_terms.get(var_p0, 0.0) - p_safe
                linear_terms[var_p1] = linear_terms.get(var_p1, 0.0) - p_safe
                quadratic_terms[(var_p0, var_p1)] = (
                    quadratic_terms.get((var_p0, var_p1), 0.0) + 2.0 * p_safe
                )

                # Signal switching costs between step t and step t+1:
                # If signal switches from phase 0 to phase 1 (or 1 to 0), incur switching cost
                if t < problem.T - 1:
                    var_next_p0 = var_names[(int_id, 0, t + 1)]
                    var_next_p1 = var_names[(int_id, 1, t + 1)]
                    # x_p0_t * x_p1_t+1 (switch from 0 to 1)
                    quadratic_terms[(var_p0, var_next_p1)] = (
                        quadratic_terms.get((var_p0, var_next_p1), 0.0) + w_switch * 2.0
                    )
                    # x_p1_t * x_p0_t+1 (switch from 1 to 0)
                    quadratic_terms[(var_p1, var_next_p0)] = (
                        quadratic_terms.get((var_p1, var_next_p0), 0.0) + w_switch * 2.0
                    )

        # Corridor coordination between neighboring intersections
        # If there are at least 2 intersections (e.g. INT_1 and INT_2), reward green wave offset along EW corridor
        if len(problem.intersection_ids) >= 2:
            int1 = problem.intersection_ids[0]
            int2 = problem.intersection_ids[1]
            tau = problem.travel_offset_steps
            for t in range(problem.T - tau):
                v1_ew = var_names[(int1, 1, t)]
                v2_ew = var_names[(int2, 1, t + tau)]
                # Reward coordinated green wave: negative cost when both are 1
                quadratic_terms[(v1_ew, v2_ew)] = (
                    quadratic_terms.get((v1_ew, v2_ew), 0.0) - w_coord * 3.0
                )

        qp.minimize(linear=linear_terms, quadratic=quadratic_terms)
        return qp
