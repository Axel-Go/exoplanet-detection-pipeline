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
  quiet:        0x484d54,
  no_data:      0x35383d,
};

const REDUCED = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

function colorFor(outcome) {
  for (const key in COLORS) {
    if (String(outcome).startsWith(key)) return COLORS[key];
  }
  return 0x4a4e54;
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

async function getJSON(path) {
  const response = await fetch(path);
  if (!response.ok) {
    console.error(`sky: could not load ${path} (HTTP ${response.status})`);
    return null;
  }
  return response.json();
}

async function main() {
  const canvas = document.getElementById("sky");
  if (!canvas) return;

  const data = await getJSON("site_data.json");
  if (!data) return;
  const stars = data.stars || data;

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 100);
  camera.position.set(0, 0.6, 3.2);

  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

  const globe = new THREE.Mesh(
    new THREE.SphereGeometry(0.985, 36, 18),
    new THREE.MeshBasicMaterial({
      color: 0x2a2e34, wireframe: true, transparent: true, opacity: 0,
    })
  );
  scene.add(globe);

  // ---- build the point cloud ----

  const base = [];
  const meta = [];

  for (const star of stars) {
    const p = star.position;
    if (!p) continue;
    const ra = p.ra ?? p[0];
    const dec = p.dec ?? p[1];
    if (ra === undefined || dec === undefined) continue;

    const v = toVector(ra, dec);
    base.push(v.x, v.y, v.z);
    meta.push(star);
  }

  const n = meta.length;
  console.log(`sky: plotted ${n} of ${stars.length} stars`);

  // three colour buffers: what is drawn, and the two ends of a transition
  const live = new Float32Array(n * 3);
  const from = new Float32Array(n * 3);
  const to = new Float32Array(n * 3);
  const scratch = new THREE.Color();

  function writeColors(target, outcomes) {
    for (let i = 0; i < n; i++) {
      scratch.setHex(colorFor(outcomes[i]));
      target[i * 3] = scratch.r;
      target[i * 3 + 1] = scratch.g;
      target[i * 3 + 2] = scratch.b;
    }
  }

  const startOutcomes = meta.map((s) => s.outcome);
  writeColors(live, startOutcomes);
  from.set(live);
  to.set(live);

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.Float32BufferAttribute(base.slice(), 3));
  geometry.setAttribute("color", new THREE.BufferAttribute(live, 3));

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

  const state = { spread: 0, fade: 0, blend: 1 };
  const SCATTER = 0.45;
  const delays = meta.map(() => Math.random() * SCATTER);

  if (REDUCED) {
    state.spread = 1;
    state.fade = 1;
  } else {
    animate(state, { spread: [0, 1], duration: 2400, ease: "outExpo" });
    animate(state, { fade: [0, 1], duration: 1100, ease: "outQuad" });
  }

  function applyFrame() {
    const pos = geometry.attributes.position.array;
    for (let i = 0; i < n; i++) {
      const local = Math.min(Math.max((state.spread - delays[i]) / (1 - SCATTER), 0), 1);
      pos[i * 3]     = base[i * 3]     * local;
      pos[i * 3 + 1] = base[i * 3 + 1] * local;
      pos[i * 3 + 2] = base[i * 3 + 2] * local;
    }
    geometry.attributes.position.needsUpdate = true;

    if (state.blend < 1) {
      const t = state.blend;
      for (let i = 0; i < live.length; i++) {
        live[i] = from[i] + (to[i] - from[i]) * t;
      }
      geometry.attributes.color.needsUpdate = true;
    }

    material.opacity = state.fade;
    globe.material.opacity = state.fade * 0.25;
  }

  // ---- the slider drives the colours ----

  const sweep = await getJSON("sweep.json");
  if (sweep) {
    const byTic = sweep.outcomes;
    let colourAnim = null;

    document.addEventListener("capchange", (event) => {
      const index = event.detail.index;
      const outcomes = meta.map((s) => {
        const row = byTic[String(s.tic_id)];
        return row ? row[index] : s.outcome;
      });

      from.set(live);
      writeColors(to, outcomes);

      if (REDUCED) {
        live.set(to);
        geometry.attributes.color.needsUpdate = true;
        return;
      }

      if (colourAnim && colourAnim.pause) colourAnim.pause();
      state.blend = 0;
      colourAnim = animate(state, { blend: 1, duration: 420, ease: "outQuad" });
    });
  }

  // ---- camera flight ----

  function flyTo(index) {
    const target = new THREE.Vector3(
      base[index * 3], base[index * 3 + 1], base[index * 3 + 2]
    ).multiplyScalar(2.1);

    const cam = { x: camera.position.x, y: camera.position.y, z: camera.position.z };
    controls.autoRotate = false;
    animate(cam, {
      x: target.x, y: target.y, z: target.z,
      duration: 1100,
      ease: "inOutQuad",
      onUpdate: () => camera.position.set(cam.x, cam.y, cam.z),
    });
  }

  // ---- click to inspect (screen-space picking) ----

  const tip = document.getElementById("sky-tip");
  const projected = new THREE.Vector3();

  function pickNearest(px, py, rect) {
    let best = -1;
    let bestDist = 24; // pixels

    for (let i = 0; i < n; i++) {
      projected.set(base[i * 3], base[i * 3 + 1], base[i * 3 + 2]);
      if (projected.dot(camera.position) < 0) continue;
      projected.project(camera);
      if (projected.z > 1) continue;

      const sx = (projected.x * 0.5 + 0.5) * rect.width;
      const sy = (-projected.y * 0.5 + 0.5) * rect.height;
      const d = Math.hypot(sx - px, sy - py);
      if (d < bestDist) { bestDist = d; best = i; }
    }
    return best;
  }

  canvas.addEventListener("pointerdown", (event) => {
    const rect = canvas.getBoundingClientRect();
    const index = pickNearest(event.clientX - rect.left, event.clientY - rect.top, rect);

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
    const link = tip.querySelector(".st-link");
    if (link) link.setAttribute("href", `stars/${star.tic_id}.html`);
    tip.querySelector(".st-meta").textContent = star.period_days
      ? `period ${Number(star.period_days).toFixed(4)} d · SDE ${Number(star.sde).toFixed(1)}`
      : "no detection";

    if (!REDUCED) {
      animate(tip, { opacity: [0, 1], translateY: [-8, 0], duration: 320, ease: "outQuad" });
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
    applyFrame();
    controls.update();
    renderer.render(scene, camera);
    requestAnimationFrame(frame);
  }
  frame();
}

main();
