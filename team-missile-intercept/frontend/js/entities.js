// Entity rendering: per-kind procedural meshes, trails, explosions.
//
// Convention: each model's long axis is +Y in local space so the generic
// orientation code (setFromUnitVectors(+Y, velocity_dir)) keeps working
// regardless of threat/interceptor kind.
import * as THREE from 'three';
import { worldToScene, SCALE } from './scene.js';

const TRAIL_LEN = 60;

// Per-kind entity scale: bigger = scarier threat. Interceptors stay
// compact so the visual hierarchy reads "threats are the big things".
const KIND_SCALE = {
  drone: 1.5,
  cruise_sub: 2.0,
  ballistic: 2.8,
  hgv: 3.0,
  ciws: 0.8,
  rbs_70: 1.2,
  iris_t_sls: 1.6,
  iris_t_slm: 2.0,
  pac_2: 2.2,
  pac_3: 2.0,
};

// Seeker scanning cone: forward-pointing translucent cone attached to
// every interceptor except CIWS. Half-angle 8°, length 10 scene units
// (= 10 km at SCALE=0.001). Default cyan, opacity 0.12; shifts to
// orange / 0.30 opacity when distance-to-target drops below 2 km
// (update logic lives in EntityMesh.update).
//
// Cone orientation: ConeGeometry default has apex at +Y=+h/2 and base
// at -Y=-h/2. We rotate X by π to flip, then translate so apex sits at
// local Y=0 and base extends to +Y=length. Caller positions the cone
// at the nose tip; the cone then opens "forward" along the +Y body
// axis exactly like the mesh convention.
function makeSeekerCone() {
  const len = 10;
  const halfAngleRad = (8 * Math.PI) / 180;
  const baseR = len * Math.tan(halfAngleRad);
  const geom = new THREE.ConeGeometry(baseR, len, 16, 1, true);
  geom.rotateX(Math.PI);            // apex now at -Y, base at +Y
  geom.translate(0, len / 2, 0);    // apex → Y=0, base → Y=+len
  const mat = new THREE.MeshBasicMaterial({
    color: 0x44ccff,
    transparent: true,
    opacity: 0.12,
    depthWrite: false,
    side: THREE.DoubleSide,
  });
  return new THREE.Mesh(geom, mat);
}

function buildModel(kind, team, color) {
  const c = new THREE.Color(color || (team === 'red' ? '#ff3040' : '#ffd24a'));
  const bodyMat = new THREE.MeshStandardMaterial({
    color: c,
    emissive: c,
    emissiveIntensity: 0.35,
    roughness: 0.5,
    metalness: 0.1,
  });
  const darkMat = new THREE.MeshStandardMaterial({
    color: c.clone().multiplyScalar(0.55),
    emissive: c.clone().multiplyScalar(0.2),
    emissiveIntensity: 0.15,
    roughness: 0.7,
  });

  const g = new THREE.Group();

  if (kind === 'drone') {
    // Simple delta-wing planform with a tail-mounted propeller disc.
    // Long flight axis = +Y (nose forward), wing plane in X-Y, thin in Z.
    // The body is a 3-segment cone squashed flat so it reads as a flat
    // triangle: nose at +Y, two wing corners trailing at -Y.
    const body = new THREE.Mesh(
      new THREE.ConeGeometry(0.95, 1.9, 3),
      bodyMat,
    );
    body.scale.set(1.0, 1.0, 0.18); // squash on Z → flat triangle
    // Tail propeller: a thin disc at the rear (-Y), perpendicular to flight.
    // Cylinder default axis is +Y so we tilt it 90° so the disc face points
    // backward (its plane is X-Z = perpendicular to Y).
    const prop = new THREE.Mesh(
      new THREE.CylinderGeometry(0.32, 0.32, 0.05, 12),
      darkMat,
    );
    // Cylinder default axis is +Y (= flight axis), so the disc face already
    // sits in the X-Z plane — perpendicular to flight direction, which is
    // what we want for a rear-mounted pusher prop.
    prop.position.set(0, -0.95, 0);
    g.add(body, prop);
    // Tag the propeller for spin animation in the update loop.
    g.userData.propeller = prop;
  } else if (kind === 'cruise_sub') {
    // Kalibr-class: long slender cigar with two horizontal mid-wings and a
    // cruciform tail. Long axis = +Y (nose forward).
    // Box dims = (X span, Y chord, Z thickness). Wings lie flat in the X-Y
    // plane (thin Z) so the missile silhouette reads as a horizontal cross
    // when viewed from above.
    const body = new THREE.Mesh(
      new THREE.CylinderGeometry(0.2, 0.24, 2.6, 14),
      bodyMat,
    );
    const nose = new THREE.Mesh(
      new THREE.ConeGeometry(0.2, 0.7, 14),
      bodyMat,
    );
    nose.position.y = 1.65;
    // Mid-body horizontal wings ONLY: span 2.4 (X), chord 0.6 (Y), thin
    // along vertical (Z). They extend symmetrically to either side of the
    // fuselage and lie flat — no vertical mid-body fin.
    const midWing = new THREE.Mesh(
      new THREE.BoxGeometry(2.4, 0.6, 0.05),
      darkMat,
    );
    midWing.position.set(0, 0.1, 0);
    // Cruciform tail: horizontal fin (X span) + vertical fin (Z span) —
    // both have the same chord along Y so they read as a "+" from behind.
    const tailH = new THREE.Mesh(
      new THREE.BoxGeometry(1.0, 0.35, 0.04),
      darkMat,
    );
    const tailV = new THREE.Mesh(
      new THREE.BoxGeometry(0.04, 0.35, 1.0),
      darkMat,
    );
    tailH.position.y = -1.15;
    tailV.position.y = -1.15;
    g.add(body, nose, midWing, tailH, tailV);
  } else if (kind === 'ballistic') {
    // Big fat reentry body: larger cylinder + sharp ogive nose + 4 grid fins
    const body = new THREE.Mesh(
      new THREE.CylinderGeometry(0.45, 0.55, 3.2, 14),
      bodyMat,
    );
    const nose = new THREE.Mesh(
      new THREE.ConeGeometry(0.45, 1.3, 14),
      bodyMat,
    );
    nose.position.y = 2.25;
    // 4 tail fins at the base — X=radial extent (sticks out), Y=chord along
    // body, Z=tangential thickness (thin). Inner edge sits flush with body.
    for (let i = 0; i < 4; i++) {
      const fin = new THREE.Mesh(
        new THREE.BoxGeometry(0.45, 0.6, 0.08),
        darkMat,
      );
      const a = (i * Math.PI) / 2;
      // body radius at y=-1.45 ≈ 0.545 → fin center at 0.545 + 0.225 = 0.77
      fin.position.set(Math.cos(a) * 0.77, -1.45, Math.sin(a) * 0.77);
      fin.rotation.y = -a;
      g.add(fin);
    }
    g.add(body, nose);
  } else if (kind === 'hgv') {
    // Slender dart-shaped hypersonic glide body (DF-ZF / HTV-2 style):
    // long tapered lifting body with a pointed nose at +Y and flared rear
    // at -Y. Diamond cross-section (4-sided cone rotated 45°) flattened on
    // Z gives a sharp dorsal ridge + flat-ish belly. Small dorsal fin and
    // two horizontal side fins sit near the rear.
    const body = new THREE.Mesh(
      new THREE.ConeGeometry(0.5, 5.5, 4),
      bodyMat,
    );
    // ConeGeometry(...,4) places base vertices on the ±X and ±Z axes, so
    // the default cross-section is already a diamond. NO rotation needed:
    // rotating 45° would move the vertices onto the diagonals, giving a
    // rectangle after the Z scale — top would be a flat face, not a ridge.
    body.scale.set(1.0, 1.0, 0.35); // flatten on Z → lifting-body silhouette
    // Body spans y ∈ [-2.75, +2.75]. At y=-1.8 (near rear) the diamond has
    // half-extent ~0.41 in X and ~0.14 in Z (after Z-scale).
    // Dorsal vertical fin — sits on top ridge, inner edge flush with body.
    const dorsal = new THREE.Mesh(
      new THREE.BoxGeometry(0.04, 0.55, 0.3),
      darkMat,
    );
    dorsal.position.set(0, -1.75, 0.29);
    // Two horizontal side fins — inner edge flush with body side vertices.
    const wingL = new THREE.Mesh(
      new THREE.BoxGeometry(0.5, 0.5, 0.04),
      darkMat,
    );
    wingL.position.set(0.68, -1.8, 0);
    const wingR = wingL.clone();
    wingR.position.set(-0.68, -1.8, 0);
    g.add(body, dorsal, wingL, wingR);
  } else if (kind === 'ciws') {
    // Lvkv 90 / Bofors 3P 40 mm round — a short stubby cannon shell, no
    // fins, no plume (cannon rounds are unguided ballistic). Small tan
    // cylinder body + nose-mounted fuze cap + dark driving band. Solid
    // silhouette keeps it readable at very small scale when it streams
    // out of the inner defense ring at 300 rpm.
    const shellMat = new THREE.MeshStandardMaterial({
      color: 0xd9b36a,
      emissive: 0x5a4220,
      emissiveIntensity: 0.35,
      roughness: 0.4,
      metalness: 0.6,
    });
    const shellDark = new THREE.MeshStandardMaterial({
      color: 0x5a3e1a,
      roughness: 0.7,
      metalness: 0.2,
    });
    const shellBody = new THREE.Mesh(
      new THREE.CylinderGeometry(0.12, 0.12, 0.7, 10),
      shellMat,
    );
    const shellNose = new THREE.Mesh(
      new THREE.ConeGeometry(0.12, 0.28, 10),
      shellMat,
    );
    shellNose.position.y = 0.49;
    const drivingBand = new THREE.Mesh(
      new THREE.CylinderGeometry(0.13, 0.13, 0.06, 10),
      shellDark,
    );
    drivingBand.position.y = -0.25;
    g.add(shellBody, shellNose, drivingBand);
    // No flame — CIWS rounds are unguided ballistic, no motor plume.
  } else if (kind === 'iris_t_sls') {
    // IRIS-T SLS (RBS 98): IR imaging seeker, thrust-vector 60G agility.
    // Slender body, ogive nose with IR seeker dome, 4 mid-body canards,
    // 4 large trapezoidal tail fins, 2 accent bands.
    const size = 1.0;
    const body = new THREE.Mesh(
      new THREE.CylinderGeometry(0.11 * size, 0.13 * size, 2.0 * size, 14),
      bodyMat,
    );
    // Truncated nose cone (tapers from body radius to small flat tip where
    // the seeker dome mounts). Using CylinderGeometry with different top/bottom
    // radii gives a frustum instead of a pointed cone.
    const nose = new THREE.Mesh(
      new THREE.CylinderGeometry(0.05 * size, 0.11 * size, 0.5 * size, 14),
      bodyMat,
    );
    nose.position.y = 1.25 * size; // bottom at +1.0 (body top), flat tip at +1.5
    // IR seeker dome: half-embedded at the flat nose tip, upper hemisphere visible
    const seekerMat = new THREE.MeshStandardMaterial({
      color: 0x1a1a22,
      roughness: 0.25,
      metalness: 0.7,
    });
    const seeker = new THREE.Mesh(
      new THREE.SphereGeometry(0.05 * size, 14, 12),
      seekerMat,
    );
    seeker.position.y = 1.5 * size;
    // 2 accent bands around body (slightly wider & darker than body)
    const bandMat = new THREE.MeshStandardMaterial({
      color: c.clone().multiplyScalar(0.6),
      emissive: c.clone().multiplyScalar(0.25),
      emissiveIntensity: 0.3,
      roughness: 0.5,
    });
    for (const yPos of [0.7, -0.2]) {
      const band = new THREE.Mesh(
        new THREE.CylinderGeometry(0.135 * size, 0.135 * size, 0.08 * size, 14),
        bandMat,
      );
      band.position.y = yPos * size;
      g.add(band);
    }
    // 4 LARGE mid-body wings — IRIS-T's prominent main control surfaces.
    // Box dims: X=radial extent, Y=chord along body, Z=tangential thickness.
    for (let i = 0; i < 4; i++) {
      const wing = new THREE.Mesh(
        new THREE.BoxGeometry(0.15 * size, 0.7 * size, 0.04 * size),
        darkMat,
      );
      const a = (i * Math.PI) / 2;
      // center at body_radius + half_radial = 0.11 + 0.25 = 0.36
      wing.position.set(
        Math.cos(a) * 0.185 * size,
        0.2 * size,
        Math.sin(a) * 0.185 * size,
      );
      wing.rotation.y = -a;
      g.add(wing);
    }
    // 4 SHORT tail cruciform fins at the base.
    for (let i = 0; i < 4; i++) {
      const fin = new THREE.Mesh(
        new THREE.BoxGeometry(0.22 * size, 0.18 * size, 0.035 * size),
        darkMat,
      );
      const a = (i * Math.PI) / 2;
      // center at body_radius(tail) + half_radial = 0.13 + 0.11 = 0.24
      fin.position.set(
        Math.cos(a) * 0.24 * size,
        -0.95 * size,
        Math.sin(a) * 0.24 * size,
      );
      fin.rotation.y = -a;
      g.add(fin);
    }
    // Exhaust plume (points backward = -Y)
    const flameMat = new THREE.MeshBasicMaterial({
      color: 0xffb347,
      transparent: true,
      opacity: 0.75,
    });
    const flame = new THREE.Mesh(
      new THREE.ConeGeometry(0.18 * size, 0.9 * size, 10),
      flameMat,
    );
    flame.position.y = -1.55 * size;
    flame.rotation.z = Math.PI; // tip points -Y
    g.add(body, nose, seeker, flame);
    // tag the flame for pulsing animation
    g.userData.flame = flame;
    // Seeker cone at the nose tip (sphere sits at y=1.5*size).
    const seekerCone = makeSeekerCone();
    seekerCone.position.y = 1.55 * size;
    g.add(seekerCone);
    g.userData.seeker = seekerCone;
  } else if (kind === 'iris_t_slm') {
    // IRIS-T SLM: longer than SLS, sharp pointed nose (no IR seeker dome,
    // since SLM uses a different seeker architecture and looks pointier in
    // reference photos). Orange.
    const slmColor = new THREE.Color('#ff8c1a');
    bodyMat.color.copy(slmColor);
    bodyMat.emissive.copy(slmColor);
    darkMat.color.copy(slmColor).multiplyScalar(0.55);
    darkMat.emissive.copy(slmColor).multiplyScalar(0.2);
    c.copy(slmColor);
    const body = new THREE.Mesh(
      new THREE.CylinderGeometry(0.11, 0.13, 2.8, 14),
      bodyMat,
    );
    // Pointed ogive nose
    const nose = new THREE.Mesh(
      new THREE.ConeGeometry(0.11, 0.8, 14),
      bodyMat,
    );
    nose.position.y = 1.8;
    // Accent bands
    const bandMat = new THREE.MeshStandardMaterial({
      color: c.clone().multiplyScalar(0.6),
      emissive: c.clone().multiplyScalar(0.25),
      emissiveIntensity: 0.3,
      roughness: 0.5,
    });
    for (const yPos of [0.9, -0.3]) {
      const band = new THREE.Mesh(
        new THREE.CylinderGeometry(0.135, 0.135, 0.08, 14),
        bandMat,
      );
      band.position.y = yPos;
      g.add(band);
    }
    // 4 large mid-body wings
    for (let i = 0; i < 4; i++) {
      const wing = new THREE.Mesh(
        new THREE.BoxGeometry(0.15, 0.7, 0.04),
        darkMat,
      );
      const a = (i * Math.PI) / 2;
      wing.position.set(Math.cos(a) * 0.185, 0.3, Math.sin(a) * 0.185);
      wing.rotation.y = -a;
      g.add(wing);
    }
    // 4 short tail fins
    for (let i = 0; i < 4; i++) {
      const fin = new THREE.Mesh(
        new THREE.BoxGeometry(0.22, 0.18, 0.035),
        darkMat,
      );
      const a = (i * Math.PI) / 2;
      fin.position.set(Math.cos(a) * 0.24, -1.25, Math.sin(a) * 0.24);
      fin.rotation.y = -a;
      g.add(fin);
    }
    // Exhaust plume
    const flameMat = new THREE.MeshBasicMaterial({
      color: 0xffb347,
      transparent: true,
      opacity: 0.75,
    });
    const flame = new THREE.Mesh(
      new THREE.ConeGeometry(0.18, 0.9, 10),
      flameMat,
    );
    flame.position.y = -1.85;
    flame.rotation.z = Math.PI;
    g.add(body, nose, flame);
    g.userData.flame = flame;
    // iris_t_slm nose tip = body(1.4) + nose_h(0.8) = 2.2
    const seekerCone = makeSeekerCone();
    seekerCone.position.y = 2.2;
    g.add(seekerCone);
    g.userData.seeker = seekerCone;
  } else if (kind === 'pac_2') {
    // PAC-2 GEM: long slender missile, pointed nose, tail fins only (no
    // mid-body wings). Pink.
    const pinkColor = new THREE.Color('#ff69b4');
    bodyMat.color.copy(pinkColor);
    bodyMat.emissive.copy(pinkColor);
    darkMat.color.copy(pinkColor).multiplyScalar(0.55);
    darkMat.emissive.copy(pinkColor).multiplyScalar(0.2);
    c.copy(pinkColor);
    const body = new THREE.Mesh(
      new THREE.CylinderGeometry(0.12, 0.14, 3.0, 14),
      bodyMat,
    );
    const nose = new THREE.Mesh(
      new THREE.ConeGeometry(0.12, 0.9, 14),
      bodyMat,
    );
    nose.position.y = 1.95;
    // One accent band
    const bandMat = new THREE.MeshStandardMaterial({
      color: c.clone().multiplyScalar(0.6),
      emissive: c.clone().multiplyScalar(0.25),
      emissiveIntensity: 0.3,
      roughness: 0.5,
    });
    const band = new THREE.Mesh(
      new THREE.CylinderGeometry(0.145, 0.145, 0.08, 14),
      bandMat,
    );
    band.position.y = 0.6;
    g.add(band);
    // 4 tail fins only
    for (let i = 0; i < 4; i++) {
      const fin = new THREE.Mesh(
        new THREE.BoxGeometry(0.35, 0.55, 0.04),
        darkMat,
      );
      const a = (i * Math.PI) / 2;
      fin.position.set(Math.cos(a) * 0.315, -1.2, Math.sin(a) * 0.315);
      fin.rotation.y = -a;
      g.add(fin);
    }
    const flameMat = new THREE.MeshBasicMaterial({
      color: 0xffb347,
      transparent: true,
      opacity: 0.75,
    });
    const flame = new THREE.Mesh(
      new THREE.ConeGeometry(0.2, 0.95, 10),
      flameMat,
    );
    flame.position.y = -1.95;
    flame.rotation.z = Math.PI;
    g.add(body, nose, flame);
    g.userData.flame = flame;
    // pac_2 nose tip = body(1.5) + nose_h(0.9) = 2.4
    const seekerCone = makeSeekerCone();
    seekerCone.position.y = 2.4;
    g.add(seekerCone);
    g.userData.seeker = seekerCone;
  } else if (kind === 'pac_3') {
    // PAC-3 CRI: compact hit-to-kill interceptor, thin ogive nose, short
    // tail fin section with 4 small fins, small ACM (attitude control)
    // ring near the nose. Purple.
    const purpleColor = new THREE.Color('#a855f7');
    bodyMat.color.copy(purpleColor);
    bodyMat.emissive.copy(purpleColor);
    darkMat.color.copy(purpleColor).multiplyScalar(0.55);
    darkMat.emissive.copy(purpleColor).multiplyScalar(0.2);
    c.copy(purpleColor);
    const body = new THREE.Mesh(
      new THREE.CylinderGeometry(0.1, 0.11, 2.0, 14),
      bodyMat,
    );
    // Long sharp nose
    const nose = new THREE.Mesh(
      new THREE.ConeGeometry(0.1, 0.9, 14),
      bodyMat,
    );
    nose.position.y = 1.45;
    // ACM (divert thruster) ring near nose
    const acm = new THREE.Mesh(
      new THREE.CylinderGeometry(0.12, 0.12, 0.12, 14),
      darkMat,
    );
    acm.position.y = 0.7;
    g.add(acm);
    // Compact tail fin assembly: small skirt + 4 stubby fins
    const skirt = new THREE.Mesh(
      new THREE.CylinderGeometry(0.13, 0.14, 0.2, 14),
      darkMat,
    );
    skirt.position.y = -1.05;
    g.add(skirt);
    for (let i = 0; i < 4; i++) {
      const fin = new THREE.Mesh(
        new THREE.BoxGeometry(0.18, 0.32, 0.035),
        darkMat,
      );
      const a = (i * Math.PI) / 2;
      fin.position.set(Math.cos(a) * 0.23, -1.05, Math.sin(a) * 0.23);
      fin.rotation.y = -a;
      g.add(fin);
    }
    const flameMat = new THREE.MeshBasicMaterial({
      color: 0xffb347,
      transparent: true,
      opacity: 0.75,
    });
    const flame = new THREE.Mesh(
      new THREE.ConeGeometry(0.16, 0.8, 10),
      flameMat,
    );
    flame.position.y = -1.55;
    flame.rotation.z = Math.PI;
    g.add(body, nose, flame);
    g.userData.flame = flame;
    // pac_3 nose tip = body(1.0) + nose_h(0.9) = 1.9
    const seekerCone = makeSeekerCone();
    seekerCone.position.y = 1.9;
    g.add(seekerCone);
    g.userData.seeker = seekerCone;
  } else if (kind === 'rbs_70') {
    // RBS 70 NG: compact MANPADS-style laser beam-rider. Slender body with
    // sharp pointed nose, 4 small canards near the front, 4 larger
    // trapezoidal rear fins at the tail. Olive green.
    const rbsColor = new THREE.Color('#4a8a3a');
    bodyMat.color.copy(rbsColor);
    bodyMat.emissive.copy(rbsColor);
    darkMat.color.copy(rbsColor).multiplyScalar(0.55);
    darkMat.emissive.copy(rbsColor).multiplyScalar(0.2);
    c.copy(rbsColor);
    const body = new THREE.Mesh(
      new THREE.CylinderGeometry(0.09, 0.1, 1.6, 14),
      bodyMat,
    );
    // Sharp pointed nose (no seeker dome — RBS 70 uses laser guidance)
    const nose = new THREE.Mesh(
      new THREE.ConeGeometry(0.09, 0.5, 14),
      bodyMat,
    );
    nose.position.y = 1.05;
    // One accent band near the front
    const bandMat = new THREE.MeshStandardMaterial({
      color: c.clone().multiplyScalar(0.6),
      emissive: c.clone().multiplyScalar(0.25),
      emissiveIntensity: 0.3,
      roughness: 0.5,
    });
    const band = new THREE.Mesh(
      new THREE.CylinderGeometry(0.105, 0.105, 0.08, 14),
      bandMat,
    );
    band.position.y = 0.3;
    g.add(band);
    // 4 small front canards
    for (let i = 0; i < 4; i++) {
      const canard = new THREE.Mesh(
        new THREE.BoxGeometry(0.12, 0.14, 0.03),
        darkMat,
      );
      const a = (i * Math.PI) / 2;
      canard.position.set(Math.cos(a) * 0.15, 0.55, Math.sin(a) * 0.15);
      canard.rotation.y = -a;
      g.add(canard);
    }
    // 4 larger rear fins at the tail
    for (let i = 0; i < 4; i++) {
      const fin = new THREE.Mesh(
        new THREE.BoxGeometry(0.28, 0.35, 0.04),
        darkMat,
      );
      const a = (i * Math.PI) / 2;
      fin.position.set(Math.cos(a) * 0.24, -0.65, Math.sin(a) * 0.24);
      fin.rotation.y = -a;
      g.add(fin);
    }
    const flameMat = new THREE.MeshBasicMaterial({
      color: 0xffb347,
      transparent: true,
      opacity: 0.75,
    });
    const flame = new THREE.Mesh(
      new THREE.ConeGeometry(0.14, 0.7, 10),
      flameMat,
    );
    flame.position.y = -1.15;
    flame.rotation.z = Math.PI;
    g.add(body, nose, flame);
    g.userData.flame = flame;
    // rbs_70 nose tip = body(0.8) + nose_h(0.5) = 1.3
    const seekerCone = makeSeekerCone();
    seekerCone.position.y = 1.3;
    g.add(seekerCone);
    g.userData.seeker = seekerCone;
  } else {
    // Fallback: original single cone.
    const h = team === 'red' ? 2.2 : 1.6;
    const r = team === 'red' ? 0.7 : 0.5;
    const geo = new THREE.ConeGeometry(r, h, 8);
    geo.translate(0, h / 2, 0);
    g.add(new THREE.Mesh(geo, bodyMat));
  }

  return g;
}

class EntityMesh {
  constructor(scene, id, team, kind, color) {
    this.id = id;
    this.team = team;
    this.kind = kind;

    // Interpolation state: world-space pos/vel from last snapshot.
    // Between snapshots, interpolate() extrapolates using velocity.
    this._worldPos = null;  // [x, y, z] from last snapshot
    this._worldVel = null;  // [vx, vy, vz] from last snapshot
    this._thrustActive = false;
    this._targetState = null;

    this.mesh = buildModel(kind, team, color);
    // Per-kind scale: threats bigger = scarier, interceptors stay compact.
    const kindScale = KIND_SCALE[kind] ?? 2.0;
    this.mesh.scale.setScalar(kindScale);
    // Tag the root Group so Raycaster intersections can resolve back to
    // this entity id by walking up .parent from the child Mesh hit.
    this.mesh.userData.entityId = id;
    this.mesh.userData.entityKind = kind;
    this.mesh.userData.entityTeam = team;

    // Invisible hit sphere so in-flight entities are easy to click.
    // Radius is inversely proportional to kind scale so the clickable
    // area in screen-space is consistent across all entity sizes.
    const hitRadius = 3.0 / kindScale;
    const hitGeo = new THREE.SphereGeometry(hitRadius, 8, 6);
    const hitMat = new THREE.MeshBasicMaterial({ visible: false });
    const hitMesh = new THREE.Mesh(hitGeo, hitMat);
    this.mesh.add(hitMesh);

    scene.add(this.mesh);

    // Trail: Line with dynamic geometry + vertex color falloff.
    // Recent points are full opacity (bright), older points fade.
    this.trailPoints = [];
    const trailGeom = new THREE.BufferGeometry();
    trailGeom.setAttribute(
      'position',
      new THREE.BufferAttribute(new Float32Array(TRAIL_LEN * 3), 3),
    );
    trailGeom.setAttribute(
      'color',
      new THREE.BufferAttribute(new Float32Array(TRAIL_LEN * 3), 3),
    );
    trailGeom.setDrawRange(0, 0);
    this._trailBaseColor = new THREE.Color(
      color || (team === 'red' ? '#ff5570' : '#ffcc33'),
    );
    const trailMat = new THREE.LineBasicMaterial({
      vertexColors: true,
      transparent: true,
      opacity: 0.85,
    });
    this.trail = new THREE.Line(trailGeom, trailMat);
    scene.add(this.trail);
  }

  update(pos, vel, thrustActive, targetState) {
    // Store world-space state for interpolation between snapshots.
    this._worldPos = [pos[0], pos[1], pos[2]];
    this._worldVel = [vel[0], vel[1], vel[2]];
    this._thrustActive = thrustActive;
    this._targetState = targetState;

    this._applyScenePosition(pos[0], pos[1], pos[2], vel, true);
  }

  /** Extrapolate position forward by dt seconds of sim-time. */
  interpolate(simDt) {
    if (!this._worldPos || !this._worldVel) return;
    const wp = this._worldPos;
    const wv = this._worldVel;
    const px = wp[0] + wv[0] * simDt;
    const py = wp[1] + wv[1] * simDt;
    const pz = wp[2] + wv[2] * simDt;
    this._applyScenePosition(px, py, pz, wv, false);
  }

  _applyScenePosition(wx, wy, wz, vel, updateTrail = false) {
    const [x, y, z] = worldToScene(wx, wy, wz);
    this.mesh.position.set(x, y, z);

    // Orient cone along velocity vector
    const [vx, vy, vz] = worldToScene(
      wx + vel[0],
      wy + vel[1],
      wz + vel[2],
    );
    const dir = new THREE.Vector3(vx - x, vy - y, vz - z);
    if (dir.lengthSq() > 1e-10) {
      dir.normalize();
      const up = new THREE.Vector3(0, 1, 0);
      this.mesh.quaternion.setFromUnitVectors(up, dir);
    }

    // Flicker the SAM exhaust plume only while the motor is burning.
    const flame = this.mesh.userData?.flame;
    if (flame) {
      if (this._thrustActive) {
        flame.visible = true;
        const t = performance.now() / 1000;
        flame.material.opacity = 0.55 + 0.25 * Math.sin(t * 22 + this.id);
        const s = 0.9 + 0.2 * Math.sin(t * 18 + this.id * 1.3);
        flame.scale.set(s, 1, s);
      } else {
        flame.visible = false;
      }
    }

    // Spin the drone propeller
    const prop = this.mesh.userData?.propeller;
    if (prop) {
      prop.rotation.y += 0.6;
    }

    // Seeker scanning cone
    const seeker = this.mesh.userData?.seeker;
    if (seeker) {
      const ts = this._targetState;
      if (ts) {
        const dx = ts.pos[0] - wx;
        const dy = ts.pos[1] - wy;
        const dz = ts.pos[2] - wz;
        const distM = Math.sqrt(dx * dx + dy * dy + dz * dz);
        const locked = distM < 2000;
        seeker.material.color.setHex(locked ? 0xff8844 : 0x44ccff);
        seeker.material.opacity = locked ? 0.30 : 0.12;
        seeker.visible = true;
      } else {
        seeker.visible = false;
      }
    }

    // Trail: only append points on snapshot updates (15Hz), not every
    // interpolation frame (60Hz), so the 60-point buffer covers ~4s.
    // On interpolation frames, just update the last trail point position
    // so the trail tip tracks the smoothly-interpolated entity.
    if (updateTrail) {
      this.trailPoints.push([x, y, z]);
      if (this.trailPoints.length > TRAIL_LEN) this.trailPoints.shift();
    } else if (this.trailPoints.length > 0) {
      // Move trail tip to interpolated position for smooth trail head.
      this.trailPoints[this.trailPoints.length - 1] = [x, y, z];
    }
    const posArr = this.trail.geometry.attributes.position.array;
    const colArr = this.trail.geometry.attributes.color.array;
    const n = this.trailPoints.length;
    const bc = this._trailBaseColor;
    for (let i = 0; i < n; i++) {
      const [tx, ty, tz] = this.trailPoints[i];
      posArr[i * 3] = tx;
      posArr[i * 3 + 1] = ty;
      posArr[i * 3 + 2] = tz;
      // Fade: oldest point → 0.1 brightness, newest → 1.0
      const fade = n > 1 ? 0.1 + 0.9 * (i / (n - 1)) : 1.0;
      colArr[i * 3] = bc.r * fade;
      colArr[i * 3 + 1] = bc.g * fade;
      colArr[i * 3 + 2] = bc.b * fade;
    }
    this.trail.geometry.attributes.position.needsUpdate = true;
    this.trail.geometry.attributes.color.needsUpdate = true;
    this.trail.geometry.setDrawRange(0, n);
  }

  dispose(scene) {
    scene.remove(this.mesh);
    // mesh is a Group — walk children to release GPU resources.
    this.mesh.traverse((obj) => {
      if (obj.geometry) obj.geometry.dispose();
      if (obj.material) {
        if (Array.isArray(obj.material)) {
          obj.material.forEach((m) => m.dispose());
        } else {
          obj.material.dispose();
        }
      }
    });
    scene.remove(this.trail);
    this.trail.geometry.dispose();
    this.trail.material.dispose();
  }
}

export class EntityRegistry {
  constructor(scene) {
    this.scene = scene;
    this.byId = new Map();
    this.explosions = [];
    // Interpolation: time of last snapshot arrival (real-time seconds)
    this._lastSnapRealTime = 0;
    this._simSpeed = 1;
    // Engagement lines: blue interceptor → assigned red target
    this.engagementLines = new Map();
    this._engLineMat = new THREE.LineBasicMaterial({
      color: 0x44ff88,
      transparent: true,
      opacity: 0.2,
      depthWrite: false,
    });
  }

  updateFromSnapshot(snap) {
    // Record snapshot arrival time + sim speed for interpolation.
    this._lastSnapRealTime = performance.now() / 1000;
    this._simSpeed = snap.speed ?? 1;

    // Build an id→state map so interceptors can look up their target
    // (for seeker-cone colour / opacity). Only include alive entities —
    // dead targets should make the seeker snap off.
    const aliveById = new Map();
    for (const e of snap.entities) {
      if (e.alive) aliveById.set(e.id, e);
    }
    // Reconcile entities
    const seen = new Set();
    for (const e of snap.entities) {
      seen.add(e.id);
      let em = this.byId.get(e.id);
      if (!em) {
        em = new EntityMesh(this.scene, e.id, e.team, e.kind, e.color);
        this.byId.set(e.id, em);
      }
      if (e.alive) {
        const tgt = (e.target_id !== null && e.target_id !== undefined)
          ? aliveById.get(e.target_id)
          : null;
        em.update(e.pos, e.vel, e.thrust_active, tgt);
      }
    }
    // Dispose disappeared entities
    for (const [id, em] of this.byId) {
      if (!seen.has(id)) {
        em.dispose(this.scene);
        this.byId.delete(id);
      }
    }

    // Engagement lines: draw from each alive blue interceptor to its target.
    const activeEngagements = new Set();
    for (const e of snap.entities) {
      if (!e.alive || e.team !== 'blue') continue;
      if (e.target_id == null) continue;
      const tgt = aliveById.get(e.target_id);
      if (!tgt) continue;
      const key = e.id;
      activeEngagements.add(key);
      let line = this.engagementLines.get(key);
      if (!line) {
        const geom = new THREE.BufferGeometry();
        geom.setAttribute('position', new THREE.BufferAttribute(new Float32Array(6), 3));
        line = new THREE.Line(geom, this._engLineMat);
        this.scene.add(line);
        this.engagementLines.set(key, line);
      }
      const [sx, sy, sz] = worldToScene(e.pos[0], e.pos[1], e.pos[2]);
      const [tx, ty, tz] = worldToScene(tgt.pos[0], tgt.pos[1], tgt.pos[2]);
      const arr = line.geometry.attributes.position.array;
      arr[0] = sx; arr[1] = sy; arr[2] = sz;
      arr[3] = tx; arr[4] = ty; arr[5] = tz;
      line.geometry.attributes.position.needsUpdate = true;
    }
    // Remove stale engagement lines
    for (const [key, line] of this.engagementLines) {
      if (!activeEngagements.has(key)) {
        this.scene.remove(line);
        line.geometry.dispose();
        this.engagementLines.delete(key);
      }
    }

    // Explosions
    for (const ex of snap.explosions) {
      // Only spawn a visual once per explosion — use position+t as key
      const key = `${ex.t.toFixed(3)}_${ex.pos[0].toFixed(1)}_${ex.pos[1].toFixed(1)}`;
      if (!this._exKeys) this._exKeys = new Set();
      if (!this._exKeys.has(key)) {
        this._exKeys.add(key);
        this._spawnExplosion(ex.pos);
        // prune old keys
        if (this._exKeys.size > 500) {
          this._exKeys = new Set(Array.from(this._exKeys).slice(-200));
        }
      }
    }
  }

  /**
   * Extrapolate all alive entities forward from their last snapshot
   * position using stored velocity. Called every RAF frame for smooth
   * 60Hz motion between 15Hz backend snapshots.
   */
  interpolateEntities() {
    const realNow = performance.now() / 1000;
    const realDt = realNow - this._lastSnapRealTime;
    // Convert real-time delta to sim-time delta
    const simDt = realDt * this._simSpeed;
    // Clamp to avoid overshooting on lag spikes or tab-switch
    const clampedDt = Math.min(simDt, 0.2 * this._simSpeed);
    for (const em of this.byId.values()) {
      em.interpolate(clampedDt);
    }

    // Step explosion animations (runs every frame for smooth visuals)
    for (const ex of this.explosions) {
      const age = realNow - ex.born;
      const t = Math.min(1, age / ex.lifetime);
      if (ex.isDebris) {
        const dt = 1 / 60;
        ex.mesh.position.x += ex.vel[0] * SCALE * dt;
        ex.mesh.position.y += ex.vel[1] * SCALE * dt;
        ex.mesh.position.z += ex.vel[2] * SCALE * dt;
        ex.mesh.material.opacity = Math.max(0, 0.9 * (1 - t));
        ex.mesh.scale.setScalar(Math.max(0.01, 1 - t));
      } else {
        const rate = ex.scaleRate ?? 18;
        const scale = 1 + t * rate;
        ex.mesh.scale.setScalar(scale * SCALE * 1000);
        ex.mesh.material.opacity = Math.max(0, 0.9 - t);
      }
    }
    this.explosions = this.explosions.filter((ex) => {
      const age = realNow - ex.born;
      if (age >= ex.lifetime) {
        this.scene.remove(ex.mesh);
        ex.mesh.geometry.dispose();
        ex.mesh.material.dispose();
        return false;
      }
      return true;
    });
  }

  _spawnExplosion(pos) {
    const [x, y, z] = worldToScene(pos[0], pos[1], pos[2]);
    const now = performance.now() / 1000;

    // 1. Hot-white core flash (original)
    const coreMat = new THREE.MeshBasicMaterial({
      color: 0xffffee,
      transparent: true,
      opacity: 1.0,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
    });
    const core = new THREE.Mesh(new THREE.SphereGeometry(0.8, 14, 12), coreMat);
    core.position.set(x, y, z);
    this.scene.add(core);
    this.explosions.push({ mesh: core, born: now, lifetime: 1.0 });

    // 2. Orange-red fireball: slower expansion, longer duration
    const fbMat = new THREE.MeshBasicMaterial({
      color: 0xff6620,
      transparent: true,
      opacity: 0.7,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
    });
    const fireball = new THREE.Mesh(new THREE.SphereGeometry(1.2, 12, 10), fbMat);
    fireball.position.set(x, y, z);
    this.scene.add(fireball);
    this.explosions.push({ mesh: fireball, born: now, lifetime: 1.3, scaleRate: 10 });

    // 3. Shockwave ring: expanding horizontal ring
    const ringMat = new THREE.MeshBasicMaterial({
      color: 0xffaa44,
      transparent: true,
      opacity: 0.5,
      depthWrite: false,
      side: THREE.DoubleSide,
      blending: THREE.AdditiveBlending,
    });
    const ring = new THREE.Mesh(new THREE.RingGeometry(0.5, 1.5, 24), ringMat);
    ring.position.set(x, y, z);
    ring.rotation.x = -Math.PI / 2;
    this.scene.add(ring);
    this.explosions.push({ mesh: ring, born: now, lifetime: 0.8, scaleRate: 25, isRing: true });

    // 4. Debris particles: small spheres flung outward
    for (let i = 0; i < 10; i++) {
      const dMat = new THREE.MeshBasicMaterial({
        color: Math.random() > 0.5 ? 0xffcc44 : 0xff6633,
        transparent: true,
        opacity: 0.9,
        depthWrite: false,
        blending: THREE.AdditiveBlending,
      });
      const debris = new THREE.Mesh(new THREE.SphereGeometry(0.15, 4, 3), dMat);
      debris.position.set(x, y, z);
      const vx = (Math.random() - 0.5) * 40;
      const vy = (Math.random() - 0.3) * 30;
      const vz = (Math.random() - 0.5) * 40;
      this.scene.add(debris);
      this.explosions.push({
        mesh: debris,
        born: now,
        lifetime: 0.6 + Math.random() * 0.4,
        vel: [vx, vy, vz],
        isDebris: true,
      });
    }
  }
}
