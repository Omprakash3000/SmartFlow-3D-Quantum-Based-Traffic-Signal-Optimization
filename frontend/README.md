# SmartFlow 3D — User Interface & Simulation Dashboard

The SmartFlow 3D frontend delivers an interactive, high-fidelity 3D visualization and real-time dashboard for urban traffic monitoring, signal control, and flow optimization.

## Features

- **Authoritative 3D Canvas Viewport**: Renders multi-intersection arterial corridors with realistic car-following motion, lane dividers, stop bars, and glowing signal gantries.
- **Interactive Signal Controls**: Start, pause, step, and reset the simulation; adjust playback speeds; dynamically update traffic arrival demands per approach; and fine-tune green-time splits.
- **Adaptive Flow Optimization**: Triggers optimization for traffic signal schedules, achieving significant reductions in waiting times and approach queue lengths while increasing throughput.
- **Baseline vs. Optimized Scenario Comparison**: Side-by-side comparative metrics and visual schedule progression timelines demonstrating the impact of adaptive signal coordination.
- **Comprehensive Report Exports**: Download empirical performance data in CSV or JSON formats for offline review and audits.
- **Safety & Compliance Verification**: Real-time auditing confirming conflict-free green phases, clearance intervals, and empirical measurement integrity.

## Getting Started

### Prerequisites
- Node.js (v18+) or any static HTTP web server (such as Python's built-in `http.server`).

### Running Locally
```bash
# In the frontend directory:
npm start
```
Or directly through Python:
```bash
python -m http.server 3000
```
Open [http://localhost:3000](http://localhost:3000) in your web browser. When running alongside the backend server on port 8000, the frontend communicates seamlessly via REST APIs.
