import glob
import json
import sys

import pandas as pd

RESULTS = "results"
TOL = 0.02
HARMONICS = [1, 2, 3, 4, 5, 6, 0.5, 1 / 3, 0.25]
MAX_RATIO = float(sys.argv[1]) if len(sys.argv) > 1 else 0.15


def tic_int(x):
    return int(str(x).replace("TIC", "").strip())


def classify(found, known):
    ratio = found / known
    for h in HARMONICS:
        if abs(ratio - h) / h < TOL:
            return "exact" if h == 1 else f"x{h:g}"
    return "wrong"


def is_candidate(r, max_ratio):
    return r["verdict"] == "candidate" and r["radius_ratio"] <= max_ratio


known_tbl = pd.read_csv("targets_known.csv")
known_tbl["tic"] = known_tbl["tic_id"].map(tic_int)
truth = known_tbl.set_index("tic").to_dict("index")

control_tbl = pd.read_csv("targets_control.csv")
matched_to = dict(zip(control_tbl["tic_id"], control_tbl["matched_to"]))

records = []
for path in glob.glob(f"{RESULTS}/*.json"):
    with open(path) as f:
        records.append(json.load(f))

k = [r for r in records if r["group"] == "known"]
k_ok = [r for r in k if r["status"] == "ok" and r["tic_id"] in truth]
k_skip = [r for r in k if r["status"] != "ok"]
c = [r for r in records if r["group"] == "control"]
c_ok = [r for r in c if r["status"] == "ok"]


def outcome(r):
    """One label per star, covering both groups."""
    if r["status"] != "ok":
        return "no_data"
    if r["group"] == "control":
        return "false_alarm" if is_candidate(r, MAX_RATIO) else "quiet"
    if not is_candidate(r, MAX_RATIO):
        return "missed"
    kind = classify(r["period_days"], truth[r["tic_id"]]["pl_orbper"])
    if kind == "exact":
        return "found"
    if kind == "wrong":
        return "wrong_period"
    return f"harmonic {kind}"


for r in records:
    r["outcome"] = outcome(r)
    if r["group"] == "known" and r["tic_id"] in truth:
        t = truth[r["tic_id"]]
        r["truth"] = {
            "planet": t["pl_name"],
            "period_days": t["pl_orbper"],
            "duration_hours": t["pl_trandur"],
            "radius_earth": t["pl_rade"],
        }
        r["position"] = {"ra": t["ra"], "dec": t["dec"],
                         "distance_pc": t["sy_dist"], "tmag": t["sy_tmag"]}
    else:
        # controls sit within one degree of their matched target — close
        # enough to share its position on a sky map at this scale
        m = matched_to.get(r["tic_id"])
        t = truth.get(m)
        r["truth"] = None
        r["position"] = ({"ra": t["ra"], "dec": t["dec"],
                          "distance_pc": t["sy_dist"], "tmag": t["sy_tmag"]}
                         if t is not None else None)

n, m_ = len(k_ok), len(c_ok)
found = [r for r in k_ok if r["outcome"].startswith(("found", "harmonic"))]
fa = [r for r in c_ok if r["outcome"] == "false_alarm"]

print("KNOWN PLANETS")
print(f"  attempted           {len(k)}")
print(f"  no usable data      {len(k_skip)}")
print(f"  analysed            {n}")
print(f"  RECALL              {len(found):3d}  {len(found)/n:6.1%}")
print("\nCONTROLS")
print(f"  analysed            {m_}")
print(f"  false alarms        {len(fa):3d}  {len(fa)/m_:6.1%}")

summary = {
    "sde_threshold": 7.0,
    "max_radius_ratio": MAX_RATIO,
    "known_analysed": n,
    "known_skipped": len(k_skip),
    "recall": len(found) / n,
    "recovered": len(found),
    "controls_analysed": m_,
    "false_alarms": len(fa),
    "false_alarm_rate": len(fa) / m_,
}

with open("summary.json", "w") as f:
    json.dump(summary, f, indent=2)

with open("site_data.json", "w") as f:
    json.dump({"summary": summary,
               "stars": sorted(records, key=lambda r: r["tic_id"])}, f, indent=2)

print(f"\nwrote site_data.json — {len(records)} stars")
