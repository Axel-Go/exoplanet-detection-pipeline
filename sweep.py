"""Run score.py across a range of size caps and collect the trade-off curve.

The detector's only tunable knob is MAX_RATIO — the largest implied
planet-to-star radius ratio it will accept as a planet. Everything else
(period, depth, SDE) was measured once by worker.py and is frozen in
results/. So sweeping the cap means re-scoring, not re-searching.

score.py is a script rather than a module, so we drive it the way a
person would: run it, then read the file it leaves behind. That keeps
exactly one implementation of the scoring rules.
"""

import json
import subprocess
import sys

SCORE = "score.py"
DATA = "site_data.json"
OUT = "sweep.json"

CAP_MIN = 0.04
CAP_MAX = 0.40
CAP_STEP = 0.01
DEFAULT_CAP = 0.15


def caps():
    values = []
    x = CAP_MIN
    while x <= CAP_MAX + 1e-9:
        values.append(round(x, 2))
        x += CAP_STEP
    return values


def run_scorer(cap):
    """Run score.py at one cap and return what it wrote."""
    result = subprocess.run(
        [sys.executable, SCORE, f"{cap:.2f}"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"score.py failed at cap {cap}:\n{result.stderr}")
        sys.exit(1)

    with open(DATA) as f:
        return json.load(f)


def main():
    cap_list = caps()
    print(f"sweeping {len(cap_list)} caps from {CAP_MIN} to {CAP_MAX}\n")

    points = []
    outcomes = {}

    for i, cap in enumerate(cap_list):
        data = run_scorer(cap)
        s = data["summary"]

        points.append({
            "cap": cap,
            "recovered": s["recovered"],
            "known_analysed": s["known_analysed"],
            "recall": s["recall"],
            "false_alarms": s["false_alarms"],
            "controls_analysed": s["controls_analysed"],
            "false_alarm_rate": s["false_alarm_rate"],
        })

        for star in data["stars"]:
            outcomes.setdefault(str(star["tic_id"]), []).append(star["outcome"])

        print(f"  {cap:.2f}  recall {s['recall']:6.1%}   "
              f"false alarms {s['false_alarm_rate']:6.1%}   "
              f"({s['recovered']}/{s['known_analysed']}, "
              f"{s['false_alarms']}/{s['controls_analysed']})")

    # Leave site_data.json in its canonical state, and use that run as a check.
    print(f"\nrestoring site_data.json at the default cap {DEFAULT_CAP}")
    canonical = run_scorer(DEFAULT_CAP)

    # --- self-check: the sweep must agree with a standalone run ---
    swept = next(p for p in points if p["cap"] == DEFAULT_CAP)
    ref = canonical["summary"]
    for key in ("recovered", "false_alarms", "known_analysed", "controls_analysed"):
        if swept[key] != ref[key]:
            print(f"MISMATCH at cap {DEFAULT_CAP}: sweep {key}={swept[key]} "
                  f"but a standalone run says {ref[key]}")
            sys.exit(1)
    print("check passed — sweep agrees with a standalone score.py run")

    # --- self-check: loosening the cap can only ever add detections ---
    for a, b in zip(points, points[1:]):
        if b["recovered"] < a["recovered"] or b["false_alarms"] < a["false_alarms"]:
            print(f"MISMATCH: counts fell between cap {a['cap']} and {b['cap']} — "
                  "a looser cap should never detect less")
            sys.exit(1)
    print("check passed — curve is monotonic")

    with open(OUT, "w") as f:
        json.dump({
            "default_cap": DEFAULT_CAP,
            "sde_threshold": ref["sde_threshold"],
            "caps": cap_list,
            "points": points,
            "outcomes": outcomes,
        }, f, indent=2)

    print(f"\nwrote {OUT} — {len(cap_list)} caps × {len(outcomes)} stars")


if __name__ == "__main__":
    main()