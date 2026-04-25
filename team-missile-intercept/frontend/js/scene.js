// Three.js scene setup: camera, lighting, ground grid, base marker.
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';
import { SMAAPass } from 'three/addons/postprocessing/SMAAPass.js';
import { BOREAL_TERRAIN, BOREAL_LOCATIONS } from './terrain_data.js';
import { enhanceTerrainGeometry, scatterTrees, createRoads, createCoastlines, createRadarScanDome } from './scene_visuals.js';

// World units: meters. Arena ~150km. We scale the whole world by 0.001 for
// rendering so Three.js works in km (avoids z-fighting and huge numbers).
export const SCALE = 0.001;

// Arena constants (must stay in sync with backend config.py)
export const ARENA_X = 150_000;
// Live-demo polish (2026-04-24, Bug 9): 250_000 → 350_000 to push the
// ballistic / HGV spawn band 100 km further north, giving PAC-3 more
// intercept runway against Mach-13/17 re-entry weapons. Saab landmass
// still occupies y=0-250 km; the extra 100 km is empty open ocean /
// "deep strategic rear" where strategic launchers sit off-map.
export const ARENA_Y = 350_000;
export const BASE_POS = [75_000, 5_000, 0];

export function createScene(canvas) {
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x1a2a3e);
  scene.fog = new THREE.Fog(0x1a2a3e, 200, 700);

  // Dusk/dawn gradient skydome. A large inverted sphere with a shader
  // that lerps from a dark-blue zenith (high world Y) to a warm amber
  // horizon (Y ≈ 0). Rendered before everything else via renderOrder
  // = -1 and depthWrite: false so fog and geometry still composite on
  // top. Placed inside the fog so distant arena edges continue to
  // fade out; the sky itself is beyond the fog far plane.
  const skyGeom = new THREE.SphereGeometry(1000, 32, 16);
  const skyMat = new THREE.ShaderMaterial({
    side: THREE.BackSide,
    depthWrite: false,
    uniforms: {
      zenithColor: { value: new THREE.Color(0x1a2d48) },
      horizonColor: { value: new THREE.Color(0x4a3828) },
      glowColor: { value: new THREE.Color(0xff9a38) },
    },
    vertexShader: /* glsl */ `
      varying vec3 vWorldPos;
      void main() {
        vec4 wp = modelMatrix * vec4(position, 1.0);
        vWorldPos = wp.xyz;
        gl_Position = projectionMatrix * viewMatrix * wp;
      }
    `,
    fragmentShader: /* glsl */ `
      uniform vec3 zenithColor;
      uniform vec3 horizonColor;
      uniform vec3 glowColor;
      varying vec3 vWorldPos;
      void main() {
        // Normalised height factor: 0 at horizon, 1 at zenith.
        float h = clamp(vWorldPos.y / 600.0, -0.2, 1.0);
        float topMix = smoothstep(0.0, 0.6, h);
        float glow = smoothstep(0.15, -0.05, h);     // brightest at horizon
        vec3 col = mix(horizonColor, zenithColor, topMix);
        col += glowColor * glow * 0.35;
        gl_FragColor = vec4(col, 1.0);
      }
    `,
  });
  const sky = new THREE.Mesh(skyGeom, skyMat);
  sky.renderOrder = -1;
  scene.add(sky);

  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
  renderer.setPixelRatio(window.devicePixelRatio);
  renderer.setSize(window.innerWidth, window.innerHeight);
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.1;

  const camera = new THREE.PerspectiveCamera(
    50,
    window.innerWidth / window.innerHeight,
    0.5,
    2000,
  );
  // W13 Phase 7: named constants let resetCameraView restore demo framing.
  const DEFAULT_CAMERA_POS = [0, 30, 55];
  const DEFAULT_CONTROLS_TARGET = [0, 0, -60];
  camera.position.set(...DEFAULT_CAMERA_POS);
  camera.lookAt(...DEFAULT_CONTROLS_TARGET);

  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.1;
  controls.target.set(...DEFAULT_CONTROLS_TARGET);

  // Post-processing: bloom gives explosions, thrust flames, city lights a
  // cinematic glow — free visual upgrade for the demo presentation.
  const pixelRatio = renderer.getPixelRatio();
  const composer = new EffectComposer(renderer);
  composer.setPixelRatio(pixelRatio);
  composer.setSize(window.innerWidth, window.innerHeight);
  composer.addPass(new RenderPass(scene, camera));
  const bloomPass = new UnrealBloomPass(
    new THREE.Vector2(window.innerWidth, window.innerHeight),
    0.4,   // strength
    0.3,   // radius
    0.6,   // threshold
  );
  composer.addPass(bloomPass);
  // SMAA anti-aliasing — the renderer's native MSAA is bypassed by
  // EffectComposer's framebuffer, so add a post-process AA pass.
  const smaaPass = new SMAAPass(
    window.innerWidth * pixelRatio,
    window.innerHeight * pixelRatio,
  );
  composer.addPass(smaaPass);
  // OutputPass applies tone mapping + sRGB conversion so the final image
  // isn't washed-out/black from the linear intermediate render target.
  composer.addPass(new OutputPass());

  // W13 Phase 7: demo-recovery helper. `R` keybinding + HUD button both
  // call this to snap the camera + OrbitControls target back to the
  // starting pose. Safe to invoke mid-match — OrbitControls picks up
  // the new state on the next `controls.update()` tick.
  function resetCameraView() {
    camera.position.set(...DEFAULT_CAMERA_POS);
    controls.target.set(...DEFAULT_CONTROLS_TARGET);
    controls.update();
  }

  // ── Lighting ─────────────────────────────────────────────────────────────
  // Hemisphere light: sky (blue-grey) from above, ground (warm olive) from
  // below. Fills shadows with soft colour variance instead of pure black.
  const hemi = new THREE.HemisphereLight(0x8aaac8, 0x3a3820, 1.0);
  scene.add(hemi);

  // Primary sun — warm amber, raking from south-east at high angle.
  const sun = new THREE.DirectionalLight(0xffd890, 2.0);
  sun.position.set(60, 90, 50);
  scene.add(sun);

  // Fill light — cool blue from the north/opposite side, moderate power.
  // Adds colour contrast: warm sunlit faces vs. cool shadow faces.
  const fill = new THREE.DirectionalLight(0x6090c8, 0.6);
  fill.position.set(-40, 30, -80);
  scene.add(fill);

  // Rim light — pale warm from below-west, lifts the horizon strip.
  const rim = new THREE.DirectionalLight(0xffa060, 0.35);
  rim.position.set(-80, -10, 20);
  scene.add(rim);

  // Arena is asymmetric (150 km wide × 250 km deep to accommodate HGV
  // spawns 180 km north of the base). Ground plane is a rectangle
  // centred on the arena centre, not the base, so the whole fight area
  // is covered.
  const widthUnits = ARENA_X * SCALE;
  const depthUnits = ARENA_Y * SCALE;
  const arenaCentreZ = -(ARENA_Y / 2 - BASE_POS[1]) * SCALE;
  // Rectangular floor grid matching the ground's 150 × 250 km extent.
  // THREE.GridHelper is square-only, so a max(150, 250) = 250 grid hung
  // 50 km off the east and west edges. makeRectGrid builds a
  // LineSegments grid whose edges line up with the ground rectangle.
  // 1 unit = 1 km; sub-lines every 1 km let the operator eyeball weapon
  // ranges (CIWS 4 km = 4 cells, RBS 70 9, SLS 12, SLM 40, PAC-3 60,
  // PAC-2 70), with brighter main lines every 10 km for coarser reads.
  // Sea plane — brighter ocean blue, no grid overlay.
  const groundGeom = new THREE.PlaneGeometry(widthUnits, depthUnits);
  const groundMat = new THREE.MeshStandardMaterial({
    color: 0x2a7ab8,
    roughness: 0.6,
    metalness: 0.2,
  });
  const ground = new THREE.Mesh(groundGeom, groundMat);
  ground.rotation.x = -Math.PI / 2;
  ground.position.set(0, -0.01, arenaCentreZ);
  scene.add(ground);
  // No-op water update — kept so main.js call site doesn't break.
  const waterUpdate = () => {};

  // Boreal Passage terrain — Saab's hand-authored scenario geometry.
  // Saab coords: X east (0..1667 km), Y SOUTH-positive (0..1300 km).
  // Scene:       X east,              Z = -north (so +Z is south).
  // We crop a 1667 × 800 km window (Y 280..1080) which contains the
  // mainland/strait/mainland band + relevant islands, then stretch
  // that window to fit the 150 × 250 km arena. Non-uniform scale is
  // accepted — the demo jury reads "two lands across a strait", not
  // a 1:1 overlay of the Saab reference.
  const SAAB_X_WINDOW = [0, 1667];
  const SAAB_Y_WINDOW = [280, 1080];
  // Map window → arena. Saab Y is SOUTH-positive: low Y is the north
  // edge of Saab's map, high Y is the south edge. Our scene Z is
  // inverted: -Z is north, +Z is south (base at scene Z=0). So the
  // correct mapping sends y_norm=0 (Saab north, top of the CSV) to
  // scene_z = -245 (scene far-north edge), and y_norm=1 (Saab south)
  // to scene_z = +5 (scene south edge, where the base sits). This is
  // the OPPOSITE direction of the task-spec pseudocode — following the
  // pseudocode literally would put the southern mainland in our scene
  // north and vice versa, contradicting the acceptance criteria.
  const SCENE_X = [-75, 75];
  const SCENE_Z_NORTH = -245;   // scene-north edge (y_norm = 0)
  const SCENE_Z_SOUTH = 5;      // scene-south edge (y_norm = 1)
  function saabToScene(x_km, y_km) {
    const xn = (x_km - SAAB_X_WINDOW[0]) / (SAAB_X_WINDOW[1] - SAAB_X_WINDOW[0]);
    const yn = (y_km - SAAB_Y_WINDOW[0]) / (SAAB_Y_WINDOW[1] - SAAB_Y_WINDOW[0]);
    const sx = SCENE_X[0] + xn * (SCENE_X[1] - SCENE_X[0]);
    const sz = SCENE_Z_NORTH + yn * (SCENE_Z_SOUTH - SCENE_Z_NORTH);
    return [sx, sz];
  }
  const EXTRUDE_DEPTH  = 0.3;       // scene units = 300 m above sea level
  for (const poly of BOREAL_TERRAIN) {
    const shape = new THREE.Shape();
    for (let i = 0; i < poly.coords.length; i++) {
      const [sx, sz] = saabToScene(poly.coords[i][0], poly.coords[i][1]);
      if (i === 0) shape.moveTo(sx, -sz);
      else shape.lineTo(sx, -sz);
    }
    const geom = new THREE.ExtrudeGeometry(shape, {
      depth: EXTRUDE_DEPTH,
      bevelEnabled: false,
    });
    const isIsland = poly.subtype !== 'mainland';
    // Stylized low-poly: vertex noise for faceted look + biome colors
    enhanceTerrainGeometry(geom, EXTRUDE_DEPTH, isIsland, poly.side);
    const mat = new THREE.MeshStandardMaterial({
      vertexColors: true,
      roughness: 0.88,
      metalness: 0.0,
      flatShading: true,
      side: THREE.DoubleSide,
    });
    const mesh = new THREE.Mesh(geom, mat);
    mesh.rotation.x = -Math.PI / 2;
    mesh.position.y = 0;
    scene.add(mesh);
  }

  // Boreal Passage location landmarks — richer per-subtype 3D structures.
  // Terrain top is at y=0.3; all structures start from y=0.32 (group offset).
  // Side tinting: north = red emissive accent, south = blue emissive accent.
  // Landmark hit meshes removed — drag_visual.js is unused dead code
  // and the 10 km-tall invisible cylinders were blocking raycasts near
  // bases (Spear Point, etc.) for launcher and entity click handlers.
  for (const loc of BOREAL_LOCATIONS) {
    const [sx, sz] = saabToScene(loc.x, loc.y);
    const group = new THREE.Group();
    const isNorth  = loc.side === 'north';
    const tint     = isNorth ? 0x441515 : 0x1a2a44;
    const litColor = isNorth ? 0xff3020 : 0x4488ff;

    // Helper: box mesh placed relative to group origin (y = half-height).
    const bld = (w, h, d, color, emissive, ei, x = 0, z = 0) => {
      const m = new THREE.Mesh(
        new THREE.BoxGeometry(w, h, d),
        new THREE.MeshStandardMaterial({ color, emissive, emissiveIntensity: ei, roughness: 0.75 }),
      );
      m.position.set(x, h / 2, z);
      group.add(m);
      return m;
    };
    const cyl = (rt, rb, h, seg, color, emissive, ei, x = 0, cy = 0, z = 0, rx = 0) => {
      const m = new THREE.Mesh(
        new THREE.CylinderGeometry(rt, rb, h, seg),
        new THREE.MeshStandardMaterial({ color, emissive, emissiveIntensity: ei, roughness: 0.6 }),
      );
      m.position.set(x, cy, z);
      if (rx) m.rotation.x = rx;
      group.add(m);
      return m;
    };

    if (loc.subtype === 'air_base') {
      // ── Air base: runway, taxiway, hangars, control tower, radar, parked jet ──

      // Primary runway (concrete strip)
      bld(1.25, 0.02, 0.20, 0xb0b0a8, 0x000000, 0,  0,  0);
      // Secondary taxiway (perpendicular, shorter)
      bld(0.18, 0.015, 0.55, 0xa8a8a0, 0x000000, 0, 0.40, 0.18);

      // Hangar 1 — large shed
      bld(0.36, 0.16, 0.30, 0x8a8a84, tint, 0.18, -0.52, -0.30);
      // Hangar roof ridge
      bld(0.37, 0.05, 0.09, 0x7a7a74, tint, 0.12, -0.52, -0.30);
      // Hangar 2 — smaller
      bld(0.28, 0.12, 0.24, 0x7e7e7a, tint, 0.18, -0.52,  0.14);

      // Control tower base
      bld(0.09, 0.28, 0.10, 0x9a9a94, tint, 0.28, 0.56, -0.28);
      // Control tower cab (glass-tinted)
      {
        const cab = new THREE.Mesh(
          new THREE.BoxGeometry(0.14, 0.07, 0.15),
          new THREE.MeshStandardMaterial({ color: 0x6090b8, emissive: litColor, emissiveIntensity: 0.55, roughness: 0.35 }),
        );
        cab.position.set(0.56, 0.315, -0.28);
        group.add(cab);
      }

      // Radar mast + dish
      cyl(0.022, 0.026, 0.32, 6, 0x888880, tint, 0.18, 0.56, 0.22, 0.22);
      cyl(0.15,  0.15,  0.026, 12, 0xa0a098, tint, 0.28, 0.56, 0.50, 0.22);

      // Parked aircraft silhouette (T-shape)
      {
        const fusMat = new THREE.MeshStandardMaterial({ color: 0xb0b8c8, roughness: 0.55 });
        const fus = new THREE.Mesh(new THREE.CylinderGeometry(0.04, 0.04, 0.52, 6), fusMat);
        fus.rotation.z = Math.PI / 2;
        fus.position.set(0.10, 0.06, -0.04);
        group.add(fus);
        const wings = new THREE.Mesh(new THREE.BoxGeometry(0.58, 0.028, 0.11), fusMat);
        wings.position.set(0.10, 0.06, -0.04);
        group.add(wings);
        const vtail = new THREE.Mesh(new THREE.BoxGeometry(0.025, 0.14, 0.09), fusMat);
        vtail.position.set(-0.13, 0.12, -0.04);
        group.add(vtail);
      }

    } else if (loc.subtype === 'capital') {
      // ── Capital: dramatic skyline, dome civic hall, lit plaza, city glow ──

      // City plaza (lit ground square)
      {
        const pl = new THREE.Mesh(
          new THREE.PlaneGeometry(0.95, 0.95),
          new THREE.MeshStandardMaterial({ color: 0x1e1e28, emissive: tint, emissiveIntensity: 0.12, roughness: 1.0 }),
        );
        pl.rotation.x = -Math.PI / 2;
        pl.position.y = 0.01;
        group.add(pl);
      }

      // Main civic tower + pyramidal spire
      bld(0.21, 0.62, 0.21, 0x38383e, tint, 0.55, 0, 0);
      {
        const spire = new THREE.Mesh(
          new THREE.ConeGeometry(0.075, 0.24, 4),
          new THREE.MeshStandardMaterial({ color: 0xb8b8c4, emissive: litColor, emissiveIntensity: 0.30, roughness: 0.40 }),
        );
        spire.position.set(0, 0.62 + 0.12, 0);
        group.add(spire);
      }

      // Glass tower (reflective)
      {
        const gt = new THREE.Mesh(
          new THREE.BoxGeometry(0.16, 0.48, 0.15),
          new THREE.MeshStandardMaterial({
            color: isNorth ? 0x3a1820 : 0x1c2e40,
            emissive: tint, emissiveIntensity: 0.78,
            roughness: 0.30, metalness: 0.55,
          }),
        );
        gt.position.set(0.25, 0.24, 0.07);
        group.add(gt);
      }

      // Office blocks (varied heights)
      const offices = [
        { x: -0.21, z: 0.11, w: 0.17, h: 0.34, d: 0.14 },
        { x:  0.10, z: -0.21, w: 0.19, h: 0.40, d: 0.15 },
        { x: -0.23, z: -0.15, w: 0.14, h: 0.26, d: 0.13 },
        { x:  0.27, z: -0.19, w: 0.12, h: 0.20, d: 0.11 },
        { x:  0.08, z:  0.25, w: 0.15, h: 0.32, d: 0.13 },
        { x: -0.09, z:  0.21, w: 0.12, h: 0.17, d: 0.11 },
        { x: -0.31, z: -0.05, w: 0.10, h: 0.15, d: 0.10 },
        { x:  0.32, z:  0.13, w: 0.09, h: 0.13, d: 0.09 },
      ];
      for (const p of offices) {
        bld(p.w, p.h, p.d, 0x424248, tint, 0.50, p.x, p.z);
      }

      // Dome civic hall
      bld(0.19, 0.13, 0.19, 0x4a4a52, tint, 0.38, -0.06, -0.09);
      {
        const dome = new THREE.Mesh(
          new THREE.SphereGeometry(0.11, 12, 8, 0, Math.PI * 2, 0, Math.PI / 2),
          new THREE.MeshStandardMaterial({ color: 0x6a6a74, emissive: litColor, emissiveIntensity: 0.22, roughness: 0.5 }),
        );
        dome.position.set(-0.06, 0.13, -0.09);
        group.add(dome);
      }

      // City ambient PointLight (warm city glow)
      const glow = new THREE.PointLight(litColor, 1.4, 28, 1.6);
      glow.position.set(0, 3.5, 0);
      group.add(glow);

    } else {
      // ── Major city: mid-rise cluster, water tower, plaza, ambient glow ──

      // City plaza
      {
        const pl = new THREE.Mesh(
          new THREE.PlaneGeometry(0.58, 0.58),
          new THREE.MeshStandardMaterial({ color: 0x1c1c24, emissive: tint, emissiveIntensity: 0.10, roughness: 1.0 }),
        );
        pl.rotation.x = -Math.PI / 2;
        pl.position.y = 0.01;
        group.add(pl);
      }

      // Building cluster
      const citySpec = [
        { x:  0,     z:  0,     w: 0.15, h: 0.28, d: 0.14 },
        { x:  0.17,  z:  0.06,  w: 0.13, h: 0.20, d: 0.12 },
        { x: -0.15,  z:  0.09,  w: 0.12, h: 0.15, d: 0.11 },
        { x:  0.07,  z: -0.17,  w: 0.14, h: 0.23, d: 0.12 },
        { x: -0.13,  z: -0.11,  w: 0.11, h: 0.11, d: 0.10 },
        { x:  0.21,  z: -0.11,  w: 0.10, h: 0.15, d: 0.10 },
      ];
      for (const p of citySpec) {
        bld(p.w, p.h, p.d, 0x444448, tint, 0.50, p.x, p.z);
      }

      // Water tower (mast + tank)
      cyl(0.030, 0.035, 0.22, 6, 0x808088, tint, 0.18, -0.22, 0.11, 0.17);
      cyl(0.075, 0.075, 0.11, 8, 0x909098, tint, 0.22, -0.22, 0.28, 0.17);

      // City ambient glow (dimmer than capital)
      const glow = new THREE.PointLight(litColor, 0.7, 18, 2.0);
      glow.position.set(0, 2.2, 0);
      group.add(glow);
    }

    // Scale landmarks up dramatically so cities dominate the landscape.
    // Per-location scale override supported via loc.scale field.
    const locScale = loc.scale ?? 10.0;
    group.scale.setScalar(locScale);
    if (loc.rotation_y) group.rotation.y = loc.rotation_y;
    group.position.set(sx, 0.32, sz);
    scene.add(group);

    const label = makeTextSprite(loc.name, loc.side);
    label.position.set(sx, 14.0, sz);
    label.scale.set(18.0, 4.5, 1);
    scene.add(label);
  }

  // Stylized terrain decorations: trees, roads, coastline shore lines.
  scatterTrees(scene, BOREAL_TERRAIN, saabToScene, BOREAL_LOCATIONS);
  // Roads and coastline outlines removed — they alias badly at this
  // camera distance and the extruded terrain shapes already define
  // land boundaries visually.

  // The old blue base cylinder (CylinderGeometry(2.0, 2.5, 1.2, 12) at
  // BASE_POS) was removed in Milestone G: the base is now just one site
  // among many, rendered by the SiteRegistry as a small coloured ring
  // along with the Saab-named air bases, capital, and major cities.
  // `BASE_POS` stays exported above for scene-origin math elsewhere.

  // Weapon range arcs are now rendered per-launcher by
  // frontend/js/launchers.js (LauncherRegistry), centred on each
  // launcher's actual world position and dimming when that launcher
  // reloads. The old base-centred stack is gone — it visually conflicted
  // with the per-launcher arcs and implied every weapon fires from the
  // base, which is no longer true after Milestone F.

  // Compass (simple N marker)
  const nLabel = new THREE.Mesh(
    new THREE.SphereGeometry(0.8, 8, 6),
    new THREE.MeshStandardMaterial({ color: 0xffcc44, emissive: 0x775500 }),
  );
  const [nx, ny] = worldToSceneXY(ARENA_X / 2, ARENA_Y - 2000);
  nLabel.position.set(nx, 2, ny);
  scene.add(nLabel);

  // ── AWACS patrol aircraft — diegetic explanation for full-map vision ─────
  // Two airborne radar platforms circle their side's territory, each with a
  // rotating dome using createRadarScanDome from scene_visuals.js. Replaces
  // the previous ground-radar stations (which were draggable but had no
  // gameplay role). Pure frontend cosmetic — no backend / fog-of-war tie-in.
  function makeAwacs(side) {
    const group = new THREE.Group();
    const isRed = side === 'red';
    const bodyColor = isRed ? 0xcc4444 : 0x4488cc;
    const trimColor = isRed ? 0xaa3333 : 0x3366aa;
    const scanColor = isRed ? 0xff8888 : 0x88ccff;

    const bodyMat = new THREE.MeshStandardMaterial({
      color: bodyColor, roughness: 0.55, metalness: 0.35,
    });
    const trimMat = new THREE.MeshStandardMaterial({
      color: trimColor, roughness: 0.55, metalness: 0.35,
    });
    const domeMat = new THREE.MeshStandardMaterial({
      color: 0x888890, roughness: 0.30, metalness: 0.55,
      emissive: scanColor, emissiveIntensity: 0.15,
    });

    // All aircraft dimensions in scene units (1 unit = 1 km). A real AWACS
    // is ~50 m long but would be invisible against a 150 km arena — these
    // readable stats (fuselage ~2 km) match the same "arcade" scale used by
    // the launcher meshes and capital-city landmarks.
    const fuselage = new THREE.Mesh(new THREE.BoxGeometry(2.0, 0.25, 0.30), bodyMat);
    group.add(fuselage);
    // Nose cone
    const nose = new THREE.Mesh(new THREE.ConeGeometry(0.15, 0.45, 8), bodyMat);
    nose.rotation.z = -Math.PI / 2;
    nose.position.set(1.22, 0, 0);
    group.add(nose);
    // Main wings (span across Z) — long thin box, slightly swept back position
    const wings = new THREE.Mesh(new THREE.BoxGeometry(0.55, 0.06, 2.4), trimMat);
    wings.position.set(-0.15, -0.02, 0);
    group.add(wings);
    // Horizontal tail
    const htail = new THREE.Mesh(new THREE.BoxGeometry(0.35, 0.04, 0.95), trimMat);
    htail.position.set(-0.90, 0.05, 0);
    group.add(htail);
    // Vertical stabiliser
    const vtail = new THREE.Mesh(new THREE.BoxGeometry(0.35, 0.40, 0.04), trimMat);
    vtail.position.set(-0.90, 0.25, 0);
    group.add(vtail);
    // Engine nacelles under wings (2)
    for (const zSide of [-0.7, 0.7]) {
      const nac = new THREE.Mesh(new THREE.CylinderGeometry(0.08, 0.08, 0.45, 10), bodyMat);
      nac.rotation.z = Math.PI / 2;
      nac.position.set(-0.10, -0.12, zSide);
      group.add(nac);
    }

    // Pylons supporting the radar dome above the fuselage
    for (const xOff of [-0.25, 0.25]) {
      const pylon = new THREE.Mesh(new THREE.BoxGeometry(0.05, 0.30, 0.05), bodyMat);
      pylon.position.set(xOff, 0.28, 0);
      group.add(pylon);
    }
    // AWACS signature: flat rotating radar disc
    const dome = new THREE.Mesh(new THREE.CylinderGeometry(0.55, 0.55, 0.07, 24), domeMat);
    dome.position.set(0, 0.45, 0);
    group.add(dome);
    // Reuse the radar-scan helper for the sweep visual
    const scan = createRadarScanDome(1.2, scanColor, 0.6);
    scan.position.set(0, 0.49, 0);
    group.add(scan);

    return { group, scan };
  }

  // Patrol parameters per side. Scene coords: +X east, -Z north. Red circles
  // deep in its own northern territory, Blue loops near its southern base.
  const redAwacs = makeAwacs('red');
  redAwacs.group.userData.patrol = {
    cx: 0, cz: -180, radius: 28, altitude: 12,
    phase: 0, angSpeed: 0.08,  // ~78 s per loop
  };
  scene.add(redAwacs.group);

  const blueAwacs = makeAwacs('blue');
  blueAwacs.group.userData.patrol = {
    cx: 0, cz: -45, radius: 22, altitude: 10,
    phase: Math.PI, angSpeed: -0.06,  // counter-direction, offset phase
  };
  scene.add(blueAwacs.group);

  const awacsList = [redAwacs, blueAwacs];

  // animateRadar(t) — keeps main.js's call site; now drives AWACS patrol +
  // each aircraft's radar-scan sweep.
  function animateRadar(t) {
    for (const a of awacsList) {
      const p = a.group.userData.patrol;
      p.angle = p.phase + p.angSpeed * t;
      const x = p.cx + Math.cos(p.angle) * p.radius;
      const z = p.cz + Math.sin(p.angle) * p.radius;
      a.group.position.set(x, p.altitude, z);
      // Nose along tangent direction. Position derivative is
      // (-sin, 0, cos) · angSpeed; for angSpeed > 0 the tangent is
      // (-sin, cos), for angSpeed < 0 it is (+sin, -cos) — opposite
      // direction. Rotating default +X forward onto that vector
      // gives θ = -angle - π/2 for the positive case and an
      // additional π for the negative case. Without the π the
      // counter-rotating Blue AWACS was rendering tail-first.
      const reverse = p.angSpeed < 0 ? Math.PI : 0;
      a.group.rotation.y = -p.angle - Math.PI / 2 + reverse;
      a.scan.userData.update(t);
    }
  }

  // Resize
  window.addEventListener('resize', () => {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
    const pr = renderer.getPixelRatio();
    composer.setPixelRatio(pr);
    composer.setSize(window.innerWidth, window.innerHeight);
    smaaPass.setSize(window.innerWidth * pr, window.innerHeight * pr);
  });

  return {
    scene, camera, renderer, controls, resetCameraView, animateRadar,
    composer, waterUpdate,
  };
}

// Backend coords: X=east, Y=north, Z=up (meters).
// Scene coords:   X=east,  Y=up,    Z=south (=-north)  (three default axes).
// We center the scene on the blue base so the camera can sit at origin.
const BASE_X = BASE_POS[0];
const BASE_Y = BASE_POS[1];

export function worldToScene(x, y, z) {
  return [
    (x - BASE_X) * SCALE,           // east → +X
    z * SCALE,                      // up → +Y
    -(y - BASE_Y) * SCALE,          // north → -Z
  ];
}

export function worldToSceneXY(x, y) {
  return [(x - BASE_X) * SCALE, -(y - BASE_Y) * SCALE];
}

// Rectangular floor grid — THREE.GridHelper is always square, so we build
// one manually from LineSegments whose extent matches the rectangular
// ground plane exactly. `spacing` is in scene units (1 unit = 1 km); every
// 10th line is drawn in `mainColor`, the rest in `subColor`, reproducing
// the main/sub colour hierarchy GridHelper provided.
function makeRectGrid(width, depth, spacing, centreZ, mainColor, subColor) {
  const halfW = width / 2;
  const halfD = depth / 2;
  const minX = -halfW;
  const minZ = centreZ - halfD;
  const maxZ = centreZ + halfD;
  const mainPositions = [];
  const subPositions = [];
  // East-west lines (vary Z).
  const nZ = Math.round(depth / spacing);
  for (let i = 0; i <= nZ; i++) {
    const z = minZ + i * spacing;
    const arr = (i % 10 === 0) ? mainPositions : subPositions;
    arr.push(minX, 0, z, halfW, 0, z);
  }
  // North-south lines (vary X).
  const nX = Math.round(width / spacing);
  for (let i = 0; i <= nX; i++) {
    const x = minX + i * spacing;
    const arr = (i % 10 === 0) ? mainPositions : subPositions;
    arr.push(x, 0, minZ, x, 0, maxZ);
  }
  const group = new THREE.Group();
  for (const [positions, color] of [[mainPositions, mainColor], [subPositions, subColor]]) {
    if (positions.length === 0) continue;
    const geom = new THREE.BufferGeometry();
    geom.setAttribute(
      'position',
      new THREE.BufferAttribute(new Float32Array(positions), 3),
    );
    const mat = new THREE.LineBasicMaterial({
      color,
      transparent: true,
      opacity: 0.55,
    });
    group.add(new THREE.LineSegments(geom, mat));
  }
  return group;
}

// Canvas-textured Sprite label used for Boreal Passage landmarks. A 256×64
// offscreen canvas with a dark translucent fill, a side-coloured border
// (red for north, blue for south), and white bold text. Sprites billboard
// to the camera so labels always face the operator. depthTest:false keeps
// them readable even when they pass behind closer terrain silhouettes.
function makeTextSprite(text, side) {
  const canvas = document.createElement('canvas');
  canvas.width = 256;
  canvas.height = 64;
  const ctx = canvas.getContext('2d');
  ctx.fillStyle = 'rgba(10, 14, 24, 0.78)';
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.strokeStyle = side === 'north' ? '#c85050' : '#5080c8';
  ctx.lineWidth = 3;
  ctx.strokeRect(1.5, 1.5, canvas.width - 3, canvas.height - 3);
  ctx.fillStyle = '#ffffff';
  ctx.font = 'bold 22px sans-serif';
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillText(text, canvas.width / 2, canvas.height / 2);
  const tex = new THREE.CanvasTexture(canvas);
  tex.minFilter = THREE.LinearFilter;
  tex.magFilter = THREE.LinearFilter;
  const mat = new THREE.SpriteMaterial({
    map: tex,
    depthTest: false,
    transparent: true,
  });
  return new THREE.Sprite(mat);
}
