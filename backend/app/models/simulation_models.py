from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class ApproachDirection(str, Enum):
    NORTHBOUND = "NB"
    SOUTHBOUND = "SB"
    EASTBOUND = "EB"
    WESTBOUND = "WB"


class SignalColor(str, Enum):
    RED = "RED"
    YELLOW = "YELLOW"
    GREEN = "GREEN"


class PhaseConfig(BaseModel):
    phase_id: int
    name: str
    active_approaches: List[ApproachDirection]
    min_green_s: float = 5.0
    max_green_s: float = 60.0
    yellow_duration_s: float = 3.0
    all_red_duration_s: float = 2.0


class TrafficLightState(BaseModel):
    intersection_id: str
    current_phase_id: int
    current_color: SignalColor
    elapsed_in_phase_s: float
    target_green_duration_s: float
    approach_signals: Dict[str, SignalColor]


class VehicleType(str, Enum):
    CAR = "car"
    BUS = "bus"
    TRUCK = "truck"


class VehicleState(BaseModel):
    id: str
    vehicle_type: VehicleType = VehicleType.CAR
    intersection_id: str
    approach: ApproachDirection
    lane_id: str
    position_m: float  # distance along approach (0 = start, approach_length = stop bar)
    speed_mps: float
    acceleration_mps2: float = 0.0
    wait_time_s: float = 0.0
    total_travel_time_s: float = 0.0
    stops_count: int = 0
    is_queued: bool = False
    has_cleared: bool = False
    has_entered_intersection: bool = False


class LaneState(BaseModel):
    lane_id: str
    approach: ApproachDirection
    length_m: float
    speed_limit_mps: float
    vehicle_count: int
    queue_length: int
    average_speed_mps: float


class ApproachState(BaseModel):
    approach: ApproachDirection
    lanes: List[LaneState]
    total_vehicles: int
    queue_length: int
    current_signal: SignalColor
    average_wait_time_s: float


class IntersectionState(BaseModel):
    id: str
    name: str
    x: float
    y: float
    signal: TrafficLightState
    approaches: Dict[str, ApproachState]


class SimulationMetrics(BaseModel):
    total_vehicles_spawned: int = 0
    total_vehicles_completed: int = 0
    active_vehicles_count: int = 0
    average_waiting_time_s: float = 0.0
    average_queue_length: float = 0.0
    max_queue_length: int = 0
    throughput_vph: float = 0.0  # vehicles per hour
    congestion_index: float = 0.0  # ratio of delay to ideal travel time
    per_approach_queues: Dict[str, int] = Field(default_factory=dict)
    per_approach_wait_times: Dict[str, float] = Field(default_factory=dict)
    total_fuel_penalty_liters: float = 0.0
    total_co2_emission_kg: float = 0.0


class SimulationConfig(BaseModel):
    topology: str = Field(
        default="two_corridor",
        description="Topology: 'single_intersection', 'two_corridor', or 'grid_2x2'"
    )
    duration_s: float = Field(default=300.0, ge=30.0, le=3600.0)
    dt: float = Field(default=0.5, ge=0.1, le=1.0)
    random_seed: int = Field(default=42)
    approach_arrival_rates_vpm: Dict[str, float] = Field(
        default_factory=lambda: {
            "NB": 16.0,
            "SB": 14.0,
            "EB": 22.0,
            "WB": 20.0
        },
        description="Vehicles per minute per approach"
    )
    speed_limit_mps: float = Field(default=13.89, ge=5.0, le=30.0)
    default_cycle_time_s: float = Field(default=60.0, ge=30.0, le=120.0)


class DemandUpdateRequest(BaseModel):
    approach_rates_vpm: Dict[str, float] = Field(
        ...,
        description="Updated vehicle arrival rates (vpm) keyed by approach or intersection_approach"
    )
    speed_limit_mps: Optional[float] = Field(default=None, ge=5.0, le=30.0)


class TimingUpdateRequest(BaseModel):
    intersection_id: str
    phase_green_times_s: Dict[int, float] = Field(
        ...,
        description="Dict mapping phase_id to green time in seconds"
    )
    cycle_time_s: Optional[float] = Field(default=None, ge=20.0, le=180.0)


class SimulationStateResponse(BaseModel):
    simulation_id: str
    step: int
    current_time_s: float
    is_running: bool
    is_paused: bool
    is_completed: bool
    topology: str
    intersections: List[IntersectionState]
    vehicles: List[VehicleState]
    metrics: SimulationMetrics
