import math
from typing import Optional
from backend.app.models.simulation_models import (
    ApproachDirection,
    SignalColor,
    VehicleType,
    VehicleState,
)


class Vehicle:
    """
    Simulated Vehicle implementing the Intelligent Driver Model (IDM)
    with strict red-light stop bar enforcement and queue dynamics.
    Guarantees that vehicles smoothly decelerate and come to a complete stop
    at red traffic lights without overshooting into the intersection.
    """

    def __init__(
        self,
        vehicle_id: str,
        intersection_id: str,
        approach: ApproachDirection,
        lane_id: str,
        spawn_time_s: float,
        vehicle_type: VehicleType = VehicleType.CAR,
        desired_speed_mps: float = 13.89,  # ~50 km/h
        length_m: float = 4.5,
    ):
        self.vehicle_id = vehicle_id
        self.intersection_id = intersection_id
        self.approach = approach
        self.lane_id = lane_id
        self.spawn_time_s = spawn_time_s
        self.vehicle_type = vehicle_type
        self.desired_speed_mps = desired_speed_mps
        self.length_m = length_m

        # Dynamic state
        self.position_m: float = 0.0  # 0 at entrance; stop_bar_m at stop line
        self.speed_mps: float = desired_speed_mps * 0.75  # enter moving
        self.acceleration_mps2: float = 0.0
        self.wait_time_s: float = 0.0
        self.total_travel_time_s: float = 0.0
        self.stops_count: int = 0
        self.is_queued: bool = False
        self.has_cleared: bool = False
        self.was_stopped_previously: bool = False
        self.has_entered_intersection: bool = False

        # IDM parameters
        self.a_max: float = 2.4  # comfortable max acceleration m/s^2
        self.b_comfort: float = 2.8  # comfortable deceleration m/s^2
        self.s0: float = 2.5  # minimum standstill gap meters
        self.time_headway_s: float = 1.3  # desired time headway

    def update_kinematics(
        self,
        dt: float,
        lead_vehicle: Optional["Vehicle"],
        approach_length_m: float,
        signal_color: SignalColor,
    ) -> None:
        """
        Updates speed, position, and queue metrics using IDM.
        Strictly prevents crossing the stop bar on red signals.
        """
        self.total_travel_time_s += dt
        stop_bar_m = approach_length_m - 2.0  # Stop line at approach_length - 2m (138m)
        dist_to_stop_bar = stop_bar_m - self.position_m

        # Determine effective obstacle distance and delta_v
        effective_lead_dist: float = 9999.0
        delta_v: float = 0.0

        # 1. Lead Vehicle Obstacle Check
        if lead_vehicle is not None:
            gap_to_lead = (lead_vehicle.position_m - lead_vehicle.length_m) - self.position_m
            if gap_to_lead > 0:
                effective_lead_dist = gap_to_lead
                delta_v = self.speed_mps - lead_vehicle.speed_mps
            else:
                effective_lead_dist = 0.1
                delta_v = self.speed_mps

        # 2. Red / Yellow Traffic Light Obstacle Check
        must_stop_at_signal = False
        if not self.has_entered_intersection:
            if signal_color == SignalColor.RED:
                must_stop_at_signal = True
            elif signal_color == SignalColor.YELLOW:
                # If vehicle can safely stop before stop bar, it must stop
                stopping_distance = (self.speed_mps ** 2) / (2.0 * self.b_comfort)
                if dist_to_stop_bar > stopping_distance + 2.0:
                    must_stop_at_signal = True

            if must_stop_at_signal:
                # Stop bar acts as stationary obstacle (v = 0)
                if dist_to_stop_bar < effective_lead_dist:
                    effective_lead_dist = max(0.1, dist_to_stop_bar)
                    delta_v = self.speed_mps

        # 3. Calculate IDM Acceleration
        s_star = self.s0 + max(
            0.0,
            self.speed_mps * self.time_headway_s
            + (self.speed_mps * delta_v) / (2.0 * math.sqrt(self.a_max * self.b_comfort)),
        )

        free_accel = 1.0 - math.pow(max(0.0, self.speed_mps) / max(0.1, self.desired_speed_mps), 4)
        interaction_accel = math.pow(s_star / max(0.1, effective_lead_dist), 2)
        accel = self.a_max * (free_accel - interaction_accel)

        # Smooth braking curve when approaching red stop bar
        if must_stop_at_signal and 0 < dist_to_stop_bar < 40.0:
            target_decel = -(self.speed_mps ** 2) / (2.0 * max(0.5, dist_to_stop_bar))
            accel = min(accel, target_decel)

        # Clamp acceleration
        accel = max(-8.5, min(self.a_max, accel))
        self.acceleration_mps2 = accel

        # 4. Integrate velocity and position
        new_speed = max(0.0, self.speed_mps + accel * dt)
        new_pos = self.position_m + new_speed * dt

        # 5. STRICT PHYSICAL CONSTRAINTS & RED LIGHT STOPPING
        # A. Stop Bar Constraint:
        # A vehicle that has not entered the intersection CANNOT cross stop_bar_m on RED or YELLOW
        if not self.has_entered_intersection and must_stop_at_signal:
            if new_pos >= stop_bar_m:
                new_pos = stop_bar_m
                new_speed = 0.0
                accel = 0.0

        # B. Permitted Entry: vehicle can ONLY enter the intersection if signal is GREEN
        if not self.has_entered_intersection:
            if signal_color == SignalColor.GREEN and new_pos >= stop_bar_m:
                self.has_entered_intersection = True

        # C. Lead Vehicle Anti-Collision Constraint
        if lead_vehicle is not None:
            max_allowed_pos = lead_vehicle.position_m - lead_vehicle.length_m - self.s0
            if new_pos >= max_allowed_pos:
                new_pos = max(0.0, max_allowed_pos)
                new_speed = min(new_speed, max(0.0, lead_vehicle.speed_mps))
                if lead_vehicle.speed_mps < 0.5:
                    new_speed = 0.0

        self.position_m = new_pos
        self.speed_mps = new_speed

        # 6. Queue and Waiting Time Tracking
        if self.speed_mps < 0.6:
            self.wait_time_s += dt
            self.is_queued = True
            if not self.was_stopped_previously:
                self.stops_count += 1
                self.was_stopped_previously = True
        else:
            self.is_queued = False
            if self.speed_mps > 2.5:
                self.was_stopped_previously = False

        # 7. Clearing Check (30m beyond stop bar through the intersection)
        if self.position_m >= (approach_length_m + 30.0):
            self.has_cleared = True

    def to_state(self) -> VehicleState:
        return VehicleState(
            id=self.vehicle_id,
            vehicle_type=self.vehicle_type,
            intersection_id=self.intersection_id,
            approach=self.approach,
            lane_id=self.lane_id,
            position_m=round(self.position_m, 2),
            speed_mps=round(self.speed_mps, 2),
            acceleration_mps2=round(self.acceleration_mps2, 2),
            wait_time_s=round(self.wait_time_s, 2),
            total_travel_time_s=round(self.total_travel_time_s, 2),
            stops_count=self.stops_count,
            is_queued=self.is_queued,
            has_cleared=self.has_cleared,
            has_entered_intersection=self.has_entered_intersection,
        )
