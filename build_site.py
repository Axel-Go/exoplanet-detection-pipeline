"""Build the static site from site_data.json and sweep.json."""

import json
import math
import shutil
from collections import Counter
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

ROOT = Path(__file__).parent
DATA = ROOT / "site_data.json"
SWEEP = ROOT / "sweep.json"
TEMPLATES = ROOT / "templates"
STATIC = ROOT / "static"
PLOTS_SRC = ROOT / "results" / "plots"
OUT = ROOT / "site"

# Chart geometry, in SVG user units. Full-bleed so the track below lines up.
CHART_W = 480
CHART_H = 160
CHART_TOP = 10
CHART_BOTTOM = 138
Y_MAX = 0.50

FIGURES = {
    "folded.png": "WASP-18 phase-folded on the recovered period. Every transit stacked together.",
    "periodogram.png": "Box-least-squares power against trial period. The tallest spike is the detection.",
}

CSS_CLASS = {
    "found": "ok",
    "quiet": "ok",
    "harmonic": "warn",
    "wrong_period": "warn",
    "missed": "bad",
    "false_alarm": "bad",
    "no_data": "muted",
}

PLOT_KINDS = [
    ("raw", "The light curve as downloaded",
     "One brightness measurement every two minutes for about 27 days. A transit is a "
     "dip of a fraction of a percent — usually invisible at this scale, which is the "
     "whole problem."),
    ("periodogram", "Box-least-squares periodogram",
     "How well a repeating box-shaped dip fits the data at each trial period. A real "
     "planet makes one tall, narrow spike; noise makes a lumpy plateau."),
    ("folded", "Folded on the best period",
     "Every cycle stacked on top of the others. If the period is right, the scattered "
     "dips line up into one; if it is wrong, they smear out."),
]


def css_class(outcome):
    for key, value in CSS_CLASS.items():
        if outcome.startswith(key):
            return value
    return "muted"


def num(value, digits=4):
    if value is None or value == "":
        return "—"
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return str(value)


def clean(obj):
    """Replace NaN/Infinity with null — Python writes them, JSON.parse rejects them."""
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    if isinstance(obj, dict):
        return {k: clean(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [clean(v) for v in obj]
    return obj


def explain(star, cap):
    """One sentence saying why this star ended up where it did."""
    outcome = str(star.get("outcome") or "")
    ratio = star.get("radius_ratio")
    sde = star.get("sde")

    if outcome == "no_data":
        return star.get("reason") or "No usable TESS data for this target."

    if outcome == "found":
        return ("The recovered period matches the archive to within 2%, so this counts "
                "as a clean recovery.")

    if outcome.startswith("harmonic"):
        factor = outcome.split()[-1]
        return (f"A real transit was detected, but the search locked onto {factor} the "
                "true period — a harmonic alias. Counted here as a failure, because every "
                "quantity derived from the period would be wrong by that factor.")

    if outcome == "wrong_period":
        return ("A signal cleared both cuts, but at a period unrelated to the known "
                "planet. Something repeating is here; it is not this planet.")

    if outcome == "missed":
        if star.get("verdict") != "candidate":
            return (f"The strongest peak reached SDE {num(sde, 1)}, below the detection "
                    "threshold of 7.0. Nothing was proposed, so nothing could be checked.")
        return (f"A candidate was found, but the implied planet was {num(ratio, 3)} times "
                f"the star's radius — above the {cap:.2f} size cap, so it was rejected as "
                "too large to be a planet.")

    if outcome == "false_alarm":
        return (f"No known planet orbits this star, yet a signal reached SDE {num(sde, 1)} "
                f"with an implied size of {num(ratio, 3)} — inside the size cap. This is "
                "the detector being wrong.")

    if outcome == "quiet":
        return ("No known planet, and nothing cleared the cuts. The correct answer, and "
                "the outcome 91 of the 100 control stars produced.")

    return ""



# Legend rows for the globe. The swatches must match COLORS in sky.js —
# this list is also the text alternative for the canvas, so it has to say
# the same thing the picture does.
LEGEND = [
    ("recovered",              "found",                     "#ffffff"),
    ("detected, wrong period", "harmonic wrong_period",     "#9aa0a7"),
    ("missed",                 "missed",                    "#5c6167"),
    ("no usable data",         "no_data",                   "#35383d"),
    ("false alarm",            "false_alarm",               "#b9bec5"),
    ("correctly quiet",        "quiet",                     "#484d54"),
]


def build_legend(rows):
    legend = []
    for name, match, swatch in LEGEND:
        prefixes = match.split()
        count = sum(1 for r in rows
                    if any(r["outcome"].startswith(pre) for pre in prefixes))
        legend.append({"name": name, "match": match, "swatch": swatch, "count": count})
    return legend


def pick_featured(rows):
    """Three stars worth opening, chosen from the data rather than hardcoded."""
    def best(candidates, key):
        pool = [r for r in candidates if r[key] not in ("—", None)]
        return max(pool, key=lambda r: float(r[key])) if pool else None

    found = [r for r in rows if r["outcome"] == "found"]
    alarms = [r for r in rows if r["outcome"] == "false_alarm"]
    harmonics = [r for r in rows if r["outcome"].startswith("harmonic")]

    picks = []
    star = best(found, "sde")
    if star:
        picks.append(dict(star, blurb=(
            "The clearest recovery in the set — the strongest signal of any known "
            "planet, found at the right period.")))

    star = best(alarms, "sde")
    if star:
        picks.append(dict(star, blurb=(
            "A control star with no known planet that produced the loudest signal "
            "of all. Look at the folded curve and you can see why it fooled the "
            "detector.")))

    if harmonics:
        picks.append(dict(harmonics[0], blurb=(
            "A real transit, found at six times the true period. Counted as a "
            "failure here — every quantity you would derive from it is wrong by "
            "that factor.")))

    return picks


def load_stars():
    raw = json.loads(DATA.read_text())
    return raw["stars"] if isinstance(raw, dict) else raw


def build_rows(stars, cap):
    rows = []
    for star in stars:
        truth = star.get("truth") or {}
        outcome = str(star.get("outcome") or "")
        tic = star["tic_id"]
        rows.append({
            "tic_id": tic,
            "group": star["group"],
            "outcome": outcome,
            "label": outcome.replace("_", " "),
            "cls": css_class(outcome),
            "sde": num(star.get("sde"), 1),
            "period": num(star.get("period_days")),
            "true_period": num(truth.get("period_days")),
            "depth": num(star.get("depth"), 5),
            "ratio": num(star.get("radius_ratio"), 3),
            "sector": star.get("sector"),
            "n_points": star.get("n_points"),
            "span": num(star.get("span_days"), 2),
            "duration_hours": num((star.get("duration_days") or 0) * 24, 2)
                              if star.get("duration_days") else "—",
            "planet": truth.get("planet"),
            "true_duration": num(truth.get("duration_hours"), 2),
            "radius_earth": num(truth.get("radius_earth"), 2),
            "verdict": star.get("verdict"),
            "why": explain(star, cap),
            "plots": [
                {"kind": kind, "title": title, "note": note,
                 "file": f"{tic}_{kind}.png"}
                for kind, title, note in PLOT_KINDS
                if (PLOTS_SRC / f"{tic}_{kind}.png").exists()
            ],
        })
    return rows


def build_stats(rows):
    known = [r for r in rows if r["group"] != "control"]
    control = [r for r in rows if r["group"] == "control"]
    with_data = [r for r in known if r["outcome"] != "no_data"]
    recovered = [r for r in with_data if r["outcome"] == "found"]
    alarms = [r for r in control if r["outcome"] == "false_alarm"]

    print("\noutcome breakdown")
    for group in ("known", "control"):
        counts = Counter(
            r["outcome"] for r in rows
            if (r["group"] == "control") == (group == "control")
        )
        for outcome, n in counts.most_common():
            print(f"  {group:8} {outcome:16} {n}")
    print()

    return {
        "n_total": len(rows),
        "n_known": len(known),
        "n_control": len(control),
        "known_with_data": len(with_data),
        "recovered": len(recovered),
        "missed": len(with_data) - len(recovered),
        "false_alarms": len(alarms),
        "recall_pct": f"{len(recovered) / len(with_data) * 100:.1f}",
        "far_pct": f"{len(alarms) / len(control) * 100:.1f}",
    }


def build_curve(sweep):
    """Turn the sweep into pixel coordinates. Python owns all plot maths."""
    caps = sweep["caps"]
    points = sweep["points"]
    lo, hi = caps[0], caps[-1]
    span = CHART_BOTTOM - CHART_TOP

    def x_of(cap):
        return round((cap - lo) / (hi - lo) * CHART_W, 2)

    def y_of(value):
        return round(CHART_TOP + (1 - min(value, Y_MAX) / Y_MAX) * span, 2)

    xs = [x_of(c) for c in caps]
    ys_recall = [y_of(p["recall"]) for p in points]
    ys_far = [y_of(p["false_alarm_rate"]) for p in points]

    def polyline(ys):
        return " ".join(f"{x},{y}" for x, y in zip(xs, ys))

    return {
        "w": CHART_W, "h": CHART_H, "top": CHART_TOP, "bottom": CHART_BOTTOM,
        "recall": polyline(ys_recall),
        "far": polyline(ys_far),
        "gridlines": [{"y": y_of(v), "label": f"{int(v * 100)}%"}
                      for v in (0.0, 0.25, 0.50)],
        "geom": {"x": xs, "recall": ys_recall, "far": ys_far},
    }


def sync_plots(rows, dest):
    """Copy each star's plots across, skipping ones already up to date."""
    dest.mkdir(exist_ok=True)
    copied = 0
    for row in rows:
        for plot in row["plots"]:
            src = PLOTS_SRC / plot["file"]
            out = dest / plot["file"]
            if out.exists() and out.stat().st_mtime >= src.stat().st_mtime:
                continue
            shutil.copy(src, out)
            copied += 1
    return copied


def main():
    stars = load_stars()
    sweep = json.loads(SWEEP.read_text())
    cap = sweep["default_cap"]

    rows = build_rows(stars, cap)
    stats = build_stats(rows)
    curve = build_curve(sweep)
    default_index = sweep["caps"].index(cap)
    print(f"curve: {len(sweep['caps'])} caps, default at index {default_index}")

    env = Environment(
        loader=FileSystemLoader(TEMPLATES),
        autoescape=select_autoescape(["html"]),
    )

    figures = [{"file": name, "caption": caption}
               for name, caption in FIGURES.items()
               if (ROOT / name).exists()]

    OUT.mkdir(exist_ok=True)

    pages = {
        "index.html": {"figures": figures, "curve": curve,
                       "default_index": default_index, "default_cap": cap,
                       "legend": build_legend(rows),
                       "featured": pick_featured(rows)},
        "results.html": {"rows": rows},
    }
    for name, extra in pages.items():
        html = env.get_template(name).render(root=".", stats=stats, page=name, **extra)
        (OUT / name).write_text(html)
        print(f"wrote site/{name}")

    # one page per star
    star_dir = OUT / "stars"
    star_dir.mkdir(exist_ok=True)
    template = env.get_template("star.html")
    for row in rows:
        html = template.render(root="..", stats=stats, page="star.html",
                               row=row, cap=cap)
        (star_dir / f"{row['tic_id']}.html").write_text(html)
    print(f"wrote {len(rows)} pages into site/stars/")

    copied = sync_plots(rows, OUT / "plots")
    print(f"plots: {copied} copied, rest already current")

    shutil.copytree(STATIC, OUT / "static", dirs_exist_ok=True)
    (OUT / "site_data.json").write_text(
        json.dumps(clean(json.loads(DATA.read_text())), allow_nan=False))
    sweep["geom"] = curve["geom"]
    (OUT / "sweep.json").write_text(json.dumps(clean(sweep), allow_nan=False))
    print("copied site/static/, site_data.json and sweep.json")

    if figures:
        (OUT / "figures").mkdir(exist_ok=True)
        for fig in figures:
            shutil.copy(ROOT / fig["file"], OUT / "figures" / fig["file"])


if __name__ == "__main__":
    main()
