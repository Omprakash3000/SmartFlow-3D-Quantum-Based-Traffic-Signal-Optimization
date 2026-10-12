from typing import Literal
from fastapi import APIRouter, Path, Query, Response
from backend.app.models.simulation_models import SimulationMetrics
from backend.app.models.report_models import SimulationReport
from backend.app.services.simulation_manager import simulation_manager

router = APIRouter(prefix="/api/simulations", tags=["Metrics & Reporting"])


@router.get(
    "/{simulation_id}/metrics",
    response_model=SimulationMetrics,
    summary="Retrieve measured performance metrics",
)
def get_simulation_metrics(
    simulation_id: str = Path(..., description="Simulation identifier"),
):
    """
    Returns empirical performance metrics measured from authoritative simulated state:
    average wait times, queue lengths, throughput (vph), congestion index, and emissions.
    """
    return simulation_manager.get_metrics(simulation_id)


@router.get(
    "/{simulation_id}/report",
    summary="Export simulation report",
)
def export_simulation_report(
    simulation_id: str = Path(..., description="Simulation identifier"),
    format: Literal["json", "csv"] = Query(
        default="json", description="Report format: 'json' or 'csv'"
    ),
):
    """
    Exports a comprehensive audit and performance report for the simulation session.
    Calculated from actual simulation execution results.
    """
    if format == "csv":
        csv_data = simulation_manager.generate_csv_report(simulation_id)
        return Response(
            content=csv_data,
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=traffic_report_{simulation_id}.csv"
            },
        )

    # JSON format
    return simulation_manager.generate_report(simulation_id)
