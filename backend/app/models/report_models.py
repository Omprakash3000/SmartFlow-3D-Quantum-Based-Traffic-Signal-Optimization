from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field


class ApproachReportSummary(BaseModel):
    approach: str
    total_vehicles: int
    queue_length: int
    average_wait_time_s: float
    max_wait_time_s: float
    throughput_vph: float


class SimulationReport(BaseModel):
    report_id: str
    simulation_id: str
    generated_at: str
    topology: str
    duration_s: float
    elapsed_time_s: float
    traffic_demand_rates_vpm: Dict[str, float]
    
    # Measured Performance
    baseline_metrics: Dict[str, float]
    optimized_metrics: Optional[Dict[str, float]] = None
    improvements: Optional[Dict[str, float]] = None
    
    # Safety & Compliance
    safety_audit: Dict[str, Any]
    
    # Approach breakdown
    approaches: List[ApproachReportSummary]
    
    # Optimization & Benchmark Details
    optimization_summary: Optional[Dict[str, Any]] = None
    
    # Export formatting info
    data_source: str = "Empirical Simulation Engine"
    validation_status: str = "Verified Feasible & Safety-Checked"
