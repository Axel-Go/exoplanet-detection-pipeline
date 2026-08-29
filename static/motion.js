// Page choreography. anime.js sequences the hero's arrival and reveals
// sections as they scroll into view.
//
// Nothing here is hidden by CSS — every starting state is set by JS at
// runtime, so if this file fails to load the page still reads normally.

const { createTimeline, animate, stagger, utils } = window.anime;
const REDUCED = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

function all(selector) {
  return Array.from(document.querySelectorAll(selector));
}

// Draw an SVG line as if traced by a pen: dash the stroke to its own
// length, offset it fully out of view, then walk the offset back to zero.
function drawable(node) {
  if (!node || !node.getTotalLength) return null;
  const length = node.getTotalLength();
  utils.set(node, { strokeDasharray: length, strokeDashoffset: length });
  return { node, length };
}

function heroIntro() {
  const copy = document.querySelector(".hero-copy");
  if (!copy) return;

  const eyebrow = copy.querySelector(".eyebrow");
  const lines = all(".hero-copy h1 .line");
  const lede = copy.querySelector(".lede");
  const stats = all(".hero-stats > div");
  const control = document.getElementById("cap-control");
  const buttons = all(".hero-actions .btn");
  const hint = document.querySelector(".sky-hint");

  const recallLine = drawable(document.querySelector(".curve .line-recall"));
  const farLine = drawable(document.querySelector(".curve .line-far"));
  const dots = all(".curve .dot");
  const track = document.getElementById("cap-track");

  // starting states
  utils.set([eyebrow, lede, ...stats, ...buttons, hint].filter(Boolean),
            { opacity: 0, translateY: 12 });
  utils.set(lines, { opacity: 0, translateY: 28 });
  utils.set(dots, { opacity: 0 });
  if (control) utils.set(control, { opacity: 0 });
  if (track) utils.set(track, { scaleX: 0, transformOrigin: "0 50%" });

  const tl = createTimeline({ defaults: { duration: 700, ease: "outQuad" } });

  tl.add(eyebrow, { opacity: [0, 1], translateY: [12, 0], duration: 500 })
    .add(lines, {
      opacity: [0, 1],
      translateY: [28, 0],
      duration: 800,
      ease: "outExpo",
      delay: stagger(90),
    }, "<-=250")
    .add(lede, { opacity: [0, 1], translateY: [12, 0] }, "<-=500")
    .add(stats, { opacity: [0, 1], translateY: [12, 0], delay: stagger(110) }, "<-=400")
    .add(control, { opacity: [0, 1], duration: 400 }, "<-=300");

  if (recallLine) {
    tl.add(recallLine.node, {
      strokeDashoffset: [recallLine.length, 0],
      duration: 1300,
      ease: "inOutQuad",
    }, "<-=200");
  }
  if (farLine) {
    tl.add(farLine.node, {
      strokeDashoffset: [farLine.length, 0],
      duration: 1300,
      ease: "inOutQuad",
    }, "<-=1250");
  }

  tl.add(track, { scaleX: [0, 1], duration: 600, ease: "outExpo" }, "<-=700")
    .add(dots, { opacity: [0, 1], duration: 400 }, "<-=200")
    .add(buttons, { opacity: [0, 1], translateY: [12, 0], delay: stagger(80) }, "<-=500")
    .add(hint, { opacity: [0, 0.6], translateY: [12, 0] }, "<-=400");
}

// Reveal on scroll. IntersectionObserver decides *when*; anime.js does the move.
function revealOnScroll() {
  const groups = [
    { nodes: all(".step-list li"), stagger: 90 },
    { nodes: all(".claim p"), stagger: 120 },
    { nodes: all(".figures .fig"), stagger: 120 },
  ].filter((g) => g.nodes.length);

  groups.forEach((group) => {
    utils.set(group.nodes, { opacity: 0, translateY: 20 });
  });

  const seen = new WeakSet();
  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (!entry.isIntersecting || seen.has(entry.target)) return;
      seen.add(entry.target);

      const group = groups.find((g) => g.nodes.includes(entry.target));
      const index = group ? group.nodes.indexOf(entry.target) : 0;

      animate(entry.target, {
        opacity: [0, 1],
        translateY: [20, 0],
        duration: 700,
        delay: (group ? group.stagger : 0) * Math.min(index, 4) * 0.3,
        ease: "outQuad",
      });
    });
  }, { rootMargin: "0px 0px -12% 0px", threshold: 0.15 });

  groups.forEach((g) => g.nodes.forEach((node) => observer.observe(node)));
}

// If anything in here throws, the page must not be left half-hidden:
// undo every starting state we set and show the content plainly.
function rescue() {
  const hidden = [
    ".hero-copy .eyebrow", ".hero-copy h1 .line", ".hero-copy .lede",
    ".hero-stats > div", "#cap-control", "#cap-track", ".curve .dot",
    ".hero-actions .btn", ".sky-hint", ".step-list li", ".claim p", ".figures .fig",
  ];
  hidden.forEach((selector) => {
    all(selector).forEach((node) => {
      node.style.opacity = "";
      node.style.transform = "";
    });
  });
  all(".curve polyline").forEach((node) => {
    node.style.strokeDasharray = "";
    node.style.strokeDashoffset = "";
  });
}

function main() {
  if (REDUCED) return; // leave everything at its natural state
  try {
    heroIntro();
    revealOnScroll();
  } catch (error) {
    console.error("motion: animation failed, showing content unanimated", error);
    rescue();
  }
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", main);
} else {
  main();
}
