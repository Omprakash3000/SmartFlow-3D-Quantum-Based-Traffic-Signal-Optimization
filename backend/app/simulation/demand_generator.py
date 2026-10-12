import random
from typing import Dict, List, Optional
from backend.app.models.simulation_models import (
    ApproachDirection,
    VehicleType,
)
from backend.app.simulation.vehicle import Vehicle


class DemandGenerator:
    """
    Deterministic vehicle arrival generator.
    Produces identical vehicle arrivals when initialized with the same random seed,
    ensuring rigorous, fair comparisons between baseline and optimized signal timing.
    """

    def __init__(
        self,
        random_seed: int = 42,
        arrival_rates_vpm: Optional[Dict[str, float]] = None,
        desired_speed_mps: float = 13.89,
    ):
        self.random_seed = random_seed
        self.rng = random.Random(random_seed)
        self.desired_speed_mps = desired_speed_mps

        # Arrival rates in vehicles per minute (vpm)
        self.arrival_rates_vpm: Dict[str, float] = arrival_rates_vpm or {
            ApproachDirection.NORTHBOUND.value: 16.0,
            ApproachDirection.SOUTHBOUND.value: 14.0,
            ApproachDirection.EASTBOUND.value: 22.0,
            ApproachDirection.WESTBOUND.value: 20.0,
        }

        self.vehicle_counter: int = 0

    def update_rates(self, new_rates: Dict[str, float]) -> None:
        for app, rate in new_rates.items():
            if rate >= 0.0:
                self.arrival_rates_vpm[app] = float(rate)

    def reset(self) -> None:
        self.rng = random.Random(self.random_seed)
        self.vehicle_counter = 0

    def generate_step_arrivals(
        self,
        current_time_s: float,
        dt: float,
        intersection_id: str,
        lanes_per_approach: int = 2,
    ) -> List[Vehicle]:
        """
        Samples Poisson arrival process for each approach over time interval dt.
        Returns newly spawned Vehicle objects.
        """
        new_vehicles: List[Vehicle] = []

        for approach_str, rate_vpm in self.arrival_rates_vpm.items():
            # Lambda for time interval dt (rate in vehicles per second)
            rate_vps = rate_vpm / 60.0
            prob_arrival = 1.0 - (2.718281828459045 ** (-rate_vps * dt))

            if self.rng.random() < prob_arrival:
                self.vehicle_counter += 1
                vehicle_id = f"veh_{intersection_id}_{approach_str}_{self.vehicle_counter}"

                # Assign lane (round-robin or random)
                lane_num = self.rng.randint(0, lanes_per_approach - 1)
                lane_id = f"{approach_str}_lane_{lane_num}"

                # Randomize vehicle type (90% car, 7% bus, 3% truck)
                r_type = self.rng.random()
                if r_type < 0.90:
                    v_type = VehicleType.CAR
                    v_len = 4.5
                elif r_type < 0.97:
                    v_type = VehicleType.BUS
                    v_len = 10.0
                else:
                    v_type = VehicleType.TRUCK
                    v_len = 12.0

                approach_enum = ApproachDirection(approach_str)
                veh = Vehicle(
                    vehicle_id=vehicle_id,
                    intersection_id=intersection_id,
                    approach=approach_enum,
                    lane_id=lane_id,
                    spawn_time_s=current_time_s,
                    vehicle_type=v_type,
                    desired_speed_mps=self.desired_speed_mps + self.rng.uniform(-1.0, 1.5),
                    length_m=v_len,
                )
                new_vehicles.append(veh)

        return new_vehicles
