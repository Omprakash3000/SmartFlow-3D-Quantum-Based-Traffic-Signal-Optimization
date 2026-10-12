import time
from typing import Dict, List, Optional
from backend.app.models.simulation_models import (
    SimulationConfig,
    SimulationStateResponse,
    SimulationMetrics,
    IntersectionState,
    ApproachState,
    LaneState,
    ApproachDirection,
    SignalColor,
)
from backend.app.simulation.network import RoadNetwork
from backend.app.simulation.vehicle import Vehicle
from backend.app.simulation.demand_generator import DemandGenerator
from backend.app.simulation.traffic_light import TrafficLightController


class SimulationEngine:
    """
    Self-contained, authoritative traffic simulation engine.
    Simulates intersections, approaches, lanes, vehicles, traffic lights, and signal phases.
    Calculates exact ground-truth metrics for baseline and optimized signal scenarios.
    """

    def __init__(self, simulation_id: str, config: SimulationConfig):
        self.simulation_id = simulation_id
        self.config = config
        self.dt = config.dt
        self.current_time_s: float = 0.0
        self.step_count: int = 0
        self.is_running: bool = False
        self.is_paused: bool = False
        self.is_completed: bool = False

        # Road Network
        self.network = RoadNetwork(
            topology=config.topology,
            speed_limit_mps=config.speed_limit_mps,
        )

        # Vehicle Demand Generator
        self.demand_generators: Dict[str, DemandGenerator] = {}
        for int_id in self.network.intersections.keys():
            self.demand_generators[int_id] = DemandGenerator(
                random_seed=config.random_seed + hash(int_id) % 1000,
                arrival_rates_vpm=config.approach_arrival_rates_vpm.copy(),
                desired_speed_mps=config.speed_limit_mps,
            )

        # Vehicles: active and completed
        self.active_vehicles: List[Vehicle] = []
        self.completed_vehicles: List[Vehicle] = []

        # Real-time metrics
        self.metrics = SimulationMetrics()

    def start(self) -> None:
        self.is_running = True
        self.is_paused = False

    def pause(self) -> None:
        self.is_paused = True

    def reset(self) -> None:
        self.current_time_s = 0.0
        self.step_count = 0
        self.is_running = False
        self.is_paused = False
        self.is_completed = False
        self.active_vehicles.clear()
        self.completed_vehicles.clear()
        self.metrics = SimulationMetrics()

        # Re-initialize network & demand
        self.network = RoadNetwork(
            topology=self.config.topology,
            speed_limit_mps=self.config.speed_limit_mps,
        )
        for int_id, gen in self.demand_generators.items():
            gen.reset()

    def update_demand(
        self,
        arrival_rates_vpm: Dict[str, float],
        speed_limit_mps: Optional[float] = None,
    ) -> None:
        for gen in self.demand_generators.values():
            gen.update_rates(arrival_rates_vpm)
        if speed_limit_mps is not None:
            self.config.speed_limit_mps = speed_limit_mps
            self.network.speed_limit_mps = speed_limit_mps

    def update_timing(
        self,
        intersection_id: str,
        phase_green_times_s: Dict[int, float],
    ) -> None:
        if intersection_id in self.network.intersections:
            controller = self.network.intersections[intersection_id].traffic_light
            for phase_id, green_time in phase_green_times_s.items():
                controller.set_phase_green_time(phase_id, green_time)

    def load_optimized_schedule(
        self,
        intersection_id: str,
        schedule_assignments: List[tuple[int, float]],
    ) -> None:
        if intersection_id in self.network.intersections:
            controller = self.network.intersections[intersection_id].traffic_light
            controller.load_schedule_plan(schedule_assignments)

    def step(self, delta_t: Optional[float] = None) -> SimulationStateResponse:
        """
        Advances the entire simulation by dt seconds.
        """
        dt = delta_t or self.dt
        self.current_time_s += dt
        self.step_count += 1

        if self.current_time_s >= self.config.duration_s:
            self.is_completed = True
            self.is_running = False

        # 1. Update traffic lights
        for intersection in self.network.intersections.values():
            intersection.traffic_light.step(dt)

        # 2. Spawn new arrivals
        for int_id, generator in self.demand_generators.items():
            new_vehs = generator.generate_step_arrivals(
                current_time_s=self.current_time_s,
                dt=dt,
                intersection_id=int_id,
            )
            for nv in new_vehs:
                # Ensure no spawn overlapping on entrance lane
                lane_vehs = [
                    v
                    for v in self.active_vehicles
                    if v.intersection_id == nv.intersection_id
                    and v.lane_id == nv.lane_id
                ]
                if not lane_vehs or min(v.position_m for v in lane_vehs) > (nv.length_m + 3.0):
                    self.active_vehicles.append(nv)
                    self.metrics.total_vehicles_spawned += 1

        # 3. Update vehicle kinematics grouped by lane
        remaining_vehicles: List[Vehicle] = []
        # Group active vehicles by (intersection_id, lane_id)
        grouped_lanes: Dict[tuple[str, str], List[Vehicle]] = {}
        for v in self.active_vehicles:
            key = (v.intersection_id, v.lane_id)
            if key not in grouped_lanes:
                grouped_lanes[key] = []
            grouped_lanes[key].append(v)

        for (int_id, lane_id), lane_vehs in grouped_lanes.items():
            # Sort vehicles so furthest ahead is index 0
            lane_vehs.sort(key=lambda v: v.position_m, reverse=True)
            intersection = self.network.intersections[int_id]

            for i, veh in enumerate(lane_vehs):
                lead_veh = lane_vehs[i - 1] if i > 0 else None
                approach_obj = intersection.approaches[veh.approach]
                approach_length = approach_obj.length_m
                sig_color = intersection.traffic_light.get_signal_for_approach(veh.approach)

                veh.update_kinematics(
                    dt=dt,
                    lead_vehicle=lead_veh,
                    approach_length_m=approach_length,
                    signal_color=sig_color,
                )

                if veh.has_cleared:
                    # Check if transferred to downstream intersection along corridor
                    downstream_id = self.network.downstream_connections.get(int_id, {}).get(
                        veh.approach.value
                    )
                    if downstream_id and downstream_id in self.network.intersections:
                        # Transfer into downstream intersection approach
                        veh.intersection_id = downstream_id
                        veh.position_m = 0.0
                        veh.has_cleared = False
                        veh.has_entered_intersection = False
                        remaining_vehicles.append(veh)
                    else:
                        self.completed_vehicles.append(veh)
                        self.metrics.total_vehicles_completed += 1
                else:
                    remaining_vehicles.append(veh)

        self.active_vehicles = remaining_vehicles
        self._calculate_metrics()
        return self.get_state()

    def _calculate_metrics(self) -> None:
        """Computes authoritative performance metrics from simulated state."""
        num_active = len(self.active_vehicles)
        num_completed = len(self.completed_vehicles)
        all_vehs = self.active_vehicles + self.completed_vehicles

        self.metrics.active_vehicles_count = num_active

        if all_vehs:
            total_wait = sum(v.wait_time_s for v in all_vehs)
            self.metrics.average_waiting_time_s = round(total_wait / len(all_vehs), 2)
        else:
            self.metrics.average_waiting_time_s = 0.0

        # Queue lengths
        per_app_queues: Dict[str, int] = {}
        per_app_waits: Dict[str, float] = {}

        for app_dir in [
            ApproachDirection.NORTHBOUND,
            ApproachDirection.SOUTHBOUND,
            ApproachDirection.EASTBOUND,
            ApproachDirection.WESTBOUND,
        ]:
            app_vehs = [v for v in self.active_vehicles if v.approach == app_dir]
            queued = sum(1 for v in app_vehs if v.is_queued)
            per_app_queues[app_dir.value] = queued
            if app_vehs:
                per_app_waits[app_dir.value] = round(
                    sum(v.wait_time_s for v in app_vehs) / len(app_vehs), 2
                )
            else:
                per_app_waits[app_dir.value] = 0.0

        self.metrics.per_approach_queues = per_app_queues
        self.metrics.per_approach_wait_times = per_app_waits

        total_queued = sum(per_app_queues.values())
        num_approaches = max(1, len(self.network.intersections) * 4)
        self.metrics.average_queue_length = round(total_queued / num_approaches, 2)
        self.metrics.max_queue_length = max(per_app_queues.values()) if per_app_queues else 0

        # Throughput in vehicles per hour (vph)
        elapsed_hours = max(self.current_time_s / 3600.0, 1.0 / 3600.0)
        self.metrics.throughput_vph = round(num_completed / elapsed_hours, 1)

        # Congestion index: ratio of average travel time vs free flow travel time
        free_flow_time = 140.0 / max(1.0, self.config.speed_limit_mps)
        if all_vehs:
            avg_travel_time = sum(v.total_travel_time_s for v in all_vehs) / len(all_vehs)
            self.metrics.congestion_index = round(
                max(0.0, (avg_travel_time - free_flow_time) / free_flow_time), 3
            )
        else:
            self.metrics.congestion_index = 0.0

        # Environmental impacts
        total_wait_hours = sum(v.wait_time_s for v in all_vehs) / 3600.0
        # Average idle fuel consumption ~ 0.8 L/hr
        self.metrics.total_fuel_penalty_liters = round(total_wait_hours * 0.8, 2)
        # Average CO2 emission per liter ~ 2.31 kg/L
        self.metrics.total_co2_emission_kg = round(self.metrics.total_fuel_penalty_liters * 2.31, 2)

    def get_state(self) -> SimulationStateResponse:
        intersection_states: List[IntersectionState] = []

        for int_id, inter in self.network.intersections.items():
            approach_states: Dict[str, ApproachState] = {}
            for app_dir, approach in inter.approaches.items():
                lane_states: List[LaneState] = []
                for lane_id, lane in approach.lanes.items():
                    l_vehs = [
                        v
                        for v in self.active_vehicles
                        if v.intersection_id == int_id and v.lane_id == lane_id
                    ]
                    q_len = sum(1 for v in l_vehs if v.is_queued)
                    avg_spd = (
                        sum(v.speed_mps for v in l_vehs) / len(l_vehs) if l_vehs else lane.speed_limit_mps
                    )
                    lane_states.append(
                        LaneState(
                            lane_id=lane_id,
                            approach=app_dir,
                            length_m=lane.length_m,
                            speed_limit_mps=lane.speed_limit_mps,
                            vehicle_count=len(l_vehs),
                            queue_length=q_len,
                            average_speed_mps=round(avg_spd, 2),
                        )
                    )

                app_vehs = [
                    v
                    for v in self.active_vehicles
                    if v.intersection_id == int_id and v.approach == app_dir
                ]
                tot_q = sum(1 for v in app_vehs if v.is_queued)
                avg_wt = (
                    sum(v.wait_time_s for v in app_vehs) / len(app_vehs) if app_vehs else 0.0
                )
                sig_col = inter.traffic_light.get_signal_for_approach(app_dir)

                approach_states[app_dir.value] = ApproachState(
                    approach=app_dir,
                    lanes=lane_states,
                    total_vehicles=len(app_vehs),
                    queue_length=tot_q,
                    current_signal=sig_col,
                    average_wait_time_s=round(avg_wt, 2),
                )

            intersection_states.append(
                IntersectionState(
                    id=inter.intersection_id,
                    name=inter.name,
                    x=inter.x,
                    y=inter.y,
                    signal=inter.traffic_light.get_state(),
                    approaches=approach_states,
                )
            )

        return SimulationStateResponse(
            simulation_id=self.simulation_id,
            step=self.step_count,
            current_time_s=round(self.current_time_s, 2),
            is_running=self.is_running,
            is_paused=self.is_paused,
            is_completed=self.is_completed,
            topology=self.config.topology,
            intersections=intersection_states,
            vehicles=[v.to_state() for v in self.active_vehicles],
            metrics=self.metrics,
        )
