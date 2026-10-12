/**
 * SmartFlow 3D - Three.js WebGL & 2D Fallback Traffic Simulator
 * Renders an immersive 3D smart-city intersection with buildings, asphalt roads,
 * pedestrian crosswalks, 3D vehicles with headlights/brake lights, and signal gantries.
 */

class SmartFlow3DSimulator {
  constructor(container3D, canvas2D) {
    this.container = container3D;
    this.canvas2D = canvas2D;
    this.ctx2D = canvas2D.getContext('2d');

    this.is3D = true;
    this.state = null;
    this.selectedIntersectionId = 'INT_1';

    // Three.js Objects
    this.scene = null;
    this.camera = null;
    this.renderer = null;
    this.controls = null;
    this.vehiclesMap = new Map(); // id -> THREE.Group
    this.signalsMap = new Map();  // `${intId}_${approach}` -> { redMesh, yelMesh, grnMesh, light }
    this.stopBarsMap = new Map(); // `${intId}_${approach}` -> THREE.Mesh

    // Camera Mode
    this.currentCameraPreset = 'isometric'; // 'isometric', 'aerial', 'street'

    this._initThree();
    this._buildEnvironment();
    this._initResize();
    this._startLoop();
  }

  _initThree() {
    const width = this.container.clientWidth || 800;
    const height = this.container.clientHeight || 560;

    // 1. Scene
    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(0x070b14);
    this.scene.fog = new THREE.FogExp2(0x070b14, 0.0018);

    // 2. Camera
    this.camera = new THREE.PerspectiveCamera(45, width / height, 1, 1500);
    this.camera.position.set(220, 190, 240);

    // 3. Renderer
    this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false, powerPreference: 'high-performance' });
    this.renderer.setSize(width, height);
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 1.1;

    this.container.appendChild(this.renderer.domElement);

    // 4. OrbitControls
    if (window.THREE && window.THREE.OrbitControls) {
      this.controls = new THREE.OrbitControls(this.camera, this.renderer.domElement);
      this.controls.enableDamping = true;
      this.controls.dampingFactor = 0.05;
      this.controls.maxPolarAngle = Math.PI / 2 - 0.04; // Don't go below ground
      this.controls.minDistance = 20;
      this.controls.maxDistance = 650;
      this.controls.target.set(0, 0, 0);
    }

    // 5. Lighting
    const ambient = new THREE.AmbientLight(0x94a3b8, 0.65);
    this.scene.add(ambient);

    const sun = new THREE.DirectionalLight(0xe0f2fe, 1.25);
    sun.position.set(160, 260, 140);
    sun.castShadow = true;
    sun.shadow.mapSize.width = 2048;
    sun.shadow.mapSize.height = 2048;
    sun.shadow.camera.near = 10;
    sun.shadow.camera.far = 700;
    const d = 260;
    sun.shadow.camera.left = -d;
    sun.shadow.camera.right = d;
    sun.shadow.camera.top = d;
    sun.shadow.camera.bottom = -d;
    sun.shadow.bias = -0.0005;
    this.scene.add(sun);

    // Cyan Atmospheric Fill
    const fillLight = new THREE.DirectionalLight(0x06b6d4, 0.4);
    fillLight.position.set(-150, 100, -150);
    this.scene.add(fillLight);
  }

  _buildEnvironment() {
    // Ground Terrain
    const groundGeo = new THREE.PlaneGeometry(1200, 1200);
    const groundMat = new THREE.MeshStandardMaterial({ color: 0x090e1a, roughness: 0.95, metalness: 0.1 });
    const ground = new THREE.Mesh(groundGeo, groundMat);
    ground.rotation.x = -Math.PI / 2;
    ground.receiveShadow = true;
    this.scene.add(ground);

    // Road Grid Mesh (Asphalt)
    this._createRoadways();

    // City Architecture (Surrounding Skyscrapers & Buildings)
    this._createCitySkyline();
  }

  _createRoadways() {
    // Intersections at (-100, 0) and (+100, 0)
    const intersectionsX = [-100, 100];
    const roadWidth = 28;
    const roadLength = 480;

    const asphaltMat = new THREE.MeshStandardMaterial({ color: 0x172033, roughness: 0.85, metalness: 0.15 });
    const sidewalkMat = new THREE.MeshStandardMaterial({ color: 0x24324d, roughness: 0.7 });
    const markingWhite = new THREE.MeshBasicMaterial({ color: 0xffffff });
    const markingYellow = new THREE.MeshBasicMaterial({ color: 0xf59e0b });

    // East-West Arterial Road Corridor
    const ewRoad = new THREE.Mesh(new THREE.BoxGeometry(roadLength, 0.4, roadWidth), asphaltMat);
    ewRoad.position.set(0, 0.2, 0);
    ewRoad.receiveShadow = true;
    this.scene.add(ewRoad);

    // Sidewalks for East-West Road
    const ewSidewalkN = new THREE.Mesh(new THREE.BoxGeometry(roadLength, 0.7, 5), sidewalkMat);
    ewSidewalkN.position.set(0, 0.35, roadWidth / 2 + 2.5);
    ewSidewalkN.receiveShadow = true;
    this.scene.add(ewSidewalkN);

    const ewSidewalkS = new THREE.Mesh(new THREE.BoxGeometry(roadLength, 0.7, 5), sidewalkMat);
    ewSidewalkS.position.set(0, 0.35, -roadWidth / 2 - 2.5);
    ewSidewalkS.receiveShadow = true;
    this.scene.add(ewSidewalkS);

    // Centerline Divider (Yellow)
    for (let x = -roadLength / 2 + 10; x < roadLength / 2 - 10; x += 18) {
      if (Math.abs(x - -100) < 20 || Math.abs(x - 100) < 20) continue; // Skip junction centers
      const dash = new THREE.Mesh(new THREE.BoxGeometry(9, 0.45, 0.5), markingYellow);
      dash.position.set(x, 0.25, 0);
      this.scene.add(dash);
    }

    // North-South Arterial Roads for each intersection
    intersectionsX.forEach((ix) => {
      const nsRoad = new THREE.Mesh(new THREE.BoxGeometry(roadWidth, 0.4, 320), asphaltMat);
      nsRoad.position.set(ix, 0.2, 0);
      nsRoad.receiveShadow = true;
      this.scene.add(nsRoad);

      // Sidewalks
      const nsSwE = new THREE.Mesh(new THREE.BoxGeometry(5, 0.7, 320), sidewalkMat);
      nsSwE.position.set(ix + roadWidth / 2 + 2.5, 0.35, 0);
      this.scene.add(nsSwE);

      const nsSwW = new THREE.Mesh(new THREE.BoxGeometry(5, 0.7, 320), sidewalkMat);
      nsSwW.position.set(ix - roadWidth / 2 - 2.5, 0.35, 0);
      this.scene.add(nsSwW);

      // Pedestrian Zebra Crossings
      this._createCrosswalks(ix, roadWidth);

      // Stop Bars
      this._createStopBars(ix, roadWidth);

      // Traffic Signal Poles & Gantries
      this._createSignalPosts(ix, roadWidth);
    });
  }

  _createCrosswalks(cx, rw) {
    const zebraMat = new THREE.MeshBasicMaterial({ color: 0xe2e8f0 });
    const offsets = [
      { x: cx, z: rw / 2 + 5, isHoriz: true },
      { x: cx, z: -rw / 2 - 5, isHoriz: true },
      { x: cx - rw / 2 - 5, z: 0, isHoriz: false },
      { x: cx + rw / 2 + 5, z: 0, isHoriz: false },
    ];

    offsets.forEach((o) => {
      for (let i = -rw / 2 + 2; i <= rw / 2 - 2; i += 4) {
        const stripe = new THREE.Mesh(
          o.isHoriz ? new THREE.BoxGeometry(1.6, 0.45, 4.5) : new THREE.BoxGeometry(4.5, 0.45, 1.6),
          zebraMat
        );
        stripe.position.set(o.isHoriz ? o.x + i : o.x, 0.26, o.isHoriz ? o.z : o.z + i);
        this.scene.add(stripe);
      }
    });
  }

  _createStopBars(cx, rw) {
    const intId = cx < 0 ? 'INT_1' : 'INT_2';
    const makeStopMesh = (w, h, d, x, y, z, app) => {
      const mat = new THREE.MeshStandardMaterial({
        color: 0xef4444,
        emissive: 0xef4444,
        emissiveIntensity: 1.6,
        roughness: 0.3,
      });
      const mesh = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), mat);
      mesh.position.set(x, y, z);
      this.scene.add(mesh);
      this.stopBarsMap.set(`${intId}_${app}`, mesh);
      return mesh;
    };

    // North stop bar (for SB approaching from North +Z heading South -Z)
    makeStopMesh(rw / 2, 0.45, 1.5, cx - rw / 4, 0.28, rw / 2 + 10, 'SB');

    // South stop bar (for NB approaching from South -Z heading North +Z)
    makeStopMesh(rw / 2, 0.45, 1.5, cx + rw / 4, 0.28, -rw / 2 - 10, 'NB');

    // West stop bar (for EB approaching from West -X heading East +X)
    makeStopMesh(1.5, 0.45, rw / 2, cx - rw / 2 - 10, 0.28, rw / 4, 'EB');

    // East stop bar (for WB approaching from East +X heading West -X)
    makeStopMesh(1.5, 0.45, rw / 2, cx + rw / 2 + 10, 0.28, -rw / 4, 'WB');
  }

  _createSignalPosts(cx, rw) {
    const intId = cx < 0 ? 'INT_1' : 'INT_2';
    const metalMat = new THREE.MeshStandardMaterial({ color: 0x475569, metalness: 0.8, roughness: 0.3 });
    const headHousingMat = new THREE.MeshStandardMaterial({ color: 0x0f172a, roughness: 0.5 });

    const approaches = [
      { app: 'NB', px: cx + rw / 2 + 4, pz: -rw / 2 - 10, rotY: Math.PI },
      { app: 'SB', px: cx - rw / 2 - 4, pz: rw / 2 + 10, rotY: 0 },
      { app: 'EB', px: cx - rw / 2 - 10, pz: rw / 2 + 4, rotY: -Math.PI / 2 },
      { app: 'WB', px: cx + rw / 2 + 10, pz: -rw / 2 - 4, rotY: Math.PI / 2 },
    ];

    approaches.forEach((a) => {
      const gantryGroup = new THREE.Group();
      gantryGroup.position.set(a.px, 0, a.pz);
      gantryGroup.rotation.y = a.rotY;

      // Vertical Pole (at local 0, 11, 0)
      const pole = new THREE.Mesh(new THREE.CylinderGeometry(0.5, 0.6, 22, 12), metalMat);
      pole.position.y = 11;
      pole.castShadow = true;
      gantryGroup.add(pole);

      // Horizontal Mast Arm extending over lanes in local +X direction
      const mast = new THREE.Mesh(new THREE.CylinderGeometry(0.35, 0.35, 12, 12), metalMat);
      mast.rotation.z = Math.PI / 2;
      mast.position.set(5.5, 20, 0);
      gantryGroup.add(mast);

      // Signal Head Housing (stacked vertically)
      const housing = new THREE.Mesh(new THREE.BoxGeometry(2.4, 6.2, 2.2), headHousingMat);
      housing.position.set(8.5, 19, 0);
      housing.castShadow = true;
      gantryGroup.add(housing);

      // 3 Stacked Signal Lenses: Red (top), Yellow (mid), Green (bot)
      const lampGeo = new THREE.SphereGeometry(0.72, 16, 16);

      // Red Lamp (top: y = 20.6)
      const redMat = new THREE.MeshStandardMaterial({
        color: 0xef4444,
        emissive: 0xef4444,
        emissiveIntensity: 3.0,
        roughness: 0.2,
      });
      const redMesh = new THREE.Mesh(lampGeo, redMat);
      redMesh.position.set(8.5, 20.6, 1.15);
      gantryGroup.add(redMesh);

      // Rear Red Lamp (for viewing from behind)
      const redRear = new THREE.Mesh(lampGeo, redMat);
      redRear.position.set(8.5, 20.6, -1.15);
      gantryGroup.add(redRear);

      // Yellow Lamp (middle: y = 19.0)
      const yelMat = new THREE.MeshStandardMaterial({
        color: 0x332200,
        emissive: 0x000000,
        emissiveIntensity: 0.0,
        roughness: 0.4,
      });
      const yelMesh = new THREE.Mesh(lampGeo, yelMat);
      yelMesh.position.set(8.5, 19.0, 1.15);
      gantryGroup.add(yelMesh);

      const yelRear = new THREE.Mesh(lampGeo, yelMat);
      yelRear.position.set(8.5, 19.0, -1.15);
      gantryGroup.add(yelRear);

      // Green Lamp (bottom: y = 17.4)
      const grnMat = new THREE.MeshStandardMaterial({
        color: 0x003300,
        emissive: 0x000000,
        emissiveIntensity: 0.0,
        roughness: 0.4,
      });
      const grnMesh = new THREE.Mesh(lampGeo, grnMat);
      grnMesh.position.set(8.5, 17.4, 1.15);
      gantryGroup.add(grnMesh);

      const grnRear = new THREE.Mesh(lampGeo, grnMat);
      grnRear.position.set(8.5, 17.4, -1.15);
      gantryGroup.add(grnRear);

      // Glowing PointLight
      const ptLight = new THREE.PointLight(0xef4444, 2.5, 36);
      ptLight.position.set(8.5, 19.0, 1.6);
      gantryGroup.add(ptLight);

      this.scene.add(gantryGroup);
      this.signalsMap.set(`${intId}_${a.app}`, {
        redMesh,
        redRear,
        yelMesh,
        yelRear,
        grnMesh,
        grnRear,
        light: ptLight,
      });
    });
  }

  _createCitySkyline() {
    // Generate surrounding smart-city architecture
    const buildingMatDark = new THREE.MeshStandardMaterial({ color: 0x111c30, roughness: 0.5, metalness: 0.7 });
    const buildingMatGlass = new THREE.MeshStandardMaterial({ color: 0x1e3a5f, roughness: 0.2, metalness: 0.9 });
    const roofMat = new THREE.MeshStandardMaterial({ color: 0x09101d, roughness: 0.9 });

    const blocks = [
      // North-West
      { x: -180, z: -100, w: 70, d: 70, h: 140 },
      { x: -180, z: -190, w: 60, d: 60, h: 95 },
      // North-Center
      { x: 0, z: -110, w: 90, d: 55, h: 120 },
      { x: 0, z: -190, w: 80, d: 65, h: 165 },
      // North-East
      { x: 180, z: -100, w: 65, d: 70, h: 130 },
      { x: 180, z: -190, w: 70, d: 60, h: 100 },
      // South-West
      { x: -180, z: 100, w: 65, d: 65, h: 110 },
      { x: -180, z: 190, w: 75, d: 70, h: 150 },
      // South-Center
      { x: 0, z: 110, w: 85, d: 60, h: 105 },
      { x: 0, z: 190, w: 75, d: 65, h: 140 },
      // South-East
      { x: 180, z: 100, w: 70, d: 65, h: 125 },
      { x: 180, z: 190, w: 60, d: 60, h: 90 },
    ];

    blocks.forEach((b) => {
      const bMesh = new THREE.Mesh(
        new THREE.BoxGeometry(b.w, b.h, b.d),
        Math.random() > 0.4 ? buildingMatDark : buildingMatGlass
      );
      bMesh.position.set(b.x, b.h / 2, b.z);
      bMesh.castShadow = true;
      bMesh.receiveShadow = true;
      this.scene.add(bMesh);

      // Roof Border
      const roof = new THREE.Mesh(new THREE.BoxGeometry(b.w - 4, 2, b.d - 4), roofMat);
      roof.position.set(b.x, b.h + 1, b.z);
      this.scene.add(roof);
    });
  }

  // Camera Presets
  setCameraPreset(preset) {
    this.currentCameraPreset = preset;
    if (!this.camera || !this.controls) return;

    if (preset === 'isometric') {
      this._tweenCamera(new THREE.Vector3(220, 190, 240), new THREE.Vector3(0, 0, 0));
    } else if (preset === 'aerial') {
      this._tweenCamera(new THREE.Vector3(0, 380, 1), new THREE.Vector3(0, 0, 0));
    } else if (preset === 'street') {
      this._tweenCamera(new THREE.Vector3(-90, 12, 45), new THREE.Vector3(-100, 4, 0));
    }
  }

  focusIntersection(intId) {
    this.selectedIntersectionId = intId;
    const targetX = intId === 'INT_1' ? -100 : 100;
    this._tweenCamera(new THREE.Vector3(targetX + 90, 85, 95), new THREE.Vector3(targetX, 0, 0));
  }

  _tweenCamera(targetPos, targetLookAt) {
    // Smooth step transition
    const startPos = this.camera.position.clone();
    const startLook = this.controls.target.clone();
    let progress = 0;

    const anim = () => {
      progress += 0.045;
      if (progress <= 1) {
        this.camera.position.lerpVectors(startPos, targetPos, progress);
        this.controls.target.lerpVectors(startLook, targetLookAt, progress);
        requestAnimationFrame(anim);
      } else {
        this.camera.position.copy(targetPos);
        this.controls.target.copy(targetLookAt);
      }
    };
    anim();
  }

  toggle2DView(enable2D) {
    this.is3D = !enable2D;
    if (this.is3D) {
      this.container.style.display = 'block';
      this.canvas2D.style.display = 'none';
      this._resize();
    } else {
      this.container.style.display = 'none';
      this.canvas2D.style.display = 'block';
      this._resize2D();
    }
  }

  updateState(state) {
    this.state = state;
    if (!state) return;

    // 1. Update Traffic Lights & Road Stop Bars
    if (state.intersections) {
      state.intersections.forEach((inter) => {
        const signals = inter.signal.approach_signals || {};
        ['NB', 'SB', 'EB', 'WB'].forEach((app) => {
          const sigItem = this.signalsMap.get(`${inter.id}_${app}`);
          const stopBar = this.stopBarsMap.get(`${inter.id}_${app}`);
          const col = signals[app] || 'RED';

          if (sigItem) {
            if (col === 'RED') {
              sigItem.redMesh.material.color.setHex(0xef4444);
              sigItem.redMesh.material.emissive.setHex(0xef4444);
              sigItem.redMesh.material.emissiveIntensity = 3.2;

              sigItem.yelMesh.material.color.setHex(0x332200);
              sigItem.yelMesh.material.emissive.setHex(0x000000);
              sigItem.yelMesh.material.emissiveIntensity = 0.0;

              sigItem.grnMesh.material.color.setHex(0x003300);
              sigItem.grnMesh.material.emissive.setHex(0x000000);
              sigItem.grnMesh.material.emissiveIntensity = 0.0;

              sigItem.light.color.setHex(0xef4444);
              sigItem.light.intensity = 2.8;
            } else if (col === 'YELLOW') {
              sigItem.redMesh.material.color.setHex(0x330000);
              sigItem.redMesh.material.emissive.setHex(0x000000);
              sigItem.redMesh.material.emissiveIntensity = 0.0;

              sigItem.yelMesh.material.color.setHex(0xf59e0b);
              sigItem.yelMesh.material.emissive.setHex(0xf59e0b);
              sigItem.yelMesh.material.emissiveIntensity = 3.0;

              sigItem.grnMesh.material.color.setHex(0x003300);
              sigItem.grnMesh.material.emissive.setHex(0x000000);
              sigItem.grnMesh.material.emissiveIntensity = 0.0;

              sigItem.light.color.setHex(0xf59e0b);
              sigItem.light.intensity = 2.2;
            } else if (col === 'GREEN') {
              sigItem.redMesh.material.color.setHex(0x330000);
              sigItem.redMesh.material.emissive.setHex(0x000000);
              sigItem.redMesh.material.emissiveIntensity = 0.0;

              sigItem.yelMesh.material.color.setHex(0x332200);
              sigItem.yelMesh.material.emissive.setHex(0x000000);
              sigItem.yelMesh.material.emissiveIntensity = 0.0;

              sigItem.grnMesh.material.color.setHex(0x10b981);
              sigItem.grnMesh.material.emissive.setHex(0x10b981);
              sigItem.grnMesh.material.emissiveIntensity = 3.2;

              sigItem.light.color.setHex(0x10b981);
              sigItem.light.intensity = 2.8;
            }
          }

          if (stopBar) {
            const barHex = col === 'GREEN' ? 0x10b981 : col === 'YELLOW' ? 0xf59e0b : 0xef4444;
            stopBar.material.color.setHex(barHex);
            stopBar.material.emissive.setHex(barHex);
            stopBar.material.emissiveIntensity = 1.8;
          }
        });
      });
    }

    // 2. Update Vehicles in 3D
    if (this.is3D && state.vehicles) {
      this._sync3DVehicles(state.vehicles);
    }

    // 3. Render 2D Fallback if active
    if (!this.is3D) {
      this._render2D(state);
    }
  }

  _sync3DVehicles(vehiclesList) {
    const presentIds = new Set();

    vehiclesList.forEach((veh) => {
      presentIds.add(veh.id);
      let vGroup = this.vehiclesMap.get(veh.id);

      if (!vGroup) {
        vGroup = this._createVehicleMesh(veh.vehicle_type);
        this.vehiclesMap.set(veh.id, vGroup);
        this.scene.add(vGroup);
      }

      // Convert simulation meters into 3D world space
      const pos = this._convertVehicleTo3DPos(veh);

      // Physical stopping clamping:
      // If vehicle is stopped or queued, immediately hold position without lerp drift
      if (veh.is_queued || veh.speed_mps < 0.6) {
        vGroup.position.set(pos.x, 0.4, pos.z);
      } else {
        vGroup.position.lerp(new THREE.Vector3(pos.x, 0.4, pos.z), 0.7);
      }
      vGroup.rotation.y = pos.heading;

      // Brake light glow when stopping / queued
      if (vGroup.userData.brakeLights) {
        const isBraking = veh.is_queued || veh.speed_mps < 1.0;
        vGroup.userData.brakeLights.forEach((bl) => {
          bl.material.color.setHex(isBraking ? 0xff0000 : 0x550000);
        });
      }
    });

    // Remove vehicles that cleared network
    this.vehiclesMap.forEach((mesh, id) => {
      if (!presentIds.has(id)) {
        this.scene.remove(mesh);
        this.vehiclesMap.delete(id);
      }
    });
  }

  _createVehicleMesh(type = 'car') {
    const group = new THREE.Group();
    const isBus = type === 'bus';
    const isTruck = type === 'truck';

    const length = isBus ? 20 : isTruck ? 22 : 10;
    const width = isBus ? 5.2 : isTruck ? 5.4 : 4.4;
    const height = isBus ? 6.2 : isTruck ? 7.0 : 3.6;

    // Body Color
    const colors = [0x0284c7, 0x06b6d4, 0x38bdf8, 0x2563eb, 0xe2e8f0];
    const bodyColor = isBus ? 0x059669 : isTruck ? 0xd97706 : colors[Math.floor(Math.random() * colors.length)];

    const bodyMat = new THREE.MeshStandardMaterial({ color: bodyColor, roughness: 0.35, metalness: 0.65 });
    const cabinMat = new THREE.MeshStandardMaterial({ color: 0x0f172a, roughness: 0.1, metalness: 0.9 });
    const wheelMat = new THREE.MeshStandardMaterial({ color: 0x111111, roughness: 0.9 });
    const lightYellow = new THREE.MeshBasicMaterial({ color: 0xfef08a });

    // Chassis Body
    const body = new THREE.Mesh(new THREE.BoxGeometry(width, height * 0.65, length), bodyMat);
    body.position.y = height * 0.45;
    body.castShadow = true;
    body.receiveShadow = true;
    group.add(body);

    // Cabin / Roof
    const cabin = new THREE.Mesh(new THREE.BoxGeometry(width * 0.88, height * 0.5, length * 0.65), cabinMat);
    cabin.position.y = height * 0.85;
    cabin.castShadow = true;
    group.add(cabin);

    // Wheels
    const wGeo = new THREE.CylinderGeometry(1.2, 1.2, 0.8, 12);
    [-length * 0.32, length * 0.32].forEach((wz) => {
      [-width / 2, width / 2].forEach((wx) => {
        const wheel = new THREE.Mesh(wGeo, wheelMat);
        wheel.rotation.z = Math.PI / 2;
        wheel.position.set(wx, 1.2, wz);
        wheel.castShadow = true;
        group.add(wheel);
      });
    });

    // Headlights (Front is +Z)
    [-width * 0.32, width * 0.32].forEach((hx) => {
      const hl = new THREE.Mesh(new THREE.BoxGeometry(0.8, 0.6, 0.3), lightYellow);
      hl.position.set(hx, height * 0.4, length / 2 + 0.1);
      group.add(hl);
    });

    // Brake Lights (Back is -Z)
    const brakeMeshes = [];
    [-width * 0.32, width * 0.32].forEach((bx) => {
      const bl = new THREE.Mesh(new THREE.BoxGeometry(0.8, 0.6, 0.3), new THREE.MeshBasicMaterial({ color: 0x770000 }));
      bl.position.set(bx, height * 0.4, -length / 2 - 0.1);
      group.add(bl);
      brakeMeshes.push(bl);
    });
    group.userData.brakeLights = brakeMeshes;

    return group;
  }

  _convertVehicleTo3DPos(veh) {
    const intCenterX = veh.intersection_id === 'INT_1' ? -100 : 100;
    const dist = veh.position_m;
    const laneOffset = veh.lane_id.endsWith('_1') ? 3.5 : 8.5;

    let x = intCenterX;
    let z = 0;
    let heading = 0;

    // Approach entrance to stop line is 138.0m, stop bar is at 24.0m from intersection center
    // Half-length of car is ~5m, so vehicle center stops at 29.0m from center when front bumper touches line
    if (veh.approach === 'NB') {
      // Approaches from South (-Z), moving North (+Z)
      x = intCenterX + laneOffset;
      z = -167.0 + dist;
      heading = 0;
    } else if (veh.approach === 'SB') {
      // Approaches from North (+Z), moving South (-Z)
      x = intCenterX - laneOffset;
      z = 167.0 - dist;
      heading = Math.PI;
    } else if (veh.approach === 'EB') {
      // Approaches from West (-X), moving East (+X)
      x = intCenterX - 167.0 + dist;
      z = laneOffset;
      heading = Math.PI / 2;
    } else if (veh.approach === 'WB') {
      // Approaches from East (+X), moving West (-X)
      x = intCenterX + 167.0 - dist;
      z = -laneOffset;
      heading = -Math.PI / 2;
    }

    return { x, z, heading };
  }

  _render2D(state) {
    const ctx = this.ctx2D;
    const w = this.canvas2D.width;
    const h = this.canvas2D.height;
    ctx.clearRect(0, 0, w, h);

    // 2D Canvas Fallback View
    ctx.fillStyle = '#090e1a';
    ctx.fillRect(0, 0, w, h);

    // Arterial Roads
    ctx.fillStyle = '#172033';
    ctx.fillRect(0, h / 2 - 24, w, 48); // East-West

    const junctions = [w * 0.35, w * 0.65];
    junctions.forEach((jx) => {
      ctx.fillRect(jx - 24, 0, 48, h); // North-South
    });

    // Dashed lines
    ctx.strokeStyle = '#f59e0b';
    ctx.setLineDash([8, 8]);
    ctx.beginPath();
    ctx.moveTo(0, h / 2); ctx.lineTo(w, h / 2);
    ctx.stroke();

    // Vehicles
    if (state.vehicles) {
      state.vehicles.forEach((veh) => {
        const jx = veh.intersection_id === 'INT_1' ? junctions[0] : junctions[1];
        let vx = jx, vy = h / 2;
        const d = (veh.position_m / 180) * 140;

        if (veh.approach === 'NB') { vx += 6; vy = h / 2 + 140 - d; }
        else if (veh.approach === 'SB') { vx -= 6; vy = h / 2 - 140 + d; }
        else if (veh.approach === 'EB') { vx = jx - 140 + d; vy += 6; }
        else if (veh.approach === 'WB') { vx = jx + 140 - d; vy -= 6; }

        ctx.fillStyle = veh.is_queued ? '#ef4444' : '#38bdf8';
        ctx.fillRect(vx - 4, vy - 4, 8, 8);
      });
    }
  }

  _initResize() {
    window.addEventListener('resize', () => {
      this._resize();
      this._resize2D();
    });
  }

  _resize() {
    if (!this.renderer || !this.camera) return;
    const width = this.container.clientWidth;
    const height = this.container.clientHeight;
    this.camera.aspect = width / height;
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(width, height);
  }

  _resize2D() {
    if (!this.canvas2D) return;
    this.canvas2D.width = this.canvas2D.clientWidth;
    this.canvas2D.height = this.canvas2D.clientHeight;
  }

  _startLoop() {
    const loop = () => {
      requestAnimationFrame(loop);
      if (this.is3D && this.controls) {
        this.controls.update();
        this.renderer.render(this.scene, this.camera);
      }
    };
    loop();
  }
}

window.SmartFlow3DSimulator = SmartFlow3DSimulator;
