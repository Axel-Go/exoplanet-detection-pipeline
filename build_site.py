"""Build the static site from site_data.json."""
import math
import json
import shutil
from collections import Counter
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

ROOT = Path(__file__).parent
DATA = ROOT / "site_data.json"
TEMPLATES = ROOT / "templates"
STATIC = ROOT / "static"
OUT = ROOT / "site"

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

def load_rows():
    raw = json.loads(DATA.read_text())
    stars = raw["stars"] if isinstance(raw, dict) else raw

    rows = []
    for star in stars:
        truth = star.get("truth") or {}
        outcome = str(star.get("outcome") or "")
        rows.append({
            "tic_id": star["tic_id"],
            "group": star["group"],
            "outcome": outcome,
            "label": outcome.replace("_", " "),
            "cls": css_class(outcome),
            "sde": num(star.get("sde"), 1),
            "period": num(star.get("period_days")),
            "true_period": num(truth.get("period_days") or truth.get("period")),
            "depth": num(star.get("depth"), 5),
            "ratio": num(star.get("radius_ratio"), 3),
            "sector": star.get("sector"),
        })
    return rows


def build_stats(rows):
    known = [r for r in rows if r["group"] != "control"]
    control = [r for r in rows if r["group"] == "control"]
    with_data = [r for r in known if r["outcome"] != "no_data"]
    recovered = [r for r in with_data if r["outcome"].startswith("found")]
    alarms = [r for r in control if r["outcome"].startswith("false_alarm")]

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


def main():
    rows = load_rows()
    stats = build_stats(rows)

    env = Environment(
        loader=FileSystemLoader(TEMPLATES),
        autoescape=select_autoescape(["html"]),
    )

    figures = [
        {"file": name, "caption": caption}
        for name, caption in FIGURES.items()
        if (ROOT / name).exists()
    ]

    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir()

    pages = {
        "index.html": {"figures": figures},
        "results.html": {"rows": rows},
    }

    for name, extra in pages.items():
        html = env.get_template(name).render(root=".", stats=stats, page=name, **extra)
        (OUT / name).write_text(html)
        print(f"wrote site/{name}")

    shutil.copytree(STATIC, OUT / "static")
    raw = json.loads(DATA.read_text())
    (OUT / "site_data.json").write_text(json.dumps(clean(raw), allow_nan=False))
    print("copied site/static/ and site/site_data.json")

    if figures:
        (OUT / "figures").mkdir()
        for fig in figures:
            shutil.copy(ROOT / fig["file"], OUT / "figures" / fig["file"])


if __name__ == "__main__":
    main()