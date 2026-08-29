// The size-cap control.
//
// Every number here came out of score.py via sweep.py — this file maps a
// pointer position to an index and paints what Python already decided.
// It computes no science of its own.

const { animate } = window.anime;
const REDUCED = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

const el = (id) => document.getElementById(id);

async function main() {
  const track = el("cap-track");
  const handle = el("cap-handle");
  if (!track || !handle) return;

  const response = await fetch("sweep.json");
  if (!response.ok) {
    console.error(`slider: could not load sweep.json (HTTP ${response.status})`);
    return;
  }
  const sweep = await response.json();

  const { caps, points, geom } = sweep;
  const last = caps.length - 1;

  const marker = el("curve-marker");
  const dotRecall = el("dot-recall");
  const dotFar = el("dot-far");
  const valueOut = el("cap-value");
  const readOut = el("cap-read");
  const readRecall = el("read-recall");
  const readFar = el("read-far");

  // The two hero figures, in document order: recall, then false alarms.
  const figures = document.querySelectorAll(".hs-value");

  // Legend rows: each declares which outcomes it counts.
  const legendRows = Array.from(document.querySelectorAll("#sky-legend li")).map((li) => ({
    node: li.querySelector(".lg-count"),
    prefixes: (li.dataset.outcomes || "").split(/\s+/).filter(Boolean),
    shown: Number(li.querySelector(".lg-count").textContent) || 0,
  }));
  const allTics = Object.keys(sweep.outcomes || {});

  function setLegend(index) {
    if (!legendRows.length || !allTics.length) return;

    const counts = legendRows.map(() => 0);
    for (const tic of allTics) {
      const outcome = sweep.outcomes[tic][index];
      legendRows.forEach((row, i) => {
        if (row.prefixes.some((pre) => outcome.startsWith(pre))) counts[i] += 1;
      });
    }

    legendRows.forEach((row, i) => {
      const target = counts[i];
      if (REDUCED || Math.abs(target - row.shown) < 1) {
        row.shown = target;
        row.node.textContent = target;
        return;
      }
      animate(row, {
        shown: target,
        duration: 320,
        ease: "outQuad",
        onUpdate: () => { row.node.textContent = Math.round(row.shown); },
      });
    });
  }

  const shown = { recall: 0, far: 0 };
  let numberAnims = [];

  function setFigures(point) {
    const targets = {
      recall: point.recall * 100,
      far: point.false_alarm_rate * 100,
    };

    numberAnims.forEach((a) => a && a.pause && a.pause());
    numberAnims = [];

    ["recall", "far"].forEach((key, i) => {
      const node = figures[i];
      if (!node) return;
      if (REDUCED) {
        shown[key] = targets[key];
        node.textContent = targets[key].toFixed(1);
        return;
      }
      numberAnims.push(
        animate(shown, {
          [key]: targets[key],
          duration: 300,
          ease: "outQuad",
          onUpdate: () => { node.textContent = shown[key].toFixed(1); },
        })
      );
    });
  }

  let current = -1;

  function setIndex(index) {
    index = Math.max(0, Math.min(last, Math.round(index)));
    if (index === current) return;
    current = index;

    const cap = caps[index];
    const point = points[index];
    const fraction = index / last;

    handle.style.left = `${fraction * 100}%`;
    valueOut.textContent = cap.toFixed(2);

    readOut.textContent =
      `${point.recovered} of ${point.known_analysed} planets recovered · ` +
      `${point.false_alarms} of ${point.controls_analysed} controls flagged`;
    if (readRecall) readRecall.textContent = `${point.recovered} of ${point.known_analysed}`;
    if (readFar) readFar.textContent = `${point.false_alarms} of ${point.controls_analysed}`;

    const x = geom.x[index];
    marker.setAttribute("x1", x);
    marker.setAttribute("x2", x);
    dotRecall.setAttribute("cx", x);
    dotRecall.setAttribute("cy", geom.recall[index]);
    dotFar.setAttribute("cx", x);
    dotFar.setAttribute("cy", geom.far[index]);

    if (!REDUCED) {
      animate([dotRecall, dotFar], { r: [6, 4], duration: 320, ease: "outQuad" });
    }

    setFigures(point);
    setLegend(index);
    track.setAttribute("aria-valuenow", cap.toFixed(2));
    track.setAttribute("aria-valuetext",
      `${cap.toFixed(2)} — ${point.recovered} of ${point.known_analysed} planets recovered, ` +
      `${point.false_alarms} of ${point.controls_analysed} false alarms`);

    document.dispatchEvent(
      new CustomEvent("capchange", { detail: { index, cap, point } })
    );
  }

  function indexFromEvent(event) {
    const rect = track.getBoundingClientRect();
    const fraction = (event.clientX - rect.left) / rect.width;
    return Math.max(0, Math.min(1, fraction)) * last;
  }

  let dragging = false;

  track.addEventListener("pointerdown", (event) => {
    dragging = true;
    track.setPointerCapture(event.pointerId);
    setIndex(indexFromEvent(event));
  });

  track.addEventListener("pointermove", (event) => {
    if (dragging) setIndex(indexFromEvent(event));
  });

  track.addEventListener("pointerup", (event) => {
    dragging = false;
    track.releasePointerCapture(event.pointerId);
  });

  // keyboard
  track.tabIndex = 0;
  track.setAttribute("role", "slider");
  track.setAttribute("aria-label", "planet size cap");
  track.setAttribute("aria-valuemin", caps[0]);
  track.setAttribute("aria-valuemax", caps[last]);
  track.addEventListener("keydown", (event) => {
    const step = { ArrowLeft: -1, ArrowDown: -1, ArrowRight: 1, ArrowUp: 1 }[event.key];
    if (!step) return;
    event.preventDefault();
    setIndex(current + step);
  });

  setIndex(caps.indexOf(sweep.default_cap));
  console.log(`slider: ${caps.length} caps, starting at ${sweep.default_cap}`);
}

main();
