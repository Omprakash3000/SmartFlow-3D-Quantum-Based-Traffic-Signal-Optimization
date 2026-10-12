/**
 * SmartFlow 3D - High-Fidelity Isometric / 3D Canvas Renderer
 * Renders authoritative traffic networks, lane markings, 3D vehicles,
 * and glowing signal gantries with smooth 60fps animation.
 */

class TrafficRenderer3D {
  constructor(canvas) {
    this.canvas = canvas;
    this.ctx = canvas.getContext('2d');
    
    // Camera / Viewport Transform
    this.zoom = 1.0;
    this.panX = 0;
    this.panY = 0;
    this.isDragging = false;
    this.lastMouseX = 0;
    this.lastMouseY = 0;

    // View Angle: 2.5D Isometric Tilt
    this.angle = Math.PI / 6; // 30 degrees
    this.cosA = Math.cos(this.angle);
    this.sinA = Math.sin(this.angle);

    // Latest State Cache
    this.currentState = null;
    this.animFrameId = null;

    this._initEvents();
    this._resize();
    window.addEventListener('resize', () => this._resize());
  }

  _initEvents() {
    this.canvas.addEventListener('mousedown', (e) => {
      this.isDragging = true;
      this.lastMouseX = e.clientX;
      this.lastMouseY = e.clientY;
    });

    window.addEventListener('mousemove', (e) => {
      if (!this.isDragging) return;
      const dx = e.clientX - this.lastMouseX;
      const dy = e.clientY - this.lastMouseY;
      this.panX += dx;
      this.panY += dy;
      this.lastMouseX = e.clientX;
      this.lastMouseY = e.clientY;
    });

    window.addEventListener('mouseup', () => {
      this.isDragging = false;
    });

    this.canvas.addEventListener('wheel', (e) => {
      e.preventDefault();
      const zoomFactor = e.deltaY < 0 ? 1.08 : 0.92;
      this.zoom = Math.max(0.4, Math.min(2.5, this.zoom * zoomFactor));
    }, { passive: false });
  }

  _resize() {
    const rect = this.canvas.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    this.canvas.width = rect.width * dpr;
    this.canvas.height = rect.height * dpr;
    this.ctx.scale(dpr, dpr);
    this.width = rect.width;
    this.height = rect.height;
  }

  // Projects World (x, y, z) into 2.5D Isometric Screen Coordinates
  toScreen(wx, wy, wz = 0) {
    const centerX = this.width / 2 + this.panX;
    const centerY = this.height / 2 + this.panY + 40;

    // Isometric projection
    const isoX = (wx - wy) * this.cosA * this.zoom;
    const isoY = ((wx + wy) * this.sinA - wz) * this.zoom;

    return {
      x: centerX + isoX,
      y: centerY + isoY,
    };
  }

  updateState(state) {
    this.currentState = state;
  }

  render() {
    const ctx = this.ctx;
    ctx.clearRect(0, 0, this.width, this.height);

    // Background Grid / Terrain
    this._drawTerrainGrid(ctx);

    if (!this.currentState || !this.currentState.intersections) {
      this._drawLoadingHint(ctx);
      return;
    }

    const intersections = this.currentState.intersections;
    const vehicles = this.currentState.vehicles || [];

    // 1. Draw Roadways & Intersections
    intersections.forEach((inter) => {
      this._drawIntersectionRoads(ctx, inter);
    });

    // 2. Draw Arterial Corridor Links between intersections if multiple
    if (intersections.length >= 2) {
      this._drawCorridorLink(ctx, intersections[0], intersections[1]);
    }

    // 3. Draw Traffic Signal Gantries
    intersections.forEach((inter) => {
      this._drawTrafficSignals(ctx, inter);
    });

    // 4. Draw Vehicles with 3D models & lighting
    this._drawVehicles(ctx, vehicles, intersections);

    // 5. Draw Approach Queue Overlays
    intersections.forEach((inter) => {
      this._drawApproachHUD(ctx, inter);
    });
  }

  _drawTerrainGrid(ctx) {
    ctx.save();
    ctx.strokeStyle = 'rgba(56, 189, 248, 0.04)';
    ctx.lineWidth = 1;

    const gridSize = 40;
    const extent = 360;

    for (let x = -extent; x <= extent; x += gridSize) {
      const p1 = this.toScreen(x, -extent);
      const p2 = this.toScreen(x, extent);
      ctx.beginPath();
      ctx.moveTo(p1.x, p1.y);
      ctx.lineTo(p2.x, p2.y);
      ctx.stroke();
    }

    for (let y = -extent; y <= extent; y += gridSize) {
      const p1 = this.toScreen(-extent, y);
      const p2 = this.toScreen(extent, y);
      ctx.beginPath();
      ctx.moveTo(p1.x, p1.y);
      ctx.lineTo(p2.x, p2.y);
      ctx.stroke();
    }
    ctx.restore();
  }

  _drawIntersectionRoads(ctx, inter) {
    const cx = inter.x;
    const cy = inter.y;
    const roadWidth = 24; // 2 lanes each way
    const approachLen = 140;

    ctx.save();
    // Road Asphalt Base
    ctx.fillStyle = '#1e293b';
    ctx.strokeStyle = 'rgba(148, 163, 184, 0.2)';
    ctx.lineWidth = 1.5;

    // North-South Arterial
    const ns_tl = this.toScreen(cx - roadWidth, cy - approachLen);
    const ns_tr = this.toScreen(cx + roadWidth, cy - approachLen);
    const ns_br = this.toScreen(cx + roadWidth, cy + approachLen);
    const ns_bl = this.toScreen(cx - roadWidth, cy + approachLen);

    ctx.beginPath();
    ctx.moveTo(ns_tl.x, ns_tl.y);
    ctx.lineTo(ns_tr.x, ns_tr.y);
    ctx.lineTo(ns_br.x, ns_br.y);
    ctx.lineTo(ns_bl.x, ns_bl.y);
    ctx.closePath();
    ctx.fill();
    ctx.stroke();

    // East-West Arterial
    const ew_tl = this.toScreen(cx - approachLen, cy - roadWidth);
    const ew_tr = this.toScreen(cx + approachLen, cy - roadWidth);
    const ew_br = this.toScreen(cx + approachLen, cy + roadWidth);
    const ew_bl = this.toScreen(cx - approachLen, cy + roadWidth);

    ctx.beginPath();
    ctx.moveTo(ew_tl.x, ew_tl.y);
    ctx.lineTo(ew_tr.x, ew_tr.y);
    ctx.lineTo(ew_br.x, ew_br.y);
    ctx.lineTo(ew_bl.x, ew_bl.y);
    ctx.closePath();
    ctx.fill();
    ctx.stroke();

    // Central Junction Box
    const j_tl = this.toScreen(cx - roadWidth, cy - roadWidth);
    const j_tr = this.toScreen(cx + roadWidth, cy - roadWidth);
    const j_br = this.toScreen(cx + roadWidth, cy + roadWidth);
    const j_bl = this.toScreen(cx - roadWidth, cy + roadWidth);

    ctx.fillStyle = '#0f172a';
    ctx.beginPath();
    ctx.moveTo(j_tl.x, j_tl.y);
    ctx.lineTo(j_tr.x, j_tr.y);
    ctx.lineTo(j_br.x, j_br.y);
    ctx.lineTo(j_bl.x, j_bl.y);
    ctx.closePath();
    ctx.fill();

    // Dashed centerlines
    ctx.strokeStyle = '#e2e8f0';
    ctx.setLineDash([8, 8]);
    ctx.lineWidth = 1.2;

    // NS centerline
    const c_n1 = this.toScreen(cx, cy - approachLen);
    const c_n2 = this.toScreen(cx, cy - roadWidth);
    ctx.beginPath(); ctx.moveTo(c_n1.x, c_n1.y); ctx.lineTo(c_n2.x, c_n2.y); ctx.stroke();

    const c_s1 = this.toScreen(cx, cy + roadWidth);
    const c_s2 = this.toScreen(cx, cy + approachLen);
    ctx.beginPath(); ctx.moveTo(c_s1.x, c_s1.y); ctx.lineTo(c_s2.x, c_s2.y); ctx.stroke();

    // EW centerline
    const c_w1 = this.toScreen(cx - approachLen, cy);
    const c_w2 = this.toScreen(cx - roadWidth, cy);
    ctx.beginPath(); ctx.moveTo(c_w1.x, c_w1.y); ctx.lineTo(c_w2.x, c_w2.y); ctx.stroke();

    const c_e1 = this.toScreen(cx + roadWidth, cy);
    const c_e2 = this.toScreen(cx + approachLen, cy);
    ctx.beginPath(); ctx.moveTo(c_e1.x, c_e1.y); ctx.lineTo(c_e2.x, c_e2.y); ctx.stroke();

    // Stop Bars (Solid White)
    ctx.setLineDash([]);
    ctx.lineWidth = 3;
    ctx.strokeStyle = '#ffffff';

    // North Stop bar (approaching Southbound)
    const sb_stop1 = this.toScreen(cx - roadWidth, cy - roadWidth);
    const sb_stop2 = this.toScreen(cx, cy - roadWidth);
    ctx.beginPath(); ctx.moveTo(sb_stop1.x, sb_stop1.y); ctx.lineTo(sb_stop2.x, sb_stop2.y); ctx.stroke();

    // South Stop bar (approaching Northbound)
    const nb_stop1 = this.toScreen(cx, cy + roadWidth);
    const nb_stop2 = this.toScreen(cx + roadWidth, cy + roadWidth);
    ctx.beginPath(); ctx.moveTo(nb_stop1.x, nb_stop1.y); ctx.lineTo(nb_stop2.x, nb_stop2.y); ctx.stroke();

    // West Stop bar (approaching Eastbound)
    const eb_stop1 = this.toScreen(cx - roadWidth, cy);
    const eb_stop2 = this.toScreen(cx - roadWidth, cy + roadWidth);
    ctx.beginPath(); ctx.moveTo(eb_stop1.x, eb_stop1.y); ctx.lineTo(eb_stop2.x, eb_stop2.y); ctx.stroke();

    // East Stop bar (approaching Westbound)
    const wb_stop1 = this.toScreen(cx + roadWidth, cy - roadWidth);
    const wb_stop2 = this.toScreen(cx + roadWidth, cy);
    ctx.beginPath(); ctx.moveTo(wb_stop1.x, wb_stop1.y); ctx.lineTo(wb_stop2.x, wb_stop2.y); ctx.stroke();

    ctx.restore();
  }

  _drawCorridorLink(ctx, inter1, inter2) {
    const roadWidth = 24;
    ctx.save();
    ctx.fillStyle = '#1e293b';
    ctx.strokeStyle = 'rgba(148, 163, 184, 0.2)';
    ctx.lineWidth = 1.5;

    const p_tl = this.toScreen(inter1.x, inter1.y - roadWidth);
    const p_tr = this.toScreen(inter2.x, inter2.y - roadWidth);
    const p_br = this.toScreen(inter2.x, inter2.y + roadWidth);
    const p_bl = this.toScreen(inter1.x, inter1.y + roadWidth);

    ctx.beginPath();
    ctx.moveTo(p_tl.x, p_tl.y);
    ctx.lineTo(p_tr.x, p_tr.y);
    ctx.lineTo(p_br.x, p_br.y);
    ctx.lineTo(p_bl.x, p_bl.y);
    ctx.closePath();
    ctx.fill();
    ctx.stroke();

    // Dashed connecting centerline
    ctx.strokeStyle = '#e2e8f0';
    ctx.setLineDash([8, 8]);
    ctx.lineWidth = 1.2;
    const c1 = this.toScreen(inter1.x, inter1.y);
    const c2 = this.toScreen(inter2.x, inter2.y);
    ctx.beginPath();
    ctx.moveTo(c1.x, c1.y);
    ctx.lineTo(c2.x, c2.y);
    ctx.stroke();

    ctx.restore();
  }

  _drawTrafficSignals(ctx, inter) {
    const cx = inter.x;
    const cy = inter.y;
    const roadWidth = 24;
    const signals = inter.signal.approach_signals || {};

    const posts = [
      { approach: 'NB', x: cx + roadWidth + 4, y: cy + roadWidth + 4 },
      { approach: 'SB', x: cx - roadWidth - 4, y: cy - roadWidth - 4 },
      { approach: 'EB', x: cx - roadWidth - 4, y: cy + roadWidth + 4 },
      { approach: 'WB', x: cx + roadWidth + 4, y: cy - roadWidth - 4 },
    ];

    posts.forEach((post) => {
      const color = signals[post.approach] || 'RED';
      const basePos = this.toScreen(post.x, post.y, 0);
      const topPos = this.toScreen(post.x, post.y, 25);

      ctx.save();
      // Pole
      ctx.strokeStyle = '#64748b';
      ctx.lineWidth = 2.5;
      ctx.beginPath();
      ctx.moveTo(basePos.x, basePos.y);
      ctx.lineTo(topPos.x, topPos.y);
      ctx.stroke();

      // Signal Head Housing
      ctx.fillStyle = '#0f172a';
      ctx.strokeStyle = '#334155';
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.arc(topPos.x, topPos.y, 6.5 * this.zoom, 0, Math.PI * 2);
      ctx.fill();
      ctx.stroke();

      // Glowing Active Lamp
      let glowColor = '#ef4444';
      if (color === 'GREEN') glowColor = '#10b981';
      else if (color === 'YELLOW') glowColor = '#f59e0b';

      ctx.shadowColor = glowColor;
      ctx.shadowBlur = 12;
      ctx.fillStyle = glowColor;
      ctx.beginPath();
      ctx.arc(topPos.x, topPos.y, 4.5 * this.zoom, 0, Math.PI * 2);
      ctx.fill();

      ctx.restore();
    });
  }

  _drawVehicles(ctx, vehicles, intersections) {
    const interMap = {};
    intersections.forEach((i) => (interMap[i.id] = i));

    vehicles.forEach((veh) => {
      const inter = interMap[veh.intersection_id] || intersections[0];
      if (!inter) return;

      // Calculate world coordinates from approach and position_m
      const pos = this._calculateVehicleWorldPos(veh, inter);
      const screenPos = this.toScreen(pos.wx, pos.wy, 4);

      ctx.save();

      // Shadow
      ctx.fillStyle = 'rgba(0, 0, 0, 0.45)';
      ctx.beginPath();
      ctx.ellipse(screenPos.x, screenPos.y + 4 * this.zoom, 8 * this.zoom, 4 * this.zoom, 0, 0, Math.PI * 2);
      ctx.fill();

      // Vehicle Body Dimensions
      const len = (veh.vehicle_type === 'bus' ? 22 : veh.vehicle_type === 'truck' ? 26 : 12) * this.zoom;
      const wid = 6 * this.zoom;

      // Body Palette
      let bodyColor = '#38bdf8'; // Blue car
      if (veh.vehicle_type === 'bus') bodyColor = '#06b6d4';
      else if (veh.vehicle_type === 'truck') bodyColor = '#f59e0b';

      // Queued Indicator
      if (veh.is_queued) {
        bodyColor = '#f43f5e';
      }

      ctx.translate(screenPos.x, screenPos.y);
      ctx.rotate(pos.heading);

      // Chassis
      ctx.fillStyle = bodyColor;
      ctx.fillRect(-len / 2, -wid / 2, len, wid);

      // Roof / Cabin
      ctx.fillStyle = 'rgba(15, 23, 42, 0.7)';
      ctx.fillRect(-len * 0.2, -wid * 0.35, len * 0.5, wid * 0.7);

      // Headlights (Front is +len/2)
      ctx.fillStyle = '#fef08a';
      ctx.shadowColor = '#fef08a';
      ctx.shadowBlur = 6;
      ctx.fillRect(len / 2 - 2, -wid / 2 + 1, 2, 2);
      ctx.fillRect(len / 2 - 2, wid / 2 - 3, 2, 2);

      // Tail / Brake Lights (Back is -len/2)
      ctx.fillStyle = veh.is_queued || veh.speed_mps < 1.0 ? '#ef4444' : '#7f1d1d';
      ctx.shadowColor = '#ef4444';
      ctx.shadowBlur = veh.is_queued ? 10 : 2;
      ctx.fillRect(-len / 2, -wid / 2 + 1, 2, 2);
      ctx.fillRect(-len / 2, wid / 2 - 3, 2, 2);

      ctx.restore();
    });
  }

  _calculateVehicleWorldPos(veh, inter) {
    const cx = inter.x;
    const cy = inter.y;
    const appLen = 140;
    const dist = veh.position_m;
    const laneOffset = veh.lane_id.endsWith('_1') ? 6 : 14;

    let wx = cx;
    let wy = cy;
    let heading = 0;

    if (veh.approach === 'NB') {
      // Moves North (from cy + appLen toward cy)
      wx = cx + laneOffset;
      wy = cy + appLen - dist;
      heading = -Math.PI / 2;
    } else if (veh.approach === 'SB') {
      // Moves South (from cy - appLen toward cy)
      wx = cx - laneOffset;
      wy = cy - appLen + dist;
      heading = Math.PI / 2;
    } else if (veh.approach === 'EB') {
      // Moves East (from cx - appLen toward cx)
      wx = cx - appLen + dist;
      wy = cy + laneOffset;
      heading = 0;
    } else if (veh.approach === 'WB') {
      // Moves West (from cx + appLen toward cx)
      wx = cx + appLen - dist;
      wy = cy - laneOffset;
      heading = Math.PI;
    }

    return { wx, wy, heading };
  }

  _drawApproachHUD(ctx, inter) {
    const approaches = inter.approaches || {};
    const cx = inter.x;
    const cy = inter.y;
    const distBadge = 110;

    const badges = [
      { app: 'NB', x: cx + 20, y: cy + distBadge },
      { app: 'SB', x: cx - 20, y: cy - distBadge },
      { app: 'EB', x: cx - distBadge, y: cy + 20 },
      { app: 'WB', x: cx + distBadge, y: cy - 20 },
    ];

    badges.forEach((b) => {
      const data = approaches[b.app];
      if (!data) return;

      const sp = this.toScreen(b.x, b.y, 10);
      ctx.save();
      ctx.font = '10px "JetBrains Mono", monospace';
      const label = `${b.app}: ${data.queue_length}q`;

      const txtW = ctx.measureText(label).width;
      ctx.fillStyle = 'rgba(15, 23, 42, 0.85)';
      ctx.strokeStyle = data.queue_length > 5 ? '#f43f5e' : 'rgba(56, 189, 248, 0.4)';
      ctx.lineWidth = 1;

      ctx.beginPath();
      ctx.roundRect(sp.x - txtW / 2 - 5, sp.y - 8, txtW + 10, 16, 4);
      ctx.fill();
      ctx.stroke();

      ctx.fillStyle = data.queue_length > 5 ? '#fb7185' : '#e2e8f0';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(label, sp.x, sp.y);
      ctx.restore();
    });
  }

  _drawLoadingHint(ctx) {
    ctx.save();
    ctx.fillStyle = 'rgba(148, 163, 184, 0.7)';
    ctx.font = '14px Outfit, sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText('Synchronizing traffic simulation state...', this.width / 2, this.height / 2);
    ctx.restore();
  }
}

window.TrafficRenderer3D = TrafficRenderer3D;
