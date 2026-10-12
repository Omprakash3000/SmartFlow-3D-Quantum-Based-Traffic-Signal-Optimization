from fastapi import APIRouter, Path
from backend.app.models.optimization_models import (
    OptimizationRequest,
    OptimizationComparisonResponse,
)
from backend.app.services.simulation_manager import simulation_manager

router = APIRouter(prefix="/api/simulations", tags=["Signal Optimization & Benchmarking"])


@router.post(
    "/{simulation_id}/optimize",
    response_model=OptimizationComparisonResponse,
    summary="Request optimized signal schedules",
)
def optimize_signals(
    request: OptimizationRequest,
    simulation_id: str = Path(..., description="Simulation identifier"),
):
    """
    Executes the optimization pipeline on current traffic demand and queue states.
    Supports QAOA quantum optimization, Google OR-Tools classical optimization, or both.
    Safety constraints (conflict matrix & minimum green) are rigorously verified.
    Returns proposed schedule, benchmark comparisons, and improvements.
    """
    return simulation_manager.optimize(simulation_id, request)


@router.get(
    "/{simulation_id}/compare",
    response_model=OptimizationComparisonResponse,
    summary="Compare baseline and optimized scenarios",
)
def get_scenario_comparison(
    simulation_id: str = Path(..., description="Simulation identifier"),
):
    """
    Retrieves comparative metrics between the original baseline signal timing
    and the proposed optimized schedule.
    """
    return simulation_manager.get_comparison(simulation_id)
