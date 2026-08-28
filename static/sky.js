import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";

const { animate } = window.anime;

// Greyscale for now — brightness carries the meaning.
const COLORS = {
  found:        0xffffff,
  false_alarm:  0xb9bec5,
  harmonic:     0x9aa0a7,
  wrong_period: 0x9aa0a7,
  missed:       0x5c6167,
  quiet:        0x44484e,
  no_data:      0x33363b,
};

const REDUCED = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

function colorFor(outcome) {
  for (const key in COLORS) {
    if (outcome.startsWith(key)) return COLORS[key];
  }
  return 0x5c6167;
}

// Right ascension / declination (degrees) -> a point on a unit sphere.
function toVector(ra, dec) {
  const a = (ra * Math.PI) / 180;
  const d = (dec * Math.PI) / 180;
  return new THREE.Vector3(
    Math.cos(d) * Math.cos(a),
    Math.sin(d),
    -Math.cos(d) * Math.sin(a)
  );
}

function dotTexture() {
  const size = 64;
  const c = document.createElement("canvas");
  c.width = c.height = size;
  const ctx = c.getContext("2d");
  const g = ctx.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2);
  g.addColorStop(0, "rgba(255,255,255,1)");
  g.addColorStop(0.4, "rgba(255,255,255,0.85)");
  g.addColorStop(1, "rgba(255,255,255,0)");
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, size, size);
  return new THREE.CanvasTexture(c);
}

async function main() {
  const canvas = document.getElementById("sky");
  if (!canvas) return;

  const response = await fetch("site_data.json");
  if (!response.ok) {
    console.error(`sky: could not load site_data.json (HTTP ${response.status})`);
    return;
  }
  const data = await response.json();
  const stars = data.stars || data;

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 100);
  camera.position.set(0, 0.6, 3.2);

  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

  const globe = new THREE.Mesh(
    new THREE.SphereGeometry(0.985, 36, 18),
    new THREE.MeshBasicMaterial({
      color: 0x2a2e34,
      wireframe: true,
      transparent: true,
      opacity: 0,
    })
  );
  scene.add(globe);

  // ---- build the point cloud ----

  const base = [];
  const colors = [];
  const meta = [];

  for (const star of stars) {
    const p = star.position;
    if (!p) continue;
    const ra = p.ra ?? p[0];
    const dec = p.dec ?? p[1];
    if (ra === undefined || dec === undefined) continue;

    const v = toVector(ra, dec);
    base.push(v.x, v.y, v.z);

    const c = new THREE.Color(colorFor(String(star.outcome || "")));
    colors.push(c.r, c.g, c.b);
    meta.push(star);
  }

  console.log(`sky: plotted ${meta.length} of ${stars.length} stars`);

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.Float32BufferAttribute(base.slice(), 3));
  geometry.setAttribute("color", new THREE.Float32BufferAttribute(colors, 3));

  const material = new THREE.PointsMaterial({
    size: 0.045,
    map: dotTexture(),
    vertexColors: true,
    transparent: true,
    opacity: 0,
    depthWrite: false,
    sizeAttenuation: true,
    blending: THREE.AdditiveBlending,
  });

  const points = new THREE.Points(geometry, material);
  scene.add(points);

  const controls = new OrbitControls(camera, canvas);
  controls.enableDamping = true;
  controls.dampingFactor = 0.06;
  controls.enablePan = false;
  controls.minDistance = 1.6;
  controls.maxDistance = 6;
  controls.autoRotate = !REDUCED;
  controls.autoRotateSpeed = 0.35;

  // ---- anime.js drives these plain numbers; the render loop reads them ----

  const state = { spread: 0, fade: 0 };
  const SCATTER = 0.45;
  const delays = meta.map(() => Math.random() * SCATTER);

  if (REDUCED) {
    state.spread = 1;
    state.fade = 1;
  } else {
    animate(state, { spread: [0, 1], duration: 2400, ease: "outExpo" });
    animate(state, { fade: [0, 1], duration: 1100, ease: "outQuad" });
  }

  function applySpread() {
    const arr = geometry.attributes.position.array;
    for (let i = 0; i < meta.length; i++) {
      const local = Math.min(Math.max((state.spread - delays[i]) / (1 - SCATTER), 0), 1);
      arr[i * 3]     = base[i * 3]     * local;
      arr[i * 3 + 1] = base[i * 3 + 1] * local;
      arr[i * 3 + 2] = base[i * 3 + 2] * local;
    }
    geometry.attributes.position.needsUpdate = true;
    material.opacity = state.fade;
    globe.material.opacity = state.fade * 0.25;
  }

  // ---- camera flight ----

  function flyTo(index) {
    const target = new THREE.Vector3(
      base[index * 3], base[index * 3 + 1], base[index * 3 + 2]
    ).multiplyScalar(2.1);

    const from = {
      x: camera.position.x,
      y: camera.position.y,
      z: camera.position.z,
    };

    controls.autoRotate = false;
    animate(from, {
      x: target.x,
      y: target.y,
      z: target.z,
      duration: 1100,
      ease: "inOutQuad",
      onUpdate: () => camera.position.set(from.x, from.y, from.z),
    });
  }

  // ---- click to inspect (screen-space picking) ----

  const tip = document.getElementById("sky-tip");
  const projected = new THREE.Vector3();

  function pickNearest(px, py, rect) {
    let best = -1;
    let bestDist = 24; // pixels

    for (let i = 0; i < meta.length; i++) {
      projected.set(base[i * 3], base[i * 3 + 1], base[i * 3 + 2]);

      // skip stars on the far side of the globe
      if (projected.dot(camera.position) < 0) continue;

      projected.project(camera);
      if (projected.z > 1) continue; // behind the camera

      const sx = (projected.x * 0.5 + 0.5) * rect.width;
      const sy = (-projected.y * 0.5 + 0.5) * rect.height;
      const d = Math.hypot(sx - px, sy - py);

      if (d < bestDist) {
        bestDist = d;
        best = i;
      }
    }
    return best;
  }

  canvas.addEventListener("pointerdown", (event) => {
    const rect = canvas.getBoundingClientRect();
    const px = event.clientX - rect.left;
    const py = event.clientY - rect.top;

    const index = pickNearest(px, py, rect);
    console.log("click: index =", index);

    if (index < 0) {
      tip.hidden = true;
      controls.autoRotate = !REDUCED;
      return;
    }

    const star = meta[index];
    tip.hidden = false;
    tip.querySelector(".st-id").textContent = "TIC " + star.tic_id;
    tip.querySelector(".st-outcome").textContent =
      String(star.outcome || "").replace(/_/g, " ") + " · " + star.group;
    tip.querySelector(".st-meta").textContent = star.period_days
      ? `period ${Number(star.period_days).toFixed(4)} d · SDE ${Number(star.sde).toFixed(1)}`
      : "no detection";

    if (!REDUCED) {
      animate(tip, {
        opacity: [0, 1],
        translateY: [-8, 0],
        duration: 320,
        ease: "outQuad",
      });
    }

    flyTo(index);
  });

  function resize() {
    const w = canvas.clientWidth;
    const h = canvas.clientHeight;
    if (canvas.width !== w || canvas.height !== h) {
      renderer.setSize(w, h, false);
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
    }
  }

  function frame() {
    resize();
    applySpread();
    controls.update();
    renderer.render(scene, camera);
    requestAnimationFrame(frame);
  }
  frame();
}

main();