import pytest
from backend.app.models.simulation_models import (
    SimulationConfig,
    ApproachDirection,
    SignalColor,
    VehicleType,
)
from backend.app.simulation.engine import SimulationEngine
from backend.app.simulation.vehicle import Vehicle
from backend.app.simulation.demand_generator import DemandGenerator


def test_simulation_initialization():
    config = SimulationConfig(
        topology="two_corridor",
        duration_s=120.0,
        random_seed=42,
    )
    engine = SimulationEngine(simulation_id="test_sim", config=config)
    assert engine.simulation_id == "test_sim"
    assert len(engine.network.intersections) == 2
    assert "INT_1" in engine.network.intersections
    assert "INT_2" in engine.network.intersections
    assert engine.current_time_s == 0.0
    assert engine.step_count == 0


def test_vehicle_idm_deceleration_at_red_signal():
    veh = Vehicle(
        vehicle_id="v1",
        intersection_id="INT_1",
        approach=ApproachDirection.NORTHBOUND,
        lane_id="NB_lane_0",
        spawn_time_s=0.0,
        desired_speed_mps=14.0,
    )
    veh.position_m = 150.0
    veh.speed_mps = 12.0
    approach_length = 180.0

    # Step vehicle approaching red light 30m away
    for _ in range(20):
        veh.update_kinematics(
            dt=0.5,
            lead_vehicle=None,
            approach_length_m=approach_length,
            signal_color=SignalColor.RED,
        )

    # Vehicle should have decelerated smoothly before the stop bar
    assert veh.speed_mps < 1.0
    assert veh.position_m <= approach_length + 1.0
    assert veh.is_queued is True
    assert veh.wait_time_s > 0.0


def test_deterministic_demand_reproducibility():
    gen1 = DemandGenerator(random_seed=999)
    gen2 = DemandGenerator(random_seed=999)

    arrivals1 = [gen1.generate_step_arrivals(t, 0.5, "INT_1") for t in range(50)]
    arrivals2 = [gen2.generate_step_arrivals(t, 0.5, "INT_1") for t in range(50)]

    assert len(arrivals1) == len(arrivals2)
    counts1 = [len(a) for a in arrivals1]
    counts2 = [len(a) for a in arrivals2]
    assert counts1 == counts2


def test_simulation_stepping_and_metrics():
    config = SimulationConfig(duration_s=60.0, dt=0.5, random_seed=123)
    engine = SimulationEngine("test_step_sim", config)

    # Step simulation 30 times (15 seconds)
    for _ in range(30):
        state = engine.step()

    assert state.step == 30
    assert state.current_time_s == 15.0
    assert state.metrics is not None
    assert isinstance(state.metrics.per_approach_queues, dict)
    assert "NB" in state.metrics.per_approach_queues
