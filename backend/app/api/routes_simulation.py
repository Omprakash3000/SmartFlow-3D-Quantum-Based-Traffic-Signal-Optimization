from typing import List, Optional
from fastapi import APIRouter, Query, Path
from backend.app.models.simulation_models import (
    SimulationConfig,
    SimulationStateResponse,
    DemandUpdateRequest,
    TimingUpdateRequest,
)
from backend.app.services.simulation_manager import simulation_manager

router = APIRouter(prefix="/api/simulations", tags=["Simulation Management"])


@router.post("", response_model=SimulationStateResponse, summary="Create and configure a traffic simulation")
def create_simulation(
    config: SimulationConfig,
    simulation_id: Optional[str] = Query(default=None, description="Optional custom simulation identifier"),
):
    """
    Creates and configures a new traffic simulation instance.
    Specifies topology ('single_intersection', 'two_corridor', 'grid_2x2'),
    arrival rates per approach, speed limit, and duration.
    """
    return simulation_manager.create_simulation(simulation_id, config)


@router.get("", response_model=List[str], summary="List active simulation IDs")
def list_simulations():
    """Returns a list of all currently loaded simulation session identifiers."""
    return simulation_manager.list_simulations()


@router.get("/{simulation_id}/state", response_model=SimulationStateResponse, summary="Get authoritative simulation state")
def get_simulation_state(
    simulation_id: str = Path(..., description="Simulation identifier"),
):
    """
    Retrieves the authoritative simulation state containing all intersections,
    signal phases, approach queues, individual vehicle positions/speeds, and metrics.
    """
    return simulation_manager.get_state(simulation_id)


@router.post("/{simulation_id}/start", response_model=SimulationStateResponse, summary="Start traffic simulation")
def start_simulation(
    simulation_id: str = Path(..., description="Simulation identifier"),
):
    """Starts continuous execution of the simulated traffic flow."""
    return simulation_manager.start(simulation_id)


@router.post("/{simulation_id}/pause", response_model=SimulationStateResponse, summary="Pause traffic simulation")
def pause_simulation(
    simulation_id: str = Path(..., description="Simulation identifier"),
):
    """Pauses the current simulation clock."""
    return simulation_manager.pause(simulation_id)


@router.post("/{simulation_id}/reset", response_model=SimulationStateResponse, summary="Reset traffic simulation")
def reset_simulation(
    simulation_id: str = Path(..., description="Simulation identifier"),
):
    """Resets the simulation clock, clears all vehicles, and restores initial conditions."""
    return simulation_manager.reset(simulation_id)


@router.post("/{simulation_id}/step", response_model=SimulationStateResponse, summary="Step simulation forward")
def step_simulation(
    simulation_id: str = Path(..., description="Simulation identifier"),
    dt: Optional[float] = Query(default=None, ge=0.05, le=5.0, description="Step duration in seconds"),
):
    """Advances the simulation by dt seconds and returns the updated state."""
    return simulation_manager.step(simulation_id, dt)


@router.post("/{simulation_id}/demand", response_model=SimulationStateResponse, summary="Update traffic demand")
def update_demand(
    request: DemandUpdateRequest,
    simulation_id: str = Path(..., description="Simulation identifier"),
):
    """
    Dynamically adjusts vehicle arrival rates per approach (vpm) and speed limit.
    """
    return simulation_manager.update_demand(simulation_id, request)


@router.post("/{simulation_id}/timing", response_model=SimulationStateResponse, summary="Update signal timing")
def update_timing(
    request: TimingUpdateRequest,
    simulation_id: str = Path(..., description="Simulation identifier"),
):
    """
    Manually modifies signal green splits for a specified intersection.
    Enforces minimum green and clearance safety requirements.
    """
    return simulation_manager.update_timing(simulation_id, request)
