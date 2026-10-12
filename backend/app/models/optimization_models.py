from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


class OptimizationMethod(str, Enum):
    QAOA = "qaoa"
    CLASSICAL_ORTOOLS = "classical_ortools"
    BOTH = "both"


class OptimizationWeights(BaseModel):
    waiting_time: float = Field(default=1.0, ge=0.0, description="Weight for vehicle waiting time penalty")
    queue_length: float = Field(default=1.5, ge=0.0, description="Weight for queue length penalty")
    throughput: float = Field(default=1.2, ge=0.0, description="Weight for maximizing throughput (discharge)")
    switching_cost: float = Field(default=0.8, ge=0.0, description="Weight penalty for phase transitions")
    coordination: float = Field(default=1.0, ge=0.0, description="Weight for corridor green-wave progression")


class OptimizationRequest(BaseModel):
    method: OptimizationMethod = OptimizationMethod.BOTH
    planning_horizon_steps: int = Field(default=8, ge=4, le=16, description="Discrete planning intervals")
    step_duration_s: float = Field(default=10.0, ge=5.0, le=30.0, description="Duration of each scheduling interval")
    weights: OptimizationWeights = Field(default_factory=OptimizationWeights)
    apply_to_simulation: bool = Field(default=True, description="Whether to apply winning schedule to running simulation")


class PhaseAssignment(BaseModel):
    step_index: int
    timestamp_s: float
    duration_s: float
    phase_id: int
    phase_name: str
    green_approaches: List[str]


class IntersectionSchedule(BaseModel):
    intersection_id: str
    assignments: List[PhaseAssignment]
    total_cycle_time_s: float


class MethodBenchmarkResult(BaseModel):
    method_name: str
    is_feasible: bool
    safety_checks_passed: bool
    objective_value: float
    estimated_waiting_time_s: float
    estimated_queue_length: float
    estimated_throughput_vph: float
    execution_time_ms: float
    resource_usage: Dict[str, Any]
    schedule: List[IntersectionSchedule]
    candidate_accepted: bool
    rejection_reason: Optional[str] = None


class ComparisonMetricItem(BaseModel):
    metric_name: str
    baseline: float
    optimized: float
    difference: float
    improvement_percent: float
    unit: str


class OptimizationComparisonResponse(BaseModel):
    simulation_id: str
    planning_horizon_s: float
    original_schedule: List[IntersectionSchedule]
    proposed_schedule: List[IntersectionSchedule]
    selected_method: str
    benchmarks: Dict[str, MethodBenchmarkResult]
    comparisons: Dict[str, ComparisonMetricItem]
    per_approach_queues: Dict[str, int]
    safety_audit_passed: bool
    status_summary: str
