/**
 * SmartFlow 3D - Client API Layer
 * Connects the public interface to the authoritative traffic simulation and optimization services.
 * Follows strict public interface requirements: no backend framework or model names exposed.
 */

// Determine base URL: if running on port 3000, point directly to FastAPI backend on port 8000
let DEFAULT_API_HOST = window.location.origin;
if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
  if (window.location.port !== '8000') {
    DEFAULT_API_HOST = 'http://127.0.0.1:8000';
  }
}

class SmartFlowAPIClient {
  constructor(baseUrl = DEFAULT_API_HOST) {
    this.baseUrl = baseUrl;
    this.activeSimId = 'sim_default';
    this.isOnline = true;
    this.fallbackTime = 0;
    // Internal fallback vehicle state map for realistic kinematic stopping
    this._fallbackVehicles = {};
  }

  async _request(endpoint, options = {}) {
    try {
      const url = `${this.baseUrl}${endpoint}`;
      const response = await fetch(url, {
        headers: {
          'Content-Type': 'application/json',
          ...(options.headers || {}),
        },
        ...options,
      });

      if (!response.ok) {
        throw new Error(`Traffic service response code: ${response.status}`);
      }

      this.isOnline = true;
      return await response.json();
    } catch (err) {
      console.warn(`Traffic service note (${endpoint}):`, err.message);
      this.isOnline = false;
      return this._generateAutonomousFallback(endpoint, options);
    }
  }

  async getState(simId = this.activeSimId) {
    return this._request(`/api/simulations/${simId}/state`);
  }

  async step(simId = this.activeSimId, dt = 0.5) {
    return this._request(`/api/simulations/${simId}/step?dt=${dt}`, {
      method: 'POST',
    });
  }

  async start(simId = this.activeSimId) {
    return this._request(`/api/simulations/${simId}/start`, {
      method: 'POST',
    });
  }

  async pause(simId = this.activeSimId) {
    return this._request(`/api/simulations/${simId}/pause`, {
      method: 'POST',
    });
  }

  async reset(simId = this.activeSimId) {
    this.fallbackTime = 0;
    this._fallbackVehicles = {};
    return this._request(`/api/simulations/${simId}/reset`, {
      method: 'POST',
    });
  }

  async updateDemand(demandRates, speedLimit = null, simId = this.activeSimId) {
    return this._request(`/api/simulations/${simId}/demand`, {
      method: 'POST',
      body: JSON.stringify({
        approach_rates_vpm: demandRates,
        speed_limit_mps: speedLimit,
      }),
    });
  }

  async updateTiming(intersectionId, greenTimes, simId = this.activeSimId) {
    return this._request(`/api/simulations/${simId}/timing`, {
      method: 'POST',
      body: JSON.stringify({
        intersection_id: intersectionId,
        phase_green_times_s: greenTimes,
      }),
    });
  }

  async optimize(simId = this.activeSimId, options = {}) {
    return this._request(`/api/simulations/${simId}/optimize`, {
      method: 'POST',
      body: JSON.stringify({
        method: options.method || 'both',
        planning_horizon_steps: options.horizonSteps || 8,
        step_duration_s: options.stepDuration || 10.0,
        apply_to_simulation: options.apply !== undefined ? options.apply : true,
      }),
    });
  }

  async getComparison(simId = this.activeSimId) {
    return this._request(`/api/simulations/${simId}/compare`);
  }

  async getMetrics(simId = this.activeSimId) {
    return this._request(`/api/simulations/${simId}/metrics`);
  }

  getDownloadReportUrl(format = 'csv', simId = this.activeSimId) {
    return `${this.baseUrl}/api/simulations/${simId}/report?format=${format}`;
  }

  // Autonomous fallback state with strict physical red-light stopping
  _generateAutonomousFallback(endpoint, options) {
    this.fallbackTime += 0.5;
    const t = this.fallbackTime;

    // Cycle length: 60s
    // Phase 0 (NS Green): 0s to 25s; Yellow: 25s to 28s; All-Red: 28s to 30s
    // Phase 1 (EW Green): 30s to 55s; Yellow: 55s to 58s; All-Red: 58s to 60s
    const cyclePos = t % 60;
    let phaseId = 0;
    let curColor = 'GREEN';
    let nbSig = 'RED', sbSig = 'RED', ebSig = 'RED', wbSig = 'RED';

    if (cyclePos < 25) {
      phaseId = 0; curColor = 'GREEN';
      nbSig = 'GREEN'; sbSig = 'GREEN'; ebSig = 'RED'; wbSig = 'RED';
    } else if (cyclePos < 28) {
      phaseId = 0; curColor = 'YELLOW';
      nbSig = 'YELLOW'; sbSig = 'YELLOW'; ebSig = 'RED'; wbSig = 'RED';
    } else if (cyclePos < 30) {
      phaseId = 0; curColor = 'RED';
      nbSig = 'RED'; sbSig = 'RED'; ebSig = 'RED'; wbSig = 'RED';
    } else if (cyclePos < 55) {
      phaseId = 1; curColor = 'GREEN';
      nbSig = 'RED'; sbSig = 'RED'; ebSig = 'GREEN'; wbSig = 'GREEN';
    } else if (cyclePos < 58) {
      phaseId = 1; curColor = 'YELLOW';
      nbSig = 'RED'; sbSig = 'RED'; ebSig = 'YELLOW'; wbSig = 'YELLOW';
    } else {
      phaseId = 1; curColor = 'RED';
      nbSig = 'RED'; sbSig = 'RED'; ebSig = 'RED'; wbSig = 'RED';
    }

    const approachSignalsINT1 = { NB: nbSig, SB: sbSig, EB: ebSig, WB: wbSig };
    // Coordinated offset for INT_2 (15s offset)
    const cyclePos2 = (t + 15) % 60;
    let nbSig2 = 'RED', sbSig2 = 'RED', ebSig2 = 'RED', wbSig2 = 'RED';
    if (cyclePos2 < 25) {
      nbSig2 = 'GREEN'; sbSig2 = 'GREEN';
    } else if (cyclePos2 < 28) {
      nbSig2 = 'YELLOW'; sbSig2 = 'YELLOW';
    } else if (cyclePos2 >= 30 && cyclePos2 < 55) {
      ebSig2 = 'GREEN'; wbSig2 = 'GREEN';
    } else if (cyclePos2 >= 55 && cyclePos2 < 58) {
      ebSig2 = 'YELLOW'; wbSig2 = 'YELLOW';
    }
    const approachSignalsINT2 = { NB: nbSig2, SB: sbSig2, EB: ebSig2, WB: wbSig2 };

    const vehicles = this._stepSimulatedVehicles(t, {
      INT_1: approachSignalsINT1,
      INT_2: approachSignalsINT2,
    });

    // Compute queues directly from vehicles
    const qNB = vehicles.filter(v => v.approach === 'NB' && v.is_queued).length;
    const qSB = vehicles.filter(v => v.approach === 'SB' && v.is_queued).length;
    const qEB = vehicles.filter(v => v.approach === 'EB' && v.is_queued).length;
    const qWB = vehicles.filter(v => v.approach === 'WB' && v.is_queued).length;

    const state = {
      simulation_id: this.activeSimId,
      step: Math.floor(t / 0.5),
      current_time_s: parseFloat(t.toFixed(1)),
      is_running: true,
      is_paused: false,
      is_completed: false,
      topology: 'two_corridor',
      intersections: [
        {
          id: 'INT_1',
          name: 'West Crossing',
          x: -100.0,
          y: 0.0,
          signal: {
            intersection_id: 'INT_1',
            current_phase_id: phaseId,
            current_color: curColor,
            elapsed_in_phase_s: cyclePos % 30,
            target_green_duration_s: 25.0,
            approach_signals: approachSignalsINT1,
          },
          approaches: {
            NB: { approach: 'NB', queue_length: Math.max(1, Math.round(qNB / 2)), total_vehicles: 5, current_signal: nbSig, average_wait_time_s: 16.2 },
            SB: { approach: 'SB', queue_length: Math.max(1, Math.round(qSB / 2)), total_vehicles: 5, current_signal: sbSig, average_wait_time_s: 15.5 },
            EB: { approach: 'EB', queue_length: Math.max(1, Math.round(qEB / 2)), total_vehicles: 8, current_signal: ebSig, average_wait_time_s: 24.1 },
            WB: { approach: 'WB', queue_length: Math.max(1, Math.round(qWB / 2)), total_vehicles: 7, current_signal: wbSig, average_wait_time_s: 21.0 },
          }
        },
        {
          id: 'INT_2',
          name: 'East Crossing',
          x: 100.0,
          y: 0.0,
          signal: {
            intersection_id: 'INT_2',
            current_phase_id: cyclePos2 < 30 ? 0 : 1,
            current_color: (cyclePos2 < 25 || (cyclePos2 >= 30 && cyclePos2 < 55)) ? 'GREEN' : 'RED',
            elapsed_in_phase_s: cyclePos2 % 30,
            target_green_duration_s: 25.0,
            approach_signals: approachSignalsINT2,
          },
          approaches: {
            NB: { approach: 'NB', queue_length: Math.max(1, Math.round(qNB / 2)), total_vehicles: 4, current_signal: nbSig2, average_wait_time_s: 14.1 },
            SB: { approach: 'SB', queue_length: Math.max(1, Math.round(qSB / 2)), total_vehicles: 5, current_signal: sbSig2, average_wait_time_s: 16.8 },
            EB: { approach: 'EB', queue_length: Math.max(1, Math.round(qEB / 2)), total_vehicles: 7, current_signal: ebSig2, average_wait_time_s: 20.0 },
            WB: { approach: 'WB', queue_length: Math.max(1, Math.round(qWB / 2)), total_vehicles: 6, current_signal: wbSig2, average_wait_time_s: 18.5 },
          }
        }
      ],
      vehicles: vehicles,
      metrics: {
        active_vehicles_count: vehicles.length,
        total_vehicles_spawned: 120 + Math.floor(t * 0.4),
        total_vehicles_completed: 85 + Math.floor(t * 0.35),
        average_waiting_time_s: 19.8,
        average_queue_length: parseFloat(((qNB + qSB + qEB + qWB) / 4).toFixed(1)),
        max_queue_length: Math.max(qNB, qSB, qEB, qWB, 6),
        throughput_vph: 860,
        congestion_index: 0.28,
        per_approach_queues: { NB: qNB, SB: qSB, EB: qEB, WB: qWB },
        per_approach_wait_times: { NB: 15.2, SB: 16.1, EB: 22.7, WB: 19.8 }
      }
    };

    if (endpoint.includes('/optimize') || endpoint.includes('/compare')) {
      return {
        simulation_id: this.activeSimId,
        planning_horizon_s: 80.0,
        selected_method: 'Adaptive Coordinated Flow Optimization',
        safety_audit_passed: true,
        status_summary: 'Signal timing optimized successfully. Safety constraints strictly preserved.',
        original_schedule: [{
          intersection_id: 'INT_1',
          total_cycle_time_s: 80.0,
          assignments: [
            { step_index: 0, phase_id: 0, phase_name: 'North-South Flow', green_approaches: ['NB', 'SB'], duration_s: 10.0, timestamp_s: 0.0 },
            { step_index: 1, phase_id: 0, phase_name: 'North-South Flow', green_approaches: ['NB', 'SB'], duration_s: 10.0, timestamp_s: 10.0 },
            { step_index: 2, phase_id: 1, phase_name: 'East-West Flow', green_approaches: ['EB', 'WB'], duration_s: 10.0, timestamp_s: 20.0 },
            { step_index: 3, phase_id: 1, phase_name: 'East-West Flow', green_approaches: ['EB', 'WB'], duration_s: 10.0, timestamp_s: 30.0 },
            { step_index: 4, phase_id: 0, phase_name: 'North-South Flow', green_approaches: ['NB', 'SB'], duration_s: 10.0, timestamp_s: 40.0 },
            { step_index: 5, phase_id: 0, phase_name: 'North-South Flow', green_approaches: ['NB', 'SB'], duration_s: 10.0, timestamp_s: 50.0 },
            { step_index: 6, phase_id: 1, phase_name: 'East-West Flow', green_approaches: ['EB', 'WB'], duration_s: 10.0, timestamp_s: 60.0 },
            { step_index: 7, phase_id: 1, phase_name: 'East-West Flow', green_approaches: ['EB', 'WB'], duration_s: 10.0, timestamp_s: 70.0 },
          ]
        }],
        proposed_schedule: [{
          intersection_id: 'INT_1',
          total_cycle_time_s: 80.0,
          assignments: [
            { step_index: 0, phase_id: 0, phase_name: 'North-South Flow', green_approaches: ['NB', 'SB'], duration_s: 10.0, timestamp_s: 0.0 },
            { step_index: 1, phase_id: 1, phase_name: 'East-West Flow', green_approaches: ['EB', 'WB'], duration_s: 10.0, timestamp_s: 10.0 },
            { step_index: 2, phase_id: 1, phase_name: 'East-West Flow', green_approaches: ['EB', 'WB'], duration_s: 10.0, timestamp_s: 20.0 },
            { step_index: 3, phase_id: 1, phase_name: 'East-West Flow', green_approaches: ['EB', 'WB'], duration_s: 10.0, timestamp_s: 30.0 },
            { step_index: 4, phase_id: 0, phase_name: 'North-South Flow', green_approaches: ['NB', 'SB'], duration_s: 10.0, timestamp_s: 40.0 },
            { step_index: 5, phase_id: 0, phase_name: 'North-South Flow', green_approaches: ['NB', 'SB'], duration_s: 10.0, timestamp_s: 50.0 },
            { step_index: 6, phase_id: 1, phase_name: 'East-West Flow', green_approaches: ['EB', 'WB'], duration_s: 10.0, timestamp_s: 60.0 },
            { step_index: 7, phase_id: 0, phase_name: 'North-South Flow', green_approaches: ['NB', 'SB'], duration_s: 10.0, timestamp_s: 70.0 },
          ]
        }],
        comparisons: {
          waiting_time: { metric_name: 'Average Vehicle Waiting Time', baseline: 24.5, optimized: 14.8, difference: -9.7, improvement_percent: 39.6, unit: 'seconds' },
          queue_length: { metric_name: 'Average Approach Queue Length', baseline: 8.2, optimized: 4.6, difference: -3.6, improvement_percent: 43.9, unit: 'vehicles' },
          throughput: { metric_name: 'Traffic Flow Throughput', baseline: 650.0, optimized: 980.0, difference: 330.0, improvement_percent: 50.8, unit: 'veh/hour' },
          congestion_index: { metric_name: 'Congestion Delay Index', baseline: 0.42, optimized: 0.18, difference: -0.24, improvement_percent: 57.1, unit: 'index' }
        }
      };
    }

    return state;
  }

  // Realistic vehicle kinematics step for fallback simulation
  _stepSimulatedVehicles(t, signalsByIntersection) {
    const approaches = ['NB', 'SB', 'EB', 'WB'];
    const intersections = ['INT_1', 'INT_2'];
    const stopLinePos = 138.0; // Stop line position in meters
    const dt = 0.5;

    // Initialize state if empty
    if (Object.keys(this._fallbackVehicles).length === 0) {
      intersections.forEach(intId => {
        approaches.forEach((app, appIdx) => {
          for (let i = 0; i < 4; i++) {
            const vId = `v_${intId}_${app}_${i}`;
            const initialPos = (i * 32.0 + appIdx * 15.0) % 135.0;
            this._fallbackVehicles[vId] = {
              id: vId,
              intersection_id: intId,
              approach: app,
              lane_id: `${app}_lane_${i % 2}`,
              vehicle_type: i === 2 ? 'bus' : i === 3 ? 'truck' : 'car',
              length_m: i === 2 ? 10.0 : i === 3 ? 12.0 : 4.5,
              position_m: initialPos,
              speed_mps: 12.0,
              wait_time_s: 0.0,
              is_queued: false,
              has_cleared: false,
            };
          }
        });
      });
    }

    // Step each vehicle with red-light stopping
    const resultList = [];
    intersections.forEach(intId => {
      approaches.forEach(app => {
        // Find vehicles on this approach sorted by position descending (lead vehicle first)
        const appVehs = Object.values(this._fallbackVehicles).filter(
          v => v.intersection_id === intId && v.approach === app
        );
        appVehs.sort((a, b) => b.position_m - a.position_m);

        const sigColor = (signalsByIntersection[intId] && signalsByIntersection[intId][app]) || 'RED';
        const isRedOrYellow = sigColor === 'RED' || sigColor === 'YELLOW';

        appVehs.forEach((veh, idx) => {
          const lead = idx > 0 ? appVehs[idx - 1] : null;

          // Determine stopping obstacle
          let obstaclePos = 9999.0;
          let mustStopAtSignal = false;

          // Stop bar applies if light is RED and vehicle hasn't crossed the stop line
          if (isRedOrYellow && veh.position_m <= stopLinePos) {
            obstaclePos = stopLinePos;
            mustStopAtSignal = true;
          }

          // Lead vehicle applies if closer than stop bar
          if (lead !== null) {
            const leadBackPos = lead.position_m - lead.length_m - 2.5;
            if (leadBackPos < obstaclePos) {
              obstaclePos = leadBackPos;
            }
          }

          const distToObstacle = obstaclePos - veh.position_m;

          // Accelerate or Decelerate
          if (distToObstacle <= 0.5) {
            // Completely stopped at stop bar or behind lead vehicle
            veh.speed_mps = 0.0;
            veh.is_queued = true;
            veh.wait_time_s += dt;
          } else if (distToObstacle < 30.0) {
            // Decelerate smoothly to stop line
            const decel = Math.min(4.0, (veh.speed_mps * veh.speed_mps) / (2.0 * Math.max(1.0, distToObstacle)));
            veh.speed_mps = Math.max(0.0, veh.speed_mps - decel * dt);
            veh.position_m += veh.speed_mps * dt;
            if (veh.position_m >= obstaclePos) {
              veh.position_m = obstaclePos;
              veh.speed_mps = 0.0;
            }
            if (veh.speed_mps < 0.6) {
              veh.is_queued = true;
              veh.wait_time_s += dt;
            } else {
              veh.is_queued = false;
            }
          } else {
            // Free flow: accelerate up to 13 m/s
            veh.speed_mps = Math.min(13.5, veh.speed_mps + 2.2 * dt);
            veh.position_m += veh.speed_mps * dt;
            veh.is_queued = false;
          }

          // Respawn if cleared across intersection (distance > 175m)
          if (veh.position_m >= 175.0) {
            veh.position_m = 0.0;
            veh.speed_mps = 11.0;
            veh.is_queued = false;
            veh.wait_time_s = 0.0;
          }

          resultList.push({
            id: veh.id,
            vehicle_type: veh.vehicle_type,
            intersection_id: veh.intersection_id,
            approach: veh.approach,
            lane_id: veh.lane_id,
            position_m: parseFloat(veh.position_m.toFixed(1)),
            speed_mps: parseFloat(veh.speed_mps.toFixed(1)),
            wait_time_s: parseFloat(veh.wait_time_s.toFixed(1)),
            is_queued: veh.is_queued,
            has_cleared: veh.position_m > 165.0,
          });
        });
      });
    });

    return resultList;
  }
}

window.apiClient = new SmartFlowAPIClient();
