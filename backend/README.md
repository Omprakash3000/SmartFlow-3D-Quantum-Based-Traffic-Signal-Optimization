# SmartFlow3D — Internal Backend & Optimization Pipeline

> **CONFIDENTIAL / INTERNAL DEVELOPMENT ONLY**  
> All quantum optimization models, mathematical formulations, library dependencies, API routes, and backend architectures documented here are for internal engineering use only and must **never** be exposed on the public-facing interface.

---

## 1. Architecture Overview

SmartFlow3D Backend is built with **Python 3.12** and **FastAPI**, featuring:
- An authoritative, self-contained multi-intersection traffic simulation engine with explicit car-following dynamics (Intelligent Driver Model - IDM), queue length accumulation, stop-bar clearance, and arterial corridor platoon transfers.
- A **QAOA (Quantum Approximate Optimization Algorithm)** scheduling pipeline using **Qiskit** and the **Qiskit Aer** statevector simulator.
- A **Classical Benchmarking Baseline** using **Google OR-Tools** (CP-SAT constraint programming solver).
- An independent **Safety Constraint Validator** enforcing strict conflict matrices, non-overlapping green phases, minimum green durations, yellow clearance, and all-red clearance intervals.
- An arbitration engine with **automatic candidate rejection**: if QAOA produces an infeasible candidate or an objective inferior to the classical baseline, the candidate is safely rejected and the verified schedule is retained.
- Structured REST endpoints for simulation lifecycle, dynamic demand/timing updates, schedule optimization, scenario comparison, and multi-format report exports (JSON & CSV).

---

## 2. Directory Structure

```
backend/
├── app/
│   ├── api/
│   │   ├── routes_simulation.py       # Simulation lifecycle & control endpoints
│   │   ├── routes_optimization.py     # QAOA & OR-Tools optimization endpoints
│   │   └── routes_reports.py          # Metrics retrieval & CSV/JSON export
│   ├── models/
│   │   ├── simulation_models.py       # Pydantic schemas for state, lights, vehicles
│   │   ├── optimization_models.py     # Schemas for QUBO/QAOA requests & benchmarks
│   │   └── report_models.py           # Schemas for audit reports & metric differences
│   ├── optimization/
│   │   ├── base.py                    # Problem formulation & optimizer abstract base
│   │   ├── qubo_formulator.py         # QuadraticProgram QUBO builder
│   │   ├── qaoa_optimizer.py          # Qiskit QAOA optimizer & Aer provider
│   │   ├── classical_optimizer.py     # Google OR-Tools CP-SAT optimizer
│   │   ├── validator.py               # Conflict matrix audit & rejection logic
│   │   └── pipeline.py                # Coordinated optimization & comparison pipeline
│   ├── services/
│   │   └── simulation_manager.py      # Simulation session state manager
│   ├── simulation/
│   │   ├── demand_generator.py        # Seeded Poisson vehicle demand generator
│   │   ├── engine.py                  # Authoritative simulation loop & metrics
│   │   ├── network.py                 # Multi-intersection topologies & corridor links
│   │   ├── traffic_light.py           # Signal controller & conflict matrix enforcement
│   │   ├── traci_connector.py         # SUMO TraCI bridge adapter with auto-fallback
│   │   └── vehicle.py                 # IDM car-following kinematics & queue tracking
│   ├── config.py                      # Environment settings (Pydantic BaseSettings)
│   └── main.py                        # FastAPI application entry point
├── tests/
│   ├── test_simulation.py             # Vehicle kinematics, IDM, demand reproducibility
│   ├── test_safety.py                 # Clearance intervals & conflict matrix auditing
│   ├── test_optimization.py           # QUBO, QAOA, OR-Tools, and candidate rejection
│   └── test_api.py                    # FastAPI TestClient endpoint integration tests
├── requirements.txt                   # Production & dev dependencies
├── .env.example                       # Configuration template without secrets
└── README.md                          # Internal developer documentation
```

---

## 3. Mathematical Formulation (QUBO)

For a set of intersections $i \in \mathcal{I}$, discrete time steps $t \in \{0, \dots, T-1\}$, and phase indices $p \in \{0, 1\}$ (where $p=0$ represents North-South and $p=1$ represents East-West):

$$\min \quad \mathcal{H}(x) = \sum_{i, t} \left[ \mathcal{C}_{\text{wait}}(x_{i, p, t}) + \mathcal{C}_{\text{queue}}(x_{i, p, t}) - \mathcal{R}_{\text{thru}}(x_{i, p, t}) \right] + \mathcal{P}_{\text{safe}} + \mathcal{P}_{\text{switch}} + \mathcal{R}_{\text{coord}}$$

1. **Waiting Time & Queue Pressure**:
   $$\mathcal{C}_{\text{wait}} + \mathcal{C}_{\text{queue}} = (w_{\text{wait}} + w_{\text{queue}}) \cdot \left[ Q_{\text{EW}}(t) x_{i, 0, t} + Q_{\text{NS}}(t) x_{i, 1, t} \right]$$
2. **Discharge Throughput**:
   $$\mathcal{R}_{\text{thru}} = w_{\text{thru}} \cdot \left[ \min(Q_{\text{NS}}, S) x_{i, 0, t} + \min(Q_{\text{EW}}, S) x_{i, 1, t} \right]$$
3. **Signal Switching Penalty**:
   $$\mathcal{P}_{\text{switch}} = w_{\text{switch}} \cdot \sum_{t} \left[ x_{i, 0, t} x_{i, 1, t+1} + x_{i, 1, t} x_{i, 0, t+1} \right]$$
4. **Corridor Green-Wave Coordination**:
   For neighboring intersections $i_1, i_2$ separated by travel delay $\tau$:
   $$\mathcal{R}_{\text{coord}} = - w_{\text{coord}} \cdot \sum_{t} x_{i_1, 1, t} \cdot x_{i_2, 1, t+\tau}$$
5. **Safety Constraints (Conflict Matrix Penalty)**:
   $$\mathcal{P}_{\text{safe}} = P \cdot (x_{i, 0, t} + x_{i, 1, t} - 1)^2$$
   Enforces that conflicting movements never receive green concurrently.

---

## 4. Setup and Installation

### Prerequisites
- Python 3.12+
- `pip`

### Installation
```bash
# In project root:
cd backend
python -m pip install -r requirements.txt
```

### Environment Configuration
```bash
cp .env.example .env
```

---

## 5. Running the Backend Server

```bash
# Launch FastAPI development server on port 8000
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

Interactive developer documentation will be available at:
- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`

---

## 6. Running Internal Automated Tests

```bash
python -m pytest backend/tests -v
```
All tests verify simulation behavior, signal safety, metric calculations, and API integration.
