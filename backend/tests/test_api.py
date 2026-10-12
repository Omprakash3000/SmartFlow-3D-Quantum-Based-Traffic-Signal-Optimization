import pytest
from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)


def test_health_check_endpoint():
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"


def test_simulation_lifecycle_api():
    # 1. Create Simulation
    create_payload = {
        "topology": "two_corridor",
        "duration_s": 180.0,
        "dt": 0.5,
        "random_seed": 77,
        "approach_arrival_rates_vpm": {"NB": 15.0, "SB": 15.0, "EB": 25.0, "WB": 20.0},
        "speed_limit_mps": 13.89,
    }
    resp = client.post("/api/simulations?simulation_id=test_api_sim", json=create_payload)
    assert resp.status_code == 200
    state = resp.json()
    assert state["simulation_id"] == "test_api_sim"
    assert len(state["intersections"]) == 2

    # 2. Step Simulation
    resp = client.post("/api/simulations/test_api_sim/step?dt=1.0")
    assert resp.status_code == 200
    state = resp.json()
    assert state["current_time_s"] == 1.0

    # 3. Get State
    resp = client.get("/api/simulations/test_api_sim/state")
    assert resp.status_code == 200
    state = resp.json()
    assert "metrics" in state

    # 4. Update Demand
    demand_payload = {
        "approach_rates_vpm": {"NB": 30.0, "SB": 30.0, "EB": 10.0, "WB": 10.0},
        "speed_limit_mps": 12.0,
    }
    resp = client.post("/api/simulations/test_api_sim/demand", json=demand_payload)
    assert resp.status_code == 200

    # 5. Update Timing
    timing_payload = {
        "intersection_id": "INT_1",
        "phase_green_times_s": {0: 35.0, 1: 20.0},
    }
    resp = client.post("/api/simulations/test_api_sim/timing", json=timing_payload)
    assert resp.status_code == 200

    # 6. Optimize Signals (using classical baseline for fast API test response)
    opt_payload = {
        "method": "classical_ortools",
        "planning_horizon_steps": 4,
        "step_duration_s": 10.0,
        "weights": {
            "waiting_time": 1.0,
            "queue_length": 1.5,
            "throughput": 1.2,
            "switching_cost": 0.8,
            "coordination": 1.0,
        },
        "apply_to_simulation": True,
    }
    resp = client.post("/api/simulations/test_api_sim/optimize", json=opt_payload)
    assert resp.status_code == 200
    comp = resp.json()
    assert "benchmarks" in comp
    assert comp["safety_audit_passed"] is True
    assert "waiting_time" in comp["comparisons"]

    # 7. Compare Scenarios
    resp = client.get("/api/simulations/test_api_sim/compare")
    assert resp.status_code == 200

    # 8. Get Metrics
    resp = client.get("/api/simulations/test_api_sim/metrics")
    assert resp.status_code == 200
    metrics = resp.json()
    assert "throughput_vph" in metrics

    # 9. Export Report (JSON)
    resp = client.get("/api/simulations/test_api_sim/report?format=json")
    assert resp.status_code == 200
    report = resp.json()
    assert report["simulation_id"] == "test_api_sim"
    assert "approaches" in report

    # 10. Export Report (CSV)
    resp = client.get("/api/simulations/test_api_sim/report?format=csv")
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    assert "SmartFlow Traffic Simulation Report" in resp.text
